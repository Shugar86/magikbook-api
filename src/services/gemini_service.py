import logging
from asyncio import TimeoutError, timeout
from typing import AsyncIterator

from google import genai
from google.genai import types

from src.config import settings
from src.models.schemas import GenerateRequest

logger = logging.getLogger(__name__)

client = genai.Client(api_key=settings.google_api_key)


def build_system_prompt(request: GenerateRequest) -> str:
    return (
        f"You are a prompt engineering assistant for MagikBook — a magical Russian-language prompt library.\n"
        f"Generate an optimized, ready-to-use prompt based on:\n"
        f"- Category: {request.category}\n"
        f"- Target AI Model: {request.model}\n"
        f"- Style/Tone: {request.style}\n"
        f"- User topic/task: {request.input}\n\n"
        f"Write the prompt in Russian. Return ONLY the optimized prompt text. "
        f"No explanations, no greetings, no markdown formatting around it."
    )


class GeminiService:
    @staticmethod
    async def generate_prompt_stream(request: GenerateRequest) -> AsyncIterator[str]:
        try:
            async with timeout(settings.gemini_stream_timeout_seconds):
                stream = await client.aio.models.generate_content_stream(
                    model="gemini-2.0-flash",
                    contents=build_system_prompt(request),
                    config=types.GenerateContentConfig(
                        temperature=0.9,
                        max_output_tokens=512,
                    ),
                )
                async for chunk in stream:
                    if chunk.text:
                        yield chunk.text
        except TimeoutError:
            logger.error(
                "Gemini generation timed out after %s seconds",
                settings.gemini_stream_timeout_seconds,
            )
            yield "Ошибка генерации: превышено время ожидания ответа модели."
        except Exception as e:
            logger.error(f"Gemini generation error: {e}")
            yield f"Ошибка генерации: {str(e)}"
