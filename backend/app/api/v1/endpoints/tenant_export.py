"""Master-scoped Tenant Data Export endpoints — request, status, cancel, download.

These endpoints allow the Master to export data for any Tenant (active or
inactive) from the Master Dashboard without requiring an active support
context.

The Master enters their own password before creating a job (step-up),
shares the same account-level job and cooldown as the Tenant Admin, and
receives localized role labels in the export metadata.
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.api.dependencies import CurrentUser, DbDep, MasterUser
from app.core.database import set_internal_rls_context
from app.core.security import verify_password
from app.repositories import tenants_repository, users_repository
from app.services import export_service
from app.services.step_up_limiter import StepUpError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tenants/{tenant_id}/export", tags=["tenant-export"])


class MasterExportRequest(BaseModel):
    """Password step-up payload for Master-initiated exports."""

    password: str


async def _validate_tenant(
    db: DbDep,
    tenant_id: UUID,
    current_user: CurrentUser,
) -> None:
    """Validate the target tenant exists (active or inactive).

    Sets internal RLS context for the operation to avoid cross-tenant
    leakage when querying tenant-owned data.
    """
    tenant = await tenants_repository.get(db, tenant_id)
    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )
    # Set safe internal RLS context — bypasses the active-tenant gate
    # so the worker can read the target tenant's data safely.
    await set_internal_rls_context(db)


async def _verify_master_password(
    db: DbDep,
    current_user: CurrentUser,
    password: str,
) -> None:
    """Verify the Master's password with step-up rate limiting.

    Raises HTTPException on failure or too many attempts.
    Uses the same three-attempt/fifteen-minute fail-closed limiter
    as Tenant Admin export.
    """
    limiter = export_service.get_limiter()

    # Check rate limit first (fail-closed when Redis is unavailable)
    if limiter is not None:
        try:
            await limiter.check(str(current_user.id))
        except StepUpError as exc:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=str(exc),
            ) from exc

    # Verify password
    master_user = await users_repository.get(db, current_user.id)
    if master_user is None or not verify_password(password, master_user.password_hash):
        # Record failure
        if limiter is not None:
            try:
                await limiter.record_failure(str(current_user.id))
            except StepUpError:
                pass  # Fail closed on the check path; record is best-effort
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Master password",
        )

    # Success — reset counter
    if limiter is not None:
        try:
            await limiter.record_success(str(current_user.id))
        except StepUpError:
            pass  # Success should succeed even if Redis is down


@router.post("", status_code=status.HTTP_201_CREATED)
async def master_request_export(
    body: MasterExportRequest,
    tenant_id: UUID,
    db: DbDep,
    current_user: MasterUser,
):
    """Request a Tenant Data Export as Master for the specified Tenant.

    Verifies the Master's password via step-up, validates the target
    Tenant (active or inactive), and creates a shared account-level
    export job visible to both Master and Tenant Admin.
    """
    await _validate_tenant(db, tenant_id, current_user)
    await _verify_master_password(db, current_user, body.password)

    try:
        job = await export_service.request_export(
            db,
            tenant_id=tenant_id,
            actor_id=current_user.id,
            actor_role="master",
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    # Build the enriched response
    enriched = await export_service.get_current_export(
        db,
        tenant_id=tenant_id,
    )
    if enriched is None:
        return {
            "id": str(job.id),
            "tenant_id": str(job.tenant_id),
            "status": job.status,
            "created_at": job.created_at.isoformat() if job.created_at else None,
        }

    return enriched


@router.get("")
async def master_get_export_status(
    tenant_id: UUID,
    db: DbDep,
    current_user: MasterUser,
):
    """Get the latest export status for the specified Tenant.

    Returns 204 No Content when no export job exists.
    """
    await _validate_tenant(db, tenant_id, current_user)

    enriched = await export_service.get_current_export(
        db,
        tenant_id=tenant_id,
    )
    if enriched is None:
        raise HTTPException(status_code=status.HTTP_204_NO_CONTENT)

    return enriched


@router.post("/cancel")
async def master_cancel_export(
    tenant_id: UUID,
    db: DbDep,
    current_user: MasterUser,
):
    """Cancel the current pending or processing export for the specified Tenant.

    Only pending or processing jobs can be cancelled.
    """
    await _validate_tenant(db, tenant_id, current_user)

    job = await export_service.cancel_export(
        db,
        tenant_id=tenant_id,
        actor_id=current_user.id,
    )
    if job is None:
        latest = await export_service.get_current_export(
            db,
            tenant_id=tenant_id,
        )
        if latest is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No export job to cancel",
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot cancel export in state '{latest['status']}'",
        )

    return {"status": "cancelled", "id": str(job.id)}


@router.get("/download")
async def master_download_export(
    tenant_id: UUID,
    db: DbDep,
    current_user: MasterUser,
):
    """Get a presigned download URL for the specified Tenant's latest ready export.

    Authorizes the Master role and exact target Tenant before signing.
    Returns 404 when no ready export exists.
    """
    await _validate_tenant(db, tenant_id, current_user)

    result = await export_service.get_download_url(
        db,
        tenant_id=tenant_id,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No ready export available",
        )

    return result
