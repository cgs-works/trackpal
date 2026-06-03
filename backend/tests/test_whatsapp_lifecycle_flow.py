"""Tests for the WhatsApp Master Console Tenant lifecycle flows.

Verifies deactivation, reactivation, deletion with CONFIRMAR, blocked
deletion of active tenants, invalid confirmation text, and cancellation
behaviour.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

import pytest

from app.services.whatsapp_console_service import WhatsAppConsoleService
from app.services.whatsapp_session_service import WhatsAppSessionService


# ---------------------------------------------------------------------------
# Fake tenant data object
# ---------------------------------------------------------------------------


class FakeTenant:
    """Minimal tenant data object for testing lifecycle actions."""

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

    def __repr__(self) -> str:
        return f"<FakeTenant {self.full_name} (active={self.is_active})>"


# ---------------------------------------------------------------------------
# Fake tenant service with lifecycle support
# ---------------------------------------------------------------------------


class FakeTenantService:
    """In-memory fake for the tenant data provider.

    Implements ``get_tenants()``, ``get_tenant(id)``, ``deactivate_tenant()``,
    ``activate_tenant()``, and ``delete_tenant()``.
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

    async def deactivate_tenant(self, tenant_id: str) -> dict:
        """Simulate ``TenantService.deactivate_tenant``."""
        tenant = self._tenants.get(tenant_id)
        if tenant is None:
            return {"success": False, "error": "Tenant not found"}
        tenant.is_active = False
        return {"success": True, "tenant": tenant}

    async def activate_tenant(self, tenant_id: str) -> dict:
        """Simulate ``TenantService.activate_tenant``."""
        tenant = self._tenants.get(tenant_id)
        if tenant is None:
            return {"success": False, "error": "Tenant not found"}
        tenant.is_active = True
        return {"success": True, "tenant": tenant}

    async def delete_tenant(self, tenant_id: str) -> dict:
        """Simulate ``TenantService.delete_tenant``.

        Raises error if tenant is active.
        """
        tenant = self._tenants.get(tenant_id)
        if tenant is None:
            return {"success": False, "error": "Tenant not found"}
        if tenant.is_active:
            return {
                "success": False,
                "error": "Cannot delete active tenant. Deactivate first.",
            }
        del self._tenants[tenant_id]
        return {"success": True}


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

TENANT_ACTIVE_ID = str(uuid4())
TENANT_INACTIVE_ID = str(uuid4())


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
            id=TENANT_ACTIVE_ID,
            full_name="Alpha Corp",
            is_active=True,
            email="alpha@example.com",
            phone="+1111111111",
            username="alpha",
            evolution_instance_name="inst-alpha",
            created_at=datetime(2025, 1, 15),
        ),
        FakeTenant(
            id=TENANT_INACTIVE_ID,
            full_name="Beta Inc",
            is_active=False,
            email="beta@example.com",
            phone="+2222222222",
            username="beta",
            evolution_instance_name="inst-beta",
            created_at=datetime(2025, 3, 20),
        ),
    ]


@pytest.fixture
def tenant_service(sample_tenants: list[FakeTenant]) -> FakeTenantService:
    return FakeTenantService(sample_tenants)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _select_tenant(
    console_service: WhatsAppConsoleService,
    session_service: WhatsAppSessionService,
    tenant_service: FakeTenantService,
    phone: str = "+10000000000",
    selection: str = "1",
) -> str:
    """Helper: list tenants, then select one, returning the detail reply."""
    await console_service.process_message(
        phone=phone,
        message="1",
        is_master=True,
        session_service=session_service,
        tenant_service=tenant_service,
    )
    reply = await console_service.process_message(
        phone=phone,
        message=selection,
        is_master=True,
        session_service=session_service,
        tenant_service=tenant_service,
    )
    return reply


# ===========================================================================
# Tests — Deactivation flow
# ===========================================================================


