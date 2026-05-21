import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Any
from sqlalchemy import select, and_, or_, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import restore_rls_context
from app.core.encryption import encrypt_value, decrypt_value
from app.models import Client, Service, Plan
from app.models.subscription import (
    Subscription,
    SubscriptionEvent,
    SubscriptionReminderSettings,
)
from app.schemas.subscription import (
    SubscriptionCreate,
    SubscriptionUpdate,
    SubscriptionReminderSettingsUpdate,
)

DURATION_MAP = {
    "1_month": 30,
    "3_months": 90,
    "6_months": 180,
    "9_months": 270,
    "1_year": 365,
}


class SubscriptionService:
    def calculate_expiration(
        self, starts_at: datetime, duration_type: str, expires_at: Optional[datetime] = None
    ) -> datetime:
        if duration_type == "custom":
            if not expires_at:
                raise ValueError("custom duration requires expires_at")
            return expires_at
        days = DURATION_MAP.get(duration_type)
        if not days:
            raise ValueError(f"Invalid duration_type: {duration_type}")
        return starts_at + timedelta(days=days)

    async def _commit_change(self, db: AsyncSession, error_message: str) -> None:
        try:
            await db.commit()
        except IntegrityError as exc:
            await db.rollback()
            raise ValueError(error_message) from exc

    async def _create_event(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        subscription_id: uuid.UUID,
        event_type: str,
        notes: Optional[str] = None,
        metadata: Optional[Any] = None,
    ) -> SubscriptionEvent:
        event = SubscriptionEvent(
            tenant_id=tenant_id,
            subscription_id=subscription_id,
            event_type=event_type,
            notes=notes,
            event_metadata=metadata,
        )
        db.add(event)
        # Flush to DB to associate/validate
        await db.flush()
        return event

    async def validate_ids(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        client_id: uuid.UUID,
        service_id: uuid.UUID,
        plan_id: uuid.UUID,
    ) -> None:
        # Validate client belongs to tenant
        client_res = await db.execute(
            select(Client).where(Client.tenant_id == tenant_id, Client.id == client_id)
        )
        if not client_res.scalar_one_or_none():
            raise ValueError("Client not found or does not belong to this tenant")

        # Validate service belongs to tenant
        service_res = await db.execute(
            select(Service).where(Service.tenant_id == tenant_id, Service.id == service_id)
        )
        if not service_res.scalar_one_or_none():
            raise ValueError("Service not found or does not belong to this tenant")

        # Validate plan belongs to tenant and service
        plan_res = await db.execute(
            select(Plan).where(
                Plan.tenant_id == tenant_id,
                Plan.service_id == service_id,
                Plan.id == plan_id,
            )
        )
        if not plan_res.scalar_one_or_none():
            raise ValueError("Plan not found or does not belong to the selected service")

    async def create_subscription(
        self, db: AsyncSession, tenant_id: uuid.UUID, payload: SubscriptionCreate
    ) -> Subscription:
        # 1. Cross-tenant and relationship validation
        await self.validate_ids(
            db, tenant_id, payload.client_id, payload.service_id, payload.plan_id
        )

        # 2. PIN requires Profile logic
        if payload.profile_pin and not payload.profile_name:
            raise ValueError("profile_pin requires profile_name")

        # 3. Expiration calculation
        starts_at = payload.starts_at
        if starts_at.tzinfo is None:
            starts_at = starts_at.replace(tzinfo=timezone.utc)

        expires_at_val = payload.expires_at
        if expires_at_val and expires_at_val.tzinfo is None:
            expires_at_val = expires_at_val.replace(tzinfo=timezone.utc)

        calculated_expires_at = self.calculate_expiration(
            starts_at, payload.duration_type, expires_at_val
        )

        # 4. Encryption
        password_encrypted = encrypt_value(payload.streaming_password)
        pin_encrypted = encrypt_value(payload.profile_pin)

        # 5. Build and save
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

        # Log event
        await self._create_event(db, tenant_id, sub.id, "created", notes="Subscription created")

        await self._commit_change(db, "Failed to create subscription")
        await restore_rls_context(db)
        await db.refresh(sub)
        return sub

    async def get_subscription(
        self, db: AsyncSession, tenant_id: uuid.UUID, subscription_id: uuid.UUID
    ) -> Optional[Subscription]:
        res = await db.execute(
            select(Subscription).where(
                Subscription.tenant_id == tenant_id, Subscription.id == subscription_id
            )
        )
        return res.scalar_one_or_none()

    async def reveal_credentials(
        self, db: AsyncSession, tenant_id: uuid.UUID, subscription_id: uuid.UUID
    ) -> Optional[dict]:
        sub = await self.get_subscription(db, tenant_id, subscription_id)
        if not sub:
            return None
        return {
            "streaming_password": decrypt_value(sub.streaming_password_encrypted),
            "profile_pin": decrypt_value(sub.profile_pin_encrypted),
        }

    async def list_subscriptions(
        self,
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

        # Apply filters
        if status:
            stmt = stmt.where(Subscription.status == status)
        else:
            # Default excludes cancelled subscriptions
            stmt = stmt.where(Subscription.status != "cancelled")

        if client_id:
            stmt = stmt.where(Subscription.client_id == client_id)

        if service_id:
            stmt = stmt.where(Subscription.service_id == service_id)

        # Quick filters
        now = datetime.now(timezone.utc)
        if quick_filter == "expired":
            stmt = stmt.where(Subscription.expires_at < now)
        elif quick_filter == "today":
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            today_end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
            stmt = stmt.where(
                and_(Subscription.expires_at >= today_start, Subscription.expires_at <= today_end)
            )
        elif quick_filter == "next_7_days":
            stmt = stmt.where(
                and_(Subscription.expires_at >= now, Subscription.expires_at <= now + timedelta(days=7))
            )
        elif quick_filter == "next_30_days":
            stmt = stmt.where(
                and_(Subscription.expires_at >= now, Subscription.expires_at <= now + timedelta(days=30))
            )

        # Custom expiration range
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

    async def update_subscription(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        subscription_id: uuid.UUID,
        payload: SubscriptionUpdate,
    ) -> Optional[Subscription]:
        sub = await self.get_subscription(db, tenant_id, subscription_id)
        if not sub:
            return None

        update_data = payload.model_dump(exclude_unset=True)

        # Check if client/service/plan are modified and validate them
        new_client_id = update_data.get("client_id", sub.client_id)
        new_service_id = update_data.get("service_id", sub.service_id)
        new_plan_id = update_data.get("plan_id", sub.plan_id)

        # Editing service must clear/require new plan selection unless selected plan belongs to new service.
        # If service is changing but plan isn't, we need to verify if the old plan belongs to the new service.
        if "service_id" in update_data and "plan_id" not in update_data:
            # Check if current sub.plan_id belongs to new_service_id
            plan_res = await db.execute(
                select(Plan).where(
                    Plan.tenant_id == tenant_id,
                    Plan.service_id == new_service_id,
                    Plan.id == sub.plan_id,
                )
            )
            if not plan_res.scalar_one_or_none():
                raise ValueError("Selected plan does not belong to the new service")

        # Verify new/updated combination
        await self.validate_ids(db, tenant_id, new_client_id, new_service_id, new_plan_id)

        # Update flat fields
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

        # Password empty vs None clear semantics
        if "streaming_password" in update_data:
            pwd = update_data["streaming_password"]
            if pwd is None or pwd == "":
                sub.streaming_password_encrypted = None
            else:
                sub.streaming_password_encrypted = encrypt_value(pwd)

        # PIN empty vs None clear semantics
        if "profile_pin" in update_data:
            pin = update_data["profile_pin"]
            if pin is None or pin == "":
                sub.profile_pin_encrypted = None
            else:
                sub.profile_pin_encrypted = encrypt_value(pin)

        # Validate PIN requires profile_name on the final state
        final_profile_name = sub.profile_name
        final_pin = sub.profile_pin_encrypted
        if final_pin and not final_profile_name:
            raise ValueError("profile_pin requires profile_name")

        # Check if dates or duration are changing
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

            # Re-calculate
            if duration_changed or starts_at_changed:
                calculated_expires = self.calculate_expiration(
                    starts_at_val, duration_val, expires_at_val if expires_at_changed else None
                )
            else:
                calculated_expires = expires_at_val

            sub.starts_at = starts_at_val
            sub.duration_type = duration_val
            sub.expires_at = calculated_expires

        # Log event
        await self._create_event(db, tenant_id, sub.id, "updated", notes="Subscription updated")

        await self._commit_change(db, "Failed to update subscription")
        await restore_rls_context(db)
        await db.refresh(sub)
        return sub

    async def cancel_subscription(
        self, db: AsyncSession, tenant_id: uuid.UUID, subscription_id: uuid.UUID, notes: Optional[str] = None
    ) -> Optional[Subscription]:
        sub = await self.get_subscription(db, tenant_id, subscription_id)
        if not sub:
            return None

        sub.status = "cancelled"
        sub.cancelled_at = datetime.now(timezone.utc)

        await self._create_event(
            db, tenant_id, sub.id, "cancelled", notes=notes or "Subscription cancelled"
        )

        await self._commit_change(db, "Failed to cancel subscription")
        await restore_rls_context(db)
        await db.refresh(sub)
        return sub

    async def reactivate_subscription(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        subscription_id: uuid.UUID,
        duration_type: str,
        starts_at: Optional[datetime] = None,
        expires_at: Optional[datetime] = None,
        notes: Optional[str] = None,
    ) -> Optional[Subscription]:
        sub = await self.get_subscription(db, tenant_id, subscription_id)
        if not sub:
            return None

        starts_at_val = starts_at or datetime.now(timezone.utc)
        if starts_at_val.tzinfo is None:
            starts_at_val = starts_at_val.replace(tzinfo=timezone.utc)

        if expires_at and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        calculated_expires = self.calculate_expiration(starts_at_val, duration_type, expires_at)

        sub.status = "active"
        sub.cancelled_at = None
        sub.starts_at = starts_at_val
        sub.duration_type = duration_type
        sub.expires_at = calculated_expires

        await self._create_event(
            db,
            tenant_id,
            sub.id,
            "reactivated",
            notes=notes or f"Subscription reactivated with duration: {duration_type}",
        )

        await self._commit_change(db, "Failed to reactivate subscription")
        await restore_rls_context(db)
        await db.refresh(sub)
        return sub

    async def renew_subscription(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        subscription_id: uuid.UUID,
        duration_type: str,
        expires_at: Optional[datetime] = None,
        notes: Optional[str] = None,
    ) -> Optional[Subscription]:
        sub = await self.get_subscription(db, tenant_id, subscription_id)
        if not sub:
            return None

        # Renew active subscriptions by extending from current expires_at
        current_expires = sub.expires_at
        if current_expires.tzinfo is None:
            current_expires = current_expires.replace(tzinfo=timezone.utc)

        if expires_at and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        new_expires = self.calculate_expiration(current_expires, duration_type, expires_at)

        sub.status = "active"
        sub.cancelled_at = None
        sub.duration_type = duration_type
        sub.expires_at = new_expires

        await self._create_event(
            db,
            tenant_id,
            sub.id,
            "renewed",
            notes=notes or f"Subscription renewed with duration: {duration_type}",
        )

        await self._commit_change(db, "Failed to renew subscription")
        await restore_rls_context(db)
        await db.refresh(sub)
        return sub

    async def list_subscription_events(
        self, db: AsyncSession, tenant_id: uuid.UUID, subscription_id: uuid.UUID
    ) -> List[SubscriptionEvent]:
        # Quick validation that subscription exists and belongs to tenant
        sub = await self.get_subscription(db, tenant_id, subscription_id)
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

    async def get_reminder_settings(
        self, db: AsyncSession, tenant_id: uuid.UUID
    ) -> SubscriptionReminderSettings:
        res = await db.execute(
            select(SubscriptionReminderSettings).where(
                SubscriptionReminderSettings.tenant_id == tenant_id
            )
        )
        settings = res.scalar_one_or_none()
        if not settings:
            # Create default settings
            settings = SubscriptionReminderSettings(
                tenant_id=tenant_id,
                timezone="UTC",
                warning_days=[7, 3, 1],
                reminder_time="09:00",
                recipient_mode="tenant_only",
            )
            db.add(settings)
            await self._commit_change(db, "Failed to create default reminder settings")
            await restore_rls_context(db)
            await db.refresh(settings)
        return settings

    async def update_reminder_settings(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        payload: SubscriptionReminderSettingsUpdate,
    ) -> SubscriptionReminderSettings:
        settings = await self.get_reminder_settings(db, tenant_id)

        update_data = payload.model_dump(exclude_unset=True)
        if "timezone" in update_data:
            settings.timezone = update_data["timezone"]
        if "warning_days" in update_data:
            settings.warning_days = update_data["warning_days"]
        if "reminder_time" in update_data:
            settings.reminder_time = update_data["reminder_time"]
        if "recipient_mode" in update_data:
            settings.recipient_mode = update_data["recipient_mode"]

        await self._commit_change(db, "Failed to update reminder settings")
        await restore_rls_context(db)
        await db.refresh(settings)
        return settings
