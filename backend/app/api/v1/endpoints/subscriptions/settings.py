from fastapi import HTTPException, status

from app.api.dependencies import ActiveTenantId, CurrentUser, DbDep, resolve_locale
from app.core.errors import UserFacingError, translate_error
from app.schemas.subscription import (
    SubscriptionReminderSettingsResponse,
    SubscriptionReminderSettingsUpdate,
)
from app.services.subscription_service import SubscriptionService
from app.api.v1.endpoints.subscriptions._common import require_tenant_or_master
from app.api.v1.endpoints.subscriptions.router import settings_router

subscription_service = SubscriptionService()


@settings_router.get("", response_model=SubscriptionReminderSettingsResponse)
async def get_reminder_settings(
    db: DbDep,
    tenant_id: ActiveTenantId,
    current_user: CurrentUser,
):
    require_tenant_or_master(current_user)
    return await subscription_service.get_reminder_settings(db, tenant_id)


@settings_router.put("", response_model=SubscriptionReminderSettingsResponse)
async def update_reminder_settings(
    payload: SubscriptionReminderSettingsUpdate,
    db: DbDep,
    tenant_id: ActiveTenantId,
    current_user: CurrentUser,
):
    require_tenant_or_master(current_user)
    try:
        return await subscription_service.update_reminder_settings(
            db, tenant_id, payload
        )
    except UserFacingError as exc:
        locale = await resolve_locale(db, tenant_id)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=translate_error(locale, exc)
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
