from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import TenantApiKey


async def get_by_tenant_id(db: AsyncSession, tenant_id: UUID) -> TenantApiKey | None:
    result = await db.execute(
        select(TenantApiKey).where(TenantApiKey.tenant_id == tenant_id)
    )
    return result.scalar_one_or_none()


async def get_by_api_key(db: AsyncSession, api_key: str) -> TenantApiKey | None:
    result = await db.execute(
        select(TenantApiKey).where(TenantApiKey.api_key == api_key)
    )
    return result.scalar_one_or_none()


async def delete_by_tenant_id(db: AsyncSession, tenant_id: UUID) -> None:
    row = await get_by_tenant_id(db, tenant_id)
    if row is not None:
        await db.delete(row)


__all__ = ["get_by_tenant_id", "get_by_api_key", "delete_by_tenant_id"]
