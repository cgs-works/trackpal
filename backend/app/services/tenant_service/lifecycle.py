"""Tenant lifecycle operations: activate, deactivate."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import restore_rls_context
from app.models import Tenant
from app.repositories import sessions_repository
from .queries import get_tenant


async def deactivate_tenant(db: AsyncSession, tenant_id: UUID) -> Tenant | None:
    profile = await get_tenant(db, tenant_id)
    if profile is None:
        return None
    if profile.is_demo:
        raise ValueError("Demo Tenant must be managed through the Demo Tenant API")
    profile.is_active = False
    await sessions_repository.revoke_all_for_user(db, profile.owner_user_id)
    await db.commit()
    await restore_rls_context(db)
    return await get_tenant(db, tenant_id)


async def activate_tenant(db: AsyncSession, tenant_id: UUID) -> Tenant | None:
    profile = await get_tenant(db, tenant_id)
    if profile is None:
        return None
    if profile.is_demo:
        raise ValueError("Demo Tenant must be managed through the Demo Tenant API")
    profile.is_active = True
    await db.commit()
    await restore_rls_context(db)
    return await get_tenant(db, tenant_id)
