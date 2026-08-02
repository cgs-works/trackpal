"""Regression coverage for executor lifecycle review findings."""

from __future__ import annotations

from uuid import uuid4

import pytest
from app.schemas.lookup_executor_protocol import ChallengeResult
from app.services.lookup_executor_transport import FakeLookupExecutorTransport

pytestmark = pytest.mark.asyncio


@pytest.fixture
def executor_transport(monkeypatch):
    transport = FakeLookupExecutorTransport()
    from app.services import lookup_executor_registry

    monkeypatch.setattr(lookup_executor_registry, "_transport", transport)
    return transport


async def _master_headers(client) -> dict[str, str]:
    login = await client.post(
        "/api/v1/auth/login",
        json={"username": "master", "password": "master-password"},
    )
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def test_transport_mode_change_quarantines_active_executor(
    client, master_user, executor_transport
):
    headers = await _master_headers(client)
    create = await client.post(
        "/api/v1/lookup-executors/",
        headers=headers,
        json={"name": "Transport", "provider_label": "custom"},
    )
    executor_id = create.json()["executor"]["id"]
    verified = await client.post(
        f"/api/v1/lookup-executors/{executor_id}/verify", headers=headers
    )
    assert verified.status_code == 200

    updated = await client.put(
        f"/api/v1/lookup-executors/{executor_id}",
        headers=headers,
        json={"transport_mode": "http_encrypted"},
    )

    assert updated.status_code == 200, updated.text
    assert updated.json()["transport_mode"] == "http_encrypted"
    assert updated.json()["lifecycle_status"] == "disabled"
    assert updated.json()["requires_reverification"] is True


async def test_failed_pending_secret_challenge_does_not_promote_rotation(
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
        json={"name": "Rotation failure", "provider_label": "custom"},
    )
    executor_id = create.json()["executor"]["id"]
    rotation = await client.post(
        f"/api/v1/lookup-executors/{executor_id}/rotate-secret", headers=headers
    )
    assert rotation.status_code == 200

    failed = await client.post(
        f"/api/v1/lookup-executors/{executor_id}/verify", headers=headers
    )

    assert failed.status_code == 502
    fetched = await client.get(
        f"/api/v1/lookup-executors/{executor_id}", headers=headers
    )
    assert fetched.json()["secret_version"] == 1
    assert fetched.json()["pending_secret_version"] == 2
    assert fetched.json()["requires_reverification"] is True


async def test_hosting_password_reveal_audit_log_excludes_secret(
    client, master_user, executor_transport, monkeypatch, caplog
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
            "name": "Audited",
            "provider_label": "custom",
            "hosting_account_password": "do-not-log-this",
        },
    )

    with caplog.at_level("INFO"):
        response = await client.post(
            f"/api/v1/lookup-executors/{create.json()['executor']['id']}/reveal-hosting-password",
            headers=headers,
            json={"password": "master-password"},
        )

    assert response.status_code == 200
    records = [
        record
        for record in caplog.records
        if record.name == "app.api.v1.endpoints.lookup_executors"
    ]
    assert records
    assert records[-1].operation == "reveal_hosting_password"
    assert records[-1].outcome == "success"
    assert "do-not-log-this" not in caplog.text
