"""Read-only subscription queries."""

import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.encryption import decrypt_value
from app.models.subscription import Subscription, SubscriptionEvent


async def get_subscription(
    db: AsyncSession, tenant_id: uuid.UUID, subscription_id: uuid.UUID
) -> Optional[Subscription]:
    res = await db.execute(
        select(Subscription)
        .options(selectinload(Subscription.plan))
        .where(
            Subscription.tenant_id == tenant_id, Subscription.id == subscription_id
        )
    )
    return res.scalar_one_or_none()


async def reveal_credentials(
    db: AsyncSession, tenant_id: uuid.UUID, subscription_id: uuid.UUID
) -> Optional[dict]:
    sub = await get_subscription(db, tenant_id, subscription_id)
    if not sub:
        return None
    return {
        "streaming_password": decrypt_value(sub.streaming_password_encrypted),
        "profile_pin": decrypt_value(sub.profile_pin_encrypted),
    }


async def list_subscriptions(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    status: Optional[str] = None,
    client_id: Optional[uuid.UUID] = None,
    service_id: Optional[uuid.UUID] = None,
    quick_filter: Optional[str] = None,
    expires_from: Optional[datetime] = None,
    expires_to: Optional[datetime] = None,
) -> List[Subscription]:
    stmt = select(Subscription).where(Subscription.tenant_id == tenant_id)

    if status:
        stmt = stmt.where(Subscription.status == status)
    else:
        stmt = stmt.where(Subscription.status != "cancelled")

    if client_id:
        stmt = stmt.where(Subscription.client_id == client_id)
    if service_id:
        stmt = stmt.where(Subscription.service_id == service_id)

    now = datetime.now(timezone.utc)
    if quick_filter == "expired":
        stmt = stmt.where(Subscription.expires_at < now)
    elif quick_filter == "today":
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
        stmt = stmt.where(
            and_(
                Subscription.expires_at >= today_start,
                Subscription.expires_at <= today_end,
            )
        )
    elif quick_filter == "next_7_days":
        stmt = stmt.where(
            and_(
                Subscription.expires_at >= now,
                Subscription.expires_at <= now + timedelta(days=7),
            )
        )
    elif quick_filter == "next_30_days":
        stmt = stmt.where(
            and_(
                Subscription.expires_at >= now,
                Subscription.expires_at <= now + timedelta(days=30),
            )
        )

    if expires_from:
        if expires_from.tzinfo is None:
            expires_from = expires_from.replace(tzinfo=timezone.utc)
        stmt = stmt.where(Subscription.expires_at >= expires_from)
    if expires_to:
        if expires_to.tzinfo is None:
            expires_to = expires_to.replace(tzinfo=timezone.utc)
        stmt = stmt.where(Subscription.expires_at <= expires_to)

    stmt = stmt.order_by(Subscription.created_at.desc())
    res = await db.execute(stmt)
    return list(res.scalars().all())


async def get_active_subscriptions_for_client(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    client_id: uuid.UUID,
) -> list[Subscription]:
    """Return active subscriptions for a client with service/plan loaded."""
    stmt = (
        select(Subscription)
        .options(
            selectinload(Subscription.service),
            selectinload(Subscription.plan),
        )
        .where(
            Subscription.tenant_id == tenant_id,
            Subscription.client_id == client_id,
            Subscription.status == "active",
        )
        .order_by(Subscription.expires_at.asc())
    )
    res = await db.execute(stmt)
    return list(res.scalars().all())


async def list_subscription_events(
    db: AsyncSession, tenant_id: uuid.UUID, subscription_id: uuid.UUID
) -> List[SubscriptionEvent]:
    sub = await get_subscription(db, tenant_id, subscription_id)
    if not sub:
        return []

    res = await db.execute(
        select(SubscriptionEvent)
        .where(
            SubscriptionEvent.tenant_id == tenant_id,
            SubscriptionEvent.subscription_id == subscription_id,
        )
        .order_by(SubscriptionEvent.created_at.desc())
    )
    return list(res.scalars().all())
