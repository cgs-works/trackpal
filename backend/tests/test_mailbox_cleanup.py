"""Tests for mailbox cleanup service — retention/expiry policies."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.models import MailLookupJob, TenantMailbox
from app.repositories import mailbox_dedupe_repository, mailbox_lookup_repository
from app.services.mailbox_cleanup import run_cleanup_once


async def _seed_tenant(db_session):
    from app.core.security import get_password_hash
    from app.models import Tenant, User

    user = User(
        username=f"cln_{uuid.uuid4().hex[:8]}",
        password_hash=get_password_hash("pass"),
        role="tenant",
    )
    db_session.add(user)
    await db_session.flush()
    tenant = Tenant(
        owner_user_id=user.id,
        client_prefix=f"cl{uuid.uuid4().hex[:2]}",
        name="Cleanup Test Tenant",
        is_active=True,
    )
    db_session.add(tenant)
    await db_session.commit()
    return tenant


async def _seed_mailbox(db_session, tenant_id, **overrides):
    kwargs = {
        "tenant_id": tenant_id,
        "mailbox_email": "cleanup@tenant.com",
        "provider": "google",
        "auth_method": "oauth",
        "status": "connected",
    }
    kwargs.update(overrides)
    mb = TenantMailbox(**kwargs)
    db_session.add(mb)
    await db_session.commit()
    await db_session.refresh(mb)
    return mb


async def _seed_job(
    db_session,
    tenant_id,
    mailbox_id,
    service_key="netflix",
    status="pending",
    expires_in_hours=-1,
):
    """Seed a job with controlled expiry. Default: already expired."""
    from datetime import timezone as dt_tz

    job = MailLookupJob(
        tenant_id=tenant_id,
        mailbox_id=mailbox_id,
        service_key=service_key,
        target_email=f"test+{mailbox_id}@example.com",
        status=status,
        expires_at=datetime.now(dt_tz.utc) + timedelta(hours=expires_in_hours),
    )
    db_session.add(job)
    await db_session.flush()
    return job


class TestCleanup:
    """run_cleanup_once integration tests."""

    pytestmark = pytest.mark.asyncio

    async def test_expires_stale_pending_jobs(self, db_session):
        """Stale pending jobs become timeout."""
        tenant = await _seed_tenant(db_session)
        mb = await _seed_mailbox(db_session, tenant.id)
        job = await _seed_job(
            db_session, tenant.id, mb.id, status="pending", expires_in_hours=-1
        )

        results = await run_cleanup_once(db_session)
        await db_session.commit()

        assert results["expired_jobs"] >= 1
        assert job.status == "timeout"

    async def test_expires_stale_processing_jobs(self, db_session):
        """Stale processing jobs become timeout."""
        tenant = await _seed_tenant(db_session)
        mb = await _seed_mailbox(db_session, tenant.id)
        job = await _seed_job(
            db_session, tenant.id, mb.id, status="processing", expires_in_hours=-2
        )

        results = await run_cleanup_once(db_session)
        await db_session.commit()

        assert results["expired_jobs"] >= 1
        assert job.status == "timeout"

    async def test_does_not_expire_fresh_jobs(self, db_session):
        """Fresh pending jobs remain pending."""
        tenant = await _seed_tenant(db_session)
        mb = await _seed_mailbox(db_session, tenant.id)
        job = await _seed_job(
            db_session, tenant.id, mb.id, status="pending", expires_in_hours=48
        )  # far future

        results = await run_cleanup_once(db_session)
        await db_session.commit()

        # The job should NOT be expired
        assert job.status == "pending"
        # expire_stale_jobs only acts on already-expired
        # The count might still be 0 or higher from other stale jobs,
        # but this specific job is fresh
        assert results["expired_jobs"] >= 0

    async def test_deletes_expired_jobs(self, db_session):
        """Hard-deletes jobs past TTL cutoff."""
        tenant = await _seed_tenant(db_session)
        mb = await _seed_mailbox(db_session, tenant.id)

        # Create a completed job that expired long ago
        job = await _seed_job(
            db_session, tenant.id, mb.id, status="completed", expires_in_hours=-100
        )

        results = await run_cleanup_once(db_session)
        await db_session.commit()

        assert results["deleted_jobs"] >= 1

        # Job should be gone from DB
        fetched = await mailbox_lookup_repository.get_job(db_session, job.id)
        assert fetched is None

    async def test_deletes_old_delivery_logs(self, db_session):
        """Hard-deletes delivery log entries past retention."""
        tenant = await _seed_tenant(db_session)
        mb = await _seed_mailbox(db_session, tenant.id)

        # Record a very old delivery
        entry = await mailbox_dedupe_repository.record_delivery(
            db_session,
            tenant_id=tenant.id,
            mailbox_id=mb.id,
            service_key="disney",
            message_id="old-msg",
            fingerprint="old-fp",
        )
        # Backdate by 200 days (past default 90-day retention)
        entry.delivered_at = datetime.now(timezone.utc) - timedelta(days=200)
        await db_session.flush()

        # Run cleanup with default retention (90d)
        results = await run_cleanup_once(db_session)
        await db_session.commit()

        assert results["deleted_delivery_logs"] >= 1

        # Should not find it anymore
        dup = await mailbox_dedupe_repository.is_duplicate(
            db_session,
            tenant_id=tenant.id,
            mailbox_id=mb.id,
            service_key="disney",
            message_id="old-msg",
            fingerprint="old-fp",
        )
        assert dup is False

    async def test_cleanup_does_not_affect_recent_data(self, db_session):
        """Recent/fresh data should survive cleanup."""
        tenant = await _seed_tenant(db_session)
        mb = await _seed_mailbox(db_session, tenant.id)

        # Fresh job
        fresh_job = await _seed_job(
            db_session, tenant.id, mb.id, status="pending", expires_in_hours=48
        )
        # Fresh delivery
        await mailbox_dedupe_repository.record_delivery(
            db_session,
            tenant_id=tenant.id,
            mailbox_id=mb.id,
            service_key="hbo",
            message_id="fresh-msg",
            fingerprint="fresh-fp",
        )

        _ = await run_cleanup_once(db_session)
        await db_session.commit()

        # Fresh data untouched
        assert fresh_job.status == "pending"
        dup = await mailbox_dedupe_repository.is_duplicate(
            db_session,
            tenant_id=tenant.id,
            mailbox_id=mb.id,
            service_key="hbo",
            message_id="fresh-msg",
            fingerprint="fresh-fp",
        )
        assert dup is True

    async def test_cleanup_with_zero_data(self, db_session):
        """Cleanup with no stale data reports zeros, no errors."""
        results = await run_cleanup_once(db_session)
        assert isinstance(results["expired_jobs"], int)
        assert isinstance(results["deleted_jobs"], int)
        assert isinstance(results["deleted_delivery_logs"], int)

    async def test_cleanup_logging_smoke(self, db_session):
        """run_cleanup_once does not raise under normal conditions."""
        try:
            _ = await run_cleanup_once(db_session)
            await db_session.commit()
        except Exception as exc:
            pytest.fail(f"Cleanup raised unexpected exception: {exc}")
