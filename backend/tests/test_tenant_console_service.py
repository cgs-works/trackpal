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
from datetime import datetime
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.services.tenant_console_protocols import (
    CatalogServiceProtocol,
    ClientServiceProtocol,
    SubscriptionServiceProtocol,
)
from app.services.whatsapp_session_service import (
    ConversationSession,
    WhatsAppSessionService,
)
from app.services.whatsapp_tenant_console_facade import (
    NOT_TENANT_REPLY,
    WhatsAppTenantConsoleFacade,
)
from app.core.errors import UserFacingError
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


@dataclass
class FakeClientObj:
    """Object returned by FakeClientService, supporting attribute access."""

    id: UUID
    tenant_id: UUID
    full_name: str
    phone: str | None = None
    is_active: bool = True
    created_at: Any = None
    local_username: str | None = None

    @property
    def user(self) -> SimpleNamespace:
        return SimpleNamespace(username=self.local_username or "")


class FakeClientService:
    """In-memory double for ``ClientServiceProtocol``."""

    def __init__(self) -> None:
        self._clients: dict[str, FakeClientObj] = {}

    async def list_clients(self, db: Any, tenant_id: UUID) -> list[FakeClientObj]:
        return list(self._clients.values())

    async def get_client(
        self, db: Any, tenant_id: UUID, client_id: UUID
    ) -> FakeClientObj | None:
        return self._clients.get(str(client_id))

    async def create_client(
        self, db: Any, tenant_id: UUID, payload: Any
    ) -> FakeClientObj:
        client_id = uuid4()
        obj = FakeClientObj(
            id=client_id,
            tenant_id=tenant_id,
            full_name=payload.full_name,
            phone=getattr(payload, "phone", None),
            is_active=True,
            created_at=None,
            local_username=getattr(payload, "local_username", ""),
        )
        self._clients[str(client_id)] = obj
        return obj

    async def update_client(
        self, db: Any, tenant_id: UUID, client_id: UUID, payload: Any
    ) -> FakeClientObj | None:
        obj = self._clients.get(str(client_id))
        if obj is None:
            return None
        for key, value in payload.model_dump(exclude_none=True).items():
            setattr(obj, key, value)
        return obj

    async def deactivate_client(
        self, db: Any, tenant_id: UUID, client_id: UUID
    ) -> FakeClientObj | None:
        obj = self._clients.get(str(client_id))
        if obj is None:
            return None
        obj.is_active = False
        return obj

    async def activate_client(
        self, db: Any, tenant_id: UUID, client_id: UUID
    ) -> FakeClientObj | None:
        obj = self._clients.get(str(client_id))
        if obj is None:
            return None
        obj.is_active = True
        return obj

    async def delete_client(self, db: Any, tenant_id: UUID, client_id: UUID) -> bool:
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

    async def list_services(self, db: Any, tenant_id: UUID) -> list[FakeServiceObj]:
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
class FakeSubscriptionObj:
    id: UUID = field(default_factory=uuid4)
    tenant_id: UUID = field(default_factory=uuid4)
    client_id: UUID = field(default_factory=uuid4)
    service_id: UUID = field(default_factory=uuid4)
    plan_id: UUID = field(default_factory=uuid4)
    streaming_email: str = "cliente@test.com"
    profile_name: str | None = "Perfil 1"
    duration_type: str = "1_month"
    starts_at: Any = field(default_factory=lambda: datetime(2026, 1, 1))
    expires_at: Any = field(default_factory=lambda: datetime(2026, 1, 31))
    cancelled_at: Any = None
    status: str = "active"
    streaming_password: str | None = "secret123"
    profile_pin: str | None = "1234"
    client_name: str = "Cliente Demo"
    client_full_name: str = "Cliente Demo"
    service_name: str = "Netflix"
    plan_name: str = "Premium"


