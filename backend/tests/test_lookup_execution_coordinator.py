"""Tests for external lookup executor selection and dispatch coordination."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from app.schemas.lookup_executor_protocol import HandoffResult, HandoffStatus
from app.services.lookup_execution_coordinator.selector import (
    ExecutorCapacity,
    select_executor,
)


def test_select_executor_uses_least_loaded_ratio_and_stable_ties() -> None:
    first = ExecutorCapacity(uuid4(), 1, 2, datetime(2024, 1, 1, tzinfo=timezone.utc))
    second = ExecutorCapacity(uuid4(), 2, 4, datetime(2024, 2, 1, tzinfo=timezone.utc))
    older = ExecutorCapacity(uuid4(), 0, 1, datetime(2024, 1, 1, tzinfo=timezone.utc))
    newer = ExecutorCapacity(uuid4(), 0, 1, datetime(2024, 2, 1, tzinfo=timezone.utc))

    assert select_executor([second, first]) == first
    assert select_executor([newer, older]) == older


def test_select_executor_excludes_full_capacity() -> None:
    assert select_executor([ExecutorCapacity(uuid4(), 1, 1)]) is None


@pytest.mark.asyncio
async def test_schedule_spawns_only_one_pump_for_duplicate_calls() -> None:
    from app.services.lookup_execution_coordinator.coordinator import (
        LookupExecutionCoordinator,
    )

    class Store:
        async def enqueue(self, job_id: UUID) -> bool:
            return True

    spawned: list[asyncio.Task[None]] = []

    def spawn(coro):
        task = asyncio.create_task(coro)
        spawned.append(task)
        return task

    coordinator = LookupExecutionCoordinator(
        session_factory=lambda: None,
        coordination_store=Store(),
        transport=object(),
        task_spawner=spawn,
    )
    await coordinator.schedule(uuid4())
    await coordinator.schedule(uuid4())

    assert len(spawned) == 1
    spawned[0].cancel()
    await asyncio.gather(spawned[0], return_exceptions=True)


@pytest.mark.asyncio
async def test_schedule_requeues_when_no_executor_is_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.repositories import mailbox_lookup_repository
    from app.services.lookup_execution_coordinator.coordinator import (
        LookupExecutionCoordinator,
    )

    job_id = uuid4()
    job = SimpleNamespace(id=job_id, status="pending")
    monkeypatch.setattr(
        mailbox_lookup_repository,
        "get_job",
        lambda db, requested_id: _return(job, requested_id),
    )
    store = _Store()
    coordinator = LookupExecutionCoordinator(
        session_factory=lambda: _Session(),
        coordination_store=store,
        transport=object(),
        task_spawner=store.spawn,
    )
    coordinator._select_executor = lambda db: _none()  # type: ignore[method-assign]

    await coordinator.schedule(job_id)
    await store.pump_task

    assert store.queue == [job_id]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "expected_health", "quarantined"),
    [
        (HandoffStatus.BUSY, "unknown", False),
        (HandoffStatus.SECURITY_ERROR, "unreachable", True),
        (HandoffStatus.PROTOCOL_ERROR, "unreachable", True),
    ],
)
async def test_handoff_outcomes_keep_job_pending_and_release_lease(
    monkeypatch: pytest.MonkeyPatch,
    status: HandoffStatus,
    expected_health: str,
    quarantined: bool,
) -> None:
    job, executor = _job_and_executor()
    store = _Store()
    store.outcome = status
    await _run_dispatch(monkeypatch, job, executor, store)

    assert job.status == "pending"
    assert store.released == [job.id]
    assert store.queue == [job.id]
    assert executor.health_status == expected_health
    assert executor.requires_reverification is quarantined
    assert store.cooldown is False


@pytest.mark.asyncio
async def test_accepted_handoff_transitions_processing_and_counts_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job, executor = _job_and_executor()
    store = _Store()
    store.outcome = HandoffStatus.ACCEPTED
    session = await _run_dispatch(monkeypatch, job, executor, store)

    assert job.status == "processing"
    assert job.executor_id == executor.id
    assert job.execution_attempts == 1
    assert executor.health_status == "healthy"
    assert store.released == []
    assert store.queue == []
    assert session.commits == 1


@pytest.mark.asyncio
async def test_three_transport_failures_open_cooldown_without_local_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job, executor = _job_and_executor()
    store = _Store()
    store.raise_transport = True
    coordinator, session = _configured_coordinator(monkeypatch, job, executor, store)

    for _ in range(3):
        await coordinator.schedule(job.id)
        await store.pump_task

    assert executor.health_status == "unreachable"
    assert store.cooldown is True
    assert coordinator._consecutive_failures[executor.id] == 3
    assert job.status == "pending"
    assert session.commits == 3


async def _run_dispatch(monkeypatch, job, executor, store):
    coordinator, session = _configured_coordinator(monkeypatch, job, executor, store)
    await coordinator.schedule(job.id)
    await store.pump_task
    return session


def _configured_coordinator(monkeypatch, job, executor, store):
    from app.repositories import mailbox_config_repository, mailbox_lookup_repository
    from app.repositories import lookup_executors_repository
    from app.services.lookup_execution_coordinator.coordinator import (
        LookupExecutionCoordinator,
    )

    session = _Session()
    mailbox = SimpleNamespace(
        mailbox_email="mailbox@example.com", app_password_encrypted="encrypted"
    )
    monkeypatch.setattr(
        mailbox_lookup_repository,
        "get_job",
        lambda db, job_id: _return(job, job_id),
    )
    monkeypatch.setattr(
        mailbox_config_repository,
        "get_by_id",
        lambda db, mailbox_id: _value(mailbox),
    )
    monkeypatch.setattr(
        lookup_executors_repository,
        "list_dispatchable",
        lambda db: _values([executor]),
    )
    monkeypatch.setattr(
        lookup_executors_repository,
        "update_health",
        lambda db, item, health, error=None: _health(item, health, error),
    )
    monkeypatch.setattr(
        mailbox_lookup_repository,
        "transition_status",
        lambda db, item, new_status: _transition(item, new_status),
    )
    monkeypatch.setattr(
        "app.services.lookup_execution_coordinator.coordinator.decrypt_value",
        lambda value: "app-password",
    )
    return (
        LookupExecutionCoordinator(
            session_factory=lambda: session,
            coordination_store=store,
            transport=_Transport(store),
            task_spawner=store.spawn,
        ),
        session,
    )


def _job_and_executor():
    job = SimpleNamespace(
        id=uuid4(),
        status="pending",
        mailbox_id=uuid4(),
        service_key="spotify",
        target_email="target@example.com",
        executor_id=None,
        execution_attempts=0,
        last_dispatch_error_safe=None,
    )
    executor = SimpleNamespace(
        id=uuid4(),
        max_concurrency=1,
        requires_reverification=False,
        health_status="unknown",
    )
    return job, executor


async def _return(value, requested_id):
    return value if requested_id == value.id else None


async def _none():
    return None


async def _value(value):
    return value


async def _values(value):
    return value


async def _health(item, health, error=None):
    item.health_status = health
    item.last_error_safe = error
    return item


async def _transition(item, status):
    item.status = status
    return item


class _Session:
    def __init__(self):
        self.commits = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def commit(self):
        self.commits += 1

    async def flush(self):
        return None


class _Store:
    def __init__(self):
        self.queue: list[UUID] = []
        self.released: list[UUID] = []
        self.cooldown = False
        self.outcome = HandoffStatus.ACCEPTED
        self.raise_transport = False
        self.pump_task: asyncio.Task[None] | None = None

    def spawn(self, coro):
        self.pump_task = asyncio.create_task(coro)
        return self.pump_task

    async def enqueue(self, job_id):
        if job_id not in self.queue:
            self.queue.append(job_id)
        return True

    async def pop(self):
        return self.queue.pop(0) if self.queue else None

    async def acquire_dispatch_lock(self, job_id):
        return True

    async def release_dispatch_lock(self, job_id):
        return None

    async def reserve_lease(self, job_id, executor_id, lease_id, expires_at):
        return True

    async def release_lease(self, job_id):
        self.released.append(job_id)

    async def active_count(self, executor_id):
        return 0

    async def is_failure_cooldown_active(self, executor_id):
        return self.cooldown

    async def clear_failure_cooldown(self, executor_id):
        self.cooldown = False

    async def set_failure_cooldown(self, executor_id, ttl_seconds):
        self.cooldown = True


class _Transport:
    def __init__(self, store):
        self.store = store

    async def handoff(self, executor, envelope):
        if self.store.raise_transport:
            raise OSError("offline")
        return HandoffResult(self.store.outcome, envelope["lease_id"])
