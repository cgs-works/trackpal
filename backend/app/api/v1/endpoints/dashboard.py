from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from app.api.dependencies import CurrentUser, DbDep
from app.models import TenantProfile
from app.schemas.dashboard import MasterDashboardResponse, TenantDashboardResponse
from app.services.profile_service import ProfileService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
profile_service = ProfileService()


@router.get("", response_model=MasterDashboardResponse | TenantDashboardResponse)
async def get_dashboard(db: DbDep, current_user: CurrentUser):
    if current_user.role == "master":
        total_result = await db.execute(select(func.count()).select_from(TenantProfile))
        active_result = await db.execute(
            select(func.count()).select_from(TenantProfile).where(TenantProfile.is_active)
        )
        total = total_result.scalar_one()
        active = active_result.scalar_one()
        return MasterDashboardResponse(
            total_tenants=total,
            active_tenants=active,
            inactive_tenants=total - active,
        )

    profile = await profile_service.get_profile(db, current_user)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found"
        )
    return TenantDashboardResponse(full_name=profile.full_name, email=profile.email)
