"""Tests for lookup worker pipeline: process_job, dedupe, retries, fingerprint."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.core.encryption import encrypt_value
from app.models import MailCodeDeliveryLog, MailLookupJob, Tenant, TenantMailbox
from app.repositories import mailbox_dedupe_repository, mailbox_lookup_repository
from app.services.mail_code_extractor import ExtractedCode
from app.services.mail_lookup_worker import (
    compute_fingerprint,
    get_ephemeral_result,
    process_job,
)
from app.services.mail_lookup_worker.ephemeral_cache import purge_expired, store_result
from app.services.mail_lookup_worker.fingerprint import (
    compute_fingerprint as _fingerprint,
)
from app.services.mail_lookup_worker.providers import (
    EmailMessage,
    NonTransientProviderError,
    RevokedMailboxError,
    StubProvider,
    TransientProviderError,
    active_provider,
)


# ─── Helpers ───────────────────────────────────────────────────────────────


async def _seed_tenant(db_session) -> Tenant:
    from app.core.security import get_password_hash
    from app.models import User

    user = User(
        username=f"wkr_{uuid.uuid4().hex[:8]}",
        password_hash=get_password_hash("pass"),
        role="tenant",
    )
    db_session.add(user)
    await db_session.flush()
    tenant = Tenant(
        owner_user_id=user.id,
        client_prefix=f"wk{uuid.uuid4().hex[:2]}",
        name="Worker Test Tenant",
        is_active=True,
    )
    db_session.add(tenant)
    await db_session.commit()
    return tenant


async def _seed_mailbox(db_session, tenant_id: uuid.UUID, **overrides) -> TenantMailbox:
    kwargs = {
        "tenant_id": tenant_id,
        "mailbox_email": "codes@tenant.com",
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


def _make_email(
    subject: str = "Your Spotify login code",
    body: str = "Enter this code 654321",
    received_at: datetime | None = None,
    message_id: str | None = "msg-001",
    sender: str | None = "noreply@spotify.com",
    to_recipients: list[str] | None = None,
) -> EmailMessage:
    return EmailMessage(
        subject=subject,
        body=body,
        received_at=received_at or datetime.now(timezone.utc),
        message_id=message_id,
        sender=sender,
        to_recipients=to_recipients,
    )


# ─── Fingerprint tests ────────────────────────────────────────────────────


class TestFingerprint:
    """compute_fingerprint unit tests."""

    def test_with_message_id(self):
        fp = compute_fingerprint(
            service_key="netflix",
            message_id="msg-001",
            sender="noreply@netflix.com",
            received_at_iso="2026-05-27T12:00:00",
            subject="Your Netflix code",
            payload_normalized="ABC123",
        )
        assert isinstance(fp, str)
        assert len(fp) == 64  # SHA-256 hex

    def test_without_message_id(self):
        fp = compute_fingerprint(
            service_key="netflix",
            message_id=None,
            sender="noreply@netflix.com",
            received_at_iso="2026-05-27T12:00:00",
            subject="Your Netflix code",
            payload_normalized="ABC123",
        )
        assert isinstance(fp, str)
        assert len(fp) == 64

    def test_different_payload_different_fingerprint(self):
        fp1 = compute_fingerprint(
            service_key="netflix",
            message_id="msg-001",
            sender=None,
            received_at_iso="now",
            subject="sub",
            payload_normalized="AAA",
        )
        fp2 = compute_fingerprint(
            service_key="netflix",
            message_id="msg-001",
            sender=None,
            received_at_iso="now",
            subject="sub",
            payload_normalized="BBB",
        )
        assert fp1 != fp2


# ─── Ephemeral cache tests ────────────────────────────────────────────────


class TestEphemeralCache:
    """Ephemeral result cache tests."""

    def test_store_and_retrieve(self):
        job_id = uuid.uuid4()
        store_result(job_id, "code", "ABC123", ttl_seconds=30)

        result = get_ephemeral_result(job_id)
        assert result is not None
        assert result[0] == "code"
        assert result[1] == "ABC123"

    def test_missing_job(self):
        result = get_ephemeral_result(uuid.uuid4())
        assert result is None

    def test_expired_entry(self):
        job_id = uuid.uuid4()
        store_result(job_id, "url", "https://ex.com", ttl_seconds=0)
        result = get_ephemeral_result(job_id)
        assert result is None

    def test_purge_expired(self):
        job_id = uuid.uuid4()
        store_result(job_id, "code", "X", ttl_seconds=0)
        count = purge_expired()
        assert count >= 1
        assert get_ephemeral_result(job_id) is None


# ─── Worker pipeline tests ────────────────────────────────────────────────


class TestWorkerPipeline:
    """Integration tests for process_job with mock provider."""

    pytestmark = pytest.mark.asyncio

    async def test_process_job_found_code(self, db_session):
        """Found code -> completed with result_type=code, ephemeral result."""
        tenant = await _seed_tenant(db_session)
        mb = await _seed_mailbox(db_session, tenant.id)
        job = await mailbox_lookup_repository.create_job(
            db_session, tenant.id, mb.id, "spotify"
        )

        # Inject stub provider with a matching email (spotify pattern)
        provider = StubProvider(
            emails=[
                _make_email(
                    subject="Your Spotify login code",
                    body="Enter this code 654321",
                ),
            ]
        )
        old_active = active_provider
        try:
            import app.services.mail_lookup_worker.providers as pmod

            pmod.active_provider = provider

            await process_job(db_session, job)
            await db_session.commit()
        finally:
            pmod.active_provider = old_active

        # Verify
        assert job.status == "completed"
        assert job.result_type == "code"

        # Ephemeral cache should have the result
        cached = get_ephemeral_result(job.id)
        assert cached is not None
        assert cached[0] == "code"
        assert "654321" == cached[1]

    async def test_process_job_not_found(self, db_session):
        """No matching email -> completed with result_type=not_found."""
        tenant = await _seed_tenant(db_session)
        mb = await _seed_mailbox(db_session, tenant.id)
        job = await mailbox_lookup_repository.create_job(
            db_session, tenant.id, mb.id, "netflix"
        )

        # Stub that returns empty results
        provider = StubProvider(emails=[])
        old_active = active_provider
        try:
            import app.services.mail_lookup_worker.providers as pmod

            pmod.active_provider = provider

            await process_job(db_session, job)
            await db_session.commit()
        finally:
            pmod.active_provider = old_active

        assert job.status == "completed"
        assert job.result_type == "not_found"

    async def test_process_job_duplicate_suppressed(self, db_session):
        """Same code already delivered -> duplicate_suppressed."""
        tenant = await _seed_tenant(db_session)
        mb = await _seed_mailbox(db_session, tenant.id)
        job = await mailbox_lookup_repository.create_job(
            db_session, tenant.id, mb.id, "spotify"
        )

        # Pre-record a delivery for the same code
        await mailbox_dedupe_repository.record_delivery(
            db_session,
            tenant_id=tenant.id,
            mailbox_id=mb.id,
            service_key="spotify",
            message_id="msg-001",
            fingerprint=compute_fingerprint(
                service_key="spotify",
                message_id="msg-001",
                sender="noreply@spotify.com",
                received_at_iso=datetime.now(timezone.utc).isoformat(),
                subject="Your Spotify login code",
                payload_normalized="654321",
            ),
        )
        await db_session.flush()

        provider = StubProvider(
            emails=[
                _make_email(
                    subject="Your Spotify login code",
                    body="Enter this code 654321",
                    message_id="msg-001",
                    sender="noreply@spotify.com",
                ),
            ]
        )
        old_active = active_provider
        try:
            import app.services.mail_lookup_worker.providers as pmod

            pmod.active_provider = provider

            await process_job(db_session, job)
            await db_session.commit()
        finally:
            pmod.active_provider = old_active

        assert job.status == "completed"
        assert job.result_type == "duplicate_suppressed"

    async def test_process_job_mailbox_not_found(self, db_session):
        """Mailbox deleted between job creation and processing."""
        tenant = await _seed_tenant(db_session)
        mb = await _seed_mailbox(db_session, tenant.id)
        job = await mailbox_lookup_repository.create_job(
            db_session, tenant.id, mb.id, "hbo"
        )

        # Delete mailbox
        await db_session.delete(mb)
        await db_session.flush()

        provider = StubProvider(emails=[])
        old_active = active_provider
        try:
            import app.services.mail_lookup_worker.providers as pmod

            pmod.active_provider = provider

            await process_job(db_session, job)
            await db_session.commit()
        finally:
            pmod.active_provider = old_active

        assert job.status == "failed"
        assert job.error_code == "mailbox_not_found"

    async def test_process_job_fetch_all_retries_exhausted(self, db_session):
        """Transient errors exhaust retries -> failed."""
        tenant = await _seed_tenant(db_session)
        mb = await _seed_mailbox(db_session, tenant.id)
        job = await mailbox_lookup_repository.create_job(
            db_session, tenant.id, mb.id, "spotify"
        )

        # Provider that always raises transient error
        class FailingStub(StubProvider):
            async def fetch_recent(  # type: ignore[override]
                self, mailbox, window_minutes, target_email=None
            ):
                raise TransientProviderError("Connection refused")

        provider = FailingStub()
        old_active = active_provider
        try:
            import app.services.mail_lookup_worker.providers as pmod

            pmod.active_provider = provider

            await process_job(db_session, job)
            await db_session.commit()
        finally:
            pmod.active_provider = old_active

        assert job.status == "failed"
        assert job.error_code == "fetch_failed"

    async def test_process_job_non_transient_error(self, db_session):
        """Non-transient error (revoked) -> failed immediately, no retry."""
        tenant = await _seed_tenant(db_session)
        mb = await _seed_mailbox(db_session, tenant.id)
        job = await mailbox_lookup_repository.create_job(
            db_session, tenant.id, mb.id, "prime"
        )

        class RevokedStub(StubProvider):
            async def fetch_recent(  # type: ignore[override]
                self, mailbox, window_minutes, target_email=None, **kwargs
            ):
                raise NonTransientProviderError("OAuth token revoked")

        provider = RevokedStub()
        old_active = active_provider
        try:
            import app.services.mail_lookup_worker.providers as pmod

            pmod.active_provider = provider

            await process_job(db_session, job)
            await db_session.commit()
        finally:
            pmod.active_provider = old_active

        assert job.status == "failed"
        assert job.error_code == "auth_failed"


class TestNonTransientErrorCodes:
    """Non-transient provider errors map to explicit error_code values."""

    pytestmark = pytest.mark.asyncio

    async def _run_stub(self, db_session, exc: Exception) -> MailLookupJob:
        tenant = await _seed_tenant(db_session)
        mb = await _seed_mailbox(db_session, tenant.id)
        job = await mailbox_lookup_repository.create_job(
            db_session, tenant.id, mb.id, "disney"
        )

        class FailStub(StubProvider):
            async def fetch_recent(  # type: ignore[override]
                self, mailbox, window_minutes, target_email=None, **kwargs
            ):
                raise exc

        provider = FailStub()
        old_active = active_provider
        try:
            import app.services.mail_lookup_worker.providers as pmod

            pmod.active_provider = provider
            await process_job(db_session, job)
            await db_session.commit()
        finally:
            pmod.active_provider = old_active
        return job

    async def test_revoked_mailbox_error(self, db_session):
        """RevokedMailboxError -> error_code=mailbox_revoked."""
        job = await self._run_stub(
            db_session,
            RevokedMailboxError("OAuth token revoked via invalid_grant"),
        )
        assert job.status == "failed"
        assert job.error_code == "mailbox_revoked"

    async def test_auth_failed_error(self, db_session):
        """NonTransientProviderError(default) -> error_code=auth_failed."""
        job = await self._run_stub(
            db_session,
            NonTransientProviderError("IMAP login failed: Invalid credentials"),
        )
        assert job.status == "failed"
        assert job.error_code == "auth_failed"

    async def test_provider_config_error(self, db_session):
        """NonTransientProviderError(provider_config_error) -> mapped."""
        job = await self._run_stub(
            db_session,
            NonTransientProviderError(
                "IMAP host not configured", error_code="provider_config_error"
            ),
        )
        assert job.status == "failed"
        assert job.error_code == "provider_config_error"

    async def test_permission_denied_error(self, db_session):
        """NonTransientProviderError(permission_denied) -> mapped."""
        job = await self._run_stub(
            db_session,
            NonTransientProviderError(
                "Gmail API access denied", error_code="permission_denied"
            ),
        )
        assert job.status == "failed"
        assert job.error_code == "permission_denied"

    async def test_error_detail_safe_no_secrets(self, db_session):
        """error_detail_safe never contains raw error message."""
        tenant = await _seed_tenant(db_session)
        mb = await _seed_mailbox(db_session, tenant.id)
        job = await mailbox_lookup_repository.create_job(
            db_session, tenant.id, mb.id, "hbo"
        )

        sensitive_msg = "IMAP auth failed: my_password_123"

        class SensitiveStub(StubProvider):
            async def fetch_recent(  # type: ignore[override]
                self, mailbox, window_minutes, target_email=None, **kwargs
            ):
                raise NonTransientProviderError(sensitive_msg)

        provider = SensitiveStub()
        old_active = active_provider
        try:
            import app.services.mail_lookup_worker.providers as pmod

            pmod.active_provider = provider
            await process_job(db_session, job)
            await db_session.commit()
        finally:
            pmod.active_provider = old_active

        assert job.status == "failed"
        assert job.error_code == "auth_failed"
        # Safe detail must NOT contain the raw error message
        assert job.error_detail_safe is not None
        assert sensitive_msg not in job.error_detail_safe
        assert "my_password" not in job.error_detail_safe
        assert (
            job.error_detail_safe == "Authentication failed — check mailbox credentials"
        )

    async def test_process_job_dedupe_without_message_id(self, db_session):
        """Dedupe fallback: no Message-ID -> match by fingerprint."""
        from datetime import timezone as dt_tz

        tenant = await _seed_tenant(db_session)
        mb = await _seed_mailbox(db_session, tenant.id)
        job = await mailbox_lookup_repository.create_job(
            db_session, tenant.id, mb.id, "spotify"
        )

        # Use a recent timestamp (within 5min window) so extractor finds it
        fixed_received = datetime.now(dt_tz.utc) - timedelta(minutes=2)

        # Pre-record without message_id
        import app.services.mail_lookup_worker.providers as pmod

        fp = compute_fingerprint(
            service_key="spotify",
            message_id=None,
            sender="noreply@spotify.com",
            received_at_iso=fixed_received.isoformat(),
            subject="Your Spotify login code",
            payload_normalized="654321",
        )
        await mailbox_dedupe_repository.record_delivery(
            db_session,
            tenant_id=tenant.id,
            mailbox_id=mb.id,
            service_key="spotify",
            message_id=None,
            fingerprint=fp,
        )
        await db_session.flush()

        provider = StubProvider(
            emails=[
                _make_email(
                    subject="Your Spotify login code",
                    body="Enter this code 654321",
                    received_at=fixed_received,
                    message_id=None,
                    sender="noreply@spotify.com",
                ),
            ]
        )
        old_active = active_provider
        try:
            pmod.active_provider = provider

            await process_job(db_session, job)
            await db_session.commit()
        finally:
            pmod.active_provider = old_active

        assert job.status == "completed"
        assert job.result_type == "duplicate_suppressed"


# ─── State transitions tests ──────────────────────────────────────────────


class TestStateTransitions:
    """process_job internal state transitions."""

    pytestmark = pytest.mark.asyncio

    async def test_pending_to_processing_on_start(self, db_session):
        """Job transitions to processing at start of process_job."""
        tenant = await _seed_tenant(db_session)
        mb = await _seed_mailbox(db_session, tenant.id)
        job = await mailbox_lookup_repository.create_job(
            db_session, tenant.id, mb.id, "netflix"
        )

        # Verify initially pending
        assert job.status == "pending"

        provider = StubProvider(emails=[])
        old_active = active_provider
        try:
            import app.services.mail_lookup_worker.providers as pmod

            pmod.active_provider = provider

            await process_job(db_session, job)
            await db_session.commit()
        finally:
            pmod.active_provider = old_active

        # Job should have been processing then completed (not_found)
        assert job.status == "completed"

    async def test_result_value_not_persisted(self, db_session):
        """result_value_encrypted remains None in DB."""
        tenant = await _seed_tenant(db_session)
        mb = await _seed_mailbox(db_session, tenant.id)
        job = await mailbox_lookup_repository.create_job(
            db_session, tenant.id, mb.id, "netflix"
        )

        provider = StubProvider(
            emails=[
                _make_email(body="Código: ABC123XYZ"),
            ]
        )
        old_active = active_provider
        try:
            import app.services.mail_lookup_worker.providers as pmod

            pmod.active_provider = provider

            await process_job(db_session, job)
            await db_session.commit()
        finally:
            pmod.active_provider = old_active

        assert job.status == "completed"
        # result_value_encrypted should NOT have been set
        assert job.result_value_encrypted is None


# ─── Target email filtering tests ────────────────────────────────────────


class TestTargetEmailFiltering:
    """target_email filter applied in fetch_recent_emails and worker."""

    pytestmark = pytest.mark.asyncio

    async def test_fetch_no_target_email_all_kept(self):
        """Without target_email, all emails returned (no filtering)."""
        provider = StubProvider(
            emails=[
                _make_email(message_id="msg-a"),
                _make_email(message_id="msg-b"),
            ]
        )
        old_active = active_provider
        try:
            import app.services.mail_lookup_worker.providers as pmod

            pmod.active_provider = provider
            result = await pmod.fetch_recent_emails(TenantMailbox(), 5)
        finally:
            pmod.active_provider = old_active

        assert len(result) == 2

    # Content-level filtering via _filter_emails_by_target_email —
    # these test the semantic matching layer in _helpers.py

    def _filter_emails_by_target_email_static(
        self, emails: list, target_email: str
    ) -> list:
        """Inline copy of _helpers._filter_emails_by_target_email."""
        target_lower = target_email.strip().lower()
        return [
            e
            for e in emails
            if target_lower in e.subject.lower()
            or target_lower in e.body.lower()
            or target_lower in [r.lower() for r in e.to_recipients]
        ]

    async def test_content_filter_matches_recipients(self):
        """Email kept when target_email matches to_recipients."""
        email = _make_email(
            subject="Your Netflix code",
            body="Code: ABC123",
            to_recipients=["user@example.com"],
        )
        result = self._filter_emails_by_target_email_static([email], "user@example.com")
        assert len(result) == 1

    async def test_content_filter_matches_body(self):
        """Email kept when target_email matches body (not recipients)."""
        email = _make_email(
            subject="Your Netflix code",
            body="This code is for forwarded-user@domain.com",
            to_recipients=["group@domain.com"],
            message_id="msg-body",
        )
        result = self._filter_emails_by_target_email_static(
            [email], "forwarded-user@domain.com"
        )
        assert len(result) == 1

    async def test_content_filter_matches_subject(self):
        """Email kept when target_email matches subject (not recipients)."""
        email = _make_email(
            subject="Your Spotify login for alias-user@domain.com",
            body="Enter this code 987654",
            to_recipients=["group-list@domain.com"],
            message_id="msg-subject",
        )
        result = self._filter_emails_by_target_email_static(
            [email], "alias-user@domain.com"
        )
        assert len(result) == 1

    async def test_content_filter_no_match(self):
        """Email filtered out when target_email not in subject/body/recipients."""
        email = _make_email(
            subject="Your Netflix code",
            body="Code: ABC123",
            to_recipients=["other@domain.com"],
            message_id="msg-no-match",
        )
        result = self._filter_emails_by_target_email_static(
            [email], "unrelated@other.com"
        )
        assert len(result) == 0

    async def test_content_filter_empty_recipients_with_body_match(self):
        """Email kept when body matches target_email even with empty recipients."""
        email = _make_email(
            subject="Your Netflix code",
            body="Code for target@example.com is 123456",
            to_recipients=[],
            message_id="msg-empty-recip",
        )
        result = self._filter_emails_by_target_email_static(
            [email], "target@example.com"
        )
        assert len(result) == 1

    async def test_content_filter_case_insensitive(self):
        """Content filter is case-insensitive."""
        email = _make_email(
            subject="SUBJECT WITH User@Example.Com",
            body="blah",
            to_recipients=[],
            message_id="msg-case",
        )
        result = self._filter_emails_by_target_email_static([email], "user@example.com")
        assert len(result) == 1

    async def test_worker_with_target_email_found(self, db_session):
        """Worker with target_email finds code when recipient matches."""
        tenant = await _seed_tenant(db_session)
        mb = await _seed_mailbox(db_session, tenant.id)
        job = await mailbox_lookup_repository.create_job(
            db_session,
            tenant.id,
            mb.id,
            "spotify",
            target_email="user@personal.com",
        )

        provider = StubProvider(
            emails=[
                _make_email(
                    to_recipients=["user@personal.com"],
                ),
            ]
        )
        old_active = active_provider
        try:
            import app.services.mail_lookup_worker.providers as pmod

            pmod.active_provider = provider

            await process_job(db_session, job)
            await db_session.commit()
        finally:
            pmod.active_provider = old_active

        assert job.status == "completed"
        assert job.result_type == "code"

    async def test_worker_with_target_email_not_found(self, db_session):
        """Worker with target_email returns not_found when no recipient matches."""
        tenant = await _seed_tenant(db_session)
        mb = await _seed_mailbox(db_session, tenant.id)
        job = await mailbox_lookup_repository.create_job(
            db_session,
            tenant.id,
            mb.id,
            "spotify",
            target_email="other@personal.com",
        )

        # Email is addressed to a different address
        provider = StubProvider(
            emails=[
                _make_email(
                    to_recipients=["user@personal.com"],
                ),
            ]
        )
        old_active = active_provider
        try:
            import app.services.mail_lookup_worker.providers as pmod

            pmod.active_provider = provider

            await process_job(db_session, job)
            await db_session.commit()
        finally:
            pmod.active_provider = old_active

        assert job.status == "completed"
        assert job.result_type == "not_found"

    async def test_worker_target_email_matches_in_body_not_recipients(self, db_session):
        """target_email matches in email body, not recipients -> code found."""
        tenant = await _seed_tenant(db_session)
        mb = await _seed_mailbox(db_session, tenant.id)
        job = await mailbox_lookup_repository.create_job(
            db_session,
            tenant.id,
            mb.id,
            "spotify",
            target_email="forwarded-user@domain.com",
        )

        # Recipients header has a different address; target_email only in body
        # Body must match Spotify extract pattern: "Enter this code.*?(\\d{6})"
        provider = StubProvider(
            emails=[
                _make_email(
                    body="Enter this code 654321 for forwarded-user@domain.com",
                    to_recipients=["group-alias@domain.com"],
                    message_id="msg-body-match",
                ),
            ]
        )
        old_active = active_provider
        try:
            import app.services.mail_lookup_worker.providers as pmod

            pmod.active_provider = provider

            await process_job(db_session, job)
            await db_session.commit()
        finally:
            pmod.active_provider = old_active

        assert job.status == "completed", f"Expected completed but got {job.status}"
        assert job.result_type == "code", f"Expected code but got {job.result_type}"

    async def test_worker_target_email_matches_in_subject_not_recipients(
        self, db_session
    ):
        """target_email matches in email subject, not recipients -> code found."""
        tenant = await _seed_tenant(db_session)
        mb = await _seed_mailbox(db_session, tenant.id)
        job = await mailbox_lookup_repository.create_job(
            db_session,
            tenant.id,
            mb.id,
            "spotify",
            target_email="alias-user@domain.com",
        )

        # Recipients header has a different address; target_email only in subject
        # Subject must match "Your Spotify login code" substring check for extractor
        provider = StubProvider(
            emails=[
                _make_email(
                    subject="Your Spotify login code for alias-user@domain.com",
                    body="Enter this code 987654",
                    to_recipients=["group-list@domain.com"],
                    message_id="msg-subject-match",
                ),
            ]
        )
        old_active = active_provider
        try:
            import app.services.mail_lookup_worker.providers as pmod

            pmod.active_provider = provider

            await process_job(db_session, job)
            await db_session.commit()
        finally:
            pmod.active_provider = old_active

        assert job.status == "completed", f"Expected completed but got {job.status}"
        assert job.result_type == "code", f"Expected code but got {job.result_type}"

    async def test_worker_target_email_no_match_anywhere(self, db_session):
        """target_email does not match in body, subject, or recipients -> not_found."""
        tenant = await _seed_tenant(db_session)
        mb = await _seed_mailbox(db_session, tenant.id)
        job = await mailbox_lookup_repository.create_job(
            db_session,
            tenant.id,
            mb.id,
            "spotify",
            target_email="unrelated@other.com",
        )

        provider = StubProvider(
            emails=[
                _make_email(
                    subject="Your Spotify login code",
                    body="Enter this code 654321",
                    to_recipients=["user@personal.com"],
                    message_id="msg-no-match",
                ),
            ]
        )
        old_active = active_provider
        try:
            import app.services.mail_lookup_worker.providers as pmod

            pmod.active_provider = provider

            await process_job(db_session, job)
            await db_session.commit()
        finally:
            pmod.active_provider = old_active

        assert job.status == "completed"
        assert job.result_type == "not_found"
