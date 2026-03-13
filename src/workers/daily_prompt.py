"""
Daily prompt worker: generates a fresh "Spell of the Day" via Gemini and saves it to DB.
Uses arq cron — registered in WorkerSettings (see elo_flush.py combined worker).
"""
import logging

from arq.connections import RedisSettings
from arq.cron import cron

from src.database import async_session_maker
from src.models.db_models import Prompt
from src.models.schemas import GenerateRequest
from src.redis_client import init_redis, close_redis
from src.services.gemini_service import GeminiService

logger = logging.getLogger(__name__)


async def refresh_daily_prompt(ctx: dict = None):
    """
    Generates a new daily prompt via Gemini and inserts it into the DB.
    Run every day at 00:00 UTC via arq cron.
    """
    logger.info("Generating daily spell of the day...")
    request = GenerateRequest(
        category="daily",
        model="gemini-2.0-flash",
        style="magic",
        input=(
            "Придумай уникальный, вдохновляющий промпт для нейросети — "
            "что-то магическое, творческое или неожиданное. "
            "Верни только сам промпт, без пояснений."
        ),
    )

    prompt_text = ""
    async for chunk in GeminiService.generate_prompt_stream(request):
        prompt_text += chunk

    if not prompt_text.strip():
        logger.error("Daily prompt generation returned empty text.")
        return

    async with async_session_maker() as session:
        new_prompt = Prompt(
            title="Заклинание дня",
            prompt_text=prompt_text.strip(),
            media_type="text",
            category="daily",
            is_trending=True,   # make it visible in feed
            is_new=True,
        )
        session.add(new_prompt)
        await session.commit()
        logger.info("Daily spell of the day saved to DB: %s...", prompt_text[:60])


# ─── Arq Worker Settings (combined with elo_flush) ────────────────────────────

from src.workers.elo_flush import process_elo_flush


class WorkerSettings:
    """Main arq worker — runs both ELO flush (every 5 min) and daily prompt (00:00 UTC)."""
    redis_settings = RedisSettings(host="localhost", port=6379, database=0)
    on_startup = [init_redis]
    on_shutdown = [close_redis]
    functions = [process_elo_flush, refresh_daily_prompt]
    cron_jobs = [
        cron(refresh_daily_prompt, hour=0, minute=0),  # 00:00 UTC daily
    ]
