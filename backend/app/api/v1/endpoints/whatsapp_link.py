"""FastAPI router for tenant WhatsApp self-linking endpoints.

All endpoints require a valid JWT, active tenant context, and either
tenant (admin) or master role.  Pro plan is enforced for tenant users;
master support bypasses the plan gate.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Annotated

from app.api.dependencies import (
    ActiveTenantId,
    CurrentUser,
    DbDep,
    TenantPlanDep,
)
from app.core.errors import UserFacingError, translate_error
from app.core.tenant_plan import TENANT_PLAN_PRO
from app.schemas.whatsapp_link import (
    WhatsAppDisconnectResponse,
    WhatsAppLinkStatusResponse,
    WhatsAppPairRequest,
    WhatsAppPairResponse,
    WhatsAppQrResponse,
)
from app.services.whatsapp_link_service import WhatsAppLinkService

router = APIRouter(prefix="/tenant/whatsapp-link", tags=["tenant-whatsapp-link"])

service = WhatsAppLinkService()

# ── Error-code → HTTP status mapping ─────────────────────────────────────

ERROR_STATUS: dict[str, int] = {
    "whatsapp_link.instance_not_configured": status.HTTP_400_BAD_REQUEST,
    "whatsapp_link.phone_required": status.HTTP_400_BAD_REQUEST,
    "whatsapp_link.already_connected": status.HTTP_409_CONFLICT,
    "whatsapp_link.service_unavailable": status.HTTP_503_SERVICE_UNAVAILABLE,
    "whatsapp_link.invalid_instance_token": status.HTTP_502_BAD_GATEWAY,
    "whatsapp_link.request_failed": status.HTTP_502_BAD_GATEWAY,
}

DEFAULT_ERROR_STATUS = status.HTTP_502_BAD_GATEWAY


# ── Authorization dependency ─────────────────────────────────────────────


async def _check_role_and_plan(
    current_user: CurrentUser,
    tenant_plan: TenantPlanDep,
) -> None:
    """Reject client role and enforce Pro plan for tenant users.

    Master support context bypasses the plan gate.
    """
    if current_user.role not in ("tenant", "master"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Role 'tenant' or 'master' required",
        )

    if current_user.role == "tenant" and tenant_plan != TENANT_PLAN_PRO:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Not found"
        )


AuthDep = Annotated[None, Depends(_check_role_and_plan)]


# ── Error handler helper ─────────────────────────────────────────────────


def _handle_user_error(
    exc: UserFacingError, locale: str
) -> HTTPException:
    """Convert a ``UserFacingError`` to an ``HTTPException`` with the
    correct status code and translated message."""
    http_status = ERROR_STATUS.get(exc.code, DEFAULT_ERROR_STATUS)
    detail = translate_error(locale, exc)
    return HTTPException(status_code=http_status, detail=detail)


async def _resolve_locale(db: DbDep, tenant_id: ActiveTenantId) -> str:
    """Resolve the tenant locale for error translations."""
    from app.api.dependencies import resolve_locale
    return await resolve_locale(db, tenant_id)


# ── Endpoints ────────────────────────────────────────────────────────────


@router.get("/status", response_model=WhatsAppLinkStatusResponse)
async def get_status(
    db: DbDep,
    tenant_id: ActiveTenantId,
    current_user: CurrentUser,
    tenant_plan: TenantPlanDep,
    _: AuthDep,
) -> WhatsAppLinkStatusResponse:
    """Return the current WhatsApp connection status for the tenant."""
    locale = await _resolve_locale(db, tenant_id)
    try:
        return await service.get_status(db, tenant_id)
    except UserFacingError as exc:
        raise _handle_user_error(exc, locale) from exc


@router.post("/pair", response_model=WhatsAppPairResponse)
async def pair(
    payload: WhatsAppPairRequest,
    db: DbDep,
    tenant_id: ActiveTenantId,
    current_user: CurrentUser,
    tenant_plan: TenantPlanDep,
    _: AuthDep,
) -> WhatsAppPairResponse:
    """Request an 8-digit pairing code for the tenant's WhatsApp instance.

    The phone number is sourced from ``tenant.whatsapp_phone``.  The request
    body must be empty — any extra fields are rejected.
    """
    locale = await _resolve_locale(db, tenant_id)
    try:
        return await service.request_pairing_code(db, tenant_id)
    except UserFacingError as exc:
        raise _handle_user_error(exc, locale) from exc


@router.get("/qr", response_model=WhatsAppQrResponse)
async def get_qr(
    db: DbDep,
    tenant_id: ActiveTenantId,
    current_user: CurrentUser,
    tenant_plan: TenantPlanDep,
    _: AuthDep,
) -> WhatsAppQrResponse:
    """Retrieve the QR code for WhatsApp Web linking."""
    locale = await _resolve_locale(db, tenant_id)
    try:
        return await service.get_qr_code(db, tenant_id)
    except UserFacingError as exc:
        raise _handle_user_error(exc, locale) from exc


@router.post("/disconnect", response_model=WhatsAppDisconnectResponse)
async def disconnect(
    db: DbDep,
    tenant_id: ActiveTenantId,
    current_user: CurrentUser,
    tenant_plan: TenantPlanDep,
    _: AuthDep,
) -> WhatsAppDisconnectResponse:
    """Log out the WhatsApp instance without deleting it.

    The Evolution instance is preserved so the tenant can re-link later.
    Idempotent: returns 200 even if already disconnected.
    """
    locale = await _resolve_locale(db, tenant_id)
    try:
        return await service.disconnect(db, tenant_id)
    except UserFacingError as exc:
        raise _handle_user_error(exc, locale) from exc
