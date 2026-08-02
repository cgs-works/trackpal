"""Integration tests for n8n mailbox lookup endpoints (create + status poll)."""

import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.repositories import mailbox_lookup_repository
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
    from app.models import Tenant, User

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
        "status": "connected",
    }
    kwargs.update(overrides)
    mb = TenantMailbox(**kwargs)
    db_session.add(mb)
    await db_session.commit()
    await db_session.refresh(mb)
    return mb


def _n8n_headers() -> dict:
    return {"X-API-Key": _N8N_API_KEY, "Content-Type": "application/json"}


class TestCreateLookupEndpoint:
    """POST /api/v1/integrations/n8n/mail/lookups"""

    pytestmark = pytest.mark.asyncio
    CREATE_URL = "/api/v1/integrations/n8n/mail/lookups"

    async def test_create_job_via_instance_name(self, client: AsyncClient, db_session):
        tenant, _ = await _seed_tenant(db_session)
        await _seed_mailbox(db_session, tenant.id)
        response = await client.post(
            self.CREATE_URL,
            json={
                "service_key": "spotify",
                "tenant_instance": "test-mailbox-instance",
                "target_email": "user@example.com",
            },
            headers=_n8n_headers(),
        )
        assert response.status_code == 201, response.text
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "pending"
        job = await mailbox_lookup_repository.get_job(
            db_session, uuid.UUID(data["job_id"]), tenant_id=tenant.id
        )
        assert job is not None
        assert job.service_key == "spotify"

    async def test_create_job_missing_tenant(self, client: AsyncClient):
        response = await client.post(
            self.CREATE_URL,
            json={
                "service_key": "netflix",
                "tenant_instance": "nonexistent-instance",
                "target_email": "user@example.com",
            },
            headers=_n8n_headers(),
        )
        assert response.status_code == 404

    async def test_create_job_no_mailbox(self, client: AsyncClient, db_session):
        await _seed_tenant(db_session)
        response = await client.post(
            self.CREATE_URL,
            json={
                "service_key": "netflix",
                "tenant_instance": "test-mailbox-instance",
                "target_email": "user@example.com",
            },
            headers=_n8n_headers(),
        )
        assert response.status_code == 400
        assert "no mailbox configured" in response.text.lower()

    async def test_create_job_inactive_tenant(self, client: AsyncClient, db_session):
        tenant, _ = await _seed_tenant(db_session)
        tenant.is_active = False
        await db_session.commit()
        response = await client.post(
            self.CREATE_URL,
            json={
                "service_key": "netflix",
                "tenant_instance": "test-mailbox-instance",
                "target_email": "user@example.com",
            },
            headers=_n8n_headers(),
        )
        assert response.status_code == 400

    async def test_create_job_wrong_mailbox_status(
        self, client: AsyncClient, db_session
    ):
        tenant, _ = await _seed_tenant(db_session)
        await _seed_mailbox(db_session, tenant.id, status="disconnected")
        response = await client.post(
            self.CREATE_URL,
            json={
                "service_key": "netflix",
                "tenant_instance": "test-mailbox-instance",
                "target_email": "user@example.com",
            },
            headers=_n8n_headers(),
        )
        assert response.status_code == 400
        assert "disconnected" in response.text.lower()

    async def test_create_job_unauthorized(self, client: AsyncClient):
        response = await client.post(
            self.CREATE_URL,
            json={
                "service_key": "netflix",
                "tenant_instance": "test-mailbox-instance",
                "target_email": "user@example.com",
            },
        )
        assert response.status_code == 401

    async def test_create_job_missing_target_email(self, client: AsyncClient):
        response = await client.post(
            self.CREATE_URL,
            json={
                "service_key": "netflix",
                "tenant_instance": "test-mailbox-instance",
            },
            headers=_n8n_headers(),
        )
        assert response.status_code == 422
        assert "target_email" in response.text.lower()


