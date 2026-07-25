from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import DemoGuardedUser, DbDep
from app.schemas.dashboard import (
    ClientDashboardResponse,
    MasterDashboardResponse,
    TenantDashboardResponse,
)
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
dashboard_service = DashboardService()


@router.get(
    "",
    response_model=MasterDashboardResponse
    | TenantDashboardResponse
    | ClientDashboardResponse,
)
async def get_dashboard(db: DbDep, current_user: DemoGuardedUser):
    dashboard = await dashboard_service.get_dashboard(db, current_user)
    if dashboard is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found"
        )
    return dashboard
