"""Master API tests for the external lookup executor registry."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.models import LookupExecutor, MailLookupJob, Tenant, TenantMailbox
from app.schemas.lookup_executor_protocol import ChallengeResult
from app.services.lookup_executor_transport import FakeLookupExecutorTransport

pytestmark = pytest.mark.asyncio


async def _master_headers(client):
    login = await client.post(
        "/api/v1/auth/login",
        json={"username": "master", "password": "master-password"},
    )
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def _tenant_headers(client):
    login = await client.post(
        "/api/v1/auth/login",
        json={"username": "tenant", "password": "tenant-password"},
    )
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


@pytest.fixture
def executor_transport(monkeypatch):
    transport = FakeLookupExecutorTransport()
    from app.services import lookup_executor_registry

    monkeypatch.setattr(lookup_executor_registry, "_transport", transport)
    return transport


@pytest.fixture
def lease_reader(monkeypatch):
    from app.services import lookup_executor_registry

    class Reader:
        count = 0

        async def active_count(self, executor_id: UUID) -> int:
            return self.count

    reader = Reader()
    monkeypatch.setattr(lookup_executor_registry, "_active_lease_reader", reader)
    return reader


async def test_master_can_create_draft_with_one_time_secret(
    client, master_user, executor_transport
):
    response = await client.post(
        "/api/v1/lookup-executors/",
        headers=await _master_headers(client),
        json={"name": "Render 1", "provider_label": "render", "max_concurrency": 1},
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["plain_secret"]
    assert body["executor"]["lifecycle_status"] == "draft"
    assert "hosting_account_password" not in body["executor"]
    assert "secret_encrypted" not in body["executor"]


async def test_capacity_uses_active_leases_instead_of_processing_job_count(
    client, db_session, master_user, active_tenant_user, lease_reader
):
    headers = await _master_headers(client)
    create = await client.post(
        "/api/v1/lookup-executors/",
        headers=headers,
        json={"name": "Capacity", "provider_label": "custom", "max_concurrency": 2},
    )
    executor_id = UUID(create.json()["executor"]["id"])
    tenant_result = await db_session.execute(
        select(Tenant).where(Tenant.owner_user_id == active_tenant_user.id)
    )
    tenant = tenant_result.scalar_one()
    mailbox = TenantMailbox(tenant_id=tenant.id, mailbox_email="capacity@example.com")
    db_session.add(mailbox)
    await db_session.flush()
    for _ in range(3):
        db_session.add(
            MailLookupJob(
                tenant_id=tenant.id,
                mailbox_id=mailbox.id,
                executor_id=executor_id,
                service_key="netflix",
                target_email="capacity@example.com",
                status="processing",
            )
        )
    await db_session.commit()
    lease_reader.count = 1

    response = await client.get(
        f"/api/v1/lookup-executors/{executor_id}", headers=headers
    )

    assert response.status_code == 200, response.text
    assert response.json()["active_jobs"] == 3
    assert response.json()["active_leases"] == 1
    assert response.json()["max_concurrency"] == 2

    listed = await client.get("/api/v1/lookup-executors/", headers=headers)
    listed_executor = next(
        item for item in listed.json() if item["id"] == str(executor_id)
    )
    assert listed_executor["active_jobs"] == 3
    assert listed_executor["active_leases"] == 1


async def test_non_master_cannot_manage_executors(client, active_tenant_user):
    response = await client.get(
        "/api/v1/lookup-executors/", headers=await _tenant_headers(client)
    )
    assert response.status_code == 403


async def test_enable_requires_a_successful_verification(
    client, master_user, executor_transport
):
    headers = await _master_headers(client)
    create = await client.post(
        "/api/v1/lookup-executors/",
        headers=headers,
        json={"name": "Unverified", "provider_label": "custom"},
    )

    response = await client.post(
        f"/api/v1/lookup-executors/{create.json()['executor']['id']}/enable",
        headers=headers,
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "executor_requires_verification"


async def test_disable_preserves_credentials_and_verified_executor_can_be_reenabled(
    client, master_user, executor_transport
):
    headers = await _master_headers(client)
    create = await client.post(
        "/api/v1/lookup-executors/",
        headers=headers,
        json={"name": "Lifecycle", "provider_label": "custom"},
    )
    executor_id = create.json()["executor"]["id"]
    verified = await client.post(
        f"/api/v1/lookup-executors/{executor_id}/verify", headers=headers
    )
    assert verified.status_code == 200

    disabled = await client.post(
        f"/api/v1/lookup-executors/{executor_id}/disable", headers=headers
    )
    assert disabled.status_code == 200
    assert disabled.json()["lifecycle_status"] == "disabled"
    assert disabled.json()["requires_reverification"] is False

    enabled = await client.post(
        f"/api/v1/lookup-executors/{executor_id}/enable", headers=headers
    )
    assert enabled.status_code == 200
    assert enabled.json()["lifecycle_status"] == "active"


async def test_verify_requires_exact_http_confirmation(
    client, master_user, executor_transport, monkeypatch
):
    create = await client.post(
        "/api/v1/lookup-executors/",
        headers=await _master_headers(client),
        json={
            "name": "HTTP executor",
            "provider_label": "custom",
            "transport_mode": "http_encrypted",
            "base_url": "http://executor.example.test",
        },
    )
    executor_id = create.json()["executor"]["id"]
    from app.services import export_service

    class Limiter:
        async def check(self, actor_id: str) -> None:
            return None

        async def record_failure(self, actor_id: str) -> None:
            return None

        async def record_success(self, actor_id: str) -> None:
            return None

    monkeypatch.setattr(export_service, "_step_up_limiter", Limiter())
    headers = await _master_headers(client)

    rejected = await client.post(
        f"/api/v1/lookup-executors/{executor_id}/verify",
        headers=headers,
        json={"confirmation": "ALLOW HTTPS"},
    )
    assert rejected.status_code == 400
    assert rejected.json()["detail"] == "insecure_http_confirmation_required"

    accepted = await client.post(
        f"/api/v1/lookup-executors/{executor_id}/verify",
        headers=headers,
        json={"confirmation": "ALLOW HTTP", "password": "master-password"},
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["lifecycle_status"] == "active"


async def test_rotation_stays_pending_until_matching_challenge(
    client, master_user, executor_transport
):
    headers = await _master_headers(client)
    create = await client.post(
        "/api/v1/lookup-executors/",
        headers=headers,
        json={"name": "Rotating", "provider_label": "custom"},
    )
    executor_id = create.json()["executor"]["id"]

    rotation = await client.post(
        f"/api/v1/lookup-executors/{executor_id}/rotate-secret", headers=headers
    )
    assert rotation.status_code == 200, rotation.text
    assert rotation.json()["plain_secret"]
    assert rotation.json()["executor"]["pending_secret_version"] == 2

    verified = await client.post(
        f"/api/v1/lookup-executors/{executor_id}/verify", headers=headers
    )
    assert verified.status_code == 200, verified.text
    assert verified.json()["pending_secret_version"] is None
    assert verified.json()["secret_version"] == 2


async def test_update_of_active_transport_forces_reverification(
    client, master_user, executor_transport
):
    headers = await _master_headers(client)
    create = await client.post(
        "/api/v1/lookup-executors/",
        headers=headers,
        json={"name": "Moved", "provider_label": "custom"},
    )
    executor_id = create.json()["executor"]["id"]
    assert (
        await client.post(
            f"/api/v1/lookup-executors/{executor_id}/verify", headers=headers
        )
    ).status_code == 200

    updated = await client.put(
        f"/api/v1/lookup-executors/{executor_id}",
        headers=headers,
        json={"base_url": "https://new-executor.example.test"},
    )

    assert updated.status_code == 200, updated.text
    assert updated.json()["lifecycle_status"] == "disabled"
    assert updated.json()["requires_reverification"] is True


async def test_failed_test_connection_quarantines_executor(
    client, master_user, monkeypatch
):
    from app.services import lookup_executor_registry

    transport = FakeLookupExecutorTransport(
        challenge_result=ChallengeResult(
            executor_id=uuid4(),
            protocol_version=1,
            runtime_version="fake",
            max_concurrency=1,
        )
    )
    monkeypatch.setattr(lookup_executor_registry, "_transport", transport)
    headers = await _master_headers(client)
    create = await client.post(
        "/api/v1/lookup-executors/",
        headers=headers,
        json={"name": "Broken", "provider_label": "custom"},
    )
    executor_id = create.json()["executor"]["id"]

    response = await client.post(
        f"/api/v1/lookup-executors/{executor_id}/test", headers=headers
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "executor_verification_failed"
    fetched = await client.get(
        f"/api/v1/lookup-executors/{executor_id}", headers=headers
    )
    assert fetched.json()["requires_reverification"] is True
    assert fetched.json()["health_status"] == "unhealthy"


async def test_failed_verification_sets_requires_reverification(
    client, master_user, monkeypatch
):
    from app.services import lookup_executor_registry

    transport = FakeLookupExecutorTransport(
        challenge_result=ChallengeResult(
            executor_id=uuid4(),
            protocol_version=1,
            runtime_version="fake",
            max_concurrency=1,
        )
    )
    monkeypatch.setattr(lookup_executor_registry, "_transport", transport)
    headers = await _master_headers(client)
    create = await client.post(
        "/api/v1/lookup-executors/",
        headers=headers,
        json={"name": "Unhealthy", "provider_label": "custom"},
    )

    response = await client.post(
        f"/api/v1/lookup-executors/{create.json()['executor']['id']}/verify",
        headers=headers,
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "executor_verification_failed"
    fetched = await client.get(
        f"/api/v1/lookup-executors/{create.json()['executor']['id']}",
        headers=headers,
    )
    assert fetched.json()["requires_reverification"] is True


async def test_reveal_hosting_password_rejects_wrong_master_password(
    client, master_user, executor_transport, monkeypatch
):
    from app.services import export_service

    class Limiter:
        async def check(self, actor_id: str) -> None:
            return None

        async def record_failure(self, actor_id: str) -> None:
            return None

        async def record_success(self, actor_id: str) -> None:
            return None

    monkeypatch.setattr(export_service, "_step_up_limiter", Limiter())
    headers = await _master_headers(client)
    create = await client.post(
        "/api/v1/lookup-executors/",
        headers=headers,
        json={
            "name": "Protected",
            "provider_label": "custom",
            "hosting_account_password": "secret",
        },
    )

    response = await client.post(
        f"/api/v1/lookup-executors/{create.json()['executor']['id']}/reveal-hosting-password",
        headers=headers,
        json={"password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "invalid_master_password"


async def test_reveal_hosting_password_fails_closed_without_limiter(
    client, master_user, executor_transport, monkeypatch
):
    from app.services import export_service

    monkeypatch.setattr(export_service, "_step_up_limiter", None)
    headers = await _master_headers(client)
    create = await client.post(
        "/api/v1/lookup-executors/",
        headers=headers,
        json={
            "name": "Unavailable step up",
            "provider_label": "custom",
            "hosting_account_password": "secret",
        },
    )

    response = await client.post(
        f"/api/v1/lookup-executors/{create.json()['executor']['id']}/reveal-hosting-password",
        headers=headers,
        json={"password": "master-password"},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "step_up_unavailable"


async def test_reveal_hosting_password_requires_step_up(
    client, master_user, executor_transport, monkeypatch
):
    from app.services import export_service

    class Limiter:
        async def check(self, actor_id: str) -> None:
            return None

        async def record_failure(self, actor_id: str) -> None:
            return None

        async def record_success(self, actor_id: str) -> None:
            return None

    monkeypatch.setattr(export_service, "_step_up_limiter", Limiter())
    headers = await _master_headers(client)
    create = await client.post(
        "/api/v1/lookup-executors/",
        headers=headers,
        json={
            "name": "Hosted",
            "provider_label": "custom",
            "hosting_account_password": "hosting-secret",
        },
    )
    response = await client.post(
        f"/api/v1/lookup-executors/{create.json()['executor']['id']}/reveal-hosting-password",
        headers=headers,
        json={"password": "master-password"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["hosting_account_password"] == "hosting-secret"


async def test_ordinary_get_does_not_reveal_hosting_password(
    client, master_user, executor_transport
):
    headers = await _master_headers(client)
    create = await client.post(
        "/api/v1/lookup-executors/",
        headers=headers,
        json={
            "name": "Safe",
            "provider_label": "custom",
            "hosting_account_password": "secret",
        },
    )
    fetched = await client.get(
        f"/api/v1/lookup-executors/{create.json()['executor']['id']}",
        headers=headers,
    )
    assert fetched.status_code == 200
    assert "hosting_account_password" not in fetched.json()
    assert fetched.json()["has_hosting_password"] is True


async def test_delete_is_blocked_by_active_jobs_and_leases(
    client, db_session, master_user, active_tenant_user, lease_reader
):
    headers = await _master_headers(client)
    create = await client.post(
        "/api/v1/lookup-executors/",
        headers=headers,
        json={"name": "Busy", "provider_label": "custom"},
    )
    executor_id = UUID(create.json()["executor"]["id"])
    tenant_result = await db_session.execute(
        select(Tenant).where(Tenant.owner_user_id == active_tenant_user.id)
    )
    tenant = tenant_result.scalar_one()
    mailbox = TenantMailbox(tenant_id=tenant.id, mailbox_email="x@example.com")
    db_session.add(mailbox)
    await db_session.flush()
    db_session.add(
        MailLookupJob(
            tenant_id=tenant.id,
            mailbox_id=mailbox.id,
            executor_id=executor_id,
            service_key="netflix",
            target_email="x@example.com",
            status="processing",
        )
    )
    await db_session.commit()

    blocked = await client.delete(
        f"/api/v1/lookup-executors/{executor_id}", headers=headers
    )
    assert blocked.status_code == 409
    assert blocked.json()["detail"] == "executor_has_active_jobs"

    executor = await db_session.get(LookupExecutor, executor_id)
    assert executor is not None
    lease_reader.count = 1
    await db_session.execute(
        MailLookupJob.__table__.delete().where(MailLookupJob.executor_id == executor_id)
    )
    await db_session.commit()
    blocked_lease = await client.delete(
        f"/api/v1/lookup-executors/{executor_id}", headers=headers
    )
    assert blocked_lease.status_code == 409
    assert blocked_lease.json()["detail"] == "executor_has_active_leases"


async def test_delete_fails_closed_when_lease_coordination_unavailable(
    client, master_user
):
    from app.services import lookup_executor_registry

    headers = await _master_headers(client)
    create = await client.post(
        "/api/v1/lookup-executors/",
        headers=headers,
        json={"name": "Unavailable", "provider_label": "custom"},
    )

    class Unavailable:
        async def active_count(self, executor_id: UUID) -> int:
            raise lookup_executor_registry.ExecutorCoordinationUnavailable

    lookup_executor_registry._active_lease_reader = Unavailable()
    response = await client.delete(
        f"/api/v1/lookup-executors/{create.json()['executor']['id']}",
        headers=headers,
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "executor_coordination_unavailable"
