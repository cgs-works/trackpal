"""Tests for the Master-scoped Tenant Data Export API endpoints.

Covers active/inactive targets, unknown Tenant, wrong role, shared
Tenant/Admin visibility, and target-specific signed downloads.
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


async def _master_headers(client):
    """Login as master and return auth headers."""
    login = await client.post(
        "/api/v1/auth/login",
        json={"username": "master", "password": "master-password"},
    )
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def _tenant_headers(client):
    """Login as the default tenant user and return auth headers."""
    login = await client.post(
        "/api/v1/auth/login",
        json={"username": "tenant", "password": "tenant-password"},
    )
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def _tenant_id_for_user(db_session, user_id) -> uuid.UUID | None:
    result = await db_session.execute(
        select(Tenant).where(Tenant.owner_user_id == user_id)
    )
    tenant = result.scalar_one_or_none()
    return tenant.id if tenant else None


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
    """Wire a step-up limiter that accepts the correct master password."""
    from app.services import export_service

    class _MasterPasswordStepUp:
        """Allows export when the correct master password is provided."""

        def __init__(self):
            self._fail_count: dict[str, int] = {}

        async def check(self, actor_id: str) -> None:
            # Allow check if under 3 attempts
            count = self._fail_count.get(actor_id, 0)
            if count >= 3:
                from app.services.step_up_limiter import StepUpError

                raise StepUpError("Too many failed attempts")

        async def record_failure(self, actor_id: str) -> None:
            self._fail_count[actor_id] = self._fail_count.get(actor_id, 0) + 1

        async def record_success(self, actor_id: str) -> None:
            self._fail_count.pop(actor_id, None)

    original = getattr(export_service, "_step_up_limiter", None)
    limiter = _MasterPasswordStepUp()
    export_service._step_up_limiter = limiter
    yield limiter
    export_service._step_up_limiter = original


# ── POST /tenants/{tenant_id}/export ───────────────────────────


async def test_master_request_export_active_tenant(
    client,
    db_session,
    master_user,
    active_tenant_user,
    fake_export_storage,
    fake_step_up_limiter,
):
    """Master can request an export for an active tenant with correct password."""
    tenant_id = await _tenant_id_for_user(db_session, active_tenant_user.id)
    assert tenant_id is not None

    headers = await _master_headers(client)
    resp = await client.post(
        f"/api/v1/tenants/{tenant_id}/export",
        json={"password": "master-password"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "pending"
    assert body["tenant_id"] == str(tenant_id)
    # Actor attribution
    assert body.get("actor_role") == "master"

    # Verify in DB
    job = await export_jobs_repository.get_by_id(db_session, uuid.UUID(body["id"]))
    assert job is not None
    assert job.status == "pending"
    assert job.actor_role == "master"


async def test_master_request_export_inactive_tenant(
    client,
    db_session,
    master_user,
    deactivated_tenant_user,
    fake_export_storage,
    fake_step_up_limiter,
):
    """Master can request an export for an inactive tenant without reactivation."""
    tenant_id = await _tenant_id_for_user(db_session, deactivated_tenant_user.id)
    assert tenant_id is not None

    headers = await _master_headers(client)
    resp = await client.post(
        f"/api/v1/tenants/{tenant_id}/export",
        json={"password": "master-password"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "pending"
    assert body["actor_role"] == "master"


async def test_master_request_export_wrong_password(
    client,
    db_session,
    master_user,
    active_tenant_user,
    fake_export_storage,
    fake_step_up_limiter,
):
    """Master receives 401 when providing wrong password."""
    tenant_id = await _tenant_id_for_user(db_session, active_tenant_user.id)
    assert tenant_id is not None

    headers = await _master_headers(client)
    resp = await client.post(
        f"/api/v1/tenants/{tenant_id}/export",
        json={"password": "wrong-password"},
        headers=headers,
    )
    assert resp.status_code == 401, resp.text


async def test_master_request_export_unknown_tenant(
    client, db_session, master_user, fake_export_storage, fake_step_up_limiter
):
    """Master receives 404 when targeting a non-existent tenant."""
    unknown_id = uuid.uuid4()
    headers = await _master_headers(client)
    resp = await client.post(
        f"/api/v1/tenants/{unknown_id}/export",
        json={"password": "master-password"},
        headers=headers,
    )
    assert resp.status_code == 404, resp.text


async def test_master_request_export_requires_master_role(
    client,
    db_session,
    master_user,
    active_tenant_user,
    fake_export_storage,
    fake_step_up_limiter,
):
    """Non-Master users receive 403 when accessing Master export endpoints."""
    tenant_id = await _tenant_id_for_user(db_session, active_tenant_user.id)
    assert tenant_id is not None

    headers = await _tenant_headers(client)
    resp = await client.post(
        f"/api/v1/tenants/{tenant_id}/export",
        json={"password": "irrelevant"},
        headers=headers,
    )
    assert resp.status_code == 403, resp.text


async def test_master_request_export_requires_authentication(
    client, db_session, active_tenant_user
):
    """Unauthenticated requests receive 401."""
    tenant_id = await _tenant_id_for_user(db_session, active_tenant_user.id)
    assert tenant_id is not None

    resp = await client.post(
        f"/api/v1/tenants/{tenant_id}/export",
        json={"password": "irrelevant"},
    )
    assert resp.status_code == 401


# ── GET /tenants/{tenant_id}/export ────────────────────────────


async def test_master_get_export_status(
    client,
    db_session,
    master_user,
    active_tenant_user,
    fake_export_storage,
    fake_step_up_limiter,
):
    """Master can get export status for a tenant."""
    tenant_id = await _tenant_id_for_user(db_session, active_tenant_user.id)
    assert tenant_id is not None

    headers = await _master_headers(client)

    # Create an export first
    create = await client.post(
        f"/api/v1/tenants/{tenant_id}/export",
        json={"password": "master-password"},
        headers=headers,
    )
    assert create.status_code == 201
    job_id = create.json()["id"]

    # Get status
    resp = await client.get(
        f"/api/v1/tenants/{tenant_id}/export",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == job_id
    assert body["status"] == "pending"


async def test_master_get_export_status_when_no_job(
    client, db_session, master_user, active_tenant_user, fake_export_storage
):
    """Master receives 204 when no export job exists for the tenant."""
    tenant_id = await _tenant_id_for_user(db_session, active_tenant_user.id)
    assert tenant_id is not None

    headers = await _master_headers(client)
    resp = await client.get(
        f"/api/v1/tenants/{tenant_id}/export",
        headers=headers,
    )
    assert resp.status_code == 204, resp.text


# ── POST /tenants/{tenant_id}/export/cancel ────────────────────


async def test_master_cancel_export(
    client,
    db_session,
    master_user,
    active_tenant_user,
    fake_export_storage,
    fake_step_up_limiter,
):
    """Master can cancel a pending export for a tenant."""
    tenant_id = await _tenant_id_for_user(db_session, active_tenant_user.id)
    assert tenant_id is not None

    headers = await _master_headers(client)

    # Create an export
    create = await client.post(
        f"/api/v1/tenants/{tenant_id}/export",
        json={"password": "master-password"},
        headers=headers,
    )
    assert create.status_code == 201

    # Cancel it
    resp = await client.post(
        f"/api/v1/tenants/{tenant_id}/export/cancel",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "cancelled"


# ── GET /tenants/{tenant_id}/export/download ───────────────────


async def test_master_download_export(
    client,
    db_session,
    master_user,
    active_tenant_user,
    fake_export_storage,
    fake_step_up_limiter,
):
    """Master can download a ready export for a tenant."""
    tenant_id = await _tenant_id_for_user(db_session, active_tenant_user.id)
    assert tenant_id is not None

    headers = await _master_headers(client)

    # Create and ready a job
    create = await client.post(
        f"/api/v1/tenants/{tenant_id}/export",
        json={"password": "master-password"},
        headers=headers,
    )
    assert create.status_code == 201
    job_id = uuid.UUID(create.json()["id"])

    # Manually set job to ready
    now = datetime.now(timezone.utc)
    await export_jobs_repository.update_status(
        db_session,
        job_id,
        "ready",
        r2_key="master-test-key",
        artifact_size_bytes=2048,
        expires_at=now + timedelta(hours=72),
        clear_lease=True,
    )

    # Upload to fake storage
    await fake_export_storage.upload("master-test-key", b"fake-export-data")

    resp = await client.get(
        f"/api/v1/tenants/{tenant_id}/export/download",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "download_url" in body
    assert "expires_in" in body
    assert "master-test-key" in body["download_url"]


async def test_master_download_export_when_no_ready(
    client, db_session, master_user, active_tenant_user, fake_export_storage
):
    """Master receives 404 when no ready export exists for the tenant."""
    tenant_id = await _tenant_id_for_user(db_session, active_tenant_user.id)
    assert tenant_id is not None

    headers = await _master_headers(client)
    resp = await client.get(
        f"/api/v1/tenants/{tenant_id}/export/download",
        headers=headers,
    )
    assert resp.status_code == 404, resp.text


# ── Shared visibility ──────────────────────────────────────────


async def test_master_and_tenant_share_same_job(
    client,
    db_session,
    master_user,
    active_tenant_user,
    fake_export_storage,
    fake_step_up_limiter,
):
    """Master and Tenant Admin see the same account-level export job."""
    tenant_id = await _tenant_id_for_user(db_session, active_tenant_user.id)
    assert tenant_id is not None

    master_headers = await _master_headers(client)
    tenant_headers = await _tenant_headers(client)

    # Master creates an export
    create = await client.post(
        f"/api/v1/tenants/{tenant_id}/export",
        json={"password": "master-password"},
        headers=master_headers,
    )
    assert create.status_code == 201
    master_job_id = create.json()["id"]

    # Tenant Admin sees the same job
    status = await client.get("/api/v1/me/export", headers=tenant_headers)
    assert status.status_code == 200, status.text
    body = status.json()
    assert body["id"] == master_job_id
    assert body["actor_role"] == "master"


# ── Cooldown is shared ─────────────────────────────────────────


async def test_master_export_enforces_cooldown(
    client,
    db_session,
    master_user,
    active_tenant_user,
    fake_export_storage,
    fake_step_up_limiter,
):
    """Master-initiated export contributes to the same 24h cooldown."""
    tenant_id = await _tenant_id_for_user(db_session, active_tenant_user.id)
    assert tenant_id is not None

    headers = await _master_headers(client)

    # Create first export
    create = await client.post(
        f"/api/v1/tenants/{tenant_id}/export",
        json={"password": "master-password"},
        headers=headers,
    )
    assert create.status_code == 201
    job_id = uuid.UUID(create.json()["id"])

    # Set to ready with cooldown active
    now = datetime.now(timezone.utc)
    await export_jobs_repository.update_status(
        db_session,
        job_id,
        "ready",
        r2_key="cooldown-key",
        artifact_size_bytes=100,
        expires_at=now + timedelta(hours=72),
        clear_lease=True,
        cooldown_until=now + timedelta(hours=24),
    )

    # Second export should be blocked by cooldown
    resp = await client.post(
        f"/api/v1/tenants/{tenant_id}/export",
        json={"password": "master-password"},
        headers=headers,
    )
    assert resp.status_code == 409, resp.text


# ── Cross-tenant isolation ─────────────────────────────────────


async def test_master_cannot_access_wrong_tenant_job(
    client,
    db_session,
    master_user,
    active_tenant_user,
    deactivated_tenant_user,
    fake_export_storage,
    fake_step_up_limiter,
):
    """Master's export for one tenant is isolated from another tenant."""
    tenant1_id = await _tenant_id_for_user(db_session, active_tenant_user.id)
    tenant2_id = await _tenant_id_for_user(db_session, deactivated_tenant_user.id)
    assert tenant1_id is not None
    assert tenant2_id is not None

    headers = await _master_headers(client)

    # Create export for tenant1
    create = await client.post(
        f"/api/v1/tenants/{tenant1_id}/export",
        json={"password": "master-password"},
        headers=headers,
    )
    assert create.status_code == 201

    # Status for tenant2 should be 204 (no job)
    status2 = await client.get(
        f"/api/v1/tenants/{tenant2_id}/export",
        headers=headers,
    )
    assert status2.status_code == 204, status2.text
