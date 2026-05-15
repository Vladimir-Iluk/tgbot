import asyncio
import logging
from google import genai
from google.genai import types as genai_types
from tgbot.misc.helpers import retry_on_error

logger = logging.getLogger(__name__)

GEMINI_MODEL = "gemini-2.5-flash"

@retry_on_error(retries=3, delay=2)
async def send_photo_to_gemini(photo_bytes: bytes, api_key: str, prompt: str) -> str:
    try:
        client = genai.Client(api_key=api_key)
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=GEMINI_MODEL,
            contents=[
                prompt,
                genai_types.Part.from_bytes(
                    data=photo_bytes,
                    mime_type="image/jpeg"
                )
            ]
        )
        return response.text
    except Exception as e:
        logger.error(f"Error in Gemini Photo API ({GEMINI_MODEL}): {e}")
        try:
            models = client.models.list()
            logger.info(f"Available models for this key: {[m.name for m in models]}")
        except:
            pass
        raise e

@retry_on_error(retries=3, delay=2)
async def send_text_to_gemini(api_key: str, prompt: str) -> str:
    """
    Відправляє лише текст для консультації або розрахунків.
    """
    try:
        client = genai.Client(api_key=api_key)
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=GEMINI_MODEL,
            contents=prompt
        )
        return response.text
    except Exception as e:
        logger.error(f"Error in Gemini Text API ({GEMINI_MODEL}): {e}")
        raise e