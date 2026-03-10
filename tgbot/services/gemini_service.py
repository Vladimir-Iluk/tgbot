import asyncio
import google.generativeai as genai
import logging
from tgbot.misc.helpers import retry_on_error

logger = logging.getLogger(__name__)


@retry_on_error(retries=3, delay=2)
async def send_photo_to_gemini(photo_bytes: bytes, api_key: str, prompt: str) -> str:
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')

        contents = [
            prompt,
            {'mime_type': 'image/jpeg', 'data': photo_bytes}
        ]

        # Виконуємо блокуючий виклик в окремому потоці
        response = await asyncio.to_thread(model.generate_content, contents)
        return response.text
    except Exception as e:
        logger.error(f"Error in Gemini Photo API: {e}")
        raise e


@retry_on_error(retries=3, delay=2)
async def send_text_to_gemini(api_key: str, prompt: str) -> str:
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')

        response = await asyncio.to_thread(model.generate_content, prompt)
        return response.text
    except Exception as e:
        logger.error(f"Error in Gemini Text API: {e}")
        raise e