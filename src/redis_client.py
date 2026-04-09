"""
Redis client with automatic fallback:
- If REDIS_URL is set in env: uses real redis.asyncio with full TTL support
- Otherwise: uses enhanced in-memory stub (dev mode, supports expire/setex)
"""
import asyncio
import logging
import time
from collections import defaultdict
from typing import Any

from src.config import settings

logger = logging.getLogger(__name__)


# ─── In-memory fallback (dev) ────────────────────────────────────────────────

class _InMemoryRedis:
    """Thread-safe in-memory Redis stub with TTL support for development."""

    def __init__(self):
        self._store: dict[str, Any] = {}
        self._expires: dict[str, float] = {}  # key → expiry timestamp

    def _is_expired(self, key: str) -> bool:
        exp = self._expires.get(key)
        if exp and time.time() > exp:
            self._store.pop(key, None)
            self._expires.pop(key, None)
            return True
        return False

    async def incr(self, key: str) -> int:
        if self._is_expired(key):
            pass
        val = int(self._store.get(key, 0)) + 1
        self._store[key] = val
        return val

    async def get(self, key: str):
        if self._is_expired(key):
            return None
        return self._store.get(key)

    async def set(
        self,
        key: str,
        value: Any,
        ex: int | None = None,
        nx: bool = False,
    ) -> bool | None:
        """Match redis.asyncio SET: NX returns None if key already exists (and not expired)."""
        self._is_expired(key)
        exists = key in self._store
        if nx and exists:
            return None
        self._store[key] = value
        if ex is not None:
            self._expires[key] = time.time() + ex
        else:
            self._expires.pop(key, None)
        return True

    async def setex(self, key: str, seconds: int, value: Any) -> bool:
        return await self.set(key, value, ex=seconds)

    async def expire(self, key: str, seconds: int) -> bool:
        if key in self._store:
            self._expires[key] = time.time() + seconds
            return True
        return False

    async def keys(self, pattern: str) -> list[bytes]:
        """Simple glob-style key listing (supports * at end or middle)."""
        import fnmatch
        return [k.encode() for k in list(self._store.keys()) if fnmatch.fnmatch(k, pattern) and not self._is_expired(k)]

    async def delete(self, *keys):
        for k in keys:
            key = k.decode() if isinstance(k, bytes) else k
            self._store.pop(key, None)
            self._expires.pop(key, None)

    async def ping(self) -> bool:
        return True

    async def aclose(self) -> None:
        pass


# ─── Client holder ────────────────────────────────────────────────────────────

redis_client = None


async def init_redis() -> None:
    global redis_client
    if settings.redis_url:
        try:
            import redis.asyncio as aioredis
            client = aioredis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            await client.ping()
            redis_client = client
            logger.info("Connected to Redis at %s", settings.redis_url)
            return
        except Exception as e:
            logger.warning("Failed to connect to Redis (%s). Falling back to in-memory stub.", e)

    redis_client = _InMemoryRedis()
    logger.info("Using in-memory Redis stub (dev mode)")


async def close_redis() -> None:
    global redis_client
    if redis_client:
        await redis_client.aclose()
        logger.info("Redis connection closed.")
        redis_client = None


def get_redis():
    return redis_client
