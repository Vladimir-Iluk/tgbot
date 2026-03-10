import asyncio
import logging

def retry_on_error(retries=3, delay=2):
    def decorator(func):
        async def wrapper(*args, **kwargs):
            for i in range(retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    error_msg = str(e)
                    # Якщо це помилка сервера (503) або тимчасовий збій
                    if "503" in error_msg or "Service Unavailable" in error_msg:
                        if i < retries - 1: # Якщо ще є спроби
                            logging.warning(f"Спроба {i+1} не вдалася (503). Чекаємо {delay}с...")
                            await asyncio.sleep(delay)
                            continue
                    # Якщо інша помилка (наприклад, 429 або 400) — прокидаємо її далі
                    raise e
            return await func(*args, **kwargs)
        return wrapper
    return decorator