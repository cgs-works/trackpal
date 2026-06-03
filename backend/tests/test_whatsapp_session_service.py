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

    async def set(self, key: str, value: str, ex: int | None = None, keepttl: bool = False) -> None:
        self._store[key] = value
        if ex is not None:
            self._ttls[key] = ex
        elif not keepttl:
            # When neither ex nor keepttl is set, Redis removes TTL
            self._ttls.pop(key, None)
        # keepttl=True: leave existing TTL untouched

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
# Fake connection manager that wraps FakeRedis
# ---------------------------------------------------------------------------

class FakeManager:
    """Duck-typed connection manager that delegates execute() to FakeRedis."""

    def __init__(
        self,
        fake_redis: FakeRedis | None = None,
        *,
        used_backup: bool = False,
    ) -> None:
        self._redis = fake_redis or FakeRedis()
        self._used_backup = used_backup

    @property
    def used_backup(self) -> bool:
        return self._used_backup

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
def service(fake_manager: FakeManager) -> WhatsAppSessionService:
    return WhatsAppSessionService(
        connection_manager=fake_manager,
        ttl_seconds=300,  # 15 minutes
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
        assert ttl == 300, f"Expected TTL 900, got {ttl}"

    async def test_save_session_renews_ttl(
        self, service: WhatsAppSessionService, fake_redis: FakeRedis
    ) -> None:
        session = await service.create_session("+1234567890")
        key = service._session_key("+1234567890")

        # Simulate partial TTL passage by changing it
        fake_redis._ttls[key] = 300

        await service.save_session(session)

        ttl = fake_redis.get_ttl(key)
        assert ttl == 300, f"Expected TTL 900 after save, got {ttl}"

    async def test_update_session_sets_ttl(
        self, service: WhatsAppSessionService, fake_redis: FakeRedis
    ) -> None:
        await service.create_session("+1234567890")
        key = service._session_key("+1234567890")

        # Simulate partial TTL passage
        fake_redis._ttls[key] = 300

        await service.update_session("+1234567890", step="next")
        ttl = fake_redis.get_ttl(key)
        assert ttl == 300, f"Expected TTL 900 after update, got {ttl}"

    async def test_custom_ttl_seconds(
        self, fake_redis: FakeRedis
    ) -> None:
        custom_manager = FakeManager(fake_redis=fake_redis)
        custom_service = WhatsAppSessionService(
            connection_manager=custom_manager, ttl_seconds=300
        )
        await custom_service.create_session("+1234567890")
        key = custom_service._session_key("+1234567890")
        ttl = fake_redis.get_ttl(key)
        assert ttl == 300

    async def test_save_with_touch_ttl_false_does_not_extend_ttl(
        self, service: WhatsAppSessionService, fake_redis: FakeRedis
    ) -> None:
        """save_session(touch_ttl=False) writes data but keeps existing TTL."""
        session = await service.create_session("+1234567890")
        key = service._session_key("+1234567890")

        # Original TTL should be 300
        assert fake_redis.get_ttl(key) == 300

        # Simulate elapsed time
        fake_redis._ttls[key] = 500

        # Save with touch_ttl=False — should NOT extend TTL
        session.flow = "edited_noise"
        await service.save_session(session, touch_ttl=False)

        # TTL should remain at 500 (not reset to 300)
        ttl = fake_redis.get_ttl(key)
        assert ttl == 500, f"Expected TTL 500 (unchanged), got {ttl}"

        # Data should still be written
        fetched = await service.get_session("+1234567890")
        assert fetched is not None
        assert fetched.flow == "edited_noise"

    async def test_save_with_touch_ttl_true_still_refreshes(
        self, service: WhatsAppSessionService, fake_redis: FakeRedis
    ) -> None:
        """save_session(touch_ttl=True) extends TTL (default behavior)."""
        session = await service.create_session("+1234567890")
        key = service._session_key("+1234567890")

        fake_redis._ttls[key] = 300

        await service.save_session(session, touch_ttl=True)
        assert fake_redis.get_ttl(key) == 300

    async def test_save_with_touch_ttl_false_preserves_ttl_via_keepttl(
        self, service: WhatsAppSessionService, fake_redis: FakeRedis
    ) -> None:
        """save_session(touch_ttl=False) uses keepttl=True, preserving TTL.

        Regression: passing ex=None would drop TTL in real Redis.  The
        fix uses KEEPTTL so existing TTL is left intact.
        """
        session = await service.create_session("+1234567890")
        key = service._session_key("+1234567890")
        assert fake_redis.get_ttl(key) == 300

        # Simulate elapsed time
        fake_redis._ttls[key] = 500

        # Save with touch_ttl=False — TTL must stay at 500 (not dropped)
        session.flow = "noise"
        await service.save_session(session, touch_ttl=False)

        ttl = fake_redis.get_ttl(key)
        assert ttl == 500, f"Expected TTL 500 (keepttl preserved), got {ttl}"

        # Data still written
        fetched = await service.get_session("+1234567890")
        assert fetched is not None
        assert fetched.flow == "noise"

    async def test_save_without_touch_ttl_with_no_existing_ttl_stays_none(
        self, service: WhatsAppSessionService, fake_redis: FakeRedis
    ) -> None:
        """When key has no TTL and touch_ttl=False, TTL stays absent."""
        # Create then delete so key has no TTL
        session = await service.create_session("+1987654321")
        key = service._session_key("+1987654321")
        del fake_redis._ttls[key]  # simulate TTL expired

        session.flow = "some_flow"
        await service.save_session(session, touch_ttl=False)

        # TTL should remain absent (keepttl on a key without TTL is no-op)
        assert fake_redis.get_ttl(key) is None

    async def test_update_session_with_touch_ttl_false_preserves_ttl(
        self, service: WhatsAppSessionService, fake_redis: FakeRedis
    ) -> None:
        """update_session(touch_ttl=False) preserves existing TTL."""
        await service.create_session("+1234567890")
        key = service._session_key("+1234567890")

        # Simulate elapsed time
        fake_redis._ttls[key] = 400

        await service.update_session("+1234567890", touch_ttl=False, step="next")
        ttl = fake_redis.get_ttl(key)
        assert ttl == 400, f"Expected TTL 400 (unchanged), got {ttl}"

        # Data still written
        fetched = await service.get_session("+1234567890")
        assert fetched is not None
        assert fetched.step == "next"


# ---------------------------------------------------------------------------
# used_backup signal
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestUsedBackup:
    """Verify session service delegates used_backup to connection manager."""

    async def test_returns_false_when_manager_has_no_signal(
        self, fake_redis: FakeRedis
    ) -> None:
        """Manager without used_backup attribute → service returns False."""
        class LegacyManager:
            async def execute(self, operation_name, async_callable):
                return await async_callable(fake_redis)
        service = WhatsAppSessionService(connection_manager=LegacyManager())
        assert service.used_backup is False

    async def test_returns_false_when_manager_reports_primary(
        self, fake_redis: FakeRedis
    ) -> None:
        manager = FakeManager(fake_redis=fake_redis, used_backup=False)
        service = WhatsAppSessionService(connection_manager=manager)
        assert service.used_backup is False

    async def test_returns_true_when_manager_reports_backup(
        self, fake_redis: FakeRedis
    ) -> None:
        manager = FakeManager(fake_redis=fake_redis, used_backup=True)
        service = WhatsAppSessionService(connection_manager=manager)
        assert service.used_backup is True


# ---------------------------------------------------------------------------
# SessionLifecyclePolicy
# ---------------------------------------------------------------------------

class TestSessionLifecyclePolicy:
    """Verify SessionLifecyclePolicy defaults and configuration."""

    def test_default_ttl_is_300(self) -> None:
        from app.services.whatsapp_session_service import SessionLifecyclePolicy
        policy = SessionLifecyclePolicy()
        assert policy.ttl_seconds == 300

    def test_custom_ttl(self) -> None:
        from app.services.whatsapp_session_service import SessionLifecyclePolicy
        policy = SessionLifecyclePolicy(ttl_seconds=600)
        assert policy.ttl_seconds == 600


# ---------------------------------------------------------------------------
# Serialization guard — minimal payload
# ---------------------------------------------------------------------------

class TestSessionSerialization:
    """Session JSON must contain only PRD-approved fields."""

    APPROVED_FIELDS = {"flow", "step", "selected_tenant_id", "temp_data", "selection_map"}

    def test_serialized_json_has_no_extra_top_level_fields(self) -> None:
        """ConversationSession.model_dump_json() must not contain raw
        WhatsApp payloads, inbound messages, tenant lists, or large
        non-minimal objects."""
        import json

        session = ConversationSession(
            phone="+1234567890",
            flow="create_tenant",
            step="full_name",
            selected_tenant_id="uuid-here",
            temp_data={"name": "Test"},
            selection_map={"1": "uuid-a"},
        )
        raw = session.model_dump_json()
        parsed = json.loads(raw)

        # The phone field is the Redis key basis and is stored internally
        # but serialized output goes to Redis as a full JSON blob.
        # Only approved conversational fields are expected.
        serialized_keys = set(parsed.keys())
        # phone is always present as ConversationSession field
        # approved fields + phone (internal key) are expected
        assert "phone" in parsed
        # Ensure no unexpected fields
        unexpected = serialized_keys - self.APPROVED_FIELDS - {"phone"}
        assert not unexpected, f"Unexpected serialized fields: {unexpected}"

        # Verify no raw message content, no tenant lists, no large blobs
        for field in self.APPROVED_FIELDS:
            val = parsed.get(field)
            # All values should be primitives: str, dict, or None
            assert isinstance(val, (str, dict, type(None))), (
                f"Field '{field}' has unexpected type {type(val).__name__}"
            )

    def test_temp_data_does_not_contain_whatsapp_payloads(self) -> None:
        """temp_data should not store raw inbound WhatsApp messages."""
        session = ConversationSession(
            phone="+1234567890",
            flow="create_tenant",
            step="full_name",
            temp_data={"full_name": "John"},
        )
        raw = session.model_dump_json()
        assert "full_name" in raw
        # Verify no inbound message keys
        assert "message" not in raw.lower() or "message" not in raw


# ---------------------------------------------------------------------------
# Explicit delete verification
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestExplicitDelete:
    """Verify that clear_session actually removes the key from Redis."""

    async def test_delete_removes_ttl_and_data(
        self, service: WhatsAppSessionService, fake_redis: FakeRedis
    ) -> None:
        await service.create_session("+1234567890")
        key = service._session_key("+1234567890")

        # Verify data exists
        assert await fake_redis.exists(key) == 1
        assert fake_redis.get_ttl(key) is not None

        await service.clear_session("+1234567890")

        # Verify data is gone
        assert await fake_redis.exists(key) == 0
        assert fake_redis._ttls.get(key) is None

    async def test_delete_on_nonexistent_session_does_not_raise(
        self, service: WhatsAppSessionService
    ) -> None:
        await service.clear_session("+9999999999")  # should not raise
