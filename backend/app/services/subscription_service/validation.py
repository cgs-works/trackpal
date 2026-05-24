"""Cross-entity ID validation for subscription operations."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import UserFacingError
from app.models import Client, Service, Plan


async def validate_ids(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    client_id: uuid.UUID,
    service_id: uuid.UUID,
    plan_id: uuid.UUID,
) -> None:
    """Validate that client/service/plan exist and belong to tenant."""
    client_res = await db.execute(
        select(Client).where(Client.tenant_id == tenant_id, Client.id == client_id)
    )
    if not client_res.scalar_one_or_none():
        raise UserFacingError("subscription_client_not_found")

    service_res = await db.execute(
        select(Service).where(Service.tenant_id == tenant_id, Service.id == service_id)
    )
    if not service_res.scalar_one_or_none():
        raise UserFacingError("subscription_service_not_found")

    plan_res = await db.execute(
        select(Plan).where(
            Plan.tenant_id == tenant_id,
            Plan.service_id == service_id,
            Plan.id == plan_id,
        )
    )
    if not plan_res.scalar_one_or_none():
        raise UserFacingError("subscription_plan_not_found")
