import io
import re
from datetime import datetime
from PIL import Image

from aiogram import Dispatcher
from aiogram.types import Message, ContentType, ReplyKeyboardRemove, CallbackQuery
from aiogram.dispatcher import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.callback_data import CallbackData

from tgbot.keyboards.reply import get_gender_kb, get_skip_kb, get_goal_kb, get_main_menu_kb, get_stats_menu_kb, \
    get_cancel_kb, get_activity_kb
from tgbot.services.gemini_service import send_photo_to_gemini, send_text_to_gemini
from tgbot.config import Config
from tgbot.misc.states import RegistrationStates
from tgbot.misc.premium import check_premium

meal_cb = CallbackData("meal", "action", "id")

# --- Реєстрація та Старт ---
async def user_start(message: Message):
    db = message.bot.get('db')
    user = await db.get_user(message.from_user.id)

    # 1. Обробка реферального посилання (тільки для нових користувачів)
    if not user:
        # Отримуємо аргументи після /start (наприклад: /start 12345678)
        args = message.get_args()
        if args and args.isdigit():
            referrer_id = int(args)

            # Перевіряємо, щоб користувач не запросив сам себе
            if referrer_id != message.from_user.id:
                # Нараховуємо 3 дні Premium тому, хто запросив
                await db.add_referral_premium(referrer_id, 3)

                # Надсилаємо сповіщення запрошуючому
                try:
                    await message.bot.send_message(
                        referrer_id,
                        "🎁 <b>У вас новий реферал!</b>\n"
                        "Дякуємо за рекомендацію. Вам нараховано <b>3 дні Premium</b>.",
                        parse_mode="HTML"
                    )
                except Exception as e:
                    print(f"Не вдалося надіслати сповіщення рефереру {referrer_id}: {e}")

    # 2. Стандартна логіка відповіді бота
    if user:
        await message.reply(
            "👋 <b>З поверненням!</b>\n\n"
            "Я готовий аналізувати ваш раціон. Просто надішліть мені <b>фото страви</b> "
            "або <b>текстовий опис</b> того, що ви з'їли.",
            reply_markup=get_main_menu_kb(),
            parse_mode="HTML"
        )
    else:
        # Початок реєстрації для нового юзера
        await message.reply(
            "Вітаю! Я ваш персональний AI-дієтолог. 🍏\n"
            "Щоб я міг робити точні розрахунки, мені потрібно дізнатися трохи про вас.\n\n"
            "<b>Оберіть вашу стать:</b>",
            reply_markup=get_gender_kb(),
            parse_mode="HTML"
        )
        await RegistrationStates.waiting_for_gender.set()


async def user_help(message: Message):
    help_text = (
        "❓ <b>Допомога та команди</b>\n\n"
        "Цей бот аналізує ваше харчування за допомогою штучного інтелекту.\n\n"
        "🔹 <b>Як записати їжу?</b> Просто надішліть фото тарілки або напишіть текст (наприклад, 'обід: борщ і хліб').\n"
        "🔹 <b>Статистика:</b> Натисніть кнопку або введіть /stats.\n"
        "🔹 <b>Профіль:</b> Ваші дані та налаштування — /profile.\n"
        "🔹 <b>Premium:</b> Доступ до аналізу по фото — /premium.\n\n"
        "⚠️ <i>Примітка: Бот не є лікарем. Розрахунки орієнтовні.</i>"
    )
    await message.reply(help_text, reply_markup=get_main_menu_kb(), parse_mode="HTML")


