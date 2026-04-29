import typing
from aiogram.dispatcher.filters import BoundFilter


class RegisteredFilter(BoundFilter):
    key = 'is_registered'

    def __init__(self, is_registered: typing.Optional[bool] = None):
        self.is_registered = is_registered

    async def check(self, obj):
        if self.is_registered is None:
            return False

        db = obj.bot.get('db')
        user_data = await db.get_user(obj.from_user.id)

        # Якщо user_data існує — користувач зареєстрований
        is_user_registered = bool(user_data)

        return is_user_registered == self.is_registered