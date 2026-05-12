"""Tests for the WhatsApp Master Console menu and navigation flow.

Verifies main menu display, help text, global reset commands, fallback
messages, and session-aware routing.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.services.whatsapp_console_service import WhatsAppConsoleService
from app.services.whatsapp_session_service import (
    ConversationSession,
    WhatsAppSessionService,
)


# ---------------------------------------------------------------------------
# Fake Redis — dict-based async double (same as session service tests)
# ---------------------------------------------------------------------------

class FakeRedis:
    """Minimal in-memory fake for redis.asyncio.Redis."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self._store[key] = value

    async def delete(self, key: str) -> int:
        return 1 if self._store.pop(key, None) is not None else 0

    async def exists(self, key: str) -> int:
        return 1 if key in self._store else 0

    def __getattr__(self, name: str) -> Any:
        raise AttributeError(f"FakeRedis does not implement '{name}'")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def fake_redis() -> FakeRedis:
    return FakeRedis()


@pytest.fixture
def session_service(fake_redis: FakeRedis) -> WhatsAppSessionService:
    return WhatsAppSessionService(redis_client=fake_redis, ttl_seconds=1800)


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
        assert "Cancelar / Menú" in reply

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
        assert "Cancelar / Menú" in reply
        assert "menu" in reply.lower()


# ---------------------------------------------------------------------------
# Global reset commands
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestResetCommands:
    @pytest.mark.parametrize("cmd", ["0", "menu", "menú", "cancelar"])
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

    @pytest.mark.parametrize("cmd", ["0", "menu", "menú", "cancelar"])
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

    @pytest.mark.parametrize("cmd", ["0", "menu", "menú", "cancelar"])
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

    @pytest.mark.parametrize("cmd", ["MENU", "Menú", "CANCELAR"])
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
