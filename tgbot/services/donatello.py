import aiohttp
import socket
import logging

logger = logging.getLogger(__name__)


async def check_donatello_payment(api_key: str, target_comment: str, amount_needed: int, db) -> bool:
    # Обов'язково .to
    url = "https://donatello.to/api/v1/donations"
    headers = {"X-Token": api_key}

    # Примусово використовуємо IPv4, щоб уникнути помилок резолвінгу на Windows
    conn = aiohttp.TCPConnector(family=socket.AF_INET, ssl=False)  # ssl=False можна прибрати, якщо сертифікати OK

    try:
        async with aiohttp.ClientSession(connector=conn) as session:
            async with session.get(url, headers=headers, timeout=10) as response:
                if response.status != 200:
                    logger.error(f"Donatello API status: {response.status}")
                    return False

                data = await response.json()
                donations = data.get('content', [])

                for donation in donations:
                    comment = str(donation.get('comment', '')).strip()
                    amount = float(donation.get('amount', 0))
                    donation_id = str(donation.get('pubId'))

                    # Гнучка перевірка коментаря (регістронезалежна)
                    if target_comment.lower() in comment.lower() and amount >= amount_needed:
                        if not await db.is_donation_used(donation_id):
                            await db.mark_donation_used(donation_id)
                            return True
    except Exception as e:
        logger.error(f"Donatello Error: {e}")

    return False