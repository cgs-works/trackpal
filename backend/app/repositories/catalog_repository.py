"""Catalog repository — Service/Plan table queries."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Plan, Service


async def list_services(db: AsyncSession, tenant_id: UUID) -> list[Service]:
    """List all services for a tenant, newest first."""
    result = await db.execute(
        select(Service)
        .where(Service.tenant_id == tenant_id)
        .order_by(Service.created_at.desc())
    )
    return list(result.scalars().all())


async def get_service(
    db: AsyncSession, tenant_id: UUID, service_id: UUID
) -> Service | None:
    """Get service by tenant and service id."""
    result = await db.execute(
        select(Service).where(
            Service.tenant_id == tenant_id, Service.id == service_id
        )
    )
    return result.scalar_one_or_none()


async def service_name_exists(
    db: AsyncSession,
    tenant_id: UUID,
    name: str,
    exclude_id: UUID | None = None,
) -> bool:
    """Check if a service name is taken within a tenant."""
    stmt = select(Service.id).where(
        Service.tenant_id == tenant_id,
        func.lower(Service.name) == name.lower(),
    )
    if exclude_id:
        stmt = stmt.where(Service.id != exclude_id)
    return (await db.execute(stmt)).first() is not None


async def list_plans(
    db: AsyncSession, tenant_id: UUID, service_id: UUID
) -> list[Plan]:
    """List all plans for a service, newest first."""
    result = await db.execute(
        select(Plan)
        .where(Plan.tenant_id == tenant_id, Plan.service_id == service_id)
        .order_by(Plan.created_at.desc())
    )
    return list(result.scalars().all())


async def get_plan(
    db: AsyncSession, tenant_id: UUID, service_id: UUID, plan_id: UUID
) -> Plan | None:
    """Get plan by tenant, service, and plan id."""
    result = await db.execute(
        select(Plan).where(
            Plan.tenant_id == tenant_id,
            Plan.service_id == service_id,
            Plan.id == plan_id,
        )
    )
    return result.scalar_one_or_none()


async def plan_name_exists(
    db: AsyncSession,
    tenant_id: UUID,
    service_id: UUID,
    name: str,
    exclude_id: UUID | None = None,
) -> bool:
    """Check if a plan name is taken within a service."""
    stmt = select(Plan.id).where(
        Plan.tenant_id == tenant_id,
        Plan.service_id == service_id,
        func.lower(Plan.name) == name.lower(),
    )
    if exclude_id:
        stmt = stmt.where(Plan.id != exclude_id)
    return (await db.execute(stmt)).first() is not None


__all__ = [
    "list_services",
    "get_service",
    "service_name_exists",
    "list_plans",
    "get_plan",
    "plan_name_exists",
]
