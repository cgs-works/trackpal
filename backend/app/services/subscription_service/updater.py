"""Subscription update operation (largest single mutation)."""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from app.core.database import restore_rls_context
from app.core.encryption import encrypt_value
from app.core.errors import UserFacingError
from app.models import Plan
from app.models.subscription import Subscription
from app.schemas.subscription import SubscriptionUpdate
from .helpers import calculate_expiration, commit_change, create_event
from .queries import get_subscription
from .validation import validate_ids


async def update_subscription(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    subscription_id: uuid.UUID,
    payload: SubscriptionUpdate,
) -> Optional[Subscription]:
    sub = await get_subscription(db, tenant_id, subscription_id)
    if not sub:
        return None

    update_data = payload.model_dump(exclude_unset=True)

    new_client_id = update_data.get("client_id", sub.client_id)
    new_service_id = update_data.get("service_id", sub.service_id)
    new_plan_id = update_data.get("plan_id", sub.plan_id)

    if "service_id" in update_data and "plan_id" not in update_data:
        plan_res = await db.execute(
            select(Plan).where(
                Plan.tenant_id == tenant_id,
                Plan.service_id == new_service_id,
                Plan.id == sub.plan_id,
            )
        )
        if not plan_res.scalar_one_or_none():
            raise UserFacingError("subscription_plan_service_mismatch")

    await validate_ids(db, tenant_id, new_client_id, new_service_id, new_plan_id)

    if "client_id" in update_data:
        sub.client_id = new_client_id
    if "service_id" in update_data:
        sub.service_id = new_service_id
    if "plan_id" in update_data:
        sub.plan_id = new_plan_id
    if "streaming_email" in update_data:
        sub.streaming_email = update_data["streaming_email"]
    if "profile_name" in update_data:
        sub.profile_name = update_data["profile_name"]

    if "streaming_password" in update_data:
        pwd = update_data["streaming_password"]
        if pwd is None or pwd == "":
            sub.streaming_password_encrypted = None
        else:
            sub.streaming_password_encrypted = encrypt_value(pwd)

    if "profile_pin" in update_data:
        pin = update_data["profile_pin"]
        if pin is None or pin == "":
            sub.profile_pin_encrypted = None
        else:
            sub.profile_pin_encrypted = encrypt_value(pin)

    final_profile_name = sub.profile_name
    final_pin = sub.profile_pin_encrypted
    if final_pin and not final_profile_name:
        raise UserFacingError("subscription_pin_requires_profile")

    starts_at_changed = "starts_at" in update_data
    duration_changed = "duration_type" in update_data
    expires_at_changed = "expires_at" in update_data

    if starts_at_changed or duration_changed or expires_at_changed:
        starts_at_val = update_data.get("starts_at", sub.starts_at)
        if starts_at_val and starts_at_val.tzinfo is None:
            starts_at_val = starts_at_val.replace(tzinfo=timezone.utc)

        duration_val = update_data.get("duration_type", sub.duration_type)

        expires_at_val = update_data.get("expires_at", sub.expires_at)
        if expires_at_val and expires_at_val.tzinfo is None:
            expires_at_val = expires_at_val.replace(tzinfo=timezone.utc)

        if duration_changed or starts_at_changed:
            calculated_expires = calculate_expiration(
                starts_at_val,
                duration_val,
                expires_at_val if expires_at_changed else None,
            )
        else:
            calculated_expires = expires_at_val

        sub.starts_at = starts_at_val
        sub.duration_type = duration_val
        sub.expires_at = calculated_expires

    await create_event(db, tenant_id, sub.id, "updated", notes="Subscription updated")
    await commit_change(db, "subscription_update_failed")
    await restore_rls_context(db)
    await db.refresh(sub)
    return sub
