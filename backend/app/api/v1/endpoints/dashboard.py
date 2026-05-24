from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import CurrentUser, DbDep
from app.repositories import tenants_repository
from app.schemas.dashboard import (
    ClientDashboardResponse,
    MasterDashboardResponse,
    TenantDashboardResponse,
)
from app.services.profile_service import ProfileService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
profile_service = ProfileService()


@router.get(
    "",
    response_model=MasterDashboardResponse | TenantDashboardResponse | ClientDashboardResponse,
)
async def get_dashboard(db: DbDep, current_user: CurrentUser):
    if current_user.role == "master":
        stats = await tenants_repository.get_stats(db)
        return MasterDashboardResponse(
            total_tenants=stats["total"],
            active_tenants=stats["active"],
            inactive_tenants=stats["inactive"],
        )

    profile = await profile_service.get_profile(db, current_user)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found"
        )
    if current_user.role == "client":
        tenant = getattr(profile, "tenant", None)
        return ClientDashboardResponse(
            id=profile.id,
            full_name=profile.full_name,
            username=profile.username,
            phone=profile.phone,
            tenant_id=profile.tenant_id,
            tenant_name=getattr(tenant, "name", ""),
            client_prefix=getattr(tenant, "client_prefix", ""),
            is_active=profile.is_active,
        )
    return TenantDashboardResponse(full_name=profile.full_name, email=profile.email)
