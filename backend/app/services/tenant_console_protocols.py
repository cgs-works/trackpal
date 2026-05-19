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
    console actually invokes.  Catalog creation and deletion are out
    of scope for the tenant WhatsApp flow.
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
