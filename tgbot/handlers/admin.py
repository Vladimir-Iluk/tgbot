import asyncio
import logging
from aiogram import types, Dispatcher
from aiogram.dispatcher import FSMContext
from aiogram.utils import exceptions

from tgbot.misc.states import AdminStates
from tgbot.models.db import Database
from tgbot.keyboards.reply import get_admin_main_kb, get_main_menu_kb

logger = logging.getLogger(__name__)


# --- Допоміжна функція для безпечної розсилки ---
async def send_broadcasting(bot, user_ids, text):
    count = 0
    blocked = 0

    for user_id in user_ids:
        try:
            await bot.send_message(user_id, text, parse_mode="HTML")
            count += 1
            await asyncio.sleep(0.05)
        except (exceptions.BotBlocked, exceptions.ChatNotFound):
            blocked += 1
        except exceptions.RetryAfter as e:
            await asyncio.sleep(e.timeout)
            await bot.send_message(user_id, text, parse_mode="HTML")
            count += 1
        except Exception as e:
            logger.error(f"Помилка відправки для {user_id}: {e}")

    return count, blocked


# --- Хендлери ---

async def admin_start(message: types.Message):

    await message.reply(
        "🛠 <b>Ви увійшли в адмін-панель.</b>\n\n"
        "Оберіть дію на клавіатурі або скористайтеся командами.",
        reply_markup=get_admin_main_kb(),
        parse_mode="HTML"
    )


async def admin_stats_cmd(message: types.Message):

    db: Database = message.bot.get('db')
    stats = await db.get_advanced_stats()

    text = (
        "📊 <b>АДМІН-СТАТИСТИКА</b>\n"
        "————————————————\n"
        f"👥 Всього юзерів: <b>{stats['total_users']}</b>\n"
        f"🔥 Активність (24г): <b>{stats['active_today']}</b>\n"
        f"💎 Активних Premium: <b>{stats['active_premium']}</b>\n"
        "————————————————\n"
        f"📸 Фото-аналізів: <b>{stats['total_photos']}</b>\n"
        f"💬 Текстових запитів: <b>{stats['total_messages']}</b>\n"
        "————————————————"
    )
    await message.reply(text, parse_mode="HTML")


async def give_premium_cmd(message: types.Message):
    """Видача Premium за ID: /give_premium 123456 30"""
    args = message.get_args().split()
    if len(args) != 2:
        return await message.reply("❌ Формат: <code>/give_premium ID ДНІ</code>", parse_mode="HTML")

    try:
        user_id, days = int(args[0]), int(args[1])
        if days <= 0:
            return await message.reply("❌ Кількість днів повинна бути більшою за 0.")

        db: Database = message.bot.get('db')
        await db.set_premium(user_id, days)
        await message.reply(f"✅ Premium активовано для <b>{user_id}</b> на {days} днів!", parse_mode="HTML")
    except ValueError:
        await message.reply("❌ ID та дні мають бути числами!")


async def ask_user_id_for_info(message: types.Message):
    # Якщо команда введена з аргументом (наприклад /info 123), відразу обробляємо
    args = message.get_args()
    if args and args.isdigit():
        message.text = args
        return await process_user_search(message, None)

    await message.reply("Введіть Telegram ID користувача, якого хочете знайти:")
    await AdminStates.waiting_for_user_id.set()


async def process_user_search(message: types.Message, state: FSMContext = None):

    user_id_text = message.text.strip()
    if not user_id_text.isdigit():
        return await message.reply("❌ ID має складатися лише з цифр. Спробуйте ще раз.")

    db: Database = message.bot.get('db')
    data = await db.get_user_full_info(int(user_id_text))

    if not data:
        if state: await state.finish()
        return await message.reply("❌ Користувача з таким ID не знайдено.")

    u = data['info']
    reg_date = u['registration_date'][:10] if u['registration_date'] else "Невідомо"
    prem_until = u['premium_until'][:10] if u['premium_until'] else "Відсутній"

    text = (
        f"👤 <b>Картка користувача: {u['user_id']}</b>\n"
        f"————————————————\n"
        f"📍 Ціль: {u['goal']}\n"
        f"⚖️ Вага: {u['current_weight']}\n"
        f"💰 Бюджет: {u['daily_budget']} грн\n"
        f"📅 Реєстрація: {reg_date}\n"
        "————————————————\n"
        f"🍎 Сьогодні спожито: <b>{data['today_calories']} ккал</b>\n"
        f"💎 Premium до: <b>{prem_until}</b>\n"
        "————————————————"
    )
    await message.reply(text, parse_mode="HTML")
    if state: await state.finish()


async def broadcast_all_cmd(message: types.Message):

    text = message.get_args()
    if not text:
        return await message.reply("❌ Введіть текст після команди:\n<code>/broadcast Текст</code>", parse_mode="HTML")

    db: Database = message.bot.get('db')
    users = await db.get_all_users_ids()

    status_msg = await message.reply(f"🚀 Починаю розсилку на <b>{len(users)}</b> юзерів...", parse_mode="HTML")
    success, blocked = await send_broadcasting(message.bot, users, text)
    await status_msg.edit_text(f"✅ <b>Розсилка завершена!</b>\n📥 Отримали: {success}\n🚫 Заблокували: {blocked}",
                               parse_mode="HTML")


async def broadcast_premium_ending_cmd(message: types.Message):

    db: Database = message.bot.get('db')
    users = await db.get_premium_ending_users()

    if not users:
        return await message.reply("Сьогодні немає користувачів з терміном Premium, що минає.")

    text = (
        "⚠️ <b>Ваш Premium-доступ закінчується!</b>\n\n"
        "Не забудьте поновити підписку, щоб зберегти доступ до фото-аналізу."
    )

    status_msg = await message.reply(f"⏳ Надсилаю нагадування {len(users)} юзерам...", parse_mode="HTML")
    success, _ = await send_broadcasting(message.bot, users, text)
    await status_msg.edit_text(f"✅ Нагадування надіслано <b>{success}</b> користувачам.", parse_mode="HTML")


async def exit_admin(message: types.Message):

    await message.reply("🔙 Ви вийшли з адмін-панелі.", reply_markup=get_main_menu_kb())


# --- Реєстрація хендлерів ---
def register_admin(dp: Dispatcher):
    # Команда входу
    dp.register_message_handler(admin_start, commands=["admin"], is_admin=True)

    # Статистика
    dp.register_message_handler(admin_stats_cmd, commands=["admin_stats"], is_admin=True)
    dp.register_message_handler(admin_stats_cmd, text="📈 Повна статистика", is_admin=True)

    # Premium
    dp.register_message_handler(give_premium_cmd, commands=["give_premium"], is_admin=True)
    dp.register_message_handler(broadcast_premium_ending_cmd, text="🎁 Розсилка (Premium)", is_admin=True)
    dp.register_message_handler(broadcast_premium_ending_cmd, commands=["broadcast_premium"], is_admin=True)

    # Пошук юзера (через кнопку або команду)
    dp.register_message_handler(ask_user_id_for_info, text="👤 Пошук юзера", is_admin=True)
    dp.register_message_handler(ask_user_id_for_info, commands=["info"], is_admin=True)
    dp.register_message_handler(process_user_search, state=AdminStates.waiting_for_user_id, is_admin=True)

    # Загальна розсилка
    dp.register_message_handler(broadcast_all_cmd, commands=["broadcast"], is_admin=True)
    dp.register_message_handler(broadcast_all_cmd, text="📣 Розсилка (всім)", is_admin=True)

    # Вихід
    dp.register_message_handler(exit_admin, text="🔙 Вийти з адмінки", is_admin=True)