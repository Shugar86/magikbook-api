import logging
from asyncio import TimeoutError, timeout
from typing import AsyncIterator

from google import genai
from google.genai import types

from src.config import settings
from src.models.schemas import GenerateRequest

logger = logging.getLogger(__name__)

_genai_client: genai.Client | None = None


def _get_genai_client() -> genai.Client:
    """Lazily build Gemini client so API can start without GOOGLE_API_KEY."""
    global _genai_client
    key = (settings.google_api_key or "").strip()
    if not key:
        raise RuntimeError("GOOGLE_API_KEY is not configured")
    if _genai_client is None:
        _genai_client = genai.Client(api_key=key)
    return _genai_client


# Модели по приоритету: от быстрой/дешевой к запасным
# Актуальные модели по результатам проверки (23 марта 2026)
GEMINI_MODELS = [
    "gemini-2.5-flash-lite",  # Самая быстрая и дешевая (рекомендуется)
    "gemini-2.5-flash",  # Основная модель 2.5 поколения
    "gemini-2.0-flash-lite",  # Стабильная lite версия 2.0
    "gemini-2.0-flash",  # Стандартная 2.0
    "gemini-1.5-flash",  # Запасная предыдущего поколения
]


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
    async def _try_generate_with_model(
        model: str, request: GenerateRequest, timeout_seconds: int
    ) -> AsyncIterator[str]:
        """Попытка генерации с конкретной моделью."""
        try:
            genai_client = _get_genai_client()
            async with timeout(timeout_seconds):
                stream = await genai_client.aio.models.generate_content_stream(
                    model=model,
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
            raise
        except Exception as e:
            error_str = str(e).lower()
            # Проверяем на rate limit ошибки
            if (
                "429" in error_str
                or "too many requests" in error_str
                or "quota exceeded" in error_str
            ):
                raise RateLimitError(f"Rate limit for {model}: {e}")
            # Модель не найдена или недоступна - тоже пробуем следующую
            if (
                "not found" in error_str
                or "not supported" in error_str
                or "invalid model" in error_str
            ):
                logger.warning(f"Model {model} not available: {e}")
                raise RateLimitError(f"Model not available {model}: {e}")
            raise

    @staticmethod
    async def generate_prompt_stream(request: GenerateRequest) -> AsyncIterator[str]:
        last_error = None

        for model in GEMINI_MODELS:
            try:
                logger.info(f"Trying model: {model}")
                chunks = []
                async for chunk in GeminiService._try_generate_with_model(
                    model, request, settings.gemini_stream_timeout_seconds
                ):
                    chunks.append(chunk)
                    yield chunk
                # Если дошли сюда без ошибки — успех
                logger.info(f"Successfully used model: {model}")
                return
            except RateLimitError as e:
                logger.warning(f"Rate limit hit for {model}: {e}")
                last_error = e
                # Пробуем следующую модель
                continue
            except TimeoutError:
                logger.error(
                    "Gemini generation timed out after %s seconds",
                    settings.gemini_stream_timeout_seconds,
                )
                yield "Ошибка генерации: превышено время ожидания ответа модели."
                return
            except Exception as e:
                logger.error(f"Gemini generation error with {model}: {e}")
                last_error = e
                # Для других ошибок тоже пробуем fallback
                continue

        # Если все модели исчерпаны
        error_msg = f"Все модели недоступны. Последняя ошибка: {last_error}"
        logger.error(error_msg)
        yield "Ошибка генерации: квота API исчерпана. Попробуйте через минуту или обратитесь к администратору."


class RateLimitError(Exception):
    """Ошибка превышения квоты API."""

    pass
