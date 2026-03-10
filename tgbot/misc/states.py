from aiogram.dispatcher.filters.state import State, StatesGroup

class RegistrationStates(StatesGroup):
    waiting_for_gender = State()
    waiting_for_age = State()
    waiting_for_height = State()
    waiting_for_current_weight = State() # Поточна вага
    waiting_for_activity = State()
    waiting_for_goal = State()
    waiting_for_target_weight = State()  # Цільова вага
    waiting_for_budget = State()


class AdminStates(StatesGroup):
    waiting_for_user_id = State()