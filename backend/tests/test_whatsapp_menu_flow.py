"""Tests for the WhatsApp Master Console menu and navigation flow.

Verifies main menu display, help text, global reset commands, fallback
messages, and session-aware routing.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.services.whatsapp_console_service import WhatsAppConsoleService
from app.services.whatsapp_session_service import WhatsAppSessionService
from app.services.whatsapp_tenant_console_service import (
    WhatsAppTenantConsoleService,
)


# ---------------------------------------------------------------------------
# Fake Redis — dict-based async double (same as session service tests)
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
        raise AttributeError(f"FakeRedis does not implement '{name}'")


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
def session_service(fake_redis: FakeRedis) -> WhatsAppSessionService:
    return WhatsAppSessionService(
        connection_manager=FakeManager(fake_redis=fake_redis),
        ttl_seconds=900,
    )


@pytest.fixture
def console_service() -> WhatsAppConsoleService:
    return WhatsAppConsoleService()


# ---------------------------------------------------------------------------
# Access control
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestAccessControl:
    async def test_non_master_gets_access_denied(
        self, console_service: WhatsAppConsoleService
    ) -> None:
        reply = await console_service.process_message(
            phone="+9999999999",
            message="hola",
            is_master=False,
        )
        assert "master" in reply.lower() or "solo" in reply.lower()

    async def test_master_gets_menu(
        self, console_service: WhatsAppConsoleService
    ) -> None:
        reply = await console_service.process_message(
            phone="+10000000000",
            message="hola",
            is_master=True,
        )
        # "hola" is unrecognised → fallback
        assert "No entendí" in reply
        assert "1" in reply
        assert "5" in reply


# ---------------------------------------------------------------------------
# Main menu
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestMainMenu:
    async def test_empty_message_returns_menu(
        self, console_service: WhatsAppConsoleService
    ) -> None:
        reply = await console_service.process_message(
            phone="+10000000000",
            message="",
            is_master=True,
        )
        assert "Trackpal Master Console" in reply

    async def test_blank_message_returns_menu(
        self, console_service: WhatsAppConsoleService
    ) -> None:
        reply = await console_service.process_message(
            phone="+10000000000",
            message="   ",
            is_master=True,
        )
        assert "Trackpal Master Console" in reply

    async def test_menu_contains_categories(
        self, console_service: WhatsAppConsoleService
    ) -> None:
        reply = console_service.MAIN_MENU
        assert "Ver Tenants" in reply
        assert "Crear Tenant" in reply
        assert "Desactivar Tenant" in reply
        assert "Eliminar Tenant" in reply
        assert "Ayuda" in reply
        assert "Cerrar sesión" in reply

    async def test_menu_contains_numeric_options(
        self, console_service: WhatsAppConsoleService
    ) -> None:
        reply = console_service.MAIN_MENU
        assert "1" in reply
        assert "2" in reply
        assert "3" in reply
        assert "4" in reply
        assert "5" in reply
        assert "0" in reply


# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestHelp:
    async def test_option_5_returns_help(
        self, console_service: WhatsAppConsoleService
    ) -> None:
        reply = await console_service.process_message(
            phone="+10000000000",
            message="5",
            is_master=True,
        )
        assert "Ayuda" in reply
        assert "comandos disponibles" in reply

    async def test_ayuda_returns_help(
        self, console_service: WhatsAppConsoleService
    ) -> None:
        reply = await console_service.process_message(
            phone="+10000000000",
            message="ayuda",
            is_master=True,
        )
        assert "Ayuda" in reply
        assert "comandos disponibles" in reply

    async def test_help_text_contains_menu_explanation(
        self, console_service: WhatsAppConsoleService
    ) -> None:
        reply = console_service.HELP_TEXT
        assert "Ver Tenants" in reply
        assert "Crear Tenant" in reply
        assert "Desactivar Tenant" in reply
        assert "Eliminar Tenant" in reply
        assert "cerrar sesión" in reply.lower() or "sesión" in reply.lower()
        assert "menu" in reply.lower()
        assert "/menu" in reply.lower()


# ---------------------------------------------------------------------------
# Global reset commands
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestResetCommands:
    @pytest.mark.parametrize("cmd", ["0", "menu", "menú", "/menu", "cancelar"])
    async def test_reset_returns_main_menu(
        self,
        console_service: WhatsAppConsoleService,
        cmd: str,
    ) -> None:
        reply = await console_service.process_message(
            phone="+10000000000",
            message=cmd,
            is_master=True,
        )
        assert "Trackpal Master Console" in reply

    @pytest.mark.parametrize("cmd", ["menu", "menú", "/menu", "cancelar"])
    async def test_reset_clears_session(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        cmd: str,
    ) -> None:
        # Create an active session first
        session = await session_service.create_session("+10000000000")
        session.flow = "create_tenant"
        session.step = "full_name"
        session.temp_data = {"full_name": "John Doe"}
        await session_service.save_session(session)

        # Verify session exists
        assert await session_service.get_session("+10000000000") is not None

        # Send reset command
        await console_service.process_message(
            phone="+10000000000",
            message=cmd,
            is_master=True,
            session_service=session_service,
        )

        # Session should be cleared
        fetched = await session_service.get_session("+10000000000")
        assert fetched is None

    @pytest.mark.parametrize("cmd", ["0", "menu", "menú", "/menu", "cancelar"])
    async def test_reset_without_session_service_does_not_raise(
        self,
        console_service: WhatsAppConsoleService,
        cmd: str,
    ) -> None:
        # Should not raise when session_service is None
        reply = await console_service.process_message(
            phone="+10000000000",
            message=cmd,
            is_master=True,
            session_service=None,
        )
        assert "Trackpal Master Console" in reply

    @pytest.mark.parametrize("cmd", ["MENU", "Menú", "/MENU", "/Menu", "CANCELAR"])
    async def test_reset_is_case_insensitive(
        self,
        console_service: WhatsAppConsoleService,
        cmd: str,
    ) -> None:
        reply = await console_service.process_message(
            phone="+10000000000",
            message=cmd,
            is_master=True,
        )
        assert "Trackpal Master Console" in reply


# ---------------------------------------------------------------------------
# Fallback messages
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestFallbackNoFlow:
    async def test_gibberish_returns_fallback(
        self, console_service: WhatsAppConsoleService
    ) -> None:
        reply = await console_service.process_message(
            phone="+10000000000",
            message="asdf1234",
            is_master=True,
        )
        assert "No entendí" in reply

    async def test_special_chars_returns_fallback(
        self, console_service: WhatsAppConsoleService
    ) -> None:
        reply = await console_service.process_message(
            phone="+10000000000",
            message="@#$%",
            is_master=True,
        )
        assert "No entendí" in reply

    async def test_fallback_suggests_valid_commands(
        self, console_service: WhatsAppConsoleService
    ) -> None:
        reply = console_service.FALLBACK_NO_FLOW
        assert "No entendí" in reply
        assert "1" in reply
        assert "5" in reply
        assert "0" in reply
        assert "menu" in reply.lower()
        assert "/menu" in reply.lower()
        assert "ayuda" in reply.lower()


@pytest.mark.asyncio
class TestFallbackActiveFlow:
    async def test_invalid_input_during_flow_returns_flow_fallback(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        # Create an active flow session at a step where "garbage" is invalid
        session = await session_service.create_session("+10000000000")
        session.flow = "create_tenant"
        session.step = "password_mode"  # only "1" or "2" are valid
        await session_service.save_session(session)

        reply = await console_service.process_message(
            phone="+10000000000",
            message="garbage",
            is_master=True,
            session_service=session_service,
        )
        assert "Opción inválida" in reply or "No entendí" in reply

    async def test_help_works_during_active_flow(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        # Create an active flow session
        session = await session_service.create_session("+10000000000")
        session.flow = "create_tenant"
        session.step = "full_name"
        await session_service.save_session(session)

        reply = await console_service.process_message(
            phone="+10000000000",
            message="ayuda",
            is_master=True,
            session_service=session_service,
        )
        assert "Ayuda" in reply
        assert "comandos disponibles" in reply

    async def test_reset_works_during_active_flow(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        # Create an active flow session
        session = await session_service.create_session("+10000000000")
        session.flow = "create_tenant"
        session.step = "full_name"
        await session_service.save_session(session)

        reply = await console_service.process_message(
            phone="+10000000000",
            message="cancelar",
            is_master=True,
            session_service=session_service,
        )
        assert "Trackpal Master Console" in reply
        assert "cancelada" in reply.lower() or "cancelado" in reply.lower()
        # Session should be cleared
        fetched = await session_service.get_session("+10000000000")
        assert fetched is None

    async def test_no_session_service_does_not_block_flow_fallback(
        self,
        console_service: WhatsAppConsoleService,
    ) -> None:
        # Without session_service, there's no way to know there's an active flow,
        # so the input should fall through to the no-flow fallback
        reply = await console_service.process_message(
            phone="+10000000000",
            message="garbage",
            is_master=True,
            session_service=None,
        )
        assert "No entendí" in reply


# ---------------------------------------------------------------------------
# Menu option placeholders (2-4) — recognised but not implemented
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestMenuOptionsNotImplemented:
    @pytest.mark.parametrize("opt", ["3", "4"])
    async def test_menu_option_returns_main_menu(
        self,
        console_service: WhatsAppConsoleService,
        opt: str,
    ) -> None:
        """Phase 4 recognises options 3-4 but returns the main menu;
        concrete flows are added in Phases 7-8. Option 2 now starts
        the create flow (Phase 6)."""
        reply = await console_service.process_message(
            phone="+10000000000",
            message=opt,
            is_master=True,
        )
        assert "Trackpal Master Console" in reply

    async def test_option_2_starts_create_flow(
        self,
        console_service: WhatsAppConsoleService,
    ) -> None:
        """Option 2 now starts the create Tenant flow (Phase 6)."""
        reply = await console_service.process_message(
            phone="+10000000000",
            message="2",
            is_master=True,
        )
        assert "Crear Tenant" in reply
        assert "nombre completo" in reply


# ---------------------------------------------------------------------------
# Session-aware routing without session service
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestNoSessionService:
    async def test_processes_reset_without_session_service(
        self, console_service: WhatsAppConsoleService
    ) -> None:
        reply = await console_service.process_message(
            phone="+10000000000",
            message="menu",
            is_master=True,
        )
        assert "Trackpal Master Console" in reply

    async def test_processes_help_without_session_service(
        self, console_service: WhatsAppConsoleService
    ) -> None:
        reply = await console_service.process_message(
            phone="+10000000000",
            message="ayuda",
            is_master=True,
        )
        assert "Ayuda" in reply
        assert "comandos disponibles" in reply

    async def test_processes_fallback_without_session_service(
        self, console_service: WhatsAppConsoleService
    ) -> None:
        reply = await console_service.process_message(
            phone="+10000000000",
            message="xyzzy",
            is_master=True,
        )
        assert "No entendí" in reply


# ---------------------------------------------------------------------------
# TTL noise guards — invalid input must not refresh session TTL
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestTTLNotRefreshedOnNoise:
    """Invalid/noise messages must not extend session TTL."""

    async def test_gibberish_no_flow_does_not_refresh_ttl(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        fake_redis: FakeRedis,
    ) -> None:
        """Gibberish without an active session just returns fallback."""
        # First create a session so there's something to measure
        reply = await console_service.process_message(
            phone="+10000000000",
            message="asdf1234",
            is_master=True,
            session_service=session_service,
        )
        assert "No entendí" in reply

        # After gibberish, no session key should be written
        fetched = await session_service.get_session("+10000000000")
        assert fetched is None

    async def test_gibberish_during_active_flow_does_not_refresh_ttl(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        fake_redis: FakeRedis,
    ) -> None:
        """Gibberish during active flow must not reset session TTL."""
        # Create an active session at password_mode step
        session = await session_service.create_session("+10000000000")
        session.flow = "create_tenant"
        session.step = "password_mode"
        session.temp_data = {"full_name": "Test"}
        await session_service.save_session(session)
        key = session_service._session_key("+10000000000")

        # Simulate partial TTL passage
        fake_redis._ttls[key] = 400

        # Send invalid input at password_mode step
        reply = await console_service.process_message(
            phone="+10000000000",
            message="garbage",
            is_master=True,
            session_service=session_service,
        )
        # Should reprompt for password mode
        assert "Opción inválida" in reply or "No entendí" in reply

        # TTL should NOT have been refreshed (still 400, not 900)
        assert fake_redis.get_ttl(key) == 400, (
            f"Expected TTL 400 (unchanged), got {fake_redis.get_ttl(key)}"
        )

    async def test_help_does_not_refresh_ttl(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        fake_redis: FakeRedis,
    ) -> None:
        """Help display must not extend TTL."""
        session = await session_service.create_session("+10000000000")
        session.flow = "create_tenant"
        session.step = "full_name"
        await session_service.save_session(session)
        key = session_service._session_key("+10000000000")

        fake_redis._ttls[key] = 300

        reply = await console_service.process_message(
            phone="+10000000000",
            message="ayuda",
            is_master=True,
            session_service=session_service,
        )
        assert "Ayuda" in reply

        # TTL unchanged
        assert fake_redis.get_ttl(key) == 300

    async def test_invalid_selection_during_list_does_not_refresh_ttl(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        fake_redis: FakeRedis,
    ) -> None:
        """Invalid selection during list flow must not reset TTL."""
        # Create a selection session
        session = await session_service.create_session("+10000000000")
        session.flow = "list_tenants"
        session.step = "select"
        session.selection_map = {"1": "uuid-a"}
        await session_service.save_session(session)
        key = session_service._session_key("+10000000000")

        fake_redis._ttls[key] = 500

        reply = await console_service.process_message(
            phone="+10000000000",
            message="99",
            is_master=True,
            session_service=session_service,
        )
        assert "número" in reply.lower() or "inválido" in reply.lower()

        # TTL unchanged
        assert fake_redis.get_ttl(key) == 500


# ---------------------------------------------------------------------------
# Tenant Admin Console navigation contract
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_redis_manager() -> FakeManager:
    return FakeManager()


@pytest.mark.asyncio
async def test_tenant_active_flow_zero_cancels_but_nine_does_not_global_cancel(
    fake_redis_manager: FakeManager,
) -> None:
    """When an active flow exists, 0 clears the session and 9 does not."""
    session_service = WhatsAppSessionService(fake_redis_manager, ttl_seconds=900)
    session = await session_service.create_session("admin:12015550001")
    session.flow = "clients"
    session.step = "list_select"
    session.selection_map = {"1": "00000000-0000-0000-0000-000000000001"}
    await session_service.save_session(session)

    service = WhatsAppTenantConsoleService()

    # 9 should NOT clear session during active flow
    nine_reply = await service.process_message(
        phone="12015550001",
        message="9",
        session_service=session_service,
    )
    assert "Operacion cancelada" not in nine_reply
    assert await session_service.get_session("admin:12015550001") is not None

    # 0 SHOULD clear session during active flow
    zero_reply = await service.process_message(
        phone="12015550001",
        message="0",
        session_service=session_service,
    )
    assert "salido de la consola" in zero_reply or "Operacion cancelada" in zero_reply
    assert await session_service.get_session("admin:12015550001") is None