@pytest.mark.asyncio
class TestDeactivateFlow:
    """Deactivation from detail screen requires CONFIRMAR."""

    async def test_option_2_from_active_detail_shows_confirm_prompt(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        """Pressing 2 on an active tenant shows the deactivation confirmation."""
        await _select_tenant(
            console_service, session_service, tenant_service, selection="1"
        )

        reply = await console_service.process_message(
            phone="+10000000000",
            message="2",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )
        assert "Desactivar Tenant" in reply or "desactivar" in reply.lower()
        assert "CONFIRMAR" in reply or "confirmar" in reply.lower()
        assert "Alpha Corp" in reply

    async def test_confirmar_deactivates_tenant(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        """Sending CONFIRMAR after deactivation prompt deactivates the tenant."""
        await _select_tenant(
            console_service, session_service, tenant_service, selection="1"
        )
        await console_service.process_message(
            phone="+10000000000",
            message="2",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )

        reply = await console_service.process_message(
            phone="+10000000000",
            message="CONFIRMAR",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )
        assert "Desactivado" in reply or "desactivado" in reply.lower()
        assert "Alpha Corp" in reply

        # Tenant should actually be deactivated
        tenant = await tenant_service.get_tenant(TENANT_ACTIVE_ID)
        assert tenant is not None
        assert tenant.is_active is False

    async def test_confirmar_case_insensitive(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        """CONFIRMAR is case-insensitive."""
        await _select_tenant(
            console_service, session_service, tenant_service, selection="1"
        )
        await console_service.process_message(
            phone="+10000000000",
            message="2",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )

        reply = await console_service.process_message(
            phone="+10000000000",
            message="confirmar",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )
        assert "Desactivado" in reply or "desactivado" in reply.lower()

        tenant = await tenant_service.get_tenant(TENANT_ACTIVE_ID)
        assert tenant is not None
        assert tenant.is_active is False

    async def test_invalid_confirmation_text_reprompts(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        """Non-CONFIRMAR text during deactivation confirm shows reprompt."""
        await _select_tenant(
            console_service, session_service, tenant_service, selection="1"
        )
        await console_service.process_message(
            phone="+10000000000",
            message="2",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )

        reply = await console_service.process_message(
            phone="+10000000000",
            message="no",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )
        assert "CONFIRMAR" in reply or "confirmar" in reply.lower()

        # Tenant should still be active
        tenant = await tenant_service.get_tenant(TENANT_ACTIVE_ID)
        assert tenant is not None
        assert tenant.is_active is True

    async def test_cancel_during_deactivation_confirm(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        """Cancel during deactivation confirm clears session."""
        await _select_tenant(
            console_service, session_service, tenant_service, selection="1"
        )
        await console_service.process_message(
            phone="+10000000000",
            message="2",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )

        reply = await console_service.process_message(
            phone="+10000000000",
            message="cancelar",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )
        assert "Trackpal Master Console" in reply
        assert "cancelada" in reply.lower() or "cancelado" in reply.lower()

        session = await session_service.get_session("+10000000000")
        assert session is None

    async def test_reset_during_deactivation_confirm(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        """Reset command during deactivation confirm clears session."""
        await _select_tenant(
            console_service, session_service, tenant_service, selection="1"
        )
        await console_service.process_message(
            phone="+10000000000",
            message="2",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )

        reply = await console_service.process_message(
            phone="+10000000000",
            message="menu",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )
        assert "Trackpal Master Console" in reply
        assert "cancelada" in reply.lower() or "cancelado" in reply.lower()

        session = await session_service.get_session("+10000000000")
        assert session is None

    async def test_session_cleared_after_successful_deactivation(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        """Session is cleared after successful deactivation."""
        await _select_tenant(
            console_service, session_service, tenant_service, selection="1"
        )
        await console_service.process_message(
            phone="+10000000000",
            message="2",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )
        await console_service.process_message(
            phone="+10000000000",
            message="CONFIRMAR",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )

        session = await session_service.get_session("+10000000000")
        assert session is None


# ===========================================================================
# Tests — Reactivation flow
# ===========================================================================


@pytest.mark.asyncio
class TestReactivateFlow:
    """Reactivation from detail screen is immediate (no CONFIRMAR)."""

    async def test_option_2_reactivates_inactive_tenant(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        """Pressing 2 on an inactive tenant immediately reactivates."""
        await _select_tenant(
            console_service, session_service, tenant_service, selection="2"
        )

        reply = await console_service.process_message(
            phone="+10000000000",
            message="2",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )
        assert "Reactivado" in reply or "reactivado" in reply.lower()
        assert "Beta Inc" in reply

        # Tenant should be active
        tenant = await tenant_service.get_tenant(TENANT_INACTIVE_ID)
        assert tenant is not None
        assert tenant.is_active is True

    async def test_reactivation_does_not_require_confirmar(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        """Reactivation is immediate without CONFIRMAR."""
        await _select_tenant(
            console_service, session_service, tenant_service, selection="2"
        )

        reply = await console_service.process_message(
            phone="+10000000000",
            message="2",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )
        # Should NOT contain a CONFIRMAR prompt
        assert "CONFIRMAR" not in reply
        assert "Reactivado" in reply or "reactivado" in reply.lower()

    async def test_session_cleared_after_reactivation(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        """Session is cleared after successful reactivation."""
        await _select_tenant(
            console_service, session_service, tenant_service, selection="2"
        )
        await console_service.process_message(
            phone="+10000000000",
            message="2",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )

        session = await session_service.get_session("+10000000000")
        assert session is None


# ===========================================================================
# Tests — Delete flow
# ===========================================================================


@pytest.mark.asyncio
class TestDeleteFlow:
    """Deletion from detail screen requires inactive tenant and CONFIRMAR."""

    async def test_delete_active_tenant_is_blocked(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        """Pressing 3 on an active tenant shows a blocked message."""
        await _select_tenant(
            console_service, session_service, tenant_service, selection="1"
        )

        reply = await console_service.process_message(
            phone="+10000000000",
            message="3",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )
        assert "no se puede eliminar" in reply.lower()
        assert "activo" in reply.lower()
        assert "desactiva" in reply.lower()

    async def test_delete_active_tenant_does_not_change_status(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        """Blocked deletion does not modify the tenant."""
        await _select_tenant(
            console_service, session_service, tenant_service, selection="1"
        )
        await console_service.process_message(
            phone="+10000000000",
            message="3",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )

        tenant = await tenant_service.get_tenant(TENANT_ACTIVE_ID)
        assert tenant is not None
        assert tenant.is_active is True

    async def test_delete_inactive_shows_confirm_prompt(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        """Pressing 3 on an inactive tenant shows the deletion confirmation."""
        await _select_tenant(
            console_service, session_service, tenant_service, selection="2"
        )

        reply = await console_service.process_message(
            phone="+10000000000",
            message="3",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )
        assert "Eliminar Tenant" in reply or "eliminar" in reply.lower()
        assert "CONFIRMAR" in reply or "confirmar" in reply.lower()
        assert "Beta Inc" in reply

    async def test_confirmar_deletes_inactive_tenant(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        """Sending CONFIRMAR after delete prompt deletes the tenant."""
        await _select_tenant(
            console_service, session_service, tenant_service, selection="2"
        )
        await console_service.process_message(
            phone="+10000000000",
            message="3",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )

        reply = await console_service.process_message(
            phone="+10000000000",
            message="CONFIRMAR",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )
        assert "Eliminado" in reply or "eliminado" in reply.lower()
        assert "Beta Inc" in reply

        # Tenant should be deleted
        tenant = await tenant_service.get_tenant(TENANT_INACTIVE_ID)
        assert tenant is None

    async def test_invalid_confirmation_text_during_delete_reprompts(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        """Non-CONFIRMAR text during delete confirm shows reprompt."""
        await _select_tenant(
            console_service, session_service, tenant_service, selection="2"
        )
        await console_service.process_message(
            phone="+10000000000",
            message="3",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )

        reply = await console_service.process_message(
            phone="+10000000000",
            message="no",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )
        assert "CONFIRMAR" in reply or "confirmar" in reply.lower()

        # Tenant should still exist
        tenant = await tenant_service.get_tenant(TENANT_INACTIVE_ID)
        assert tenant is not None

    async def test_cancel_during_delete_confirm(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        """Cancel during delete confirm clears session."""
        await _select_tenant(
            console_service, session_service, tenant_service, selection="2"
        )
        await console_service.process_message(
            phone="+10000000000",
            message="3",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )

        reply = await console_service.process_message(
            phone="+10000000000",
            message="cancelar",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )
        assert "Trackpal Master Console" in reply

        session = await session_service.get_session("+10000000000")
        assert session is None

    async def test_reset_during_delete_confirm(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        """Reset command during delete confirm clears session."""
        await _select_tenant(
            console_service, session_service, tenant_service, selection="2"
        )
        await console_service.process_message(
            phone="+10000000000",
            message="3",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )

        reply = await console_service.process_message(
            phone="+10000000000",
            message="menu",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )
        assert "Trackpal Master Console" in reply

        session = await session_service.get_session("+10000000000")
        assert session is None

    async def test_session_cleared_after_successful_delete(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        """Session is cleared after successful deletion."""
        await _select_tenant(
            console_service, session_service, tenant_service, selection="2"
        )
        await console_service.process_message(
            phone="+10000000000",
            message="3",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )
        await console_service.process_message(
            phone="+10000000000",
            message="CONFIRMAR",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )

        session = await session_service.get_session("+10000000000")
        assert session is None


# ===========================================================================
# Tests — Main menu options 3 and 4
# ===========================================================================


@pytest.mark.asyncio
class TestMainMenuLifecycleShortcuts:
    """Main menu options 3 and 4 list tenants (same as option 1)."""

    async def test_option_3_lists_tenants(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        """Option 3 from main menu lists tenants."""
        reply = await console_service.process_message(
            phone="+10000000000",
            message="3",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )
        assert "Lista de Tenants" in reply
        assert "Alpha Corp" in reply
        assert "Beta Inc" in reply

    async def test_option_4_lists_tenants(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        """Option 4 from main menu lists tenants."""
        reply = await console_service.process_message(
            phone="+10000000000",
            message="4",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )
        assert "Lista de Tenants" in reply
        assert "Alpha Corp" in reply
        assert "Beta Inc" in reply

    async def test_option_3_without_tenant_service_returns_menu(
        self,
        console_service: WhatsAppConsoleService,
    ) -> None:
        """Without tenant_service, option 3 shows main menu."""
        reply = await console_service.process_message(
            phone="+10000000000",
            message="3",
            is_master=True,
        )
        assert "Trackpal Master Console" in reply

    async def test_option_4_without_tenant_service_returns_menu(
        self,
        console_service: WhatsAppConsoleService,
    ) -> None:
        """Without tenant_service, option 4 shows main menu."""
        reply = await console_service.process_message(
            phone="+10000000000",
            message="4",
            is_master=True,
        )
        assert "Trackpal Master Console" in reply


# ===========================================================================
# Tests — End-to-end lifecycle scenarios
# ===========================================================================


@pytest.mark.asyncio
class TestFullLifecycleScenario:
    """End-to-end lifecycle: deactivate then reactivate then delete."""

    async def test_deactivate_then_reactivate(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        """Deactivate an active tenant, then reactivate it."""
        # Select active tenant (Alpha Corp)
        await _select_tenant(
            console_service, session_service, tenant_service, selection="1"
        )

        # Deactivate
        await console_service.process_message(
            phone="+10000000000",
            message="2",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )
        await console_service.process_message(
            phone="+10000000000",
            message="CONFIRMAR",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )

        # Verify deactivated
        tenant = await tenant_service.get_tenant(TENANT_ACTIVE_ID)
        assert tenant is not None
        assert tenant.is_active is False

        # List again and select the now-inactive tenant
        await _select_tenant(
            console_service, session_service, tenant_service, selection="1"
        )

        # Reactivate (option 2 for inactive)
        reply = await console_service.process_message(
            phone="+10000000000",
            message="2",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )
        assert "Reactivado" in reply or "reactivado" in reply.lower()

        # Verify reactivated
        tenant = await tenant_service.get_tenant(TENANT_ACTIVE_ID)
        assert tenant is not None
        assert tenant.is_active is True

    async def test_deactivate_then_delete(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        """Deactivate an active tenant, then delete it."""
        # Select active tenant (Alpha Corp)
        await _select_tenant(
            console_service, session_service, tenant_service, selection="1"
        )

        # Deactivate
        await console_service.process_message(
            phone="+10000000000",
            message="2",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )
        await console_service.process_message(
            phone="+10000000000",
            message="CONFIRMAR",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )

        # List again and select the now-inactive tenant
        await _select_tenant(
            console_service, session_service, tenant_service, selection="1"
        )

        # Delete (option 3 for inactive)
        await console_service.process_message(
            phone="+10000000000",
            message="3",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )
        reply = await console_service.process_message(
            phone="+10000000000",
            message="CONFIRMAR",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )
        assert "Eliminado" in reply or "eliminado" in reply.lower()

        # Verify deleted
        tenant = await tenant_service.get_tenant(TENANT_ACTIVE_ID)
        assert tenant is None


# ===========================================================================
# Tests — Detail screen unknown actions
# ===========================================================================


@pytest.mark.asyncio
class TestDetailScreenUnknownActions:
    """Unrecognised options from detail screen."""

    async def test_unknown_option_returns_fallback(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        """Unrecognised option from detail screen shows fallback."""
        await _select_tenant(
            console_service, session_service, tenant_service, selection="1"
        )

        reply = await console_service.process_message(
            phone="+10000000000",
            message="99",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )
        assert (
            "inválida" in reply.lower()
            or "inválido" in reply.lower()
            or "No entendí" in reply
        )
