"""Tenant Data Export orchestration — create, claim, cancel, and finalise exports.

Handles the full lifecycle: creation with cooldown enforcement, 30-minute
recoverable leases, 3 retries with backoff, cancellation with worker
checkpoints, replacement with previous-artifact preservation, 72-hour
ready/failed expiry, and safe R2 cleanup.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.export_job import ExportJob
from app.repositories import export_jobs_repository
from app.services.export_storage import (
    ExportStorageAdapter,
    StorageObjectNotFoundError,
    StorageOperationError,
)
from app.services.step_up_limiter import StepUpRateLimiter

logger = logging.getLogger(__name__)

EXPORT_TTL_HOURS = 72
COOLDOWN_HOURS = 24
SIGNED_URL_TTL_SECONDS = 900  # 15 minutes


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
    if _export_storage is None:
        raise RuntimeError("Export storage is not configured")
    return _export_storage


def get_limiter() -> StepUpRateLimiter | None:
    return _step_up_limiter


# ── Cooldown helpers ───────────────────────────────────────────


def _ensure_tz(dt: datetime | None) -> datetime | None:
    """Ensure a datetime is timezone-aware; assume UTC if naive."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _now() -> datetime:
    """Return current UTC time as an aware datetime."""
    return datetime.now(timezone.utc)


def _compute_cooldown_until() -> datetime:
    """Return the timestamp for the end of the 24-hour cooldown."""
    return _now() + timedelta(hours=COOLDOWN_HOURS)


def _cap_signed_url_expiry(remaining_lifetime: timedelta | None) -> int:
    """Return the signed URL expiry in seconds, capped to object lifetime."""
    if remaining_lifetime is None:
        return SIGNED_URL_TTL_SECONDS
    remaining_seconds = int(remaining_lifetime.total_seconds())
    return min(SIGNED_URL_TTL_SECONDS, max(remaining_seconds, 60))


# ── Core operations ───────────────────────────────────────────


async def request_export(
    db: AsyncSession,
    tenant_id: UUID,
    actor_id: UUID,
    actor_role: str = "tenant",
) -> ExportJob:
    """Create a new export job for the tenant.

    Enforces:
    - 24-hour cooldown after the last ready/failed/cancelled job.
    - Replacement chain: if a ready job exists, the new job replaces it.
    - Previous artifact remains downloadable while replacement is pending.

    Returns the pending ExportJob.
    Raises ``ValueError`` if within cooldown.
    """
    # Check cooldown
    cooling = await export_jobs_repository.is_within_cooldown(db, tenant_id)
    if cooling is not None:
        cooldown_tz = _ensure_tz(cooling.cooldown_until)
        if cooldown_tz:
            remaining = cooldown_tz - _now()
            if remaining.total_seconds() > 0:
                remaining_minutes = int(remaining.total_seconds() / 60)
                raise ValueError(
                    f"Export generation is on cooldown. Try again in {remaining_minutes} minutes."
                )

    # Check for existing ready job to link as replacement
    current_ready = await export_jobs_repository.get_ready_by_tenant(db, tenant_id)
    replaced_job_id = current_ready.id if current_ready else None

    cooldown_until = _compute_cooldown_until()

    job = await export_jobs_repository.create(
        db,
        tenant_id=tenant_id,
        requested_by=actor_id,
        actor_role=actor_role,
        cooldown_until=cooldown_until,
        replaced_job_id=replaced_job_id,
    )

    # If replacing, link the replacement_job_id on the previous ready
    if current_ready:
        await export_jobs_repository.update_status(
            db,
            current_ready.id,
            current_ready.status,
            replacement_job_id=job.id,
            r2_key=current_ready.r2_key,
            artifact_size_bytes=current_ready.artifact_size_bytes,
            expires_at=current_ready.expires_at,
        )

    return job


