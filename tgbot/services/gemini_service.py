import aiohttp
import certifi
import ssl
import base64

from tgbot.misc.helpers import retry_on_error

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent"
@retry_on_error(retries=3, delay=2)
async def send_photo_to_gemini(photo_bytes: bytes, api_key: str, prompt: str) -> str:
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    payload = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(photo_bytes).decode('utf-8')}}
            ]
        }]
    }
    headers = {'Content-Type': 'application/json', 'X-goog-api-key': api_key}
    return await _make_request(payload, headers, ssl_context)
@retry_on_error(retries=3, delay=2)
async def send_text_to_gemini(api_key: str, prompt: str) -> str:
    """Функція для текстових порад"""
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }
    headers = {'Content-Type': 'application/json', 'X-goog-api-key': api_key}
    return await _make_request(payload, headers, ssl_context)


async def _make_request(payload, headers, ssl_context):
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_context)) as session:
        async with session.post(GEMINI_URL, json=payload, headers=headers) as resp:
            if resp.status != 200:
                # Викидаємо помилку, щоб спрацював декоратор retry
                error_text = await resp.text()
                raise Exception(f"API Error {resp.status}: {error_text}")

            data = await resp.json()
            return data['candidates'][0]['content']['parts'][0]['text']