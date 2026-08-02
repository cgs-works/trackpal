"""Contract tests for lookup execution coordination stores."""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

import pytest
from cryptography.fernet import Fernet

from app.core.config import settings
from app.services.lookup_execution_coordinator.fake_store import (
    FakeLookupCoordinationStore,
)
from app.services.lookup_execution_coordinator.redis_store import (
    RedisLookupCoordinationStore,
)


class FakeRedis:
    """Small async Redis double covering the coordination commands."""

    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.expiry: dict[str, float] = {}
        self.lists: dict[str, list[str]] = {}
        self.sets: dict[str, set[str]] = {}
        self.sorted_sets: dict[str, dict[str, float]] = {}

    def _expire(self, key: str) -> None:
        if self.expiry.get(key, float("inf")) <= time.monotonic():
            self.values.pop(key, None)
            self.expiry.pop(key, None)

    async def set(
        self,
        key: str,
        value: str,
        *,
        ex: int | None = None,
        nx: bool = False,
    ) -> bool:
        self._expire(key)
        if nx and (key in self.values or key in self.sets):
            return False
        self.values[key] = value
        if ex is not None:
            self.expiry[key] = time.monotonic() + ex
        return True

    async def get(self, key: str) -> str | None:
        self._expire(key)
        return self.values.get(key)

    async def delete(self, key: str) -> int:
        existed = key in self.values
        self.values.pop(key, None)
        self.expiry.pop(key, None)
        return int(existed)

    async def rpush(self, key: str, value: str) -> int:
        self.lists.setdefault(key, []).append(value)
        return len(self.lists[key])

    async def lpop(self, key: str) -> str | None:
        values = self.lists.get(key, [])
        return values.pop(0) if values else None

    async def sadd(self, key: str, value: str) -> int:
        values = self.sets.setdefault(key, set())
        before = len(values)
        values.add(value)
        return int(len(values) != before)

    async def srem(self, key: str, value: str) -> int:
        values = self.sets.get(key, set())
        existed = value in values
        values.discard(value)
        return int(existed)

    async def zadd(self, key: str, mapping: dict[str, float]) -> int:
        values = self.sorted_sets.setdefault(key, {})
        added = 0
        for member, score in mapping.items():
            if member not in values:
                added += 1
            values[member] = score
        return added

    async def zrem(self, key: str, member: str) -> int:
        values = self.sorted_sets.get(key, {})
        existed = member in values
        values.pop(member, None)
        return int(existed)

    async def zremrangebyscore(self, key: str, minimum: float, maximum: float) -> int:
        values = self.sorted_sets.get(key, {})
        members = [
            member for member, score in values.items() if minimum <= score <= maximum
        ]
        for member in members:
            values.pop(member, None)
        return len(members)

    async def zcard(self, key: str) -> int:
        return len(self.sorted_sets.get(key, {}))


class FakeManager:
    """Manager-shaped wrapper used by the Redis store contract tests."""

    def __init__(self) -> None:
        self.redis = FakeRedis()

    async def execute(self, operation_name: str, operation: Any) -> Any:
        del operation_name
        return await operation(self.redis)


@pytest.fixture(autouse=True)
def encryption_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "data_encryption_key", Fernet.generate_key().decode())


@pytest.fixture(params=["fake", "redis"])
def store(request: pytest.FixtureRequest):
    if request.param == "fake":
        return FakeLookupCoordinationStore()
    return RedisLookupCoordinationStore(FakeManager())


@pytest.mark.asyncio
async def test_duplicate_enqueue_is_harmless(store: Any) -> None:
    job_id = uuid4()

    assert await store.enqueue(job_id) is True
    assert await store.enqueue(job_id) is False
    assert await store.pop() == job_id
    assert await store.pop() is None


@pytest.mark.asyncio
async def test_only_one_dispatch_lock_wins(store: Any) -> None:
    job_id = uuid4()

    assert await store.acquire_dispatch_lock(job_id) is True
    assert await store.acquire_dispatch_lock(job_id) is False
    await store.release_dispatch_lock(job_id)
    assert await store.acquire_dispatch_lock(job_id) is True


@pytest.mark.asyncio
async def test_expired_leases_stop_counting(store: Any) -> None:
    executor_id = uuid4()
    job_id = uuid4()
    lease_id = uuid4()
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=1)

    assert await store.reserve_lease(job_id, executor_id, lease_id, expires_at) is True
    assert await store.active_count(executor_id) == 1
    assert await store.get_lease(job_id) is not None

    await asyncio.sleep(1.05)
    assert await store.active_count(executor_id) == 0

    releasable_job = uuid4()
    assert (
        await store.reserve_lease(
            releasable_job,
            executor_id,
            uuid4(),
            datetime.now(timezone.utc) + timedelta(seconds=1),
        )
        is True
    )
    await store.release_lease(releasable_job)
    assert await store.active_count(executor_id) == 0

    expired_job = uuid4()
    assert (
        await store.reserve_lease(
            expired_job,
            executor_id,
            uuid4(),
            datetime.now(timezone.utc) - timedelta(seconds=1),
        )
        is False
    )
    assert await store.active_count(executor_id) == 0


@pytest.mark.asyncio
async def test_callback_nonce_is_single_use(store: Any) -> None:
    executor_id = uuid4()

    assert await store.consume_callback_nonce(executor_id, "nonce", 60) is True
    assert await store.consume_callback_nonce(executor_id, "nonce", 60) is False


@pytest.mark.asyncio
async def test_result_is_encrypted_and_round_trips(store: Any) -> None:
    job_id = uuid4()
    result_value = "sensitive-code-654321"

    await store.put_result(job_id, "code", result_value, 120)
    assert await store.get_result(job_id) == ("code", result_value)

    if isinstance(store, RedisLookupCoordinationStore):
        raw = await store._manager.redis.get(f"lookup:result:{job_id}")
        assert raw is not None
        assert result_value not in raw
        assert "sensitive-code" not in raw


@pytest.mark.asyncio
async def test_failure_cooldown_can_be_set_and_cleared(store: Any) -> None:
    executor_id = UUID("00000000-0000-0000-0000-000000000001")

    assert await store.is_failure_cooldown_active(executor_id) is False
    await store.set_failure_cooldown(executor_id, 60)
    assert await store.is_failure_cooldown_active(executor_id) is True
    await store.clear_failure_cooldown(executor_id)
    assert await store.is_failure_cooldown_active(executor_id) is False
