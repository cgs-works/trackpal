import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import HTTPException, status
from pydantic import BaseModel

from app.api.dependencies import CurrentUser, DbDep, ProTenantId, resolve_locale
from app.core.errors import UserFacingError, translate_error
from app.core.i18n import t as _t
from app.schemas.subscription import (
    SubscriptionResponse,
    SubscriptionEventResponse,
)
from app.services.subscription_service import SubscriptionService
from app.api.v1.endpoints.subscriptions._common import require_tenant_or_master
from app.api.v1.endpoints.subscriptions.router import router

subscription_service = SubscriptionService()


class CancelRequest(BaseModel):
    notes: Optional[str] = None


class ReactivateRequest(BaseModel):
    duration_type: str
    starts_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    notes: Optional[str] = None


class RenewRequest(BaseModel):
    duration_type: str
    expires_at: Optional[datetime] = None
    notes: Optional[str] = None


@router.post("/{subscription_id}/cancel", response_model=SubscriptionResponse)
@router.patch("/{subscription_id}/cancel", response_model=SubscriptionResponse)
async def cancel_subscription(
    subscription_id: uuid.UUID,
    payload: CancelRequest,
    db: DbDep,
    tenant_id: ProTenantId,
    current_user: CurrentUser,
):
    require_tenant_or_master(current_user)
    sub = await subscription_service.cancel_subscription(
        db, tenant_id, subscription_id, notes=payload.notes
    )
    if sub is None:
        locale = await resolve_locale(db, tenant_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_t(locale, "errors.subscription_not_found"),
        )
    return sub


@router.post("/{subscription_id}/reactivate", response_model=SubscriptionResponse)
@router.patch("/{subscription_id}/reactivate", response_model=SubscriptionResponse)
async def reactivate_subscription(
    subscription_id: uuid.UUID,
    payload: ReactivateRequest,
    db: DbDep,
    tenant_id: ProTenantId,
    current_user: CurrentUser,
):
    require_tenant_or_master(current_user)
    try:
        sub = await subscription_service.reactivate_subscription(
            db,
            tenant_id,
            subscription_id,
            duration_type=payload.duration_type,
            starts_at=payload.starts_at,
            expires_at=payload.expires_at,
            notes=payload.notes,
        )
    except UserFacingError as exc:
        locale = await resolve_locale(db, tenant_id)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=translate_error(locale, exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    if sub is None:
        locale = await resolve_locale(db, tenant_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_t(locale, "errors.subscription_not_found"),
        )
    return sub


@router.post("/{subscription_id}/renew", response_model=SubscriptionResponse)
@router.patch("/{subscription_id}/renew", response_model=SubscriptionResponse)
async def renew_subscription(
    subscription_id: uuid.UUID,
    payload: RenewRequest,
    db: DbDep,
    tenant_id: ProTenantId,
    current_user: CurrentUser,
):
    require_tenant_or_master(current_user)
    try:
        sub = await subscription_service.renew_subscription(
            db,
            tenant_id,
            subscription_id,
            duration_type=payload.duration_type,
            expires_at=payload.expires_at,
            notes=payload.notes,
        )
    except UserFacingError as exc:
        locale = await resolve_locale(db, tenant_id)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=translate_error(locale, exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    if sub is None:
        locale = await resolve_locale(db, tenant_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_t(locale, "errors.subscription_not_found"),
        )
    return sub


@router.get("/{subscription_id}/events", response_model=List[SubscriptionEventResponse])
async def list_subscription_events(
    subscription_id: uuid.UUID,
    db: DbDep,
    tenant_id: ProTenantId,
    current_user: CurrentUser,
):
    require_tenant_or_master(current_user)
    return await subscription_service.list_subscription_events(
        db, tenant_id, subscription_id
    )