class TestLookupCoordinatorContract:
    """Endpoint callers use durable coordination rather than the legacy queue."""

    pytestmark = pytest.mark.asyncio

    async def test_create_returns_committed_job_when_schedule_unavailable(
        self, client: AsyncClient, db_session
    ) -> None:
        tenant, _ = await _seed_tenant(db_session)
        await _seed_mailbox(db_session, tenant.id)
        coordinator = AsyncMock()
        coordinator.schedule.side_effect = RuntimeError("Redis unavailable")
        with patch(
            "app.api.v1.endpoints.integrations.mail_lookups.get_lookup_execution_coordinator",
            return_value=coordinator,
        ):
            response = await client.post(
                "/api/v1/integrations/n8n/mail/lookups",
                json={
                    "service_key": "spotify",
                    "tenant_instance": "test-mailbox-instance",
                    "target_email": "user@example.com",
                },
                headers=_n8n_headers(),
            )
        assert response.status_code == 201
        job = await mailbox_lookup_repository.get_job(
            db_session, uuid.UUID(response.json()["job_id"]), tenant_id=tenant.id
        )
        assert job is not None
        coordinator.schedule.assert_awaited_once_with(job.id)

    async def test_pending_poll_reschedules_job(
        self, client: AsyncClient, db_session
    ) -> None:
        tenant, _ = await _seed_tenant(db_session)
        mailbox = await _seed_mailbox(db_session, tenant.id)
        job = await mailbox_lookup_repository.create_job(
            db_session, tenant.id, mailbox.id, "spotify"
        )
        await db_session.commit()
        coordinator = AsyncMock()
        with patch(
            "app.api.v1.endpoints.integrations.mail_lookups.get_lookup_execution_coordinator",
            return_value=coordinator,
        ):
            response = await client.get(
                f"/api/v1/integrations/n8n/mail/lookups/{job.id}",
                headers=_n8n_headers(),
                params={"tenant_id": str(tenant.id)},
            )
        assert response.status_code == 200
        coordinator.schedule.assert_awaited_once_with(job.id)

    async def test_expired_pending_poll_does_not_reschedule(
        self, client: AsyncClient, db_session
    ) -> None:
        tenant, _ = await _seed_tenant(db_session)
        mailbox = await _seed_mailbox(db_session, tenant.id)
        job = await mailbox_lookup_repository.create_job(
            db_session, tenant.id, mailbox.id, "spotify"
        )
        job.expires_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await db_session.commit()
        coordinator = AsyncMock()
        with patch(
            "app.api.v1.endpoints.integrations.mail_lookups.get_lookup_execution_coordinator",
            return_value=coordinator,
        ):
            response = await client.get(
                f"/api/v1/integrations/n8n/mail/lookups/{job.id}",
                headers=_n8n_headers(),
                params={"tenant_id": str(tenant.id)},
            )
        assert response.status_code == 200
        coordinator.schedule.assert_not_awaited()

    async def test_completed_poll_reads_result_from_coordinator(
        self, client: AsyncClient, db_session
    ) -> None:
        tenant, _ = await _seed_tenant(db_session)
        mailbox = await _seed_mailbox(db_session, tenant.id)
        job = await mailbox_lookup_repository.create_job(
            db_session, tenant.id, mailbox.id, "spotify"
        )
        job.status = "completed"
        job.result_type = "code"
        await db_session.commit()
        coordinator = AsyncMock()
        coordinator.get_result.return_value = ("code", "987654")
        with patch(
            "app.api.v1.endpoints.integrations.mail_lookups.get_lookup_execution_coordinator",
            return_value=coordinator,
        ):
            response = await client.get(
                f"/api/v1/integrations/n8n/mail/lookups/{job.id}",
                headers=_n8n_headers(),
                params={"tenant_id": str(tenant.id)},
            )
        assert response.status_code == 200
        assert response.json()["result_value"] == "987654"
        coordinator.get_result.assert_awaited_once_with(job.id)


