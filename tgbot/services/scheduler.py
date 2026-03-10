import random
import logging
from aiogram import Bot
from tgbot.models.db import Database

logger = logging.getLogger(__name__)

# Пули повідомлень
MORNING_MESSAGES = [
    "Доброго ранку! Почніть свій день з чашечки запашного чаю. ☕️",
    "Прокидайтеся! Подивіться у вікно — який сьогодні чудовий день! ☀️",
    "Ранок — найкращий час для нових звершень. Бажаємо продуктивного дня! 💪",
    "Не забудьте поснідати, це важливо для вашої енергії сьогодні! 🍳"
]

EVENING_MESSAGES = [
    "Ви провели чудовий день! Тепер час для відпочинку. 🌙",
    "Вечір — час видихнути та подякувати собі за зусилля. Спокійної ночі! ✨",
    "Нехай ваш сон буде міцним, а ранок — бадьорим. Відпочивайте! 🛌",
    "Ви — молодець! Завтра буде ще кращий день. 🌟"
]


async def send_daily_motivation(bot: Bot, db: Database, time_of_day: str):
    """Розсилка приємних повідомлень Premium користувачам"""
    users = await db.get_active_premium_users_with_settings(time_of_day)  # Потрібно додати цей метод в db.py

    if time_of_day == "morning":
        text = random.choice(MORNING_MESSAGES)
    else:
        text = random.choice(EVENING_MESSAGES)

    for user_id in users:
        try:
            await bot.send_message(user_id, text)
        except Exception as e:
            logger.error(f"Не вдалося надіслати мотивацію {user_id}: {e}")


async def send_premium_reminders(bot: Bot, db: Database):
    """Нагадування про закінчення преміуму (за 1-2 дні)"""
    users = await db.get_premium_ending_users()

    text = (
        "⚠️ <b>Ваш Premium-доступ скоро закінчується!</b>\n\n"
        "Щоб не втратити можливість аналізувати їжу по фото, не забудьте поновити підписку. ✨"
    )

    for user_id in users:
        try:
            await bot.send_message(user_id, text, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Не вдалося надіслати нагадування {user_id}: {e}")


async def send_inactivity_reminders(bot: Bot, db: Database):
    """М'які нагадування та подарунки для тих, хто пропав"""

    # 1. Ті, хто не заходив 3 дні (М'яке нагадування)
    inactive_3_days = await db.get_inactive_non_premium_users(3)
    for user_id in inactive_3_days:
        try:
            await bot.send_message(
                user_id,
                "Ми сумуємо! 🍏 Не забудьте записати свій сьогоднішній обід, щоб тримати форму в тонусі."
            )
        except Exception:
            pass

    # 2. Ті, хто не заходив 7 днів (Подарунок)
    inactive_7_days = await db.get_inactive_users(7)
    for user_id in inactive_7_days:
        try:
            gave_gift = await db.check_and_give_gift_premium(user_id)
            if gave_gift:
                await bot.send_message(
                    user_id,
                    "🎁 <b>Ми приготували подарунок!</b>\n\n"
                    "Вас давно не було, тому ми даруємо вам <b>3 дні Premium</b>, "
                    "щоб ви могли знову спробувати аналіз їжі по фото. Повертайтеся! ✨",
                    parse_mode="HTML"
                )
        except Exception:
            pass