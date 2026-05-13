"""Tests for WhatsApp auth session + lockout service.

Uses the same fake-Redis pattern as test_whatsapp_session_service.py.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from app.services.whatsapp_auth_session_service import (
    WhatsAppAuthSession,
    WhatsAppAuthFailState,
    WhatsAppAuthLockState,
    WhatsAppAuthSessionService,
)


# ---------------------------------------------------------------------------
# Fake Redis — dict-based async double
# ---------------------------------------------------------------------------

class FakeRedis:
    """Minimal in-memory fake for redis.asyncio.Redis."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}
        self._ttls: dict[str, int] = {}

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None, keepttl: bool = False) -> None:
        self._store[key] = value
        if ex is not None:
            self._ttls[key] = ex
        elif not keepttl:
            self._ttls.pop(key, None)

    async def delete(self, key: str) -> int:
        self._ttls.pop(key, None)
        return 1 if self._store.pop(key, None) is not None else 0

    async def exists(self, key: str) -> int:
        return 1 if key in self._store else 0

    def __getattr__(self, name: str) -> Any:
        raise AttributeError(f"FakeRedis does not implement '{name}'")


# ---------------------------------------------------------------------------
# Fake connection manager
# ---------------------------------------------------------------------------

class FakeManager:
    """Duck-typed connection manager that delegates execute() to FakeRedis."""

    def __init__(self, fake_redis: FakeRedis | None = None) -> None:
        self._redis = fake_redis or FakeRedis()

    async def execute(self, operation_name: str, async_callable: Any) -> Any:
        return await async_callable(self._redis)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def fake_redis() -> FakeRedis:
    return FakeRedis()


@pytest.fixture
def fake_manager(fake_redis: FakeRedis) -> FakeManager:
    return FakeManager(fake_redis=fake_redis)


@pytest.fixture
def service(fake_manager: FakeManager) -> WhatsAppAuthSessionService:
    return WhatsAppAuthSessionService(
        connection_manager=fake_manager,
        session_ttl_seconds=900,
        fail_threshold=3,
        lock_minutes=5,
        fail_window_minutes=15,
    )


# ===================================================================
# Model tests
# ===================================================================

class TestWhatsAppAuthSessionModel:
    """Verify WhatsAppAuthSession data shape."""

    def test_required_fields(self) -> None:
        now = datetime.now(timezone.utc)
        session = WhatsAppAuthSession(
            phone="+1234567890",
            user_id=uuid.uuid4(),
            username="master",
            role="master",
            authenticated_at=now,
        )
        assert session.phone == "+1234567890"
        assert session.username == "master"
        assert session.role == "master"
        assert session.authenticated_at == now

    def test_user_id_is_uuid(self) -> None:
        uid = uuid.uuid4()
        session = WhatsAppAuthSession(
            phone="+1234567890",
            user_id=uid,
            username="master",
            role="master",
            authenticated_at=datetime.now(timezone.utc),
        )
        assert session.user_id == uid
        assert isinstance(session.user_id, uuid.UUID)


class TestWhatsAppAuthFailStateModel:
    """Verify fail-state data shape."""

    def test_required_fields(self) -> None:
        now = datetime.now(timezone.utc)
        state = WhatsAppAuthFailState(
            count=1,
            first_failed_at=now,
            last_failed_at=now,
        )
        assert state.count == 1
        assert state.first_failed_at == now
        assert state.last_failed_at == now

    def test_defaults(self) -> None:
        now = datetime.now(timezone.utc)
        state = WhatsAppAuthFailState(
            count=0,
            first_failed_at=now,
            last_failed_at=now,
        )
        assert state.count == 0


class TestWhatsAppAuthLockStateModel:
    """Verify lock-state data shape."""

    def test_required_fields(self) -> None:
        now = datetime.now(timezone.utc)
        lock = WhatsAppAuthLockState(locked_until=now)
        assert lock.locked_until == now

    def test_is_locked_true_when_not_expired(self) -> None:
        future = datetime.now(timezone.utc) + timedelta(minutes=5)
        lock = WhatsAppAuthLockState(locked_until=future)
        assert lock.is_locked is True

    def test_is_locked_false_when_expired(self) -> None:
        past = datetime.now(timezone.utc) - timedelta(minutes=1)
        lock = WhatsAppAuthLockState(locked_until=past)
        assert lock.is_locked is False


# ===================================================================
# Auth session CRUD
# ===================================================================

@pytest.mark.asyncio
class TestGetAuthSession:
    async def test_returns_none_when_no_session(
        self, service: WhatsAppAuthSessionService
    ) -> None:
        session = await service.get_auth_session("+9999999999")
        assert session is None

    async def test_returns_session_after_set(
        self, service: WhatsAppAuthSessionService
    ) -> None:
        now = datetime.now(timezone.utc)
        auth = WhatsAppAuthSession(
            phone="+1234567890",
            user_id=uuid.uuid4(),
            username="master",
            role="master",
            authenticated_at=now,
        )
        await service.set_auth_session(auth)
        fetched = await service.get_auth_session("+1234567890")
        assert fetched is not None
        assert fetched.phone == "+1234567890"
        assert fetched.username == "master"
        assert fetched.role == "master"


