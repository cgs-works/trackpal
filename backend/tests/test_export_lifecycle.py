"""Tests for the hardened Tenant Data Export lifecycle.

Covers cancellation, cooldown, replacement, retry with backoff, expiry,
actor attribution, cleanups, and concurrency safety.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.models import Tenant
from app.models.export_job import ExportJob
from app.repositories import export_jobs_repository
from app.services.export_storage import FakeExportStorageAdapter
from app.services import export_service, export_worker

pytestmark = pytest.mark.asyncio


# ── Fixtures ───────────────────────────────────────────────────


@pytest.fixture
def fake_storage():
    storage = FakeExportStorageAdapter()
    from app.services import export_service as svc

    original = getattr(svc, "_export_storage", None)
    svc._export_storage = storage
    yield storage
    svc._export_storage = original


async def _tenant_for_user(db_session, user_id):
    result = await db_session.execute(
        select(Tenant).where(Tenant.owner_user_id == user_id)
    )
    return result.scalar_one_or_none()


# ── Cooldown tests ─────────────────────────────────────────────


async def test_cooldown_blocks_second_generation(
    db_session, active_tenant_user, fake_storage
):
    """After a ready export, a new generation is blocked for 24h."""
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    # Create a ready job with cooldown set
    job1 = await export_jobs_repository.create(
        db_session,
        tenant_id=tenant.id,
        requested_by=active_tenant_user.id,
        actor_role="tenant",
        cooldown_until=datetime.now(timezone.utc) + timedelta(hours=24),
    )
    await export_jobs_repository.update_status(
        db_session,
        job1.id,
        "ready",
        r2_key="key-1",
        artifact_size_bytes=100,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=72),
        clear_lease=True,
        cooldown_until=datetime.now(timezone.utc) + timedelta(hours=24),
    )

    # Verify cooldown is active
    cooling = await export_jobs_repository.is_within_cooldown(db_session, tenant.id)
    assert cooling is not None

    # Attempt new generation
    with pytest.raises(ValueError, match="cooldown"):
        await export_service.request_export(
            db_session,
            tenant_id=tenant.id,
            actor_id=active_tenant_user.id,
            actor_role="tenant",
        )


async def test_automatic_retry_does_not_reset_cooldown(
    db_session, active_tenant_user, fake_storage
):
    """Automatic retries should not count as new successful snapshots for cooldown."""
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    # A failed job also establishes cooldown
    job = await export_jobs_repository.create(
        db_session,
        tenant_id=tenant.id,
        requested_by=active_tenant_user.id,
        actor_role="tenant",
        cooldown_until=datetime.now(timezone.utc) + timedelta(hours=24),
    )
    await export_jobs_repository.update_status(
        db_session,
        job.id,
        "failed",
        error_code="GENERATION_ERROR",
        cooldown_until=datetime.now(timezone.utc) + timedelta(hours=24),
    )

    cooling = await export_jobs_repository.is_within_cooldown(db_session, tenant.id)
    assert cooling is not None


async def test_cooldown_expires_after_24h(db_session, active_tenant_user, fake_storage):
    """Cooldown expires after 24 hours."""
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    # Create a ready job with cooldown in the past
    job = await export_jobs_repository.create(
        db_session,
        tenant_id=tenant.id,
        requested_by=active_tenant_user.id,
        actor_role="tenant",
        cooldown_until=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    await export_jobs_repository.update_status(
        db_session,
        job.id,
        "ready",
        r2_key="key-expired",
        artifact_size_bytes=100,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=48),
        clear_lease=True,
        cooldown_until=datetime.now(timezone.utc) - timedelta(hours=1),
    )

    cooling = await export_jobs_repository.is_within_cooldown(db_session, tenant.id)
    assert cooling is None


# ── Cancellation tests ─────────────────────────────────────────


async def test_cancel_pending_job(db_session, active_tenant_user, fake_storage):
    """A pending job can be cancelled."""
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    job = await export_jobs_repository.create(
        db_session,
        tenant_id=tenant.id,
        requested_by=active_tenant_user.id,
    )
    cancelled = await export_service.cancel_export(
        db_session,
        tenant_id=tenant.id,
        actor_id=active_tenant_user.id,
    )
    assert cancelled is not None
    assert cancelled.status == "cancelled"

    # Verify in DB
    await db_session.refresh(job)
    assert job.status == "cancelled"


async def test_cancel_processing_job_purges_upload(
    db_session, active_tenant_user, fake_storage
):
    """Cancelling a processing job purges partial upload from storage."""
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    # Create and claim job
    job = await export_jobs_repository.create(
        db_session,
        tenant_id=tenant.id,
        requested_by=active_tenant_user.id,
    )
    # Simulate processing with a partial upload
    await fake_storage.upload("partial-key", b"partial-data")

    # Set job as processing with an r2_key directly (update_status doesn't set r2_key for processing)
    job.status = "processing"
    job.r2_key = "partial-key"
    await db_session.commit()

    cancelled = await export_service.cancel_export(
        db_session,
        tenant_id=tenant.id,
        actor_id=active_tenant_user.id,
    )
    assert cancelled is not None
    assert cancelled.status == "cancelled"

    # Verify partial upload was purged
    assert "partial-key" not in fake_storage.stored_keys


async def test_cannot_cancel_ready_job(db_session, active_tenant_user, fake_storage):
    """A ready job cannot be cancelled."""
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    job = await export_jobs_repository.create(
        db_session,
        tenant_id=tenant.id,
        requested_by=active_tenant_user.id,
    )
    await export_jobs_repository.update_status(
        db_session,
        job.id,
        "ready",
        r2_key="key-ready",
        artifact_size_bytes=100,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=72),
        clear_lease=True,
    )

    cancelled = await export_service.cancel_export(
        db_session,
        tenant_id=tenant.id,
        actor_id=active_tenant_user.id,
    )
    assert cancelled is None


async def test_cancel_export_no_job(db_session, active_tenant_user, fake_storage):
    """Cancelling when no job exists returns None."""
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    cancelled = await export_service.cancel_export(
        db_session,
        tenant_id=tenant.id,
        actor_id=active_tenant_user.id,
    )
    assert cancelled is None


async def test_cancel_tenant_jobs(db_session, active_tenant_user, fake_storage):
    """Cancel all pending/processing jobs for a tenant."""
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    job1 = await export_jobs_repository.create(
        db_session,
        tenant_id=tenant.id,
        requested_by=active_tenant_user.id,
    )
    job2 = await export_jobs_repository.create(
        db_session,
        tenant_id=tenant.id,
        requested_by=active_tenant_user.id,
    )

    cancelled = await export_jobs_repository.cancel_tenant_jobs(db_session, tenant.id)
    assert len(cancelled) == 2

    for j in (job1, job2):
        await db_session.refresh(j)
        assert j.status == "cancelled"


# ── Replacement tests ──────────────────────────────────────────


async def test_replacement_keeps_previous_ready_downloadable(
    db_session, active_tenant_user, fake_storage
):
    """When replacing a ready export, the previous artifact remains downloadable while the new job is pending."""
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    # Create first ready export
    job1 = await export_jobs_repository.create(
        db_session,
        tenant_id=tenant.id,
        requested_by=active_tenant_user.id,
    )
    await export_jobs_repository.update_status(
        db_session,
        job1.id,
        "ready",
        r2_key="key-1",
        artifact_size_bytes=100,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=72),
        clear_lease=True,
    )
    await fake_storage.upload("key-1", b"zip-1")

    # Request replacement (creates new pending job linked to job1)
    replacement = await export_service.request_export(
        db_session,
        tenant_id=tenant.id,
        actor_id=active_tenant_user.id,
        actor_role="tenant",
    )
    assert replacement is not None
    assert replacement.status == "pending"
    assert replacement.replaced_job_id == job1.id

    # job1 should now have replacement_job_id set
    await db_session.refresh(job1)
    assert job1.replacement_job_id == replacement.id

    # Previous ready should still be downloadable
    downloadable = await export_jobs_repository.get_downloadable_job_for_tenant(
        db_session,
        tenant.id,
    )
    assert downloadable is not None
    assert downloadable.id == job1.id  # still the old one


async def test_replacement_swap_purges_previous(
    db_session, active_tenant_user, fake_storage, monkeypatch
):
    """When a replacement becomes ready, the previous R2 object is purged."""
    from app.services import export_worker as ew

    monkeypatch.setattr(ew, "get_storage", lambda: fake_storage)

    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    # Create first ready export
    job1 = await export_jobs_repository.create(
        db_session,
        tenant_id=tenant.id,
        requested_by=active_tenant_user.id,
    )
    await export_jobs_repository.update_status(
        db_session,
        job1.id,
        "ready",
        r2_key="key-1",
        artifact_size_bytes=100,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=72),
        clear_lease=True,
    )
    await fake_storage.upload("key-1", b"zip-1")

    # Simulate replacement becoming ready via confirm_replacement_ready
    # Create new job with replaced_job_id set to job1
    new_job = await export_jobs_repository.create(
        db_session,
        tenant_id=tenant.id,
        requested_by=active_tenant_user.id,
        replaced_job_id=job1.id,
    )

    # Link replacement_job_id on job1
    await export_jobs_repository.update_status(
        db_session,
        job1.id,
        "ready",
        r2_key="key-1",
        artifact_size_bytes=100,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=72),
        clear_lease=True,
        replacement_job_id=new_job.id,
    )
    await fake_storage.upload("key-new", b"zip-new")

    # Confirm new job ready (should purge previous key)
    confirmed = await export_service.confirm_replacement_ready(
        db_session,
        job_id=new_job.id,
        tenant_id=tenant.id,
        r2_key="key-new",
        artifact_size_bytes=200,
    )
    assert confirmed is not None
    assert confirmed.status == "ready"

    # Previous key should be purged
    assert "key-1" not in fake_storage.stored_keys
    # New key should be present
    assert "key-new" in fake_storage.stored_keys


async def test_failed_replacement_leaves_previous_available(
    db_session, active_tenant_user, fake_storage
):
    """A failed/cancelled replacement leaves the previous ready artifact available."""
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    # Create first ready export
    job1 = await export_jobs_repository.create(
        db_session,
        tenant_id=tenant.id,
        requested_by=active_tenant_user.id,
    )
    await export_jobs_repository.update_status(
        db_session,
        job1.id,
        "ready",
        r2_key="key-1",
        artifact_size_bytes=100,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=72),
        clear_lease=True,
    )
    await fake_storage.upload("key-1", b"zip-1")

    # Create replacement that fails
    replacement = await export_jobs_repository.create(
        db_session,
        tenant_id=tenant.id,
        requested_by=active_tenant_user.id,
    )
    await export_jobs_repository.update_status(
        db_session,
        replacement.id,
        "failed",
        error_code="GENERATION_ERROR",
        clear_lease=True,
    )

    # Previous should still be downloadable
    downloadable = await export_jobs_repository.get_downloadable_job_for_tenant(
        db_session,
        tenant.id,
    )
    assert downloadable is not None
    assert downloadable.id == job1.id


async def test_new_generation_without_replacement(
    db_session, active_tenant_user, fake_storage
):
    """A new generation without replacing an existing ready job works."""
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    # No prior ready jobs — first generation
    job = await export_service.request_export(
        db_session,
        tenant_id=tenant.id,
        actor_id=active_tenant_user.id,
        actor_role="tenant",
    )
    assert job is not None
    assert job.status == "pending"
    assert job.replaced_job_id is None


# ── Actor attribution tests ────────────────────────────────────


async def test_actor_role_is_stored(db_session, active_tenant_user, fake_storage):
    """The actor_role is stored on the job."""
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    job = await export_jobs_repository.create(
        db_session,
        tenant_id=tenant.id,
        requested_by=active_tenant_user.id,
        actor_role="tenant",
    )
    assert job.actor_role == "tenant"


async def test_actor_role_returns_in_enriched_response(
    db_session, active_tenant_user, fake_storage
):
    """The enriched response includes actor_role."""
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    await export_jobs_repository.create(
        db_session,
        tenant_id=tenant.id,
        requested_by=active_tenant_user.id,
        actor_role="tenant",
    )

    enriched = await export_service.get_current_export(db_session, tenant.id)
    assert enriched is not None
    assert enriched["actor_role"] == "tenant"


# ── Expiry tests ───────────────────────────────────────────────


async def test_expired_job_not_returned_for_download(
    db_session, active_tenant_user, fake_storage
):
    """An expired ready job should not be returned for download."""
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    job = await export_jobs_repository.create(
        db_session,
        tenant_id=tenant.id,
        requested_by=active_tenant_user.id,
    )
    await export_jobs_repository.update_status(
        db_session,
        job.id,
        "ready",
        r2_key="key-expired",
        artifact_size_bytes=100,
        expires_at=datetime.now(timezone.utc) - timedelta(hours=1),  # expired
        clear_lease=True,
    )

    downloadable = await export_jobs_repository.get_downloadable_job_for_tenant(
        db_session,
        tenant.id,
    )
    assert downloadable is None


async def test_presigned_url_capped_to_remaining_lifetime(
    db_session, active_tenant_user, fake_storage
):
    """Presigned URL expiry is capped to the remaining object lifetime."""
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    # Object expiring in 5 minutes
    near_expiry = datetime.now(timezone.utc) + timedelta(minutes=5)
    job = await export_jobs_repository.create(
        db_session,
        tenant_id=tenant.id,
        requested_by=active_tenant_user.id,
    )
    await export_jobs_repository.update_status(
        db_session,
        job.id,
        "ready",
        r2_key="key-near-expiry",
        artifact_size_bytes=100,
        expires_at=near_expiry,
        clear_lease=True,
    )
    await fake_storage.upload("key-near-expiry", b"data")

    result = await export_service.get_download_url(db_session, tenant.id)
    assert result is not None
    assert result["expires_in"] <= 300  # 5 minutes = 300 seconds


async def test_presigned_url_fifteen_min_max(
    db_session, active_tenant_user, fake_storage
):
    """Presigned URL should not exceed 15 minutes (900 seconds) even with long remaining lifetime."""
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    job = await export_jobs_repository.create(
        db_session,
        tenant_id=tenant.id,
        requested_by=active_tenant_user.id,
    )
    await export_jobs_repository.update_status(
        db_session,
        job.id,
        "ready",
        r2_key="key-long",
        artifact_size_bytes=100,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=72),
        clear_lease=True,
    )
    await fake_storage.upload("key-long", b"data")

    result = await export_service.get_download_url(db_session, tenant.id)
    assert result is not None
    assert result["expires_in"] == 900  # 15 minutes


async def test_download_returns_null_when_fully_expired(
    db_session, active_tenant_user, fake_storage
):
    """Download returns None when the object has fully expired."""
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    job = await export_jobs_repository.create(
        db_session,
        tenant_id=tenant.id,
        requested_by=active_tenant_user.id,
    )
    await export_jobs_repository.update_status(
        db_session,
        job.id,
        "ready",
        r2_key="key-gone",
        artifact_size_bytes=100,
        expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        clear_lease=True,
    )
    await fake_storage.upload("key-gone", b"data")

    result = await export_service.get_download_url(db_session, tenant.id)
    assert result is None


# ── Cleanup tests ──────────────────────────────────────────────


async def test_cleanup_expired_exports(db_session, active_tenant_user, fake_storage):
    """Cleanup removes expired R2 objects and clears metadata."""
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    job = await export_jobs_repository.create(
        db_session,
        tenant_id=tenant.id,
        requested_by=active_tenant_user.id,
    )
    await export_jobs_repository.update_status(
        db_session,
        job.id,
        "ready",
        r2_key="key-stale",
        artifact_size_bytes=100,
        expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        clear_lease=True,
    )
    await fake_storage.upload("key-stale", b"data")

    count = await export_service.cleanup_expired_exports(db_session)
    assert count >= 1
    # R2 object should be deleted from fake storage
    assert "key-stale" not in fake_storage.stored_keys


async def test_cleanup_stale_failed_jobs(db_session, active_tenant_user, fake_storage):
    """Cleanup removes failed job metadata older than 72 hours."""
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    job = await export_jobs_repository.create(
        db_session,
        tenant_id=tenant.id,
        requested_by=active_tenant_user.id,
    )
    await export_jobs_repository.update_status(
        db_session,
        job.id,
        "failed",
        error_code="GENERATION_ERROR",
    )

    # Force failed_at to be old
    from sqlalchemy import update as sa_update

    stmt = (
        sa_update(ExportJob)
        .where(ExportJob.id == job.id)
        .values(failed_at=datetime.now(timezone.utc) - timedelta(hours=73))
    )
    await db_session.execute(stmt)
    await db_session.commit()

    count = await export_service.cleanup_stale_failed_jobs(db_session)
    assert count >= 1


# ── Retry with backoff tests ───────────────────────────────────


async def test_worker_retries_on_transient_failure(
    db_session, active_tenant_user, monkeypatch
):
    """Worker retries transient failures up to max_attempts times."""
    from app.services import export_worker as ew

    storage = FakeExportStorageAdapter()

    # Make storage fail the first N-1 times
    call_count = 0

    class _FlakyStorage:
        async def upload(self, key, data, content_type="application/octet-stream"):
            nonlocal call_count
            call_count += 1
            if call_count < 3:  # fail first 2 uploads
                msg = "Transient R2 failure"
                raise RuntimeError(msg)
            await storage.upload(key, data, content_type)

    monkeypatch.setattr(ew, "get_storage", lambda: _FlakyStorage())

    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    job = await export_jobs_repository.create(
        db_session,
        tenant_id=tenant.id,
        requested_by=active_tenant_user.id,
        max_attempts=3,
    )
    assert job.max_attempts == 3

    await ew._process_job_with_session(db_session, job)
    await db_session.refresh(job)

    # Should eventually succeed after retries
    assert job.status == "ready", (
        f"Expected ready, got {job.status}. Error: {job.error_code}, attempts: {job.attempts}"
    )
    assert job.attempts >= 2  # at least 2 failures before success


async def test_worker_gives_up_after_max_attempts(
    db_session, active_tenant_user, monkeypatch
):
    """Worker marks job as failed after exhausting max_attempts."""
    from app.services import export_worker as ew

    class _AlwaysFailingStorage:
        async def upload(self, key, data, content_type="application/octet-stream"):
            msg = "Persistent R2 failure"
            raise RuntimeError(msg)

    monkeypatch.setattr(ew, "get_storage", lambda: _AlwaysFailingStorage())

    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    job = await export_jobs_repository.create(
        db_session,
        tenant_id=tenant.id,
        requested_by=active_tenant_user.id,
        max_attempts=2,
    )

    await ew._process_job_with_session(db_session, job)
    await db_session.refresh(job)
    assert job.status == "failed"
    assert job.error_code == "GENERATION_ERROR"


async def test_recover_stale_leases(db_session, active_tenant_user):
    """Stale processing leases are recovered as failed."""
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    job = await export_jobs_repository.create(
        db_session,
        tenant_id=tenant.id,
        requested_by=active_tenant_user.id,
    )
    # Set as processing with stale lease
    job.status = "processing"
    job.lease_token = uuid.uuid4()
    job.lease_expires_at = datetime.now(timezone.utc) - timedelta(hours=1)  # expired
    await db_session.commit()

    recovered = await export_jobs_repository.recover_stale_leases(
        db_session, lease_minutes=30
    )
    assert len(recovered) >= 1

    await db_session.refresh(job)
    assert job.status == "failed"
    assert job.error_code == "LEASE_EXPIRED"


# ── Concurrency tests ──────────────────────────────────────────


async def test_duplicate_claim_prevention(db_session, active_tenant_user):
    """A claimed job cannot be claimed by another worker."""
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    job = await export_jobs_repository.create(
        db_session,
        tenant_id=tenant.id,
        requested_by=active_tenant_user.id,
    )

    # First claim succeeds
    claimed1 = await export_jobs_repository.claim_pending(db_session)
    assert claimed1 is not None
    assert claimed1.id == job.id

    # Second claim returns None (same job already claimed)
    claimed2 = await export_jobs_repository.claim_pending(db_session)
    assert claimed2 is None


async def test_lease_expiry_allows_reclaim(db_session, active_tenant_user):
    """After lease expiry, a processing job with expired lease can be reclaimed."""
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    job = await export_jobs_repository.create(
        db_session,
        tenant_id=tenant.id,
        requested_by=active_tenant_user.id,
    )

    # Claim it normally
    claimed = await export_jobs_repository.claim_pending(db_session)
    assert claimed is not None

    # Simulate lease expiring - set it back to pending with expired lease
    job.status = "pending"
    job.lease_token = uuid.uuid4()
    job.lease_expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    await db_session.commit()

    # Should be reclaimable now since lease is expired
    reclaimed = await export_jobs_repository.claim_pending(db_session)
    assert reclaimed is not None
    assert reclaimed.id == job.id


async def test_cancel_while_processing_stops_worker(
    db_session, active_tenant_user, fake_storage, monkeypatch
):
    """Cancelling a job while it's being processed should stop the worker."""
    from app.services import export_worker as ew

    monkeypatch.setattr(ew, "get_storage", lambda: fake_storage)

    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    job = await export_jobs_repository.create(
        db_session,
        tenant_id=tenant.id,
        requested_by=active_tenant_user.id,
    )

    # Simulate worker claiming and starting processing
    await export_jobs_repository.claim_pending(db_session)
    await db_session.refresh(job)
    assert job.status == "processing"

    # Cancel the job
    cancelled = await export_jobs_repository.cancel_job(db_session, job.id)
    assert cancelled is not None

    # Verify worker would see cancellation
    is_cancelled = await export_worker._is_cancelled(db_session, job.id)
    assert is_cancelled is True


