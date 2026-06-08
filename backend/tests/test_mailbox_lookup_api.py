"""Integration tests for n8n mailbox lookup endpoints (create + status poll)."""

import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.repositories import mailbox_lookup_repository
from app.services.mail_lookup_worker import process_job
from app.services.mail_lookup_worker.providers import EmailMessage, StubProvider
from app.services.whatsapp_session_service import ConversationSession

_N8N_API_KEY = settings.n8n_api_key


class _FakeRedis:
    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def set(
        self, key: str, value: str, ex: int | None = None, **kwargs: Any
    ) -> None:
        del ex, kwargs
        self._store[key] = value

    async def delete(self, key: str) -> int:
        return 1 if self._store.pop(key, None) is not None else 0


class _FakeManager:
    def __init__(self, redis: _FakeRedis) -> None:
        self._redis = redis

    async def execute(self, operation_name: str, async_callable: Any) -> Any:
        del operation_name
        return await async_callable(self._redis)


async def _seed_tenant(db_session, instance_name="test-mailbox-instance"):
    from app.core.security import get_password_hash
    from app.models import User, Tenant

    user = User(
        username=f"api_{uuid.uuid4().hex[:8]}",
        password_hash=get_password_hash("pass"),
        role="tenant",
    )
    db_session.add(user)
    await db_session.flush()
    tenant = Tenant(
        owner_user_id=user.id,
        client_prefix=f"ap{uuid.uuid4().hex[:2]}",
        name="API Test Tenant",
        is_active=True,
        evolution_instance_name=instance_name or f"inst-{uuid.uuid4().hex[:8]}",
    )
    db_session.add(tenant)
    await db_session.commit()
    return tenant, user


async def _seed_mailbox(db_session, tenant_id, **overrides):
    from app.models import TenantMailbox

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


# ─── Auth helpers ──────────────────────────────────────────────────────────


def _n8n_headers() -> dict:
    return {"X-API-Key": _N8N_API_KEY, "Content-Type": "application/json"}


class TestCreateLookupEndpoint:
    """POST /api/v1/integrations/n8n/mail/lookups"""

    pytestmark = pytest.mark.asyncio

    CREATE_URL = "/api/v1/integrations/n8n/mail/lookups"

    async def test_create_job_via_instance_name(self, client: AsyncClient, db_session):
        """Create job using tenant_instance (evolution instance name)."""
        tenant, _ = await _seed_tenant(db_session)
        await _seed_mailbox(db_session, tenant.id)

        payload = {
            "service_key": "spotify",
            "tenant_instance": "test-mailbox-instance",
            "target_email": "user@example.com",
        }
        response = await client.post(
            self.CREATE_URL, json=payload, headers=_n8n_headers()
        )
        assert response.status_code == 201, response.text
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "pending"

        # Verify job exists in DB
        job_id = uuid.UUID(data["job_id"])
        job = await mailbox_lookup_repository.get_job(
            db_session, job_id, tenant_id=tenant.id
        )
        assert job is not None
        assert job.service_key == "spotify"

    async def test_create_job_missing_tenant(self, client: AsyncClient):
        """Unknown tenant_instance -> 404."""
        payload = {
            "service_key": "netflix",
            "tenant_instance": "nonexistent-instance",
            "target_email": "user@example.com",
        }
        response = await client.post(
            self.CREATE_URL, json=payload, headers=_n8n_headers()
        )
        assert response.status_code == 404

    async def test_create_job_no_mailbox(self, client: AsyncClient, db_session):
        """Tenant without mailbox -> 400."""
        tenant, _ = await _seed_tenant(db_session)

        payload = {
            "service_key": "netflix",
            "tenant_instance": "test-mailbox-instance",
            "target_email": "user@example.com",
        }
        response = await client.post(
            self.CREATE_URL, json=payload, headers=_n8n_headers()
        )
        assert response.status_code == 400
        assert "no mailbox configured" in response.text.lower()

    async def test_create_job_inactive_tenant(self, client: AsyncClient, db_session):
        """Inactive tenant -> 400."""

        tenant, _ = await _seed_tenant(db_session)
        tenant.is_active = False
        await db_session.commit()

        payload = {
            "service_key": "netflix",
            "tenant_instance": "test-mailbox-instance",
            "target_email": "user@example.com",
        }
        response = await client.post(
            self.CREATE_URL, json=payload, headers=_n8n_headers()
        )
        assert response.status_code == 400

    async def test_create_job_wrong_mailbox_status(
        self, client: AsyncClient, db_session
    ):
        """Mailbox status is 'disconnected' -> 400."""
        tenant, _ = await _seed_tenant(db_session)
        await _seed_mailbox(db_session, tenant.id, status="disconnected")

        payload = {
            "service_key": "netflix",
            "tenant_instance": "test-mailbox-instance",
            "target_email": "user@example.com",
        }
        response = await client.post(
            self.CREATE_URL, json=payload, headers=_n8n_headers()
        )
        assert response.status_code == 400
        assert "disconnected" in response.text.lower()

    async def test_create_job_unauthorized(self, client: AsyncClient):
        """Missing API key -> 401."""
        payload = {
            "service_key": "netflix",
            "tenant_instance": "test-mailbox-instance",
            "target_email": "user@example.com",
        }
        response = await client.post(self.CREATE_URL, json=payload)
        assert response.status_code == 401

    async def test_create_job_missing_target_email(self, client: AsyncClient):
        """Missing target_email -> 422 (Pydantic validation error)."""
        payload = {
            "service_key": "netflix",
            "tenant_instance": "test-mailbox-instance",
        }
        response = await client.post(
            self.CREATE_URL, json=payload, headers=_n8n_headers()
        )
        # Pydantic enforces required target_email at schema level
        assert response.status_code == 422
        assert "target_email" in response.text.lower()


