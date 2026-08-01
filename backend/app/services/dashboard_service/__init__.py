"""Dashboard response assembly services."""

from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func, select

from app.models import (
    BlockedClient,
    Client,
    Service,
    Subscription,
    TenantMailbox,
    TenantSettings,
)
from app.models.user import User
from app.repositories import code_services_repository, tenants_repository
from app.schemas.dashboard import (
    ClientActiveSubscription,
    ClientDashboardResponse,
    MasterDashboardResponse,
    TenantDashboardResponse,
)
from app.services.profile_service import ProfileService
from app.services.subscription_service.queries import (
    get_active_subscriptions_for_client,
)


class DashboardService:
    """Build dashboard payloads outside API endpoint layer."""

    def __init__(self, profile_service: ProfileService | None = None) -> None:
        self._profile_service = profile_service or ProfileService()

    async def get_dashboard(self, db, current_user: User):
        """Return role-specific dashboard payload, or ``None`` if profile missing."""
        if current_user.role == "master":
            stats = await tenants_repository.get_stats(db)
            return MasterDashboardResponse(
                total_tenants=stats["total"],
                active_tenants=stats["active"],
                inactive_tenants=stats["inactive"],
            )

        profile = await self._profile_service.get_profile(db, current_user)
        if profile is None:
            return None

        if current_user.role == "client":
            return await self._client_dashboard(db, profile)

        return await self._tenant_dashboard(db, profile)

    async def _tenant_dashboard(self, db, profile) -> TenantDashboardResponse:
        tenant_id = profile.id
        mailbox_status = await self._mailbox_status(db, tenant_id)
        enabled = await code_services_repository.get_effective_service_keys(
            db, tenant_id
        )
        access_count = await self._access_control_count(db, tenant_id)
        payload = TenantDashboardResponse(
            full_name=profile.full_name,
            email=profile.email,
            tenant_plan=profile.plan,
            mailbox_status=mailbox_status,
            enabled_code_services=enabled,
            access_control_count=access_count,
        )
        if profile.plan == "pro":
            payload.active_clients = await self._count(
                db, Client, tenant_id, Client.is_active.is_(True)
            )
            payload.catalog_services = await self._count(db, Service, tenant_id)
            payload.active_subscriptions = await self._count(
                db, Subscription, tenant_id, Subscription.status == "active"
            )
            payload.subscriptions_expiring_soon = (
                await self._subscriptions_expiring_soon(db, tenant_id)
            )
        return payload

    async def _mailbox_status(self, db, tenant_id) -> str:
        row = await db.execute(
            select(TenantMailbox.status).where(TenantMailbox.tenant_id == tenant_id)
        )
        return row.scalar_one_or_none() or "missing"

    async def _access_control_count(self, db, tenant_id) -> int:
        row = await db.execute(
            select(func.count())
            .select_from(BlockedClient)
            .where(BlockedClient.tenant_id == tenant_id)
        )
        return int(row.scalar_one())

    async def _count(self, db, model, tenant_id, *conditions) -> int:
        stmt = (
            select(func.count()).select_from(model).where(model.tenant_id == tenant_id)
        )
        for condition in conditions:
            stmt = stmt.where(condition)
        row = await db.execute(stmt)
        return int(row.scalar_one())

    async def _subscriptions_expiring_soon(self, db, tenant_id) -> int:
        settings_row = await db.execute(
            select(TenantSettings.timezone).where(TenantSettings.tenant_id == tenant_id)
        )
        tz_name = settings_row.scalar_one_or_none() or "UTC"
        try:
            tz = ZoneInfo(tz_name)
        except (KeyError, TypeError, ValueError):
            tz = ZoneInfo("UTC")
        local_today = datetime.now(timezone.utc).astimezone(tz).date()
        start_utc = datetime.combine(local_today, time.min, tzinfo=tz).astimezone(
            timezone.utc
        )
        end_utc = datetime.combine(
            local_today + timedelta(days=7), time.max, tzinfo=tz
        ).astimezone(timezone.utc)
        row = await db.execute(
            select(func.count())
            .select_from(Subscription)
            .where(
                Subscription.tenant_id == tenant_id,
                Subscription.status == "active",
                Subscription.expires_at >= start_utc,
                Subscription.expires_at <= end_utc,
            )
        )
        return int(row.scalar_one())

    async def _client_dashboard(self, db, profile) -> ClientDashboardResponse:
        tenant = getattr(profile, "tenant", None)
        subs = await get_active_subscriptions_for_client(
            db, profile.tenant_id, profile.id
        )
        subscriptions = [
            ClientActiveSubscription(
                id=sub.id,
                service_name=sub.service.name if sub.service else "—",
                service_icon=sub.service.icon if sub.service else None,
                plan_name=sub.plan.name if sub.plan else "—",
                status=sub.status,
                starts_at=sub.starts_at,
                expires_at=sub.expires_at,
            )
            for sub in subs
        ]
        return ClientDashboardResponse(
            id=profile.id,
            full_name=profile.full_name,
            username=profile.username,
            phone=profile.phone,
            tenant_id=profile.tenant_id,
            tenant_name=getattr(tenant, "name", ""),
            client_prefix=getattr(tenant, "client_prefix", ""),
            is_active=profile.is_active,
            subscriptions=subscriptions,
        )
