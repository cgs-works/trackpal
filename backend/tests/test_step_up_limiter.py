"""Tests for the Redis-backed step-up rate limiter.

Uses a minimal in-memory fake Redis to avoid real infrastructure.
"""

from __future__ import annotations


import pytest

from app.services.step_up_limiter import (
    StepUpError,
    StepUpRateLimiter,
    StepUpRedisError,
)

pytestmark = pytest.mark.asyncio


class _FakeRedis:
    """Minimal in-memory fake for redis.asyncio.Redis methods used by the limiter."""

    def __init__(self) -> None:
        self.store: dict[str, str | bytes] = {}
        self.ttls: dict[str, float] = {}
        self.sorted_sets: dict[str, dict[str, float]] = {}

    async def get(self, key: str) -> str | None:
        val = self.store.get(key)
        if isinstance(val, bytes):
            return val.decode()
        return val  # type: ignore[return-value]

    async def delete(self, key: str) -> int:
        self.store.pop(key, None)
        self.ttls.pop(key, None)
        self.sorted_sets.pop(key, None)
        return 1

    async def ttl(self, key: str) -> int:
        if key in self.ttls:
            return int(self.ttls[key])
        return -2

    async def expire(self, key: str, seconds: int) -> None:
        self.ttls[key] = float(seconds)

    async def zadd(self, key: str, mapping: dict[str | bytes, float]) -> None:
        if key not in self.sorted_sets:
            self.sorted_sets[key] = {}
        for member, score in mapping.items():
            member_str = member.decode() if isinstance(member, bytes) else member
            self.sorted_sets[key][member_str] = score

    async def zremrangebyscore(
        self, key: str, min_score: float, max_score: float
    ) -> int:
        if key not in self.sorted_sets:
            return 0
        to_remove = [
            m for m, s in self.sorted_sets[key].items() if min_score <= s <= max_score
        ]
        for m in to_remove:
            del self.sorted_sets[key][m]
        return len(to_remove)

    async def zcard(self, key: str) -> int:
        if key not in self.sorted_sets:
            return 0
        return len(self.sorted_sets[key])

    def pipeline(self) -> _FakePipeline:
        return _FakePipeline(self)


class _FakePipeline:
    """Minimal pipeline that batches operations and executes sequentially."""

    def __init__(self, redis: _FakeRedis) -> None:
        self._redis = redis
        self._commands: list[tuple] = []

    def zadd(self, key: str, mapping: dict[str | bytes, float]) -> "_FakePipeline":
        self._commands.append(("zadd", key, mapping))
        return self

    def zremrangebyscore(
        self, key: str, min_score: float, max_score: float
    ) -> "_FakePipeline":
        self._commands.append(("zremrangebyscore", key, min_score, max_score))
        return self

    def zcard(self, key: str) -> "_FakePipeline":
        self._commands.append(("zcard", key))
        return self

    def expire(self, key: str, seconds: int) -> "_FakePipeline":
        self._commands.append(("expire", key, seconds))
        return self

    async def execute(self) -> list:
        results = []
        for cmd in self._commands:
            op = cmd[0]
            if op == "zadd":
                await self._redis.zadd(cmd[1], cmd[2])
                results.append(1)
            elif op == "zremrangebyscore":
                r = await self._redis.zremrangebyscore(cmd[1], cmd[2], cmd[3])
                results.append(r)
            elif op == "zcard":
                r = await self._redis.zcard(cmd[1])
                results.append(r)
            elif op == "expire":
                await self._redis.expire(cmd[1], cmd[2])
                results.append(True)
        return results


class _FakeManager:
    """Duck-typed connection manager that delegates execute() to _FakeRedis."""

    def __init__(self, redis: _FakeRedis) -> None:
        self._redis = redis

    async def execute(self, operation_name: str, async_callable):
        return await async_callable(self._redis)


@pytest.fixture
def fake_redis() -> _FakeRedis:
    return _FakeRedis()


@pytest.fixture
def limiter(fake_redis: _FakeRedis) -> StepUpRateLimiter:
    return StepUpRateLimiter(_FakeManager(fake_redis))


# ── Tests ──────────────────────────────────────────────────────


async def test_allows_first_attempt(limiter: StepUpRateLimiter):
    """A fresh actor is not rate-limited."""
    await limiter.check("actor-1")  # should not raise


async def test_blocks_after_three_failures(limiter: StepUpRateLimiter):
    """Three failures within the window block further attempts."""
    actor = "actor-2"
    await limiter.check(actor)
    await limiter.record_failure(actor)
    await limiter.record_failure(actor)
    await limiter.record_failure(actor)

    with pytest.raises(StepUpError, match="Too many failed attempts"):
        await limiter.check(actor)


async def test_success_resets_counter(limiter: StepUpRateLimiter):
    """A successful attempt resets the failure count."""
    actor = "actor-3"
    await limiter.record_failure(actor)
    await limiter.record_failure(actor)
    await limiter.record_success(actor)
    await limiter.check(actor)  # should not raise


async def test_two_failures_then_success_then_three_more(limiter: StepUpRateLimiter):
    """After success, failure counter resets and allows 3 new failures."""
    actor = "actor-4"
    await limiter.record_failure(actor)
    await limiter.record_failure(actor)
    await limiter.record_success(actor)

    await limiter.record_failure(actor)
    await limiter.record_failure(actor)
    await limiter.record_failure(actor)

    with pytest.raises(StepUpError):
        await limiter.check(actor)


async def test_different_actors_independent(limiter: StepUpRateLimiter):
    """Rate limit is per-actor, not global."""
    await limiter.record_failure("actor-a")
    await limiter.record_failure("actor-a")
    await limiter.record_failure("actor-a")

    await limiter.check("actor-b")  # should not raise


async def test_redis_unavailable_check_raises_step_up_redis_error():
    """When Redis is unavailable, check() raises StepUpRedisError."""

    class _BrokenManager:
        async def execute(self, operation_name: str, async_callable):
            msg = "Redis connection refused"
            raise ConnectionError(msg)

    broken = StepUpRateLimiter(_BrokenManager())
    with pytest.raises(StepUpRedisError):
        await broken.check("actor-c")


async def test_redis_unavailable_record_failure_raises_step_up_redis_error():
    """When Redis is unavailable, record_failure() raises StepUpRedisError."""

    class _BrokenManager:
        async def execute(self, operation_name: str, async_callable):
            msg = "Redis connection refused"
            raise ConnectionError(msg)

    broken = StepUpRateLimiter(_BrokenManager())
    with pytest.raises(StepUpRedisError):
        await broken.record_failure("actor-d")
