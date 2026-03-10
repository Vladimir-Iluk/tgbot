import logging
from aiogram import Dispatcher, types

logger = logging.getLogger(__name__)


async def show_premium_info(message: types.Message):
    """Виставляє рахунок через Telegram Stars"""
    user_id = message.from_user.id

    # Ціна в зірках. Наприклад, 100 зірок.
    # Оскільки Stars — це цифрова валюта, provider_token залишаємо порожнім.
    prices = [types.LabeledPrice(label="Premium 30 днів", amount=225)]

    # Текст залишаємо без змін, як ти просив
    text = (
        "💎 <b>Premium підписка (30 днів)</b>\n\n"
        "Premium надає доступ до аналізу страв по фото, розширеної статистики та щоденної мотивації.\n\n"
        "💰 Ціна: <b>489 зірок / міс</b>\n\n"
        "<i>Бот надішле вам повідомлення, як тільки транзакція буде підтвержена.</i>"
    )

    # Inline-кнопки (тексти та структура збережені)
    kb = types.InlineKeyboardMarkup(row_width=1)
    # Перша кнопка (pay=True) автоматично підтягне ціну Stars
    kb.add(
        types.InlineKeyboardButton("💳 Оформити підписку", pay=True),
        # Кнопку статусу залишаємо для вигляду, хоча Stars активуються миттєво
        types.InlineKeyboardButton("🔄 Перевірити статус", callback_data=f"check_status_{user_id}"),
        types.InlineKeyboardButton("🤝 Реферальна система", callback_data="referral_menu")
    )

    await message.bot.send_invoice(
        chat_id=user_id,
        title="Premium підписка",
        description="Доступ до аналізу страв по фото на 30 днів",
        provider_token="",  # Для Telegram Stars порожньо
        currency="XTR",  # Валюта Stars
        prices=prices,
        payload=f"premium_30_{user_id}",
        start_parameter="premium_pay",
        reply_markup=kb  # Передаємо нашу клавіатуру з текстом
    )


async def process_pre_checkout_query(pre_checkout_query: types.PreCheckoutQuery):
    """Технічне підтвердження платежу (обов'язково для Stars)"""
    await pre_checkout_query.bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)


async def success_payment(message: types.Message):
    """Логіка активації Premium після отримання зірок"""
    db = message.bot.get('db')
    user_id = message.from_user.id

    # Нараховуємо 30 днів у БД
    await db.set_premium(user_id, 30)

    await message.answer(
        "✅ <b>Ваш Premium активний!</b>\n"
        "Ви можете користуватися всіма функціями бота.",
        parse_mode="HTML"
    )


async def process_referral_menu(callback_query: types.CallbackQuery):
    """Видає реферальне посилання користувачу (без змін)"""
    bot_info = await callback_query.bot.get_me()
    referral_link = f"https://t.me/{bot_info.username}?start={callback_query.from_user.id}"

    ref_text = (
        "🤝 <b>Реферальна програма</b>\n\n"
        "Запрошуйте друзів та отримуйте бонуси! За кожного друга, який зареєструється "
        "за вашим посиланням, ви отримаєте <b>3 дні Premium-доступу</b>.\n\n"
        f"🔗 <b>Ваше посилання:</b>\n<code>{referral_link}</code>\n\n"
        "<i>(Натисніть на посилання, щоб скопіювати)</i>"
    )

    share_kb = types.InlineKeyboardMarkup().add(
        types.InlineKeyboardButton("🚀 Поділитися з другом",
                                   switch_inline_query=f"\nРаджу цього AI-дієтолога: {referral_link}")
    )

    await callback_query.message.answer(ref_text, reply_markup=share_kb, parse_mode="HTML")
    await callback_query.answer()


async def check_premium_status_callback(call: types.CallbackQuery):
    """Перевірка статусу (без змін логіки)"""
    db = call.bot.get('db')
    user_id = call.from_user.id
    await call.answer("🔄 Перевіряю статус підписки...")

    user_data = await db.get_user(user_id)
    from tgbot.misc.premium import check_premium
    user = dict(user_data) if user_data else {}

    if check_premium(user):
        await call.message.answer(
            "✅ <b>Ваш Premium активний!</b>\n"
            "Ви можете користуватися всіма функціями бота.",
            parse_mode="HTML"
        )
    else:
        await call.answer(
            "⌛ Оплата ще обробляється або не була здійснена.",
            show_alert=True
        )


def register_payments(dp: Dispatcher):
    """Реєстрація хендлерів"""
    dp.register_message_handler(show_premium_info, text="💎 Premium", state="*")
    dp.register_message_handler(show_premium_info, commands=["premium"], state="*")

    # Технічні хендлери для Stars
    dp.register_pre_checkout_query_handler(process_pre_checkout_query, lambda q: True)
    dp.register_message_handler(success_payment, content_types=types.ContentTypes.SUCCESSFUL_PAYMENT)

    dp.register_callback_query_handler(
        check_premium_status_callback,
        lambda c: c.data.startswith("check_status_"),
        state="*"
    )
    dp.register_callback_query_handler(
        process_referral_menu,
        lambda c: c.data == "referral_menu",
        state="*"
    )