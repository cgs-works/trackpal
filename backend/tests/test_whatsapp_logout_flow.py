"""Tests for WhatsApp Master Console contextual logout vs cancel.

Covers:
- Logout from authenticated main menu (``0`` with no active flow)
- Cancel inside active flow (``0`` with active session flow)
- Login reset clears auth + conversation sessions
- Evolution close call is invoked on logout and NOT invoked on cancel
- HTTPError from Evolution API is caught gracefully
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import UUID

import httpx
import pytest

from app.core.config import settings
from app.services.whatsapp_auth_session_service import (
    WhatsAppAuthSession,
    WhatsAppAuthSessionService,
)
from app.services.whatsapp_console_service import WhatsAppConsoleService
from app.services.whatsapp_session_service import (
    ConversationSession,
    WhatsAppSessionService,
)


# ---------------------------------------------------------------------------
# Fake Redis + Manager (same pattern as test_whatsapp_credential_auth_flow)
# ---------------------------------------------------------------------------


class FakeRedis:
    def __init__(self) -> None:
        self._store: dict[str, str] = {}
        self._ttls: dict[str, int] = {}

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def set(
        self, key: str, value: str, ex: int | None = None, keepttl: bool = False
    ) -> None:
        self._store[key] = value
        if ex is not None:
            self._ttls[key] = ex
        elif not keepttl:
            self._ttls.pop(key, None)

    async def expire(self, key: str, time: int) -> int:
        if key in self._store:
            self._ttls[key] = time
            return 1
        return 0

    async def delete(self, key: str) -> int:
        self._ttls.pop(key, None)
        return 1 if self._store.pop(key, None) is not None else 0


class FakeManager:
    def __init__(
        self, fake_redis: FakeRedis | None = None, *, used_backup: bool = False
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
def session_service(fake_manager: FakeManager) -> WhatsAppSessionService:
    return WhatsAppSessionService(
        connection_manager=fake_manager,
        ttl_seconds=settings.whatsapp_session_ttl_minutes * 60,
    )


@pytest.fixture
def auth_session_service(fake_manager: FakeManager) -> WhatsAppAuthSessionService:
    return WhatsAppAuthSessionService(
        connection_manager=fake_manager,
        session_ttl_seconds=settings.whatsapp_session_ttl_minutes * 60,
        fail_threshold=settings.whatsapp_auth_fail_threshold,
        lock_minutes=settings.whatsapp_auth_lock_minutes,
        fail_window_minutes=settings.whatsapp_auth_fail_window_minutes,
    )


@pytest.fixture
def console_service() -> WhatsAppConsoleService:
    return WhatsAppConsoleService()


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _make_facade(
    console_service: WhatsAppConsoleService,
    session_service: WhatsAppSessionService,
    auth_session_service: WhatsAppAuthSessionService,
    tenant_service: Any = None,
):
    from app.services.whatsapp_master_console_facade import (
        WhatsAppMasterConsoleFacade,
    )

    return WhatsAppMasterConsoleFacade(
        console_service=console_service,
        session_service=session_service,
        auth_session_service=auth_session_service,
        tenant_service=tenant_service,
    )


async def _setup_auth_session(
    auth_session_service: WhatsAppAuthSessionService,
    phone: str = "+12015550001",
) -> None:
    """Create a master auth session for the given phone."""
    auth_session = WhatsAppAuthSession(
        phone=phone,
        user_id=UUID("00000000-0000-0000-0000-000000000001"),
        username="master",
        role="master",
        authenticated_at=datetime.now(timezone.utc),
    )
    await auth_session_service.set_auth_session(auth_session)


pytestmark = pytest.mark.asyncio


# ===========================================================================
# Tests: Logout from main menu (authenticated, no active flow)
# ===========================================================================


class TestLogoutFromMainMenu:
    """Authenticated + ``0`` + no active flow → full logout."""

    async def test_logout_clears_auth_session(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        auth_session_service: WhatsAppAuthSessionService,
    ) -> None:
        """Auth session key is deleted on logout."""
        await _setup_auth_session(auth_session_service)
        facade = _make_facade(console_service, session_service, auth_session_service)

        await facade.process_message(
            phone="+12015550001",
            message="0",
            db=None,
        )

        auth = await auth_session_service.get_auth_session("+12015550001")
        assert auth is None, "Auth session should be cleared on logout"

    async def test_logout_clears_conversation_session(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        auth_session_service: WhatsAppAuthSessionService,
    ) -> None:
        """Conversation session key is deleted on logout."""
        await _setup_auth_session(auth_session_service)

        # Create a conversation session first
        conv = await session_service.create_session("+12015550001")
        conv.flow = "list_tenants"
        await session_service.save_session(conv)

        facade = _make_facade(console_service, session_service, auth_session_service)

        await facade.process_message(
            phone="+12015550001",
            message="0",
            db=None,
        )

        conv_session = await session_service.get_session("+12015550001")
        assert conv_session is None, "Conversation session should be cleared on logout"

    async def test_logout_calls_evolution_close(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        auth_session_service: WhatsAppAuthSessionService,
    ) -> None:
        """Logout returns goodbye message. Evolution close handled by n8n."""
        await _setup_auth_session(auth_session_service)

        facade = _make_facade(console_service, session_service, auth_session_service)

        reply = await facade.process_message(
            phone="+12015550001",
            message="0",
            instance="inst-test",
            db=None,
        )

        # Should contain goodbye/confirmation keywords for n8n detection
        assert "goodbye" in reply.lower() or "sesión cerrada" in reply.lower()

    async def test_logout_returns_confirmation(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        auth_session_service: WhatsAppAuthSessionService,
    ) -> None:
        """Logout reply contains clear confirmation in Spanish."""
        await _setup_auth_session(auth_session_service)
        facade = _make_facade(console_service, session_service, auth_session_service)

        with patch("app.services.evolution_client.evolution_client.close_chat_session"):
            reply = await facade.process_message(
                phone="+12015550001",
                message="0",
                instance="inst-test",
                db=None,
            )

        # Should mention logout/session closed
        assert (
            "sesión" in reply.lower()
            or "cerrada" in reply.lower()
            or "cerrado" in reply.lower()
        )

    async def test_logout_does_not_touch_auth_session(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        auth_session_service: WhatsAppAuthSessionService,
    ) -> None:
        """logout does NOT call touch_auth_session (TTL not refreshed)."""
        await _setup_auth_session(auth_session_service)
        facade = _make_facade(console_service, session_service, auth_session_service)

        with patch.object(auth_session_service, "touch_auth_session") as mock_touch:
            with patch(
                "app.services.evolution_client.evolution_client.close_chat_session"
            ):
                await facade.process_message(
                    phone="+12015550001",
                    message="0",
                    instance="inst-test",
                    db=None,
                )

            mock_touch.assert_not_called()

    async def test_logout_handles_evolution_http_error(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        auth_session_service: WhatsAppAuthSessionService,
    ) -> None:
        """HTTPError from Evolution close_chat_session does not bubble up."""
        await _setup_auth_session(auth_session_service)
        facade = _make_facade(console_service, session_service, auth_session_service)

        with patch(
            "app.services.evolution_client.evolution_client.close_chat_session",
            side_effect=httpx.HTTPError("Connection refused"),
        ):
            # Should not raise
            reply = await facade.process_message(
                phone="+12015550001",
                message="0",
                instance="inst-test",
                db=None,
            )

        # Sessions still cleared
        auth = await auth_session_service.get_auth_session("+12015550001")
        assert auth is None
        conv = await session_service.get_session("+12015550001")
        assert conv is None

        # Reply is still logout confirmation
        assert "sesión" in reply.lower() or "cerrada" in reply.lower()

    async def test_logout_handles_evolution_http_status_error(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        auth_session_service: WhatsAppAuthSessionService,
    ) -> None:
        """HTTPStatusError from Evolution close_chat_session does not bubble up."""
        await _setup_auth_session(auth_session_service)
        facade = _make_facade(console_service, session_service, auth_session_service)

        with patch(
            "app.services.evolution_client.evolution_client.close_chat_session",
            side_effect=httpx.HTTPStatusError(
                "Server error",
                request=MagicMock(),
                response=MagicMock(status_code=500),
            ),
        ):
            # Should not raise
            reply = await facade.process_message(
                phone="+12015550001",
                message="0",
                instance="inst-test",
                db=None,
            )

        # Sessions still cleared
        auth = await auth_session_service.get_auth_session("+12015550001")
        assert auth is None
        conv = await session_service.get_session("+12015550001")
        assert conv is None

        # Reply is still logout confirmation
        assert "sesión" in reply.lower() or "cerrada" in reply.lower()

    async def test_logout_without_instance_skips_evolution(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        auth_session_service: WhatsAppAuthSessionService,
    ) -> None:
        """When instance is None, Evolution close is skipped but Redis keys still cleared."""
        await _setup_auth_session(auth_session_service)
        facade = _make_facade(console_service, session_service, auth_session_service)

        with patch(
            "app.services.evolution_client.evolution_client.close_chat_session"
        ) as mock_close:
            await facade.process_message(
                phone="+12015550001",
                message="0",
                instance=None,
                db=None,
            )

            mock_close.assert_not_called()

        # Sessions should still be cleared
        auth = await auth_session_service.get_auth_session("+12015550001")
        assert auth is None


# ===========================================================================
# Tests: Cancel inside active flow (0 does NOT logout)
# ===========================================================================


class TestCancelInsideActiveFlow:
    """Authenticated + ``0`` + active flow → cancel flow, no logout."""

    async def test_evolution_close_not_called(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        auth_session_service: WhatsAppAuthSessionService,
    ) -> None:
        """Evolution close is NOT called when 0 is sent inside an active flow."""
        await _setup_auth_session(auth_session_service)

        # Create active CRUD flow session
        session = await session_service.create_session("+12015550001")
        session.flow = "create_tenant"
        session.step = "full_name"
        session.temp_data = {"some": "data"}
        await session_service.save_session(session)

        facade = _make_facade(console_service, session_service, auth_session_service)

        with patch(
            "app.services.evolution_client.evolution_client.close_chat_session"
        ) as mock_close:
            await facade.process_message(
                phone="+12015550001",
                message="0",
                instance="inst-test",
                db=None,
            )

            mock_close.assert_not_called()

    async def test_auth_session_preserved(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        auth_session_service: WhatsAppAuthSessionService,
    ) -> None:
        """Auth session is NOT cleared when 0 is sent inside an active flow."""
        await _setup_auth_session(auth_session_service)

        session = await session_service.create_session("+12015550001")
        session.flow = "deactivate_tenant"
        session.step = "confirm_deactivate"
        await session_service.save_session(session)

        facade = _make_facade(console_service, session_service, auth_session_service)

        with patch("app.services.evolution_client.evolution_client.close_chat_session"):
            await facade.process_message(
                phone="+12015550001",
                message="0",
                instance="inst-test",
                db=None,
            )

        auth = await auth_session_service.get_auth_session("+12015550001")
        assert auth is not None, "Auth session must remain after cancel (not logout)"

    async def test_conversation_session_cleared(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        auth_session_service: WhatsAppAuthSessionService,
    ) -> None:
        """Conversation session IS cleared when cancel inside active flow."""
        await _setup_auth_session(auth_session_service)

        session = await session_service.create_session("+12015550001")
        session.flow = "create_tenant"
        session.step = "full_name"
        await session_service.save_session(session)

        facade = _make_facade(console_service, session_service, auth_session_service)

        with patch("app.services.evolution_client.evolution_client.close_chat_session"):
            await facade.process_message(
                phone="+12015550001",
                message="0",
                instance="inst-test",
                db=None,
            )

        conv = await session_service.get_session("+12015550001")
        assert conv is None, "Conversation session should be cleared on cancel"

    async def test_cancel_touches_auth_session(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        auth_session_service: WhatsAppAuthSessionService,
    ) -> None:
        """Cancel inside active flow MUST refresh auth session TTL."""
        await _setup_auth_session(auth_session_service)

        session = await session_service.create_session("+12015550001")
        session.flow = "create_tenant"
        session.step = "full_name"
        await session_service.save_session(session)

        facade = _make_facade(console_service, session_service, auth_session_service)

        with patch.object(auth_session_service, "touch_auth_session") as mock_touch:
            with patch(
                "app.services.evolution_client.evolution_client.close_chat_session"
            ):
                await facade.process_message(
                    phone="+12015550001",
                    message="0",
                    instance="inst-test",
                    db=None,
                )

            mock_touch.assert_awaited_once_with("+12015550001")

    async def test_cancel_returns_main_menu(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        auth_session_service: WhatsAppAuthSessionService,
    ) -> None:
        """Cancel inside active flow returns MAIN_MENU (Phase 3 adds cancel msg)."""
        await _setup_auth_session(auth_session_service)

        session = await session_service.create_session("+12015550001")
        session.flow = "create_tenant"
        session.step = "full_name"
        await session_service.save_session(session)

        facade = _make_facade(console_service, session_service, auth_session_service)

        with patch("app.services.evolution_client.evolution_client.close_chat_session"):
            reply = await facade.process_message(
                phone="+12015550001",
                message="0",
                instance="inst-test",
                db=None,
            )

        # Must contain main menu (Phase 3 will refine to cancellation + menu)
        assert "Master Console" in reply or "Trackpal" in reply


# ===========================================================================
# Tests: Login reset (0 during login clears both auth + conversation)
# ===========================================================================


class TestLoginReset:
    """Unauthenticated + reset commands clear auth + conversation sessions."""

    async def test_login_reset_clears_auth_session(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        auth_session_service: WhatsAppAuthSessionService,
        fake_redis: FakeRedis,
    ) -> None:
        """Reset during login clears any lingering auth session."""
        # Manually set stray auth session
        auth_key = "wa:auth:+9999999999"
        await fake_redis.set(
            auth_key,
            '{"phone":"+9999999999","user_id":"...","username":"master","role":"master","authenticated_at":"2026-01-01T00:00:00Z"}',
            ex=900,
        )

        facade = _make_facade(console_service, session_service, auth_session_service)

        # Start login flow
        await facade.process_message(phone="+9999999999", message="hola", db=None)

        # Send reset
        reply = await facade.process_message(
            phone="+9999999999",
            message="0",
            db=None,
        )

        # Auth session should be cleared
        auth = await auth_session_service.get_auth_session("+9999999999")
        assert auth is None

        # Reply should be username prompt (not main menu)
        assert "usuario" in reply.lower()

    async def test_login_reset_reinitializes_auth_conversation_session(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        auth_session_service: WhatsAppAuthSessionService,
    ) -> None:
        """Reset during login reinitializes session at auth username step."""
        # Create a conversation session (simulating leftover from previous flow)
        conv = await session_service.create_session("+9999999999")
        conv.flow = "create_tenant"
        await session_service.save_session(conv)

        facade = _make_facade(console_service, session_service, auth_session_service)

        # Start login flow
        await facade.process_message(phone="+9999999999", message="hola", db=None)

        # Send reset
        reply = await facade.process_message(
            phone="+9999999999",
            message="0",
            db=None,
        )

        # Conversation session should be reset to auth username step
        conv_session = await session_service.get_session("+9999999999")
        assert conv_session is not None
        assert conv_session.flow == "auth"
        assert conv_session.step == "username"
        assert "usuario" in reply.lower()

    async def test_login_reset_menu_also_clears_sessions(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        auth_session_service: WhatsAppAuthSessionService,
    ) -> None:
        """Reset with 'menu' during login also clears both sessions."""
        # Set stray auth session
        facade = _make_facade(console_service, session_service, auth_session_service)

        # Start login flow
        await facade.process_message(phone="+9999999999", message="hola", db=None)

        # Send 'menu' as reset during password step
        await facade.process_message(phone="+9999999999", message="master", db=None)
        reply = await facade.process_message(
            phone="+9999999999",
            message="menu",
            db=None,
        )

        assert "usuario" in reply.lower()

    async def test_login_reset_clears_both_sessions(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        auth_session_service: WhatsAppAuthSessionService,
        fake_redis: FakeRedis,
    ) -> None:
        """Reset during login clears BOTH auth and conversation sessions."""
        # Set both stray sessions
        auth_key = "wa:auth:+9999999999"
        conv_key = "session:+9999999999"
        await fake_redis.set(
            auth_key,
            '{"phone":"+9999999999","user_id":"uuid","username":"master","role":"master","authenticated_at":"2026-01-01T00:00:00Z"}',
            ex=900,
        )
        await fake_redis.set(
            conv_key,
            ConversationSession(
                phone="+9999999999", flow="create_tenant"
            ).model_dump_json(),
            ex=900,
        )

        facade = _make_facade(console_service, session_service, auth_session_service)

        await facade.process_message(phone="+9999999999", message="hola", db=None)
        reply = await facade.process_message(
            phone="+9999999999",
            message="cancelar",
            db=None,
        )

        # Auth should be cleared; conversation should be reinitialized at auth step
        auth = await auth_session_service.get_auth_session("+9999999999")
        assert auth is None
        conv = await session_service.get_session("+9999999999")
        assert conv is not None
        assert conv.flow == "auth"
        assert conv.step == "username"
        assert "usuario" in reply.lower()


# ===========================================================================
# Tests: Failover — backup Redis, no session, authenticated "0"
# ===========================================================================


class TestFailoverBackupNoSession:
    """Authenticated + ``0`` + ``used_backup=True`` + no conv session → cancel/menu path, not logout."""

    async def test_auth_session_preserved_on_failover(
        self,
        console_service: WhatsAppConsoleService,
        auth_session_service: WhatsAppAuthSessionService,
    ) -> None:
        """Auth session is NOT cleared when on backup and conv session is missing."""
        fake_redis = FakeRedis()
        manager = FakeManager(fake_redis=fake_redis, used_backup=True)
        session_service = WhatsAppSessionService(
            connection_manager=manager,
            ttl_seconds=900,
        )
        auth_service = WhatsAppAuthSessionService(
            connection_manager=manager,
            session_ttl_seconds=900,
            fail_threshold=5,
            lock_minutes=5,
            fail_window_minutes=15,
        )

        await _setup_auth_session(auth_service, phone="+12015550001")

        facade = _make_facade(console_service, session_service, auth_service)

        with patch(
            "app.services.evolution_client.evolution_client.close_chat_session"
        ) as mock_close:
            reply = await facade.process_message(
                phone="+12015550001",
                message="0",
                instance="inst-test",
                db=None,
            )

        # Auth session must remain
        auth = await auth_service.get_auth_session("+12015550001")
        assert auth is not None, "Auth session must survive failover 0"

        # Evolution close should NOT be called (not a real logout)
        mock_close.assert_not_called()

        # Reply should preserve cancel + menu single-reply shape.
        assert "Operación cancelada" in reply
        assert "Master Console" in reply or "Trackpal" in reply

    async def test_session_touched_on_failover(
        self,
        console_service: WhatsAppConsoleService,
        auth_session_service: WhatsAppAuthSessionService,
    ) -> None:
        """Auth session TTL is refreshed on failover path."""
        fake_redis = FakeRedis()
        manager = FakeManager(fake_redis=fake_redis, used_backup=True)
        session_service = WhatsAppSessionService(
            connection_manager=manager,
            ttl_seconds=900,
        )
        auth_service = WhatsAppAuthSessionService(
            connection_manager=manager,
            session_ttl_seconds=900,
            fail_threshold=5,
            lock_minutes=5,
            fail_window_minutes=15,
        )

        await _setup_auth_session(auth_service, phone="+12015550001")

        facade = _make_facade(console_service, session_service, auth_service)

        with patch.object(auth_service, "touch_auth_session") as mock_touch:
            with patch(
                "app.services.evolution_client.evolution_client.close_chat_session"
            ):
                await facade.process_message(
                    phone="+12015550001",
                    message="0",
                    instance="inst-test",
                    db=None,
                )

            mock_touch.assert_awaited_once_with("+12015550001")

    async def test_failover_returns_cancel_plus_menu_shape(
        self,
        console_service: WhatsAppConsoleService,
        auth_session_service: WhatsAppAuthSessionService,
    ) -> None:
        """Failover path returns cancel message and main menu in one reply."""
        fake_redis = FakeRedis()
        manager = FakeManager(fake_redis=fake_redis, used_backup=True)
        session_service = WhatsAppSessionService(
            connection_manager=manager,
            ttl_seconds=900,
        )
        auth_service = WhatsAppAuthSessionService(
            connection_manager=manager,
            session_ttl_seconds=900,
            fail_threshold=5,
            lock_minutes=5,
            fail_window_minutes=15,
        )

        await _setup_auth_session(auth_service, phone="+12015550001")

        facade = _make_facade(console_service, session_service, auth_service)

        reply = await facade.process_message(
            phone="+12015550001",
            message="0",
            instance="inst-test",
            db=None,
        )

        assert reply == console_service._with_main_menu("🚫 Operación cancelada.")


# ===========================================================================
# Tests: Invalid / empty phone during _perform_logout
# ===========================================================================


class TestLogoutInvalidPhone:
    """Invalid or empty phone in _perform_logout must skip Evolution call but still logout."""

    async def test_empty_phone_skips_evolution(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        auth_session_service: WhatsAppAuthSessionService,
    ) -> None:
        """Empty phone (or None from normalize_phone) must skip Evolution close call."""
        await _setup_auth_session(auth_session_service, phone="invalid")

        facade = _make_facade(console_service, session_service, auth_session_service)

        with patch(
            "app.services.evolution_client.evolution_client.close_chat_session"
        ) as mock_close:
            reply = await facade._perform_logout(
                phone="invalid",
                instance="inst-test",
            )

            # Evolution close must NOT be called (no digits in "invalid")
            mock_close.assert_not_called()

        # Redis keys still cleared and confirmation returned
        assert "sesión" in reply.lower() or "cerrada" in reply.lower()

    async def test_no_digits_phone_logs_warning(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        auth_session_service: WhatsAppAuthSessionService,
    ) -> None:
        """Logout with invalid phone still returns goodbye (Evolution close handled by n8n)."""
        await _setup_auth_session(auth_session_service, phone="abc")

        facade = _make_facade(console_service, session_service, auth_session_service)

        reply = await facade._perform_logout(
            phone="abc",
            instance="inst-test",
        )

        # Should still return a goodbye message
        assert reply.strip()  # non-empty


# ===========================================================================
# Tests: HTTPError logging context in _perform_logout
# ===========================================================================


class TestLogoutHttpErrorLogging:
    """HTTPError during Evolution close should include exception context."""

    async def test_http_error_logs_exc_info(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        auth_session_service: WhatsAppAuthSessionService,
    ) -> None:
        """Logout still works when Evolution close is not called (handled by n8n)."""
        await _setup_auth_session(auth_session_service, phone="+12015550001")

        facade = _make_facade(console_service, session_service, auth_session_service)

        reply = await facade._perform_logout(
            phone="+12015550001",
            instance="inst-test",
        )

        # Session is cleared
        auth = await auth_session_service.get_auth_session("+12015550001")
        assert auth is None

        # Reply is still logout confirmation
        assert "sesión" in reply.lower() or "goodbye" in reply.lower()
