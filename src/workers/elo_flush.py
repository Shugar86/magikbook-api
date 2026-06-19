"""
ELO flush worker: reads battle votes from Redis and applies ELO rating changes to DB.

Redis keys written by /api/battle/vote:
  battle:{prompt_id}:wins   → number of wins
  battle:{prompt_id}:losses → number of losses

This worker is run periodically (e.g. every 5 minutes via arq cron).
"""

import logging


from src.database import async_session_maker
from src.redis_client import get_redis
from src.services.elo_service import EloService
from src.models.db_models import Prompt

logger = logging.getLogger(__name__)

AVERAGE_RATING = 1200  # used when we only have wins or losses, not matched pairs


async def process_elo_flush(ctx: dict = None):
    """
    Reads all battle:*:wins keys from Redis, computes new ELO ratings,
    updates the database, and clears the processed keys.
    """
    redis = get_redis()
    if not redis:
        logger.error("ELO flush: Redis not available.")
        return

    logger.info("Starting ELO flush...")

    win_keys = await redis.keys("battle:*:wins")
    if not win_keys:
        logger.info("ELO flush: no votes to process.")
        return

    async with async_session_maker() as session:
        processed = 0
        for raw_key in win_keys:
            key = raw_key.decode() if isinstance(raw_key, bytes) else raw_key
            prompt_id = key.split(":")[1]

            wins_raw = await redis.get(key)
            losses_raw = await redis.get(f"battle:{prompt_id}:losses")

            wins = int(wins_raw) if wins_raw else 0
            losses = int(losses_raw) if losses_raw else 0

            if wins == 0 and losses == 0:
                continue

            prompt = await session.get(Prompt, prompt_id)
            if not prompt:
                logger.warning(
                    "ELO flush: prompt %s not found in DB, skipping.", prompt_id
                )
                await redis.delete(key, f"battle:{prompt_id}:losses")
                continue

            current_rating = prompt.elo_rating

            # Apply wins: each win is against an average-rated opponent
            for _ in range(wins):
                new_rating, _ = EloService.calculate_new_ratings(
                    current_rating, AVERAGE_RATING
                )
                current_rating = new_rating

            # Apply losses: each loss is against an average-rated opponent
            for _ in range(losses):
                _, new_rating = EloService.calculate_new_ratings(
                    AVERAGE_RATING, current_rating
                )
                current_rating = new_rating

            prompt.elo_rating = current_rating
            session.add(prompt)

            # Clear processed keys
            await redis.delete(key)
            await redis.delete(f"battle:{prompt_id}:losses")
            processed += 1

        await session.commit()
        logger.info("ELO flush complete: updated %d prompts.", processed)


# ─── Arq Worker Settings ──────────────────────────────────────────────────────

from src.redis_client import init_redis, close_redis  # noqa: E402
from src.workers.arq_redis import get_arq_redis_settings  # noqa: E402


async def _elo_worker_startup(ctx: dict) -> None:
    """Initialize Redis for an ELO-only arq worker.

    Args:
        ctx: Arq worker context (unused).
    """
    await init_redis()


async def _elo_worker_shutdown(ctx: dict) -> None:
    """Close Redis after an ELO-only worker stops.

    Args:
        ctx: Arq worker context (unused).
    """
    await close_redis()


class WorkerSettings:
    redis_settings = get_arq_redis_settings()
    on_startup = _elo_worker_startup
    on_shutdown = _elo_worker_shutdown
    functions = [process_elo_flush]
    # Run every 5 minutes
    from arq.cron import cron

    cron_jobs = [
        cron(process_elo_flush, minute={0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55})
    ]
