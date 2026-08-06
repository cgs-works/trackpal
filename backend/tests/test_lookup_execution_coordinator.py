"""Tests for external lookup executor selection and dispatch coordination."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from unittest.mock import AsyncMock

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


def test_select_executor_uses_executor_id_for_final_tie_breaking() -> None:
    timestamp = datetime(2024, 1, 1, tzinfo=timezone.utc)
    lower_id = ExecutorCapacity(UUID(int=1), 0, 1, timestamp)
    higher_id = ExecutorCapacity(UUID(int=2), 0, 1, timestamp)

    assert select_executor([higher_id, lower_id]) == lower_id


def test_select_executor_excludes_full_capacity() -> None:
    assert select_executor([ExecutorCapacity(uuid4(), 1, 1)]) is None


def test_lookup_search_after_is_anchored_to_job_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import settings
    from app.services.lookup_execution_coordinator.coordinator import (
        _lookup_search_after,
    )

    requested_at = datetime(2026, 8, 5, 18, 59, tzinfo=timezone.utc)
    monkeypatch.setattr(settings, "mailbox_lookup_window_minutes", 15)

    assert _lookup_search_after(SimpleNamespace(requested_at=requested_at)) == (
        requested_at - timedelta(minutes=15)
    )


def test_remaining_lookup_budget_uses_end_to_end_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import settings
    from app.services.lookup_execution_coordinator.coordinator import (
        _remaining_lookup_budget,
    )

    requested_at = datetime(2026, 8, 5, 18, 59, tzinfo=timezone.utc)
    job = SimpleNamespace(requested_at=requested_at)
    monkeypatch.setattr(
        settings, "mailbox_lookup_response_budget_seconds", 120, raising=False
    )

    assert _remaining_lookup_budget(job, now=requested_at) == 120  # warm executor
    assert (
        _remaining_lookup_budget(job, now=requested_at + timedelta(seconds=60)) == 60
    )  # simulated cold start
    assert _remaining_lookup_budget(job, now=requested_at + timedelta(seconds=121)) == 0


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
async def test_pump_restarts_after_processing_a_full_batch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import settings
    from app.services.lookup_execution_coordinator.coordinator import (
        LookupExecutionCoordinator,
    )

    store = _BatchStore()
    processed: list[UUID] = []
    coordinator = LookupExecutionCoordinator(
        session_factory=lambda: None,
        coordination_store=store,
        transport=object(),
        task_spawner=store.spawn,
    )

    async def dispatch(job_id: UUID) -> bool:
        processed.append(job_id)
        return True

    coordinator._dispatch = dispatch  # type: ignore[method-assign]
    monkeypatch.setattr(settings, "lookup_dispatch_batch_size", 1)
    first, second = uuid4(), uuid4()

    await coordinator.schedule(first)
    await coordinator.schedule(second)
    await store.spawned[0]

    assert len(store.spawned) >= 2
    await store.spawned[1]
    assert processed == [first, second]
    assert store.queue == []


@pytest.mark.asyncio
async def test_pump_restarts_when_work_is_enqueued_during_completion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import settings
    from app.services.lookup_execution_coordinator.coordinator import (
        LookupExecutionCoordinator,
    )

    store = _CompletionRaceStore()
    processed: list[UUID] = []
    coordinator = LookupExecutionCoordinator(
        session_factory=lambda: None,
        coordination_store=store,
        transport=object(),
        task_spawner=store.spawn,
    )
    store.coordinator = coordinator

    async def dispatch(job_id: UUID) -> bool:
        processed.append(job_id)
        return True

    coordinator._dispatch = dispatch  # type: ignore[method-assign]
    monkeypatch.setattr(settings, "lookup_dispatch_batch_size", 1)
    first, second = uuid4(), uuid4()
    store.completion_job = second

    await coordinator.schedule(first)
    await store.spawned[0]
    await store.spawned[1]

    assert processed == [first, second]
    assert store.observed_active_during_completion == [True]
    assert store.queue == []


@pytest.mark.asyncio
async def test_pump_restarts_after_dispatch_requeues_with_remaining_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import settings
    from app.services.lookup_execution_coordinator.coordinator import (
        LookupExecutionCoordinator,
    )

    store = _BatchStore()
    processed: list[UUID] = []
    coordinator = LookupExecutionCoordinator(
        session_factory=lambda: None,
        coordination_store=store,
        transport=object(),
        task_spawner=store.spawn,
    )

    async def dispatch(job_id: UUID) -> bool:
        processed.append(job_id)
        if len(processed) == 1:
            await store.enqueue(job_id)
            return False
        return True

    coordinator._dispatch = dispatch  # type: ignore[method-assign]
    monkeypatch.setattr(settings, "lookup_dispatch_batch_size", 10)
    first, second = uuid4(), uuid4()

    await coordinator.schedule(first)
    await coordinator.schedule(second)
    await store.spawned[0]

    assert len(store.spawned) >= 2
    await store.spawned[1]
    assert processed == [first, second, first]
    assert store.queue == []


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
    coordinator, _ = await _run_dispatch(monkeypatch, job, executor, store)

    assert job.status == "pending"
    assert store.released == [job.id]
    assert store.queue == [job.id]
    assert executor.health_status == expected_health
    assert executor.requires_reverification is quarantined
    assert store.cooldown is False
    assert executor.id in coordinator._last_selected_at


@pytest.mark.asyncio
async def test_accepted_handoff_transitions_processing_and_counts_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job, executor = _job_and_executor()
    store = _Store()
    store.outcome = HandoffStatus.ACCEPTED
    _, session = await _run_dispatch(monkeypatch, job, executor, store)

    assert job.status == "processing"
    assert job.executor_id == executor.id
    assert job.execution_attempts == 1
    assert executor.health_status == "healthy"
    assert store.released == []
    assert store.queue == []
    assert session.commits == 1


@pytest.mark.asyncio
async def test_dispatch_does_not_resurrect_job_cancelled_during_handoff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job, executor = _job_and_executor()
    store = _Store()

    async def cancel_during_handoff() -> None:
        job.status = "failed"
        job.error_code = "user_cancelled"

    store.handoff_hook = cancel_during_handoff

    _, session = await _run_dispatch(monkeypatch, job, executor, store)

    assert job.status == "failed"
    assert job.execution_attempts == 0
    assert store.released == [job.id]
    assert session.commits == 0


@pytest.mark.asyncio
async def test_dispatch_rechecks_deadline_after_slow_handoff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import settings

    job, executor = _job_and_executor()
    store = _Store()
    store.resume_urls[job.id] = "https://n8n.example.com/resume/slow-handoff"
    notifier = SimpleNamespace(notify=AsyncMock(return_value=True))

    async def exhaust_budget_during_handoff() -> None:
        job.requested_at = datetime.now(timezone.utc) - timedelta(seconds=121)

    store.handoff_hook = exhaust_budget_during_handoff
    coordinator, session = _configured_coordinator(
        monkeypatch,
        job,
        executor,
        store,
        resume_notifier=notifier,
    )
    monkeypatch.setattr(settings, "mailbox_lookup_response_budget_seconds", 120)

    await coordinator.schedule(job.id)
    await store.pump_task

    assert job.status == "timeout"
    assert job.execution_attempts == 0
    assert store.released == [job.id]
    assert session.commits == 1
    notifier.notify.assert_awaited_once()


@pytest.mark.asyncio
async def test_dispatch_uses_fixed_cutoff_and_remaining_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import settings

    job, executor = _job_and_executor()
    requested_at = datetime.now(timezone.utc) - timedelta(seconds=60)
    job.requested_at = requested_at
    store = _Store()
    coordinator, _ = _configured_coordinator(monkeypatch, job, executor, store)
    monkeypatch.setattr(settings, "mailbox_lookup_window_minutes", 15)
    monkeypatch.setattr(settings, "mailbox_lookup_response_budget_seconds", 120)

    await coordinator.schedule(job.id)
    await store.pump_task

    envelope = store.envelopes[0]
    assert envelope["search_after"] == requested_at - timedelta(minutes=15)
    assert envelope["deadline_at"] == requested_at + timedelta(seconds=120)
    assert 58 <= envelope["timeout_seconds"] <= 60


@pytest.mark.asyncio
async def test_dispatch_marks_job_timeout_when_interactive_budget_is_exhausted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import settings

    job, executor = _job_and_executor()
    job.requested_at = datetime.now(timezone.utc) - timedelta(seconds=121)
    store = _Store()
    store.resume_urls[job.id] = "https://n8n.example.com/resume/timeout"
    notifier = SimpleNamespace(notify=AsyncMock(return_value=True))
    coordinator, session = _configured_coordinator(
        monkeypatch,
        job,
        executor,
        store,
        resume_notifier=notifier,
    )
    monkeypatch.setattr(settings, "mailbox_lookup_response_budget_seconds", 120)

    await coordinator.schedule(job.id)
    await store.pump_task

    assert job.status == "timeout"
    assert store.envelopes == []
    assert store.queue == []
    assert session.commits == 1
    notifier.notify.assert_awaited_once()
    assert job.id not in store.resume_urls


@pytest.mark.asyncio
async def test_dispatch_includes_recent_delivery_exclusions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.repositories import mailbox_dedupe_repository

    job, executor = _job_and_executor()
    store = _Store()
    coordinator, _ = _configured_coordinator(monkeypatch, job, executor, store)
    monkeypatch.setattr(
        mailbox_dedupe_repository,
        "list_delivery_keys_since",
        lambda *args, **kwargs: _value(
            [("msg-1", "fingerprint-1"), (None, "fingerprint-2")]
        ),
    )

    await coordinator.schedule(job.id)
    await store.pump_task

    assert store.envelopes[0]["excluded_deliveries"] == [
        {"message_id": "msg-1", "fingerprint": "fingerprint-1"},
        {"message_id": None, "fingerprint": "fingerprint-2"},
    ]


@pytest.mark.asyncio
async def test_duplicate_same_lease_handoff_transitions_processing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job, executor = _job_and_executor()
    store = _Store()
    store.outcome = HandoffStatus.DUPLICATE_SAME_LEASE
    await _run_dispatch(monkeypatch, job, executor, store)

    assert job.status == "processing"
    assert job.executor_id == executor.id
    assert job.execution_attempts == 1
    assert store.released == []


@pytest.mark.asyncio
async def test_integrated_selection_excludes_disabled_reverification_and_cooldown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job, available = _job_and_executor()
    disabled = _executor(id=UUID(int=1), lifecycle_status="disabled")
    quarantined = _executor(id=UUID(int=2), requires_reverification=True)
    cooled = _executor(id=UUID(int=3))
    available.id = UUID(int=4)
    store = _Store()
    store.cooldown_ids.add(cooled.id)
    coordinator, _ = _configured_coordinator(
        monkeypatch,
        job,
        available,
        store,
        executors=[disabled, quarantined, cooled, available],
    )

    selected = await coordinator._select_executor(_Session())

    assert selected is available


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
    return coordinator, session


def _configured_coordinator(
    monkeypatch,
    job,
    executor,
    store,
    *,
    executors=None,
    resume_notifier=None,
):
    from app.repositories import mailbox_config_repository, mailbox_dedupe_repository
    from app.repositories import mailbox_lookup_repository, lookup_executors_repository
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
        lambda db, job_id, **kwargs: _return(job, job_id),
    )
    monkeypatch.setattr(
        mailbox_config_repository,
        "get_by_id",
        lambda db, mailbox_id: _value(mailbox),
    )
    monkeypatch.setattr(
        mailbox_dedupe_repository,
        "list_delivery_keys_since",
        lambda *args, **kwargs: _value([]),
    )
    monkeypatch.setattr(
        lookup_executors_repository,
        "list_dispatchable",
        lambda db: _values(executors or [executor]),
    )
    monkeypatch.setattr(
        lookup_executors_repository,
        "update_health",
        lambda db, item, health, error=None: _health(item, health, error),
    )
    monkeypatch.setattr(
        mailbox_lookup_repository,
        "transition_status",
        lambda db, item, new_status, **kwargs: _transition(item, new_status, **kwargs),
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
            resume_notifier=resume_notifier,
        ),
        session,
    )


def _job_and_executor():
    job = SimpleNamespace(
        id=uuid4(),
        status="pending",
        requested_at=datetime.now(timezone.utc),
        tenant_id=uuid4(),
        mailbox_id=uuid4(),
        service_key="spotify",
        target_email="target@example.com",
        executor_id=None,
        execution_attempts=0,
        last_dispatch_error_safe=None,
    )
    return job, _executor()


def _executor(**overrides):
    values = {
        "id": uuid4(),
        "max_concurrency": 1,
        "requires_reverification": False,
        "health_status": "unknown",
        "lifecycle_status": "active",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


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


async def _transition(item, status, **kwargs):
    item.status = status
    item.error_code = kwargs.get("error_code")
    item.error_detail_safe = kwargs.get("error_detail_safe")
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

    async def execute(self, *args, **kwargs):
        del args, kwargs
        return SimpleNamespace(scalar_one_or_none=lambda: "es")


class _Store:
    def __init__(self):
        self.queue: list[UUID] = []
        self.released: list[UUID] = []
        self.cooldown = False
        self.cooldown_ids: set[UUID] = set()
        self.outcome = HandoffStatus.ACCEPTED
        self.raise_transport = False
        self.handoff_hook = None
        self.envelopes: list[dict[str, object]] = []
        self.resume_urls: dict[UUID, str] = {}
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

    async def has_queued_jobs(self, excluding_job_id=None):
        return any(job_id != excluding_job_id for job_id in self.queue)

    async def acquire_dispatch_lock(self, job_id):
        return True

    async def release_dispatch_lock(self, job_id):
        return None

    async def reserve_lease(self, job_id, executor_id, lease_id, expires_at):
        return True

    async def release_lease(self, job_id):
        self.released.append(job_id)

    async def get_resume_url(self, job_id):
        return self.resume_urls.get(job_id)

    async def delete_resume_url(self, job_id):
        self.resume_urls.pop(job_id, None)

    async def active_count(self, executor_id):
        return 0

    async def is_failure_cooldown_active(self, executor_id):
        return self.cooldown or executor_id in self.cooldown_ids

    async def clear_failure_cooldown(self, executor_id):
        self.cooldown = False

    async def set_failure_cooldown(self, executor_id, ttl_seconds):
        self.cooldown = True


class _BatchStore(_Store):
    def __init__(self):
        super().__init__()
        self.spawned: list[asyncio.Task[None]] = []

    def spawn(self, coro):
        task = asyncio.create_task(coro)
        self.spawned.append(task)
        return task


class _CompletionRaceStore(_BatchStore):
    def __init__(self):
        super().__init__()
        self.completion_job = None
        self.coordinator = None
        self.observed_active_during_completion = []

    async def has_queued_jobs(self, excluding_job_id=None):
        if self.completion_job is not None:
            job_id = self.completion_job
            self.completion_job = None
            await self.enqueue(job_id)
            self.observed_active_during_completion.append(
                self.coordinator._pump_task is not None
            )
        return await super().has_queued_jobs(excluding_job_id)


class _Transport:
    def __init__(self, store):
        self.store = store

    async def handoff(self, executor, envelope):
        self.store.envelopes.append(envelope)
        if self.store.handoff_hook is not None:
            await self.store.handoff_hook()
        if self.store.raise_transport:
            raise OSError("offline")
        return HandoffResult(self.store.outcome, envelope["lease_id"])
