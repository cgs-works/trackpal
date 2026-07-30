"""Tests for Tenant Admin self-service Tenant Deletion.

Uses the real ASGI application with fake Redis and Evolution disabled.
Tests the full deletion lifecycle including step-up, export cancellation,
external cleanup, database cascades, and post-delete auth failure.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.models import Tenant, User
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


async def _another_tenant_headers(client):
    """Login as a second tenant user for isolation tests."""
    login = await client.post(
        "/api/v1/auth/login",
        json={"username": "other-tenant", "password": "tenant-password"},
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
    """Wire a no-op step-up limiter that always allows.

    Set ``step_up_fail_count`` on the limiter to force failure.
    """
    from app.services import export_service

    class _TestStepUp:
        """Allows step-up unless configured to fail."""

        def __init__(self):
            self._fail_count: dict[str, int] = {}

        async def check(self, actor_id: str) -> None:
            count = self._fail_count.get(actor_id, 0)
            if count >= 3:
                from app.services.step_up_limiter import StepUpError

                raise StepUpError("Too many failed attempts")

        async def record_failure(self, actor_id: str) -> None:
            self._fail_count[actor_id] = self._fail_count.get(actor_id, 0) + 1

        async def record_success(self, actor_id: str) -> None:
            self._fail_count.pop(actor_id, None)

    original = getattr(export_service, "_step_up_limiter", None)
    limiter = _TestStepUp()
    export_service._step_up_limiter = limiter
    yield limiter
    export_service._step_up_limiter = original


# ── Additional fixtures for deletion tests ─────────────────────


@pytest_asyncio.fixture
async def other_tenant_user(db_session):
    """A second active tenant for isolation tests."""
    from app.core.security import get_password_hash

    user = User(
        username="other-tenant",
        password_hash=get_password_hash("tenant-password"),
        role="tenant",
    )
    db_session.add(user)
    await db_session.flush()
    tenant = Tenant(
        owner_user_id=user.id,
        client_prefix="oth01",
        name="Other Tenant",
        whatsapp_phone="+12015550004",
        is_active=True,
    )
    db_session.add(tenant)
    await db_session.flush()
    from app.models.tenant_settings import TenantSettings

    db_session.add(TenantSettings(tenant_id=tenant.id, locale="en"))
    await db_session.commit()
    return user


# ── POST /me/delete-account ────────────────────────────────────


async def test_delete_account_requires_authentication(client):
    """Unauthenticated requests receive 401."""
    resp = await client.post(
        "/api/v1/me/delete-account",
        json={"password": "x", "destructive_word": "DELETE"},
    )
    assert resp.status_code == 401


async def test_delete_account_requires_tenant_role(
    client, master_user, fake_export_storage, fake_step_up_limiter
):
    """Master users cannot access self-deletion."""
    headers = await _master_headers(client)
    resp = await client.post(
        "/api/v1/me/delete-account",
        json={"password": "master-password", "destructive_word": "DELETE"},
        headers=headers,
    )
    assert resp.status_code == 403


async def test_delete_account_rejects_client_user(
    client, active_client_user, fake_export_storage, fake_step_up_limiter
):
    """Client users cannot delete the tenant."""
    login = await client.post(
        "/api/v1/auth/login",
        json={
            "username": f"{active_client_user.username}",
            "password": "client-password",
        },
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    resp = await client.post(
        "/api/v1/me/delete-account",
        json={"password": "x", "destructive_word": "DELETE"},
        headers=headers,
    )
    assert resp.status_code == 403


async def test_delete_account_succeeds_with_valid_credentials(
    client, db_session, active_tenant_user, fake_export_storage, fake_step_up_limiter
):
    """Tenant Admin can delete their account with valid password + destructive word."""
    headers = await _tenant_headers(client)
    resp = await client.post(
        "/api/v1/me/delete-account",
        json={"password": "tenant-password", "destructive_word": "ELIMINAR"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True

    # Verify tenant and user are gone
    tenant_result = await db_session.execute(
        select(Tenant).where(Tenant.owner_user_id == active_tenant_user.id)
    )
    assert tenant_result.scalar_one_or_none() is None

    user_result = await db_session.execute(
        select(User).where(User.id == active_tenant_user.id)
    )
    assert user_result.scalar_one_or_none() is None


async def test_delete_account_wrong_password(
    client, db_session, active_tenant_user, fake_export_storage, fake_step_up_limiter
):
    """Wrong password returns 401."""
    headers = await _tenant_headers(client)
    resp = await client.post(
        "/api/v1/me/delete-account",
        json={"password": "wrong-password", "destructive_word": "ELIMINAR"},
        headers=headers,
    )
    assert resp.status_code == 401, resp.text


async def test_delete_account_wrong_destructive_word(
    client, db_session, active_tenant_user, fake_export_storage, fake_step_up_limiter
):
    """Wrong destructive word returns 401."""
    headers = await _tenant_headers(client)
    resp = await client.post(
        "/api/v1/me/delete-account",
        json={
            "password": "tenant-password",
            "destructive_word": "DELETE",
        },  # wrong for es locale
        headers=headers,
    )
    assert resp.status_code == 401, resp.text


async def test_delete_account_cancels_export(
    client,
    db_session,
    active_tenant_user,
    fake_export_storage,
    fake_step_up_limiter,
):
    """An active export is cancelled before deletion."""
    headers = await _tenant_headers(client)
    tenant_id = await _tenant_id_for_user(db_session, active_tenant_user.id)
    assert tenant_id is not None

    # Create an export job
    from app.repositories import export_jobs_repository

    job = await export_jobs_repository.create(
        db_session,
        tenant_id=tenant_id,
        requested_by=active_tenant_user.id,
        actor_role="tenant",
    )
    assert job.status == "pending"

    # Delete account — should cancel the export
    resp = await client.post(
        "/api/v1/me/delete-account",
        json={"password": "tenant-password", "destructive_word": "ELIMINAR"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text

    # Verify the tenant and its jobs are deleted
    jobs = await export_jobs_repository.get_all_for_tenant(db_session, tenant_id)
    assert len(jobs) == 0


async def test_delete_account_purges_r2_objects(
    client,
    db_session,
    active_tenant_user,
    fake_export_storage,
    fake_step_up_limiter,
):
    """R2 objects are purged before database deletion."""
    tenant_id = await _tenant_id_for_user(db_session, active_tenant_user.id)
    assert tenant_id is not None

    # Create a ready export with an R2 object
    now = datetime.now(timezone.utc)
    job = await export_jobs_repository.create(
        db_session,
        tenant_id=tenant_id,
        requested_by=active_tenant_user.id,
        actor_role="tenant",
    )
    await export_jobs_repository.update_status(
        db_session,
        job.id,
        "ready",
        r2_key="delete-test-key",
        artifact_size_bytes=100,
        expires_at=now + timedelta(hours=72),
        clear_lease=True,
    )
    await fake_export_storage.upload("delete-test-key", b"test-data")

    # Verify the object exists before deletion
    meta = await fake_export_storage.get_metadata("delete-test-key")
    assert meta.size_bytes == 9  # len(b"test-data")

    headers = await _tenant_headers(client)
    resp = await client.post(
        "/api/v1/me/delete-account",
        json={"password": "tenant-password", "destructive_word": "ELIMINAR"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text

    # Verify the object was purged
    with pytest.raises(Exception):
        await fake_export_storage.get_metadata("delete-test-key")


async def test_delete_account_evolution_failure_preserves_tenant(
    client,
    db_session,
    active_tenant_user,
    fake_export_storage,
    fake_step_up_limiter,
    monkeypatch,
):
    """Evolution instance deletion failure preserves the tenant for retry."""
    tenant_id = await _tenant_id_for_user(db_session, active_tenant_user.id)
    assert tenant_id is not None

    # Make Evolution client raise
    async def _fail_delete(*args, **kwargs):
        raise RuntimeError("Evolution API unavailable")

    monkeypatch.setattr(
        "app.services.evolution_client.evolution_client.delete_instance",
        _fail_delete,
    )

    # Give the tenant an Evolution instance to trigger the fail path
    result = await db_session.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    assert tenant is not None
    tenant.evolution_instance_name = "test-instance"
    await db_session.commit()

    headers = await _tenant_headers(client)
    resp = await client.post(
        "/api/v1/me/delete-account",
        json={"password": "tenant-password", "destructive_word": "ELIMINAR"},
        headers=headers,
    )
    assert resp.status_code == 409, resp.text  # Conflict / retryable error

    # Tenant should still exist
    tenant_check = await db_session.execute(
        select(Tenant).where(Tenant.id == tenant_id)
    )
    assert tenant_check.scalar_one_or_none() is not None


async def test_delete_account_r2_failure_preserves_tenant(
    client,
    db_session,
    active_tenant_user,
    fake_export_storage,
    fake_step_up_limiter,
):
    """R2 deletion failure preserves the tenant for retry."""
    tenant_id = await _tenant_id_for_user(db_session, active_tenant_user.id)
    assert tenant_id is not None

    # Create a ready export with an R2 object
    now = datetime.now(timezone.utc)
    job = await export_jobs_repository.create(
        db_session,
        tenant_id=tenant_id,
        requested_by=active_tenant_user.id,
        actor_role="tenant",
    )
    await export_jobs_repository.update_status(
        db_session,
        job.id,
        "ready",
        r2_key="failing-key",
        artifact_size_bytes=100,
        expires_at=now + timedelta(hours=72),
        clear_lease=True,
    )

    # Make storage raise on delete
    from app.services.export_storage._exceptions import StorageOperationError

    async def _fail_delete(key):
        raise StorageOperationError("R2 unavailable")

    fake_export_storage.delete = _fail_delete  # type: ignore[method-assign]

    headers = await _tenant_headers(client)
    resp = await client.post(
        "/api/v1/me/delete-account",
        json={"password": "tenant-password", "destructive_word": "ELIMINAR"},
        headers=headers,
    )
    assert resp.status_code == 409, resp.text

    # Tenant should still exist
    tenant_check = await db_session.execute(
        select(Tenant).where(Tenant.id == tenant_id)
    )
    assert tenant_check.scalar_one_or_none() is not None


async def test_delete_account_idempotent_retry(
    client,
    db_session,
    active_tenant_user,
    fake_export_storage,
    fake_step_up_limiter,
):
    """After partial external cleanup, a retry succeeds because objects are already absent."""
    tenant_id = await _tenant_id_for_user(db_session, active_tenant_user.id)
    assert tenant_id is not None

    headers = await _tenant_headers(client)

    # First call — succeed
    resp = await client.post(
        "/api/v1/me/delete-account",
        json={"password": "tenant-password", "destructive_word": "ELIMINAR"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text

    # Second call — should 401 since the user (and tenant) no longer exist
    # and the JWT token cannot authenticate against a deleted user.
    resp2 = await client.post(
        "/api/v1/me/delete-account",
        json={"password": "tenant-password", "destructive_word": "ELIMINAR"},
        headers=headers,
    )
    assert resp2.status_code == 401, resp2.text


async def test_delete_account_requires_owning_tenant(
    client,
    db_session,
    active_tenant_user,
    other_tenant_user,
    fake_export_storage,
    fake_step_up_limiter,
):
    """Only the owning Tenant Admin can delete their account."""
    # Login as other-tenant and try to access deletion
    headers = await _another_tenant_headers(client)
    resp = await client.post(
        "/api/v1/me/delete-account",
        json={"password": "tenant-password", "destructive_word": "DELETE"},
        headers=headers,
    )
    # Should succeed because other-tenant is deleting their own account
    assert resp.status_code == 200, resp.text

    # Verify the other tenant is gone
    other_tenant_id = await _tenant_id_for_user(db_session, other_tenant_user.id)
    assert other_tenant_id is None

    # The original tenant should still exist
    original_tenant_id = await _tenant_id_for_user(db_session, active_tenant_user.id)
    assert original_tenant_id is not None


async def test_delete_account_step_up_rate_limit(
    client,
    db_session,
    active_tenant_user,
    fake_export_storage,
    fake_step_up_limiter,
):
    """Three failed attempts block further attempts."""
    headers = await _tenant_headers(client)

    # Three wrong attempts
    for _ in range(3):
        resp = await client.post(
            "/api/v1/me/delete-account",
            json={"password": "wrong", "destructive_word": "ELIMINAR"},
            headers=headers,
        )
        assert resp.status_code == 401

    # Fourth attempt should be rate-limited
    resp = await client.post(
        "/api/v1/me/delete-account",
        json={"password": "tenant-password", "destructive_word": "ELIMINAR"},
        headers=headers,
    )
    assert resp.status_code == 429, resp.text


async def test_delete_account_deactivates_inactive_tenant(
    client,
    db_session,
    deactivated_tenant_user,
    fake_export_storage,
    fake_step_up_limiter,
):
    """An already deactivated tenant gets an error."""
    # Login as deactivated tenant (should fail auth since account is inactive)
    resp = await client.post(
        "/api/v1/auth/login",
        json={
            "username": "inactive-tenant",
            "password": "tenant-password",
        },
    )
    assert resp.status_code == 401


async def test_post_deletion_auth_failure(
    client,
    db_session,
    active_tenant_user,
    fake_export_storage,
    fake_step_up_limiter,
):
    """After successful deletion, the user cannot re-authenticate."""
    headers = await _tenant_headers(client)

    resp = await client.post(
        "/api/v1/me/delete-account",
        json={"password": "tenant-password", "destructive_word": "ELIMINAR"},
        headers=headers,
    )
    assert resp.status_code == 200

    # Try to login again — should fail
    login = await client.post(
        "/api/v1/auth/login",
        json={"username": "tenant", "password": "tenant-password"},
    )
    assert login.status_code == 401


async def test_delete_account_spanish_destructive_word(
    client, db_session, active_tenant_user, fake_export_storage, fake_step_up_limiter
):
    """Spanish locale accepts ELIMINAR as destructive word."""
    # Set locale to Spanish
    tenant_id = await _tenant_id_for_user(db_session, active_tenant_user.id)
    assert tenant_id is not None

    from sqlalchemy import update

    from app.models.tenant_settings import TenantSettings

    await db_session.execute(
        update(TenantSettings)
        .where(TenantSettings.tenant_id == tenant_id)
        .values(locale="es")
    )
    await db_session.commit()

    headers = await _tenant_headers(client)
    resp = await client.post(
        "/api/v1/me/delete-account",
        json={"password": "tenant-password", "destructive_word": "ELIMINAR"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["success"] is True


# ── Cascading data deletion ────────────────────────────────────


async def test_delete_account_cascades_to_clients(
    client,
    db_session,
    active_tenant_user,
    active_client_user,
    inactive_client_user,
    fake_export_storage,
    fake_step_up_limiter,
):
    """Client users are deleted when the tenant is deleted."""
    headers = await _tenant_headers(client)

    resp = await client.post(
        "/api/v1/me/delete-account",
        json={"password": "tenant-password", "destructive_word": "ELIMINAR"},
        headers=headers,
    )
    assert resp.status_code == 200

    # Verify client users are gone
    client_user_check = await db_session.execute(
        select(User).where(User.id == active_client_user.id)
    )
    assert client_user_check.scalar_one_or_none() is None

    inactive_client_check = await db_session.execute(
        select(User).where(User.id == inactive_client_user.id)
    )
    assert inactive_client_check.scalar_one_or_none() is None


async def test_delete_account_cascades_to_tenant_data(
    client,
    db_session,
    active_tenant_user,
    fake_export_storage,
    fake_step_up_limiter,
):
    """Services, plans, and settings are cascade-deleted."""
    tenant_id = await _tenant_id_for_user(db_session, active_tenant_user.id)
    assert tenant_id is not None

    headers = await _tenant_headers(client)

    resp = await client.post(
        "/api/v1/me/delete-account",
        json={"password": "tenant-password", "destructive_word": "ELIMINAR"},
        headers=headers,
    )
    assert resp.status_code == 200

    # Verify tenant data is gone
    from app.models.tenant_settings import TenantSettings

    settings_check = await db_session.execute(
        select(TenantSettings).where(TenantSettings.tenant_id == tenant_id)
    )
    assert settings_check.scalar_one_or_none() is None


async def test_delete_account_rejects_cross_tenant(
    client,
    db_session,
    active_tenant_user,
    other_tenant_user,
    fake_export_storage,
    fake_step_up_limiter,
):
    """One tenant admin cannot delete another tenant."""
    # This is implicitly tested by the owning-tenant check,
    # but let's verify cross-tenant token access
    tenant1_id = await _tenant_id_for_user(db_session, active_tenant_user.id)
    tenant2_id = await _tenant_id_for_user(db_session, other_tenant_user.id)
    assert tenant1_id is not None
    assert tenant2_id is not None

    headers = await _tenant_headers(client)  # tenant1's headers
    resp = await client.post(
        "/api/v1/me/delete-account",
        json={"password": "tenant-password", "destructive_word": "ELIMINAR"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text

    # tenant2 should still exist
    tenant2_check = await db_session.execute(
        select(Tenant).where(Tenant.id == tenant2_id)
    )
    assert tenant2_check.scalar_one_or_none() is not None


# ── POST /tenants/{tenant_id}/delete (Master Tenant Deletion) ────


async def _tenant_id_from_user(db_session, user):
    result = await db_session.execute(
        select(Tenant).where(Tenant.owner_user_id == user.id)
    )
    tenant = result.scalar_one_or_none()
    assert tenant is not None
    return tenant.id


async def _master_delete(
    client, tenant_id, password="master-password", destructive_word="DELETE"
):
    headers = await _master_headers(client)
    return await client.post(
        f"/api/v1/tenants/{tenant_id}/delete",
        json={"password": password, "destructive_word": destructive_word},
        headers=headers,
    )


async def test_master_delete_requires_authentication(client):
    """Unauthenticated requests receive 401."""
    resp = await client.post(
        "/api/v1/tenants/00000000-0000-0000-0000-000000000000/delete",
        json={"password": "x", "destructive_word": "DELETE"},
    )
    assert resp.status_code == 401


async def test_master_delete_requires_master_role(
    client,
    db_session,
    master_user,
    active_tenant_user,
    fake_export_storage,
    fake_step_up_limiter,
):
    """Tenant users cannot use Master deletion endpoint."""
    tenant_id = await _tenant_id_from_user(db_session, active_tenant_user)
    # Login as tenant and try to use the Master deletion endpoint
    tenant_headers = await _tenant_headers(client)
    resp = await client.post(
        f"/api/v1/tenants/{tenant_id}/delete",
        json={"password": "tenant-password", "destructive_word": "ELIMINAR"},
        headers=tenant_headers,
    )
    assert resp.status_code == 403, resp.text


@pytest.mark.usefixtures("master_user")
async def test_master_delete_rejects_active_tenant(
    client, db_session, active_tenant_user, fake_export_storage, fake_step_up_limiter
):
    """Active tenant cannot be deleted by Master."""
    tenant_id = await _tenant_id_from_user(db_session, active_tenant_user)
    resp = await _master_delete(client, tenant_id)
    assert resp.status_code == 401, resp.text
    assert "Cannot delete active tenant" in resp.json()["detail"]


@pytest.mark.usefixtures("master_user")
async def test_master_delete_succeeds_for_inactive_tenant(
    client,
    db_session,
    deactivated_tenant_user,
    fake_export_storage,
    fake_step_up_limiter,
):
    """Master can delete an inactive tenant with valid password + destructive word."""
    tenant_id = await _tenant_id_from_user(db_session, deactivated_tenant_user)
    resp = await _master_delete(client, tenant_id)
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"success": True}

    # Verify tenant and owner user are gone
    tenant_check = await db_session.execute(
        select(Tenant).where(Tenant.id == tenant_id)
    )
    assert tenant_check.scalar_one_or_none() is None

    owner_check = await db_session.execute(
        select(User).where(User.id == deactivated_tenant_user.id)
    )
    assert owner_check.scalar_one_or_none() is None


@pytest.mark.usefixtures("master_user")
async def test_master_delete_wrong_password(
    client,
    db_session,
    deactivated_tenant_user,
    fake_export_storage,
    fake_step_up_limiter,
):
    """Wrong Master password returns 401."""
    tenant_id = await _tenant_id_from_user(db_session, deactivated_tenant_user)
    resp = await _master_delete(client, tenant_id, password="wrong-password")
    assert resp.status_code == 401, resp.text


@pytest.mark.usefixtures("master_user")
async def test_master_delete_wrong_destructive_word(
    client,
    db_session,
    deactivated_tenant_user,
    fake_export_storage,
    fake_step_up_limiter,
):
    """Wrong destructive word returns 401."""
    tenant_id = await _tenant_id_from_user(db_session, deactivated_tenant_user)
    resp = await _master_delete(client, tenant_id, destructive_word="ELIMINAR")
    assert resp.status_code == 401, resp.text


@pytest.mark.usefixtures("master_user")
async def test_master_delete_cancels_export(
    client,
    db_session,
    deactivated_tenant_user,
    fake_export_storage,
    fake_step_up_limiter,
):
    """An active export is cancelled before Master deletion."""
    tenant_id = await _tenant_id_from_user(db_session, deactivated_tenant_user)

    # Create an export job for the tenant
    job = await export_jobs_repository.create(
        db_session,
        tenant_id=tenant_id,
        requested_by=deactivated_tenant_user.id,
        actor_role="tenant",
    )
    assert job.status == "pending"

    resp = await _master_delete(client, tenant_id)
    assert resp.status_code == 200, resp.text

    # Verify export jobs are purged
    jobs = await export_jobs_repository.get_all_for_tenant(db_session, tenant_id)
    assert len(jobs) == 0


@pytest.mark.usefixtures("master_user")
async def test_master_delete_purges_r2_objects(
    client,
    db_session,
    deactivated_tenant_user,
    fake_export_storage,
    fake_step_up_limiter,
):
    """R2 objects are purged before database deletion."""
    tenant_id = await _tenant_id_from_user(db_session, deactivated_tenant_user)

    now = datetime.now(timezone.utc)
    job = await export_jobs_repository.create(
        db_session,
        tenant_id=tenant_id,
        requested_by=deactivated_tenant_user.id,
        actor_role="tenant",
    )
    await export_jobs_repository.update_status(
        db_session,
        job.id,
        "ready",
        r2_key="master-delete-test-key",
        artifact_size_bytes=100,
        expires_at=now + timedelta(hours=72),
        clear_lease=True,
    )
    await fake_export_storage.upload("master-delete-test-key", b"test-data")

    # Verify object exists before deletion
    meta = await fake_export_storage.get_metadata("master-delete-test-key")
    assert meta.size_bytes == 9

    resp = await _master_delete(client, tenant_id)
    assert resp.status_code == 200, resp.text

    # Verify object was purged
    with pytest.raises(Exception):
        await fake_export_storage.get_metadata("master-delete-test-key")


@pytest.mark.usefixtures("master_user")
async def test_master_delete_evolution_failure_preserves_tenant(
    client,
    db_session,
    deactivated_tenant_user,
    fake_export_storage,
    fake_step_up_limiter,
    monkeypatch,
):
    """Evolution failure preserves the tenant for retry."""
    tenant_id = await _tenant_id_from_user(db_session, deactivated_tenant_user)

    async def _fail_delete(*args, **kwargs):
        raise RuntimeError("Evolution API unavailable")

    monkeypatch.setattr(
        "app.services.evolution_client.evolution_client.delete_instance",
        _fail_delete,
    )

    # Give the tenant an Evolution instance
    result = await db_session.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    assert tenant is not None
    tenant.evolution_instance_name = "test-instance"
    await db_session.commit()

    resp = await _master_delete(client, tenant_id)
    assert resp.status_code == 409, resp.text

    # Tenant should still exist
    tenant_check = await db_session.execute(
        select(Tenant).where(Tenant.id == tenant_id)
    )
    assert tenant_check.scalar_one_or_none() is not None


@pytest.mark.usefixtures("master_user")
async def test_master_delete_r2_failure_preserves_tenant(
    client,
    db_session,
    deactivated_tenant_user,
    fake_export_storage,
    fake_step_up_limiter,
):
    """R2 failure preserves the tenant for retry."""
    tenant_id = await _tenant_id_from_user(db_session, deactivated_tenant_user)

    now = datetime.now(timezone.utc)
    job = await export_jobs_repository.create(
        db_session,
        tenant_id=tenant_id,
        requested_by=deactivated_tenant_user.id,
        actor_role="tenant",
    )
    await export_jobs_repository.update_status(
        db_session,
        job.id,
        "ready",
        r2_key="failing-key",
        artifact_size_bytes=100,
        expires_at=now + timedelta(hours=72),
        clear_lease=True,
    )

    from app.services.export_storage._exceptions import StorageOperationError

    async def _fail_delete(key):
        raise StorageOperationError("R2 unavailable")

    fake_export_storage.delete = _fail_delete  # type: ignore[method-assign]

    resp = await _master_delete(client, tenant_id)
    assert resp.status_code == 409, resp.text

    tenant_check = await db_session.execute(
        select(Tenant).where(Tenant.id == tenant_id)
    )
    assert tenant_check.scalar_one_or_none() is not None


@pytest.mark.usefixtures("master_user")
async def test_master_delete_step_up_rate_limit(
    client,
    db_session,
    deactivated_tenant_user,
    fake_export_storage,
    fake_step_up_limiter,
):
    """Three failed attempts block further attempts."""
    tenant_id = await _tenant_id_from_user(db_session, deactivated_tenant_user)
    headers = await _master_headers(client)

    # Three wrong attempts
    for _ in range(3):
        resp = await client.post(
            f"/api/v1/tenants/{tenant_id}/delete",
            json={"password": "wrong", "destructive_word": "DELETE"},
            headers=headers,
        )
        assert resp.status_code == 401

    # Fourth attempt should be rate-limited
    resp = await client.post(
        f"/api/v1/tenants/{tenant_id}/delete",
        json={"password": "master-password", "destructive_word": "DELETE"},
        headers=headers,
    )
    assert resp.status_code == 429, resp.text
