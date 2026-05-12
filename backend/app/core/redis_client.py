"""Redis client lifecycle for ephemeral WhatsApp session state.

Redis stores only transient conversational state (flows, steps, temp data)
for the WhatsApp Master Console. It is NOT used for business data persistence.

Usage:
    from app.core.redis_client import get_redis

    redis = await get_redis()
    await redis.set("key", "value", ex=1800)
"""

from typing import Optional

from redis.asyncio import Redis

from app.core.config import settings

_redis: Optional[Redis] = None


async def init_redis() -> None:
    """Initialize the Redis client if redis_url is configured."""
    global _redis
    if not settings.redis_url:
        _redis = None
        return
    _redis = Redis.from_url(
        settings.redis_url,
        decode_responses=True,
    )


async def close_redis() -> None:
    """Close the Redis client connection."""
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None


async def get_redis() -> Optional[Redis]:
    """Return the Redis client instance, or None if not configured.

    Services should check for None and handle Redis unavailability gracefully.
    """
    return _redis
