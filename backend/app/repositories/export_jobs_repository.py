"""ExportJob repository — durable job lifecycle queries."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.export_job import ExportJob


def _ensure_tz(dt: datetime | None) -> datetime | None:
    """Ensure a datetime is timezone-aware; assume UTC if naive."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _now() -> datetime:
    """Return current UTC time as aware datetime."""
    return datetime.now(timezone.utc)


async def get_latest_by_tenant(db: AsyncSession, tenant_id: UUID) -> ExportJob | None:
    """Return the most recently created job for *tenant_id* (if any)."""
    result = await db.execute(
        select(ExportJob)
        .where(ExportJob.tenant_id == tenant_id)
        .order_by(ExportJob.created_at.desc(), ExportJob.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_ready_by_tenant(
    db: AsyncSession,
    tenant_id: UUID,
) -> ExportJob | None:
    """Return the most recent ready (unexpired) job for *tenant_id*."""
    now = _now()
    result = await db.execute(
        select(ExportJob)
        .where(
            ExportJob.tenant_id == tenant_id,
            ExportJob.status == "ready",
            ExportJob.expires_at > now,
        )
        .order_by(ExportJob.created_at.desc(), ExportJob.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_downloadable_ready(
    db: AsyncSession,
    tenant_id: UUID,
) -> ExportJob | None:
    """Return the appropriate ready export for download.

    If a ready replacement is available (newer ready job), return it.
    Otherwise, if the latest ready job's replacement is pending/failed,
    return the previous ready job if still unexpired.
    This handles the replacement lifecycle: the previous artifact remains
    downloadable while a new one is pending/processing, and the new one
    becomes current only after ready confirmation.
    """
    now = _now()
    # Find all unexpired ready jobs for this tenant
    result = await db.execute(
        select(ExportJob)
        .where(
            ExportJob.tenant_id == tenant_id,
            ExportJob.status == "ready",
            ExportJob.expires_at > now,
        )
        .order_by(ExportJob.ready_at.desc(), ExportJob.created_at.desc())
    )
    ready_jobs = list(result.scalars().all())
    if not ready_jobs:
        return None

    newest = ready_jobs[0]

    if not newest.replacement_job_id:
        return newest

    repl_result = await db.execute(
        select(ExportJob).where(ExportJob.id == newest.replacement_job_id)
    )
    replacement = repl_result.scalar_one_or_none()
    if replacement and replacement.status in ("pending", "processing"):
        if len(ready_jobs) > 1:
            return ready_jobs[1]
        return newest

    return newest


async def get_previous_ready(
    db: AsyncSession,
    tenant_id: UUID,
    current_ready_id: UUID,
) -> ExportJob | None:
    """Return the previous unexpired ready job for *tenant_id* (if any).

    Used when the current ready job has a pending replacement — the
    previous artifact remains downloadable.
    """
    now = _now()
    result = await db.execute(
        select(ExportJob)
        .where(
            ExportJob.tenant_id == tenant_id,
            ExportJob.status == "ready",
            ExportJob.expires_at > now,
            ExportJob.id != current_ready_id,
        )
        .order_by(ExportJob.ready_at.desc(), ExportJob.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_by_id(db: AsyncSession, job_id: UUID) -> ExportJob | None:
    """Return a single job by its primary key."""
    result = await db.execute(select(ExportJob).where(ExportJob.id == job_id))
    return result.scalar_one_or_none()


async def create(
    db: AsyncSession,
    tenant_id: UUID,
    requested_by: UUID | None = None,
    actor_role: str | None = None,
    *,
    max_attempts: int = 3,
    cooldown_until: datetime | None = None,
    replaced_job_id: UUID | None = None,
) -> ExportJob:
    """Create a new pending ExportJob.

    When *replaced_job_id* is set, the new job is a replacement for the
    previous ready export.  *cooldown_until* is set to enforce the 24-hour
    generation cooldown.
    """
    job = ExportJob(
        tenant_id=tenant_id,
        requested_by=requested_by,
        actor_role=actor_role,
        status="pending",
        max_attempts=max_attempts,
        cooldown_until=cooldown_until,
        replaced_job_id=replaced_job_id,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


async def claim_pending(
    db: AsyncSession,
    *,
    lease_minutes: int = 30,
) -> ExportJob | None:
    """Atomically claim the oldest pending job, setting lease details.

    Returns the claimed job, or ``None`` if no pending/unclaimed job is
    available.  Skips jobs that have exceeded their max attempts.
    """
    now = _now()
    result = await db.execute(
        select(ExportJob)
        .where(
            ExportJob.status == "pending",
            ExportJob.attempts < ExportJob.max_attempts,
            (
                (ExportJob.lease_expires_at < now)
                | (ExportJob.lease_expires_at.is_(None))
            ),
        )
        .order_by(ExportJob.created_at.asc())
        .limit(1)
    )
    job = result.scalar_one_or_none()
    if job is None:
        return None

    job.status = "processing"
    job.lease_token = uuid.uuid4()
    job.lease_expires_at = now + timedelta(minutes=lease_minutes)
    await db.commit()
    await db.refresh(job)
    return job


async def update_status(
    db: AsyncSession,
    job_id: UUID,
    status: str,
    *,
    r2_key: str | None = None,
    artifact_size_bytes: int | None = None,
    error_code: str | None = None,
    error_detail: str | None = None,
    expires_at: datetime | None = None,
    clear_lease: bool = False,
    cooldown_until: datetime | None = None,
    replacement_job_id: UUID | None = None,
) -> ExportJob | None:
    """Update the status of a job, optionally setting artifact or error fields."""
    now = _now()
    values: dict = {"status": status}

    if replacement_job_id is not None:
        values["replacement_job_id"] = replacement_job_id

    if status == "ready":
        values["ready_at"] = now
        values["r2_key"] = r2_key
        values["artifact_size_bytes"] = artifact_size_bytes
        if expires_at is not None:
            values["expires_at"] = expires_at
    elif status == "failed":
        values["error_code"] = error_code
        values["error_detail"] = error_detail
        values["failed_at"] = now
    elif status == "cancelled":
        values["error_code"] = None
        values["error_detail"] = None

    if cooldown_until is not None:
        values["cooldown_until"] = cooldown_until

    if clear_lease:
        values["lease_token"] = None
        values["lease_expires_at"] = None

    stmt = (
        update(ExportJob)
        .where(ExportJob.id == job_id)
        .values(**values)
        .returning(ExportJob)
    )
    result = await db.execute(stmt)
    await db.commit()
    return result.scalar_one_or_none()


async def increment_attempts(
    db: AsyncSession,
    job_id: UUID,
) -> ExportJob | None:
    """Increment the attempt counter for a job."""
    stmt = (
        update(ExportJob)
        .where(ExportJob.id == job_id)
        .values(attempts=ExportJob.attempts + 1)
        .returning(ExportJob)
    )
    result = await db.execute(stmt)
    await db.commit()
    return result.scalar_one_or_none()


async def recover_stale_leases(
    db: AsyncSession,
    *,
    lease_minutes: int = 30,
) -> list[ExportJob]:
    """Find and recover processing jobs whose lease has expired.

    These are treated as failed with a ``LEASE_EXPIRED`` error so they
    can be retried or surfaced.
    """
    now = _now()
    cutoff = now - timedelta(minutes=lease_minutes)
    result = await db.execute(
        select(ExportJob).where(
            ExportJob.status == "processing",
            ExportJob.lease_expires_at < cutoff,
        )
    )
    jobs = result.scalars().all()
    for job in jobs:
        job.status = "failed"
        job.error_code = "LEASE_EXPIRED"
        job.attempts = ExportJob.attempts + 1
        job.lease_token = None
        job.lease_expires_at = None
    await db.commit()
    return jobs


async def cancel_job(
    db: AsyncSession,
    job_id: UUID,
) -> ExportJob | None:
    """Cancel a pending or processing job.

    Only jobs in ``pending`` or ``processing`` status can be cancelled.
    Returns the updated job, or ``None`` if the job cannot be cancelled
    (e.g. already ready, failed, or cancelled).
    """
    stmt = (
        update(ExportJob)
        .where(
            ExportJob.id == job_id,
            ExportJob.status.in_(["pending", "processing"]),
        )
        .values(
            status="cancelled",
            lease_token=None,
            lease_expires_at=None,
        )
        .returning(ExportJob)
    )
    result = await db.execute(stmt)
    await db.commit()
    return result.scalar_one_or_none()


async def cancel_tenant_jobs(
    db: AsyncSession,
    tenant_id: UUID,
) -> list[ExportJob]:
    """Cancel all pending/processing jobs for a tenant.

    Returns the list of cancelled jobs.
    """
    result = await db.execute(
        select(ExportJob).where(
            ExportJob.tenant_id == tenant_id,
            ExportJob.status.in_(["pending", "processing"]),
        )
    )
    jobs = result.scalars().all()
    for job in jobs:
        job.status = "cancelled"
        job.lease_token = None
        job.lease_expires_at = None
    await db.commit()
    return jobs


async def count_by_tenant_and_status(
    db: AsyncSession, tenant_id: UUID, status: str
) -> int:
    """Count jobs for a tenant with a specific status."""
    result = await db.execute(
        select(ExportJob).where(
            ExportJob.tenant_id == tenant_id,
            ExportJob.status == status,
        )
    )
    return len(result.scalars().all())


async def find_expired_ready_jobs(
    db: AsyncSession,
) -> list[ExportJob]:
    """Return all ready jobs whose expiry has passed."""
    now = _now()
    result = await db.execute(
        select(ExportJob).where(
            ExportJob.status == "ready",
            ExportJob.expires_at < now,
        )
    )
    return list(result.scalars().all())


async def find_stale_failed_jobs(
    db: AsyncSession,
    *,
    max_age_hours: int = 72,
) -> list[ExportJob]:
    """Return all failed jobs older than *max_age_hours*."""
    now = _now()
    cutoff = now - timedelta(hours=max_age_hours)
    result = await db.execute(
        select(ExportJob).where(
            ExportJob.status == "failed",
            ExportJob.failed_at < cutoff,
        )
    )
    return list(result.scalars().all())


async def purge_job(
    db: AsyncSession,
    job_id: UUID,
) -> None:
    """Permanently delete an ExportJob row.

    Used during cleanup of expired/failed jobs and during Tenant Deletion.
    """
    stmt = select(ExportJob).where(ExportJob.id == job_id)
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()
    if job is not None:
        await db.delete(job)
        await db.commit()


async def purge_tenant_jobs(
    db: AsyncSession,
    tenant_id: UUID,
) -> None:
    """Permanently delete all export jobs for a tenant.

    Used during Tenant Deletion.
    """
    result = await db.execute(select(ExportJob).where(ExportJob.tenant_id == tenant_id))
    jobs = result.scalars().all()
    for job in jobs:
        await db.delete(job)
    await db.commit()


async def is_within_cooldown(
    db: AsyncSession,
    tenant_id: UUID,
) -> ExportJob | None:
    """Check if the tenant is within the 24-hour generation cooldown.

    Returns the job that established the cooldown, or ``None`` if no
    cooldown is active.  A job establishes cooldown on creation; the
    cooldown is based on the ``cooldown_until`` field regardless of
    current job status.
    """
    now = _now()
    result = await db.execute(
        select(ExportJob)
        .where(
            ExportJob.tenant_id == tenant_id,
            ExportJob.cooldown_until.is_not(None),
            ExportJob.cooldown_until > now,
        )
        .order_by(ExportJob.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_downloadable_job_for_tenant(
    db: AsyncSession,
    tenant_id: UUID,
) -> ExportJob | None:
    """Get the best job to serve a download for *tenant_id*.

    Priority:
    1. The latest ready job whose replacement is not pending/processing
       (current active export).
    2. If the latest ready job has a pending/processing replacement,
       the previous ready job (still downloadable).
    3. Any unexpired ready job.
    """
    now = _now()
    result = await db.execute(
        select(ExportJob)
        .where(
            ExportJob.tenant_id == tenant_id,
            ExportJob.status == "ready",
            ExportJob.r2_key.is_not(None),
            ExportJob.expires_at > now,
        )
        .order_by(ExportJob.ready_at.desc())
    )
    ready_jobs = list(result.scalars().all())
    if not ready_jobs:
        return None

    latest = ready_jobs[0]

    if latest.replacement_job_id is None:
        return latest

    repl = await get_by_id(db, latest.replacement_job_id)
    if repl is not None and repl.status in ("pending", "processing"):
        if len(ready_jobs) > 1:
            return ready_jobs[1]
        return latest

    return latest