async def process_settings_change(callback_query: CallbackQuery, state: FSMContext):
    action = callback_query.data

    if action == "change_goal":
        await callback_query.message.answer("Яка ваша нова ціль?", reply_markup=get_goal_kb())
        await RegistrationStates.waiting_for_goal.set()

    elif action == "change_weight":
        await callback_query.message.answer("Введіть вашу нову вагу (кг):", reply_markup=ReplyKeyboardRemove())
        await RegistrationStates.waiting_for_current_weight.set()

    elif action == "change_budget":
        await callback_query.message.answer("Вкажіть новий денний бюджет (грн):", reply_markup=ReplyKeyboardRemove())
        await RegistrationStates.waiting_for_budget.set()

    elif action == "full_reset":
        await callback_query.message.answer("Розпочнемо реєстрацію заново. Оберіть стать:",
                                            reply_markup=get_gender_kb())
        await RegistrationStates.waiting_for_gender.set()

    # Обов'язково відповідаємо на callback, щоб прибрати "годинник" на кнопці
    await callback_query.answer()


async def process_referral_menu(callback_query: CallbackQuery):
    bot_info = await callback_query.bot.get_me()
    # Генеруємо посилання: t.me/bot_name?start=user_id
    referral_link = f"https://t.me/{bot_info.username}?start={callback_query.from_user.id}"

    ref_text = (
        "🤝 <b>Реферальна програма</b>\n\n"
        "Запрошуйте друзів та отримуйте бонуси! За кожного друга, який зареєструється "
        "за вашим посиланням, ви отримаєте <b>3 дні Premium-доступу</b>.\n\n"
        f"🔗 <b>Ваше посилання:</b>\n<code>{referral_link}</code>\n\n"
        "<i>(Натисніть на посилання, щоб скопіювати)</i>"
    )

    # Створимо кнопку "Поділитися", щоб було зручніше
    share_kb = InlineKeyboardMarkup().add(
        InlineKeyboardButton("🚀 Поділитися з другом",
                             switch_inline_query=f"\nПривіт! Раджу цього AI-дієтолога: {referral_link}")
    )

    await callback_query.message.answer(ref_text, reply_markup=share_kb, parse_mode="HTML")
    await callback_query.answer()

async def about_help(message: Message):
    about_text = (
        "🍏 <b>Твій AI-Дієтолог: Професійний аналіз раціону</b>\n\n"
        "Цей бот створений для того, щоб зробити контроль харчування максимально простим та технологічним. "
        "Більше не потрібно вручну шукати калорійність кожного продукту — штучний інтелект зробить це за тебе!\n\n"

        "<b>Що вміє цей бот?</b>\n"
        "📸 <b>Аналіз по фото (Premium):</b> Просто сфотографуй тарілку, і я визначу склад страви, БЖВ та калорійність.\n"
        "✍️ <b>Текстовий щоденник:</b> Пиши звичайною мовою (наприклад, <i>'з'їв два банани та йогурт'</i>), і я запишу це у твою статистику.\n"
        "📊 <b>Персональні поради:</b> Я враховую твою стать, вік, вагу та цілі, щоб давати влучні рекомендації.\n"
        "💰 <b>Економія:</b> Я допомагаю підбирати раціон відповідно до твого денного бюджету на їжу.\n\n"

        "<b>Як користуватися?</b>\n"
        "1️⃣ Надішли фото страви або напиши текст.\n"
        "2️⃣ Отримай розрахунок КБЖВ.\n"
        "3️⃣ Переглядай свою статистику за день кнопкою «📊 Статистика».\n\n"

        "⚖️ <b>Disclaimer):</b>\n"
        "<i>Зверніть увагу, що цей бот використовує технології штучного інтелекту .</i>\n\n"
        "• Бот <b>не є дипломованим лікарем або дієтологом</b>. Вся інформація носить виключно ознайомчий характер.\n"
        "• Розрахунки калорійності та БЖВ є <b>орієнтовними</b> (похибка залежить від якості фото та опису).\n"
        "• Перш ніж вносити кардинальні зміни у свій раціон або розпочинати дієту, обов'язково <b>проконсультуйтеся з кваліфікованим медичним фахівцем</b>.\n"
        "• Розробники не несуть відповідальності за будь-які наслідки, пов'язані з використанням рекомендацій бота.\n\n"
        "Використовуючи бота, ви погоджуєтесь з цими умовами."
    )
    await message.reply(about_text, parse_mode="HTML")