class FakeSubscriptionService:
    """In-memory double for ``SubscriptionServiceProtocol``."""

    def __init__(self, tenant_id: UUID, client_service: FakeClientService, catalog_service: FakeCatalogService) -> None:
        self.tenant_id = tenant_id
        self.client_service = client_service
        self.catalog_service = catalog_service
        service = next(iter(catalog_service._services.values()))
        plan = FakePlanObj(name="Premium")
        catalog_service._plans[str(plan.id)] = plan
        self.default_subscription = FakeSubscriptionObj(
            tenant_id=tenant_id,
            service_id=service.id,
            plan_id=plan.id,
            service_name=service.name,
            plan_name=plan.name,
        )
        self._subscriptions: dict[str, FakeSubscriptionObj] = {
            str(self.default_subscription.id): self.default_subscription
        }

    async def list_subscriptions(
        self,
        db: Any,
        tenant_id: UUID,
        status: str | None = None,
        client_id: UUID | None = None,
        service_id: UUID | None = None,
        quick_filter: str | None = None,
        expires_from: Any = None,
        expires_to: Any = None,
    ) -> list[FakeSubscriptionObj]:
        del db, quick_filter, expires_from, expires_to
        items = [s for s in self._subscriptions.values() if s.tenant_id == tenant_id]
        if status is not None:
            items = [s for s in items if s.status == status]
        if client_id is not None:
            items = [s for s in items if s.client_id == client_id]
        if service_id is not None:
            items = [s for s in items if s.service_id == service_id]
        return items

    async def get_subscription(
        self, db: Any, tenant_id: UUID, subscription_id: UUID
    ) -> FakeSubscriptionObj | None:
        del db
        sub = self._subscriptions.get(str(subscription_id))
        if sub is None or sub.tenant_id != tenant_id:
            return None
        return sub

    async def create_subscription(
        self, db: Any, tenant_id: UUID, payload: Any
    ) -> FakeSubscriptionObj:
        del db
        client = self.client_service._clients[str(payload.client_id)]
        service = self.catalog_service._services[str(payload.service_id)]
        plan = self.catalog_service._plans[str(payload.plan_id)]
        obj = FakeSubscriptionObj(
            tenant_id=tenant_id,
            client_id=payload.client_id,
            service_id=payload.service_id,
            plan_id=payload.plan_id,
            streaming_email=payload.streaming_email,
            profile_name=payload.profile_name,
            duration_type=payload.duration_type,
            starts_at=payload.starts_at,
            expires_at=payload.expires_at or datetime(2026, 2, 1),
            streaming_password=payload.streaming_password,
            profile_pin=payload.profile_pin,
            client_name=client.full_name,
            client_full_name=client.full_name,
            service_name=service.name,
            plan_name=plan.name,
        )
        self._subscriptions[str(obj.id)] = obj
        return obj

    async def update_subscription(
        self,
        db: Any,
        tenant_id: UUID,
        subscription_id: UUID,
        payload: Any,
    ) -> FakeSubscriptionObj | None:
        del db, tenant_id
        sub = self._subscriptions.get(str(subscription_id))
        if sub is None:
            return None
        for key, value in payload.model_dump(exclude_unset=True).items():
            if key == "streaming_password":
                sub.streaming_password = value or None
            elif key == "profile_pin":
                sub.profile_pin = value or None
            else:
                setattr(sub, key, value)
        if getattr(sub, "client_id", None):
            client = self.client_service._clients.get(str(sub.client_id))
            if client is not None:
                sub.client_name = client.full_name
                sub.client_full_name = client.full_name
        if getattr(sub, "service_id", None):
            service = self.catalog_service._services.get(str(sub.service_id))
            if service is not None:
                sub.service_name = service.name
        if getattr(sub, "plan_id", None):
            plan = self.catalog_service._plans.get(str(sub.plan_id))
            if plan is not None:
                sub.plan_name = plan.name
        return sub

    async def cancel_subscription(
        self,
        db: Any,
        tenant_id: UUID,
        subscription_id: UUID,
        notes: str | None = None,
    ) -> FakeSubscriptionObj | None:
        del db, tenant_id, notes
        sub = self._subscriptions.get(str(subscription_id))
        if sub is None:
            return None
        sub.status = "cancelled"
        return sub

    async def reactivate_subscription(
        self,
        db: Any,
        tenant_id: UUID,
        subscription_id: UUID,
        duration_type: str,
        starts_at: Any = None,
        expires_at: Any = None,
        notes: str | None = None,
    ) -> FakeSubscriptionObj | None:
        del db, tenant_id, notes
        sub = self._subscriptions.get(str(subscription_id))
        if sub is None:
            return None
        sub.status = "active"
        sub.duration_type = duration_type
        if starts_at is not None:
            sub.starts_at = starts_at
        if expires_at is not None:
            sub.expires_at = expires_at
        return sub

    async def renew_subscription(
        self,
        db: Any,
        tenant_id: UUID,
        subscription_id: UUID,
        duration_type: str,
        expires_at: Any = None,
        notes: str | None = None,
    ) -> FakeSubscriptionObj | None:
        del db, tenant_id, notes
        sub = self._subscriptions.get(str(subscription_id))
        if sub is None:
            return None
        sub.status = "active"
        sub.duration_type = duration_type
        if expires_at is not None:
            sub.expires_at = expires_at
        return sub

    async def reveal_credentials(
        self, db: Any, tenant_id: UUID, subscription_id: UUID
    ) -> dict[str, str | None] | None:
        del db, tenant_id
        sub = self._subscriptions.get(str(subscription_id))
        if sub is None:
            return None
        return {
            "streaming_password": sub.streaming_password,
            "profile_pin": sub.profile_pin,
        }


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

    async def get_tenant(self, db: Any, user_id: UUID) -> FakeTenantObj | None:
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
    svc = FakeClientService()
    client_id = uuid4()
    svc._clients[str(client_id)] = FakeClientObj(
        id=client_id,
        tenant_id=uuid4(),
        full_name="Cliente Demo",
        phone="1234567890",
        local_username="cliente.demo",
    )
    return svc


