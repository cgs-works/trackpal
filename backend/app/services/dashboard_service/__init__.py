"""Dashboard response assembly services."""

from app.models.user import User
from app.repositories import tenants_repository
from app.schemas.dashboard import (
    ClientActiveSubscription,
    ClientDashboardResponse,
    MasterDashboardResponse,
    TenantDashboardResponse,
)
from app.services.profile_service import ProfileService
from app.services.subscription_service.queries import get_active_subscriptions_for_client


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

        return TenantDashboardResponse(full_name=profile.full_name, email=profile.email)

    async def _client_dashboard(self, db, profile) -> ClientDashboardResponse:
        tenant = getattr(profile, "tenant", None)
        subs = await get_active_subscriptions_for_client(db, profile.tenant_id, profile.id)
        subscriptions = [
            ClientActiveSubscription(
                id=sub.id,
                service_name=sub.service.name if sub.service else "—",
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