def compress_image(image_bytes: bytes) -> bytes:
    img = Image.open(io.BytesIO(image_bytes))
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    img.thumbnail((1024, 1024))
    output = io.BytesIO()
    img.save(output, format="JPEG", quality=85)
    return output.getvalue()

async def user_settings(message: Message):
    db = message.bot.get('db')
    user = await db.get_user(message.from_user.id)
    if not user:
        return await user_start(message)

    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("🎯 Змінити ціль", callback_data="change_goal"),
        InlineKeyboardButton("⚖️ Оновити вагу", callback_data="change_weight"),
        InlineKeyboardButton("💰 Змінити бюджет", callback_data="change_budget"),
        InlineKeyboardButton("🔄 Скинути все (Реєстрація)", callback_data="full_reset")
    )

    await message.reply("⚙️ <b>Налаштування профілю</b>\n\nЩо саме ви бажаєте змінити?",
                         reply_markup=keyboard, parse_mode="HTML")


async def cancel_handler(message: Message, state: FSMContext):
    """Дозволяє користувачу перервати будь-яку активну дію (FSM)"""
    current_state = await state.get_state()

    if current_state is None:
        return await message.reply(
            "Наразі немає активних дій для скасування.",
            reply_markup=get_main_menu_kb()
        )

    await state.finish()
    await message.reply(
        "❌ <b>Дію скасовано.</b>\nПовертаємось до головного меню.",
        reply_markup=get_main_menu_kb(),
        parse_mode="HTML"
    )


async def show_stats_menu(message: Message):
    """Викликається при натисканні на '📊 Статистика' в головному меню"""
    await message.reply("Оберіть період для перегляду статистики:", reply_markup=get_stats_menu_kb())


async def process_stats(message: Message):
    """Обробляє вибір конкретного періоду (сьогодні/тиждень/місяць)"""
    db = message.bot.get('db')

    days = 1
    period_text = "сьогодні"

    if "тиждень" in message.text:
        days = 7
        period_text = "останні 7 днів"
    elif "місяць" in message.text:
        days = 30
        period_text = "останні 30 днів"

    # Виклик методу БД, який ми підготували раніше
    stats = await db.get_stats_for_period(message.from_user.id, days)

    stats_text = (
        f"📊 <b>Статистика за {period_text}:</b>\n"
        f"————————————————\n"
        f"🍏 Калорії: <b>{stats['total_calories']} ккал</b>\n"
        f"🥩 Білки: <b>{stats['total_proteins']} г</b>\n"
        f"🧀 Жири: <b>{stats['total_fats']} г</b>\n"
        f"🍞 Вуглеводи: <b>{stats['total_carbs']} г</b>\n"
        f"🍽 Кількість страв: <b>{stats['meals_count']}</b>\n"
        f"————————————————\n"
        f"Продовжуйте записувати їжу, щоб бачити динаміку! 👇"
    )
    await message.reply(stats_text, reply_markup=get_stats_menu_kb(), parse_mode="HTML")


def calculate_bmi(weight: float, height: int) -> tuple[float, str]:
    """Розраховує ІМТ та повертає значення з категорією"""
    if not weight or not height:
        return 0.0, "Недостатньо даних"

    # Формула: вага (кг) / зріст (м)^2
    height_m = height / 100
    bmi = round(weight / (height_m ** 2), 1)

    if bmi < 18.5:
        category = "Недостатня вага 🦴"
    elif 18.5 <= bmi < 25:
        category = "Норма ✅"
    elif 25 <= bmi < 30:
        category = "Надмірна вага ⚠️"
    else:
        category = "Ожиріння 🚨"

    return bmi, category


