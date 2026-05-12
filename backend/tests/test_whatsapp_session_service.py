"""Tests for the Redis Conversation Session service.

Uses a fake in-memory Redis client so tests are isolated and
require no external Redis service.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.services.whatsapp_session_service import (
    ConversationSession,
    WhatsAppSessionService,
)


# ---------------------------------------------------------------------------
# Fake Redis — dict-based async double that mimics only the methods we need
# ---------------------------------------------------------------------------

class FakeRedis:
    """Minimal in-memory fake for redis.asyncio.Redis."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}
        self._ttls: dict[str, int] = {}

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self._store[key] = value
        if ex is not None:
            self._ttls[key] = ex

    async def delete(self, key: str) -> int:
        self._ttls.pop(key, None)
        return 1 if self._store.pop(key, None) is not None else 0

    async def exists(self, key: str) -> int:
        return 1 if key in self._store else 0

    def get_ttl(self, key: str) -> int | None:
        """Return the TTL set for *key* (test helper)."""
        return self._ttls.get(key)

    def __getattr__(self, name: str) -> Any:
        # Fail fast if a test accidentally calls a real Redis method we haven't faked.
        raise AttributeError(f"FakeRedis does not implement '{name}'")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def fake_redis() -> FakeRedis:
    return FakeRedis()


@pytest.fixture
def service(fake_redis: FakeRedis) -> WhatsAppSessionService:
    return WhatsAppSessionService(
        redis_client=fake_redis,
        ttl_seconds=1800,  # 30 minutes
    )


# ---------------------------------------------------------------------------
# Session model
# ---------------------------------------------------------------------------

class TestConversationSessionModel:
    """Verify the session data shape."""

    def test_default_flow_is_empty_string(self) -> None:
        session = ConversationSession(phone="+1234567890")
        assert session.flow == ""

    def test_optional_fields_default(self) -> None:
        session = ConversationSession(phone="+1234567890")
        assert session.step == ""
        assert session.selected_tenant_id is None
        assert session.temp_data == {}
        assert session.selection_map == {}

    def test_phone_is_required(self) -> None:
        with pytest.raises(ValueError):
            ConversationSession()  # type: ignore[call-arg]

    def test_fields_are_assignable(self) -> None:
        session = ConversationSession(
            phone="+1234567890",
            flow="create_tenant",
            step="full_name",
            selected_tenant_id="uuid-here",
            temp_data={"full_name": "Foo"},
            selection_map={"1": "uuid-1", "2": "uuid-2"},
        )
        assert session.phone == "+1234567890"
        assert session.flow == "create_tenant"
        assert session.step == "full_name"
        assert session.selected_tenant_id == "uuid-here"
        assert session.temp_data == {"full_name": "Foo"}
        assert session.selection_map == {"1": "uuid-1", "2": "uuid-2"}


# ---------------------------------------------------------------------------
# Session creation and retrieval
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestGetSession:
    async def test_returns_none_when_no_session(
        self, service: WhatsAppSessionService
    ) -> None:
        session = await service.get_session("+9999999999")
        assert session is None

    async def test_returns_session_after_create(
        self, service: WhatsAppSessionService, fake_redis: FakeRedis
    ) -> None:
        created = await service.create_session("+1234567890")
        assert created.phone == "+1234567890"
        assert created.flow == ""

        fetched = await service.get_session("+1234567890")
        assert fetched is not None
        assert fetched.phone == "+1234567890"
        assert fetched.flow == ""


@pytest.mark.asyncio
class TestCreateSession:
    async def test_creates_with_defaults(
        self, service: WhatsAppSessionService
    ) -> None:
        session = await service.create_session("+1234567890")
        assert session.phone == "+1234567890"
        assert session.flow == ""
        assert session.step == ""
        assert session.selected_tenant_id is None
        assert session.temp_data == {}
        assert session.selection_map == {}

    async def test_overwrites_existing(
        self, service: WhatsAppSessionService
    ) -> None:
        await service.create_session("+1234567890")
        session2 = await service.create_session("+1234567890")
        assert session2.phone == "+1234567890"


