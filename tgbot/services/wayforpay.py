import hashlib
import hmac
import logging
import time

logger = logging.getLogger(__name__)


def generate_signature(secret_key: str, data: list) -> str:
    """Генерує HMAC-MD5 підпис для WayForPay"""
    msg = ";".join(map(str, data))
    return hmac.new(secret_key.encode('utf-8'), msg.encode('utf-8'), hashlib.md5).hexdigest()


async def process_wayforpay_callback(data: dict, secret_key: str, db, bot):
    """Обробка вхідного Webhook від WayForPay та формування відповіді"""
    keys_for_signature = [
        'merchantAccount', 'orderReference', 'amount', 'currency',
        'authCode', 'cardPan', 'transactionStatus', 'reasonCode'
    ]

    # 1. Перевірка вхідного підпису
    sign_data = [data.get(key) for key in keys_for_signature]
    expected_signature = generate_signature(secret_key, sign_data)

    if data.get('merchantSignature') != expected_signature:
        logger.warning(f"Invalid signature for order {data.get('orderReference')}")
        return None  # Повертаємо None, щоб у main.py ви могли надіслати порожню відповідь або помилку

    order_ref = data.get('orderReference')

    # 2. Логіка активації при успішному статусі
    if data.get('transactionStatus') == 'Approved':
        try:
            # Формат orderReference: user_380953429_time
            user_id = int(order_ref.split('_')[1])

            # Нараховуємо 30 днів преміуму
            await db.set_premium(user_id, 30)

            # Повідомляємо користувача
            await bot.send_message(
                user_id,
                "💎 <b>Premium активовано!</b>\n\nДякуємо за підписку! Тепер вам доступний аналіз страв по фото."
            )
        except (IndexError, ValueError) as e:
            logger.error(f"Error parsing user_id from order {order_ref}: {e}")

    # 3. Формування обов'язкової відповіді для WayForPay (WFP_RESPONSE)
    # Згідно з документацією, ми маємо повернути JSON із підписом відповіді
    time_now = int(time.time())

    # Рядок для підпису відповіді: orderReference;status;time
    response_sign_data = [order_ref, "accept", time_now]
    response_signature = generate_signature(secret_key, response_sign_data)

    return {
        "orderReference": order_ref,
        "status": "accept",
        "time": time_now,
        "signature": response_signature
    }