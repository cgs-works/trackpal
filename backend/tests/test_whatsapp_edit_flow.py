"""Tests for the WhatsApp Master Console edit Tenant flow.

Verifies the Master can edit full name, email, phone, and Evolution
Instance from the Tenant detail screen. Covers valid updates, invalid
input, duplicate phone detection, and cancel/reset from edit steps.
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
# Fake tenant data object
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

    def __repr__(self) -> str:
        return f"<FakeTenant {self.full_name} (active={self.is_active})>"


# ---------------------------------------------------------------------------
# Fake tenant service with update support
# ---------------------------------------------------------------------------

class FakeTenantService:
    """In-memory fake for the tenant data provider used by the console.

    Implements ``get_tenants()``, ``get_tenant(id)``, and ``update_tenant()``.
    """

    def __init__(self, tenants: list[FakeTenant] | None = None) -> None:
        self._tenants: dict[str, FakeTenant] = {}
        self._phones_in_use: set[str] = set()
        if tenants:
            for t in tenants:
                self._tenants[str(t.id)] = t
                if t.phone:
                    # Store canonical digits-only for duplicate tracking
                    import re
                    canonical = re.sub(r"\D", "", t.phone)
                    self._phones_in_use.add(canonical)

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

    async def update_tenant(self, tenant_id: str, payload: dict) -> dict:
        """Simulate ``TenantService.update_tenant``.

        Returns:
            Success dict:  ``{'success': True, 'tenant': FakeTenant}``
            Error dict:    ``{'success': False, 'error': '...'}``
        """
        tenant = self._tenants.get(tenant_id)
        if tenant is None:
            return {"success": False, "error": "Tenant not found"}

        # Validate phone uniqueness (canonical digits-only for matching)
        if "phone" in payload and payload["phone"] is not None:
            import re
            new_phone = re.sub(r"\D", "", payload["phone"])
            old_phone_canonical = re.sub(r"\D", "", tenant.phone or "")
            if new_phone != old_phone_canonical and new_phone in self._phones_in_use:
                return {"success": False, "error": "Phone already registered"}

        # Apply updates (excluding None values)
        for field, value in payload.items():
            if value is not None:
                setattr(tenant, field, value)

        # Track phone changes
        if "phone" in payload:
            old_phone = tenant.phone
            new_phone = payload["phone"]
            if old_phone in self._phones_in_use:
                self._phones_in_use.discard(old_phone)
            if new_phone:
                self._phones_in_use.add(new_phone)

        return {"success": True, "tenant": tenant}


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


@pytest.fixture
def sample_tenants() -> list[FakeTenant]:
    return [
        FakeTenant(
            id=TENANT_1_ID,
            full_name="Alpha Corp",
            is_active=True,
            email="alpha@example.com",
            phone="525512345678",
            username="alpha",
            evolution_instance_name="inst-alpha",
            created_at=datetime(2025, 1, 15),
        ),
        FakeTenant(
            id=TENANT_2_ID,
            full_name="Beta Inc",
            is_active=True,
            email="beta@example.com",
            phone="525598765432",
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
    # List tenants
    await console_service.process_message(
        phone=phone,
        message="1",
        is_master=True,
        session_service=session_service,
        tenant_service=tenant_service,
    )
    # Select tenant by number
    reply = await console_service.process_message(
        phone=phone,
        message=selection,
        is_master=True,
        session_service=session_service,
        tenant_service=tenant_service,
    )
    return reply


# ===========================================================================
# Tests
# ===========================================================================

@pytest.mark.asyncio
class TestEditFlowStart:
    """Detail screen action '1' starts the edit flow."""

    async def test_option_1_from_detail_starts_edit(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        await _select_tenant(console_service, session_service, tenant_service)

        reply = await console_service.process_message(
            phone="+10000000000",
            message="1",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )

        # Should show edit field selection menu
        assert "Editar Tenant" in reply or "editar" in reply.lower()
        assert "campo" in reply.lower() or "editar" in reply.lower()
        # Should list editable fields
        assert "nombre completo" in reply.lower()
        assert "email" in reply.lower()
        assert "teléfono" in reply.lower() or "telefono" in reply.lower()
        assert "evolution" in reply.lower() or "instancia" in reply.lower()

    async def test_option_1_sets_edit_session(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        await _select_tenant(console_service, session_service, tenant_service)

        await console_service.process_message(
            phone="+10000000000",
            message="1",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )

        session = await session_service.get_session("+10000000000")
        assert session is not None
        assert session.flow == "edit_tenant"
        assert session.step == "select_field"
        assert session.selected_tenant_id == TENANT_1_ID

    async def test_unrecognised_option_from_detail_returns_fallback(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        await _select_tenant(console_service, session_service, tenant_service)

        reply = await console_service.process_message(
            phone="+10000000000",
            message="garbage",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )

        assert "No entendí" in reply or "inválida" in reply.lower() or "inválido" in reply.lower()

    async def test_option_0_from_detail_returns_menu(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        await _select_tenant(console_service, session_service, tenant_service)

        reply = await console_service.process_message(
            phone="+10000000000",
            message="0",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )

        assert "Trackpal Master Console" in reply


@pytest.mark.asyncio
class TestEditFieldSelection:
    """Selecting which field to edit."""

    async def _start_edit(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        """Helper: navigate to edit field selection."""
        await _select_tenant(console_service, session_service, tenant_service)
        await console_service.process_message(
            phone="+10000000000",
            message="1",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )

    async def test_select_full_name_prompts_for_new_value(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        await self._start_edit(console_service, session_service, tenant_service)

        reply = await console_service.process_message(
            phone="+10000000000",
            message="1",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )

        assert "nuevo nombre completo" in reply.lower() or "nuevo nombre" in reply.lower()

        session = await session_service.get_session("+10000000000")
        assert session is not None
        assert session.flow == "edit_tenant"
        assert session.step == "new_value"
        assert session.temp_data.get("edit_field") == "full_name"

    async def test_select_email_prompts_for_new_value(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        await self._start_edit(console_service, session_service, tenant_service)

        reply = await console_service.process_message(
            phone="+10000000000",
            message="2",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )

        assert "nuevo email" in reply.lower() or "nuevo correo" in reply.lower()

        session = await session_service.get_session("+10000000000")
        assert session is not None
        assert session.step == "new_value"
        assert session.temp_data.get("edit_field") == "email"

    async def test_select_phone_prompts_for_new_value(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        await self._start_edit(console_service, session_service, tenant_service)

        reply = await console_service.process_message(
            phone="+10000000000",
            message="3",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )

        assert "nuevo teléfono" in reply.lower() or "nuevo telefono" in reply.lower()

        session = await session_service.get_session("+10000000000")
        assert session is not None
        assert session.step == "new_value"
        assert session.temp_data.get("edit_field") == "phone"

    async def test_select_evolution_instance_prompts_for_new_value(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        await self._start_edit(console_service, session_service, tenant_service)

        reply = await console_service.process_message(
            phone="+10000000000",
            message="4",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )

        assert "instancia evolution" in reply.lower() or "evolution" in reply.lower()

        session = await session_service.get_session("+10000000000")
        assert session is not None
        assert session.step == "new_value"
        assert session.temp_data.get("edit_field") == "evolution_instance_name"

    async def test_invalid_field_selection_reprompts(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        await self._start_edit(console_service, session_service, tenant_service)

        reply = await console_service.process_message(
            phone="+10000000000",
            message="99",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )

        # Should show error and reprompt for field selection
        assert "inválido" in reply.lower() or "opción" in reply.lower()

        session = await session_service.get_session("+10000000000")
        assert session is not None
        assert session.step == "select_field"  # Not advanced

    async def test_cancel_from_field_selection(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        await self._start_edit(console_service, session_service, tenant_service)

        reply = await console_service.process_message(
            phone="+10000000000",
            message="0",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )

        assert "Trackpal Master Console" in reply

    async def test_reset_from_field_selection(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        await self._start_edit(console_service, session_service, tenant_service)

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


@pytest.mark.asyncio
class TestEditNewValue:
    """Providing a new value for the selected field."""

    async def _select_field(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
        field_num: str = "1",
    ) -> None:
        """Helper: navigate to edit new value prompt for a specific field."""
        await _select_tenant(console_service, session_service, tenant_service)
        await console_service.process_message(
            phone="+10000000000",
            message="1",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )
        await console_service.process_message(
            phone="+10000000000",
            message=field_num,
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )

    async def test_valid_full_name_update(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        await self._select_field(console_service, session_service, tenant_service, "1")

        reply = await console_service.process_message(
            phone="+10000000000",
            message="Alpha Corp Renamed",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )

        # Should return success message + main menu
        assert "Tenant actualizado exitosamente" in reply
        assert "Alpha Corp Renamed" in reply
        assert "Trackpal Master Console" in reply

        # Tenant should be updated in the fake service
        tenant = await tenant_service.get_tenant(TENANT_1_ID)
        assert tenant is not None
        assert tenant.full_name == "Alpha Corp Renamed"

        # Session should be cleared
        session = await session_service.get_session("+10000000000")
        assert session is None

    async def test_valid_email_update(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        await self._select_field(console_service, session_service, tenant_service, "2")

        reply = await console_service.process_message(
            phone="+10000000000",
            message="newalpha@example.com",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )

        assert "Tenant actualizado exitosamente" in reply
        assert "Alpha Corp" in reply
        assert "Trackpal Master Console" in reply

        tenant = await tenant_service.get_tenant(TENANT_1_ID)
        assert tenant is not None
        assert tenant.email == "newalpha@example.com"

        # Session should be cleared
        session = await session_service.get_session("+10000000000")
        assert session is None

    async def test_valid_phone_update(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        await self._select_field(console_service, session_service, tenant_service, "3")

        reply = await console_service.process_message(
            phone="+10000000000",
            message="+525500001111",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )

        assert "Tenant actualizado exitosamente" in reply
        assert "Alpha Corp" in reply
        assert "Trackpal Master Console" in reply

        tenant = await tenant_service.get_tenant(TENANT_1_ID)
        assert tenant is not None
        assert tenant.phone == "525500001111"

        # Session should be cleared
        session = await session_service.get_session("+10000000000")
        assert session is None

    async def test_valid_evolution_instance_update(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        await self._select_field(console_service, session_service, tenant_service, "4")

        reply = await console_service.process_message(
            phone="+10000000000",
            message="inst-alpha-renamed",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )

        assert "Tenant actualizado exitosamente" in reply
        assert "Alpha Corp" in reply
        assert "Trackpal Master Console" in reply

        tenant = await tenant_service.get_tenant(TENANT_1_ID)
        assert tenant is not None
        assert tenant.evolution_instance_name == "inst-alpha-renamed"

        # Session should be cleared
        session = await session_service.get_session("+10000000000")
        assert session is None

    async def test_update_shows_success_with_tenant_name(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        """After update, reply contains success message and main menu."""
        await self._select_field(console_service, session_service, tenant_service, "1")

        reply = await console_service.process_message(
            phone="+10000000000",
            message="New Name",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )

        assert "Tenant actualizado exitosamente" in reply
        assert "New Name" in reply
        assert "Trackpal Master Console" in reply

    async def test_empty_full_name_reprompts(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        await self._select_field(console_service, session_service, tenant_service, "1")

        reply = await console_service.process_message(
            phone="+10000000000",
            message="   ",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )

        # Should show error and reprompt
        assert "vacío" in reply.lower() or "nombre" in reply.lower()

        # Should stay in edit flow, same step
        session = await session_service.get_session("+10000000000")
        assert session is not None
        assert session.flow == "edit_tenant"
        assert session.step == "new_value"
        assert session.temp_data.get("edit_field") == "full_name"

        # Tenant should NOT be updated
        tenant = await tenant_service.get_tenant(TENANT_1_ID)
        assert tenant is not None
        assert tenant.full_name == "Alpha Corp"

    async def test_invalid_full_name_reprompts(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        """Invalid full name in edit is rejected with error message."""
        await self._select_field(console_service, session_service, tenant_service, "1")

        reply = await console_service.process_message(
            phone="+10000000000",
            message="Alpha Corp!",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )

        # Should show validation error and reprompt
        assert "letras" in reply.lower() or "solo" in reply.lower()
        assert "nombre" in reply.lower()

        # Should stay in edit flow, same step
        session = await session_service.get_session("+10000000000")
        assert session is not None
        assert session.flow == "edit_tenant"
        assert session.step == "new_value"
        assert session.temp_data.get("edit_field") == "full_name"
        # selected_tenant_id must be preserved
        assert session.selected_tenant_id == TENANT_1_ID

        # Tenant should NOT be updated
        tenant = await tenant_service.get_tenant(TENANT_1_ID)
        assert tenant is not None
        assert tenant.full_name == "Alpha Corp"

    async def test_invalid_email_reprompts(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        """Invalid email in edit is rejected, stays on step, preserves context."""
        await self._select_field(console_service, session_service, tenant_service, "2")

        reply = await console_service.process_message(
            phone="+10000000000",
            message="not-an-email",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )

        # Should show validation error
        assert "email" in reply.lower() or "correo" in reply.lower()

        session = await session_service.get_session("+10000000000")
        assert session is not None
        assert session.step == "new_value"
        assert session.temp_data.get("edit_field") == "email"
        # Preserve selected tenant context
        assert session.selected_tenant_id == TENANT_1_ID

    async def test_invalid_phone_reprompts(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        """Invalid phone in edit is rejected, stays on step, preserves context."""
        await self._select_field(console_service, session_service, tenant_service, "3")

        reply = await console_service.process_message(
            phone="+10000000000",
            message="abc",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )

        # Should show validation error
        assert "teléfono" in reply.lower() or "telefono" in reply.lower()

        session = await session_service.get_session("+10000000000")
        assert session is not None
        assert session.step == "new_value"
        assert session.temp_data.get("edit_field") == "phone"
        # Preserve selected tenant context
        assert session.selected_tenant_id == TENANT_1_ID

    async def test_edit_valid_email_normalized(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        """Valid email with mixed case is normalized in edit."""
        await self._select_field(console_service, session_service, tenant_service, "2")

        reply = await console_service.process_message(
            phone="+10000000000",
            message="NewAlpha@Example.COM",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )

        assert "Tenant actualizado exitosamente" in reply
        assert "Trackpal Master Console" in reply
        tenant = await tenant_service.get_tenant(TENANT_1_ID)
        assert tenant is not None
        # Email normalized (domain lowercase, local part preserved)
        assert tenant.email == "NewAlpha@example.com"

    async def test_edit_valid_phone_normalized(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        """Valid phone with + is stored digits-only in edit."""
        await self._select_field(console_service, session_service, tenant_service, "3")

        reply = await console_service.process_message(
            phone="+10000000000",
            message="+525500001111",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )

        assert "Tenant actualizado exitosamente" in reply
        assert "Trackpal Master Console" in reply
        tenant = await tenant_service.get_tenant(TENANT_1_ID)
        assert tenant is not None
        # Phone stored canonical digits-only (no + prefix)
        assert tenant.phone == "525500001111"

    async def test_duplicate_phone_reprompts(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        """Duplicate phone error keeps user in edit flow without losing context."""
        await self._select_field(console_service, session_service, tenant_service, "3")

        # Try to update to a phone already in use by Beta Inc
        reply = await console_service.process_message(
            phone="+10000000000",
            message="+525598765432",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )

        # Should show error about duplicate phone
        assert "registrado" in reply.lower() or "already" in reply.lower() or "duplicate" in reply.lower()

        # Should stay in edit flow
        session = await session_service.get_session("+10000000000")
        assert session is not None
        assert session.flow == "edit_tenant"
        assert session.step == "new_value"
        assert session.temp_data.get("edit_field") == "phone"

        # Tenant phone should NOT have changed
        tenant = await tenant_service.get_tenant(TENANT_1_ID)
        assert tenant is not None
        assert tenant.phone == "525512345678"

    async def test_duplicate_phone_then_valid(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        """After duplicate error, user can provide a valid phone."""
        await self._select_field(console_service, session_service, tenant_service, "3")

        # Send duplicate phone
        await console_service.process_message(
            phone="+10000000000",
            message="+525598765432",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )

        # Send valid phone
        reply = await console_service.process_message(
            phone="+10000000000",
            message="+525500001111",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )

        # Should show success with main menu
        assert "Tenant actualizado exitosamente" in reply
        assert "Trackpal Master Console" in reply

        tenant = await tenant_service.get_tenant(TENANT_1_ID)
        assert tenant is not None
        assert tenant.phone == "525500001111"

        # Session should be cleared
        session = await session_service.get_session("+10000000000")
        assert session is None

    async def test_cancel_during_new_value(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        await self._select_field(console_service, session_service, tenant_service, "1")

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

    async def test_reset_during_new_value(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        await self._select_field(console_service, session_service, tenant_service, "1")

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

    async def test_help_during_new_value(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        await self._select_field(console_service, session_service, tenant_service, "1")

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
class TestEditFlowWithoutSessionService:
    """Edit flow without Redis session persistence."""

    async def test_edit_without_session_service_does_not_crash(
        self,
        console_service: WhatsAppConsoleService,
        tenant_service: FakeTenantService,
    ) -> None:
        # List and select tenant without session service
        await console_service.process_message(
            phone="+10000000000",
            message="1",
            is_master=True,
            tenant_service=tenant_service,
        )
        # Without session service, there's no stored selection,
        # so sending "1" falls through to no-active-flow handling
        reply = await console_service.process_message(
            phone="+10000000000",
            message="1",
            is_master=True,
            tenant_service=tenant_service,
        )
        # Should not crash — it's just stateless fallback
        assert isinstance(reply, str)


@pytest.mark.asyncio
class TestEditFlowFullScenario:
    """End-to-end edit scenarios."""

    async def test_edit_full_name_then_email(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        """Edit two fields sequentially: full name then email."""
        await _select_tenant(console_service, session_service, tenant_service)

        # Edit full name
        await console_service.process_message(
            phone="+10000000000",
            message="1",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )
        await console_service.process_message(
            phone="+10000000000",
            message="1",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )
        reply = await console_service.process_message(
            phone="+10000000000",
            message="New Alpha Name",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )
        assert "Tenant actualizado exitosamente" in reply
        assert "New Alpha Name" in reply
        assert "Trackpal Master Console" in reply

        # Session cleared after first edit — re-navigate from main menu
        await console_service.process_message(
            phone="+10000000000",
            message="1",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )
        await console_service.process_message(
            phone="+10000000000",
            message="1",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )
        await console_service.process_message(
            phone="+10000000000",
            message="1",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
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
            message="newalpha@newdomain.com",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )
        assert "Tenant actualizado exitosamente" in reply
        assert "New Alpha Name" in reply  # Previous edit preserved in DB
        assert "Trackpal Master Console" in reply

        # Verify persisted changes
        tenant = await tenant_service.get_tenant(TENANT_1_ID)
        assert tenant is not None
        assert tenant.full_name == "New Alpha Name"
        assert tenant.email == "newalpha@newdomain.com"
        assert tenant.phone == "525512345678"  # Unchanged

        # Session should be cleared after second edit too
        session = await session_service.get_session("+10000000000")
        assert session is None
        # Verify persisted changes
        tenant = await tenant_service.get_tenant(TENANT_1_ID)
        assert tenant is not None
        assert tenant.full_name == "New Alpha Name"
        assert tenant.email == "newalpha@newdomain.com"
        assert tenant.phone == "525512345678"  # Unchanged

    async def test_edit_invalid_input_does_not_lose_selected_tenant(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        """Invalid edit input keeps the selected tenant context."""
        await _select_tenant(console_service, session_service, tenant_service)

        # Start edit, select full name
        await console_service.process_message(
            phone="+10000000000",
            message="1",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )
        await console_service.process_message(
            phone="+10000000000",
            message="1",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )
        # Send empty value
        await console_service.process_message(
            phone="+10000000000",
            message="",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )

        # Session should still have selected_tenant_id
        session = await session_service.get_session("+10000000000")
        assert session is not None
        assert session.selected_tenant_id == TENANT_1_ID
