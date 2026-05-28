"""Lookup jobs repository — mail_lookup_jobs CRUD and state transitions."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MailLookupJob

VALID_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"processing", "failed", "timeout"},
    "processing": {"completed", "failed", "timeout"},
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
    db: AsyncSession, job_id: UUID, tenant_id: UUID | None = None
) -> MailLookupJob | None:
    """Get job by id, optionally scoped to tenant."""
    stmt = select(MailLookupJob).where(MailLookupJob.id == job_id)
    if tenant_id is not None:
        stmt = stmt.where(MailLookupJob.tenant_id == tenant_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


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
    result_value_encrypted: str | None = None,
    error_code: str | None = None,
    error_detail_safe: str | None = None,
) -> MailLookupJob:
    """Transition job status with validation.

    Only allows valid transitions per VALID_TRANSITIONS dict.
    Sets processing_started_at when moving to processing.
    Sets completed_at when moving to completed/failed/timeout.
    """
    allowed = VALID_TRANSITIONS.get(job.status, set())
    if new_status not in allowed:
        raise ValueError(
            f"Invalid transition: {job.status} -> {new_status}. Allowed: {allowed}"
        )

    job.status = new_status

    if new_status == "processing":
        job.processing_started_at = datetime.now(timezone.utc)
    elif new_status in ("completed", "failed", "timeout"):
        job.completed_at = datetime.now(timezone.utc)

    if result_type is not None:
        job.result_type = result_type
    if result_value_encrypted is not None:
        job.result_value_encrypted = result_value_encrypted
    if error_code is not None:
        job.error_code = error_code
    if error_detail_safe is not None:
        job.error_detail_safe = error_detail_safe

    await db.flush()
    return job


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

    Returns count of deleted rows.
    Default cutoff: now - 5m.
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
    "list_pending_jobs",
    "transition_status",
    "expire_stale_jobs",
    "delete_expired_jobs",
]
