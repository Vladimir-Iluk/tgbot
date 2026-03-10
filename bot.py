import asyncio
import logging

from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.contrib.fsm_storage.redis import RedisStorage2
from aiohttp import web
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from tgbot.config import load_config
from tgbot.filters.admin import AdminFilter
from tgbot.handlers.admin import register_admin
from tgbot.handlers.echo import register_echo
from tgbot.handlers.user import register_user
from tgbot.middlewares.environment import EnvironmentMiddleware
from tgbot.models.db import Database
from tgbot.services.backup import scheduled_backup
from tgbot.services.scheduler import send_daily_motivation, send_premium_reminders, send_inactivity_reminders
from tgbot.handlers.payments import register_payments
from tgbot.services.wayforpay import process_wayforpay_callback

logger = logging.getLogger(__name__)


async def set_default_commands(bot: Bot):
    """Встановлює меню команд (кнопка 'Menu' зліва)"""
    commands = [
        types.BotCommand("start", "Головне меню"),
        types.BotCommand("stats", "Статистика за сьогодні"),
        types.BotCommand("premium", "💎 Активувати Premium"),
        types.BotCommand("profile", "Мій профіль та налаштування"),
        types.BotCommand("help", "Допомога та інфо"),
        types.BotCommand("cancel", "Скасувати дію"),
    ]
    await bot.set_my_commands(commands)


def register_all_middlewares(dp, config, db):
    dp.setup_middleware(EnvironmentMiddleware(config=config, db=db))


def register_all_filters(dp):
    dp.filters_factory.bind(AdminFilter)


def register_all_handlers(dp):
    register_admin(dp)
    register_payments(dp)
    register_user(dp)
    register_echo(dp)


async def on_startup(dp: Dispatcher):
    """Виконується при запуску бота"""
    bot = dp.bot
    db = bot.get('db')
    config = bot.get('config')

    # 1. Налаштування команд меню
    await set_default_commands(bot)

    # 2. Налаштування планувальника (APScheduler) для розсилок
    scheduler = AsyncIOScheduler(timezone="Europe/Kyiv")

    # Ранкова мотивація о 08:30 (для Premium)
    scheduler.add_job(send_daily_motivation, "cron", hour=8, minute=30, args=(bot, db, "morning"))

    scheduler.add_job(send_inactivity_reminders, "cron", hour=14, minute=0, args=(bot, db))
    # Вечірня мотивація о 23:18 (для Premium)
    scheduler.add_job(send_daily_motivation, "cron", hour=23, minute=18, args=(bot, db, "evening"))
    # Нагадування про закінчення Premium об 11:00
    scheduler.add_job(send_premium_reminders, "cron", hour=11, minute=0, args=(bot, db))

    scheduler.start()
    logger.info("APScheduler (мотивація та нагадування) запущено.")

    # 3. Запуск бекапів через asyncio.create_task (працює паралельно)
    admin_id = config.tg_bot.admin_ids[0]
    # ВАЖЛИВО: Використовуй той самий шлях, що і при ініціалізації Database в main()
    db_path = "tgbot/models/database.db"

    asyncio.create_task(scheduled_backup(bot, admin_id, db_path))
    logger.info(f"Фонова задача бекапів запущена для адміна {admin_id}.")


async def handle_wayforpay(request):
    """Ендпоінт для Service URL в кабінеті WayForPay"""
    db = request.app['db']
    bot = request.app['bot']
    config = request.app['config']

    try:
        data = await request.json()
        # Тепер функція повертає JSON-словник з підписом (WFP_RESPONSE)
        response_data = await process_wayforpay_callback(
            data, config.tg_bot.wayforpay_secret, db, bot
        )

        if response_data:
            # Повертаємо JSON-відповідь, яку вимагає WayForPay
            return web.json_response(response_data)

        # Якщо підпис невірний або виникла помилка логіки
        return web.Response(text="error", status=400)
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return web.Response(text="fail", status=500)


async def start_webhook_server(bot, config, db):
    """Запуск сервера для прийому платежів"""
    app = web.Application()
    app['db'] = db
    app['bot'] = bot
    app['config'] = config
    app.router.add_post('/payments/wayforpay', handle_wayforpay)

    runner = web.AppRunner(app)
    await runner.setup()
    # Слухаємо на порту 8080 (його треба відкрити на сервері)
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    logger.info("WayForPay Webhook server started on port 8080")
    return runner


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format=u'%(filename)s:%(lineno)d #%(levelname)-8s [%(asctime)s] - %(name)s - %(message)s',
    )
    logger.info("Starting bot")
    config = load_config(".env")

    # База даних (використовуємо один стабільний конект)
    db = Database("tgbot/models/database.db")
    await db.connect()  # Замість await db.create_tables()

    storage = RedisStorage2() if config.tg_bot.use_redis else MemoryStorage()
    bot = Bot(token=config.tg_bot.token, parse_mode='HTML')
    dp = Dispatcher(bot, storage=storage)

    # Зберігаємо об'єкти в словнику бота для доступу з хендлерів
    bot['config'] = config
    bot['db'] = db

    # Реєстрація компонентів aiogram
    register_all_middlewares(dp, config, db)
    register_all_filters(dp)
    register_all_handlers(dp)

    # Запуск сервера платежів
    webhook_runner = await start_webhook_server(bot, config, db)

    try:
        # Запуск функцій ініціалізації
        await on_startup(dp)
        # Запуск polling (отримання повідомлень Telegram)
        await dp.start_polling()
    finally:
        # Коректне завершення роботи
        await dp.storage.close()
        await dp.storage.wait_closed()
        await webhook_runner.cleanup()

        # Закриваємо з'єднання з БД, якщо такий метод передбачений
        if hasattr(db, 'close'):
            await db.close()
        elif hasattr(db, 'conn') and db.conn:
            await db.conn.close()

        session = await bot.get_session()
        await session.close()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.error("Bot stopped!")