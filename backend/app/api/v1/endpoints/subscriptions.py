import uuid
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, status, Response
from pydantic import BaseModel

from app.api.dependencies import ActiveTenantId, ApiKeyDbDep, CurrentUser, DbDep, resolve_locale
from app.core.errors import UserFacingError, translate_error
from app.core.i18n import t as _t
from app.schemas.subscription import (
    MarkFailedRequest,
    ReminderPendingResponse,
    SubscriptionCreate,
    SubscriptionUpdate,
    SubscriptionResponse,
    SubscriptionEventResponse,
    SubscriptionReminderSettingsResponse,
    SubscriptionReminderSettingsUpdate,
    SubscriptionRevealResponse,
)
from app.services.subscription_job_service import SubscriptionJobService
from app.services.subscription_service import SubscriptionService

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])
settings_router = APIRouter(
    prefix="/subscription-settings", tags=["subscription-settings"]
)

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


@router.post(
    "", response_model=SubscriptionResponse, status_code=status.HTTP_201_CREATED
)
async def create_subscription(
    payload: SubscriptionCreate,
    db: DbDep,
    tenant_id: ActiveTenantId,
    current_user: CurrentUser,
):
    _require_tenant_or_master_in_context(current_user)
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
        locale = await resolve_locale(db, tenant_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=_t(locale, "errors.subscription_not_found")
        )
    return sub


@router.get("/{subscription_id}/reveal", response_model=SubscriptionRevealResponse)
async def reveal_subscription_credentials(
    subscription_id: uuid.UUID,
    db: DbDep,
    tenant_id: ActiveTenantId,
    current_user: CurrentUser,
):
    _require_tenant_or_master_in_context(current_user)
    creds = await subscription_service.reveal_credentials(
        db, tenant_id, subscription_id
    )
    if creds is None:
        locale = await resolve_locale(db, tenant_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=_t(locale, "errors.subscription_not_found")
        )
    return creds


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
            status_code=status.HTTP_404_NOT_FOUND, detail=_t(locale, "errors.subscription_not_found")
        )
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
            status_code=status.HTTP_404_NOT_FOUND, detail=_t(locale, "errors.subscription_not_found")
        )
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
    sub = await subscription_service.cancel_subscription(
        db, tenant_id, subscription_id, notes=payload.notes
    )
    if sub is None:
        locale = await resolve_locale(db, tenant_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=_t(locale, "errors.subscription_not_found")
        )
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
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    if sub is None:
        locale = await resolve_locale(db, tenant_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=_t(locale, "errors.subscription_not_found")
        )
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
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    if sub is None:
        locale = await resolve_locale(db, tenant_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=_t(locale, "errors.subscription_not_found")
        )
    return sub


@router.get("/{subscription_id}/events", response_model=List[SubscriptionEventResponse])
async def list_subscription_events(
    subscription_id: uuid.UUID,
    db: DbDep,
    tenant_id: ActiveTenantId,
    current_user: CurrentUser,
):
    _require_tenant_or_master_in_context(current_user)
    return await subscription_service.list_subscription_events(
        db, tenant_id, subscription_id
    )


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
        return await subscription_service.update_reminder_settings(
            db, tenant_id, payload
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc


# Subscription Jobs Endpoint

jobs_router = APIRouter(prefix="/subscriptions", tags=["subscriptions-jobs"])

subscription_job_service = SubscriptionJobService()


@jobs_router.post("/jobs")
async def run_subscription_job(
    db: ApiKeyDbDep,
    task: str = "cleanup",
):
    """Run a subscription lifecycle job.

    Protected by ``N8N_API_KEY`` header.  Supported tasks:
    - ``cleanup``: expire/cancel/delete lifecycle transitions.
    - ``reminders``: placeholder (separate TODO).
    - ``all``: run both.

    Returns per-item results with IDs, action, status, and optional error.
    No PII or secrets are returned.
    """
    if task not in ("cleanup", "reminders", "all"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid task '{task}'. Must be one of: cleanup, reminders, all",
        )

    results: list[dict] = []

    if task in ("cleanup", "all"):
        cleanup_results = await subscription_job_service.run_cleanup(db)
        results.extend(cleanup_results)

    if task in ("reminders", "all"):
        reminder_results = await subscription_job_service.run_reminders_stub()
        results.extend(reminder_results)

    return {"task": task, "items_processed": len(results), "results": results}


# Reminder Generation Endpoints

reminders_router = APIRouter(
    prefix="/subscriptions/reminders", tags=["subscriptions-reminders"]
)


@reminders_router.post("/pending", response_model=ReminderPendingResponse)
async def get_pending_reminders(
    db: ApiKeyDbDep,
    cursor: Optional[str] = None,
    page_size: int = 100,
):
    """Generate and return pending reminder payloads.

    Protected by ``N8N_API_KEY`` header.  Returns at most ``page_size``
    payloads (default 100).  If more pages exist, includes an opaque
    ``next_cursor``.
    """
    if page_size < 1 or page_size > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="page_size must be between 1 and 100",
        )
    result = await subscription_job_service.generate_reminder_payloads(
        db, cursor=cursor, page_size=page_size
    )
    return result


@reminders_router.post("/{log_id}/mark-sent")
async def mark_reminder_sent(
    db: ApiKeyDbDep,
    log_id: uuid.UUID,
):
    """Mark a reminder log as sent after n8n confirms Evolution success."""
    locale = "en"  # API-key flow; no tenant context to resolve locale
    result = await subscription_job_service.mark_reminder_sent(db, log_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_t(locale, "errors.reminder_log_not_found"),
        )
    return result


@reminders_router.post("/{log_id}/mark-failed")
async def mark_reminder_failed(
    db: ApiKeyDbDep,
    log_id: uuid.UUID,
    payload: MarkFailedRequest,
):
    """Mark a reminder log as failed after Evolution send failure.

    Retries up to 3 attempts before setting permanent ``failed`` status.
    """
    locale = "en"  # API-key flow; no tenant context to resolve locale
    result = await subscription_job_service.mark_reminder_failed(
        db, log_id, reason=payload.reason
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_t(locale, "errors.reminder_log_not_found"),
        )
    return result
