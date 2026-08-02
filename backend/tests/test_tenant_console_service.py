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
from decimal import Decimal
from datetime import datetime
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.whatsapp_session_service import (
    ConversationSession,
    WhatsAppSessionService,
)
from app.services.whatsapp_tenant_console_facade import (
    NOT_TENANT_REPLY,
    WhatsAppTenantConsoleFacade,
)
from app.core.errors import UserFacingError
from app.core.redis_client import RedisConnectionManager
from app.schemas.whatsapp import WhatsAppConsoleResponse
from app.services.tenant_service import TenantService
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

    async def set(
        self, key: str, value: str, ex: int | None = None, **kwargs: Any
    ) -> None:
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
    username: str | None = None

    @property
    def user(self) -> SimpleNamespace:
        return SimpleNamespace(username=self.username or "")


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
            username=getattr(payload, "username", ""),
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
class FakeDeletePagination:
    page: int = 1
    page_size: int = 7
    total_items: int = 0
    total_pages: int = 1
    has_next: bool = False


@dataclass
class FakeDeleteRow:
    id: UUID = field(default_factory=uuid4)
    streaming_email: str = "active@example.com"
    client_name: str = "Cliente Demo"
    client_phone: str = "584241234567"
    service_name: str = "Netflix"
    plan_name: str = "Premium"
    expires_at: datetime = field(default_factory=lambda: datetime(2026, 7, 1))


@dataclass
class FakeDeletePreview:
    target_type: str = "service"
    target_id: UUID = field(default_factory=uuid4)
    target_name: str = "Netflix"
    affected_plan_count: int = 0
    active_subscription_count: int = 0
    historical_subscription_count: int = 0
    total_subscription_count: int = 0
    active_subscriptions: list[FakeDeleteRow] = field(default_factory=list)
    pagination: FakeDeletePagination = field(default_factory=FakeDeletePagination)
    note: str = "Las suscripciones historicas tambien se eliminaran."


@dataclass
class FakeServiceObj:
    id: UUID = field(default_factory=uuid4)
    name: str = "Test Service"
    plan_count: int = 0
    active_subscription_count: int = 0


@dataclass
class FakePlanObj:
    id: UUID = field(default_factory=uuid4)
    service_id: UUID | None = None
    name: str = "Test Plan"
    active_subscription_count: int = 0
    price: Any = None  # Decimal | None