@pytest.mark.asyncio
class TestSetAuthSession:
    async def test_persists_session(
        self, service: WhatsAppAuthSessionService
    ) -> None:
        now = datetime.now(timezone.utc)
        auth = WhatsAppAuthSession(
            phone="+1234567890",
            user_id=uuid.uuid4(),
            username="master",
            role="master",
            authenticated_at=now,
        )
        result = await service.set_auth_session(auth)
        assert result.phone == "+1234567890"

    async def test_overwrites_existing(
        self, service: WhatsAppAuthSessionService
    ) -> None:
        now = datetime.now(timezone.utc)
        uid = uuid.uuid4()
        auth1 = WhatsAppAuthSession(
            phone="+1234567890",
            user_id=uid,
            username="master",
            role="master",
            authenticated_at=now,
        )
        await service.set_auth_session(auth1)
        auth2 = WhatsAppAuthSession(
            phone="+1234567890",
            user_id=uid,
            username="master",
            role="master",
            authenticated_at=now,
        )
        await service.set_auth_session(auth2)
        fetched = await service.get_auth_session("+1234567890")
        assert fetched is not None
        assert fetched.authenticated_at == now


@pytest.mark.asyncio
class TestClearAuthSession:
    async def test_removes_session(
        self, service: WhatsAppAuthSessionService
    ) -> None:
        now = datetime.now(timezone.utc)
        auth = WhatsAppAuthSession(
            phone="+1234567890",
            user_id=uuid.uuid4(),
            username="master",
            role="master",
            authenticated_at=now,
        )
        await service.set_auth_session(auth)
        await service.clear_auth_session("+1234567890")
        fetched = await service.get_auth_session("+1234567890")
        assert fetched is None

    async def test_clear_nonexistent_does_not_raise(
        self, service: WhatsAppAuthSessionService
    ) -> None:
        await service.clear_auth_session("+9999999999")


@pytest.mark.asyncio
class TestAuthSessionTTL:
    async def test_session_write_sets_ttl(
        self, service: WhatsAppAuthSessionService, fake_redis: FakeRedis
    ) -> None:
        now = datetime.now(timezone.utc)
        auth = WhatsAppAuthSession(
            phone="+1234567890",
            user_id=uuid.uuid4(),
            username="master",
            role="master",
            authenticated_at=now,
        )
        await service.set_auth_session(auth)
        key = service._auth_key("+1234567890")
        # TTL should be 900 (our fixture value)
        ttl = fake_redis._ttls.get(key)
        assert ttl == 900, f"Expected TTL 900, got {ttl}"


# ===================================================================
# Lockout primitives
# ===================================================================

@pytest.mark.asyncio
class TestGetLockState:
    async def test_returns_none_when_not_locked(
        self, service: WhatsAppAuthSessionService
    ) -> None:
        state = await service.get_lock_state("+9999999999")
        assert state is None

    async def test_returns_lock_state_when_locked(
        self, service: WhatsAppAuthSessionService, fake_redis: FakeRedis
    ) -> None:
        # Manually set a lock
        lock_key = service._lock_key("+1234567890")
        future = datetime.now(timezone.utc) + timedelta(minutes=5)
        lock = WhatsAppAuthLockState(locked_until=future)
        await fake_redis.set(lock_key, lock.model_dump_json(), ex=300)
        state = await service.get_lock_state("+1234567890")
        assert state is not None
        assert state.is_locked is True


@pytest.mark.asyncio
class TestRecordFailedAttempt:
    async def test_first_failure_returns_count_1_not_locked(
        self, service: WhatsAppAuthSessionService
    ) -> None:
        count, locked = await service.record_failed_attempt("+1234567890")
        assert count == 1
        assert locked is False

    async def test_repeated_failures_increment_count(
        self, service: WhatsAppAuthSessionService
    ) -> None:
        await service.record_failed_attempt("+1234567890")
        count, locked = await service.record_failed_attempt("+1234567890")
        assert count == 2
        assert locked is False

    async def test_lockout_after_threshold(
        self, service: WhatsAppAuthSessionService
    ) -> None:
        # Our fixture uses fail_threshold=3
        count1, locked1 = await service.record_failed_attempt("+1234567890")
        assert count1 == 1
        assert locked1 is False

        count2, locked2 = await service.record_failed_attempt("+1234567890")
        assert count2 == 2
        assert locked2 is False

        count3, locked3 = await service.record_failed_attempt("+1234567890")
        assert count3 == 3
        assert locked3 is True

    async def test_lockout_creates_lock_state(
        self, service: WhatsAppAuthSessionService
    ) -> None:
        for _ in range(3):
            await service.record_failed_attempt("+1234567890")
        state = await service.get_lock_state("+1234567890")
        assert state is not None
        assert state.is_locked is True

    async def test_fail_counter_cleared_after_lock(
        self, service: WhatsAppAuthSessionService, fake_redis: FakeRedis
    ) -> None:
        for _ in range(3):
            await service.record_failed_attempt("+1234567890")
        fail_key = service._fail_key("+1234567890")
        raw = await fake_redis.get(fail_key)
        assert raw is None, "Fail key should be deleted after lock"

    async def test_lockout_payload_has_future_locked_until(
        self, service: WhatsAppAuthSessionService
    ) -> None:
        for _ in range(3):
            await service.record_failed_attempt("+1234567890")
        state = await service.get_lock_state("+1234567890")
        assert state is not None
        assert state.locked_until > datetime.now(timezone.utc)
