"""Tenant Settings API — get and update tenant locale/timezone settings."""

from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import ActiveTenantId, CurrentUser, DbDep
from app.api.v1.endpoints.subscriptions._common import require_tenant_or_master
from app.schemas.tenant_settings import TenantSettingsResponse, TenantSettingsUpdate
from app.services.subscription_service.timezone_catalog import list_timezones
from app.services.tenant_settings_service import TenantSettingsService

router = APIRouter(prefix="/tenant-settings", tags=["tenant-settings"])
service = TenantSettingsService()


@router.get("", response_model=TenantSettingsResponse)
async def get_tenant_settings(
    db: DbDep,
    tenant_id: ActiveTenantId,
    current_user: CurrentUser,
):
    require_tenant_or_master(current_user)
    return await service.get_settings(db, tenant_id)


@router.put("", response_model=TenantSettingsResponse)
async def update_tenant_settings(
    payload: TenantSettingsUpdate,
    db: DbDep,
    tenant_id: ActiveTenantId,
    current_user: CurrentUser,
):
    require_tenant_or_master(current_user)
    try:
        return await service.update_settings(db, tenant_id, payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc


@router.get("/timezones")
async def list_supported_timezones(current_user: CurrentUser):
    require_tenant_or_master(current_user)
    return await list_timezones()