class FakeCatalogService:
    """In-memory double for ``CatalogServiceProtocol``."""

    def __init__(self) -> None:
        self._services: dict[str, FakeServiceObj] = {}
        self._plans: dict[str, FakePlanObj] = {}

    async def list_services(self, db: Any, tenant_id: UUID) -> list[FakeServiceObj]:
        return list(self._services.values())

    async def list_service_summaries(
        self, db: Any, tenant_id: UUID
    ) -> list[FakeServiceObj]:
        return sorted(self._services.values(), key=lambda s: s.name.lower())

    async def list_plan_summaries(
        self, db: Any, tenant_id: UUID, service_id: UUID
    ) -> list[FakePlanObj] | None:
        if str(service_id) not in self._services:
            return None
        return sorted(
            [plan for plan in self._plans.values() if plan.service_id == service_id],
            key=lambda p: p.name.lower(),
        )

    async def create_service(
        self, db: Any, tenant_id: UUID, payload: Any
    ) -> FakeServiceObj:
        if any(s.name.lower() == payload.name.lower() for s in self._services.values()):
            raise UserFacingError("service_name_already_exists")
        service = FakeServiceObj(name=payload.name)
        self._services[str(service.id)] = service
        return service

    async def create_plan(
        self,
        db: Any,
        tenant_id: UUID,
        service_id: UUID,
        payload: Any,
    ) -> FakePlanObj | None:
        if str(service_id) not in self._services:
            return None
        if any(
            p.service_id == service_id and p.name.lower() == payload.name.lower()
            for p in self._plans.values()
        ):
            raise UserFacingError("plan_name_already_exists")
        plan = FakePlanObj(
            service_id=service_id,
            name=payload.name,
            price=getattr(payload, "price", None),
        )
        self._plans[str(plan.id)] = plan
        return plan

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
        if "price" in payload.model_fields_set:
            plan.price = payload.price
        return plan

    async def get_service_delete_preview(
        self,
        db: Any,
        tenant_id: UUID,
        service_id: UUID,
        *,
        page: int = 1,
        page_size: int = 7,
    ) -> FakeDeletePreview | None:
        service = self._services.get(str(service_id))
        if service is None:
            return None
        rows = [FakeDeleteRow(service_name=service.name, plan_name="Premium")]
        return FakeDeletePreview(
            target_type="service",
            target_id=service.id,
            target_name=service.name,
            affected_plan_count=service.plan_count,
            active_subscription_count=service.active_subscription_count,
            historical_subscription_count=1,
            total_subscription_count=service.active_subscription_count + 1,
            active_subscriptions=rows[:page_size],
            pagination=FakeDeletePagination(
                page=page,
                page_size=page_size,
                total_items=len(rows),
                total_pages=1,
                has_next=False,
            ),
        )

    async def get_plan_delete_preview(
        self,
        db: Any,
        tenant_id: UUID,
        service_id: UUID,
        plan_id: UUID,
        *,
        page: int = 1,
        page_size: int = 7,
    ) -> FakeDeletePreview | None:
        plan = self._plans.get(str(plan_id))
        if plan is None:
            return None
        rows = (
            [FakeDeleteRow(plan_name=plan.name)]
            if plan.active_subscription_count
            else []
        )
        return FakeDeletePreview(
            target_type="plan",
            target_id=plan.id,
            target_name=plan.name,
            affected_plan_count=0,
            active_subscription_count=plan.active_subscription_count,
            historical_subscription_count=0,
            total_subscription_count=plan.active_subscription_count,
            active_subscriptions=rows[:page_size],
            pagination=FakeDeletePagination(
                page=page,
                page_size=page_size,
                total_items=len(rows),
                total_pages=1,
                has_next=False,
            ),
        )

    async def delete_service(
        self, db: Any, tenant_id: UUID, service_id: UUID, *, confirm: bool = False
    ) -> FakeDeletePreview | None:
        if not confirm:
            raise UserFacingError("catalog_delete_confirmation_required")
        preview = await self.get_service_delete_preview(db, tenant_id, service_id)
        self._services.pop(str(service_id), None)
        return preview

    async def delete_plan(
        self,
        db: Any,
        tenant_id: UUID,
        service_id: UUID,
        plan_id: UUID,
        *,
        confirm: bool = False,
    ) -> FakeDeletePreview | None:
        if not confirm:
            raise UserFacingError("catalog_delete_confirmation_required")
        preview = await self.get_plan_delete_preview(db, tenant_id, service_id, plan_id)
        self._plans.pop(str(plan_id), None)
        return preview


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

    def __init__(
        self,
        tenant_id: UUID,
        client_service: FakeClientService,
        catalog_service: FakeCatalogService,
    ) -> None:
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

    async def get_reminder_settings(self, db: Any, tenant_id: UUID) -> Any:
        del db
        # Return an object with a timezone attribute defaulting to UTC
        _settings = type("_ReminderSettings", (), {"timezone": "UTC"})()
        return _settings


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
        return old_password == "correct-password"


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
        ttl_seconds=300,
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
        username="cliente.demo",
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
        tenant_service=cast(TenantService, tenant_service),
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
            db=cast(AsyncSession, object()),  # Needs db to trigger tenant lookup
        )
        assert "desactivada" in reply and "Máster de TrackPal" in reply

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
            db=cast(AsyncSession, object()),
        )
        # The service returns MAIN_MENU for empty message
        assert "administración" in reply or "Administracion" in reply

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
            db=cast(AsyncSession, object()),
        )
        assert "Sesión cerrada" in reply and "consola de administración" in reply

    async def test_facade_top_level_zero_closes_evolution_session(
        self,
        facade: WhatsAppTenantConsoleFacade,
    ) -> None:
        """Top-level '0' returns goodbye. Evolution close is handled by n8n."""
        identity = _tenant_identity(role="tenant")
        reply = await facade.process_message(
            phone="+10000000000",
            message="0",
            identity=identity,
            instance="tenant-instance",
            db=cast(AsyncSession, object()),
        )

        assert "Sesión cerrada" in reply and "consola de administración" in reply

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
            db=cast(AsyncSession, object()),
        )
        # Should return goodbye without menu (n8n closes session)
        assert "Has salido de la consola" in reply or "You have exited" in reply

    async def test_facade_top_level_zero_returns_goodbye_message(
        self,
        facade: WhatsAppTenantConsoleFacade,
    ) -> None:
        """Top-level '0' returns closed-session goodbye message."""
        identity = _tenant_identity(role="tenant")
        reply = await facade.process_message(
            phone="+10000000000",
            message="0",
            identity=identity,
            db=cast(AsyncSession, object()),
        )
        lowered = reply.lower()
        assert "sesión cerrada" in lowered


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
        assert "administración" in reply or "Administracion" in reply

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
        assert "administración" in reply or "Administracion" in reply

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
        assert "Mi perfil" in reply

        # Session should be persisted with flow=profile, step=action
        session = await session_service.get_session("admin:+10000000000")
        assert session is not None
        assert session.flow == "profile"
        assert session.step == "action"

    async def test_service_help(
        self, console_service: WhatsAppTenantConsoleService
    ) -> None:
        """'ayuda' returns HELP_TEXT."""
        reply = await console_service.process_message(
            phone="+10000000000",
            message="ayuda",
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
            db=AsyncMock(),
            session_service=session_service,
        )
        reply_filter = await console_service.process_message(
            phone="+10000000000",
            message="1",
            tenant_id=tenant_id,
            db=AsyncMock(),
            session_service=session_service,
        )
        assert "Filtrar por estado" in reply_filter

        reply_list = await console_service.process_message(
            phone="+10000000000",
            message="1",
            tenant_id=tenant_id,
            db=AsyncMock(),
            session_service=session_service,
        )
        assert "Lista" in reply_list or "Suscripciones" in reply_list

        reply_detail = await console_service.process_message(
            phone="+10000000000",
            message="1",
            tenant_id=tenant_id,
            db=AsyncMock(),
            session_service=session_service,
        )
        assert "Detalle de suscripción" in reply_detail
        assert "secret123" in reply_detail
        assert "1234" in reply_detail

    async def test_service_subscriptions_list_paginates_and_keeps_selection_map(
        self,
        console_service: WhatsAppTenantConsoleService,
        session_service: WhatsAppSessionService,
        subscription_service: FakeSubscriptionService,
    ) -> None:
        tenant_id = subscription_service.tenant_id
        subscription_service._subscriptions = {}
        subscriptions = [
            FakeSubscriptionObj(
                tenant_id=tenant_id,
                streaming_email=f"cliente-page-{index}@test.com",
            )
            for index in range(1, 9)
        ]
        for subscription in subscriptions:
            subscription_service._subscriptions[str(subscription.id)] = subscription

        for step in ["4", "1"]:
            await console_service.process_message(
                phone="+10000000000",
                message=step,
                tenant_id=tenant_id,
                db=AsyncMock(),
                session_service=session_service,
            )

        reply_page_1 = await console_service.process_message(
            phone="+10000000000",
            message="1",
            tenant_id=tenant_id,
            db=AsyncMock(),
            session_service=session_service,
        )
        session = await session_service.get_session("admin:+10000000000")
        assert session is not None
        assert set(session.selection_map) == {"1", "2", "3", "4", "5", "6", "7"}
        assert session.selection_map["7"] == str(subscriptions[6].id)
        assert "cliente-page-7@test.com" in reply_page_1
        assert "cliente-page-8@test.com" not in reply_page_1
        assert "0️⃣ Cancelar" in reply_page_1
        assert "8️⃣ Siguiente" in reply_page_1
        assert "8️⃣ Siguiente" in reply_page_1
        assert "9️⃣ Anterior" not in reply_page_1

        reply_page_2 = await console_service.process_message(
            phone="+10000000000",
            message="8",
            tenant_id=tenant_id,
            db=AsyncMock(),
            session_service=session_service,
        )
        session = await session_service.get_session("admin:+10000000000")
        assert session is not None
        assert session.selection_map == {"1": str(subscriptions[7].id)}
        assert "cliente-page-8@test.com" in reply_page_2
        assert "cliente-page-7@test.com" not in reply_page_2
        assert "9️⃣ Regresar" in reply_page_2
        assert "8️⃣ Siguiente" not in reply_page_2

        reply_detail = await console_service.process_message(
            phone="+10000000000",
            message="1",
            tenant_id=tenant_id,
            db=AsyncMock(),
            session_service=session_service,
        )
        assert "Detalle de suscripción" in reply_detail
        assert "cliente-page-8@test.com" in reply_detail

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
            db=AsyncMock(),
            session_service=session_service,
        )
        steps = [
            "2",
            "1",
            "1",
            "1",
            "nuevo@test.com",
            "clave123",
            "clave123",
            "1",
            "Perfil Kids",
            "7788",
            "7788",
            "1",
            "CONFIRMAR",
        ]
        reply = ""
        for step in steps:
            reply = await console_service.process_message(
                phone="+10000000000",
                message=step,
                tenant_id=tenant_id,
                db=AsyncMock(),
                session_service=session_service,
            )
        assert "Suscripción creada exitosamente" in reply
        assert len(subscription_service._subscriptions) == 2

    async def test_service_subscriptions_create_plan_back_navigation(
        self,
        console_service: WhatsAppTenantConsoleService,
        session_service: WhatsAppSessionService,
        subscription_service: FakeSubscriptionService,
    ) -> None:
        """9 at plan selection goes back to service selection."""
        tenant_id = subscription_service.tenant_id
        await console_service.process_message(
            phone="+10000000000",
            message="4",
            tenant_id=tenant_id,
            db=AsyncMock(),
            session_service=session_service,
        )
        # Start create flow
        await console_service.process_message(
            phone="+10000000000",
            message="2",
            tenant_id=tenant_id,
            db=AsyncMock(),
            session_service=session_service,
        )
        # Select client
        await console_service.process_message(
            phone="+10000000000",
            message="1",
            tenant_id=tenant_id,
            db=AsyncMock(),
            session_service=session_service,
        )
        # Select service -> arrives at plan list
        reply = await console_service.process_message(
            phone="+10000000000",
            message="1",
            tenant_id=tenant_id,
            db=AsyncMock(),
            session_service=session_service,
        )
        # Verify we're at plan selection
        assert "Selecciona el *plan*" in reply
        assert "9" in reply or "Regresar" in reply or "Back" in reply

        # Send 9 to go back
        reply = await console_service.process_message(
            phone="+10000000000",
            message="9",
            tenant_id=tenant_id,
            db=AsyncMock(),
            session_service=session_service,
        )
        # Verify back to service selection
        assert "Selecciona el *servicio*" in reply
        session = await session_service.get_session("admin:+10000000000")
        assert session is not None
        assert session.step == "create_service"
        assert "service_id" not in session.temp_data

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
                db=AsyncMock(),
                session_service=session_service,
            )
        assert "Suscripción actualizada exitosamente" in reply
        assert (
            subscription_service.default_subscription.streaming_email
            == "editado@test.com"
        )

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
                db=AsyncMock(),
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
                db=AsyncMock(),
                session_service=session_service,
            )
        assert "Suscripción renovada exitosamente" in reply

        subscription_service.default_subscription.status = "cancelled"
        for step in ["4", "1", "3", "1", "4", "1", "CONFIRMAR"]:
            reply = await console_service.process_message(
                phone="+10000000000",
                message=step,
                tenant_id=tenant_id,
                db=AsyncMock(),
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
        assert "salido" in reply.lower() or "goodbye" in reply.lower()

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
        assert (
            "cancelada" in reply.lower()
            or "Consola de administración" in reply
            or "salido de la consola" in reply.lower()
        )

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
        assert "Has salido de la consola" in reply or "You have exited" in reply

        # Session should be cleared
        fetched = await session_service.get_session("admin:+10000000000")
        assert fetched is None

    @pytest.mark.parametrize(
        "cmd", ["menu", "/menu", "MENU", "/MENU", "/Menu", "cancelar"]
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
        assert "cancelada" in reply.lower() or "Consola de administración" in reply

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
        assert "administración" in reply or "Administracion" in reply

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
            username="testclient",
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
            db=AsyncMock(),  # db needed for list_clients
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
            db=AsyncMock(),
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
        assert (
            "cancelada" in reply.lower()
            or "Consola de administración" in reply
            or "salido de la consola" in reply.lower()
        )
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
            db=AsyncMock(),
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
            db=AsyncMock(),
        )

        assert "El nombre de usuario ya existe" in reply
        assert "username_already_registered" not in reply


# ===================================================================
# Post-action prompt tests
# ===================================================================


@pytest.mark.asyncio
class TestPostActionPrompt:
    """Post-action decision prompt appears after terminal CRUD operations."""

    async def test_client_create_success_includes_post_action_prompt(
        self,
        console_service: WhatsAppTenantConsoleService,
    ) -> None:
        """Successful client creation includes post-action prompt."""
        session = SimpleNamespace(
            temp_data={
                "full_name": "Cliente Test",
                "local_username": "clientetest",
                "phone": "+12015550099",
                "password": "secret123",
            },
            step=console_service.CLIENTS_STEP_CREATE_CONFIRM,
        )

        created_client = SimpleNamespace(
            full_name="Cliente Test",
            username="eq3wn_clientetest",
            phone="+12015550099",
        )

        async def _create(*args: Any, **kwargs: Any) -> SimpleNamespace:
            return created_client

        console_service._client_service.create_client = _create  # type: ignore[assignment]

        reply = await console_service._handle_client_create_confirm(
            phone="+10000000000",
            msg="CONFIRMAR",
            session=session,
            session_service=None,
            tenant_id=uuid4(),
            db=AsyncMock(),
        )

        assert "Cliente Test" in reply
        assert "Cerrar sesión" in reply or "0️⃣" in reply
        assert "Realizar otra operación" in reply or "menu principal" in reply

    async def test_subscription_cancel_success_includes_post_action_prompt(
        self,
        console_service: WhatsAppTenantConsoleService,
    ) -> None:
        """Successful subscription cancel includes post-action prompt."""
        session = SimpleNamespace(
            selected_tenant_id=str(uuid4()),
            temp_data={},
        )

        async def _cancel(*args: Any, **kwargs: Any) -> bool:
            return True

        console_service._subscription_service.cancel_subscription = _cancel  # type: ignore[assignment]

        reply = await console_service._handle_subscriptions_cancel_confirm(
            phone="+10000000000",
            msg="CONFIRMAR",
            session=session,
            session_service=None,
            tenant_id=uuid4(),
            db=AsyncMock(),
        )

        assert "cancelada" in reply.lower() or "cancelled" in reply.lower()
        assert "Cerrar sesión" in reply or "0️⃣" in reply


# ===================================================================
# UserFacingError translation tests
# ===================================================================


@pytest.mark.asyncio
class TestUserFacingErrorTranslation:
    """UserFacingError codes are translated, not leaked as raw codes."""

    async def test_profile_edit_phone_duplicate_translated(
        self,
        console_service: WhatsAppTenantConsoleService,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Profile phone duplicate returns translated text, not raw code."""
        session = SimpleNamespace(
            temp_data={"field": "phone"},
        )

        async def _raise(*args: Any, **kwargs: Any) -> None:
            raise UserFacingError("profile_phone_registered")

        console_service._profile_service.update_profile = _raise  # type: ignore[assignment]

        async def _fake_get(db: Any, user_id: UUID) -> SimpleNamespace:
            return SimpleNamespace(id=user_id, role="tenant")

        import app.repositories.users_repository as users_repo

        monkeypatch.setattr(users_repo, "get", _fake_get)

        reply = await console_service._handle_profile_edit_value(
            phone="+10000000000",
            msg="+12015550099",
            session=session,
            session_service=None,
            user_id=uuid4(),
            db=AsyncMock(),
        )

        assert "El teléfono ya está registrado" in reply
        assert "profile_phone_registered" not in reply

    async def test_catalog_service_name_duplicate_translated(
        self,
        console_service: WhatsAppTenantConsoleService,
    ) -> None:
        """Catalog service name duplicate returns translated text, not raw code."""
        session = SimpleNamespace(
            temp_data={"service_id": str(uuid4())},
        )

        async def _raise(*args: Any, **kwargs: Any) -> None:
            raise UserFacingError("service_name_already_exists")

        console_service._catalog_service.update_service = _raise  # type: ignore[assignment]

        reply = await console_service._handle_catalog_edit_service(
            phone="+10000000000",
            msg="Netflix",
            session=session,
            session_service=None,
            tenant_id=uuid4(),
            db=AsyncMock(),
        )

        assert "El nombre del servicio ya existe" in reply
        assert "service_name_already_exists" not in reply

    async def test_catalog_plan_name_duplicate_translated(
        self,
        console_service: WhatsAppTenantConsoleService,
    ) -> None:
        """Catalog plan name duplicate returns translated text, not raw code."""
        session = SimpleNamespace(
            temp_data={"service_id": str(uuid4()), "plan_id": str(uuid4())},
        )

        async def _raise(*args: Any, **kwargs: Any) -> None:
            raise UserFacingError("plan_name_already_exists")

        console_service._catalog_service.update_plan = _raise  # type: ignore[assignment]

        reply = await console_service._handle_catalog_edit_plan(
            phone="+10000000000",
            msg="Premium",
            session=session,
            session_service=None,
            tenant_id=uuid4(),
            db=AsyncMock(),
        )

        assert "El nombre del plan ya existe" in reply
        assert "plan_name_already_exists" not in reply

    async def test_subscription_create_client_not_found_translated(
        self,
        console_service: WhatsAppTenantConsoleService,
    ) -> None:
        """Subscription create client-not-found returns translated text, not raw code."""
        session = SimpleNamespace(
            temp_data={
                "client_id": str(uuid4()),
                "service_id": str(uuid4()),
                "plan_id": str(uuid4()),
                "streaming_email": "test@test.com",
                "streaming_password": "pass123",
                "profile_name": "Perfil",
                "profile_pin": "1234",
                "duration_type": "1_month",
                "starts_at": "2026-06-01T00:00:00",
                "expires_at": None,
            },
            selected_tenant_id=str(uuid4()),
        )

        async def _raise(*args: Any, **kwargs: Any) -> None:
            raise UserFacingError("subscription_client_not_found")

        console_service._subscription_service.create_subscription = _raise  # type: ignore[assignment]

        reply = await console_service._handle_subscriptions_create_confirm(
            phone="+10000000000",
            msg="CONFIRMAR",
            session=session,
            session_service=None,
            tenant_id=uuid4(),
            db=AsyncMock(),
        )

        assert "Cliente no encontrado" in reply
        assert "subscription_client_not_found" not in reply


# ===================================================================
# Codigo flow tests
# ===================================================================


@pytest.mark.asyncio
class TestCodigoFlow:
    """Tests for the "codigo" lookup flow (service + target email)."""

    async def test_codigo_start_shows_service_list(
        self,
        console_service: WhatsAppTenantConsoleService,
    ) -> None:
        """Starting codigo flow shows list of available services."""
        from unittest.mock import AsyncMock, patch

        mock_session_service = AsyncMock()
        mock_session = AsyncMock()
        mock_session.flow = ""
        mock_session.step = ""
        mock_session.temp_data = {}
        mock_session_service.get_session.return_value = None
        mock_session_service.create_session.return_value = mock_session

        # Mock the effective keys repository to return all supported services
        with (
            patch(
                "app.services.whatsapp_tenant_console_service.codigo_flow"
                ".code_services_repository.get_effective_service_keys",
                new_callable=AsyncMock,
                return_value=[
                    "disney",
                    "hbo_max",
                    "netflix",
                    "prime_video",
                    "spotify",
                    "universal_plus",
                ],
            ),
            patch(
                "app.services.whatsapp_tenant_console_service.codigo_flow"
                ".mailbox_config_repository.get_by_tenant",
                new_callable=AsyncMock,
                return_value=AsyncMock(status="connected"),
            ),
        ):
            result = await console_service._start_codigo_flow(
                phone="+10000000000",
                session_service=mock_session_service,
                tenant_id="00000000-0000-0000-0000-000000000001",
                db=AsyncMock(),
                started_from_menu=False,
                role="tenant",
            )
        assert result is not None
        assert "Netflix" in result or "netflix" in result.lower()
        assert "Cancelar" in result

    async def test_codigo_trigger_words_in_process_message(
        self,
        console_service: WhatsAppTenantConsoleService,
    ) -> None:
        """Trigger words codigo/codigo/code start the codigo flow."""
        from unittest.mock import AsyncMock

        mock_session_service = AsyncMock()
        mock_session = AsyncMock()
        mock_session.flow = ""
        mock_session.step = ""
        mock_session.temp_data = {}
        mock_session_service.get_session.return_value = None
        mock_session_service.create_session.return_value = mock_session

        for trigger in ("codigo", "codigo", "code"):
            reply = await console_service.process_message(
                phone="+10000000000",
                message=trigger,
                session_service=mock_session_service,
                locale="es",
            )
            assert reply is not None
            # Should not return fallback or menu help
            assert "No entendí" not in reply

    async def test_codigo_cancel_direct_does_not_render_main_menu(
        self,
        console_service: WhatsAppTenantConsoleService,
    ) -> None:
        """Direct command flow cancel returns cancelled text only."""
        from unittest.mock import AsyncMock

        mock_session_service = AsyncMock()
        mock_session = AsyncMock()
        mock_session.temp_data = {
            "codigo_started_from_menu": "false",
            "codigo_effective_keys": [
                "disney",
                "hbo_max",
                "netflix",
                "prime_video",
                "spotify",
                "universal_plus",
            ],
        }
        mock_session.flow = console_service.CODIGO_FLOW
        mock_session.step = console_service.CODIGO_STEP_SERVICE

        reply = await console_service._handle_codigo_service(
            phone="+10000000000",
            msg="0",
            session=mock_session,
            session_service=mock_session_service,
            tenant_id=None,
            db=None,
        )

        assert "Operación cancelada" in reply
        assert "TrackPal Consola" not in reply

    async def test_codigo_flow_service_1_selected(
        self,
        console_service: WhatsAppTenantConsoleService,
    ) -> None:
        """Selecting service 1 asks for email (Disney+ is index 1 after alphabetical reorder)."""
        from unittest.mock import AsyncMock

        mock_session_service = AsyncMock()
        mock_session = AsyncMock()
        mock_session.temp_data = {
            "codigo_effective_keys": [
                "disney",
                "hbo_max",
                "netflix",
                "prime_video",
                "spotify",
                "universal_plus",
            ]
        }
        mock_session.flow = console_service.CODIGO_FLOW
        mock_session.step = console_service.CODIGO_STEP_SERVICE
        mock_session_service.get_session.return_value = mock_session

        reply = await console_service._handle_codigo_service(
            phone="+10000000000",
            msg="1",
            session=mock_session,
            session_service=mock_session_service,
            tenant_id=None,
            db=None,
        )
        assert reply is not None
        assert "Disney" in reply or "email" in reply.lower()

    async def test_codigo_flow_invalid_service(
        self,
        console_service: WhatsAppTenantConsoleService,
    ) -> None:
        """Invalid service selection returns error."""
        from unittest.mock import AsyncMock

        mock_session_service = AsyncMock()
        mock_session = AsyncMock()
        mock_session.temp_data = {
            "codigo_effective_keys": [
                "disney",
                "hbo_max",
                "netflix",
                "prime_video",
                "spotify",
                "universal_plus",
            ]
        }
        mock_session.flow = console_service.CODIGO_FLOW
        mock_session.step = console_service.CODIGO_STEP_SERVICE

        reply = await console_service._handle_codigo_service(
            phone="+10000000000",
            msg="99",
            session=mock_session,
            session_service=mock_session_service,
            tenant_id=None,
            db=None,
        )
        assert "inválido" in reply.lower() or "invalid" in reply.lower()

    async def test_codigo_flow_cancel(
        self,
        console_service: WhatsAppTenantConsoleService,
    ) -> None:
        """Cancel (0) returns to main menu."""
        from unittest.mock import AsyncMock

        mock_session_service = AsyncMock()
        mock_session = AsyncMock()
        mock_session.temp_data = {}
        mock_session.flow = console_service.CODIGO_FLOW
        mock_session.step = console_service.CODIGO_STEP_SERVICE

        reply = await console_service._handle_codigo_service(
            phone="+10000000000",
            msg="0",
            session=mock_session,
            session_service=mock_session_service,
            tenant_id=None,
            db=None,
        )
        assert (
            "cancelada" in reply.lower()
            or "cancelled" in reply.lower()
            or "menu" in reply
            or "menu" in reply
        )

    async def test_codigo_email_empty(
        self,
        console_service: WhatsAppTenantConsoleService,
    ) -> None:
        """Empty/invalid email returns error."""
        from unittest.mock import AsyncMock

        mock_session_service = AsyncMock()
        mock_session = AsyncMock()
        mock_session.temp_data = {"service_key": "netflix"}
        mock_session.flow = console_service.CODIGO_FLOW
        mock_session.step = console_service.CODIGO_STEP_EMAIL

        reply = await console_service._handle_codigo_email(
            phone="+10000000000",
            msg="ab",
            session=mock_session,
            session_service=mock_session_service,
            tenant_id=None,
            db=None,
        )
        assert "inválido" in reply.lower() or "invalid" in reply.lower()

    async def test_codigo_service_keys_alphabetical_order(
        self,
        console_service: WhatsAppTenantConsoleService,
    ) -> None:
        """STREAMING_SERVICE_KEYS must be alphabetical by visible label."""
        from app.services.whatsapp_tenant_console_service.codigo_flow import (
            _CODIGO_SERVICE_LABELS,
        )

        keys = console_service.STREAMING_SERVICE_KEYS
        labels = [_CODIGO_SERVICE_LABELS.get(k, k) for k in keys]
        assert labels == sorted(labels), f"Service labels not alphabetical: {labels}"

    async def test_codigo_index_to_service_key_mapping(
        self,
        console_service: WhatsAppTenantConsoleService,
    ) -> None:
        """Index 1..N maps to correct service_key (alphabetical)."""
        from unittest.mock import AsyncMock

        expected_keys = [
            "disney",  # 1
            "hbo_max",  # 2
            "netflix",  # 3
            "prime_video",  # 4
            "spotify",  # 5
            "universal_plus",  # 6
        ]
        keys = console_service.STREAMING_SERVICE_KEYS
        assert keys == expected_keys

        # Verify selection for each index resolves correct service_key
        for i, expected_key in enumerate(expected_keys, start=1):
            mock_session_service = AsyncMock()
            mock_session = AsyncMock()
            mock_session.temp_data = {"codigo_effective_keys": expected_keys}
            mock_session.flow = console_service.CODIGO_FLOW
            mock_session.step = console_service.CODIGO_STEP_SERVICE
            mock_session_service.get_session.return_value = mock_session

            await console_service._handle_codigo_service(
                phone="+10000000000",
                msg=str(i),
                session=mock_session,
                session_service=mock_session_service,
                tenant_id=None,
                db=None,
            )
            assert mock_session.temp_data["service_key"] == expected_key, (
                f"Index {i} mapped to {mock_session.temp_data['service_key']}, "
                f"expected {expected_key}"
            )


@pytest.mark.asyncio
class TestConsoleHandlersCodigoScope:
    """Verify WhatsApp console handlers return codigo poll scope reliably.

    The handler now orchestrates job creation after the flow returns,
    using session intent data (``pending_lookup_intent``) instead of
    a pre-set ``pending_job_id``.  The job is created durably (committed)
    before the response includes ``lookup_job_id`` + ``tenant_id``.

    Tests cover the tenant handler directly with mocked auth + repos,
    proving the response contract is satisfied.
    """

    async def _seed_codigo_intent_session(
        self, fake_redis, tenant_uuid, intent_data=None
    ):
        """Seed a session with pending_lookup_intent for codigo flow."""
        data = intent_data or {
            "pending_lookup_intent": "true",
            "service_key": "netflix",
            "target_email": "user@example.com",
        }
        session = ConversationSession(
            phone="admin:+12015550002",
            temp_data=data,
        )
        await fake_redis.set(
            "session:admin:+12015550002",
            session.model_dump_json(),
        )

    async def test_tenant_handler_returns_lookup_job_id_with_tenant_scope(
        self,
    ) -> None:
        """When codigo flow stores intent, handler creates job and returns both fields."""
        from app.api.v1.endpoints.integrations.console_handlers import (
            _handle_tenant_console,
        )

        mock_db = AsyncMock()
        fake_redis = FakeRedis()
        tenant_uuid = uuid4()

        # Seed session with intent
        await self._seed_codigo_intent_session(fake_redis, tenant_uuid)
        manager = cast(RedisConnectionManager, FakeManager(fake_redis=fake_redis))

        fake_tenant = SimpleNamespace(id=tenant_uuid, is_active=True)
        fake_mailbox = SimpleNamespace(id=uuid4(), status="connected")
        fake_job = SimpleNamespace(id=uuid4())

        with (
            patch(
                "app.api.v1.endpoints.integrations.console_handlers.auth_service.identify_by_phone",
                AsyncMock(
                    return_value={
                        "user_id": str(uuid4()),
                        "role": "tenant",
                        "username": "testadmin",
                    }
                ),
            ),
            patch(
                "app.api.v1.endpoints.integrations.console_handlers.tenants_repository.get_by_owner",
                AsyncMock(return_value=fake_tenant),
            ),
            patch(
                "app.api.v1.endpoints.integrations.console_handlers.mailbox_config_repository.get_by_tenant",
                AsyncMock(return_value=fake_mailbox),
            ),
            patch(
                "app.api.v1.endpoints.integrations.console_handlers.mailbox_lookup_repository.create_job",
                AsyncMock(return_value=fake_job),
            ),
            patch(
                "app.api.v1.endpoints.integrations.console_handlers.get_lookup_execution_coordinator",
                return_value=AsyncMock(),
            ),
            patch.object(
                WhatsAppTenantConsoleFacade,
                "process_message",
                AsyncMock(return_value="\U0001f50d Buscando c\u00f3digo\u2026"),
            ),
        ):
            result = await _handle_tenant_console(
                phone="+12015550002",
                message="cliente@test.com",
                instance=None,
                manager=manager,
                db=mock_db,
            )

        assert isinstance(result, WhatsAppConsoleResponse)
        assert result.reply == "\U0001f50d Buscando c\u00f3digo\u2026"
        assert result.lookup_job_id == str(fake_job.id)
        assert result.tenant_id == str(tenant_uuid)
        assert result.status is None

        # Verify db.flush() and db.commit() were called for durability
        mock_db.flush.assert_awaited_once()
        mock_db.commit.assert_awaited_once()

        # Verify JSON serialization includes both fields
        serialized = result.model_dump(mode="json")
        assert serialized.get("lookup_job_id") == str(fake_job.id)
        assert serialized.get("tenant_id") == str(tenant_uuid)
        assert serialized.get("reply") == "\U0001f50d Buscando c\u00f3digo\u2026"

    async def test_tenant_handler_no_scope_when_no_intent(
        self,
    ) -> None:
        """Without pending_lookup_intent, neither field appears in response."""
        from app.api.v1.endpoints.integrations.console_handlers import (
            _handle_tenant_console,
        )

        mock_db = AsyncMock()
        fake_redis = FakeRedis()
        manager = cast(RedisConnectionManager, FakeManager(fake_redis=fake_redis))

        with (
            patch(
                "app.api.v1.endpoints.integrations.console_handlers.auth_service.identify_by_phone",
                AsyncMock(
                    return_value={
                        "user_id": str(uuid4()),
                        "role": "tenant",
                        "username": "testadmin",
                    }
                ),
            ),
            patch.object(
                WhatsAppTenantConsoleFacade,
                "process_message",
                AsyncMock(return_value="\U0001f4cb Men\u00fa principal"),
            ),
        ):
            result = await _handle_tenant_console(
                phone="+12015550002",
                message="menu",
                instance=None,
                manager=manager,
                db=mock_db,
            )

        assert isinstance(result, WhatsAppConsoleResponse)
        assert result.reply == "\U0001f4cb Men\u00fa principal"
        assert result.lookup_job_id is None
        assert result.tenant_id is None

        # Verify no db operations were attempted (no intent)
        mock_db.flush.assert_not_called()
        mock_db.commit.assert_not_called()

        serialized = result.model_dump(mode="json")
        assert "lookup_job_id" not in serialized
        assert "tenant_id" not in serialized

    async def test_tenant_handler_returns_scope_when_schedule_fails(
        self,
    ) -> None:
        """A committed job remains pollable when immediate scheduling fails."""
        from app.api.v1.endpoints.integrations.console_handlers import (
            _handle_tenant_console,
        )

        mock_db = AsyncMock()
        fake_redis = FakeRedis()
        tenant_uuid = uuid4()
        await self._seed_codigo_intent_session(fake_redis, tenant_uuid)
        manager = cast(RedisConnectionManager, FakeManager(fake_redis=fake_redis))
        fake_tenant = SimpleNamespace(id=tenant_uuid, is_active=True)
        fake_mailbox = SimpleNamespace(id=uuid4(), status="connected")
        fake_job = SimpleNamespace(id=uuid4())
        coordinator = AsyncMock()
        coordinator.schedule.side_effect = RuntimeError("Redis unavailable")

        with (
            patch(
                "app.api.v1.endpoints.integrations.console_handlers.auth_service.identify_by_phone",
                AsyncMock(
                    return_value={
                        "user_id": str(uuid4()),
                        "role": "tenant",
                        "username": "testadmin",
                    }
                ),
            ),
            patch(
                "app.api.v1.endpoints.integrations.console_handlers.tenants_repository.get_by_owner",
                AsyncMock(return_value=fake_tenant),
            ),
            patch(
                "app.api.v1.endpoints.integrations.console_handlers.mailbox_config_repository.get_by_tenant",
                AsyncMock(return_value=fake_mailbox),
            ),
            patch(
                "app.api.v1.endpoints.integrations.console_handlers.mailbox_lookup_repository.create_job",
                AsyncMock(return_value=fake_job),
            ),
            patch(
                "app.api.v1.endpoints.integrations.console_handlers.get_lookup_execution_coordinator",
                return_value=coordinator,
            ),
            patch.object(
                WhatsAppTenantConsoleFacade,
                "process_message",
                AsyncMock(return_value="🔍 Buscando código…"),
            ),
        ):
            result = await _handle_tenant_console(
                phone="+12015550002",
                message="cliente@test.com",
                instance=None,
                manager=manager,
                db=mock_db,
            )

        assert result.lookup_job_id == str(fake_job.id)
        assert result.tenant_id == str(tenant_uuid)
        coordinator.schedule.assert_awaited_once_with(fake_job.id)
        mock_db.delete.assert_not_awaited()

    async def test_tenant_handler_no_scope_when_mailbox_not_connected(
        self,
    ) -> None:
        """When mailbox is not connected, handler does NOT return lookup_job_id."""
        from app.api.v1.endpoints.integrations.console_handlers import (
            _handle_tenant_console,
        )

        mock_db = AsyncMock()
        fake_redis = FakeRedis()
        tenant_uuid = uuid4()

        await self._seed_codigo_intent_session(fake_redis, tenant_uuid)
        manager = cast(RedisConnectionManager, FakeManager(fake_redis=fake_redis))

        fake_tenant = SimpleNamespace(id=tenant_uuid, is_active=True)
        fake_mailbox = SimpleNamespace(id=uuid4(), status="disconnected")

        with (
            patch(
                "app.api.v1.endpoints.integrations.console_handlers.auth_service.identify_by_phone",
                AsyncMock(
                    return_value={
                        "user_id": str(uuid4()),
                        "role": "tenant",
                        "username": "testadmin",
                    }
                ),
            ),
            patch(
                "app.api.v1.endpoints.integrations.console_handlers.tenants_repository.get_by_owner",
                AsyncMock(return_value=fake_tenant),
            ),
            patch(
                "app.api.v1.endpoints.integrations.console_handlers.mailbox_config_repository.get_by_tenant",
                AsyncMock(return_value=fake_mailbox),
            ),
            patch.object(
                WhatsAppTenantConsoleFacade,
                "process_message",
                AsyncMock(return_value="\U0001f50d Buscando c\u00f3digo\u2026"),
            ),
        ):
            result = await _handle_tenant_console(
                phone="+12015550002",
                message="cliente@test.com",
                instance=None,
                manager=manager,
                db=mock_db,
            )

        assert isinstance(result, WhatsAppConsoleResponse)
        assert "Error" in result.reply or "error" in result.reply.lower()
        assert result.lookup_job_id is None
        assert result.tenant_id is None
        saved = await fake_redis.get("session:admin:+12015550002")
        assert saved is not None
        saved_session = ConversationSession.model_validate_json(saved)
        assert saved_session.temp_data.get("pending_lookup_intent") == "true"
        # No job was created — no db operations
        mock_db.flush.assert_not_called()
        mock_db.commit.assert_not_called()

    async def test_codigo_flow_no_direct_persistence(
        self,
        console_service: WhatsAppTenantConsoleService,
    ) -> None:
        """_handle_codigo_email now goes to email_confirm, not awaiting_result."""
        from unittest.mock import AsyncMock

        mock_session_service = AsyncMock()
        mock_session = AsyncMock()
        mock_session.temp_data = {
            "service_key": "netflix",
            "service_label": "Netflix",
        }
        mock_session.flow = console_service.CODIGO_FLOW
        mock_session.step = console_service.CODIGO_STEP_EMAIL
        mock_session_service.get_session.return_value = mock_session

        result = await console_service._handle_codigo_email(
            phone="+10000000000",
            msg="User@Example.COM",
            session=mock_session,
            session_service=mock_session_service,
            tenant_id=uuid4(),
            db=None,
        )

        # Should return email confirm prompt, not buscando directly
        assert result is not None
        assert "confirm" in result.lower() or "confirmar" in result.lower()
        assert "user@example.com" in result

        # Should now be in EMAIL_CONFIRM step, not awaiting_result
        assert mock_session.step == console_service.CODIGO_STEP_EMAIL_CONFIRM

        # Should store normalized email
        assert mock_session.temp_data.get("target_email") == "user@example.com"
        assert mock_session.temp_data.get("service_key") == "netflix"

        # Should NOT have set pending_lookup_intent (that's now in confirm step)
        assert "pending_lookup_intent" not in mock_session.temp_data
        assert "lookup_job_id" not in mock_session.temp_data

        mock_session_service.save_session.assert_awaited_once_with(mock_session)

    async def test_codigo_email_valid_moves_to_email_confirm(
        self,
        console_service: WhatsAppTenantConsoleService,
    ) -> None:
        from unittest.mock import AsyncMock

        mock_session_service = AsyncMock()
        mock_session = AsyncMock()
        mock_session.temp_data = {
            "service_key": "netflix",
            "service_label": "Netflix",
        }
        mock_session.flow = console_service.CODIGO_FLOW
        mock_session.step = console_service.CODIGO_STEP_EMAIL

        reply = await console_service._handle_codigo_email(
            phone="+10000000000",
            msg="User@Example.COM",
            session=mock_session,
            session_service=mock_session_service,
            tenant_id=uuid4(),
            db=AsyncMock(),
        )

        assert "confirm" in reply.lower() or "confirmar" in reply.lower()
        assert "user@example.com" in reply
        assert mock_session.step == console_service.CODIGO_STEP_EMAIL_CONFIRM
        assert mock_session.temp_data["target_email"] == "user@example.com"
        assert "pending_lookup_intent" not in mock_session.temp_data
        mock_session_service.save_session.assert_awaited_once_with(mock_session)

    async def test_codigo_email_confirm_yes_sets_pending_lookup_intent(
        self,
        console_service: WhatsAppTenantConsoleService,
    ) -> None:
        from unittest.mock import AsyncMock

        mock_session_service = AsyncMock()
        mock_session = AsyncMock()
        mock_session.temp_data = {
            "service_key": "netflix",
            "service_label": "Netflix",
            "target_email": "user@example.com",
        }
        mock_session.flow = console_service.CODIGO_FLOW
        mock_session.step = console_service.CODIGO_STEP_EMAIL_CONFIRM

        reply = await console_service._handle_codigo_email_confirm(
            phone="+10000000000",
            msg="1",
            session=mock_session,
            session_service=mock_session_service,
            tenant_id=uuid4(),
            db=AsyncMock(),
        )

        assert "buscando" in reply.lower() or "searching" in reply.lower()
        assert mock_session.step == console_service.CODIGO_STEP_AWAITING_RESULT
        assert mock_session.temp_data["pending_lookup_intent"] == "true"

    async def test_codigo_email_confirm_text_cancel_is_invalid_option(
        self,
        console_service: WhatsAppTenantConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        session = await session_service.create_session("admin:+10000000000")
        session.flow = console_service.CODIGO_FLOW
        session.step = console_service.CODIGO_STEP_EMAIL_CONFIRM
        session.temp_data = {
            "service_key": "netflix",
            "service_label": "Netflix",
            "target_email": "user@example.com",
            "codigo_effective_keys": ["netflix"],
            "codigo_current_page": 0,
        }
        await session_service.save_session(session)

        reply = await console_service.process_message(
            phone="+10000000000",
            message="cancelar",
            tenant_id=uuid4(),
            db=AsyncMock(),
            session_service=session_service,
        )

        assert "inválida" in reply.lower() or "invalid" in reply.lower()
        saved = await session_service.get_session("admin:+10000000000")
        assert saved is not None
        assert saved.step == console_service.CODIGO_STEP_EMAIL_CONFIRM

    async def test_codigo_awaiting_result_retry_allows_pending_job(
        self,
        console_service: WhatsAppTenantConsoleService,
    ) -> None:
        from types import SimpleNamespace
        from unittest.mock import AsyncMock, patch

        mock_session_service = AsyncMock()
        mock_session = SimpleNamespace(
            temp_data={
                "lookup_job_id": str(uuid4()),
                "service_key": "netflix",
                "target_email": "user@example.com",
            }
        )

        with patch(
            "app.services.whatsapp_tenant_console_service.codigo_flow.mailbox_lookup_repository.get_job",
            AsyncMock(return_value=SimpleNamespace(status="pending")),
        ):
            reply = await console_service._handle_codigo_awaiting_result(
                phone="+10000000000",
                msg="1",
                session=mock_session,
                session_service=mock_session_service,
                tenant_id=uuid4(),
                db=AsyncMock(),
            )

        assert "buscando" in reply.lower() or "searching" in reply.lower()
        assert mock_session.temp_data["pending_lookup_intent"] == "true"
        mock_session_service.save_session.assert_awaited_once_with(mock_session)

    async def test_codigo_awaiting_result_back_reopens_services_even_if_job_pending(
        self,
        console_service: WhatsAppTenantConsoleService,
    ) -> None:
        from types import SimpleNamespace
        from unittest.mock import AsyncMock, patch

        tenant_id = uuid4()
        mock_session_service = AsyncMock()
        mock_session = SimpleNamespace(temp_data={"lookup_job_id": str(uuid4())})
        new_session = SimpleNamespace(flow=None, step=None, temp_data={})
        mock_session_service.create_session.return_value = new_session

        with (
            patch(
                "app.services.whatsapp_tenant_console_service.codigo_flow.mailbox_lookup_repository.get_job",
                AsyncMock(return_value=SimpleNamespace(status="pending")),
            ),
            patch(
                "app.services.whatsapp_tenant_console_service.codigo_flow.code_services_repository.get_effective_service_keys",
                AsyncMock(return_value=["netflix"]),
            ),
        ):
            reply = await console_service._handle_codigo_awaiting_result(
                phone="+10000000000",
                msg="2",
                session=mock_session,
                session_service=mock_session_service,
                tenant_id=tenant_id,
                db=AsyncMock(),
            )

        assert "Netflix" in reply
        assert new_session.flow == console_service.CODIGO_FLOW
        assert new_session.step == console_service.CODIGO_STEP_SERVICE

    async def test_codigo_awaiting_result_trigger_restarts_flow_and_cancels_active_job(
        self,
        console_service: WhatsAppTenantConsoleService,
    ) -> None:
        from types import SimpleNamespace
        from unittest.mock import AsyncMock, patch

        mock_db = AsyncMock()
        tenant_id = uuid4()
        lookup_job_id = uuid4()
        mock_session_service = AsyncMock()
        mock_session = SimpleNamespace(
            temp_data={
                "lookup_job_id": str(lookup_job_id),
                "service_key": "netflix",
                "target_email": "user@example.com",
            }
        )
        restart_reply = "📩 Buscar código\n\n[1] Netflix\n\n0️⃣ Cancelar"

        with (
            patch(
                "app.services.whatsapp_tenant_console_service.codigo_flow.mailbox_lookup_repository.cancel_active_job_if_present",
                AsyncMock(return_value=True),
            ) as cancel_job,
            patch.object(
                console_service,
                "_start_codigo_flow",
                AsyncMock(return_value=restart_reply),
            ) as start_flow,
        ):
            reply = await console_service._handle_codigo_awaiting_result(
                phone="+10000000000",
                msg=" code ",
                session=mock_session,
                session_service=mock_session_service,
                tenant_id=tenant_id,
                db=mock_db,
            )

        assert reply == restart_reply
        cancel_job.assert_awaited_once_with(
            mock_db,
            lookup_job_id,
            tenant_id=tenant_id,
        )
        mock_db.commit.assert_awaited_once()
        mock_session_service.clear_session.assert_awaited_once_with(
            "admin:+10000000000"
        )
        start_flow.assert_awaited_once_with(
            "+10000000000",
            mock_session_service,
            tenant_id,
            mock_db,
            started_from_menu=False,
            role="tenant",
        )

    async def test_codigo_awaiting_result_trigger_restarts_when_cancel_helper_noops(
        self,
        console_service: WhatsAppTenantConsoleService,
    ) -> None:
        from types import SimpleNamespace
        from unittest.mock import AsyncMock, patch

        mock_db = AsyncMock()
        tenant_id = uuid4()
        lookup_job_id = uuid4()
        mock_session_service = AsyncMock()
        mock_session = SimpleNamespace(temp_data={"lookup_job_id": str(lookup_job_id)})
        restart_reply = "📩 Buscar código\n\n[1] Netflix\n\n0️⃣ Cancelar"

        with (
            patch(
                "app.services.whatsapp_tenant_console_service.codigo_flow.mailbox_lookup_repository.cancel_active_job_if_present",
                AsyncMock(return_value=False),
            ) as cancel_job,
            patch.object(
                console_service,
                "_start_codigo_flow",
                AsyncMock(return_value=restart_reply),
            ) as start_flow,
        ):
            reply = await console_service._handle_codigo_awaiting_result(
                phone="+10000000000",
                msg="código",
                session=mock_session,
                session_service=mock_session_service,
                tenant_id=tenant_id,
                db=mock_db,
            )

        assert reply == restart_reply
        cancel_job.assert_awaited_once_with(
            mock_db,
            lookup_job_id,
            tenant_id=tenant_id,
        )
        mock_db.commit.assert_not_awaited()
        start_flow.assert_awaited_once()

    async def test_codigo_awaiting_result_trigger_restarts_with_invalid_lookup_job_id(
        self,
        console_service: WhatsAppTenantConsoleService,
    ) -> None:
        from types import SimpleNamespace
        from unittest.mock import AsyncMock, patch

        mock_db = AsyncMock()
        tenant_id = uuid4()
        mock_session_service = AsyncMock()
        mock_session = SimpleNamespace(temp_data={"lookup_job_id": "not-a-uuid"})
        restart_reply = "📩 Buscar código\n\n[1] Netflix\n\n0️⃣ Cancelar"

        with (
            patch(
                "app.services.whatsapp_tenant_console_service.codigo_flow.mailbox_lookup_repository.cancel_active_job_if_present",
                AsyncMock(),
            ) as cancel_job,
            patch.object(
                console_service,
                "_start_codigo_flow",
                AsyncMock(return_value=restart_reply),
            ) as start_flow,
        ):
            reply = await console_service._handle_codigo_awaiting_result(
                phone="+10000000000",
                msg="codigo",
                session=mock_session,
                session_service=mock_session_service,
                tenant_id=tenant_id,
                db=mock_db,
            )

        assert reply == restart_reply
        cancel_job.assert_not_called()
        mock_db.commit.assert_not_awaited()
        start_flow.assert_awaited_once()

    async def test_codigo_awaiting_result_non_trigger_still_returns_still_checking(
        self,
        console_service: WhatsAppTenantConsoleService,
    ) -> None:
        from types import SimpleNamespace
        from unittest.mock import AsyncMock

        mock_session_service = AsyncMock()
        mock_session = SimpleNamespace(temp_data={})

        reply = await console_service._handle_codigo_awaiting_result(
            phone="+10000000000",
            msg="hola",
            session=mock_session,
            session_service=mock_session_service,
            tenant_id=uuid4(),
            db=AsyncMock(),
        )

        assert "todavía buscando" in reply.lower() or "still" in reply.lower()


# ===================================================================
# Bug 02 — Navigation contract: 9=back, 0=exit
# ===================================================================


@pytest.mark.asyncio
class TestNavigationContract:
    """Verify that 9=back and 0=exit semantics hold across consoles."""

    async def test_eight_goes_to_next_page_in_subscription_list(
        self,
        console_service: WhatsAppTenantConsoleService,
        session_service: WhatsAppSessionService,
        subscription_service: FakeSubscriptionService,
    ) -> None:
        """'8' in subscription list triggers next-page, not global exit."""
        tenant_id = subscription_service.tenant_id
        subscription_service._subscriptions = {}
        subs = [
            FakeSubscriptionObj(
                tenant_id=tenant_id,
                streaming_email=f"nav-test-{i}@test.com",
            )
            for i in range(1, 9)
        ]
        for s in subs:
            subscription_service._subscriptions[str(s.id)] = s

        # Navigate to subscription list
        for step in ["4", "1", "1"]:
            await console_service.process_message(
                phone="+10000000000",
                message=step,
                tenant_id=tenant_id,
                db=AsyncMock(),
                session_service=session_service,
            )

        # Send 8 → should go to page 2, NOT exit
        reply = await console_service.process_message(
            phone="+10000000000",
            message="8",
            tenant_id=tenant_id,
            db=AsyncMock(),
            session_service=session_service,
        )
        # Page 2 shows sub 8 only
        assert "nav-test-8@test.com" in reply
        assert "nav-test-7@test.com" not in reply
        # Session should still exist (not cleared by exit)
        session = await session_service.get_session("admin:+10000000000")
        assert session is not None

    async def test_zero_exits_from_active_flow(
        self,
        console_service: WhatsAppTenantConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        """'0' with active flow exits the console."""
        session = await session_service.create_session("admin:+10000000000")
        session.flow = "clients"
        session.step = "list"
        await session_service.save_session(session)

        reply = await console_service.process_message(
            phone="+10000000000",
            message="0",
            session_service=session_service,
        )
        # Should show goodbye, not just cancel
        assert "salido" in reply.lower() or "goodbye" in reply.lower()
        # Session should be cleared
        fetched = await session_service.get_session("admin:+10000000000")
        assert fetched is None

    async def test_zero_exits_from_main_menu(
        self,
        console_service: WhatsAppTenantConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        """'0' from main menu exits."""
        reply = await console_service.process_message(
            phone="+10000000000",
            message="0",
            session_service=session_service,
        )
        assert "salido" in reply.lower() or "goodbye" in reply.lower()

    async def test_nine_from_main_menu_shows_fallback(
        self,
        console_service: WhatsAppTenantConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        """'9' from main menu (no active flow) shows fallback, not menu."""
        reply = await console_service.process_message(
            phone="+10000000000",
            message="9",
            session_service=session_service,
        )
        # 9 no longer triggers global reset; should show fallback
        assert "No entendí" in reply
        assert "Clientes" not in reply


# ===================================================================
# Blocked Clients — Tenant Console
# ===================================================================


@pytest.mark.asyncio
class TestBlockedClients:
    """Block list/unblock from the Tenant console clients menu (option 3)."""

    async def test_clients_menu_no_longer_shows_blocks_option(
        self,
        console_service: WhatsAppTenantConsoleService,
    ) -> None:
        """Clients menu no longer includes blocks option (moved to Access Control)."""
        reply = await console_service.process_message(
            phone="+10000000000",
            message="1",
        )
        assert "Bloqueos de mensajes" not in reply and "Message blocks" not in reply
        assert "Ver clientes" in reply or "View clients" in reply

    async def test_block_list_empty(
        self,
        console_service: WhatsAppTenantConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        """Access control list with no active blocks shows empty message."""
        tenant_id = uuid4()
        with patch("app.repositories.blocked_clients_repository") as mock_repo:
            mock_repo.list_active = AsyncMock(return_value=[])

            # Start access control flow (option 5 in pro menu)
            reply = await console_service.process_message(
                phone="+10000000001",
                message="5",
                session_service=session_service,
                tenant_id=tenant_id,
            )
            assert "Control" in reply or "acceso" in reply

            # Press 1 (list blocked identities)
            reply = await console_service.process_message(
                phone="+10000000001",
                message="1",
                session_service=session_service,
                tenant_id=tenant_id,
                db=AsyncMock(),
            )
            assert "No hay bloqueos" in reply or "No active message blocks" in reply

    async def test_block_list_shows_blocks(
        self,
        console_service: WhatsAppTenantConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        """Access control list with active blocks shows numbered list."""
        tenant_id = uuid4()
        block_id = uuid4()

        fake_block = SimpleNamespace(
            id=block_id,
            tenant_id=tenant_id,
            phone="12015559999",
            whatsapp_lid=None,
            is_active=True,
        )

        with patch("app.repositories.blocked_clients_repository") as mock_repo:
            mock_repo.list_active = AsyncMock(return_value=[fake_block])

            # Start access control flow (option 5 in pro menu)
            reply = await console_service.process_message(
                phone="+10000000002",
                message="5",
                session_service=session_service,
                tenant_id=tenant_id,
            )
            assert "Control" in reply or "acceso" in reply

            # Press 1 (list blocked identities)
            reply = await console_service.process_message(
                phone="+10000000002",
                message="1",
                session_service=session_service,
                tenant_id=tenant_id,
                db=AsyncMock(),
            )
            assert "12015559999" in reply
            assert "Bloqueos" in reply or "blocks" in reply.lower()
            assert "1" in reply

            # Session should advance to block_list step
            session = await session_service.get_session("admin:+10000000002")
            assert session is not None
            assert session.step == "block_list"
            assert session.selection_map.get("1") == str(block_id)

    async def test_block_unblock_success(
        self,
        console_service: WhatsAppTenantConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        """Selecting a block from the list unblocks the identity."""
        tenant_id = uuid4()
        block_id = uuid4()

        fake_block = SimpleNamespace(
            id=block_id,
            tenant_id=tenant_id,
            phone="12015559999",
            whatsapp_lid=None,
            is_active=True,
        )

        with patch("app.repositories.blocked_clients_repository") as mock_repo:
            mock_repo.list_active = AsyncMock(return_value=[fake_block])
            mock_repo.unblock = AsyncMock(return_value=fake_block)

            # Start access control flow & show blocks
            await console_service.process_message(
                phone="+10000000003",
                message="5",
                session_service=session_service,
                tenant_id=tenant_id,
            )
            await console_service.process_message(
                phone="+10000000003",
                message="1",
                session_service=session_service,
                tenant_id=tenant_id,
                db=AsyncMock(),
            )

            # Press 1 to unblock the first identity
            mock_db = AsyncMock()
            reply = await console_service.process_message(
                phone="+10000000003",
                message="1",
                session_service=session_service,
                tenant_id=tenant_id,
                db=mock_db,
            )
            assert "12015559999" in reply
            assert "eliminado" in reply or "removed" in reply.lower()

            # Session should be cleared
            session = await session_service.get_session("admin:+10000000003")
            assert session is None

            # Verify unblock was called with correct args
            mock_repo.unblock.assert_called_once()
            call_args = mock_repo.unblock.call_args[0]
            assert call_args[1] == tenant_id  # db, tenant_id, block_id
            assert call_args[2] == block_id

            # Regression: the unblock path must commit the session so the
            # block deactivation is not rolled back at request end.
            mock_db.commit.assert_awaited()

    async def test_block_list_invalid_selection(
        self,
        console_service: WhatsAppTenantConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        """Invalid selection in block list shows error."""
        tenant_id = uuid4()
        block_id = uuid4()

        fake_block = SimpleNamespace(
            id=block_id,
            tenant_id=tenant_id,
            phone="12015559999",
            whatsapp_lid=None,
            is_active=True,
        )

        with patch("app.repositories.blocked_clients_repository") as mock_repo:
            mock_repo.list_active = AsyncMock(return_value=[fake_block])

            # Start clients flow & show blocks
            await console_service.process_message(
                phone="+10000000004",
                message="1",
                session_service=session_service,
                tenant_id=tenant_id,
            )
            await console_service.process_message(
                phone="+10000000004",
                message="3",
                session_service=session_service,
                tenant_id=tenant_id,
                db=AsyncMock(),
            )

            # Press 99 (invalid number)
            reply = await console_service.process_message(
                phone="+10000000004",
                message="99",
                session_service=session_service,
                tenant_id=tenant_id,
                db=AsyncMock(),
            )
            assert "inválido" in reply.lower() or "invalid" in reply.lower()

    async def test_block_list_zero_goes_back(
        self,
        console_service: WhatsAppTenantConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        """Pressing 0 from block list goes back to clients menu."""
        tenant_id = uuid4()
        block_id = uuid4()

        fake_block = SimpleNamespace(
            id=block_id,
            tenant_id=tenant_id,
            phone="12015559999",
            whatsapp_lid=None,
            is_active=True,
        )

        with patch("app.repositories.blocked_clients_repository") as mock_repo:
            mock_repo.list_active = AsyncMock(return_value=[fake_block])

            # Start clients flow & show blocks
            await console_service.process_message(
                phone="+10000000005",
                message="1",
                session_service=session_service,
                tenant_id=tenant_id,
            )
            await console_service.process_message(
                phone="+10000000005",
                message="3",
                session_service=session_service,
                tenant_id=tenant_id,
                db=AsyncMock(),
            )

            # Press 0 to go back to clients menu
            reply = await console_service.process_message(
                phone="+10000000005",
                message="0",
                session_service=session_service,
                tenant_id=tenant_id,
                db=AsyncMock(),
            )
            # 0 from within a flow exits (global handler)
            assert "salido" in reply.lower() or "goodbye" in reply.lower()

    async def test_clients_menu_nine_goes_back(
        self,
        console_service: WhatsAppTenantConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        """Pressing 9 from clients menu goes back to main menu."""
        # Start clients flow
        reply = await console_service.process_message(
            phone="+10000000006",
            message="1",
            session_service=session_service,
        )
        assert "Clientes" in reply or "Clients" in reply

        # Press 9 to go back to main menu
        reply = await console_service.process_message(
            phone="+10000000006",
            message="9",
            session_service=session_service,
        )
        # Should show main menu
        assert "consola de administración" in reply.lower() or "Admin Console" in reply

        # Session should be cleared
        session = await session_service.get_session("admin:+10000000006")
        assert session is None

    async def test_clients_menu_zero_from_list_is_not_back(
        self,
        console_service: WhatsAppTenantConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        """0 from clients menu exits (not back)."""
        # Start clients flow
        await console_service.process_message(
            phone="+10000000007",
            message="1",
            session_service=session_service,
        )

        # Press 0 - should exit, not go back
        reply = await console_service.process_message(
            phone="+10000000007",
            message="0",
            session_service=session_service,
        )
        assert "salido" in reply.lower() or "goodbye" in reply.lower()

        # Session should be cleared
        session = await session_service.get_session("admin:+10000000007")
        assert session is None


# Additional catalog flow test class to append

# ===================================================================
# Catalog flow tests
# ===================================================================


@pytest.mark.asyncio
class TestCatalogFlow:
    """Catalog menu, service list pagination, create/edit, detail, post-success."""

    async def test_catalog_starts_with_main_catalog_menu(
        self,
        console_service: WhatsAppTenantConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        """Press 2 from main menu starts catalog flow with menu options."""
        reply = await console_service.process_message(
            phone="+10000000000",
            message="2",
            tenant_id=uuid4(),
            db=cast(AsyncSession, object()),
            session_service=session_service,
        )
        assert "📦" in reply
        assert "Ver servicios" in reply
        assert "Crear servicio" in reply
        assert "Eliminar servicio" in reply
        session = await session_service.get_session("admin:+10000000000")
        assert session is not None
        assert session.flow == "catalog"
        assert session.step == "menu"

    async def test_catalog_empty_menu_only_offers_create(
        self,
        console_service: WhatsAppTenantConsoleService,
        catalog_service: FakeCatalogService,
        session_service: WhatsAppSessionService,
    ) -> None:
        """Empty catalog menu only shows create option."""
        catalog_service._services.clear()
        reply = await console_service.process_message(
            phone="+10000000000",
            message="2",
            tenant_id=uuid4(),
            db=cast(AsyncSession, object()),
            session_service=session_service,
        )
        assert "No hay servicios" in reply
        assert "Crear servicio" in reply
        assert "Eliminar servicio" not in reply

    async def test_catalog_service_list_is_alphabetical_paginated_and_has_counts(
        self,
        console_service: WhatsAppTenantConsoleService,
        catalog_service: FakeCatalogService,
        session_service: WhatsAppSessionService,
    ) -> None:
        """Service list shows alphabetical paginated list with plan/subscription counts."""
        catalog_service._services.clear()
        for name in [
            "Zulu",
            "Alpha",
            "Beta",
            "Gamma",
            "Delta",
            "Epsilon",
            "Eta",
            "Theta",
        ]:
            service = FakeServiceObj(
                name=name, plan_count=1, active_subscription_count=2
            )
            catalog_service._services[str(service.id)] = service
        await console_service.process_message(
            "+10000000000",
            "2",
            tenant_id=uuid4(),
            db=cast(AsyncSession, object()),
            session_service=session_service,
        )
        reply = await console_service.process_message(
            "+10000000000",
            "1",
            tenant_id=uuid4(),
            db=cast(AsyncSession, object()),
            session_service=session_service,
        )
        assert "1️⃣ Alpha - 1 plan - 2 suscripciones activas" in reply
        assert "5️⃣ Eta" in reply
        assert "8️⃣ Siguiente" in reply
        assert "Zulu" not in reply

    async def test_catalog_service_detail_hides_id_and_exposes_required_actions(
        self,
        console_service: WhatsAppTenantConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        """Service detail hides ID and shows create/delete plan actions."""
        tenant_id = uuid4()
        await console_service.process_message(
            "+10000000000",
            "2",
            tenant_id=tenant_id,
            db=cast(AsyncSession, object()),
            session_service=session_service,
        )
        await console_service.process_message(
            "+10000000000",
            "1",
            tenant_id=tenant_id,
            db=cast(AsyncSession, object()),
            session_service=session_service,
        )
        reply = await console_service.process_message(
            "+10000000000",
            "1",
            tenant_id=tenant_id,
            db=cast(AsyncSession, object()),
            session_service=session_service,
        )
        assert "*ID:*" not in reply
        assert "Editar nombre" in reply
        assert "Ver planes" in reply
        assert "Crear plan" in reply
        assert "Eliminar plan" in reply
        assert "Eliminar servicio" not in reply

    async def test_catalog_create_service_direct_success_and_duplicate_retry(
        self,
        console_service: WhatsAppTenantConsoleService,
        catalog_service: FakeCatalogService,
        session_service: WhatsAppSessionService,
    ) -> None:
        """Create service flow: duplicate stays on step, success shows post-action."""
        tenant_id = uuid4()
        await console_service.process_message(
            "+10000000000",
            "2",
            tenant_id=tenant_id,
            db=cast(AsyncSession, object()),
            session_service=session_service,
        )
        prompt = await console_service.process_message(
            "+10000000000",
            "2",
            tenant_id=tenant_id,
            db=cast(AsyncSession, object()),
            session_service=session_service,
        )
        assert "nombre" in prompt.lower()
        duplicate = await console_service.process_message(
            "+10000000000",
            "Netflix",
            tenant_id=tenant_id,
            db=cast(AsyncSession, object()),
            session_service=session_service,
        )
        assert "nombre del servicio ya existe" in duplicate
        session = await session_service.get_session("admin:+10000000000")
        assert session is not None
        assert session.step == "create_service_name"
        success = await console_service.process_message(
            "+10000000000",
            "Disney",
            tenant_id=tenant_id,
            db=cast(AsyncSession, object()),
            session_service=session_service,
        )
        assert "Servicio" in success and "creado" in success
        assert "1️⃣ Volver al menú principal" in success

    async def test_catalog_edit_service_success_uses_post_action(
        self,
        console_service: WhatsAppTenantConsoleService,
        catalog_service: FakeCatalogService,
        session_service: WhatsAppSessionService,
    ) -> None:
        """Successful service edit transitions to POST_ACTION step with prompt, no ID shown."""
        tenant_id = uuid4()
        service = next(iter(catalog_service._services.values()))
        session = await session_service.create_session("admin:+10000000000")
        session.flow = "catalog"
        session.step = "edit_service"
        session.temp_data = {"service_id": str(service.id)}
        await session_service.save_session(session)

        reply = await console_service._handle_catalog_edit_service(
            phone="+10000000000",
            msg="Netflix Renamed",
            session=session,
            session_service=session_service,
            tenant_id=tenant_id,
            db=AsyncMock(),
        )

        # Success message present
        assert "Nombre del servicio" in reply
        assert "actualizado" in reply
        # Post-action prompt appended
        assert "1️⃣ Volver al menú principal" in reply
        # No ID exposed
        assert "*ID:*" not in reply
        # Session is in POST_ACTION step
        updated = await session_service.get_session("admin:+10000000000")
        assert updated is not None
        assert updated.step == "post_action"
        assert updated.flow == "catalog"

    async def test_catalog_edit_plan_success_uses_post_action(
        self,
        console_service: WhatsAppTenantConsoleService,
        catalog_service: FakeCatalogService,
        session_service: WhatsAppSessionService,
    ) -> None:
        """Successful plan edit transitions to POST_ACTION step with prompt, no ID shown."""
        tenant_id = uuid4()
        service = next(iter(catalog_service._services.values()))
        plan = FakePlanObj(service_id=service.id, name="Premium")
        catalog_service._plans[str(plan.id)] = plan
        session = await session_service.create_session("admin:+10000000000")
        session.flow = "catalog"
        session.step = "edit_plan"
        session.temp_data = {"service_id": str(service.id), "plan_id": str(plan.id)}
        await session_service.save_session(session)

        reply = await console_service._handle_catalog_edit_plan(
            phone="+10000000000",
            msg="Premium Plus",
            session=session,
            session_service=session_service,
            tenant_id=tenant_id,
            db=AsyncMock(),
        )

        # Success message present
        assert "Nombre del plan" in reply
        assert "actualizado" in reply
        # Post-action prompt appended
        assert "1️⃣ Volver al menú principal" in reply
        # No ID exposed
        assert "*ID:*" not in reply
        # Session is in POST_ACTION step
        updated = await session_service.get_session("admin:+10000000000")
        assert updated is not None
        assert updated.step == "post_action"
        assert updated.flow == "catalog"

    async def test_catalog_edit_service_missing_id_returns_failure(
        self,
        console_service: WhatsAppTenantConsoleService,
    ) -> None:
        """Edit service without service_id in temp_data returns failure message."""
        session = SimpleNamespace(temp_data={})
        reply = await console_service._handle_catalog_edit_service(
            phone="+10000000000",
            msg="New Name",
            session=session,
            session_service=None,
            tenant_id=uuid4(),
            db=AsyncMock(),
        )
        assert "No se pudo actualizar el servicio" in reply

    async def test_catalog_edit_plan_missing_id_returns_failure(
        self,
        console_service: WhatsAppTenantConsoleService,
    ) -> None:
        """Edit plan without plan_id in temp_data returns failure message."""
        session = SimpleNamespace(temp_data={"service_id": str(uuid4())})
        reply = await console_service._handle_catalog_edit_plan(
            phone="+10000000000",
            msg="New Name",
            session=session,
            session_service=None,
            tenant_id=uuid4(),
            db=AsyncMock(),
        )
        assert "No se pudo actualizar el plan" in reply

    async def test_delete_service_warning_requires_confirm_and_summarizes_cascade(
        self,
        console_service: WhatsAppTenantConsoleService,
        catalog_service: FakeCatalogService,
        session_service: WhatsAppSessionService,
    ) -> None:
        """Verify delete service warning, invalid confirm retry, and successful confirm."""
        tenant_id = uuid4()
        service = next(iter(catalog_service._services.values()))
        service.plan_count = 3
        service.active_subscription_count = 1
        await console_service.process_message(
            "+10000000000",
            "2",
            tenant_id=tenant_id,
            db=cast(AsyncSession, object()),
            session_service=session_service,
        )
        await console_service.process_message(
            "+10000000000",
            "3",
            tenant_id=tenant_id,
            db=cast(AsyncSession, object()),
            session_service=session_service,
        )
        warning = await console_service.process_message(
            "+10000000000",
            "1",
            tenant_id=tenant_id,
            db=cast(AsyncSession, object()),
            session_service=session_service,
        )
        assert "eliminar servicio" in warning.lower()
        assert "3" in warning
        assert "planes" in warning
        assert "suscripciones" in warning
        assert (
            "active@example.com - Cliente Demo - 584241234567 - Netflix/Premium"
            in warning
        )
        assert "CONFIRMAR" in warning
        invalid = await console_service.process_message(
            "+10000000000",
            "si",
            tenant_id=tenant_id,
            db=cast(AsyncSession, object()),
            session_service=session_service,
        )
        assert "CONFIRMAR" in invalid
        success = await console_service.process_message(
            "+10000000000",
            "confirmar",
            tenant_id=tenant_id,
            db=cast(AsyncSession, object()),
            session_service=session_service,
        )
        assert "Servicio" in success and "eliminado" in success
        assert "3 planes" in success
        assert "2 suscripciones" in success

    async def test_delete_plan_no_plans_returns_to_catalog_menu(
        self,
        console_service: WhatsAppTenantConsoleService,
        catalog_service: FakeCatalogService,
        session_service: WhatsAppSessionService,
    ) -> None:
        """Trying to delete a plan when service has none returns to catalog menu."""
        tenant_id = uuid4()
        catalog_service._plans.clear()
        await console_service.process_message(
            "+10000000000",
            "2",
            tenant_id=tenant_id,
            db=cast(AsyncSession, object()),
            session_service=session_service,
        )
        await console_service.process_message(
            "+10000000000",
            "1",
            tenant_id=tenant_id,
            db=cast(AsyncSession, object()),
            session_service=session_service,
        )
        await console_service.process_message(
            "+10000000000",
            "1",
            tenant_id=tenant_id,
            db=cast(AsyncSession, object()),
            session_service=session_service,
        )
        reply = await console_service.process_message(
            "+10000000000",
            "4",
            tenant_id=tenant_id,
            db=cast(AsyncSession, object()),
            session_service=session_service,
        )
        assert "no tiene planes" in reply.lower()
        assert "Cat" in reply or "catalog" in reply.lower()

    async def test_delete_plan_warning_and_confirm(
        self,
        console_service: WhatsAppTenantConsoleService,
        catalog_service: FakeCatalogService,
        session_service: WhatsAppSessionService,
    ) -> None:
        """Verify delete plan warning with subscription shows confirm prompt."""
        tenant_id = uuid4()
        service = next(iter(catalog_service._services.values()))
        plan = FakePlanObj(
            service_id=service.id, name="Premium", active_subscription_count=1
        )
        catalog_service._plans[str(plan.id)] = plan
        await console_service.process_message(
            "+10000000000",
            "2",
            tenant_id=tenant_id,
            db=cast(AsyncSession, object()),
            session_service=session_service,
        )
        await console_service.process_message(
            "+10000000000",
            "1",
            tenant_id=tenant_id,
            db=cast(AsyncSession, object()),
            session_service=session_service,
        )
        await console_service.process_message(
            "+10000000000",
            "1",
            tenant_id=tenant_id,
            db=cast(AsyncSession, object()),
            session_service=session_service,
        )
        await console_service.process_message(
            "+10000000000",
            "4",
            tenant_id=tenant_id,
            db=cast(AsyncSession, object()),
            session_service=session_service,
        )
        warning = await console_service.process_message(
            "+10000000000",
            "1",
            tenant_id=tenant_id,
            db=cast(AsyncSession, object()),
            session_service=session_service,
        )
        assert "eliminar plan" in warning.lower()
        assert "Premium" in warning
        success = await console_service.process_message(
            "+10000000000",
            "CONFIRM",
            tenant_id=tenant_id,
            db=cast(AsyncSession, object()),
            session_service=session_service,
        )
        assert "Plan" in success and "eliminado" in success

    async def test_catalog_plan_list_paginates_and_shows_counts(
        self,
        console_service: WhatsAppTenantConsoleService,
        catalog_service: FakeCatalogService,
        session_service: WhatsAppSessionService,
    ) -> None:
        """Plan list for a service paginates at CATALOG_PAGE_SIZE, 8=next, 9=back."""
        tenant_id = uuid4()
        service = next(iter(catalog_service._services.values()))
        catalog_service._plans.clear()
        plan_names = [f"Plan {chr(65 + i)}" for i in range(9)]  # 9 plans → 2 pages
        for name in plan_names:
            plan = FakePlanObj(
                service_id=service.id, name=name, active_subscription_count=1
            )
            catalog_service._plans[str(plan.id)] = plan

        # Navigate: Main menu → Catalog → Service 1 → Service detail → Option 2 (View plans)
        await console_service.process_message(
            "+10000000000",
            "2",
            tenant_id=tenant_id,
            db=cast(AsyncSession, object()),
            session_service=session_service,
        )
        await console_service.process_message(
            "+10000000000",
            "1",
            tenant_id=tenant_id,
            db=cast(AsyncSession, object()),
            session_service=session_service,
        )
        await console_service.process_message(
            "+10000000000",
            "1",
            tenant_id=tenant_id,
            db=cast(AsyncSession, object()),
            session_service=session_service,
        )
        reply = await console_service.process_message(
            "+10000000000",
            "2",
            tenant_id=tenant_id,
            db=cast(AsyncSession, object()),
            session_service=session_service,
        )

        # Page 1: first 7 plans only
        assert "1️⃣ Plan A - Precio a consultar - 1 suscripción activa" in reply
        assert "7️⃣ Plan G - Precio a consultar - 1 suscripción activa" in reply
        assert "Plan H" not in reply
        assert "8️⃣ Siguiente" in reply

        session = await session_service.get_session("admin:+10000000000")
        assert session is not None
        assert session.step == "plan_select"
        assert session.selection_map["7"] == str(
            next(p.id for p in catalog_service._plans.values() if p.name == "Plan G")
        )

        # 8 → page 2
        reply = await console_service.process_message(
            "+10000000000",
            "8",
            tenant_id=tenant_id,
            db=cast(AsyncSession, object()),
            session_service=session_service,
        )
        assert "1️⃣ Plan H - Precio a consultar - 1 suscripción activa" in reply
        assert "2️⃣ Plan I - Precio a consultar - 1 suscripción activa" in reply
        assert "Plan A" not in reply
        # No "Next" on last page
        assert "8️⃣ Siguiente" not in reply

        # 9 → back to service detail
        reply = await console_service.process_message(
            "+10000000000",
            "9",
            tenant_id=tenant_id,
            db=cast(AsyncSession, object()),
            session_service=session_service,
        )
        assert "Servicio" in reply
        assert "Ver planes" in reply or "Acciones" in reply

    async def test_delete_service_warning_uses_i18n_confirm_prompt(
        self,
        console_service: WhatsAppTenantConsoleService,
        catalog_service: FakeCatalogService,
        session_service: WhatsAppSessionService,
    ) -> None:
        """Delete service warning uses i18n key — EN locale does not contain hardcoded ES text."""
        tenant_id = uuid4()
        service = next(iter(catalog_service._services.values()))
        service.plan_count = 2
        service.active_subscription_count = 1

        # Navigate to delete service list
        await console_service.process_message(
            "+10000000000",
            "2",
            tenant_id=tenant_id,
            db=cast(AsyncSession, object()),
            session_service=session_service,
        )
        await console_service.process_message(
            "+10000000000",
            "3",
            tenant_id=tenant_id,
            db=cast(AsyncSession, object()),
            session_service=session_service,
        )

        # Get warning with English locale
        warning = await console_service.process_message(
            "+10000000000",
            "1",
            tenant_id=tenant_id,
            db=cast(AsyncSession, object()),
            session_service=session_service,
            locale="en",
        )

        # Should NOT contain Spanish hardcoded text (confirm prompt AND warning body)
        assert "Escribe *CONFIRMAR* para eliminar" not in warning
        # Should NOT contain hardcoded Spanish warning body
        assert "El servicio" not in warning
        # Should contain the English confirm prompt from i18n
        assert "Type *CONFIRM* or *CONFIRMAR*" in warning

    async def test_delete_service_warning_body_localizes_to_english(
        self,
        console_service: WhatsAppTenantConsoleService,
        catalog_service: FakeCatalogService,
        session_service: WhatsAppSessionService,
    ) -> None:
        """Delete service warning body uses i18n — EN locale has English body text, not hardcoded ES."""
        tenant_id = uuid4()
        service = next(iter(catalog_service._services.values()))
        service.plan_count = 2
        service.active_subscription_count = 1

        # Navigate to delete service list
        await console_service.process_message(
            "+10000000000",
            "2",
            tenant_id=tenant_id,
            db=cast(AsyncSession, object()),
            session_service=session_service,
        )
        await console_service.process_message(
            "+10000000000",
            "3",
            tenant_id=tenant_id,
            db=cast(AsyncSession, object()),
            session_service=session_service,
        )

        # Get warning with English locale
        warning = await console_service.process_message(
            "+10000000000",
            "1",
            tenant_id=tenant_id,
            db=cast(AsyncSession, object()),
            session_service=session_service,
            locale="en",
        )

        # Should contain English body text (not hardcoded Spanish)
        assert "Service *" in warning
        assert "has" in warning
        assert "Active subscriptions:" in warning
        assert "Historical/inactive subscriptions:" in warning
        assert "Total affected:" in warning
        # Should NOT contain Spanish hardcoded strings
        assert "El servicio" not in warning
        assert "asociados" not in warning
        assert "Suscripciones activas:" not in warning

    async def test_delete_plan_warning_body_localizes_to_english(
        self,
        console_service: WhatsAppTenantConsoleService,
        catalog_service: FakeCatalogService,
        session_service: WhatsAppSessionService,
    ) -> None:
        """Delete plan warning body uses i18n — EN locale has English body text, not hardcoded ES."""
        tenant_id = uuid4()
        service = next(iter(catalog_service._services.values()))
        plan = FakePlanObj(
            service_id=service.id, name="Premium", active_subscription_count=1
        )
        catalog_service._plans[str(plan.id)] = plan
        service.plan_count = 1

        # Navigate: Main menu -> Catalog -> Service 1 -> Service detail -> Option 4 -> Plan 1
        await console_service.process_message(
            "+10000000000",
            "2",
            tenant_id=tenant_id,
            db=cast(AsyncSession, object()),
            session_service=session_service,
        )
        await console_service.process_message(
            "+10000000000",
            "1",
            tenant_id=tenant_id,
            db=cast(AsyncSession, object()),
            session_service=session_service,
        )
        await console_service.process_message(
            "+10000000000",
            "1",
            tenant_id=tenant_id,
            db=cast(AsyncSession, object()),
            session_service=session_service,
        )
        await console_service.process_message(
            "+10000000000",
            "4",
            tenant_id=tenant_id,
            db=cast(AsyncSession, object()),
            session_service=session_service,
        )
        # Get warning with English locale
        warning = await console_service.process_message(
            "+10000000000",
            "1",
            tenant_id=tenant_id,
            db=cast(AsyncSession, object()),
            session_service=session_service,
            locale="en",
        )

        # Should contain English body text (not hardcoded Spanish)
        assert "Plan *Premium* has" in warning
        assert "Active subscriptions:" in warning
        assert "Historical/inactive subscriptions:" in warning
        assert "Total affected:" in warning
        # Should NOT contain Spanish hardcoded strings
        assert "El plan" not in warning
        assert "suscripciones asociadas" not in warning

    async def test_catalog_page_is_stored_as_integer_and_next_page_works(
        self,
        console_service: WhatsAppTenantConsoleService,
        catalog_service: FakeCatalogService,
        session_service: WhatsAppSessionService,
    ) -> None:
        """catalog_page is stored as int; navigates to next page without type errors."""
        tenant_id = uuid4()
        # Populate many services to force pagination
        catalog_service._services.clear()
        for name in ["A", "B", "C", "D", "E", "F", "G", "H", "I"]:
            svc = FakeServiceObj(name=name, plan_count=1, active_subscription_count=0)
            catalog_service._services[str(svc.id)] = svc

        # Main menu -> Catalog
        await console_service.process_message(
            "+10000000000",
            "2",
            tenant_id=tenant_id,
            db=cast(AsyncSession, object()),
            session_service=session_service,
        )
        # Catalog -> View services (option 1)
        await console_service.process_message(
            "+10000000000",
            "1",
            tenant_id=tenant_id,
            db=cast(AsyncSession, object()),
            session_service=session_service,
        )

        session = await session_service.get_session("admin:+10000000000")
        assert session is not None
        # catalog_page should be int, not str
        assert isinstance(session.temp_data.get("catalog_page"), int), (
            "catalog_page should be int"
        )
        assert session.temp_data["catalog_page"] == 1

        # Navigate to next page with 8
        await console_service.process_message(
            "+10000000000",
            "8",
            tenant_id=tenant_id,
            db=cast(AsyncSession, object()),
            session_service=session_service,
        )
        session = await session_service.get_session("admin:+10000000000")
        assert session is not None
        assert isinstance(session.temp_data.get("catalog_page"), int), (
            "catalog_page should still be int after next"
        )
        assert session.temp_data["catalog_page"] == 2

    async def test_catalog_delete_plan_list_page_stored_as_int_and_next_works(
        self,
        console_service: WhatsAppTenantConsoleService,
        catalog_service: FakeCatalogService,
        session_service: WhatsAppSessionService,
    ) -> None:
        """catalog_page for delete plan list is stored as int; next-page navigation works."""
        tenant_id = uuid4()
        service = next(iter(catalog_service._services.values()))
        # Populate many plans to force pagination
        catalog_service._plans.clear()
        for name in [
            "Alpha",
            "Beta",
            "Gamma",
            "Delta",
            "Epsilon",
            "Zeta",
            "Eta",
            "Theta",
            "Iota",
        ]:
            plan = FakePlanObj(
                service_id=service.id, name=name, active_subscription_count=0
            )
            catalog_service._plans[str(plan.id)] = plan

        # Navigate: Main menu -> Catalog -> Service 1 -> Service detail -> Option 4 (Delete plan)
        await console_service.process_message(
            "+10000000000",
            "2",
            tenant_id=tenant_id,
            db=cast(AsyncSession, object()),
            session_service=session_service,
        )
        await console_service.process_message(
            "+10000000000",
            "1",
            tenant_id=tenant_id,
            db=cast(AsyncSession, object()),
            session_service=session_service,
        )
        await console_service.process_message(
            "+10000000000",
            "1",
            tenant_id=tenant_id,
            db=cast(AsyncSession, object()),
            session_service=session_service,
        )
        await console_service.process_message(
            "+10000000000",
            "4",
            tenant_id=tenant_id,
            db=cast(AsyncSession, object()),
            session_service=session_service,
        )

        session = await session_service.get_session("admin:+10000000000")
        assert session is not None
        assert isinstance(session.temp_data.get("catalog_page"), int), (
            "catalog_page should be int in delete plan list"
        )
        assert session.temp_data["catalog_page"] == 1

        # Navigate to next page with 8
        reply = await console_service.process_message(
            "+10000000000",
            "8",
            tenant_id=tenant_id,
            db=cast(AsyncSession, object()),
            session_service=session_service,
        )
        assert "Iota" in reply or "Theta" in reply  # should be on page 2
        session = await session_service.get_session("admin:+10000000000")
        assert session is not None
        assert isinstance(session.temp_data.get("catalog_page"), int), (
            "catalog_page should still be int after next in delete plan"
        )
        assert session.temp_data["catalog_page"] == 2

    async def test_paginated_service_list_after_refactor(
        self,
        console_service: WhatsAppTenantConsoleService,
        catalog_service: FakeCatalogService,
        session_service: WhatsAppSessionService,
    ) -> None:
        """_show_catalog_service_list refactored to use _paginate still works correctly."""
        tenant_id = uuid4()
        catalog_service._services.clear()
        for name in [
            "Alpha",
            "Bravo",
            "Charlie",
            "Delta",
            "Echo",
            "Foxtrot",
            "Golf",
            "Zulu",
        ]:
            svc = FakeServiceObj(name=name, plan_count=0, active_subscription_count=0)
            catalog_service._services[str(svc.id)] = svc

        # Main menu -> Catalog -> View services
        await console_service.process_message(
            "+10000000000",
            "2",
            tenant_id=tenant_id,
            db=cast(AsyncSession, object()),
            session_service=session_service,
        )
        reply = await console_service.process_message(
            "+10000000000",
            "1",
            tenant_id=tenant_id,
            db=cast(AsyncSession, object()),
            session_service=session_service,
        )

        # First 7 items on page 1, 8th item on next page
        assert "1\ufe0f\u20e3 Alpha" in reply
        assert "7\ufe0f\u20e3 Golf" in reply
        assert "Zulu" not in reply
        assert "8\ufe0f\u20e3 Siguiente" in reply

        # Go to page 2
        reply = await console_service.process_message(
            "+10000000000",
            "8",
            tenant_id=tenant_id,
            db=cast(AsyncSession, object()),
            session_service=session_service,
        )
        assert "1\ufe0f\u20e3 Zulu" in reply
        assert "8\ufe0f\u20e3 Siguiente" not in reply

    async def test_catalog_plan_select_next_page_after_refactor(
        self,
        console_service: WhatsAppTenantConsoleService,
        catalog_service: FakeCatalogService,
        session_service: WhatsAppSessionService,
    ) -> None:
        """_handle_catalog_plan_select next-page refactored to use _paginate still works correctly."""
        tenant_id = uuid4()
        service = next(iter(catalog_service._services.values()))
        catalog_service._plans.clear()
        plan_names = [f"P{chr(65 + i)}" for i in range(9)]
        for name in plan_names:
            plan = FakePlanObj(
                service_id=service.id, name=name, active_subscription_count=1
            )
            catalog_service._plans[str(plan.id)] = plan

        # Navigate to plan list
        await console_service.process_message(
            "+10000000000",
            "2",
            tenant_id=tenant_id,
            db=cast(AsyncSession, object()),
            session_service=session_service,
        )
        await console_service.process_message(
            "+10000000000",
            "1",
            tenant_id=tenant_id,
            db=cast(AsyncSession, object()),
            session_service=session_service,
        )
        await console_service.process_message(
            "+10000000000",
            "1",
            tenant_id=tenant_id,
            db=cast(AsyncSession, object()),
            session_service=session_service,
        )
        reply = await console_service.process_message(
            "+10000000000",
            "2",
            tenant_id=tenant_id,
            db=cast(AsyncSession, object()),
            session_service=session_service,
        )
        assert "1\ufe0f\u20e3 PA" in reply
        assert "7\ufe0f\u20e3 PG" in reply
        assert "PH" not in reply
        assert "8\ufe0f\u20e3 Siguiente" in reply

        # 8 -> next page
        reply = await console_service.process_message(
            "+10000000000",
            "8",
            tenant_id=tenant_id,
            db=cast(AsyncSession, object()),
            session_service=session_service,
        )
        assert "1\ufe0f\u20e3 PH" in reply
        assert "2\ufe0f\u20e3 PI" in reply
        assert "8\ufe0f\u20e3 Siguiente" not in reply


@pytest.mark.asyncio
async def test_tenant_console_profile_locale_updates_tenant_settings(
    db_session, active_tenant_user
):
    """Profile locale change via WhatsApp updates TenantSettings (not Tenant)."""
    from sqlalchemy import select

    from app.models import Tenant, TenantSettings
    from app.services.whatsapp_session_service import WhatsAppSessionService
    from app.services.whatsapp_tenant_console_service import (
        WhatsAppTenantConsoleService,
    )

    tenant = (
        await db_session.execute(
            select(Tenant).where(Tenant.owner_user_id == active_tenant_user.id)
        )
    ).scalar_one()
    settings = (
        await db_session.execute(
            select(TenantSettings).where(TenantSettings.tenant_id == tenant.id)
        )
    ).scalar_one()
    assert settings.locale == "es"

    service = WhatsAppTenantConsoleService()
    session_service = WhatsAppSessionService(FakeManager())
    session = await session_service.create_session("admin:12015550002")
    session.flow = service.PROFILE_FLOW
    session.step = service.PROFILE_STEP_CHANGE_LOCALE_SELECT
    await session_service.save_session(session)

    response = await service.process_message(
        phone="12015550002",
        message="2",
        tenant_id=tenant.id,
        user_id=active_tenant_user.id,
        db=db_session,
        session_service=session_service,
        locale="en",
    )

    refreshed = (
        await db_session.execute(
            select(TenantSettings).where(TenantSettings.tenant_id == tenant.id)
        )
    ).scalar_one()
    assert refreshed.locale == "es"
    assert "Español" in response


# ===================================================================
# FakeTenantSettingsService for currency symbol tests
# ===================================================================


@dataclass
class FakeTenantSettingsObj:
    currency: str | None = "VES"
    locale: str = "es"


class FakeTenantSettingsService:
    """In-memory double for TenantSettingsService."""

    def __init__(self, currency: str | None = "VES") -> None:
        self._settings = FakeTenantSettingsObj(currency=currency)

    async def get_settings(self, db: Any, tenant_id: UUID) -> FakeTenantSettingsObj:
        return self._settings


# ===================================================================
# format_price unit tests
# ===================================================================


class TestFormatPrice:
    """Tests for the format_price helper."""

    def test_format_price_with_symbol_and_amount(self) -> None:
        from decimal import Decimal
        from app.services.whatsapp_tenant_console_service.format_helpers import (
            format_price,
        )

        result = format_price(Decimal("12.50"), "Bs.", "es")
        assert "Bs." in result
        assert "12" in result

    def test_format_price_none_returns_on_request_label(self) -> None:
        from app.services.whatsapp_tenant_console_service.format_helpers import (
            format_price,
        )

        result = format_price(None, "Bs.", "es")
        assert "consultar" in result.lower() or "request" in result.lower()

    def test_format_price_without_symbol(self) -> None:
        from decimal import Decimal
        from app.services.whatsapp_tenant_console_service.format_helpers import (
            format_price,
        )

        result = format_price(Decimal("12.50"), None, "es")
        assert "12" in result
        assert "50" in result

    def test_format_price_english_locale(self) -> None:
        from decimal import Decimal
        from app.services.whatsapp_tenant_console_service.format_helpers import (
            format_price,
        )

        result = format_price(Decimal("12.50"), "$", "en")
        assert "$" in result
        assert "12.50" in result


# ===================================================================
# Plan price display tests
# ===================================================================


@pytest.mark.asyncio
class TestPlanPriceDisplay:
    """Tests for plan price display in formatters and flows."""

    def test_format_plan_list_shows_price(self) -> None:
        from app.services.whatsapp_tenant_console_service._context import (
            set_locale,
            reset_locale,
        )
        from app.services.whatsapp_tenant_console_service.formatters import (
            _format_plan_list,
        )

        plan = FakePlanObj(id=uuid4(), name="Basico", price=Decimal("12.50"))
        token = set_locale("es")
        try:
            reply, selection = _format_plan_list([plan], symbol="Bs.")
            assert "Basico" in reply
            assert "Bs." in reply
        finally:
            reset_locale(token)

    def test_format_plan_list_without_price(self) -> None:
        from app.services.whatsapp_tenant_console_service._context import (
            set_locale,
            reset_locale,
        )
        from app.services.whatsapp_tenant_console_service.formatters import (
            _format_plan_list,
        )

        plan = FakePlanObj(id=uuid4(), name="Basico", price=None)
        token = set_locale("es")
        try:
            reply, selection = _format_plan_list([plan], symbol="Bs.")
            assert "Basico" in reply
        finally:
            reset_locale(token)

    def test_format_plan_detail_shows_price(self) -> None:
        from app.services.whatsapp_tenant_console_service._context import (
            set_locale,
            reset_locale,
        )
        from app.services.whatsapp_tenant_console_service.formatters import (
            _format_plan_detail,
        )

        plan = FakePlanObj(id=uuid4(), name="Premium", price=Decimal("25.00"))
        token = set_locale("es")
        try:
            reply = _format_plan_detail(plan, symbol="Bs.")
            assert "Premium" in reply
            assert "Bs." in reply
        finally:
            reset_locale(token)

    def test_format_plan_detail_without_price(self) -> None:
        from app.services.whatsapp_tenant_console_service._context import (
            set_locale,
            reset_locale,
        )
        from app.services.whatsapp_tenant_console_service.formatters import (
            _format_plan_detail,
        )

        plan = FakePlanObj(id=uuid4(), name="Free", price=None)
        token = set_locale("es")
        try:
            reply = _format_plan_detail(plan, symbol="Bs.")
            assert "Free" in reply
        finally:
            reset_locale(token)


# ===================================================================
# Plan price create/edit flow tests
# ===================================================================


@pytest.mark.asyncio
class TestPlanPriceFlows:
    """Tests for plan price create/edit flows."""

    async def test_create_plan_flow_shows_price_prompt(
        self,
        console_service: WhatsAppTenantConsoleService,
        session_service: WhatsAppSessionService,
        catalog_service: FakeCatalogService,
    ) -> None:
        """After entering plan name, user sees price prompt."""
        # Setup: add a service
        service = FakeServiceObj(name="Netflix")
        catalog_service._services[str(service.id)] = service
        tenant_id = uuid4()

        # Start catalog → service action → create plan
        # 1. Start catalog flow
        reply = await console_service.process_message(
            phone="+10000000000",
            message="2",
            session_service=session_service,
            tenant_id=tenant_id,
            db=AsyncMock(),
        )
        # 2. View services list
        reply = await console_service.process_message(
            phone="+10000000000",
            message="1",
            session_service=session_service,
            tenant_id=tenant_id,
            db=AsyncMock(),
        )
        # 3. Select service (service #1)
        reply = await console_service.process_message(
            phone="+10000000000",
            message="1",
            session_service=session_service,
            tenant_id=tenant_id,
            db=AsyncMock(),
        )
        # 4. Create plan (option 3 from service actions)
        reply = await console_service.process_message(
            phone="+10000000000",
            message="3",
            session_service=session_service,
            tenant_id=tenant_id,
            db=AsyncMock(),
        )
        # 4. Enter plan name
        reply = await console_service.process_message(
            phone="+10000000000",
            message="Premium",
            session_service=session_service,
            tenant_id=tenant_id,
            db=AsyncMock(),
        )
        # Should show price prompt now
        assert "precio" in reply.lower() or "price" in reply.lower()

    async def test_create_plan_flow_accepts_price(
        self,
        console_service: WhatsAppTenantConsoleService,
        session_service: WhatsAppSessionService,
        catalog_service: FakeCatalogService,
    ) -> None:
        """Entering a valid price creates plan with price."""
        catalog_service._plans.clear()
        service = FakeServiceObj(name="Netflix")
        catalog_service._services[str(service.id)] = service
        tenant_id = uuid4()

        # Navigate to create plan price step
        for step in ["2", "1", "1", "3", "Premium"]:
            await console_service.process_message(
                phone="+10000000000",
                message=step,
                session_service=session_service,
                tenant_id=tenant_id,
                db=AsyncMock(),
            )

        # Send price
        reply = await console_service.process_message(
            phone="+10000000000",
            message="12.50",
            session_service=session_service,
            tenant_id=tenant_id,
            db=AsyncMock(),
        )

        # Plan should be created with price
        plans = list(catalog_service._plans.values())
        assert len(plans) == 1
        assert plans[0].name == "Premium"
        assert plans[0].price == Decimal("12.50")
        assert "creado" in reply.lower() or "created" in reply.lower()

    async def test_create_plan_flow_skips_price(
        self,
        console_service: WhatsAppTenantConsoleService,
        session_service: WhatsAppSessionService,
        catalog_service: FakeCatalogService,
    ) -> None:
        """Sending 'sin precio' at price prompt creates plan without price."""
        catalog_service._plans.clear()
        service = FakeServiceObj(name="Netflix")
        catalog_service._services[str(service.id)] = service
        tenant_id = uuid4()

        for step in ["2", "1", "1", "3", "Premium"]:
            await console_service.process_message(
                phone="+10000000000",
                message=step,
                session_service=session_service,
                tenant_id=tenant_id,
                db=AsyncMock(),
            )

        await console_service.process_message(
            phone="+10000000000",
            message="sin precio",
            session_service=session_service,
            tenant_id=tenant_id,
            db=AsyncMock(),
        )

        plans = list(catalog_service._plans.values())
        assert len(plans) == 1
        assert plans[0].price is None

    async def test_create_plan_flow_invalid_price_reprompts(
        self,
        console_service: WhatsAppTenantConsoleService,
        session_service: WhatsAppSessionService,
        catalog_service: FakeCatalogService,
    ) -> None:
        """Invalid price input reprompts user."""
        catalog_service._plans.clear()
        service = FakeServiceObj(name="Netflix")
        catalog_service._services[str(service.id)] = service
        tenant_id = uuid4()

        for step in ["2", "1", "1", "3", "Premium"]:
            await console_service.process_message(
                phone="+10000000000",
                message=step,
                session_service=session_service,
                tenant_id=tenant_id,
                db=AsyncMock(),
            )

        reply = await console_service.process_message(
            phone="+10000000000",
            message="abc",
            session_service=session_service,
            tenant_id=tenant_id,
            db=AsyncMock(),
        )

        # Should show invalid price error and reprompt
        assert "inválido" in reply.lower() or "invalid" in reply.lower()
        plans = list(catalog_service._plans.values())
        assert len(plans) == 0  # Plan not yet created

    async def test_edit_plan_price_flow(
        self,
        console_service: WhatsAppTenantConsoleService,
        session_service: WhatsAppSessionService,
        catalog_service: FakeCatalogService,
    ) -> None:
        """Plan action '2' edits price."""
        catalog_service._plans.clear()
        service = FakeServiceObj(name="Netflix")
        catalog_service._services[str(service.id)] = service
        plan = FakePlanObj(
            service_id=service.id, name="Premium", price=Decimal("10.00")
        )
        catalog_service._plans[str(plan.id)] = plan
        tenant_id = uuid4()

        # Navigate to plan list: catalog menu → service list → service action → view plans
        for step in ["2", "1", "1", "2"]:
            await console_service.process_message(
                phone="+10000000000",
                message=step,
                session_service=session_service,
                tenant_id=tenant_id,
                db=AsyncMock(),
            )

        # Select plan #1
        reply = await console_service.process_message(
            phone="+10000000000",
            message="1",
            session_service=session_service,
            tenant_id=tenant_id,
            db=AsyncMock(),
        )

        # Plan action: edit price (option 2)
        reply = await console_service.process_message(
            phone="+10000000000",
            message="2",
            session_service=session_service,
            tenant_id=tenant_id,
            db=AsyncMock(),
        )
        assert "precio" in reply.lower() or "price" in reply.lower()

        # Send new price
        reply = await console_service.process_message(
            phone="+10000000000",
            message="9.99",
            session_service=session_service,
            tenant_id=tenant_id,
            db=AsyncMock(),
        )
        assert plan.price == Decimal("9.99")
        assert "actualizado" in reply.lower() or "updated" in reply.lower()

    async def test_edit_plan_price_clear(
        self,
        console_service: WhatsAppTenantConsoleService,
        session_service: WhatsAppSessionService,
        catalog_service: FakeCatalogService,
    ) -> None:
        """Sending 'sin precio' clears the price."""
        catalog_service._plans.clear()
        service = FakeServiceObj(name="Netflix")
        catalog_service._services[str(service.id)] = service
        plan = FakePlanObj(
            service_id=service.id, name="Premium", price=Decimal("10.00")
        )
        catalog_service._plans[str(plan.id)] = plan
        tenant_id = uuid4()

        # Navigate to plan list: catalog menu → service list → service action → view plans
        for step in ["2", "1", "1", "2"]:
            await console_service.process_message(
                phone="+10000000000",
                message=step,
                session_service=session_service,
                tenant_id=tenant_id,
                db=AsyncMock(),
            )

        # Select plan
        await console_service.process_message(
            phone="+10000000000",
            message="1",
            session_service=session_service,
            tenant_id=tenant_id,
            db=AsyncMock(),
        )

        # Edit price
        await console_service.process_message(
            phone="+10000000000",
            message="2",
            session_service=session_service,
            tenant_id=tenant_id,
            db=AsyncMock(),
        )

        # Clear price
        reply = await console_service.process_message(
            phone="+10000000000",
            message="sin precio",
            session_service=session_service,
            tenant_id=tenant_id,
            db=AsyncMock(),
        )
        assert plan.price is None
        assert "limpiado" in reply.lower() or "cleared" in reply.lower()

    async def test_plan_action_menu_has_three_options(
        self,
        console_service: WhatsAppTenantConsoleService,
        session_service: WhatsAppSessionService,
        catalog_service: FakeCatalogService,
    ) -> None:
        """Plan action menu now has 3 options: edit name, edit price, delete."""
        catalog_service._plans.clear()
        service = FakeServiceObj(name="Netflix")
        catalog_service._services[str(service.id)] = service
        plan = FakePlanObj(service_id=service.id, name="Premium")
        catalog_service._plans[str(plan.id)] = plan
        tenant_id = uuid4()

        # Navigate to plan list: catalog menu → service list → service action → view plans
        for step in ["2", "1", "1", "2"]:
            await console_service.process_message(
                phone="+10000000000",
                message=step,
                session_service=session_service,
                tenant_id=tenant_id,
                db=AsyncMock(),
            )

        reply = await console_service.process_message(
            phone="+10000000000",
            message="1",
            session_service=session_service,
            tenant_id=tenant_id,
            db=AsyncMock(),
        )

        # Should have 3 action options
        assert "1️⃣" in reply
        assert "2️⃣" in reply
        assert "3️⃣" in reply

    async def test_plan_price_prompt_cancel_reachable(
        self,
        console_service: WhatsAppTenantConsoleService,
        session_service: WhatsAppSessionService,
        catalog_service: FakeCatalogService,
    ) -> None:
        """Universal cancel handler catches 'salir' at the price prompt."""
        catalog_service._plans.clear()
        service = FakeServiceObj(name="Netflix")
        catalog_service._services[str(service.id)] = service
        tenant_id = uuid4()

        # Navigate to create plan price step
        for step in ["2", "1", "1", "3", "Premium"]:
            await console_service.process_message(
                phone="+10000000000",
                message=step,
                session_service=session_service,
                tenant_id=tenant_id,
                db=AsyncMock(),
            )

        # Send "salir" — should be caught by universal cancel handler
        reply = await console_service.process_message(
            phone="+10000000000",
            message="salir",
            session_service=session_service,
            tenant_id=tenant_id,
            db=AsyncMock(),
        )

        # Should cancel and return to main menu or goodbye
        assert (
            "cancelada" in reply.lower()
            or "consola" in reply.lower()
            or "salido" in reply.lower()
            or "menu" in reply.lower()
        )

        # Session should be cleared
        session = await session_service.get_session("admin:+10000000000")
        assert session is None


# ===================================================================
# Currency symbol loading tests
# ===================================================================


@pytest.mark.asyncio
class TestLoadCurrencySymbol:
    """Tests for _load_currency_symbol helper."""

    async def test_load_currency_symbol_returns_symbol(self) -> None:
        """_load_currency_symbol resolves 'VES' to 'Bs.'."""
        from app.services.whatsapp_tenant_console_service.format_helpers import (
            _load_currency_symbol,
        )

        mock_db = AsyncMock()
        with patch(
            "app.repositories.tenant_settings_repository"
        ) as mock_repo:
            settings = FakeTenantSettingsObj(currency="VES")
            mock_repo.get_by_tenant_id = AsyncMock(return_value=settings)

            symbol = await _load_currency_symbol(mock_db, uuid4())
            assert symbol == "Bs."

    async def test_load_currency_symbol_none_when_no_currency(self) -> None:
        """_load_currency_symbol returns None when currency not set."""
        from app.services.whatsapp_tenant_console_service.format_helpers import (
            _load_currency_symbol,
        )

        mock_db = AsyncMock()
        with patch(
            "app.repositories.tenant_settings_repository"
        ) as mock_repo:
            settings = FakeTenantSettingsObj(currency=None)
            mock_repo.get_by_tenant_id = AsyncMock(return_value=settings)

            symbol = await _load_currency_symbol(mock_db, uuid4())
            assert symbol is None

    async def test_load_currency_symbol_none_when_no_settings(self) -> None:
        """_load_currency_symbol returns None when no tenant settings."""
        from app.services.whatsapp_tenant_console_service.format_helpers import (
            _load_currency_symbol,
        )

        mock_db = AsyncMock()
        with patch(
            "app.repositories.tenant_settings_repository"
        ) as mock_repo:
            mock_repo.get_by_tenant_id = AsyncMock(return_value=None)

            symbol = await _load_currency_symbol(mock_db, uuid4())
            assert symbol is None


# ===================================================================
# Subscription detail price display tests
# ===================================================================


class TestSubscriptionDetailPrice:
    """Tests for subscription detail formatter showing price."""

    def test_format_subscription_detail_shows_price_with_symbol(self) -> None:
        """When symbol is provided and sub has plan price, price is shown."""
        from app.services.whatsapp_tenant_console_service._context import (
            set_locale,
            reset_locale,
        )
        from app.services.whatsapp_tenant_console_service.formatters import (
            _format_subscription_detail,
        )

        sub = FakeSubscriptionObj(plan_name="Premium")
        sub.plan_price = Decimal("25.00")
        token = set_locale("es")
        try:
            reply = _format_subscription_detail(sub, symbol="Bs.")
            assert "Premium" in reply
            assert "Bs." in reply
            assert "25,00" in reply
        finally:
            reset_locale(token)

    def test_format_subscription_detail_no_price_when_no_symbol(self) -> None:
        """When symbol is None, price is not shown in plan line."""
        from app.services.whatsapp_tenant_console_service._context import (
            set_locale,
            reset_locale,
        )
        from app.services.whatsapp_tenant_console_service.formatters import (
            _format_subscription_detail,
        )

        sub = FakeSubscriptionObj(plan_name="Basic")
        sub.plan_price = Decimal("10.00")
        token = set_locale("es")
        try:
            reply = _format_subscription_detail(sub, symbol=None)
            assert "Basic" in reply
            assert "10,00" not in reply
        finally:
            reset_locale(token)

    def test_format_subscription_detail_plan_only_when_no_price(self) -> None:
        """When plan has no price, only plan name is shown."""
        from app.services.whatsapp_tenant_console_service._context import (
            set_locale,
            reset_locale,
        )
        from app.services.whatsapp_tenant_console_service.formatters import (
            _format_subscription_detail,
        )

        sub = FakeSubscriptionObj(plan_name="Free")
        sub.plan_price = None
        token = set_locale("es")
        try:
            reply = _format_subscription_detail(sub, symbol="Bs.")
            assert "Free" in reply
            assert "consultar" in reply.lower() or "request" in reply.lower()
        finally:
            reset_locale(token)


# ===================================================================
# Integration: catalog flow passes symbol to formatters
# ===================================================================


@pytest.mark.asyncio
class TestCatalogFlowCurrencyIntegration:
    """Integration tests verifying currency symbol reaches formatters in catalog flow."""

    async def test_catalog_plan_list_shows_currency(
        self,
        console_service: WhatsAppTenantConsoleService,
        session_service: WhatsAppSessionService,
        catalog_service: FakeCatalogService,
    ) -> None:
        """Plan list in catalog flow should show currency symbol when configured."""
        catalog_service._plans.clear()
        service = FakeServiceObj(name="Netflix")
        catalog_service._services[str(service.id)] = service
        plan = FakePlanObj(
            service_id=service.id, name="Premium", price=Decimal("12.50")
        )
        catalog_service._plans[str(plan.id)] = plan
        tenant_id = uuid4()
        mock_db = AsyncMock()

        for step in ["2", "1", "1", "2"]:
            reply = await console_service.process_message(
                phone="+10000000000",
                message=step,
                session_service=session_service,
                tenant_id=tenant_id,
                db=mock_db,
            )

        assert "Premium" in reply
        assert "12" in reply
