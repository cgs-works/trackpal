"""Tenant Data Export orchestration — create, claim, and finalise exports."""

from __future__ import annotations


from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import export_jobs_repository
from app.services.export_storage import (
    ExportStorageAdapter,
    FakeExportStorageAdapter,
)
from app.services.step_up_limiter import StepUpRateLimiter
from uuid import UUID

from app.models.export_job import ExportJob

EXPORT_TTL_HOURS = 72


# Module-level storage adapter — wired from tests or lifespan
_export_storage: ExportStorageAdapter | None = None

# Module-level step-up limiter — wired from tests or lifespan
_step_up_limiter: StepUpRateLimiter | None = None


def configure_export_service(
    storage: ExportStorageAdapter,
    limiter: StepUpRateLimiter | None = None,
) -> None:
    """Set the active storage adapter and optional rate limiter."""
    global _export_storage, _step_up_limiter
    _export_storage = storage
    _step_up_limiter = limiter


def get_storage() -> ExportStorageAdapter:
    global _export_storage
    if _export_storage is None:
        _export_storage = FakeExportStorageAdapter()
    return _export_storage


def get_limiter() -> StepUpRateLimiter | None:
    return _step_up_limiter


async def request_export(
    db: AsyncSession,
    tenant_id: UUID,
    actor_id: UUID,
) -> ExportJob:
    """Create a new export job for the tenant.

    Returns the pending ExportJob.
    """
    job = await export_jobs_repository.create(
        db,
        tenant_id=tenant_id,
        requested_by=actor_id,
    )
    return job


async def get_current_export(
    db: AsyncSession,
    tenant_id: UUID,
) -> ExportJob | None:
    """Get the latest export job for the tenant (if any)."""
    return await export_jobs_repository.get_latest_by_tenant(db, tenant_id)


async def get_ready_export(
    db: AsyncSession,
    tenant_id: UUID,
) -> ExportJob | None:
    """Get the latest ready, unexpired export for the tenant."""
    return await export_jobs_repository.get_ready_by_tenant(db, tenant_id)


async def get_download_url(
    db: AsyncSession,
    tenant_id: UUID,
) -> str | None:
    """Get a presigned download URL for the tenant's ready export.

    Returns None if no ready export exists.
    """
    job = await get_ready_export(db, tenant_id)
    if job is None or job.r2_key is None:
        return None

    storage = get_storage()
    url = await storage.generate_presigned_get(
        key=job.r2_key,
        expires_in_seconds=900,  # 15 minutes
    )
    return url


__all__ = [
    "EXPORT_TTL_HOURS",
    "configure_export_service",
    "get_storage",
    "get_limiter",
    "request_export",
    "get_current_export",
    "get_ready_export",
    "get_download_url",
]
