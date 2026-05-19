"""Tests for the WhatsApp Tenant Admin Console service and facade.

Tests the facade orchestration layer (role validation, tenant status,
top-level exit) and the service conversation flow routing (menu display,
submenu session persistence, cancellation, fallback).

Uses the same FakeRedis/FakeManager pattern as ``test_whatsapp_menu_flow.py``
for session persistence, plus simple in-memory doubles for the protocol
interfaces.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.services.tenant_console_protocols import (
    CatalogServiceProtocol,
    ClientServiceProtocol,
)
from app.services.whatsapp_session_service import (
    ConversationSession,
    WhatsAppSessionService,
)
from app.services.whatsapp_tenant_console_facade import (
    GOODBYE_REPLY,
    INACTIVE_TENANT_REPLY,
    NOT_TENANT_REPLY,
    WhatsAppTenantConsoleFacade,
)
from app.services.whatsapp_tenant_console_service import (
    WhatsAppTenantConsoleService,
)

# ===================================================================
# Fakes
# ===================================================================


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


# -------------------------------------------------------------------
# In-memory service doubles
# -------------------------------------------------------------------


class FakeClientService:
    """In-memory double for ``ClientServiceProtocol``."""

    def __init__(self) -> None:
        self._clients: dict[str, dict[str, Any]] = {}

    async def list_clients(
        self, db: Any, tenant_id: UUID
    ) -> list[Any]:
        return list(self._clients.values())

    async def get_client(
        self, db: Any, tenant_id: UUID, client_id: UUID
    ) -> Any | None:
        return self._clients.get(str(client_id))

    async def create_client(
        self, db: Any, tenant_id: UUID, payload: Any
    ) -> Any:
        client_id = uuid4()
        obj = {
            "id": client_id,
            "tenant_id": tenant_id,
            "full_name": payload.full_name,
            "phone": getattr(payload, "phone", None),
            "is_active": True,
            "created_at": None,
        }
        self._clients[str(client_id)] = obj
        return obj

    async def update_client(
        self, db: Any, tenant_id: UUID, client_id: UUID, payload: Any
    ) -> Any | None:
        obj = self._clients.get(str(client_id))
        if obj is None:
            return None
        for key, value in payload.model_dump(exclude_none=True).items():
            obj[key] = value
        return obj

    async def deactivate_client(
        self, db: Any, tenant_id: UUID, client_id: UUID
    ) -> Any | None:
        obj = self._clients.get(str(client_id))
        if obj is None:
            return None
        obj["is_active"] = False
        return obj

    async def activate_client(
        self, db: Any, tenant_id: UUID, client_id: UUID
    ) -> Any | None:
        obj = self._clients.get(str(client_id))
        if obj is None:
            return None
        obj["is_active"] = True
        return obj

    async def delete_client(
        self, db: Any, tenant_id: UUID, client_id: UUID
    ) -> bool:
        return self._clients.pop(str(client_id), None) is not None


@dataclass
class FakeServiceObj:
    id: UUID = field(default_factory=uuid4)
    name: str = "Test Service"


@dataclass
class FakePlanObj:
    id: UUID = field(default_factory=uuid4)
    name: str = "Test Plan"


class FakeCatalogService:
    """In-memory double for ``CatalogServiceProtocol``."""

    def __init__(self) -> None:
        self._services: dict[str, FakeServiceObj] = {}
        self._plans: dict[str, FakePlanObj] = {}

    async def list_services(
        self, db: Any, tenant_id: UUID
    ) -> list[FakeServiceObj]:
        return list(self._services.values())

    async def get_service(
        self, db: Any, tenant_id: UUID, service_id: UUID
    ) -> FakeServiceObj | None:
        return self._services.get(str(service_id))

    async def update_service(
        self, db: Any, tenant_id: UUID, service_id: UUID, payload: Any
    ) -> FakeServiceObj | None:
        service = self._services.get(str(service_id))
        if service is None:
            return None
        service.name = payload.name
        return service

    async def list_plans(
        self, db: Any, tenant_id: UUID, service_id: UUID
    ) -> list[FakePlanObj] | None:
        return list(self._plans.values())

    async def get_plan(
        self,
        db: Any,
        tenant_id: UUID,
        service_id: UUID,
        plan_id: UUID,
    ) -> FakePlanObj | None:
        return self._plans.get(str(plan_id))

    async def update_plan(
        self,
        db: Any,
        tenant_id: UUID,
        service_id: UUID,
        plan_id: UUID,
        payload: Any,
    ) -> FakePlanObj | None:
        plan = self._plans.get(str(plan_id))
        if plan is None:
            return None
        plan.name = payload.name
        return plan


@dataclass
class FakeProfileObj:
    full_name: str = "Test Admin"
    email: str = "admin@test.com"
    phone: str = "1234567890"


class FakeProfileService:
    """In-memory double for the profile service."""

    def __init__(self) -> None:
        self._profile = FakeProfileObj()

    async def get_profile(self, db: Any, user: Any) -> FakeProfileObj | None:
        return self._profile

    async def update_profile(
        self, db: Any, user: Any, payload: Any
    ) -> FakeProfileObj | None:
        for key, value in payload.model_dump(exclude_none=True).items():
            setattr(self._profile, key, value)
        return self._profile

    async def change_password(
        self, db: Any, user: Any, old_password: str, new_password: str
    ) -> bool:
        if old_password != "correct-password":
            return False
        return True


@dataclass
class FakeTenantObj:
    id: UUID = field(default_factory=uuid4)
    owner_user_id: UUID = field(default_factory=uuid4)
    is_active: bool = True


class FakeTenantService:
    """In-memory double for TenantService."""

    def __init__(self) -> None:
        self._tenants: dict[str, FakeTenantObj] = {}
        self._default_tenant = FakeTenantObj()

    async def get_tenant(
        self, db: Any, user_id: UUID
    ) -> FakeTenantObj | None:
        return self._default_tenant

    def set_active(self, active: bool) -> None:
        self._default_tenant.is_active = active


# ===================================================================
# Fixtures
# ===================================================================


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
def client_service() -> FakeClientService:
    return FakeClientService()


@pytest.fixture
def catalog_service() -> FakeCatalogService:
    svc = FakeCatalogService()
    svc._services["svc-1"] = FakeServiceObj()
    return svc


@pytest.fixture
def profile_service() -> FakeProfileService:
    return FakeProfileService()


@pytest.fixture
def tenant_service() -> FakeTenantService:
    return FakeTenantService()


@pytest.fixture
def console_service(
    client_service: FakeClientService,
    catalog_service: FakeCatalogService,
    profile_service: FakeProfileService,
) -> WhatsAppTenantConsoleService:
    return WhatsAppTenantConsoleService(
        client_service=client_service,
        catalog_service=catalog_service,
        profile_service=profile_service,
    )


@pytest.fixture
def facade(
    console_service: WhatsAppTenantConsoleService,
    session_service: WhatsAppSessionService,
    tenant_service: FakeTenantService,
) -> WhatsAppTenantConsoleFacade:
    return WhatsAppTenantConsoleFacade(
        console_service=console_service,
        session_service=session_service,
        tenant_service=tenant_service,
    )


def _tenant_identity(role: str = "tenant") -> dict[str, Any]:
    return {
        "user_id": str(uuid4()),
        "role": role,
        "username": "testadmin",
    }


# ===================================================================
# Facade tests
# ===================================================================


@pytest.mark.asyncio
class TestFacade:
    """Orchestration layer: role validation, tenant status, top-level exit."""

    async def test_facade_unknown_role_rejected(
        self, facade: WhatsAppTenantConsoleFacade
    ) -> None:
        """Non-tenant role returns NOT_TENANT_REPLY."""
        identity = _tenant_identity(role="master")
        reply = await facade.process_message(
            phone="+10000000000",
            message="1",
            identity=identity,
        )
        assert reply == NOT_TENANT_REPLY

    async def test_facade_inactive_tenant_rejected(
        self,
        facade: WhatsAppTenantConsoleFacade,
        tenant_service: FakeTenantService,
    ) -> None:
        """Inactive tenant returns INACTIVE_TENANT_REPLY."""
        tenant_service.set_active(False)
        identity = _tenant_identity(role="tenant")
        reply = await facade.process_message(
            phone="+10000000000",
            message="1",
            identity=identity,
            db=object(),  # Needs db to trigger tenant lookup
        )
        assert reply == INACTIVE_TENANT_REPLY

    async def test_facade_active_tenant_delegates(
        self,
        facade: WhatsAppTenantConsoleFacade,
    ) -> None:
        """Active tenant delegates to console service, returns menu."""
        identity = _tenant_identity(role="tenant")
        reply = await facade.process_message(
            phone="+10000000000",
            message="",
            identity=identity,
            db=object(),
        )
        # The service returns MAIN_MENU for empty message
        assert "Trackpal Consola de Administración" in reply

    async def test_facade_top_level_zero_exits(
        self,
        facade: WhatsAppTenantConsoleFacade,
    ) -> None:
        """Top-level '0' with no active flow returns GOODBYE_REPLY."""
        identity = _tenant_identity(role="tenant")
        reply = await facade.process_message(
            phone="+10000000000",
            message="0",
            identity=identity,
            db=object(),
        )
        assert reply == GOODBYE_REPLY

    async def test_facade_zero_with_active_flow_cancels(
        self,
        facade: WhatsAppTenantConsoleFacade,
        session_service: WhatsAppSessionService,
    ) -> None:
        """'0' with an active flow cancels the flow (not top-level exit)."""
        # Create an active session first
        session = await session_service.create_session("admin:+10000000000")
        session.flow = "clients"
        session.step = "list"
        await session_service.save_session(session)

        identity = _tenant_identity(role="tenant")
        reply = await facade.process_message(
            phone="+10000000000",
            message="0",
            identity=identity,
            db=object(),
        )
        # Should cancel (not goodbye), returning main menu
        assert "Operación cancelada" in reply or "Consola de Administración" in reply


# ===================================================================
# Service flow tests
# ===================================================================


@pytest.mark.asyncio
class TestServiceMainMenu:
    """Main menu display and navigation."""

    async def test_service_main_menu(
        self, console_service: WhatsAppTenantConsoleService
    ) -> None:
        """No session returns MAIN_MENU."""
        reply = await console_service.process_message(
            phone="+10000000000",
            message="",
        )
        assert "Trackpal Consola de Administración" in reply

    async def test_service_clients_menu(
        self,
        console_service: WhatsAppTenantConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        """Option '1' returns CLIENTS_MENU with persisted session."""
        reply = await console_service.process_message(
            phone="+10000000000",
            message="1",
            session_service=session_service,
        )
        assert "Clientes" in reply

        # Session should be persisted with flow=clients, step=list
        session = await session_service.get_session("admin:+10000000000")
        assert session is not None
        assert session.flow == "clients"
        assert session.step == "list"

    async def test_service_catalog_menu(
        self,
        console_service: WhatsAppTenantConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        """Option '2' starts catalog flow."""
        reply = await console_service.process_message(
            phone="+10000000000",
            message="2",
            session_service=session_service,
        )
        # Should show services or catalog prompt
        assert "Servicio" in reply or "Catálogo" in reply or "catalog" in reply.lower()

    async def test_service_profile_menu(
        self,
        console_service: WhatsAppTenantConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        """Option '3' returns PROFILE_MENU with persisted session."""
        reply = await console_service.process_message(
            phone="+10000000000",
            message="3",
            session_service=session_service,
        )
        assert "Mi Perfil" in reply

        # Session should be persisted with flow=profile, step=action
        session = await session_service.get_session("admin:+10000000000")
        assert session is not None
        assert session.flow == "profile"
        assert session.step == "action"

    async def test_service_help(
        self, console_service: WhatsAppTenantConsoleService
    ) -> None:
        """Option '4' returns HELP_TEXT."""
        reply = await console_service.process_message(
            phone="+10000000000",
            message="4",
        )
        assert "Ayuda" in reply
        assert "comandos disponibles" in reply

    async def test_service_zero_main_menu_exits(
        self,
        console_service: WhatsAppTenantConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        """'0' with no active flow exits the console."""
        reply = await console_service.process_message(
            phone="+10000000000",
            message="0",
            session_service=session_service,
        )
        assert "Has salido" in reply

    async def test_service_zero_active_flow_cancels(
        self,
        console_service: WhatsAppTenantConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        """'0' with active flow cancels the operation."""
        # Create an active session
        session = await session_service.create_session("admin:+10000000000")
        session.flow = "clients"
        session.step = "list"
        await session_service.save_session(session)

        reply = await console_service.process_message(
            phone="+10000000000",
            message="0",
            session_service=session_service,
        )
        assert "cancelada" in reply.lower()

    async def test_service_fallback_no_flow(
        self, console_service: WhatsAppTenantConsoleService
    ) -> None:
        """Invalid input with no flow returns FALLBACK_NO_FLOW."""
        reply = await console_service.process_message(
            phone="+10000000000",
            message="xyzzy",
        )
        assert "No entendí" in reply


# ===================================================================
# Zero-handling tests
# ===================================================================


@pytest.mark.asyncio
class TestZeroHandling:
    """Zero/cancel behaviour inside active submenu flows."""

    async def test_service_cancel_inside_clients_flow(
        self,
        console_service: WhatsAppTenantConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        """'0' inside clients flow (after _start_clients_flow) cancels."""
        # Start clients flow first (creates session)
        session = await session_service.create_session("admin:+10000000000")
        session.flow = "clients"
        session.step = "list"
        await session_service.save_session(session)

        # Now send '0'
        reply = await console_service.process_message(
            phone="+10000000000",
            message="0",
            session_service=session_service,
        )
        assert "cancelada" in reply.lower() or "Consola de Administración" in reply

        # Session should be cleared
        fetched = await session_service.get_session("admin:+10000000000")
        assert fetched is None

    async def test_service_cancel_inside_profile_flow(
        self,
        console_service: WhatsAppTenantConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        """'0' inside profile flow cancels."""
        session = await session_service.create_session("admin:+10000000000")
        session.flow = "profile"
        session.step = "action"
        await session_service.save_session(session)

        reply = await console_service.process_message(
            phone="+10000000000",
            message="0",
            session_service=session_service,
        )
        assert "cancelada" in reply.lower() or "Consola de Administración" in reply

        # Session should be cleared
        fetched = await session_service.get_session("admin:+10000000000")
        assert fetched is None


# ===================================================================
# Service without session service
# ===================================================================


@pytest.mark.asyncio
class TestServiceNoSession:
    """Edge case: process_message without session_service."""

    async def test_empty_message_without_session(
        self, console_service: WhatsAppTenantConsoleService
    ) -> None:
        """Empty message without session_service returns main menu."""
        reply = await console_service.process_message(
            phone="+10000000000",
            message="",
        )
        assert "Trackpal Consola de Administración" in reply

    async def test_main_menu_options_without_session(
        self, console_service: WhatsAppTenantConsoleService
    ) -> None:
        """Main menu options work without session_service."""
        reply = await console_service.process_message(
            phone="+10000000000",
            message="1",
        )
        assert "Clientes" in reply
