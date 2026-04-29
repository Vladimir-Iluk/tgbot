import typing
from aiogram import types
from aiogram.dispatcher.filters import BoundFilter


class IsPrivateFilter(BoundFilter):
    key = 'is_private'

    def __init__(self, is_private: typing.Optional[bool] = None):
        self.is_private = is_private

    async def check(self, obj: types.Message | types.CallbackQuery):
        if self.is_private is None:
            return False

        # Якщо це CallbackQuery, беремо чат з message
        chat = obj.message.chat if isinstance(obj, types.CallbackQuery) else obj.chat

        is_chat_private = chat.type == types.ChatType.PRIVATE

        return is_chat_private == self.is_private