async def user_profile(message: Message):
    db = message.bot.get('db')
    user_id = message.from_user.id
    user_data = await db.get_user(user_id)

    if not user_data:
        return await user_start(message)

    user = dict(user_data)

    # --- Розрахунок ІМТ ---
    weight = float(user.get('current_weight', 0))
    height = int(user.get('height', 0))
    bmi_value, bmi_category = calculate_bmi(weight, height)
    # ----------------------

    reg_date = user.get('registration_date', "невідомо")[:10]
    prem_status = "✅ Активний" if check_premium(user) else "❌ Неактивний"

    m_status = "✅" if user.get('morning_motivation', 1) else "❌"
    e_status = "✅" if user.get('evening_motivation', 1) else "❌"

    activity_labels = {
        1.2: "Мінімальна",
        1.375: "Помірна",
        1.55: "Висока",
        1.725: "Екстремальна"
    }
    activity_text = activity_labels.get(user.get('activity'), "Не вказано")

    profile_text = (
        f"👤 <b>Ваш профіль:</b>\n"
        f"————————————————\n"
        f"📍 Ціль: <b>{user.get('goal', 'Не вказано')}</b>\n"
        f"📏 Зріст: <b>{height} см</b>\n"
        f"⚖️ Вага: <b>{weight} кг</b> (Ціль: {user.get('target_weight', '—')} кг)\n"
        f"📊 ІМТ: <b>{bmi_value}</b> ({bmi_category})\n"  # НОВИЙ РЯДОК
        f"🏃 Активність: <b>{activity_text}</b>\n"
        f"🍎 Денна норма: <b>{user.get('daily_kcal_limit', 0)} ккал</b>\n"
        f"💰 Бюджет: <b>{user.get('daily_budget', 0)} грн/день</b>\n"
        f"📅 Реєстрація: <b>{reg_date}</b>\n"
        f"💎 Premium: <b>{prem_status}</b>\n"
        f"————————————————\n"
        f"🔔 <b>Сповіщення:</b>"
    )

    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton(f"{m_status} Ранкова мотивація", callback_data="toggle_morning"),
        InlineKeyboardButton(f"{e_status} Вечірній підсумок", callback_data="toggle_evening"),
        InlineKeyboardButton("⚙️ Налаштування даних", callback_data="open_settings")
    )

    if isinstance(message, Message):
        await message.answer(profile_text, reply_markup=kb, parse_mode="HTML")
    elif isinstance(message, CallbackQuery):
        await message.message.edit_text(profile_text, reply_markup=kb, parse_mode="HTML")


# --- Реєстрація FSM (без змін) ---
async def set_gender(message: Message, state: FSMContext):
    await state.update_data(gender=message.text)
    await message.reply("Вкажіть ваш вік:", reply_markup=get_cancel_kb())
    await RegistrationStates.waiting_for_age.set()