class TestGetLookupStatusEndpoint:
    """GET /api/v1/integrations/n8n/mail/lookups/{job_id}"""

    pytestmark = pytest.mark.asyncio
    BASE_URL = "/api/v1/integrations/n8n/mail/lookups"

    async def test_get_pending_status(self, client: AsyncClient, db_session):
        tenant, _ = await _seed_tenant(db_session)
        mailbox = await _seed_mailbox(db_session, tenant.id)
        job = await mailbox_lookup_repository.create_job(
            db_session, tenant.id, mailbox.id, "spotify"
        )
        await db_session.commit()
        response = await client.get(
            f"{self.BASE_URL}/{job.id}",
            headers=_n8n_headers(),
            params={"tenant_id": str(tenant.id)},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "pending"

    async def test_get_completed_status_with_value(
        self, client: AsyncClient, db_session
    ):
        tenant, _ = await _seed_tenant(db_session)
        mailbox = await _seed_mailbox(db_session, tenant.id)
        job = await mailbox_lookup_repository.create_job(
            db_session, tenant.id, mailbox.id, "spotify"
        )
        job.status = "completed"
        job.result_type = "code"
        await db_session.commit()
        coordinator = AsyncMock()
        coordinator.get_result.return_value = ("code", "654321")
        with patch(
            "app.api.v1.endpoints.integrations.mail_lookups.get_lookup_execution_coordinator",
            return_value=coordinator,
        ):
            response = await client.get(
                f"{self.BASE_URL}/{job.id}",
                headers=_n8n_headers(),
                params={"tenant_id": str(tenant.id)},
            )
        assert response.status_code == 200
        assert response.json()["result_value"] == "654321"

    async def test_get_not_found(self, client: AsyncClient, db_session):
        tenant, _ = await _seed_tenant(db_session)
        mailbox = await _seed_mailbox(db_session, tenant.id)
        job = await mailbox_lookup_repository.create_job(
            db_session, tenant.id, mailbox.id, "spotify"
        )
        job.status = "completed"
        job.result_type = "not_found"
        await db_session.commit()
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
        response = await client.get(
            f"{self.BASE_URL}/{uuid.uuid4()}",
            headers=_n8n_headers(),
            params={"tenant_id": str(uuid.uuid4())},
        )
        assert response.status_code == 404

    async def test_get_unauthorized(self, client: AsyncClient, db_session):
        tenant, _ = await _seed_tenant(db_session)
        mailbox = await _seed_mailbox(db_session, tenant.id)
        job = await mailbox_lookup_repository.create_job(
            db_session, tenant.id, mailbox.id, "netflix"
        )
        await db_session.commit()
        response = await client.get(
            f"{self.BASE_URL}/{job.id}",
            params={"tenant_id": str(tenant.id)},
        )
        assert response.status_code == 401

    async def test_get_duplicate_suppressed(self, client: AsyncClient, db_session):
        tenant, _ = await _seed_tenant(db_session)
        mailbox = await _seed_mailbox(db_session, tenant.id)
        job = await mailbox_lookup_repository.create_job(
            db_session, tenant.id, mailbox.id, "spotify"
        )
        job.status = "completed"
        job.result_type = "duplicate_suppressed"
        await db_session.commit()
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
        tenant_a, _ = await _seed_tenant(db_session)
        tenant_b, _ = await _seed_tenant(
            db_session, instance_name="test-mailbox-instance-b"
        )
        mailbox = await _seed_mailbox(db_session, tenant_a.id)
        job = await mailbox_lookup_repository.create_job(
            db_session, tenant_a.id, mailbox.id, "spotify"
        )
        await db_session.commit()
        response = await client.get(
            f"{self.BASE_URL}/{job.id}",
            headers=_n8n_headers(),
            params={"tenant_id": str(tenant_b.id)},
        )
        assert response.status_code == 404
        response = await client.get(
            f"{self.BASE_URL}/{job.id}",
            headers=_n8n_headers(),
            params={"tenant_id": str(tenant_a.id)},
        )
        assert response.status_code == 200

    async def test_get_missing_tenant_id(self, client: AsyncClient):
        response = await client.get(
            f"{self.BASE_URL}/{uuid.uuid4()}", headers=_n8n_headers()
        )
        assert response.status_code == 422


class TestConsoleLookupCreation:
    """The WhatsApp console creates a durable job for later external execution."""

    pytestmark = pytest.mark.asyncio
    CREATE_URL = "/api/v1/integrations/n8n/mail/lookups"

    async def test_codigo_console_response_job_can_be_polled(
        self, client: AsyncClient, db_session
    ):
        from app.api.v1.endpoints.integrations.console_handlers import (
            _handle_tenant_console,
        )

        tenant, _ = await _seed_tenant(db_session)
        tenant.whatsapp_phone = "+12015550002"
        await db_session.commit()
        await _seed_mailbox(db_session, tenant.id)
        manager = _FakeManager(_FakeRedis())
        session = ConversationSession(
            phone="admin:+12015550002",
            flow="codigo",
            step="email_confirm",
            temp_data={
                "service_key": "netflix",
                "service_label": "Netflix",
                "target_email": "user@example.com",
            },
        )
        await manager._redis.set(
            "session:admin:+12015550002", session.model_dump_json()
        )
        with patch(
            "app.api.v1.endpoints.integrations.console_handlers.get_lookup_execution_coordinator",
            return_value=AsyncMock(),
        ):
            response = await _handle_tenant_console(
                phone="+12015550002",
                message="1",
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
