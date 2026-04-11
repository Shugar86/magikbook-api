"""Arq Redis connection helpers shared by background workers."""

from arq.connections import RedisSettings

from src.config import settings


def get_arq_redis_settings() -> RedisSettings:
    """Resolve arq broker settings from env.

    Returns:
        RedisSettings: Parsed from ``REDIS_URL`` when set, otherwise localhost
        defaults for local development.
    """
    url = (settings.redis_url or "").strip()
    if url:
        return RedisSettings.from_dsn(url)
    return RedisSettings(host="localhost", port=6379, database=0)
