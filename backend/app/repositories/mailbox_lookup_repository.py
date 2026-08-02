"""Lookup jobs repository - mail_lookup_jobs CRUD and state transitions."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MailLookupJob

VALID_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"processing", "failed", "timeout"},
    "processing": {"completed", "failed", "timeout", "pending"},
}

JOB_TTL_DEFAULT_MINUTES = 5


async def create_job(
    db: AsyncSession,
    tenant_id: UUID,
    mailbox_id: UUID,
    service_key: str,
    target_email: str = "",
    ttl_minutes: int = JOB_TTL_DEFAULT_MINUTES,
) -> MailLookupJob:
    """Create a new lookup job in pending status."""
    from datetime import timedelta

    job = MailLookupJob(
        tenant_id=tenant_id,
        mailbox_id=mailbox_id,
        service_key=service_key,
        target_email=target_email,
        status="pending",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes),
    )
    db.add(job)
    await db.flush()
    return job


async def get_job(
    db: AsyncSession,
    job_id: UUID,
    tenant_id: UUID | None = None,
    *,
    with_for_update: bool = False,
) -> MailLookupJob | None:
    """Get a job by id, optionally scoped to a tenant and row-locked."""
    stmt = select(MailLookupJob).where(MailLookupJob.id == job_id)
    if tenant_id is not None:
        stmt = stmt.where(MailLookupJob.tenant_id == tenant_id)
    if with_for_update:
        stmt = stmt.with_for_update()
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def cancel_active_job_if_present(
    db: AsyncSession,
    job_id: UUID,
    tenant_id: UUID | None = None,
) -> bool:
    """Best-effort cancel for a session-linked active lookup job.

    Returns ``True`` only when an active job (``pending`` or ``processing``)
    was mutated to ``failed``. Returns ``False`` for missing jobs and for jobs
    that are already terminal.

    The helper does not commit; callers keep transaction control.
    """
    job = await get_job(db, job_id, tenant_id=tenant_id)
    if job is None:
        return False

    if job.status not in {"pending", "processing"}:
        return False

    job.status = "failed"
    job.completed_at = datetime.now(timezone.utc)
    job.error_code = "user_cancelled"
    job.error_detail_safe = "User restarted codigo flow"
    await db.flush()
    return True


async def list_pending_jobs(db: AsyncSession, limit: int = 10) -> list[MailLookupJob]:
    """List pending jobs ready for processing, ordered by creation."""
    result = await db.execute(
        select(MailLookupJob)
        .where(
            MailLookupJob.status == "pending",
            MailLookupJob.expires_at > datetime.now(timezone.utc),
        )
        .order_by(MailLookupJob.created_at.asc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def transition_status(
    db: AsyncSession,
    job: MailLookupJob,
    new_status: str,
    result_type: str | None = None,
    error_code: str | None = None,
    error_detail_safe: str | None = None,
    last_dispatch_error_safe: str | None = None,
) -> MailLookupJob:
    """Transition a job status and maintain assignment lifecycle metadata."""
    allowed = VALID_TRANSITIONS.get(job.status, set())
    if new_status not in allowed:
        raise ValueError(
            f"Invalid transition: {job.status} -> {new_status}. Allowed: {allowed}"
        )

    job.status = new_status

    if new_status == "processing":
        job.processing_started_at = datetime.now(timezone.utc)
    elif new_status == "pending":
        job.executor_id = None
        job.processing_started_at = None
        job.completed_at = None
    elif new_status in ("completed", "failed", "timeout"):
        job.completed_at = datetime.now(timezone.utc)

    if result_type is not None:
        job.result_type = result_type
    if error_code is not None:
        job.error_code = error_code
    if error_detail_safe is not None:
        job.error_detail_safe = error_detail_safe
        if new_status == "pending" and last_dispatch_error_safe is None:
            last_dispatch_error_safe = error_detail_safe
    if last_dispatch_error_safe is not None:
        job.last_dispatch_error_safe = last_dispatch_error_safe

    await db.flush()
    return job


async def recover_processing_job(
    db: AsyncSession,
    job: MailLookupJob,
    error: str | None = None,
) -> MailLookupJob:
    """Return a processing job to pending after an external lease failure."""
    return await transition_status(
        db,
        job,
        "pending",
        last_dispatch_error_safe=error,
    )


async def expire_stale_jobs(db: AsyncSession) -> int:
    """Mark expired jobs as timeout. Returns count of updated rows."""
    result = await db.execute(
        select(MailLookupJob).where(
            MailLookupJob.expires_at <= datetime.now(timezone.utc),
            MailLookupJob.status.in_(["pending", "processing"]),
        )
    )
    jobs = list(result.scalars().all())
    for job in jobs:
        job.status = "timeout"
        job.completed_at = datetime.now(timezone.utc)
        job.error_code = "timeout"
        job.error_detail_safe = "Job expired before processing"
    await db.flush()
    return len(jobs)


async def delete_expired_jobs(db: AsyncSession, before: datetime | None = None) -> int:
    """Hard-delete expired jobs older than given cutoff.

    Returns count of deleted rows. Default cutoff: now - 5m.
    """
    from datetime import timedelta

    cutoff = before or (
        datetime.now(timezone.utc) - timedelta(minutes=JOB_TTL_DEFAULT_MINUTES)
    )
    result = await db.execute(
        select(MailLookupJob).where(MailLookupJob.expires_at <= cutoff)
    )
    jobs = list(result.scalars().all())
    for job in jobs:
        await db.delete(job)
    await db.flush()
    return len(jobs)


__all__ = [
    "create_job",
    "get_job",
    "cancel_active_job_if_present",
    "list_pending_jobs",
    "transition_status",
    "recover_processing_job",
    "expire_stale_jobs",
    "delete_expired_jobs",
]