@pytest.mark.asyncio
class TestSaveSession:
    async def test_persists_modified_session(
        self, service: WhatsAppSessionService
    ) -> None:
        session = await service.create_session("+1234567890")
        session.flow = "create_tenant"
        session.step = "full_name"
        session.temp_data = {"full_name": "John Doe"}

        saved = await service.save_session(session)
        assert saved.flow == "create_tenant"
        assert saved.step == "full_name"
        assert saved.temp_data == {"full_name": "John Doe"}

        fetched = await service.get_session("+1234567890")
        assert fetched is not None
        assert fetched.flow == "create_tenant"
        assert fetched.step == "full_name"
        assert fetched.temp_data == {"full_name": "John Doe"}

    async def test_preserves_unchanged_fields(
        self, service: WhatsAppSessionService
    ) -> None:
        session = await service.create_session("+1234567890")
        session.flow = "list_tenants"
        await service.save_session(session)

        session.step = "selecting"
        await service.save_session(session)

        fetched = await service.get_session("+1234567890")
        assert fetched is not None
        assert fetched.flow == "list_tenants"  # unchanged
        assert fetched.step == "selecting"  # updated


@pytest.mark.asyncio
class TestUpdateSession:
    async def test_updates_single_field(
        self, service: WhatsAppSessionService
    ) -> None:
        await service.create_session("+1234567890")
        updated = await service.update_session(
            "+1234567890", flow="create_tenant"
        )
        assert updated is not None
        assert updated.flow == "create_tenant"
        assert updated.step == ""  # untouched

    async def test_updates_multiple_fields(
        self, service: WhatsAppSessionService
    ) -> None:
        await service.create_session("+1234567890")
        updated = await service.update_session(
            "+1234567890",
            flow="edit_tenant",
            step="choose_field",
            selected_tenant_id="uuid-target",
        )
        assert updated is not None
        assert updated.flow == "edit_tenant"
        assert updated.step == "choose_field"
        assert updated.selected_tenant_id == "uuid-target"

    async def test_updates_temp_data(
        self, service: WhatsAppSessionService
    ) -> None:
        await service.create_session("+1234567890")
        updated = await service.update_session(
            "+1234567890",
            temp_data={"full_name": "Jane"},
        )
        assert updated is not None
        assert updated.temp_data == {"full_name": "Jane"}

    async def test_updates_selection_map(
        self, service: WhatsAppSessionService
    ) -> None:
        await service.create_session("+1234567890")
        updated = await service.update_session(
            "+1234567890",
            selection_map={"1": "uuid-a", "2": "uuid-b"},
        )
        assert updated is not None
        assert updated.selection_map == {"1": "uuid-a", "2": "uuid-b"}

    async def test_returns_none_for_missing_session(
        self, service: WhatsAppSessionService
    ) -> None:
        result = await service.update_session("+9999999999", flow="main_menu")
        assert result is None


@pytest.mark.asyncio
class TestClearSession:
    async def test_removes_session(
        self, service: WhatsAppSessionService
    ) -> None:
        await service.create_session("+1234567890")
        await service.clear_session("+1234567890")

        fetched = await service.get_session("+1234567890")
        assert fetched is None

    async def test_clear_nonexistent_does_not_raise(
        self, service: WhatsAppSessionService
    ) -> None:
        # Should not raise when clearing a session that does not exist.
        await service.clear_session("+9999999999")


@pytest.mark.asyncio
class TestTTL:
    async def test_session_write_sets_ttl(
        self, service: WhatsAppSessionService, fake_redis: FakeRedis
    ) -> None:
        await service.create_session("+1234567890")
        key = service._session_key("+1234567890")
        ttl = fake_redis.get_ttl(key)
        assert ttl == 1800, f"Expected TTL 1800, got {ttl}"

    async def test_save_session_renews_ttl(
        self, service: WhatsAppSessionService, fake_redis: FakeRedis
    ) -> None:
        session = await service.create_session("+1234567890")
        key = service._session_key("+1234567890")

        # Simulate partial TTL passage by changing it
        fake_redis._ttls[key] = 900

        await service.save_session(session)

        ttl = fake_redis.get_ttl(key)
        assert ttl == 1800, f"Expected TTL 1800 after save, got {ttl}"

    async def test_update_session_sets_ttl(
        self, service: WhatsAppSessionService, fake_redis: FakeRedis
    ) -> None:
        await service.create_session("+1234567890")
        key = service._session_key("+1234567890")

        # Simulate partial TTL passage
        fake_redis._ttls[key] = 600

        await service.update_session("+1234567890", step="next")
        ttl = fake_redis.get_ttl(key)
        assert ttl == 1800, f"Expected TTL 1800 after update, got {ttl}"

    async def test_custom_ttl_seconds(
        self, fake_redis: FakeRedis
    ) -> None:
        custom_service = WhatsAppSessionService(
            redis_client=fake_redis, ttl_seconds=300
        )
        await custom_service.create_session("+1234567890")
        key = custom_service._session_key("+1234567890")
        ttl = fake_redis.get_ttl(key)
        assert ttl == 300
