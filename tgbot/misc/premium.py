from datetime import datetime


def check_premium(user) -> bool:
    if not user:
        return False

    # sqlite3.Row не має методу .get(), використовуємо спробу доступу
    try:
        # Перевіряємо, чи є в об'єкті такий ключ і чи він не порожній
        premium_until = user['premium_until']
    except (KeyError, TypeError, IndexError):
        return False

    if not premium_until:
        return False

    try:
        until_date = datetime.fromisoformat(premium_until)
        return datetime.now() < until_date
    except (ValueError, TypeError):
        return False