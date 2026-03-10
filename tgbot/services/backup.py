import asyncio
import logging
from datetime import datetime
from aiogram import Bot
from aiogram.types import InputFile


async def scheduled_backup(bot: Bot, admin_id: int, db_path: str):
    """Функція, яка щодня надсилає файл бази даних адміну"""
    while True:
        try:
            # Чекаємо 24 години перед наступним бекапом
            await asyncio.sleep(86400)

            # Формуємо ім'я файлу з датою
            date_str = datetime.now().strftime("%Y-%m-%d_%H-%M")
            caption = f"📦 <b>Автоматичний бекап бази</b>\n📅 Дата: {date_str}"

            # Відправляємо файл
            with open(db_path, 'rb') as db_file:
                await bot.send_document(
                    admin_id,
                    db_file,
                    caption=caption,
                    parse_mode="HTML"
                )
            logging.info(f"Бекап успішно надіслано адміну {admin_id}")

        except Exception as e:
            logging.error(f"Помилка при створенні бекапу: {e}")
            # У разі помилки чекаємо 10 хвилин і пробуємо ще раз
            await asyncio.sleep(600)