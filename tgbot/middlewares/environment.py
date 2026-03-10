from aiogram import types
from aiogram.dispatcher.middlewares import LifetimeControllerMiddleware


class EnvironmentMiddleware(LifetimeControllerMiddleware):
    skip_patterns = ["error", "update"]

    def __init__(self, **kwargs):
        super().__init__()
        self.kwargs = kwargs

    async def pre_process(self, obj, data, *args):
        # Прокидаємо всі передані об'єкти (config, db тощо) у хендлери
        data.update(**self.kwargs)

        # Отримуємо об'єкт бази даних
        db = self.kwargs.get('db')

        # Логуємо дію користувача, якщо це повідомлення
        if isinstance(obj, types.Message) and obj.from_user and db:
            user_id = obj.from_user.id

            # Визначаємо тип дії для статистики
            action_type = "message"
            if obj.content_type == types.ContentType.PHOTO:
                action_type = "photo"
            elif obj.content_type == types.ContentType.TEXT and obj.text.startswith('/'):
                action_type = "command"

            # Записуємо в БД
            try:
                await db.log_action(user_id, action_type)
            except Exception as e:
                print(f"Помилка логування: {e}")