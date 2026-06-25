import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import HTTPException, status

from app.api.dependencies import CurrentUser, DbDep, ProTenantId, resolve_locale
from app.core.errors import UserFacingError, translate_error
from app.core.i18n import t as _t
from app.schemas.subscription import (
    SubscriptionCreate,
    SubscriptionUpdate,
    SubscriptionResponse,
    SubscriptionRevealResponse,
)
from app.services.subscription_service import SubscriptionService
from app.api.v1.endpoints.subscriptions._common import require_tenant_or_master
from app.api.v1.endpoints.subscriptions.router import router

subscription_service = SubscriptionService()


@router.post(
    "", response_model=SubscriptionResponse, status_code=status.HTTP_201_CREATED
)
async def create_subscription(
    payload: SubscriptionCreate,
    db: DbDep,
    tenant_id: ProTenantId,
    current_user: CurrentUser,
):
    require_tenant_or_master(current_user)
    try:
        return await subscription_service.create_subscription(db, tenant_id, payload)
    except UserFacingError as exc:
        locale = await resolve_locale(db, tenant_id)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=translate_error(locale, exc)
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc


@router.get("", response_model=List[SubscriptionResponse])
async def list_subscriptions(
    db: DbDep,
    tenant_id: ProTenantId,
    current_user: CurrentUser,
    status: Optional[str] = None,
    client_id: Optional[uuid.UUID] = None,
    service_id: Optional[uuid.UUID] = None,
    quick_filter: Optional[str] = None,
    expires_from: Optional[datetime] = None,
    expires_to: Optional[datetime] = None,
):
    require_tenant_or_master(current_user)
    return await subscription_service.list_subscriptions(
        db,
        tenant_id=tenant_id,
        status=status,
        client_id=client_id,
        service_id=service_id,
        quick_filter=quick_filter,
        expires_from=expires_from,
        expires_to=expires_to,
    )


@router.get("/{subscription_id}", response_model=SubscriptionResponse)
async def get_subscription(
    subscription_id: uuid.UUID,
    db: DbDep,
    tenant_id: ProTenantId,
    current_user: CurrentUser,
):
    require_tenant_or_master(current_user)
    sub = await subscription_service.get_subscription(db, tenant_id, subscription_id)
    if sub is None:
        locale = await resolve_locale(db, tenant_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_t(locale, "errors.subscription_not_found"),
        )
    return sub


@router.get("/{subscription_id}/reveal", response_model=SubscriptionRevealResponse)
async def reveal_subscription_credentials(
    subscription_id: uuid.UUID,
    db: DbDep,
    tenant_id: ProTenantId,
    current_user: CurrentUser,
):
    require_tenant_or_master(current_user)
    creds = await subscription_service.reveal_credentials(
        db, tenant_id, subscription_id
    )
    if creds is None:
        locale = await resolve_locale(db, tenant_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_t(locale, "errors.subscription_not_found"),
        )
    return creds


@router.put("/{subscription_id}", response_model=SubscriptionResponse)
async def update_subscription(
    subscription_id: uuid.UUID,
    payload: SubscriptionUpdate,
    db: DbDep,
    tenant_id: ProTenantId,
    current_user: CurrentUser,
):
    require_tenant_or_master(current_user)
    try:
        sub = await subscription_service.update_subscription(
            db, tenant_id, subscription_id, payload
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
    if sub is None:
        locale = await resolve_locale(db, tenant_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_t(locale, "errors.subscription_not_found"),
        )
    return sub


@router.patch("/{subscription_id}", response_model=SubscriptionResponse)
async def patch_subscription(
    subscription_id: uuid.UUID,
    payload: SubscriptionUpdate,
    db: DbDep,
    tenant_id: ProTenantId,
    current_user: CurrentUser,
):
    require_tenant_or_master(current_user)
    try:
        sub = await subscription_service.update_subscription(
            db, tenant_id, subscription_id, payload
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
    if sub is None:
        locale = await resolve_locale(db, tenant_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_t(locale, "errors.subscription_not_found"),
        )
    return sub