async def get_current_export(
    db: AsyncSession,
    tenant_id: UUID,
) -> dict | None:
    """Get the latest export status with enriched metadata (actor, cooldown, etc).

    Returns a dict with the latest export job, cooldown status, and
    previous-ready download availability, or ``None`` if no job exists.
    """
    job = await export_jobs_repository.get_latest_by_tenant(db, tenant_id)
    if job is None:
        return None

    # Check if there's a previous ready available for download
    previous_ready = None
    if job.replaced_job_id and job.status in ("pending", "processing"):
        prev = await export_jobs_repository.get_by_id(db, job.replaced_job_id)
        prev_expires = _ensure_tz(prev.expires_at) if prev else None
        if prev and prev.status == "ready" and prev_expires and prev_expires > _now():
            previous_ready = {
                "id": str(prev.id),
                "ready_at": prev.ready_at.isoformat() if prev.ready_at else None,
                "artifact_size_bytes": prev.artifact_size_bytes,
                "expires_at": prev.expires_at.isoformat() if prev.expires_at else None,
            }

    # Check cooldown info - from active cooldown or from the job directly
    cooling = await export_jobs_repository.is_within_cooldown(db, tenant_id)
    if cooling is not None:
        cooldown_val = _ensure_tz(cooling.cooldown_until)
    else:
        cooldown_val = _ensure_tz(job.cooldown_until) if job.cooldown_until else None
    cooldown_until = cooldown_val.isoformat() if cooldown_val else None

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
        "failed_at": job.failed_at.isoformat() if job.failed_at else None,
        "cooldown_until": cooldown_until,
        "actor_role": job.actor_role,
        "replaced_job_id": str(job.replaced_job_id) if job.replaced_job_id else None,
        "replacement_job_id": str(job.replacement_job_id)
        if job.replacement_job_id
        else None,
        "previous_ready": previous_ready,
    }


async def get_ready_export(
    db: AsyncSession,
    tenant_id: UUID,
) -> ExportJob | None:
    """Get the latest ready, unexpired export for the tenant (with replacement awareness)."""
    return await export_jobs_repository.get_downloadable_job_for_tenant(db, tenant_id)


async def get_download_url(
    db: AsyncSession,
    tenant_id: UUID,
) -> dict | None:
    """Get a presigned download URL for the tenant's downloadable export.

    Returns a dict with ``download_url`` and ``expires_in``, or ``None`` if
    no downloadable export exists.
    URL expiry is capped to min(15 minutes, remaining object lifetime).
    """
    job = await get_ready_export(db, tenant_id)
    if job is None or job.r2_key is None:
        return None

    storage = get_storage()
    remaining = None
    expires_at = _ensure_tz(job.expires_at)
    if expires_at:
        remaining = expires_at - _now()
        if remaining.total_seconds() <= 0:
            return None  # expired

    url_ttl = _cap_signed_url_expiry(remaining)
    url = await storage.generate_presigned_get(
        key=job.r2_key,
        expires_in_seconds=url_ttl,
    )

    return {
        "download_url": url,
        "expires_in": url_ttl,
    }


async def cancel_export(
    db: AsyncSession,
    tenant_id: UUID,
    actor_id: UUID,
) -> ExportJob | None:
    """Cancel the current pending or processing export job.

    The worker must honour cancellation checkpoints.  Partial uploads
    from a processing job are purged from storage.
    """
    job = await export_jobs_repository.get_latest_by_tenant(db, tenant_id)
    if job is None:
        return None

    if job.status not in ("pending", "processing"):
        return None

    # If the worker uploaded a partial artifact, purge it
    if job.status == "processing" and job.r2_key:
        storage = get_storage()
        try:
            await storage.delete(job.r2_key)
        except (StorageObjectNotFoundError, StorageOperationError) as exc:
            logger.warning("Failed to purge partial upload %s: %s", job.r2_key, exc)

    cancelled = await export_jobs_repository.cancel_job(db, job.id)
    return cancelled


