"""Tenant Data Export endpoints — request, status, cancel, and download."""

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
    Enforces 24-hour cooldown and links replacement chain.
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

    try:
        job = await export_service.request_export(
            db,
            tenant_id=active_tenant_id,
            actor_id=current_user.id,
            actor_role=current_user.role,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    # Build response from the service's enriched format
    enriched = await export_service.get_current_export(db, tenant_id=active_tenant_id)
    if enriched is None:
        return {
            "id": str(job.id),
            "tenant_id": str(job.tenant_id),
            "status": job.status,
            "created_at": job.created_at.isoformat() if job.created_at else None,
        }

    return enriched


@router.get("")
async def get_export_status(
    db: DbDep,
    current_user: CurrentUser,
    active_tenant_id: ActiveTenantId,
):
    """Get the latest export status with enriched metadata.

    Returns 204 No Content when no export job exists.
    """
    enriched = await export_service.get_current_export(
        db,
        tenant_id=active_tenant_id,
    )
    if enriched is None:
        raise HTTPException(status_code=status.HTTP_204_NO_CONTENT)

    return enriched


@router.post("/cancel")
async def cancel_export(
    db: DbDep,
    current_user: CurrentUser,
    active_tenant_id: ActiveTenantId,
):
    """Cancel the current pending or processing export.

    Only pending or processing jobs can be cancelled.  Partial uploads
    from a processing job are purged from storage.
    """
    if current_user.role not in ("tenant", "master"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Tenant Admins and Master can cancel exports",
        )

    job = await export_service.cancel_export(
        db,
        tenant_id=active_tenant_id,
        actor_id=current_user.id,
    )
    if job is None:
        # Could be no job or job not in cancellable state
        latest = await export_service.get_current_export(db, tenant_id=active_tenant_id)
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
async def download_export(
    db: DbDep,
    current_user: CurrentUser,
    active_tenant_id: ActiveTenantId,
):
    """Get a presigned download URL for the latest ready export.

    Returns 404 when no ready export exists.
    URL expiry is capped to min(15 minutes, remaining object lifetime).
    """
    result = await export_service.get_download_url(
        db,
        tenant_id=active_tenant_id,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No ready export available",
        )

    return result
