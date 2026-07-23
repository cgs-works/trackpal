"""Tests for the Tenant Data Export API endpoints.

Uses the real ASGI application with fake Redis and fake storage adapter.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta

import pytest
from sqlalchemy import select

from app.models import Tenant
from app.repositories import export_jobs_repository
from app.services.export_storage import FakeExportStorageAdapter

pytestmark = pytest.mark.asyncio


# ── Helpers ────────────────────────────────────────────────────


async def _tenant_headers(client):
    """Login as the default tenant user and return auth headers."""
    login = await client.post(
        "/api/v1/auth/login",
        json={"username": "tenant", "password": "tenant-password"},
    )
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def _master_headers(client):
    """Login as master and return auth headers."""
    login = await client.post(
        "/api/v1/auth/login",
        json={"username": "master", "password": "master-password"},
    )
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


# ── Fixtures ───────────────────────────────────────────────────


@pytest.fixture
def fake_export_storage():
    """Provide a FakeExportStorageAdapter and wire it into the app."""
    storage = FakeExportStorageAdapter()
    from app.services import export_service

    original = getattr(export_service, "_export_storage", None)
    export_service._export_storage = storage
    yield storage
    export_service._export_storage = original


@pytest.fixture
def fake_step_up_limiter():
    """Wire a no-op step-up limiter that always allows."""
    from app.services import export_service

    class _AlwaysAllow:
        async def check(self, actor_id: str) -> None:
            pass
        async def record_failure(self, actor_id: str) -> None:
            pass
        async def record_success(self, actor_id: str) -> None:
            pass

    original = getattr(export_service, "_step_up_limiter", None)
    export_service._step_up_limiter = _AlwaysAllow()
    yield
    export_service._step_up_limiter = original


# ── POST /me/export ────────────────────────────────────────────


async def test_request_export_creates_pending_job(client, db_session, active_tenant_user, fake_export_storage, fake_step_up_limiter):
    """A Tenant Admin can request an export and gets a pending job back."""
    headers = await _tenant_headers(client)
    resp = await client.post("/api/v1/me/export", headers=headers)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "pending"
    assert "id" in body
    assert body["tenant_id"] is not None

    # Verify in DB
    job = await export_jobs_repository.get_by_id(db_session, uuid.UUID(body["id"]))
    assert job is not None
    assert job.status == "pending"


async def test_request_export_requires_authentication(client):
    """Unauthenticated requests receive 401."""
    resp = await client.post("/api/v1/me/export")
    assert resp.status_code == 401


async def test_request_export_rejects_client_user(client, active_client_user):
    """Client users cannot request an export."""
    login = await client.post(
        "/api/v1/auth/login",
        json={"username": f"{active_client_user.username}", "password": "client-password"},
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    resp = await client.post("/api/v1/me/export", headers=headers)
    assert resp.status_code == 403


# ── GET /me/export ─────────────────────────────────────────────


async def test_get_export_status_returns_latest(client, db_session, active_tenant_user, fake_export_storage, fake_step_up_limiter):
    """GET /me/export returns the latest job for the current tenant."""
    headers = await _tenant_headers(client)

    # Create a job first
    create = await client.post("/api/v1/me/export", headers=headers)
    assert create.status_code == 201
    job_id = create.json()["id"]

    resp = await client.get("/api/v1/me/export", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == job_id
    assert body["status"] in ("pending", "processing", "ready", "failed")


async def test_get_export_status_when_no_job(client, db_session, active_tenant_user):
    """GET /me/export returns 204 No Content when no job exists."""
    headers = await _tenant_headers(client)
    resp = await client.get("/api/v1/me/export", headers=headers)
    assert resp.status_code == 204


# ── GET /me/export/download ────────────────────────────────────


async def test_download_returns_presigned_url_when_ready(client, db_session, active_tenant_user, fake_export_storage, fake_step_up_limiter):
    """GET /me/export/download returns a download URL when a ready job exists."""
    headers = await _tenant_headers(client)

    # Create and ready a job
    create = await client.post("/api/v1/me/export", headers=headers)
    assert create.status_code == 201
    job_id = uuid.UUID(create.json()["id"])

    # Manually set job to ready
    tenant_result = await db_session.execute(
        select(Tenant).where(Tenant.owner_user_id == active_tenant_user.id)
    )
    tenant = tenant_result.scalar_one()
    now = datetime.now(timezone.utc)
    await export_jobs_repository.update_status(
        db_session, job_id, "ready",
        r2_key="test-key-123",
        artifact_size_bytes=1024,
        expires_at=now + timedelta(hours=72),
        clear_lease=True,
    )

    # Upload to fake storage
    await fake_export_storage.upload("test-key-123", b"fake-zip-content")

    resp = await client.get("/api/v1/me/export/download", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "download_url" in body
    assert "expires_in" in body
    assert "test-key-123" in body["download_url"]


async def test_download_returns_404_when_no_ready_job(client, db_session, active_tenant_user, fake_export_storage, fake_step_up_limiter):
    """GET /me/export/download returns 404 when no ready job exists."""
    headers = await _tenant_headers(client)
    resp = await client.get("/api/v1/me/export/download", headers=headers)
    assert resp.status_code == 404
