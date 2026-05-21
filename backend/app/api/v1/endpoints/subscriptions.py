import uuid
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, status, Response
from pydantic import BaseModel

from app.api.dependencies import ActiveTenantId, CurrentUser, DbDep
from app.schemas.subscription import (
    SubscriptionCreate,
    SubscriptionUpdate,
    SubscriptionResponse,
    SubscriptionEventResponse,
    SubscriptionReminderSettingsResponse,
    SubscriptionReminderSettingsUpdate,
)
from app.services.subscription_service import SubscriptionService

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])
settings_router = APIRouter(prefix="/subscription-settings", tags=["subscription-settings"])

subscription_service = SubscriptionService()


def _require_tenant_or_master_in_context(current_user: CurrentUser) -> None:
    if current_user.role not in ("tenant", "master"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Role 'tenant' or 'master' required",
        )


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


# Subscriptions Endpoints

@router.post("", response_model=SubscriptionResponse, status_code=status.HTTP_201_CREATED)
async def create_subscription(
    payload: SubscriptionCreate,
    db: DbDep,
    tenant_id: ActiveTenantId,
    current_user: CurrentUser,
):
    _require_tenant_or_master_in_context(current_user)
    try:
        return await subscription_service.create_subscription(db, tenant_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("", response_model=List[SubscriptionResponse])
async def list_subscriptions(
    db: DbDep,
    tenant_id: ActiveTenantId,
    current_user: CurrentUser,
    status: Optional[str] = None,
    client_id: Optional[uuid.UUID] = None,
    service_id: Optional[uuid.UUID] = None,
    quick_filter: Optional[str] = None,
    expires_from: Optional[datetime] = None,
    expires_to: Optional[datetime] = None,
):
    _require_tenant_or_master_in_context(current_user)
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
    tenant_id: ActiveTenantId,
    current_user: CurrentUser,
):
    _require_tenant_or_master_in_context(current_user)
    sub = await subscription_service.get_subscription(db, tenant_id, subscription_id)
    if sub is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")
    return sub


@router.put("/{subscription_id}", response_model=SubscriptionResponse)
async def update_subscription(
    subscription_id: uuid.UUID,
    payload: SubscriptionUpdate,
    db: DbDep,
    tenant_id: ActiveTenantId,
    current_user: CurrentUser,
):
    _require_tenant_or_master_in_context(current_user)
    try:
        sub = await subscription_service.update_subscription(db, tenant_id, subscription_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if sub is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")
    return sub


@router.patch("/{subscription_id}", response_model=SubscriptionResponse)
async def patch_subscription(
    subscription_id: uuid.UUID,
    payload: SubscriptionUpdate,
    db: DbDep,
    tenant_id: ActiveTenantId,
    current_user: CurrentUser,
):
    _require_tenant_or_master_in_context(current_user)
    try:
        sub = await subscription_service.update_subscription(db, tenant_id, subscription_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if sub is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")
    return sub


@router.post("/{subscription_id}/cancel", response_model=SubscriptionResponse)
@router.patch("/{subscription_id}/cancel", response_model=SubscriptionResponse)
async def cancel_subscription(
    subscription_id: uuid.UUID,
    payload: CancelRequest,
    db: DbDep,
    tenant_id: ActiveTenantId,
    current_user: CurrentUser,
):
    _require_tenant_or_master_in_context(current_user)
    sub = await subscription_service.cancel_subscription(db, tenant_id, subscription_id, notes=payload.notes)
    if sub is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")
    return sub


@router.post("/{subscription_id}/reactivate", response_model=SubscriptionResponse)
@router.patch("/{subscription_id}/reactivate", response_model=SubscriptionResponse)
async def reactivate_subscription(
    subscription_id: uuid.UUID,
    payload: ReactivateRequest,
    db: DbDep,
    tenant_id: ActiveTenantId,
    current_user: CurrentUser,
):
    _require_tenant_or_master_in_context(current_user)
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
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if sub is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")
    return sub


@router.post("/{subscription_id}/renew", response_model=SubscriptionResponse)
@router.patch("/{subscription_id}/renew", response_model=SubscriptionResponse)
async def renew_subscription(
    subscription_id: uuid.UUID,
    payload: RenewRequest,
    db: DbDep,
    tenant_id: ActiveTenantId,
    current_user: CurrentUser,
):
    _require_tenant_or_master_in_context(current_user)
    try:
        sub = await subscription_service.renew_subscription(
            db,
            tenant_id,
            subscription_id,
            duration_type=payload.duration_type,
            expires_at=payload.expires_at,
            notes=payload.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if sub is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")
    return sub


@router.get("/{subscription_id}/events", response_model=List[SubscriptionEventResponse])
async def list_subscription_events(
    subscription_id: uuid.UUID,
    db: DbDep,
    tenant_id: ActiveTenantId,
    current_user: CurrentUser,
):
    _require_tenant_or_master_in_context(current_user)
    return await subscription_service.list_subscription_events(db, tenant_id, subscription_id)


# Subscription Settings Endpoints

@settings_router.get("", response_model=SubscriptionReminderSettingsResponse)
async def get_reminder_settings(
    db: DbDep,
    tenant_id: ActiveTenantId,
    current_user: CurrentUser,
):
    _require_tenant_or_master_in_context(current_user)
    return await subscription_service.get_reminder_settings(db, tenant_id)


@settings_router.put("", response_model=SubscriptionReminderSettingsResponse)
async def update_reminder_settings(
    payload: SubscriptionReminderSettingsUpdate,
    db: DbDep,
    tenant_id: ActiveTenantId,
    current_user: CurrentUser,
):
    _require_tenant_or_master_in_context(current_user)
    try:
        return await subscription_service.update_reminder_settings(db, tenant_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
