"""ExportJob repository — durable job lifecycle queries."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.export_job import ExportJob


async def get_latest_by_tenant(
    db: AsyncSession, tenant_id: UUID
) -> ExportJob | None:
    """Return the most recently created job for *tenant_id* (if any)."""
    result = await db.execute(
        select(ExportJob)
        .where(ExportJob.tenant_id == tenant_id)
        .order_by(ExportJob.created_at.desc(), ExportJob.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_ready_by_tenant(
    db: AsyncSession, tenant_id: UUID,
) -> ExportJob | None:
    """Return the most recent ready (unexpired) job for *tenant_id*."""
    now = datetime.now(timezone.utc)
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


async def get_by_id(db: AsyncSession, job_id: UUID) -> ExportJob | None:
    """Return a single job by its primary key."""
    result = await db.execute(select(ExportJob).where(ExportJob.id == job_id))
    return result.scalar_one_or_none()


async def create(
    db: AsyncSession,
    tenant_id: UUID,
    requested_by: UUID | None = None,
    *,
    max_attempts: int = 3,
) -> ExportJob:
    """Create a new pending ExportJob."""
    job = ExportJob(
        tenant_id=tenant_id,
        requested_by=requested_by,
        status="pending",
        max_attempts=max_attempts,
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
    available.
    """
    now = datetime.now(timezone.utc)
    # Find a pending job whose lease has expired (or was never claimed)
    result = await db.execute(
        select(ExportJob).where(
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
    job.lease_expires_at = now.replace(tzinfo=timezone.utc) + __import__(
        "datetime"
    ).timedelta(minutes=lease_minutes)
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
) -> ExportJob | None:
    """Update the status of a job, optionally setting artifact or error fields."""
    now = datetime.now(timezone.utc)
    values: dict = {"status": status}

    if status == "ready":
        values["ready_at"] = now
        values["r2_key"] = r2_key
        values["artifact_size_bytes"] = artifact_size_bytes
        if expires_at is not None:
            values["expires_at"] = expires_at
    elif status == "failed":
        values["error_code"] = error_code
        values["error_detail"] = error_detail

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
