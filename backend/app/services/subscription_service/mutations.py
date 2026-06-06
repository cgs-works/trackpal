"""Subscription lifecycle mutations: create, cancel, reactivate, renew."""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import restore_rls_context
from app.core.encryption import encrypt_value
from app.core.errors import UserFacingError
from app.models.subscription import Subscription
from app.schemas.subscription import SubscriptionCreate
from .helpers import calculate_expiration, commit_change, create_event
from .queries import get_subscription
from .validation import validate_ids


async def create_subscription(
    db: AsyncSession, tenant_id: uuid.UUID, payload: SubscriptionCreate
) -> Subscription:
    await validate_ids(db, tenant_id, payload.client_id, payload.service_id, payload.plan_id)

    if payload.profile_pin and not payload.profile_name:
        raise UserFacingError("subscription_pin_requires_profile")

    # Check for duplicate active subscription with same service + streaming email
    from app.services.subscription_service.queries import (
        get_active_subscriptions_for_client,
    )

    existing = await get_active_subscriptions_for_client(
        db, tenant_id, payload.client_id
    )
    for sub in existing:
        if (
            sub.service_id == payload.service_id
            and sub.streaming_email == payload.streaming_email
        ):
            from app.models import Service as _Svc
            from sqlalchemy import select as _select

            res = await db.execute(
                _select(_Svc).where(_Svc.id == payload.service_id)
            )
            svc = res.scalar_one_or_none()
            svc_name = svc.name if svc else "Unknown"
            from app.repositories.clients_repository import (
                get_client_by_id,
            )

            cli = await get_client_by_id(db, payload.client_id)
            cli_name = cli.full_name if cli else "Unknown"
            raise UserFacingError(
                "subscription_duplicate_service_email",
                params={
                    "client_name": cli_name,
                    "service_name": svc_name,
                    "email": payload.streaming_email,
                },
            )

    starts_at = payload.starts_at
    if starts_at.tzinfo is None:
        starts_at = starts_at.replace(tzinfo=timezone.utc)

    expires_at_val = payload.expires_at
    if expires_at_val and expires_at_val.tzinfo is None:
        expires_at_val = expires_at_val.replace(tzinfo=timezone.utc)

    calculated_expires_at = calculate_expiration(
        starts_at, payload.duration_type, expires_at_val
    )

    password_encrypted = encrypt_value(payload.streaming_password)
    pin_encrypted = encrypt_value(payload.profile_pin)

    sub = Subscription(
        tenant_id=tenant_id,
        client_id=payload.client_id,
        service_id=payload.service_id,
        plan_id=payload.plan_id,
        streaming_email=payload.streaming_email,
        streaming_password_encrypted=password_encrypted,
        profile_name=payload.profile_name,
        profile_pin_encrypted=pin_encrypted,
        duration_type=payload.duration_type,
        starts_at=starts_at,
        expires_at=calculated_expires_at,
        status="active",
    )
    db.add(sub)
    await db.flush()

    await create_event(db, tenant_id, sub.id, "created", notes="Subscription created")
    await commit_change(db, "subscription_create_failed")
    await restore_rls_context(db)
    await db.refresh(sub)
    return sub


async def cancel_subscription(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    subscription_id: uuid.UUID,
    notes: Optional[str] = None,
) -> Optional[Subscription]:
    sub = await get_subscription(db, tenant_id, subscription_id)
    if not sub:
        return None

    sub.status = "cancelled"
    sub.cancelled_at = datetime.now(timezone.utc)

    await create_event(
        db, tenant_id, sub.id, "cancelled", notes=notes or "Subscription cancelled"
    )
    await commit_change(db, "subscription_cancel_failed")
    await restore_rls_context(db)
    await db.refresh(sub)
    return sub


async def reactivate_subscription(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    subscription_id: uuid.UUID,
    duration_type: str,
    starts_at: Optional[datetime] = None,
    expires_at: Optional[datetime] = None,
    notes: Optional[str] = None,
) -> Optional[Subscription]:
    sub = await get_subscription(db, tenant_id, subscription_id)
    if not sub:
        return None

    starts_at_val = starts_at or datetime.now(timezone.utc)
    if starts_at_val.tzinfo is None:
        starts_at_val = starts_at_val.replace(tzinfo=timezone.utc)
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    calculated_expires = calculate_expiration(starts_at_val, duration_type, expires_at)

    sub.status = "active"
    sub.cancelled_at = None
    sub.starts_at = starts_at_val
    sub.duration_type = duration_type
    sub.expires_at = calculated_expires

    await create_event(
        db,
        tenant_id,
        sub.id,
        "reactivated",
        notes=notes or f"Subscription reactivated with duration: {duration_type}",
    )
    await commit_change(db, "subscription_reactivate_failed")
    await restore_rls_context(db)
    await db.refresh(sub)
    return sub


async def renew_subscription(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    subscription_id: uuid.UUID,
    duration_type: str,
    expires_at: Optional[datetime] = None,
    notes: Optional[str] = None,
) -> Optional[Subscription]:
    sub = await get_subscription(db, tenant_id, subscription_id)
    if not sub:
        return None

    current_expires = sub.expires_at
    if current_expires.tzinfo is None:
        current_expires = current_expires.replace(tzinfo=timezone.utc)
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    new_expires = calculate_expiration(current_expires, duration_type, expires_at)

    sub.status = "active"
    sub.cancelled_at = None
    sub.duration_type = duration_type
    sub.expires_at = new_expires

    await create_event(
        db,
        tenant_id,
        sub.id,
        "renewed",
        notes=notes or f"Subscription renewed with duration: {duration_type}",
    )
    await commit_change(db, "subscription_renew_failed")
    await restore_rls_context(db)
    await db.refresh(sub)
    return sub
