import typing
from aiogram.dispatcher.filters import BoundFilter
from tgbot.misc.premium import check_premium


class PremiumFilter(BoundFilter):
    key = 'is_premium'

    def __init__(self, is_premium: typing.Optional[bool] = None):
        self.is_premium = is_premium

    async def check(self, obj):
        if self.is_premium is None:
            return False

        db = obj.bot.get('db')
        user_data = await db.get_user(obj.from_user.id)

        # Перевіряємо статус преміуму
        is_user_premium = check_premium(user_data)

        return is_user_premium == self.is_premium