class TestGetLookupStatusEndpoint:
    """GET /api/v1/integrations/n8n/mail/lookups/{job_id}"""

    pytestmark = pytest.mark.asyncio

    BASE_URL = "/api/v1/integrations/n8n/mail/lookups"

    async def test_get_pending_status(self, client: AsyncClient, db_session):
        """Pending job returns status=pending."""
        tenant, _ = await _seed_tenant(db_session)
        mb = await _seed_mailbox(db_session, tenant.id)
        job = await mailbox_lookup_repository.create_job(
            db_session, tenant.id, mb.id, "spotify"
        )
        await db_session.commit()

        response = await client.get(
            f"{self.BASE_URL}/{job.id}",
            headers=_n8n_headers(),
            params={"tenant_id": str(tenant.id)},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "pending"

    async def test_get_completed_status_with_value(
        self, client: AsyncClient, db_session
    ):
        """Completed job with result returns result_value ephemerally."""
        tenant, _ = await _seed_tenant(db_session)
        mb = await _seed_mailbox(db_session, tenant.id)
        job = await mailbox_lookup_repository.create_job(
            db_session, tenant.id, mb.id, "spotify"
        )
        await db_session.flush()

        # Process job directly with mock provider
        provider = StubProvider(
            emails=[
                EmailMessage(
                    subject="Your Spotify login code",
                    body="Enter this code 654321",
                    received_at=datetime.now(timezone.utc),
                    message_id="msg-001",
                    sender="noreply@spotify.com",
                )
            ]
        )

        # Need to import and set active_provider
        import app.services.mail_lookup_worker.providers as pmod

        old_active = pmod.active_provider

        try:
            real_email = EmailMessage(
                subject="Your Spotify login code",
                body="Enter this code 654321",
                received_at=datetime.now(timezone.utc),
                message_id="msg-001",
                sender="noreply@spotify.com",
            )
            pmod.active_provider = StubProvider(emails=[real_email])

            await process_job(db_session, job)
            await db_session.commit()
        finally:
            pmod.active_provider = old_active

        # Poll endpoint
        response = await client.get(
            f"{self.BASE_URL}/{job.id}",
            headers=_n8n_headers(),
            params={"tenant_id": str(tenant.id)},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["result_type"] == "code"
        assert data["result_value"] == "654321"

    async def test_get_not_found(self, client: AsyncClient, db_session):
        """Job completes with not_found -> no result_value but status completed."""
        tenant, _ = await _seed_tenant(db_session)
        mb = await _seed_mailbox(db_session, tenant.id)
        job = await mailbox_lookup_repository.create_job(
            db_session, tenant.id, mb.id, "spotify"
        )
        await db_session.flush()

        provider = StubProvider(emails=[])
        import app.services.mail_lookup_worker.providers as pmod

        old_active = pmod.active_provider
        try:
            pmod.active_provider = provider
            await process_job(db_session, job)
            await db_session.commit()
        finally:
            pmod.active_provider = old_active

        response = await client.get(
            f"{self.BASE_URL}/{job.id}",
            headers=_n8n_headers(),
            params={"tenant_id": str(tenant.id)},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["result_type"] == "not_found"
        assert data["result_value"] is None

    async def test_get_job_not_found(self, client: AsyncClient):
        """Non-existent job_id -> 404."""
        fake_id = uuid.uuid4()
        fake_tenant_id = uuid.uuid4()
        response = await client.get(
            f"{self.BASE_URL}/{fake_id}",
            headers=_n8n_headers(),
            params={"tenant_id": str(fake_tenant_id)},
        )
        assert response.status_code == 404

    async def test_get_unauthorized(self, client: AsyncClient, db_session):
        """Missing API key -> 401."""
        tenant, _ = await _seed_tenant(db_session)
        mb = await _seed_mailbox(db_session, tenant.id)
        job = await mailbox_lookup_repository.create_job(
            db_session, tenant.id, mb.id, "netflix"
        )
        await db_session.commit()

        response = await client.get(
            f"{self.BASE_URL}/{job.id}",
            params={"tenant_id": str(tenant.id)},
        )
        assert response.status_code == 401

    async def test_get_duplicate_suppressed(self, client: AsyncClient, db_session):
        """Duplicate code -> result_type=duplicate_suppressed, no result_value."""
        tenant, _ = await _seed_tenant(db_session)
        mb = await _seed_mailbox(db_session, tenant.id)
        job = await mailbox_lookup_repository.create_job(
            db_session, tenant.id, mb.id, "spotify"
        )
        await db_session.flush()

        # Pre-record delivery
        from app.repositories import mailbox_dedupe_repository
        from app.services.mail_lookup_worker.fingerprint import compute_fingerprint

        fp = compute_fingerprint(
            service_key="spotify",
            message_id="msg-001",
            sender="noreply@spotify.com",
            received_at_iso=datetime.now(timezone.utc).isoformat(),
            subject="Your Spotify login code",
            payload_normalized="654321",
        )
        await mailbox_dedupe_repository.record_delivery(
            db_session,
            tenant.id,
            mb.id,
            "spotify",
            "msg-001",
            fp,
        )
        await db_session.flush()

        # Process job
        import app.services.mail_lookup_worker.providers as pmod

        old_active = pmod.active_provider
        try:
            pmod.active_provider = StubProvider(
                emails=[
                    EmailMessage(
                        subject="Your Spotify login code",
                        body="Enter this code 654321",
                        received_at=datetime.now(timezone.utc),
                        message_id="msg-001",
                        sender="noreply@spotify.com",
                    ),
                ]
            )
            await process_job(db_session, job)
            await db_session.commit()
        finally:
            pmod.active_provider = old_active

        response = await client.get(
            f"{self.BASE_URL}/{job.id}",
            headers=_n8n_headers(),
            params={"tenant_id": str(tenant.id)},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["result_type"] == "duplicate_suppressed"
        assert data["result_value"] is None

    async def test_cross_tenant_isolation(self, client: AsyncClient, db_session):
        """Tenant A cannot poll tenant B's job."""
        tenant_a, _ = await _seed_tenant(db_session)
        tenant_b, _ = await _seed_tenant(
            db_session, instance_name="test-mailbox-instance-b"
        )
        mb_a = await _seed_mailbox(db_session, tenant_a.id)
        job_a = await mailbox_lookup_repository.create_job(
            db_session, tenant_a.id, mb_a.id, "spotify"
        )
        await db_session.commit()

        # Poll with tenant_b's id -> 404 (job not found for tenant_b)
        response = await client.get(
            f"{self.BASE_URL}/{job_a.id}",
            headers=_n8n_headers(),
            params={"tenant_id": str(tenant_b.id)},
        )
        assert response.status_code == 404

        # Poll with tenant_a's id -> 200 (correct owner)
        response = await client.get(
            f"{self.BASE_URL}/{job_a.id}",
            headers=_n8n_headers(),
            params={"tenant_id": str(tenant_a.id)},
        )
        assert response.status_code == 200

    async def test_get_missing_tenant_id(self, client: AsyncClient):
        """Missing tenant_id -> 422 validation error."""
        fake_id = uuid.uuid4()
        response = await client.get(
            f"{self.BASE_URL}/{fake_id}",
            headers=_n8n_headers(),
        )
        assert response.status_code == 422


class TestCreateThenPoll:
    """End-to-end: create job, verify pending, process, verify completed."""

    pytestmark = pytest.mark.asyncio

    CREATE_URL = "/api/v1/integrations/n8n/mail/lookups"

    async def test_create_and_poll_flow(self, client: AsyncClient, db_session):
        """Full create -> process -> poll flow."""
        tenant, _ = await _seed_tenant(db_session)
        await _seed_mailbox(db_session, tenant.id)

        # Create job via API
        payload = {
            "service_key": "spotify",
            "tenant_instance": "test-mailbox-instance",
            "target_email": "user@example.com",
        }
        create_resp = await client.post(
            self.CREATE_URL, json=payload, headers=_n8n_headers()
        )
        assert create_resp.status_code == 201
        job_id = create_resp.json()["job_id"]

        # Verify pending
        poll_resp = await client.get(
            f"{self.CREATE_URL}/{job_id}",
            headers=_n8n_headers(),
            params={"tenant_id": str(tenant.id)},
        )
        assert poll_resp.status_code == 200
        assert poll_resp.json()["status"] == "pending"

        # Process directly (simulating worker)
        from app.models import MailLookupJob
        from sqlalchemy import select

        result = await db_session.execute(
            select(MailLookupJob).where(MailLookupJob.id == uuid.UUID(job_id))
        )
        job = result.scalar_one_or_none()
        assert job is not None

        import app.services.mail_lookup_worker.providers as pmod

        old_active = pmod.active_provider
        try:
            pmod.active_provider = StubProvider(
                emails=[
                    EmailMessage(
                        subject="Your Spotify login code",
                        body="Enter this code 654321",
                        received_at=datetime.now(timezone.utc),
                        message_id="msg-002",
                        sender="noreply@spotify.com",
                        to_recipients=["user@example.com"],
                    ),
                ]
            )
            await process_job(db_session, job)
            await db_session.commit()
        finally:
            pmod.active_provider = old_active

        # Poll completed result
        poll_resp2 = await client.get(
            f"{self.CREATE_URL}/{job_id}",
            headers=_n8n_headers(),
            params={"tenant_id": str(tenant.id)},
        )
        assert poll_resp2.status_code == 200
        data = poll_resp2.json()
        assert data["status"] == "completed"
        assert data["result_type"] == "code"
        assert data["result_value"] == "654321"

    async def test_codigo_console_response_job_can_be_polled(
        self, client: AsyncClient, db_session
    ):
        """Codigo final step returns durable job; correct tenant polls it."""
        from app.api.v1.endpoints.integrations.console_handlers import (
            _handle_tenant_console,
        )

        tenant, _ = await _seed_tenant(db_session)
        tenant.whatsapp_phone = "+12015550002"
        await db_session.commit()
        await _seed_mailbox(db_session, tenant.id)

        fake_redis = _FakeRedis()
        manager = _FakeManager(fake_redis)
        session = ConversationSession(
            phone="admin:+12015550002",
            flow="codigo",
            step="email",
            temp_data={"service_key": "netflix"},
        )
        await fake_redis.set(
            "session:admin:+12015550002",
            session.model_dump_json(),
        )

        with (
            patch(
                "app.api.v1.endpoints.integrations.console_handlers.get_redis_manager",
                return_value=object(),
            ),
            patch(
                "app.api.v1.endpoints.integrations.console_handlers.enqueue_job",
                AsyncMock(return_value=True),
            ),
        ):
            response = await _handle_tenant_console(
                phone="+12015550002",
                message="user@example.com",
                instance="test-mailbox-instance",
                manager=manager,
                db=db_session,
            )

        assert response.lookup_job_id is not None
        assert response.tenant_id == str(tenant.id)
        job_id = uuid.UUID(response.lookup_job_id)
        job = await mailbox_lookup_repository.get_job(
            db_session, job_id, tenant_id=tenant.id
        )
        assert job is not None
        assert job.target_email == "user@example.com"

        poll_ok = await client.get(
            f"{self.CREATE_URL}/{job_id}",
            headers=_n8n_headers(),
            params={"tenant_id": str(tenant.id)},
        )
        assert poll_ok.status_code == 200
        assert poll_ok.json()["status"] == "pending"

        poll_wrong_tenant = await client.get(
            f"{self.CREATE_URL}/{job_id}",
            headers=_n8n_headers(),
            params={"tenant_id": str(uuid.uuid4())},
        )
        assert poll_wrong_tenant.status_code == 404
