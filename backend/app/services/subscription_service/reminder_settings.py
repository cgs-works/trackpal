"""Subscription reminder settings operations."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import restore_rls_context
from app.models.subscription import SubscriptionReminderSettings
from app.schemas.subscription import SubscriptionReminderSettingsUpdate
from .helpers import commit_change


async def get_reminder_settings(
    db: AsyncSession, tenant_id: uuid.UUID
) -> SubscriptionReminderSettings:
    res = await db.execute(
        select(SubscriptionReminderSettings).where(
            SubscriptionReminderSettings.tenant_id == tenant_id
        )
    )
    settings = res.scalar_one_or_none()
    if not settings:
        settings = SubscriptionReminderSettings(
            tenant_id=tenant_id,
            timezone="UTC",
            warning_days=[7, 3, 1],
            reminder_time="09:00",
            recipient_mode="tenant_only",
        )
        db.add(settings)
        await commit_change(db, "subscription_reminder_settings_failed")
        await restore_rls_context(db)
        await db.refresh(settings)
    return settings


async def update_reminder_settings(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    payload: SubscriptionReminderSettingsUpdate,
) -> SubscriptionReminderSettings:
    settings = await get_reminder_settings(db, tenant_id)

    update_data = payload.model_dump(exclude_unset=True)
    if "timezone" in update_data:
        settings.timezone = update_data["timezone"]
    if "warning_days" in update_data:
        settings.warning_days = update_data["warning_days"]
    if "reminder_time" in update_data:
        settings.reminder_time = update_data["reminder_time"]
    if "recipient_mode" in update_data:
        settings.recipient_mode = update_data["recipient_mode"]

    await commit_change(db, "subscription_reminder_settings_failed")
    await restore_rls_context(db)
    await db.refresh(settings)
    return settings
