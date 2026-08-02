"""Behavioral coverage for signed external lookup executor callbacks."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

from app.core.lookup_executor_protocol import (
    derive_protocol_keys,
    encrypt_payload,
    sign_request,
)
from app.main import app
from app.services.lookup_execution_coordinator.coordinator import (
    CompletionAck,
    LookupExecutionCoordinator,
    VerifiedCallback,
)
from app.services.lookup_execution_coordinator.redis_store import (
    RedisLookupCoordinationStore,
)


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    async def __aenter__(self) -> FakeSession:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1

    async def flush(self) -> None:
        return None


class FakeStore:
    def __init__(self, lease: object | None) -> None:
        self.lease = lease
        self.released: list[object] = []
        self.enqueued: list[object] = []
        self.results: list[tuple[object, str, str, int]] = []

    async def get_lease(self, job_id: object) -> object | None:
        return self.lease

    async def release_lease(self, job_id: object) -> None:
        self.released.append(job_id)

    async def enqueue(self, job_id: object) -> bool:
        self.enqueued.append(job_id)
        return True

    async def put_result(
        self, job_id: object, result_type: str, result_value: str, ttl_seconds: int
    ) -> None:
        self.results.append((job_id, result_type, result_value, ttl_seconds))

    async def get_result(self, job_id: object) -> tuple[str, str] | None:
        for stored_job_id, result_type, result_value, _ in self.results:
            if stored_job_id == job_id:
                return result_type, result_value
        return None


class Outcome(BaseModel):
    kind: str
    result_type: str | None = None
    result_value: str | None = None
    message_id: str | None = None
    fingerprint: str | None = None
    error_code: str | None = None
    error_detail: str | None = None


def _job(*, status: str = "processing", expires_in: int = 300) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        tenant_id=uuid4(),
        mailbox_id=uuid4(),
        service_key="netflix",
        status=status,
        executor_id=None,
        result_type=None,
        error_code=None,
        error_detail_safe=None,
        last_dispatch_error_safe=None,
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=expires_in),
    )


def _callback(
    job: SimpleNamespace, executor_id: object, lease_id: object, outcome: Outcome
) -> VerifiedCallback:
    return VerifiedCallback(
        executor_id=executor_id,
        lease_id=lease_id,
        key_version=1,
        nonce="nonce",
        outcome=outcome,
    )


@pytest.mark.asyncio
async def test_found_callback_completes_job_and_stores_encrypted_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.repositories import mailbox_dedupe_repository, mailbox_lookup_repository

    job = _job()
    executor_id, lease_id = uuid4(), uuid4()
    store = FakeStore(
        SimpleNamespace(
            job_id=job.id,
            executor_id=executor_id,
            lease_id=lease_id,
            expires_at=job.expires_at,
        )
    )
    session = FakeSession()
    monkeypatch.setattr(
        mailbox_lookup_repository, "get_job", lambda *args, **kwargs: _async_value(job)
    )
    monkeypatch.setattr(
        mailbox_lookup_repository,
        "transition_status",
        lambda db, item, status, **kwargs: _transition(item, status, **kwargs),
    )
    monkeypatch.setattr(
        mailbox_dedupe_repository,
        "record_delivery_atomic",
        lambda *args, **kwargs: _async_value(True),
    )

    coordinator = LookupExecutionCoordinator(lambda: session, store, object())
    outcome = Outcome(
        kind="found",
        result_type="code",
        result_value="654321",
        fingerprint="fingerprint",
    )

    ack = await coordinator.complete(
        job.id, _callback(job, executor_id, lease_id, outcome)
    )

    assert ack == CompletionAck(accepted=True)
    assert job.status == "completed"
    assert job.result_type == "code"
    assert store.results[0][1:3] == ("code", "654321")
    assert store.released == [job.id]


@pytest.mark.asyncio
async def test_duplicate_found_callback_is_suppressed_without_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.repositories import mailbox_dedupe_repository, mailbox_lookup_repository

    job = _job()
    executor_id, lease_id = uuid4(), uuid4()
    store = FakeStore(
        SimpleNamespace(
            job_id=job.id,
            executor_id=executor_id,
            lease_id=lease_id,
            expires_at=job.expires_at,
        )
    )
    monkeypatch.setattr(
        mailbox_lookup_repository, "get_job", lambda *args, **kwargs: _async_value(job)
    )
    monkeypatch.setattr(
        mailbox_lookup_repository,
        "transition_status",
        lambda db, item, status, **kwargs: _transition(item, status, **kwargs),
    )
    monkeypatch.setattr(
        mailbox_dedupe_repository,
        "record_delivery_atomic",
        lambda *args, **kwargs: _async_value(False),
    )

    coordinator = LookupExecutionCoordinator(lambda: FakeSession(), store, object())
    outcome = Outcome(
        kind="found", result_type="code", result_value="654321", fingerprint="same"
    )

    ack = await coordinator.complete(
        job.id, _callback(job, executor_id, lease_id, outcome)
    )

    assert ack.accepted is True
    assert job.status == "completed"
    assert job.result_type == "duplicate_suppressed"
    assert store.results == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("kind", "expected_status", "expected_result_type"),
    [
        ("not_found", "completed", "not_found"),
        ("terminal_failure", "failed", None),
    ],
)
async def test_non_retryable_outcomes_complete_without_result(
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
    expected_status: str,
    expected_result_type: str | None,
) -> None:
    from app.repositories import mailbox_lookup_repository

    job = _job()
    executor_id, lease_id = uuid4(), uuid4()
    store = FakeStore(
        SimpleNamespace(
            job_id=job.id,
            executor_id=executor_id,
            lease_id=lease_id,
            expires_at=job.expires_at,
        )
    )
    monkeypatch.setattr(
        mailbox_lookup_repository, "get_job", lambda *args, **kwargs: _async_value(job)
    )
    monkeypatch.setattr(
        mailbox_lookup_repository,
        "transition_status",
        lambda db, item, status, **kwargs: _transition(item, status, **kwargs),
    )

    coordinator = LookupExecutionCoordinator(lambda: FakeSession(), store, object())
    outcome = Outcome(
        kind=kind,
        error_code="auth_failed",
        error_detail="Mailbox authentication failed",
    )

    ack = await coordinator.complete(
        job.id, _callback(job, executor_id, lease_id, outcome)
    )

    assert ack.accepted is True
    assert job.status == expected_status
    assert job.result_type == expected_result_type
    assert store.results == []


@pytest.mark.asyncio
async def test_retryable_callback_returns_processing_job_to_pending_and_requeues(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.repositories import mailbox_lookup_repository

    job = _job()
    executor_id, lease_id = uuid4(), uuid4()
    store = FakeStore(
        SimpleNamespace(
            job_id=job.id,
            executor_id=executor_id,
            lease_id=lease_id,
            expires_at=job.expires_at,
        )
    )
    monkeypatch.setattr(
        mailbox_lookup_repository, "get_job", lambda *args, **kwargs: _async_value(job)
    )
    monkeypatch.setattr(
        mailbox_lookup_repository,
        "transition_status",
        lambda db, item, status, **kwargs: _transition(item, status, **kwargs),
    )

    coordinator = LookupExecutionCoordinator(lambda: FakeSession(), store, object())
    outcome = Outcome(
        kind="retryable_failure", error_code="timeout", error_detail="Mailbox timed out"
    )

    ack = await coordinator.complete(
        job.id, _callback(job, executor_id, lease_id, outcome)
    )

    assert ack.accepted is True
    assert job.status == "pending"
    assert job.executor_id is None
    assert store.released == [job.id]
    assert store.enqueued == [job.id]


@pytest.mark.asyncio
async def test_callback_can_win_pending_handoff_race(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.repositories import mailbox_dedupe_repository, mailbox_lookup_repository

    job = _job(status="pending")
    executor_id, lease_id = uuid4(), uuid4()
    store = FakeStore(
        SimpleNamespace(
            job_id=job.id,
            executor_id=executor_id,
            lease_id=lease_id,
            expires_at=job.expires_at,
        )
    )
    transitions: list[str] = []

    async def transition(
        db: object, item: SimpleNamespace, status: str, **kwargs: object
    ) -> SimpleNamespace:
        transitions.append(status)
        return await _transition(item, status, **kwargs)

    monkeypatch.setattr(
        mailbox_lookup_repository, "get_job", lambda *args, **kwargs: _async_value(job)
    )
    monkeypatch.setattr(mailbox_lookup_repository, "transition_status", transition)
    monkeypatch.setattr(
        mailbox_dedupe_repository,
        "record_delivery_atomic",
        lambda *args, **kwargs: _async_value(True),
    )

    coordinator = LookupExecutionCoordinator(lambda: FakeSession(), store, object())
    outcome = Outcome(
        kind="found",
        result_type="code",
        result_value="654321",
        fingerprint="race",
    )

    ack = await coordinator.complete(
        job.id, _callback(job, executor_id, lease_id, outcome)
    )

    assert ack.accepted is True
    assert transitions == ["processing", "completed"]
    assert job.status == "completed"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "callback_mutation",
    [
        lambda job, executor_id, lease_id: (executor_id, uuid4()),
        lambda job, executor_id, lease_id: (uuid4(), lease_id),
    ],
)
async def test_wrong_executor_or_lease_is_acknowledged_without_mutation(
    monkeypatch: pytest.MonkeyPatch,
    callback_mutation,
) -> None:
    from app.repositories import mailbox_lookup_repository

    job = _job()
    executor_id, lease_id = uuid4(), uuid4()
    store = FakeStore(
        SimpleNamespace(
            job_id=job.id,
            executor_id=executor_id,
            lease_id=lease_id,
            expires_at=job.expires_at,
        )
    )
    monkeypatch.setattr(
        mailbox_lookup_repository, "get_job", lambda *args, **kwargs: _async_value(job)
    )

    coordinator = LookupExecutionCoordinator(lambda: FakeSession(), store, object())
    wrong_executor, wrong_lease = callback_mutation(job, executor_id, lease_id)
    outcome = Outcome(kind="not_found")

    ack = await coordinator.complete(
        job.id, _callback(job, wrong_executor, wrong_lease, outcome)
    )

    assert ack == CompletionAck(accepted=False)
    assert job.status == "processing"
    assert store.released == []


@pytest.mark.asyncio
async def test_terminal_job_and_expired_lease_are_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.repositories import mailbox_lookup_repository

    job = _job(status="completed")
    executor_id, lease_id = uuid4(), uuid4()
    store = FakeStore(None)
    monkeypatch.setattr(
        mailbox_lookup_repository, "get_job", lambda *args, **kwargs: _async_value(job)
    )
    coordinator = LookupExecutionCoordinator(lambda: FakeSession(), store, object())

    assert (
        await coordinator.complete(
            job.id, _callback(job, executor_id, lease_id, Outcome(kind="not_found"))
        )
    ).accepted is False

    job.status = "processing"
    assert (
        await coordinator.complete(
            job.id, _callback(job, executor_id, lease_id, Outcome(kind="not_found"))
        )
    ).accepted is False
    assert job.status == "processing"


@pytest.mark.asyncio
async def test_expired_lease_is_rejected_even_when_job_is_processing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.repositories import mailbox_lookup_repository

    job = _job()
    executor_id, lease_id = uuid4(), uuid4()
    store = FakeStore(
        SimpleNamespace(
            job_id=job.id,
            executor_id=executor_id,
            lease_id=lease_id,
            expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        )
    )
    monkeypatch.setattr(
        mailbox_lookup_repository, "get_job", lambda *args, **kwargs: _async_value(job)
    )
    coordinator = LookupExecutionCoordinator(lambda: FakeSession(), store, object())

    ack = await coordinator.complete(
        job.id, _callback(job, executor_id, lease_id, Outcome(kind="not_found"))
    )

    assert ack == CompletionAck(accepted=False)
    assert job.status == "processing"


@pytest.mark.asyncio
async def test_duplicate_callback_is_rejected_after_lease_release(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.repositories import mailbox_lookup_repository
    from app.services.lookup_execution_coordinator.fake_store import (
        FakeLookupCoordinationStore,
    )

    job = _job()
    executor_id, lease_id = uuid4(), uuid4()
    store = FakeLookupCoordinationStore()
    assert (
        await store.reserve_lease(
            job.id,
            executor_id,
            lease_id,
            datetime.now(timezone.utc) + timedelta(minutes=1),
        )
        is True
    )
    monkeypatch.setattr(
        mailbox_lookup_repository, "get_job", lambda *args, **kwargs: _async_value(job)
    )
    monkeypatch.setattr(
        mailbox_lookup_repository,
        "transition_status",
        lambda db, item, status, **kwargs: _transition(item, status, **kwargs),
    )
    coordinator = LookupExecutionCoordinator(lambda: FakeSession(), store, object())
    callback = _callback(job, executor_id, lease_id, Outcome(kind="not_found"))

    assert await coordinator.complete(job.id, callback) == CompletionAck(accepted=True)
    job.status = "processing"
    assert await coordinator.complete(job.id, callback) == CompletionAck(accepted=False)


@pytest.mark.asyncio
async def test_null_message_id_dedupe_rejects_duplicate_without_precheck(
    db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.repositories import mailbox_dedupe_repository

    monkeypatch.setattr(
        mailbox_dedupe_repository,
        "is_duplicate",
        lambda *args, **kwargs: _async_value(False),
    )
    values = {
        "tenant_id": uuid4(),
        "mailbox_id": uuid4(),
        "service_key": "netflix",
        "message_id": None,
        "fingerprint": "same-fingerprint",
    }

    assert (
        await mailbox_dedupe_repository.record_delivery_atomic(db_session, **values)
        is True
    )
    assert (
        await mailbox_dedupe_repository.record_delivery_atomic(db_session, **values)
        is False
    )


class _CiphertextRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    async def set(
        self,
        key: str,
        value: str,
        *,
        ex: int | None = None,
        nx: bool = False,
    ) -> bool:
        del ex, nx
        self.values[key] = value
        return True

    async def get(self, key: str) -> str | None:
        return self.values.get(key)


class _CiphertextRedisManager:
    def __init__(self) -> None:
        self.redis = _CiphertextRedis()

    async def execute(
        self,
        operation_name: str,
        operation: Callable[[_CiphertextRedis], Awaitable[Any]],
    ) -> Any:
        del operation_name
        return await operation(self.redis)


@pytest.mark.asyncio
async def test_redis_result_is_encrypted_and_round_trips() -> None:
    job_id = uuid4()
    manager = _CiphertextRedisManager()
    store = RedisLookupCoordinationStore(manager)

    await store.put_result(job_id, "code", "654321", 120)

    raw = manager.redis.values[f"lookup:result:{job_id}"]
    assert "654321" not in raw
    assert await store.get_result(job_id) == ("code", "654321")


@pytest.mark.asyncio
async def test_coordinator_get_result_delegates_to_coordination_store() -> None:
    job_id = uuid4()
    store = FakeStore(None)
    await store.put_result(job_id, "code", "654321", 120)
    coordinator = LookupExecutionCoordinator(lambda: FakeSession(), store, object())

    assert await coordinator.get_result(job_id) == ("code", "654321")


@pytest.mark.asyncio
async def test_callback_endpoint_verifies_signature_nonce_and_decrypts_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.api.v1.endpoints.integrations import executor_callbacks
    from app.core.database import get_db
    from app.repositories import lookup_executors_repository

    executor_id, job_id, lease_id = uuid4(), uuid4(), uuid4()
    secret = "callback-secret"
    keys = derive_protocol_keys(secret)
    payload = {
        "job_id": str(job_id),
        "lease_id": str(lease_id),
        "outcome": {"kind": "not_found"},
    }
    encrypted = encrypt_payload(payload, keys.encryption)
    body = encrypted.model_dump_json().encode()
    path = f"/api/v1/integrations/executors/{executor_id}/jobs/{job_id}/complete"
    timestamp = 1_900_000_000
    nonce = "callback-nonce"
    signature = sign_request(
        "POST", path, executor_id, 1, timestamp, nonce, body, keys.signing
    )

    class FakeCoordinator:
        def __init__(self) -> None:
            self._store = self
            self.received: VerifiedCallback | None = None
            self.nonce_calls: list[tuple[object, ...]] = []

        async def consume_callback_nonce(self, *args: object) -> bool:
            self.nonce_calls.append(args)
            return len(self.nonce_calls) == 1

        async def complete(
            self, requested_job_id: object, callback: VerifiedCallback
        ) -> CompletionAck:
            self.received = callback
            return CompletionAck(accepted=True)

    coordinator = FakeCoordinator()
    monkeypatch.setattr(
        executor_callbacks, "get_lookup_execution_coordinator", lambda: coordinator
    )
    monkeypatch.setattr(executor_callbacks, "set_internal_rls_context", _noop)
    monkeypatch.setattr(
        lookup_executors_repository,
        "get",
        lambda db, requested_id: _async_value(
            SimpleNamespace(
                id=executor_id, secret_encrypted="encrypted", secret_version=1
            )
        ),
    )
    monkeypatch.setattr(executor_callbacks, "decrypt_value", lambda value: secret)
    monkeypatch.setattr(executor_callbacks.time, "time", lambda: timestamp)

    async def override_db():
        yield object()

    app.dependency_overrides[get_db] = override_db
    try:
        headers = {
            "X-TrackPal-Executor-Id": str(executor_id),
            "X-TrackPal-Key-Version": "1",
            "X-TrackPal-Timestamp": str(timestamp),
            "X-TrackPal-Nonce": nonce,
            "X-TrackPal-Signature": signature,
        }
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            response = await client.post(path, content=body, headers=headers)
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"accepted": True}
    assert coordinator.received is not None
    assert coordinator.received.outcome.kind == "not_found"
    assert coordinator.nonce_calls[0][2] == 180

    app.dependency_overrides[get_db] = override_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            replay = await client.post(path, content=body, headers=headers)
    finally:
        app.dependency_overrides.clear()
    assert replay.status_code == 401
    assert replay.json() == {"detail": "replayed protocol nonce"}


@pytest.mark.asyncio
async def test_callback_nonce_survives_inclusive_signature_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.api.v1.endpoints.integrations import executor_callbacks
    from app.core.database import get_db
    from app.repositories import lookup_executors_repository

    executor_id, job_id, lease_id = uuid4(), uuid4(), uuid4()
    secret = "callback-secret"
    keys = derive_protocol_keys(secret)
    payload = {
        "job_id": str(job_id),
        "lease_id": str(lease_id),
        "outcome": {"kind": "not_found"},
    }
    body = encrypt_payload(payload, keys.encryption).model_dump_json().encode()
    path = f"/api/v1/integrations/executors/{executor_id}/jobs/{job_id}/complete"
    skew = 60
    timestamp = 1_900_000_000
    nonce = "boundary-nonce"
    signature = sign_request(
        "POST", path, executor_id, 1, timestamp, nonce, body, keys.signing
    )
    clock = iter((timestamp - skew, timestamp + skew))
    current_time = [timestamp - skew]

    def fake_time() -> int:
        current_time[0] = next(clock)
        return current_time[0]

    monkeypatch.setattr(executor_callbacks, "time", SimpleNamespace(time=fake_time))
    monkeypatch.setattr(executor_callbacks, "set_internal_rls_context", _noop)
    monkeypatch.setattr(
        lookup_executors_repository,
        "get",
        lambda db, requested_id: _async_value(
            SimpleNamespace(
                id=executor_id, secret_encrypted="encrypted", secret_version=1
            )
        ),
    )
    monkeypatch.setattr(executor_callbacks, "decrypt_value", lambda value: secret)

    class FakeCoordinator:
        def __init__(self) -> None:
            self._store = self
            self.nonce_expires_at: int | None = None

        async def consume_callback_nonce(
            self, executor_id: object, nonce: str, ttl_seconds: int
        ) -> bool:
            if self.nonce_expires_at is None:
                self.nonce_expires_at = current_time[0] + ttl_seconds
                return True
            return current_time[0] >= self.nonce_expires_at

        async def complete(
            self, requested_job_id: object, callback: VerifiedCallback
        ) -> CompletionAck:
            return CompletionAck(accepted=True)

    coordinator = FakeCoordinator()
    monkeypatch.setattr(
        executor_callbacks, "get_lookup_execution_coordinator", lambda: coordinator
    )

    async def override_db() -> AsyncIterator[object]:
        yield object()

    app.dependency_overrides[get_db] = override_db
    headers = {
        "X-TrackPal-Executor-Id": str(executor_id),
        "X-TrackPal-Key-Version": "1",
        "X-TrackPal-Timestamp": str(timestamp),
        "X-TrackPal-Nonce": nonce,
        "X-TrackPal-Signature": signature,
    }
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            first = await client.post(path, content=body, headers=headers)
            replay = await client.post(path, content=body, headers=headers)
    finally:
        app.dependency_overrides.clear()

    assert first.status_code == 200
    assert replay.status_code == 401
    assert replay.json() == {"detail": "replayed protocol nonce"}


async def _async_value(value: object) -> object:
    return value


async def _transition(
    job: SimpleNamespace, status: str, **kwargs: object
) -> SimpleNamespace:
    job.status = status
    job.result_type = kwargs.get("result_type")
    job.error_code = kwargs.get("error_code")
    job.error_detail_safe = kwargs.get("error_detail_safe")
    return job


async def _noop(*args: object, **kwargs: object) -> None:
    return None
