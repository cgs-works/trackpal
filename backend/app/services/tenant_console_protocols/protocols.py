"""Protocol definitions for tenant-console dependency injection.

Defines ``ClientServiceProtocol`` and ``CatalogServiceProtocol`` so
the tenant facade and conversation service can depend on stable async
contracts instead of concrete ``ClientService`` / ``CatalogService``
implementations (following the same style as
``TenantServiceProtocol`` in the Master Console facade).
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession


@runtime_checkable
class ClientServiceProtocol(Protocol):
    """Minimal interface for tenant-scoped client CRUD operations.

    Matches the subset of ``ClientService`` methods that the tenant
    console actually invokes, enabling static type checking without
    circular imports between endpoint and service layers.
    """

    async def list_clients(
        self, db: AsyncSession, tenant_id: UUID
    ) -> list[Any]: ...

    async def get_client(
        self, db: AsyncSession, tenant_id: UUID, client_id: UUID
    ) -> Any | None: ...

    async def create_client(
        self, db: AsyncSession, tenant_id: UUID, payload: Any
    ) -> Any | None: ...

    async def update_client(
        self, db: AsyncSession, tenant_id: UUID, client_id: UUID, payload: Any
    ) -> Any | None: ...

    async def deactivate_client(
        self, db: AsyncSession, tenant_id: UUID, client_id: UUID
    ) -> Any | None: ...

    async def activate_client(
        self, db: AsyncSession, tenant_id: UUID, client_id: UUID
    ) -> Any | None: ...

    async def delete_client(
        self, db: AsyncSession, tenant_id: UUID, client_id: UUID
    ) -> bool: ...


@runtime_checkable
class CatalogServiceProtocol(Protocol):
    """Minimal interface for tenant-scoped catalog operations.

    Matches the subset of ``CatalogService`` methods that the tenant
    console actually invokes.
    """

    async def list_services(
        self, db: AsyncSession, tenant_id: UUID
    ) -> list[Any]: ...

    async def get_service(
        self, db: AsyncSession, tenant_id: UUID, service_id: UUID
    ) -> Any | None: ...

    async def update_service(
        self, db: AsyncSession, tenant_id: UUID, service_id: UUID, payload: Any
    ) -> Any | None: ...

    async def list_plans(
        self, db: AsyncSession, tenant_id: UUID, service_id: UUID
    ) -> list[Any] | None: ...

    async def get_plan(
        self, db: AsyncSession, tenant_id: UUID, service_id: UUID, plan_id: UUID
    ) -> Any | None: ...

    async def update_plan(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        service_id: UUID,
        plan_id: UUID,
        payload: Any,
    ) -> Any | None: ...

    async def list_service_summaries(
        self, db: AsyncSession, tenant_id: UUID
    ) -> list[Any]: ...

    async def list_plan_summaries(
        self, db: AsyncSession, tenant_id: UUID, service_id: UUID
    ) -> list[Any] | None: ...

    async def create_service(
        self, db: AsyncSession, tenant_id: UUID, payload: Any
    ) -> Any | None: ...

    async def create_plan(
        self, db: AsyncSession, tenant_id: UUID, service_id: UUID, payload: Any
    ) -> Any | None: ...

    async def get_service_delete_preview(
        self, db: AsyncSession, tenant_id: UUID, service_id: UUID, *, page: int = 1, page_size: int = 10
    ) -> Any | None: ...

    async def get_plan_delete_preview(
        self, db: AsyncSession, tenant_id: UUID, service_id: UUID, plan_id: UUID, *, page: int = 1, page_size: int = 10
    ) -> Any | None: ...

    async def delete_service(
        self, db: AsyncSession, tenant_id: UUID, service_id: UUID, *, confirm: bool = False
    ) -> Any | None: ...

    async def delete_plan(
        self, db: AsyncSession, tenant_id: UUID, service_id: UUID, plan_id: UUID, *, confirm: bool = False
    ) -> Any | None: ...


@runtime_checkable
class SubscriptionServiceProtocol(Protocol):
    """Minimal interface for tenant-scoped subscription CRUD operations.

    Matches the subset of ``SubscriptionService`` methods that the tenant
    WhatsApp console actually invokes.
    """

    async def list_subscriptions(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        status: str | None = None,
        client_id: UUID | None = None,
        service_id: UUID | None = None,
        quick_filter: str | None = None,
        expires_from=None,
        expires_to=None,
    ) -> list[Any]: ...

    async def get_subscription(
        self, db: AsyncSession, tenant_id: UUID, subscription_id: UUID
    ) -> Any | None: ...

    async def create_subscription(
        self, db: AsyncSession, tenant_id: UUID, payload: Any
    ) -> Any | None: ...

    async def update_subscription(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        subscription_id: UUID,
        payload: Any,
    ) -> Any | None: ...

    async def cancel_subscription(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        subscription_id: UUID,
        notes: str | None = None,
    ) -> Any | None: ...

    async def reactivate_subscription(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        subscription_id: UUID,
        duration_type: str,
        starts_at=None,
        expires_at=None,
        notes: str | None = None,
    ) -> Any | None: ...

    async def renew_subscription(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        subscription_id: UUID,
        duration_type: str,
        expires_at=None,
        notes: str | None = None,
    ) -> Any | None: ...

    async def reveal_credentials(
        self, db: AsyncSession, tenant_id: UUID, subscription_id: UUID
    ) -> dict | None: ...

    async def get_reminder_settings(
        self, db: AsyncSession, tenant_id: UUID
    ) -> Any: ...
