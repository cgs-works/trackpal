"""Tests for mailbox config, lookup jobs, and delivery log persistence."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.core.encryption import encrypt_value
from app.models import (
    Tenant,
    TenantMailbox,
)
from app.repositories import (
    mailbox_config_repository,
    mailbox_dedupe_repository,
    mailbox_lookup_repository,
)
from app.schemas.mailbox import GmailAppPasswordConnectRequest, MailboxAuthMethod

# ─── Helpers ───────────────────────────────────────────────────────────────


async def _seed_tenant(db_session) -> Tenant:
    from app.core.security import get_password_hash
    from app.models import User

    user = User(
        username=f"mailbox_t_{uuid.uuid4().hex[:8]}",
        password_hash=get_password_hash("pass"),
        role="tenant",
    )
    db_session.add(user)
    await db_session.flush()
    tenant = Tenant(
        owner_user_id=user.id,
        client_prefix=f"mbx{uuid.uuid4().hex[:2]}",
        name="Mailbox Test Tenant",
        is_active=True,
    )
    db_session.add(tenant)
    await db_session.commit()
    return tenant


async def _seed_mailbox(db_session, tenant_id: uuid.UUID, **overrides) -> TenantMailbox:
    kwargs = {
        "tenant_id": tenant_id,
        "mailbox_email": "codes@tenant.com",
        "auth_method": "oauth",
        "status": "connected",
    }
    kwargs.update(overrides)
    mb = TenantMailbox(**kwargs)
    db_session.add(mb)
    await db_session.commit()
    await db_session.refresh(mb)
    return mb


# ─── Gmail Schema Tests ────────────────────────────────────────────────────


def test_gmail_connect_request_requires_email_and_app_password() -> None:
    payload = GmailAppPasswordConnectRequest(
        mailbox_email="codes@example.com",
        app_password="abcd efgh ijkl mnop",
    )
    assert payload.mailbox_email == "codes@example.com"
    assert payload.app_password == "abcd efgh ijkl mnop"
    assert MailboxAuthMethod.app_password.value == "app_password"


def test_gmail_connect_request_rejects_empty_password() -> None:
    with pytest.raises(ValidationError):
        GmailAppPasswordConnectRequest(
            mailbox_email="codes@example.com", app_password=""
        )


# ─── TenantMailbox Repository ──────────────────────────────────────────────


class TestMailboxConfigRepository:
    """Mailbox config CRUD repository tests."""

    pytestmark = pytest.mark.asyncio

    async def test_create_and_get_by_tenant(self, db_session):
        tenant = await _seed_tenant(db_session)
        mb = TenantMailbox(
            tenant_id=tenant.id,
            mailbox_email="test@example.com",
            auth_method="oauth",
            status="disconnected",
        )
        created = await mailbox_config_repository.create(db_session, tenant.id, mb)
        assert created.id is not None
        assert created.mailbox_email == "test@example.com"
        assert created.auth_method == "oauth"

        fetched = await mailbox_config_repository.get_by_tenant(db_session, tenant.id)
        assert fetched is not None
        assert fetched.id == created.id

    async def test_get_by_tenant_not_found(self, db_session):
        result = await mailbox_config_repository.get_by_tenant(db_session, uuid.uuid4())
        assert result is None

    async def test_get_by_id_with_tenant_scope(self, db_session):
        tenant = await _seed_tenant(db_session)
        mb = await _seed_mailbox(db_session, tenant.id)

        # Same tenant — should find
        found = await mailbox_config_repository.get_by_id(
            db_session, mb.id, tenant_id=tenant.id
        )
        assert found is not None
        assert found.id == mb.id

        # Different tenant — should NOT find
        other_tenant = uuid.uuid4()
        not_found = await mailbox_config_repository.get_by_id(
            db_session, mb.id, tenant_id=other_tenant
        )
        assert not_found is None

    async def test_update_status_and_error(self, db_session):
        tenant = await _seed_tenant(db_session)
        mb = await _seed_mailbox(db_session, tenant.id, status="connected")

        await mailbox_config_repository.update_status(
            db_session, mb, "revoked", error="Token expired"
        )
        assert mb.status == "revoked"
        assert mb.last_connection_error == "Token expired"

    async def test_update_connection_test(self, db_session):
        tenant = await _seed_tenant(db_session)
        mb = await _seed_mailbox(db_session, tenant.id)

        await mailbox_config_repository.update_connection_test(
            db_session, mb, success=True
        )
        assert mb.last_connection_test_at is not None

    async def test_update_fields(self, db_session):
        tenant = await _seed_tenant(db_session)
        mb = await _seed_mailbox(db_session, tenant.id)

        await mailbox_config_repository.update(
            db_session, mb, mailbox_email="new@example.com"
        )
        assert mb.mailbox_email == "new@example.com"

    async def test_delete_mailbox(self, db_session):
        tenant = await _seed_tenant(db_session)
        mb = await _seed_mailbox(db_session, tenant.id)

        await mailbox_config_repository.delete(db_session, mb)

        fetched = await mailbox_config_repository.get_by_tenant(db_session, tenant.id)
        assert fetched is None

    async def test_count_by_status(self, db_session):
        tenant1 = await _seed_tenant(db_session)
        tenant2 = await _seed_tenant(db_session)

        await _seed_mailbox(db_session, tenant1.id, status="connected")
        await _seed_mailbox(db_session, tenant2.id, status="connected")

        count = await mailbox_config_repository.count_by_status(db_session, "connected")
        assert count >= 2


# ─── MailLookupJob Repository ──────────────────────────────────────────────


class TestMailboxLookupRepository:
    """Lookup job repository tests."""

    pytestmark = pytest.mark.asyncio

    async def test_create_job(self, db_session):
        tenant = await _seed_tenant(db_session)
        mb = await _seed_mailbox(db_session, tenant.id)

        job = await mailbox_lookup_repository.create_job(
            db_session, tenant.id, mb.id, "netflix"
        )
        assert job.id is not None
        assert job.status == "pending"
        assert job.service_key == "netflix"
        assert job.expires_at is not None

    async def test_get_job_with_tenant_scope(self, db_session):
        tenant = await _seed_tenant(db_session)
        mb = await _seed_mailbox(db_session, tenant.id)
        job = await mailbox_lookup_repository.create_job(
            db_session, tenant.id, mb.id, "disney"
        )

        # Same tenant
        found = await mailbox_lookup_repository.get_job(
            db_session, job.id, tenant_id=tenant.id
        )
        assert found is not None
        assert found.id == job.id

        # Different tenant
        not_found = await mailbox_lookup_repository.get_job(
            db_session, job.id, tenant_id=uuid.uuid4()
        )
        assert not_found is None

    async def test_cancel_active_job_if_present_marks_pending_job_failed(
        self, db_session
    ):
        tenant = await _seed_tenant(db_session)
        mb = await _seed_mailbox(db_session, tenant.id)
        job = await mailbox_lookup_repository.create_job(
            db_session,
            tenant.id,
            mb.id,
            "netflix",
        )

        cancelled = await mailbox_lookup_repository.cancel_active_job_if_present(
            db_session,
            job.id,
            tenant_id=tenant.id,
        )

        assert cancelled is True
        assert job.status == "failed"
        assert job.error_code == "user_cancelled"
        assert job.error_detail_safe == "User restarted codigo flow"
        assert job.completed_at is not None

    async def test_cancel_active_job_if_present_leaves_completed_job_unchanged(
        self, db_session
    ):
        tenant = await _seed_tenant(db_session)
        mb = await _seed_mailbox(db_session, tenant.id)
        job = await mailbox_lookup_repository.create_job(
            db_session,
            tenant.id,
            mb.id,
            "netflix",
        )
        await mailbox_lookup_repository.transition_status(db_session, job, "processing")
        await mailbox_lookup_repository.transition_status(
            db_session,
            job,
            "completed",
            result_type="code",
            result_value_encrypted=encrypt_value("227597"),
        )
        original_completed_at = job.completed_at

        cancelled = await mailbox_lookup_repository.cancel_active_job_if_present(
            db_session,
            job.id,
            tenant_id=tenant.id,
        )

        assert cancelled is False
        assert job.status == "completed"
        assert job.error_code is None
        assert job.completed_at == original_completed_at

    async def test_cancel_active_job_if_present_returns_false_for_missing_job(
        self, db_session
    ):
        tenant = await _seed_tenant(db_session)

        cancelled = await mailbox_lookup_repository.cancel_active_job_if_present(
            db_session,
            uuid.uuid4(),
            tenant_id=tenant.id,
        )

        assert cancelled is False

    async def test_transition_status_valid(self, db_session):
        tenant = await _seed_tenant(db_session)
        mb = await _seed_mailbox(db_session, tenant.id)
        job = await mailbox_lookup_repository.create_job(
            db_session, tenant.id, mb.id, "hbo"
        )

        # pending -> processing
        await mailbox_lookup_repository.transition_status(db_session, job, "processing")
        assert job.status == "processing"
        assert job.processing_started_at is not None

        # processing -> completed
        await mailbox_lookup_repository.transition_status(
            db_session,
            job,
            "completed",
            result_type="code",
            result_value_encrypted=encrypt_value("ABC123"),
        )
        assert job.status == "completed"
        assert job.result_type == "code"
        assert job.completed_at is not None

    async def test_transition_status_invalid(self, db_session):
        tenant = await _seed_tenant(db_session)
        mb = await _seed_mailbox(db_session, tenant.id)
        job = await mailbox_lookup_repository.create_job(
            db_session, tenant.id, mb.id, "spotify"
        )

        # pending -> completed directly is invalid
        with pytest.raises(ValueError, match="Invalid transition"):
            await mailbox_lookup_repository.transition_status(
                db_session, job, "completed"
            )

    async def test_transition_to_failed(self, db_session):
        tenant = await _seed_tenant(db_session)
        mb = await _seed_mailbox(db_session, tenant.id)
        job = await mailbox_lookup_repository.create_job(
            db_session, tenant.id, mb.id, "prime"
        )

        # pending -> processing -> failed
        await mailbox_lookup_repository.transition_status(db_session, job, "processing")
        await mailbox_lookup_repository.transition_status(
            db_session,
            job,
            "failed",
            error_code="oauth_revoked",
            error_detail_safe="Mailbox credentials revoked",
        )
        assert job.status == "failed"
        assert job.error_code == "oauth_revoked"

    async def test_transition_to_timeout(self, db_session):
        tenant = await _seed_tenant(db_session)
        mb = await _seed_mailbox(db_session, tenant.id)
        job = await mailbox_lookup_repository.create_job(
            db_session, tenant.id, mb.id, "netflix"
        )

        # pending -> timeout (valid direct transition)
        await mailbox_lookup_repository.transition_status(
            db_session,
            job,
            "timeout",
            error_code="timeout",
            error_detail_safe="SLA exceeded",
        )
        assert job.status == "timeout"

    async def test_list_pending_jobs(self, db_session):
        tenant = await _seed_tenant(db_session)
        mb = await _seed_mailbox(db_session, tenant.id)

        await mailbox_lookup_repository.create_job(db_session, tenant.id, mb.id, "a")
        await mailbox_lookup_repository.create_job(db_session, tenant.id, mb.id, "b")

        pending = await mailbox_lookup_repository.list_pending_jobs(db_session)
        assert len(pending) >= 2

    async def test_expire_stale_jobs(self, db_session):
        tenant = await _seed_tenant(db_session)
        mb = await _seed_mailbox(db_session, tenant.id)

        job = await mailbox_lookup_repository.create_job(
            db_session, tenant.id, mb.id, "stale"
        )
        # Set expires_at to past
        job.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        await db_session.flush()

        expired = await mailbox_lookup_repository.expire_stale_jobs(db_session)
        assert expired >= 1
        assert job.status == "timeout"

    async def test_delete_expired_jobs(self, db_session):
        tenant = await _seed_tenant(db_session)
        mb = await _seed_mailbox(db_session, tenant.id)

        job = await mailbox_lookup_repository.create_job(
            db_session, tenant.id, mb.id, "old"
        )
        job.expires_at = datetime.now(timezone.utc) - timedelta(days=5)
        await db_session.flush()

        deleted = await mailbox_lookup_repository.delete_expired_jobs(
            db_session,
            before=datetime.now(timezone.utc) - timedelta(days=1),
        )
        assert deleted >= 1

        # Verify gone
        fetched = await mailbox_lookup_repository.get_job(db_session, job.id)
        assert fetched is None


# ─── MailCodeDeliveryLog Repository ────────────────────────────────────────


class TestMailboxDedupeRepository:
    """Dedupe delivery log repository tests."""

    pytestmark = pytest.mark.asyncio

    async def test_record_and_check_delivery(self, db_session):
        tenant = await _seed_tenant(db_session)
        mb = await _seed_mailbox(db_session, tenant.id)

        entry = await mailbox_dedupe_repository.record_delivery(
            db_session,
            tenant_id=tenant.id,
            mailbox_id=mb.id,
            service_key="netflix",
            message_id="msg-001",
            fingerprint="sha256:::code=ABC123",
        )
        assert entry.id is not None
        assert entry.fingerprint == "sha256:::code=ABC123"

        # Check duplicate exists
        dup = await mailbox_dedupe_repository.is_duplicate(
            db_session,
            tenant_id=tenant.id,
            mailbox_id=mb.id,
            service_key="netflix",
            message_id="msg-001",
            fingerprint="sha256:::code=ABC123",
        )
        assert dup is True

        # Different fingerprint — not duplicate
        not_dup = await mailbox_dedupe_repository.is_duplicate(
            db_session,
            tenant_id=tenant.id,
            mailbox_id=mb.id,
            service_key="netflix",
            message_id="msg-001",
            fingerprint="sha256:::code=XYZ789",
        )
        assert not_dup is False

    async def test_fallback_dedup_no_message_id(self, db_session):
        tenant = await _seed_tenant(db_session)
        mb = await _seed_mailbox(db_session, tenant.id)

        await mailbox_dedupe_repository.record_delivery(
            db_session,
            tenant_id=tenant.id,
            mailbox_id=mb.id,
            service_key="disney",
            message_id=None,
            fingerprint="fallback::sender+subject",
        )

        # Same fingerprint without message_id — duplicate
        dup = await mailbox_dedupe_repository.is_duplicate(
            db_session,
            tenant_id=tenant.id,
            mailbox_id=mb.id,
            service_key="disney",
            message_id=None,
            fingerprint="fallback::sender+subject",
        )
        assert dup is True

        # Same fingerprint but WITH message_id — should NOT match
        not_dup = await mailbox_dedupe_repository.is_duplicate(
            db_session,
            tenant_id=tenant.id,
            mailbox_id=mb.id,
            service_key="disney",
            message_id="msg-002",
            fingerprint="fallback::sender+subject",
        )
        assert not_dup is False

    async def test_delete_older_than(self, db_session):
        tenant = await _seed_tenant(db_session)
        mb = await _seed_mailbox(db_session, tenant.id)

        # Create delivery with old timestamp
        entry = await mailbox_dedupe_repository.record_delivery(
            db_session,
            tenant_id=tenant.id,
            mailbox_id=mb.id,
            service_key="hbo",
            message_id="old-msg",
            fingerprint="old::fp",
        )
        # Manually backdate
        entry.delivered_at = datetime.now(timezone.utc) - timedelta(days=200)
        await db_session.flush()

        deleted = await mailbox_dedupe_repository.delete_older_than(
            db_session,
            before=datetime.now(timezone.utc) - timedelta(days=30),
        )
        assert deleted >= 1


# ─── Schema Validation ────────────────────────────────────────────────────


class TestMailboxSchemas:
    """Schema validation tests — no async needed."""

    def test_gmail_connect_request_valid(self):
        from app.schemas.mailbox import GmailAppPasswordConnectRequest

        req = GmailAppPasswordConnectRequest(
            mailbox_email="user@gmail.com", app_password="abcd efgh ijkl mnop"
        )
        assert req.mailbox_email == "user@gmail.com"
        assert req.app_password == "abcd efgh ijkl mnop"

    def test_lookup_create_request(self):
        from app.schemas.mailbox import LookupCreateRequest

        req = LookupCreateRequest(
            service_key="netflix", target_email="user@example.com"
        )
        assert req.service_key == "netflix"
        assert req.target_email == "user@example.com"

    def test_lookup_create_request_empty_fails(self):
        from app.schemas.mailbox import LookupCreateRequest

        with pytest.raises(ValidationError):
            LookupCreateRequest(service_key="")

    def test_enums_values(self):
        from app.schemas.mailbox import (
            MailboxAuthMethod,
            MailboxStatus,
            LookupJobStatus,
            LookupResultType,
        )

        assert MailboxAuthMethod.oauth.value == "oauth"
        assert MailboxAuthMethod.app_password.value == "app_password"
        assert MailboxStatus.connected.value == "connected"
        assert LookupJobStatus.completed.value == "completed"
        assert LookupResultType.code.value == "code"


# ─── Tenant Isolation ─────────────────────────────────────────────────────


class TestMailboxTenantIsolation:
    """Tenant isolation tests."""

    pytestmark = pytest.mark.asyncio

    async def test_mailbox_isolation(self, db_session):
        """Tenant A cannot access Tenant B's mailbox config."""
        tenant_a = await _seed_tenant(db_session)
        tenant_b = await _seed_tenant(db_session)

        mb = await _seed_mailbox(db_session, tenant_a.id)

        # Tenant B tries to get Tenant A's mailbox by tenant_id
        fetched = await mailbox_config_repository.get_by_tenant(db_session, tenant_b.id)
        assert fetched is None

        # Tenant B tries to get Tenant A's mailbox by id with tenant scope
        found = await mailbox_config_repository.get_by_id(
            db_session, mb.id, tenant_id=tenant_b.id
        )
        assert found is None

    async def test_lookup_job_isolation(self, db_session):
        """Tenant A cannot access Tenant B's lookup jobs."""
        tenant_a = await _seed_tenant(db_session)
        tenant_b = await _seed_tenant(db_session)

        mb_a = await _seed_mailbox(db_session, tenant_a.id)
        job_a = await mailbox_lookup_repository.create_job(
            db_session, tenant_a.id, mb_a.id, "netflix"
        )

        # Tenant B tries to get job by id with tenant scope
        found = await mailbox_lookup_repository.get_job(
            db_session, job_a.id, tenant_id=tenant_b.id
        )
        assert found is None

    async def test_delivery_log_isolation(self, db_session):
        """Tenant A delivery log not visible to Tenant B."""
        tenant_a = await _seed_tenant(db_session)
        tenant_b = await _seed_tenant(db_session)
        mb_a = await _seed_mailbox(db_session, tenant_a.id)

        # Record for tenant A
        await mailbox_dedupe_repository.record_delivery(
            db_session,
            tenant_id=tenant_a.id,
            mailbox_id=mb_a.id,
            service_key="hbo",
            message_id="msg-a",
            fingerprint="fp-a",
        )

        # Tenant B checks — should not be duplicate
        dup = await mailbox_dedupe_repository.is_duplicate(
            db_session,
            tenant_id=tenant_b.id,
            mailbox_id=mb_a.id,
            service_key="hbo",
            message_id="msg-a",
            fingerprint="fp-a",
        )
        assert dup is False
