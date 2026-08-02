"""Regression tests for Redis lookup queue script edge cases."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.services.lookup_execution_coordinator.redis_store import (
    QUEUE_KEY,
    QUEUE_SEEN_KEY,
    RedisLookupCoordinationStore,
)
from tests.test_lookup_coordination_store import FakeManager


@pytest.mark.asyncio
async def test_enqueue_rejects_missing_push_result_and_cleans_dedup_marker() -> None:
    """A failed queue push must not leave a job permanently deduplicated."""
    manager = FakeManager()
    store = RedisLookupCoordinationStore(manager)
    job_id = uuid4()

    async def failed_rpush(key: str, value: str) -> None:
        del key, value
        return None

    manager.redis.rpush = failed_rpush  # type: ignore[method-assign]

    with pytest.raises(RuntimeError, match="queue enqueue failed"):
        await store.enqueue(job_id)

    assert str(job_id) not in manager.redis.sets.get(QUEUE_SEEN_KEY, set())
    assert manager.redis.lists.get(QUEUE_KEY, []) == []


@pytest.mark.asyncio
async def test_empty_pop_does_not_change_queue_deduplication_state() -> None:
    """An empty queue must not remove a marker for a job that is not queued."""
    manager = FakeManager()
    store = RedisLookupCoordinationStore(manager)
    job_id = uuid4()
    manager.redis.sets[QUEUE_SEEN_KEY] = {str(job_id)}

    assert await store.pop() is None
    assert manager.redis.sets[QUEUE_SEEN_KEY] == {str(job_id)}
