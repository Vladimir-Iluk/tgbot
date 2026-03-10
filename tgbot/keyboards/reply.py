from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def get_cancel_kb():
    """Універсальна кнопка скасування"""
    return ReplyKeyboardMarkup(resize_keyboard=True).add(KeyboardButton("Скасувати ❌"))

def get_skip_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("Пропустити ➡️"))
    kb.add(KeyboardButton("Скасувати ❌"))
    return kb

def get_gender_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.add("Чоловік", "Жінка")
    kb.add("Скасувати ❌")
    return kb

def get_goal_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.add("Схуднути", "Зберегти вагу", "Набрати масу")
    kb.add("Скасувати ❌")
    return kb

def get_activity_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.add(KeyboardButton("Мінімальна (офіс)"), KeyboardButton("Помірна (1-3 трен.)"))
    kb.add(KeyboardButton("Висока (4-5 трен.)"), KeyboardButton("Екстремальна (спортсмен)"))
    kb.add(KeyboardButton("Скасувати ❌"))
    return kb

def get_stats_menu_kb():
    """Меню вибору періоду статистики"""
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("📊 Статистика за сьогодні"))
    kb.row(KeyboardButton("📊 Статистика за тиждень"))
    kb.row(KeyboardButton("📊 Статистика за місяць"))
    kb.row(KeyboardButton("⬅️ Назад"))
    return kb

def get_main_menu_kb():
    """Оновлене головне меню (кнопка 'Статистика' тепер веде до вибору періоду)"""
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("📊 Статистика"))
    kb.row(KeyboardButton("👤 Мій профіль"), KeyboardButton("💎 Premium"), KeyboardButton("❓ Допомога"))
    return kb
def get_admin_main_kb():
    """Швидкі команди для адміна (Reply версія)"""
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("📈 Повна статистика"), KeyboardButton("👤 Пошук юзера"))
    kb.row(KeyboardButton("📣 Розсилка (всім)"), KeyboardButton("🎁 Розсилка (Premium)"))
    kb.row(KeyboardButton("🔙 Вийти з адмінки"))
    return kb