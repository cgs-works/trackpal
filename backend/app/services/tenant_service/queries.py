"""Read-only tenant queries."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import tenants_repository
from app.models import Tenant


async def get_tenants(db: AsyncSession) -> tuple[list[Tenant], dict]:
    return await tenants_repository.get_all(db)


async def get_tenant(db: AsyncSession, tenant_id: UUID) -> Tenant | None:
    return await tenants_repository.get_by_id_or_owner(db, tenant_id)
