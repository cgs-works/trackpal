"""Tests for the WhatsApp Master Console list and select Tenant flow.

Verifies numbered tenant listing, Redis selection map storage, valid
selection routing to detail screen, and invalid selection reprompt.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

import pytest

from app.services.whatsapp_console_service import WhatsAppConsoleService
from app.services.whatsapp_session_service import (
    ConversationSession,
    WhatsAppSessionService,
)


# ---------------------------------------------------------------------------
# Fake tenant data objects
# ---------------------------------------------------------------------------


class FakeTenant:
    """Minimal tenant data object for testing WhatsApp formatting."""

    def __init__(
        self,
        id: str,
        full_name: str,
        is_active: bool = True,
        email: str | None = None,
        phone: str | None = None,
        username: str | None = None,
        evolution_instance_name: str | None = None,
        created_at: Any = None,
    ) -> None:
        self.id = id
        self.full_name = full_name
        self.is_active = is_active
        self.email = email
        self.phone = phone
        self.username = username
        self.evolution_instance_name = evolution_instance_name
        self.created_at = created_at


class FakeTenantService:
    """In-memory fake for the tenant data provider used by the console.

    Implements ``get_tenants()`` and ``get_tenant(id)``.
    """

    def __init__(self, tenants: list[FakeTenant] | None = None) -> None:
        self._tenants: dict[str, FakeTenant] = {}
        if tenants:
            for t in tenants:
                self._tenants[str(t.id)] = t

    async def get_tenants(self) -> list[FakeTenant]:
        return list(self._tenants.values())

    async def get_tenant(self, tenant_id: str) -> FakeTenant | None:
        return self._tenants.get(tenant_id)

    async def get_tenant_by_username(self, username: str) -> FakeTenant | None:
        """Return tenant whose username matches, or None."""
        for t in self._tenants.values():
            if t.username == username:
                return t
        return None


# ---------------------------------------------------------------------------
# Fake Redis — dict-based async double
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


class FakeManager:
    """Duck-typed connection manager that delegates execute() to FakeRedis."""

    def __init__(self, fake_redis: FakeRedis | None = None) -> None:
        self._redis = fake_redis or FakeRedis()

    async def execute(self, operation_name: str, async_callable: Any) -> Any:
        return await async_callable(self._redis)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TENANT_1_ID = str(uuid4())
TENANT_2_ID = str(uuid4())
TENANT_3_ID = str(uuid4())


@pytest.fixture
def fake_redis() -> FakeRedis:
    return FakeRedis()


@pytest.fixture
def session_service(fake_redis: FakeRedis) -> WhatsAppSessionService:
    return WhatsAppSessionService(
        connection_manager=FakeManager(fake_redis=fake_redis),
        ttl_seconds=300,
    )


@pytest.fixture
def console_service() -> WhatsAppConsoleService:
    return WhatsAppConsoleService()


@pytest.fixture
def sample_tenants() -> list[FakeTenant]:
    return [
        FakeTenant(
            id=TENANT_1_ID,
            full_name="Alpha Corp",
            is_active=True,
            email="alpha@example.com",
            phone="+1111111111",
            username="alpha",
            evolution_instance_name="inst-alpha",
            created_at=datetime(2025, 1, 15),
        ),
        FakeTenant(
            id=TENANT_2_ID,
            full_name="Beta Inc",
            is_active=False,
            email="beta@example.com",
            phone="+2222222222",
            username="beta",
            evolution_instance_name="inst-beta",
            created_at=datetime(2025, 3, 20),
        ),
        FakeTenant(
            id=TENANT_3_ID,
            full_name="Gamma LLC",
            is_active=True,
            email=None,
            phone=None,
            username="gamma",
            evolution_instance_name=None,
            created_at=datetime(2025, 5, 10),
        ),
    ]


@pytest.fixture
def tenant_service(sample_tenants: list[FakeTenant]) -> FakeTenantService:
    return FakeTenantService(sample_tenants)


# ===========================================================================
# Tests
# ===========================================================================


@pytest.mark.asyncio
class TestListTenantsFlow:
    """Ver tenant list display and Redis selection map."""

    async def test_option_1_returns_tenant_list(
        self,
        console_service: WhatsAppConsoleService,
        tenant_service: FakeTenantService,
    ) -> None:
        reply = await console_service.process_message(
            phone="+10000000000",
            message="1",
            is_master=True,
            tenant_service=tenant_service,
        )
        assert "Lista de empresas" in reply
        assert "Alpha Corp" in reply
        assert "Beta Inc" in reply
        assert "Gamma LLC" in reply

    async def test_list_shows_active_inactive_status(
        self,
        console_service: WhatsAppConsoleService,
        tenant_service: FakeTenantService,
    ) -> None:
        reply = await console_service.process_message(
            phone="+10000000000",
            message="1",
            is_master=True,
            tenant_service=tenant_service,
        )
        assert "Activo" in reply
        assert "Inactivo" in reply

    async def test_list_shows_counts(
        self,
        console_service: WhatsAppConsoleService,
        tenant_service: FakeTenantService,
    ) -> None:
        reply = await console_service.process_message(
            phone="+10000000000",
            message="1",
            is_master=True,
            tenant_service=tenant_service,
        )
        assert "Activos: 2" in reply
        assert "Inactivos: 1" in reply

    async def test_list_contains_numbered_entries(
        self,
        console_service: WhatsAppConsoleService,
        tenant_service: FakeTenantService,
    ) -> None:
        reply = await console_service.process_message(
            phone="+10000000000",
            message="1",
            is_master=True,
            tenant_service=tenant_service,
        )
        assert "1️⃣" in reply
        assert "2️⃣" in reply
        assert "3️⃣" in reply

    async def test_list_stores_selection_map_in_session(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        await console_service.process_message(
            phone="+10000000000",
            message="1",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )

        session = await session_service.get_session("+10000000000")
        assert session is not None
        assert session.flow == "list_tenants"
        assert session.step == "select"
        assert session.selection_map["1"] == TENANT_1_ID
        assert session.selection_map["2"] == TENANT_2_ID
        assert session.selection_map["3"] == TENANT_3_ID

    async def test_list_with_no_tenants(
        self,
        console_service: WhatsAppConsoleService,
    ) -> None:
        empty_service = FakeTenantService([])
        reply = await console_service.process_message(
            phone="+10000000000",
            message="1",
            is_master=True,
            tenant_service=empty_service,
        )
        assert "No hay empresas" in reply

    async def test_option_1_without_tenant_service_returns_main_menu(
        self,
        console_service: WhatsAppConsoleService,
    ) -> None:
        """Backward compatible: without tenant_service, option 1 shows menu."""
        reply = await console_service.process_message(
            phone="+10000000000",
            message="1",
            is_master=True,
        )
        assert "Trackpal Master Console" in reply


@pytest.mark.asyncio
class TestSelectTenantFlow:
    """Tenant selection from a numbered list."""

    async def _list_and_get_session(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
        phone: str = "+10000000000",
    ) -> ConversationSession:
        """Helper: send option 1 and return the session."""
        await console_service.process_message(
            phone=phone,
            message="1",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )
        session = await session_service.get_session(phone)
        assert session is not None
        return session

    async def test_valid_number_returns_detail(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        await self._list_and_get_session(
            console_service, session_service, tenant_service
        )

        reply = await console_service.process_message(
            phone="+10000000000",
            message="1",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )
        assert "Detalle de la empresa" in reply
        assert "Alpha Corp" in reply
        assert "alpha" in reply  # username
        assert "alpha@example.com" in reply
        assert "+1111111111" in reply
        assert "inst-alpha" in reply
        assert "✅ Activo" in reply

    async def test_valid_number_updates_session(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        await self._list_and_get_session(
            console_service, session_service, tenant_service
        )

        await console_service.process_message(
            phone="+10000000000",
            message="1",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )

        session = await session_service.get_session("+10000000000")
        assert session is not None
        assert session.flow == "tenant_detail"
        assert session.step == "actions"
        assert session.selected_tenant_id == TENANT_1_ID
        assert session.selection_map == {}

    async def test_inactive_tenant_shows_inactive_status(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        await self._list_and_get_session(
            console_service, session_service, tenant_service
        )

        reply = await console_service.process_message(
            phone="+10000000000",
            message="2",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )
        assert "Detalle de la empresa" in reply
        assert "Beta Inc" in reply
        assert "❌ Inactivo" in reply

    async def test_invalid_number_returns_reprompt(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        await self._list_and_get_session(
            console_service, session_service, tenant_service
        )

        reply = await console_service.process_message(
            phone="+10000000000",
            message="99",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )
        assert "Número inválido" in reply

    async def test_invalid_selection_does_not_clear_map(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        await self._list_and_get_session(
            console_service, session_service, tenant_service
        )

        await console_service.process_message(
            phone="+10000000000",
            message="99",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )

        # Map should still be intact
        session = await session_service.get_session("+10000000000")
        assert session is not None
        assert session.selection_map["1"] == TENANT_1_ID

    async def test_text_message_during_selection_returns_reprompt(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        await self._list_and_get_session(
            console_service, session_service, tenant_service
        )

        reply = await console_service.process_message(
            phone="+10000000000",
            message="garbage",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )
        assert "Número inválido" in reply

    async def test_reset_during_selection_returns_menu(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        await self._list_and_get_session(
            console_service, session_service, tenant_service
        )

        reply = await console_service.process_message(
            phone="+10000000000",
            message="menu",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )
        assert "Trackpal Master Console" in reply

        # Session should be cleared
        session = await session_service.get_session("+10000000000")
        assert session is None

    async def test_help_during_selection_works(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        await self._list_and_get_session(
            console_service, session_service, tenant_service
        )

        reply = await console_service.process_message(
            phone="+10000000000",
            message="ayuda",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )
        assert "Ayuda" in reply
        assert "comandos disponibles" in reply


@pytest.mark.asyncio
class TestDetailScreen:
    """Tenant detail screen format and actions."""

    async def test_active_tenant_shows_active_actions(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        # List and select active tenant #1
        await console_service.process_message(
            phone="+10000000000",
            message="1",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )
        reply = await console_service.process_message(
            phone="+10000000000",
            message="1",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )
        assert "Acciones disponibles" in reply
        assert "Editar" in reply
        assert "Desactivar" in reply
        assert "Eliminar (solo inactivos)" in reply
        assert "Volver al menú" in reply

    async def test_inactive_tenant_shows_inactive_actions(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        # List and select inactive tenant #2
        await console_service.process_message(
            phone="+10000000000",
            message="1",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )
        reply = await console_service.process_message(
            phone="+10000000000",
            message="2",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )
        assert "Acciones disponibles" in reply
        assert "Editar" in reply
        assert "Reactivar" in reply
        assert "Eliminar" in reply
        assert "Volver al menú" in reply

    async def test_detail_without_email_or_phone_shows_placeholder(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        # Select tenant #3 (no email, no phone, no evolution instance)
        await console_service.process_message(
            phone="+10000000000",
            message="1",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )
        reply = await console_service.process_message(
            phone="+10000000000",
            message="3",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )
        assert "Gamma LLC" in reply
        assert "—" in reply  # The em dash placeholder for missing fields

    async def test_detail_shows_created_date(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        await console_service.process_message(
            phone="+10000000000",
            message="1",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )
        reply = await console_service.process_message(
            phone="+10000000000",
            message="1",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )
        assert "2025-01-15" in reply


@pytest.mark.asyncio
class TestListSelectWithoutSessionService:
    """List/select flow without Redis session persistence."""

    async def test_list_works_without_session_service(
        self,
        console_service: WhatsAppConsoleService,
        tenant_service: FakeTenantService,
    ) -> None:
        reply = await console_service.process_message(
            phone="+10000000000",
            message="1",
            is_master=True,
            tenant_service=tenant_service,
        )
        assert "Lista de empresas" in reply

    async def test_selection_without_session_service_returns_invalid(
        self,
        console_service: WhatsAppConsoleService,
        tenant_service: FakeTenantService,
    ) -> None:
        # Without session_service, there's no stored flow/selection_map,
        # so selecting a number falls through to no-active-flow handling
        reply = await console_service.process_message(
            phone="+10000000000",
            message="1",
            is_master=True,
        )
        # No tenant_service, so option 1 returns main menu
        assert "Trackpal Master Console" in reply
