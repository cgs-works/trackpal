"""Tenant Data Export endpoints — request, status, and download."""

from __future__ import annotations


from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import ActiveTenantId, CurrentUser, DbDep
from app.services import export_service
from app.services.step_up_limiter import StepUpError

router = APIRouter(prefix="/me/export", tags=["export"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def request_export(
    db: DbDep,
    current_user: CurrentUser,
    active_tenant_id: ActiveTenantId,
):
    """Request a new Tenant Data Export.

    Requires password step-up authentication (handled separately).
    Creates a pending ExportJob that a background worker will process.
    """
    # Enforce role: only tenant and master (in support context) can export
    if current_user.role not in ("tenant", "master"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Tenant Admins and Master can request exports",
        )

    # Step-up check
    limiter = export_service.get_limiter()
    if limiter is not None:
        try:
            await limiter.check(str(current_user.id))
        except StepUpError as exc:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=str(exc),
            ) from exc

    job = await export_service.request_export(
        db,
        tenant_id=active_tenant_id,
        actor_id=current_user.id,
    )

    return {
        "id": str(job.id),
        "tenant_id": str(job.tenant_id),
        "status": job.status,
        "created_at": job.created_at.isoformat() if job.created_at else None,
    }


@router.get("")
async def get_export_status(
    db: DbDep,
    current_user: CurrentUser,
    active_tenant_id: ActiveTenantId,
):
    """Get the latest export status for the current tenant.

    Returns 204 No Content when no export job exists.
    """
    job = await export_service.get_current_export(
        db,
        tenant_id=active_tenant_id,
    )
    if job is None:
        raise HTTPException(status_code=status.HTTP_204_NO_CONTENT)

    return {
        "id": str(job.id),
        "tenant_id": str(job.tenant_id),
        "status": job.status,
        "attempts": job.attempts,
        "max_attempts": job.max_attempts,
        "error_code": job.error_code,
        "artifact_size_bytes": job.artifact_size_bytes,
        "ready_at": job.ready_at.isoformat() if job.ready_at else None,
        "expires_at": job.expires_at.isoformat() if job.expires_at else None,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
    }


@router.get("/download")
async def download_export(
    db: DbDep,
    current_user: CurrentUser,
    active_tenant_id: ActiveTenantId,
):
    """Get a presigned download URL for the latest ready export.

    Returns 404 when no ready export exists.
    """
    url = await export_service.get_download_url(
        db,
        tenant_id=active_tenant_id,
    )
    if url is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No ready export available",
        )

    return {"url": url}