@pytest.fixture
def catalog_service() -> FakeCatalogService:
    svc = FakeCatalogService()
    service = FakeServiceObj(name="Netflix")
    svc._services[str(service.id)] = service
    return svc


@pytest.fixture
def subscription_service(
    client_service: FakeClientService,
    catalog_service: FakeCatalogService,
) -> FakeSubscriptionService:
    tenant_id = next(iter(client_service._clients.values())).tenant_id
    service = FakeSubscriptionService(tenant_id, client_service, catalog_service)
    client = next(iter(client_service._clients.values()))
    service.default_subscription.client_id = client.id
    service.default_subscription.client_name = client.full_name
    service.default_subscription.client_full_name = client.full_name
    return service


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
    subscription_service: FakeSubscriptionService,
) -> WhatsAppTenantConsoleService:
    return WhatsAppTenantConsoleService(
        client_service=client_service,
        catalog_service=catalog_service,
        profile_service=profile_service,
        subscription_service=subscription_service,
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
        """Inactive tenant returns translated inactive message."""
        tenant_service.set_active(False)
        identity = _tenant_identity(role="tenant")
        reply = await facade.process_message(
            phone="+10000000000",
            message="1",
            identity=identity,
            db=object(),  # Needs db to trigger tenant lookup
        )
        assert "desactivada" in reply and "Master de Trackpal" in reply

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
        """Top-level '0' with no active flow returns translated goodbye."""
        identity = _tenant_identity(role="tenant")
        reply = await facade.process_message(
            phone="+10000000000",
            message="0",
            identity=identity,
            db=object(),
        )
        assert "Sesión cerrada" in reply and "consola de administración" in reply

    async def test_facade_top_level_zero_closes_evolution_session(
        self,
        facade: WhatsAppTenantConsoleFacade,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Top-level '0' closes the Evolution chat session when instance is present."""
        calls: list[dict[str, str]] = []

        async def fake_close_chat_session(instance: str, remote_jid: str) -> None:
            calls.append({"instance": instance, "remote_jid": remote_jid})

        monkeypatch.setattr(
            "app.services.whatsapp_tenant_console_facade.evolution_client.close_chat_session",
            fake_close_chat_session,
        )

        identity = _tenant_identity(role="tenant")
        reply = await facade.process_message(
            phone="+10000000000",
            message="0",
            identity=identity,
            instance="tenant-instance",
            db=object(),
        )

        assert "Sesión cerrada" in reply and "consola de administración" in reply
        assert calls == [
            {
                "instance": "tenant-instance",
                "remote_jid": "10000000000@s.whatsapp.net",
            }
        ]

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

    @pytest.mark.parametrize("cmd", ["menu", "/menu", "MENU", "/MENU"])
    async def test_service_menu_commands_return_main_menu(
        self,
        console_service: WhatsAppTenantConsoleService,
        cmd: str,
    ) -> None:
        """Menu commands without active flow return main menu."""
        reply = await console_service.process_message(
            phone="+10000000000",
            message=cmd,
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
        """Option '5' returns HELP_TEXT."""
        reply = await console_service.process_message(
            phone="+10000000000",
            message="5",
        )
        assert "Ayuda" in reply
        assert "comandos disponibles" in reply

    async def test_service_subscriptions(
        self,
        console_service: WhatsAppTenantConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        """Option '4' returns SUBSCRIPTIONS_MENU with persisted session."""
        reply = await console_service.process_message(
            phone="+10000000000",
            message="4",
            session_service=session_service,
        )
        assert "Suscripciones" in reply

        # Session should be persisted with flow=subscriptions, step=menu
        session = await session_service.get_session("admin:+10000000000")
        assert session is not None
        assert session.flow == "subscriptions"
        assert session.step == "menu"

    async def test_service_subscriptions_list_and_detail(
        self,
        console_service: WhatsAppTenantConsoleService,
        session_service: WhatsAppSessionService,
        subscription_service: FakeSubscriptionService,
    ) -> None:
        tenant_id = subscription_service.tenant_id
        await console_service.process_message(
            phone="+10000000000",
            message="4",
            tenant_id=tenant_id,
            db=object(),
            session_service=session_service,
        )
        reply_filter = await console_service.process_message(
            phone="+10000000000",
            message="1",
            tenant_id=tenant_id,
            db=object(),
            session_service=session_service,
        )
        assert "Filtrar por estado" in reply_filter

        reply_list = await console_service.process_message(
            phone="+10000000000",
            message="1",
            tenant_id=tenant_id,
            db=object(),
            session_service=session_service,
        )
        assert "Lista" in reply_list or "Suscripciones" in reply_list

        reply_detail = await console_service.process_message(
            phone="+10000000000",
            message="1",
            tenant_id=tenant_id,
            db=object(),
            session_service=session_service,
        )
        assert "Detalle de Suscripción" in reply_detail
        assert "secret123" in reply_detail
        assert "1234" in reply_detail

    async def test_service_subscriptions_create_flow(
        self,
        console_service: WhatsAppTenantConsoleService,
        session_service: WhatsAppSessionService,
        subscription_service: FakeSubscriptionService,
    ) -> None:
        tenant_id = subscription_service.tenant_id
        await console_service.process_message(
            phone="+10000000000",
            message="4",
            tenant_id=tenant_id,
            db=object(),
            session_service=session_service,
        )
        steps = ["2", "1", "1", "1", "nuevo@test.com", "clave123", "clave123", "1", "Perfil Kids", "7788", "7788", "1", "CONFIRMAR"]
        reply = ""
        for step in steps:
            reply = await console_service.process_message(
                phone="+10000000000",
                message=step,
                tenant_id=tenant_id,
                db=object(),
                session_service=session_service,
            )
        assert "Suscripción creada exitosamente" in reply
        assert len(subscription_service._subscriptions) == 2

    async def test_service_subscriptions_edit_email_flow(
        self,
        console_service: WhatsAppTenantConsoleService,
        session_service: WhatsAppSessionService,
        subscription_service: FakeSubscriptionService,
    ) -> None:
        tenant_id = subscription_service.tenant_id
        for step in ["4", "1", "1", "1", "1", "4", "editado@test.com"]:
            reply = await console_service.process_message(
                phone="+10000000000",
                message=step,
                tenant_id=tenant_id,
                db=object(),
                session_service=session_service,
            )
        assert "Suscripción actualizada exitosamente" in reply
        assert subscription_service.default_subscription.streaming_email == "editado@test.com"

    async def test_service_subscriptions_cancel_flow(
        self,
        console_service: WhatsAppTenantConsoleService,
        session_service: WhatsAppSessionService,
        subscription_service: FakeSubscriptionService,
    ) -> None:
        tenant_id = subscription_service.tenant_id
        for step in ["4", "1", "1", "1", "2", "CONFIRMAR"]:
            reply = await console_service.process_message(
                phone="+10000000000",
                message=step,
                tenant_id=tenant_id,
                db=object(),
                session_service=session_service,
            )
        assert "Suscripción cancelada exitosamente" in reply
        assert subscription_service.default_subscription.status == "cancelled"

    async def test_service_subscriptions_renew_and_reactivate_flows(
        self,
        console_service: WhatsAppTenantConsoleService,
        session_service: WhatsAppSessionService,
        subscription_service: FakeSubscriptionService,
    ) -> None:
        tenant_id = subscription_service.tenant_id
        for step in ["4", "1", "1", "1", "3", "1", "CONFIRMAR"]:
            reply = await console_service.process_message(
                phone="+10000000000",
                message=step,
                tenant_id=tenant_id,
                db=object(),
                session_service=session_service,
            )
        assert "Suscripción renovada exitosamente" in reply

        subscription_service.default_subscription.status = "cancelled"
        for step in ["4", "1", "3", "1", "4", "1", "CONFIRMAR"]:
            reply = await console_service.process_message(
                phone="+10000000000",
                message=step,
                tenant_id=tenant_id,
                db=object(),
                session_service=session_service,
            )
        assert "Suscripción reactivada exitosamente" in reply
        assert subscription_service.default_subscription.status == "active"

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

    @pytest.mark.parametrize(
        "cmd", ["menu", "menú", "/menu", "MENU", "/MENU", "/Menu", "cancelar"]
    )
    async def test_service_reset_commands_cancel_flow(
        self,
        console_service: WhatsAppTenantConsoleService,
        session_service: WhatsAppSessionService,
        cmd: str,
    ) -> None:
        """Various menu/reset commands inside clients flow cancel and clear session."""
        session = await session_service.create_session("admin:+10000000000")
        session.flow = "clients"
        session.step = "list"
        await session_service.save_session(session)

        reply = await console_service.process_message(
            phone="+10000000000",
            message=cmd,
            session_service=session_service,
        )
        assert "cancelada" in reply.lower() or "Consola de Administración" in reply

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


# ===================================================================
# Client selection flow tests
# ===================================================================


@pytest.mark.asyncio
class TestClientSelect:
    """Client selection from numbered list with dedicated SELECT step."""

    async def test_service_client_list_select_shows_detail(
        self,
        console_service: WhatsAppTenantConsoleService,
        session_service: WhatsAppSessionService,
        client_service: FakeClientService,
    ) -> None:
        """Selecting a client from the list shows its detail."""
        tenant_id = uuid4()
        client_id = uuid4()
        client_service._clients[str(client_id)] = FakeClientObj(
            id=client_id,
            tenant_id=tenant_id,
            full_name="Test Client",
            phone="52123456789",
            is_active=True,
            created_at=None,
            local_username="testclient",
        )

        # Start clients flow
        reply = await console_service.process_message(
            phone="+20000000001",
            message="1",
            session_service=session_service,
            tenant_id=tenant_id,
        )
        assert "Clientes" in reply

        # Now show the list (press "1" on the clients submenu)
        reply = await console_service.process_message(
            phone="+20000000001",
            message="1",
            session_service=session_service,
            tenant_id=tenant_id,
            db="fake",  # db needed for list_clients
        )
        assert "Test Client" in reply

        # Session should be in CLIENTS_STEP_SELECT
        session = await session_service.get_session("admin:+20000000001")
        assert session is not None
        assert session.step == "select"

        # Now select client #1
        reply = await console_service.process_message(
            phone="+20000000001",
            message="1",
            session_service=session_service,
            tenant_id=tenant_id,
            db="fake",
        )
        assert "Detalle" in reply or "Test Client" in reply
        # Session should advance to detail_action
        session = await session_service.get_session("admin:+20000000001")
        assert session is not None
        assert session.step == "detail_action"

    async def test_service_client_select_zero_goes_back(
        self,
        console_service: WhatsAppTenantConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        """'0' from client selection is intercepted by global reset."""
        # Create session at SELECT step
        session = await session_service.create_session("admin:+20000000002")
        session.flow = "clients"
        session.step = "select"
        session.selection_map = {"1": str(uuid4())}
        await session_service.save_session(session)

        reply = await console_service.process_message(
            phone="+20000000002",
            message="0",
            session_service=session_service,
        )
        # Global reset intercepts '0' on any active flow → cancel
        assert "cancelada" in reply.lower() or "Consola de Administración" in reply
        # Session is cleared by global reset
        session = await session_service.get_session("admin:+20000000002")
        assert session is None

    async def test_service_client_create_duplicate_phone_uses_translated_message(
        self,
        console_service: WhatsAppTenantConsoleService,
    ) -> None:
        session = SimpleNamespace(
            temp_data={
                "full_name": "Cliente Uno",
                "local_username": "clienteuno",
                "phone": "+12015550030",
                "password": "secret123",
            },
            step=console_service.CLIENTS_STEP_CREATE_CONFIRM,
        )

        async def _raise(*args: Any, **kwargs: Any) -> None:
            raise UserFacingError("phone_already_registered")

        console_service._client_service.create_client = _raise  # type: ignore[assignment]

        reply = await console_service._handle_client_create_confirm(
            phone="+10000000000",
            msg="CONFIRMAR",
            session=session,
            session_service=None,
            tenant_id=uuid4(),
            db=object(),
        )

        assert "El teléfono ya está registrado" in reply
        assert "phone_already_registered" not in reply
        assert session.step == console_service.CLIENTS_STEP_CREATE_PHONE

    async def test_service_client_edit_duplicate_username_uses_translated_message(
        self,
        console_service: WhatsAppTenantConsoleService,
    ) -> None:
        session = SimpleNamespace(
            temp_data={"field": "local_username"},
            selected_tenant_id=str(uuid4()),
        )

        async def _raise(*args: Any, **kwargs: Any) -> None:
            raise UserFacingError("username_already_registered")

        console_service._client_service.update_client = _raise  # type: ignore[assignment]

        reply = await console_service._handle_client_edit_value(
            phone="+10000000000",
            msg="nuevo",
            session=session,
            session_service=None,
            tenant_id=uuid4(),
            db=object(),
        )

        assert "El nombre de usuario ya existe" in reply
        assert "username_already_registered" not in reply