async def set_age(message: Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.reply("Будь ласка, введіть число.")

    age = int(message.text)
    if not (10 <= age <= 100):
        return await message.reply("Будь ласка, введіть реальний вік (від 10 до 100 років).")

    await state.update_data(age=age)
    await message.reply("Вкажіть ваш зріст у см (наприклад, 175):", reply_markup=get_cancel_kb())
    await RegistrationStates.waiting_for_height.set()


async def set_height(message: Message, state: FSMContext):
    if not message.text.isdigit() or not (100 <= int(message.text) <= 250):
        return await message.reply("Введіть реальний зріст у см (100-250).")

    await state.update_data(height=int(message.text))
    await message.reply("Введіть вашу поточну вагу (кг):", reply_markup=get_skip_kb())
    await RegistrationStates.waiting_for_current_weight.set()


async def set_current_weight(message: Message, state: FSMContext):
    text = message.text.replace(',', '.').strip()
    clean_text = "".join(re.findall(r"[\d.]", text))

    try:
        weight = float(clean_text)
        if not (30 <= weight <= 300):
            return await message.reply("Вкажіть реальну вагу від 30 до 300 кг.")
    except ValueError:
        if "Пропустити" in message.text:
            weight = 70 # Дефолтне значення, якщо пропустили
        else:
            return await message.reply("Будь ласка, введіть число (наприклад: 75).")

    await state.update_data(current_weight=weight)
    await message.reply("Який ваш рівень фізичної активності?", reply_markup=get_activity_kb())
    await RegistrationStates.waiting_for_activity.set()


async def set_activity(message: Message, state: FSMContext):
    activity_map = {
        "Мінімальна (офіс)": 1.2,
        "Помірна (1-3 трен.)": 1.375,
        "Висока (4-5 трен.)": 1.55,
        "Екстремальна (спортсмен)": 1.725
    }
    # Отримуємо коефіцієнт, якщо кнопка не збігається — ставимо 1.2
    coef = activity_map.get(message.text, 1.2)
    await state.update_data(activity=coef)

    await message.reply("Яка ваша ціль?", reply_markup=get_goal_kb())
    await RegistrationStates.waiting_for_goal.set()

async def set_target_weight(message: Message, state: FSMContext):
    text = message.text.replace(',', '.').strip()
    clean_text = "".join(re.findall(r"[\d.]", text))

    if "Пропустити" in message.text:
        target = "Не вказано"
    elif clean_text:
        target = clean_text
    else:
        return await message.reply("Введіть число або натисніть 'Пропустити'.")

    await state.update_data(target_weight=target)
    await message.reply("Ваш орієнтовний денний бюджет на їжу (грн):", reply_markup=ReplyKeyboardRemove())
    await RegistrationStates.waiting_for_budget.set()


async def set_goal(message: Message, state: FSMContext):
    await state.update_data(goal=message.text)
    await message.reply("Яку вагу ви хочете досягти? (кг)", reply_markup=get_skip_kb())
    await RegistrationStates.waiting_for_target_weight.set()


async def set_budget(message: Message, state: FSMContext):
    # Перевірка вводу
    if not message.text.isdigit():
        return await message.reply("Введіть суму числом (наприклад: 500).")

    db = message.bot.get('db')
    user_id = message.from_user.id
    new_budget = int(message.text)

    if not (50 <= new_budget <= 10000):
        return await message.reply("Введіть реальну суму денного бюджету (від 50 до 10 000 грн).")

    # 1. Отримуємо дані з FSM (ті, що користувач вводив зараз)
    data = await state.get_data()

    # 2. Отримуємо поточні дані з бази (якщо користувач вже існує)
    user_row = await db.get_user(user_id)
    user_db = dict(user_row) if user_row else {}

    # 3. Вибираємо дані: пріоритет у того, що в FSM (нові дані),
    # якщо в FSM порожньо (це було оновлення одного поля) — беремо старі з БД.
    gender = data.get('gender') or user_db.get('gender')
    age = data.get('age') or user_db.get('age')
    weight = data.get('current_weight') or user_db.get('current_weight')

    # НОВІ ПОЛЯ ДЛЯ КБЖВ
    height = data.get('height') or user_db.get('height', 170)
    activity = data.get('activity') or user_db.get('activity', 1.2)

    goal = data.get('goal') or user_db.get('goal')
    target_weight = data.get('target_weight') or user_db.get('target_weight')

    # Якщо немає статі — значить реєстрація зламалася, просимо почати спочатку
    if not gender:
        await message.reply("❌ Виникла помилка. Спробуйте пройти реєстрацію заново /start.")
        await state.finish()
        return

    # 4. Зберігаємо оновлені дані в БД.
    # Оскільки в add_user ми додали height та activity, передаємо їх сюди.
    await db.add_user(
        user_id=user_id,
        gender=gender,
        age=age,
        weight=weight,
        height=height,
        activity=activity,
        goal=goal,
        target_weight=target_weight,
        budget=new_budget
    )

    # Завершуємо стан FSM
    await state.finish()

    # Повідомлення залежить від того, чи був користувач у базі раніше
    if user_row:
        # Розраховуємо залишок калорій для виводу (якщо хочеш додати в повідомлення)
        await message.reply(
            f"✅ <b>Дані оновлено!</b>\n"
            f"Новий бюджет: {new_budget} грн/день.\n"
            f"Ваша норма калорій була перерахована автоматично.",
            reply_markup=get_main_menu_kb(),
            parse_mode="HTML"
        )
    else:
        await message.reply(
            "✅ <b>Реєстрація завершена!</b>\n\n"
            "Ми розрахували ваші норми КБЖВ.\n"
            "🎁 Вам надано <b>7 днів Premium</b>!\n"
            "Тепер просто надішліть фото своєї тарілки. 📸",
            reply_markup=get_main_menu_kb(),
            parse_mode="HTML"
        )

# --- Аналіз фото та тексту ---


async def user_send_photo(message: Message, config: Config):
    db = message.bot.get('db')
    user_data = await db.get_user(message.from_user.id)
    if not user_data: return
    user = dict(user_data)

    if not check_premium(user):
        return await message.reply(
            "💎 Аналіз по фото — це функція <b>Premium</b>.\n"
            "Будь ласка, опишіть їжу текстом або активуйте подписку.",
            parse_mode="HTML"
        )

    user_context = (
        f"Користувач: {user.get('gender')}, {user.get('age')} років. "
        f"Параметри: {user.get('height')}см / {user.get('current_weight')}кг. "
        f"Активність: {user.get('activity')} (коеф. BMR). "
        f"Ціль: {user.get('goal')}. Бюджет: {user.get('daily_budget')} грн/день. "
        f"Денний ліміт: {user.get('daily_kcal_limit')} ккал."
    )

    processing_msg = await message.reply("🥗 Аналізую страву...")

    try:
        photo = message.photo[-1]
        file_in_io = io.BytesIO()
        await photo.download(destination_file=file_in_io)
        image_bytes = file_in_io.getvalue()

        # Твій оригінальний промпт
        prompt = (
            "Роль: Ти — професійний дієтолог. Твоя відповідь має бути чистою, БЕЗ символів ** для виділення.\n"
            "Завдання: Проаналізуй фото. Надай стислий звіт українською.\n"
            f"Контекст користувача: {user_context}.\n"
            f"Нотатки: {message.caption or 'відсутні'}.\n\n"
            "Структура:\n"
            "Назва: [назва]\n"
            "Склад та БЖВ: Б: [г], Ж: [г], В: [г]\n"
            "Калорійність: [число] ккал\n"
            "Оцінка балансу: [1 речення]\n"
            "Порада: [1 речення]\n\n"
            "Враховуй фізіологічні особливості (стать та вік) при оцінці порції. Для молодших користувачів акцентуй на енергії, для старших — на балансі нутрієнтів та легкості засвоєння."
            "Твоя порада має базуватися на активності користувача. Якщо активність 'Мінімальна', а страва містить багато швидких вуглеводів — попередь про це. Якщо 'Екстремальна' — підтримай вибір калорійної їжі для відновлення."
            "Враховуй фізіологічний контекст та фінансовий ліміт ({user.get('daily_budget')} грн/день). Якщо страва виглядає занадто дорогою для такого бюджету, запропонуй дешевший, але корисний аналог у пораді."
            "В КІНЦІ: DATA: dish='[назва]', kcal=[число], p=[білки], f=[жири], c=[вуглеводи]"
        )

        response = await send_photo_to_gemini(image_bytes, config.tg_bot.gemini_api_key, prompt)
        response = response.replace("**", "")

        match = re.search(
            r"DATA:\s*dish=['\"]?(.*?)['\"]?,\s*kcal[:=]\s*(\d+),\s*p[:=]\s*([\d.]+),\s*f[:=]\s*([\d.]+),\s*c[:=]\s*([\d.]+)",
            response, re.IGNORECASE)

        if match:
            dish, kcal, p, f, c = match.group(1).strip(), int(match.group(2)), float(match.group(3)), \
                float(match.group(4)), float(match.group(5))

            # Зберігаємо в БД як непідтверджене
            meal_id = await db.add_meal(message.from_user.id, kcal, p, f, c, dish, confirmed=0)

            clean_text = response.split("DATA:")[0].strip()

            kb = InlineKeyboardMarkup(row_width=2)
            kb.add(
                InlineKeyboardButton("✅ З'їв, запиши", callback_data=meal_cb.new(action="save", id=meal_id)),
                InlineKeyboardButton("❌ Не записувати", callback_data=meal_cb.new(action="cancel", id=meal_id))
            )

            await processing_msg.delete()
            await message.reply(clean_text, reply_markup=kb, parse_mode="HTML")
        else:
            await processing_msg.edit_text(response)  # Виправлено edit -> edit_text
    except Exception as e:
        print(f"Error in user_send_photo: {e}")
        await processing_msg.edit_text("⚠️ Не вдалося проаналізувати фото.")


async def user_text_advice(message: Message, config: Config):
    db = message.bot.get('db')
    user_data = await db.get_user(message.from_user.id)
    if not user_data: return
    user = dict(user_data)

    processing_msg = await message.reply("⏳ Обробляю...")
    stats = await db.get_stats_for_period(message.from_user.id, 1)

    # Твій оригінальний промпт
    prompt = (
        "Роль: Професійний дієтолог. Пиши українською, БЕЗ символів **.\n"
        f"Контекст: вага {user['current_weight']}, ціль {user['goal']}, норма {user['daily_kcal_limit']} ккал.\n"
        f"Вже спожито: {stats['total_calories']} ккал.\n"
        f"Запит: \"{message.text}\"\n\n"
        "1. Якщо це опис їжі: Назва, БЖВ, Калорійність + порада.\n"
        "   Додай в кінці: DATA: dish='[назва]', kcal=[число], p=[білки], f=[жири], c=[вуглеводи]\n"
        "2. Якщо питання: Відповідь до 5 речень."
    )

    try:
        response = await send_text_to_gemini(config.tg_bot.gemini_api_key, prompt)
        response = response.replace("**", "")

        match = re.search(
            r"DATA:\s*dish=['\"]?(.*?)['\"]?,\s*kcal[:=]\s*(\d+),\s*p[:=]\s*([\d.]+),\s*f[:=]\s*([\d.]+),\s*c[:=]\s*([\d.]+)",
            response, re.IGNORECASE)

        if match:
            dish, kcal, p, f, c = match.group(1).strip(), int(match.group(2)), float(match.group(3)), \
                float(match.group(4)), float(match.group(5))

            # Зберігаємо як непідтверджене
            meal_id = await db.add_meal(message.from_user.id, kcal, p, f, c, dish, confirmed=0)

            clean_text = response.split("DATA:")[0].strip()

            kb = InlineKeyboardMarkup(row_width=2)
            kb.add(
                InlineKeyboardButton("✅ Записати", callback_data=meal_cb.new(action="save", id=meal_id)),
                InlineKeyboardButton("❌ Просто порада", callback_data=meal_cb.new(action="cancel", id=meal_id))
            )
            await processing_msg.delete()
            await message.reply(clean_text, reply_markup=kb)
        else:
            await processing_msg.delete()
            await message.reply(response)
    except Exception as e:
        print(f"Error in user_text_advice: {e}")
        await message.reply("⚠️ Помилка Gemini API.")


async def process_meal_confirmation(callback_query: CallbackQuery, callback_data: dict):
    action = callback_data['action']
    meal_id = int(callback_data['id'])
    db = callback_query.bot.get('db')

    if action == "save":
        await db.confirm_meal(meal_id)
        await callback_query.answer("✅ Записано!")
        await callback_query.message.edit_text(
            callback_query.message.text + "\n\n📥 <b>Збережено</b>",
            parse_mode="HTML", reply_markup=None
        )
    else:
        await db.delete_meal(meal_id)
        await callback_query.answer("❌ Скасовано")
        await callback_query.message.edit_text(
            "<i>Запис скасовано.</i>",
            parse_mode="HTML", reply_markup=None
        )


async def toggle_notifications(callback_query: CallbackQuery):
    db = callback_query.bot.get('db')
    user_id = callback_query.from_user.id
    user = await db.get_user(user_id)

    if not user:
        return await callback_query.answer("Користувача не знайдено.")

    setting = "morning_motivation" if callback_query.data == "toggle_morning" else "evening_motivation"
    # Інвертуємо значення: якщо було 1, стане 0, і навпаки
    new_value = 0 if user[setting] else 1

    await db.update_notification_setting(user_id, setting, new_value)

    # Оновлюємо профіль прямо в тому ж повідомленні
    await user_profile(callback_query)
    await callback_query.answer("Оновлено!")


async def process_open_settings(callback_query: CallbackQuery):
    """Викликає меню налаштувань профілю"""
    # Ми викликаємо існуючу функцію user_settings
    await user_settings(callback_query.message)
    await callback_query.answer()


def register_user(dp: Dispatcher):
    # Список кнопок, які не повинні сприйматися як текстовий запит до Gemini
    main_menu_buttons = [
        "📊 Статистика", "📊 Статистика за сьогодні", "📊 Статистика за тиждень",
        "📊 Статистика за місяць", "👤 Мій профіль", "💎 Premium", "❓ Допомога",
        "Скасувати ❌", "Пропустити ➡️", "⬅️ Назад", "Мій профіль", "Допомога"
    ]

    # --- 1. СКАСУВАННЯ (Найвищий пріоритет) ---
    dp.register_message_handler(cancel_handler, commands=["cancel"], state="*")
    dp.register_message_handler(cancel_handler, lambda m: "Скасувати" in m.text, state="*")

    # --- 2. ГОЛОВНЕ МЕНЮ ТА КОМАНДИ ---
    dp.register_message_handler(user_start, commands=["start"], state="*")
    dp.register_message_handler(user_start, text="⬅️ Назад", state="*")

    dp.register_message_handler(user_profile, lambda m: "Мій профіль" in m.text, state="*")
    dp.register_message_handler(user_profile, commands=["profile"], state="*")

    dp.register_message_handler(show_stats_menu, text="📊 Статистика", state="*")
    dp.register_message_handler(process_stats, lambda m: "Статистика за" in m.text, state="*")
    dp.register_message_handler(user_help, text="❓ Допомога", state="*")
    dp.register_message_handler(about_help, text="💎 Premium", state="*")
    dp.register_message_handler(user_settings, commands=["settings", "change"], state="*")

    # --- 3. CALLBACKS ---
    # Обробка кнопок підтвердження їжі (action=save/cancel)
    dp.register_callback_query_handler(process_meal_confirmation, meal_cb.filter(), state="*")

    # Налаштування та сповіщення
    dp.register_callback_query_handler(process_settings_change,
                                       lambda c: c.data in ["change_goal", "change_weight", "change_budget",
                                                            "full_reset"],
                                       state="*")
    dp.register_callback_query_handler(process_open_settings, lambda c: c.data == "open_settings", state="*")
    dp.register_callback_query_handler(toggle_notifications, lambda c: c.data in ["toggle_morning", "toggle_evening"],
                                       state="*")
    dp.register_callback_query_handler(process_referral_menu, lambda c: c.data == "referral_menu", state="*")

    # --- 4. КРОКИ РЕЄСТРАЦІЇ (FSM) ---
    dp.register_message_handler(set_gender, state=RegistrationStates.waiting_for_gender)
    dp.register_message_handler(set_age, state=RegistrationStates.waiting_for_age)
    dp.register_message_handler(set_height, state=RegistrationStates.waiting_for_height)
    dp.register_message_handler(set_current_weight, state=RegistrationStates.waiting_for_current_weight)
    dp.register_message_handler(set_activity, state=RegistrationStates.waiting_for_activity)
    dp.register_message_handler(set_goal, state=RegistrationStates.waiting_for_goal)
    dp.register_message_handler(set_target_weight, state=RegistrationStates.waiting_for_target_weight)
    dp.register_message_handler(set_budget, state=RegistrationStates.waiting_for_budget)

    # --- 5. КОНТЕНТ (АНАЛІЗ) ---
    dp.register_message_handler(user_send_photo, content_types=ContentType.PHOTO, state="*")
    dp.register_message_handler(
        user_text_advice,
        lambda m: m.text not in main_menu_buttons and not m.text.startswith('/'),
        state="*"
    )