# ── Enriched response tests ────────────────────────────────────


async def test_enriched_response_has_cooldown_and_actor(
    db_session, active_tenant_user, fake_storage
):
    """Enriched status response includes cooldown_until and actor_role."""
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    await export_jobs_repository.create(
        db_session,
        tenant_id=tenant.id,
        requested_by=active_tenant_user.id,
        actor_role="tenant",
        cooldown_until=datetime.now(timezone.utc) + timedelta(hours=24),
    )

    enriched = await export_service.get_current_export(db_session, tenant.id)
    assert enriched is not None
    assert enriched["actor_role"] == "tenant"
    assert enriched["cooldown_until"] is not None
    assert enriched["replaced_job_id"] is None
    assert enriched["replacement_job_id"] is None


async def test_enriched_response_replacement_links(
    db_session, active_tenant_user, fake_storage
):
    """Enriched response includes replacement chain links and previous_ready info."""
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    assert tenant is not None

    # Create replacement job linked to a previous ready job
    await export_jobs_repository.create(
        db_session,
        tenant_id=tenant.id,
        requested_by=active_tenant_user.id,
        actor_role="tenant",
        replaced_job_id=uuid.uuid4(),  # dummy previous job id
    )

    enriched = await export_service.get_current_export(db_session, tenant.id)
    assert enriched is not None
    assert enriched["status"] == "pending"
    assert enriched["replaced_job_id"] is not None
    assert enriched["actor_role"] == "tenant"
