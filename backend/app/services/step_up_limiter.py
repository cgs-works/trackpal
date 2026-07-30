"""Redis-backed step-up authentication rate limiter.

Limits failed password attempts before export generation or Tenant
Deletion.  Uses a sliding 15-minute window with a threshold of 3 failed
attempts.  Successful attempts reset the counter.

Fail-closed: if Redis is unavailable, operations raise
``StepUpRedisError`` so callers can reject the request safely.
"""

from __future__ import annotations

import time
import uuid

from app.core.redis_client import RedisConnectionManager, RedisUnavailableError

# ── Constants ──────────────────────────────────────────────────
_STEP_UP_FAIL_PREFIX = "stepup:fail:"
_STEP_UP_WINDOW_SECONDS = 15 * 60  # 15 minutes
_STEP_UP_MAX_ATTEMPTS = 3


class StepUpError(Exception):
    """Generic step-up failure when the limiter blocks the request."""


class StepUpRedisError(StepUpError):
    """Redis is unavailable — operation must fail closed."""


class StepUpRateLimiter:
    """Sliding-window rate limiter for step-up authentication.

    Usage::

        limiter = StepUpRateLimiter(get_redis_manager())
        try:
            await limiter.check(actor_id)
            # verify password ...
            await limiter.record_success(actor_id)
        except StepUpError:
            # reject
    """

    def __init__(self, redis_manager: RedisConnectionManager | None) -> None:
        self._manager = redis_manager

    # ── Public API ─────────────────────────────────────────────

    async def check(self, actor_id: str) -> None:
        """Check whether *actor_id* is currently rate-limited.

        Raises ``StepUpRedisError`` if Redis cannot be reached (fail-closed).
        Raises ``StepUpError`` if the actor is currently blocked.
        Returns ``None`` when the actor may continue.
        """
        key = _STEP_UP_FAIL_PREFIX + actor_id
        try:
            count = await self._get_count(key)
        except (RedisUnavailableError, OSError, ConnectionError) as exc:
            raise StepUpRedisError("Step-up rate limiter unavailable") from exc

        if count >= _STEP_UP_MAX_ATTEMPTS:
            remaining = await self._ttl(key)
            raise StepUpError(
                f"Too many failed attempts. Try again in {int(remaining)} seconds."
            )

    async def record_failure(self, actor_id: str) -> None:
        """Record one failed attempt for *actor_id*."""
        key = _STEP_UP_FAIL_PREFIX + actor_id
        try:
            await self._manager.execute(
                "stepup_record_failure",
                lambda r: self._do_record_failure(r, key),
            )
        except (RedisUnavailableError, OSError, ConnectionError):
            # Fail-closed: caller MUST NOT proceed
            raise StepUpRedisError("Step-up rate limiter unavailable")

    async def record_success(self, actor_id: str) -> None:
        """Reset the failure counter for *actor_id* after a successful step-up."""
        key = _STEP_UP_FAIL_PREFIX + actor_id
        try:
            await self._manager.execute(
                "stepup_reset",
                lambda r: r.delete(key),
            )
        except (RedisUnavailableError, OSError, ConnectionError):
            # A successful step-up should succeed even if Redis is down.
            # The limiter fails closed only on the *check* path.
            pass

    # ── Internal ───────────────────────────────────────────────

    async def _get_count(self, key: str) -> int:
        """Return the number of recorded failures for *key*."""
        return await self._manager.execute(
            "stepup_get_count",
            lambda r: self._do_get_count(r, key),
        )

    async def _ttl(self, key: str) -> int:
        """Return remaining TTL in seconds for *key* (0 if absent)."""
        return await self._manager.execute(
            "stepup_ttl",
            lambda r: self._do_ttl(r, key),
        )

    @staticmethod
    async def _do_record_failure(redis, key: str) -> None:
        now = int(time.time())
        window_start = now - _STEP_UP_WINDOW_SECONDS
        pipe = redis.pipeline()
        pipe.zadd(key, {f"{now}:{uuid.uuid4().hex[:8]}": now})
        pipe.zremrangebyscore(key, 0, window_start)
        pipe.expire(key, _STEP_UP_WINDOW_SECONDS)
        await pipe.execute()

    @staticmethod
    async def _do_get_count(redis, key: str) -> int:
        now = int(time.time())
        window_start = now - _STEP_UP_WINDOW_SECONDS
        pipe = redis.pipeline()
        pipe.zremrangebyscore(key, 0, window_start)
        pipe.zcard(key)
        pipe.expire(key, _STEP_UP_WINDOW_SECONDS)
        results = await pipe.execute()
        return int(results[1])  # zcard result

    @staticmethod
    async def _do_ttl(redis, key: str) -> int:
        return await redis.ttl(key)


__all__ = [
    "StepUpError",
    "StepUpRateLimiter",
    "StepUpRedisError",
]
