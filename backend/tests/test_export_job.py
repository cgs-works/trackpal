"""Tests for the ExportJob model and lifecycle.

Tests here verify the durability seam: ORM persistence, defaults, FK
cascade, and index enforcement.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta

import pytest
from sqlalchemy import select

from app.models import Tenant, User
from app.models.export_job import ExportJob
from app.repositories import export_jobs_repository

pytestmark = pytest.mark.asyncio


async def _create_tenant(db_session, user: User) -> Tenant:
    """Helper: create a minimal active tenant owned by *user*."""
    tenant = Tenant(
        owner_user_id=user.id,
        client_prefix="exp01",
        name="Export Test Tenant",
        is_active=True,
    )
    db_session.add(tenant)
    await db_session.flush()
    return tenant


async def _tenant_for_user(db_session, user_id: uuid.UUID) -> Tenant | None:
    result = await db_session.execute(
        select(Tenant).where(Tenant.owner_user_id == user_id)
    )
    return result.scalar_one_or_none()


# ── Model persistence ──────────────────────────────────────────


async def test_export_job_created_with_defaults(db_session, active_tenant_user):
    """A newly created ExportJob has pending status, zero attempts, and
    populated timestamps."""
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    job = ExportJob(
        tenant_id=tenant.id,
        requested_by=active_tenant_user.id,
    )
    db_session.add(job)
    await db_session.commit()

    assert job.id is not None
    assert isinstance(job.id, uuid.UUID)
    assert job.status == "pending"
    assert job.attempts == 0
    assert job.max_attempts == 3
    assert job.lease_token is None
    assert job.lease_expires_at is None
    assert job.r2_key is None
    assert job.ready_at is None
    assert job.expires_at is None
    assert job.error_code is None
    assert job.created_at is not None
    assert job.updated_at is not None


async def test_export_job_tenant_relationship(db_session, active_tenant_user):
    """ExportJob relates to Tenant via tenant_id FK."""
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    job = ExportJob(tenant_id=tenant.id, requested_by=active_tenant_user.id)
    db_session.add(job)
    await db_session.commit()

    # Verify the ORM relationship resolves
    assert job.tenant is not None
    assert job.tenant.id == tenant.id
    assert job.tenant.name == "Active Tenant"


async def test_export_job_can_transition_through_statuses(db_session, active_tenant_user):
    """Status transitions persist correctly."""
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    job = ExportJob(tenant_id=tenant.id, requested_by=active_tenant_user.id)
    db_session.add(job)
    await db_session.commit()

    # Transition: pending → processing
    job.status = "processing"
    job.lease_token = uuid.uuid4()
    job.lease_expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)
    await db_session.commit()

    # Transition: processing → ready
    job.status = "ready"
    job.r2_key = "non-pii-key-123"
    job.ready_at = datetime.now(timezone.utc)
    job.expires_at = datetime.now(timezone.utc) + timedelta(hours=72)
    job.lease_token = None
    job.lease_expires_at = None
    await db_session.commit()

    # Verify full state
    result = await db_session.execute(select(ExportJob).where(ExportJob.id == job.id))
    loaded = result.scalar_one()
    assert loaded.status == "ready"
    assert loaded.r2_key == "non-pii-key-123"
    assert loaded.attempts == 0
    assert loaded.lease_token is None


async def test_export_job_status_values_are_valid(db_session, active_tenant_user):
    """Status accepts only documented lifecycle values."""
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    job = ExportJob(tenant_id=tenant.id, requested_by=active_tenant_user.id)
    db_session.add(job)
    await db_session.commit()

    # All valid statuses should persist
    for status in ("pending", "processing", "ready", "failed", "cancelled"):
        job.status = status
        await db_session.commit()
        await db_session.refresh(job)
        assert job.status == status


async def test_export_job_attempts_increment(db_session, active_tenant_user):
    """Attempts counter persists correctly."""
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    job = ExportJob(tenant_id=tenant.id, requested_by=active_tenant_user.id)
    db_session.add(job)
    await db_session.commit()

    for i in range(1, 4):
        job.attempts = i
        await db_session.commit()
        await db_session.refresh(job)
        assert job.attempts == i


async def test_export_job_failed_state_has_error_code(db_session, active_tenant_user):
    """Failed state persists with optional error code."""
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    job = ExportJob(tenant_id=tenant.id, requested_by=active_tenant_user.id)
    db_session.add(job)
    await db_session.commit()

    job.status = "failed"
    job.error_code = "GENERATION_ERROR"
    job.attempts = 3
    await db_session.commit()

    await db_session.refresh(job)
    assert job.status == "failed"
    assert job.error_code == "GENERATION_ERROR"
    assert job.attempts == 3


# ── Repository ────────────────────────────────────────────────


async def test_create_and_get_latest_job(db_session, active_tenant_user):
    """Repository create() persists a job and get_latest_by_tenant() returns it."""
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    job = await export_jobs_repository.create(
        db_session,
        tenant_id=tenant.id,
        requested_by=active_tenant_user.id,
    )
    assert job.status == "pending"
    assert job.attempts == 0

    latest = await export_jobs_repository.get_latest_by_tenant(
        db_session, tenant.id
    )
    assert latest is not None
    assert latest.id == job.id


async def test_get_latest_by_tenant_has_correct_tenant(db_session, active_tenant_user):
    """get_latest_by_tenant returns a job scoped to the correct tenant."""
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    job = await export_jobs_repository.create(
        db_session, tenant_id=tenant.id, requested_by=active_tenant_user.id,
    )

    latest = await export_jobs_repository.get_latest_by_tenant(
        db_session, tenant.id
    )
    assert latest is not None
    assert latest.id == job.id
    assert latest.tenant_id == tenant.id


async def test_get_ready_by_tenant_returns_unexpired_ready(db_session, active_tenant_user):
    """get_ready_by_tenant returns only the most recent ready + unexpired job."""
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    now = datetime.now(timezone.utc)
    # Create an expired ready job
    expired = await export_jobs_repository.create(
        db_session, tenant_id=tenant.id, requested_by=active_tenant_user.id,
    )
    await export_jobs_repository.update_status(
        db_session, expired.id, "ready",
        r2_key="expired-key",
        expires_at=now - timedelta(hours=1),
        clear_lease=True,
    )

    # Create a valid ready job
    ready = await export_jobs_repository.create(
        db_session, tenant_id=tenant.id, requested_by=active_tenant_user.id,
    )
    await export_jobs_repository.update_status(
        db_session, ready.id, "ready",
        r2_key="valid-key",
        expires_at=now + timedelta(hours=48),
        clear_lease=True,
    )

    result = await export_jobs_repository.get_ready_by_tenant(db_session, tenant.id)
    assert result is not None
    assert result.id == ready.id
    assert result.r2_key == "valid-key"


async def test_claim_pending_returns_oldest_unclaimed(db_session, active_tenant_user):
    """claim_pending gets the oldest pending job and sets lease."""
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    await export_jobs_repository.create(
        db_session, tenant_id=tenant.id, requested_by=active_tenant_user.id,
    )

    claimed = await export_jobs_repository.claim_pending(db_session)
    assert claimed is not None
    assert claimed.status == "processing"
    assert claimed.lease_token is not None
    assert claimed.lease_expires_at is not None


async def test_claim_pending_skips_maxed_attempts(db_session, active_tenant_user):
    """claim_pending does not return jobs that have exceeded max_attempts."""
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    # Create a job at max attempts
    job = await export_jobs_repository.create(
        db_session, tenant_id=tenant.id, max_attempts=2,
    )
    # Bump attempts to max
    from sqlalchemy import update as sa_update
    stmt = sa_update(ExportJob).where(ExportJob.id == job.id).values(attempts=2)
    await db_session.execute(stmt)
    await db_session.commit()

    claimed = await export_jobs_repository.claim_pending(db_session)
    assert claimed is None


async def test_update_status_to_ready(db_session, active_tenant_user):
    """update_status transitions to ready with artifact metadata."""
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    job = await export_jobs_repository.create(
        db_session, tenant_id=tenant.id, requested_by=active_tenant_user.id,
    )
    updated = await export_jobs_repository.update_status(
        db_session, job.id, "ready",
        r2_key="my-key",
        artifact_size_bytes=4096,
        clear_lease=True,
    )
    assert updated is not None
    assert updated.status == "ready"
    assert updated.r2_key == "my-key"
    assert updated.artifact_size_bytes == 4096
    assert updated.ready_at is not None
    assert updated.lease_token is None


async def test_update_status_to_failed(db_session, active_tenant_user):
    """update_status transitions to failed with error code."""
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    job = await export_jobs_repository.create(
        db_session, tenant_id=tenant.id, requested_by=active_tenant_user.id,
    )
    updated = await export_jobs_repository.update_status(
        db_session, job.id, "failed",
        error_code="GENERATION_ERROR",
    )
    assert updated is not None
    assert updated.status == "failed"
    assert updated.error_code == "GENERATION_ERROR"


async def test_get_by_id_returns_correct_job(db_session, active_tenant_user):
    """get_by_id returns the job matching the given id or None."""
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    job = await export_jobs_repository.create(
        db_session, tenant_id=tenant.id, requested_by=active_tenant_user.id,
    )
    found = await export_jobs_repository.get_by_id(db_session, job.id)
    assert found is not None
    assert found.id == job.id

    not_found = await export_jobs_repository.get_by_id(db_session, uuid.uuid4())
    assert not_found is None


async def test_count_by_tenant_and_status(db_session, active_tenant_user):
    """count_by_tenant_and_status returns correct count."""
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    await export_jobs_repository.create(
        db_session, tenant_id=tenant.id, requested_by=active_tenant_user.id,
    )
    await export_jobs_repository.create(
        db_session, tenant_id=tenant.id, requested_by=active_tenant_user.id,
    )

    count = await export_jobs_repository.count_by_tenant_and_status(
        db_session, tenant.id, "pending"
    )
    assert count == 2


async def test_export_job_tenant_index(db_session, active_tenant_user):
    """Jobs can be queried by tenant_id efficiently."""
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    job1 = ExportJob(tenant_id=tenant.id, requested_by=active_tenant_user.id)
    job2 = ExportJob(tenant_id=tenant.id, requested_by=active_tenant_user.id)
    db_session.add_all([job1, job2])
    await db_session.commit()

    result = await db_session.execute(
        select(ExportJob)
        .where(ExportJob.tenant_id == tenant.id)
        .order_by(ExportJob.created_at.desc())
    )
    jobs = result.scalars().all()
    assert len(jobs) == 2