async def cancel_export_by_job_id(
    db: AsyncSession,
    job_id: UUID,
    tenant_id: UUID,
) -> ExportJob | None:
    """Cancel a specific export job by ID.

    Verifies the job belongs to the tenant before cancelling.
    """
    job = await export_jobs_repository.get_by_id(db, job_id)
    if job is None or job.tenant_id != tenant_id:
        return None

    if job.status not in ("pending", "processing"):
        return None

    # Purge partial upload if any
    if job.status == "processing" and job.r2_key:
        storage = get_storage()
        try:
            await storage.delete(job.r2_key)
        except (StorageObjectNotFoundError, StorageOperationError) as exc:
            logger.warning("Failed to purge partial upload %s: %s", job.r2_key, exc)

    return await export_jobs_repository.cancel_job(db, job_id)


async def confirm_replacement_ready(
    db: AsyncSession,
    job_id: UUID,
    tenant_id: UUID,
    r2_key: str,
    artifact_size_bytes: int,
) -> ExportJob | None:
    """Mark a replacement job as ready and purge the previous object.

    Called by the worker after successful upload.  Atomically:
    1. Transitions the new job to ``ready`` with expiry 72h.
    2. If the new job replaced a previous ready job, deletes the previous
       R2 object so the new one becomes the sole downloadable artifact.

    Returns the updated job.
    """
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=EXPORT_TTL_HOURS)
    cooldown_until = _compute_cooldown_until()

    job = await export_jobs_repository.update_status(
        db,
        job_id,
        "ready",
        r2_key=r2_key,
        artifact_size_bytes=artifact_size_bytes,
        expires_at=expires_at,
        clear_lease=True,
        cooldown_until=cooldown_until,
    )
    if job is None:
        return None

    # If this job replaced a previous ready, purge the previous R2 object
    if job.replaced_job_id:
        prev = await export_jobs_repository.get_by_id(db, job.replaced_job_id)
        if prev and prev.r2_key:
            storage = get_storage()
            try:
                await storage.delete(prev.r2_key)
            except (StorageObjectNotFoundError, StorageOperationError) as exc:
                logger.warning(
                    "Failed to purge replaced R2 object %s: %s",
                    prev.r2_key,
                    exc,
                )
            # Also mark the replaced job as superseded (clear its r2_key so
            # it can no longer be served)
            await export_jobs_repository.update_status(
                db,
                prev.id,
                prev.status,
                r2_key=None,
                artifact_size_bytes=prev.artifact_size_bytes,
                expires_at=prev.expires_at,
            )

    return job


async def cleanup_expired_exports(
    db: AsyncSession,
) -> int:
    """Clean up expired ready jobs: delete R2 objects and remove metadata.

    Returns the number of jobs cleaned up.
    """
    storage = get_storage()
    expired = await export_jobs_repository.find_expired_ready_jobs(db)
    count = 0
    for job in expired:
        if job.r2_key:
            try:
                await storage.delete(job.r2_key)
            except (StorageObjectNotFoundError, StorageOperationError) as exc:
                logger.warning(
                    "Failed to delete expired R2 object %s: %s",
                    job.r2_key,
                    exc,
                )
        # Clear the job metadata (keep the row for audit, remove sensitive info)
        await export_jobs_repository.update_status(
            db,
            job.id,
            job.status,
            r2_key=None,
            artifact_size_bytes=None,
            expires_at=job.expires_at,
        )
        count += 1
    return count


async def cleanup_stale_failed_jobs(
    db: AsyncSession,
) -> int:
    """Remove failed job metadata older than 72 hours.

    Returns the number of jobs cleaned up.
    """
    stale = await export_jobs_repository.find_stale_failed_jobs(db)
    count = 0
    for job in stale:
        await export_jobs_repository.update_status(
            db,
            job.id,
            job.status,
            error_code=job.error_code,
            error_detail=None,
            r2_key=None,
            artifact_size_bytes=None,
        )
        count += 1
    return count


__all__ = [
    "EXPORT_TTL_HOURS",
    "COOLDOWN_HOURS",
    "configure_export_service",
    "get_storage",
    "get_limiter",
    "request_export",
    "get_current_export",
    "get_ready_export",
    "get_download_url",
    "cancel_export",
    "cancel_export_by_job_id",
    "confirm_replacement_ready",
    "cleanup_expired_exports",
    "cleanup_stale_failed_jobs",
]
