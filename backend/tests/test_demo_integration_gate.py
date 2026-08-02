from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from sqlalchemy import select

from app.models import Tenant

pytestmark = pytest.mark.asyncio


async def _login(client, username: str, password: str) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.mark.parametrize("plan", ["starter", "pro"])
async def test_demo_creation_login_workspace_lifecycle_and_ending_contract(
    client, db_session, master_user, plan
):
    master_headers = await _login(client, master_user.username, "master-password")
    created = await client.post(
        "/api/v1/demos/",
        json={"name": f"Integration Gate {plan.title()} Demo", "plan": plan},
        headers=master_headers,
    )

    assert created.status_code == 201, created.text
    credentials = created.json()
    assert credentials["status"] == "pending"
    assert credentials["demo_activated_at"] is None
    assert credentials["demo_expires_at"] is None

    demo_login = await client.post(
        "/api/v1/auth/login",
        json={
            "username": credentials["username"],
            "password": credentials["plain_password"],
        },
    )

    assert demo_login.status_code == 200, demo_login.text
    token_data = demo_login.json()
    assert token_data["is_demo"] is True
    assert token_data["demo_status"] == "active"
    assert token_data["tenant_plan"] == plan
    demo_headers = {"Authorization": f"Bearer {token_data['access_token']}"}

    tenant = await db_session.scalar(
        select(Tenant).where(Tenant.id == UUID(credentials["id"]))
    )
    assert tenant is not None
    assert tenant.demo_activated_at is not None
    assert tenant.demo_expires_at is not None

    heartbeat = await client.post("/api/v1/auth/heartbeat", headers=demo_headers)
    assert heartbeat.status_code == 200, heartbeat.text
    assert heartbeat.json()["demo_status"] == "active"

    expired_at = datetime.now(timezone.utc) - timedelta(hours=1)
    tenant.demo_activated_at = expired_at - timedelta(hours=48)
    tenant.demo_expires_at = expired_at
    await db_session.commit()

    ended_heartbeat = await client.post("/api/v1/auth/heartbeat", headers=demo_headers)
    assert ended_heartbeat.status_code == 410, ended_heartbeat.text
    assert ended_heartbeat.json()["detail"] == "demo_ended"


async def test_demo_guardrail_covers_business_and_external_route_families(
    client, active_demo_user
):
    headers = await _login(client, active_demo_user.username, "demo-password")

    routes = [
        ("get", "/api/v1/dashboard", None),
        ("get", "/api/v1/me", None),
        ("put", "/api/v1/me", {"full_name": "Blocked"}),
        ("get", "/api/v1/tenant-settings", None),
        ("get", "/api/v1/tenant-settings/timezones", None),
        ("get", "/api/v1/access-control/blocks", None),
        ("get", "/api/v1/clients", None),
        ("get", "/api/v1/catalog/services", None),
        ("get", "/api/v1/subscriptions", None),
        ("get", "/api/v1/subscription-settings", None),
        ("get", "/api/v1/code-services/tenants/current", None),
        ("get", "/api/v1/tenant/mailbox/", None),
        ("post", "/api/v1/tenant/mailbox/test", None),
        ("post", "/api/v1/tenant/mailbox/disconnect", None),
        ("get", "/api/v1/tenant/whatsapp-link/status", None),
        ("post", "/api/v1/tenant/whatsapp-link/pair", {}),
        ("get", "/api/v1/tenant/whatsapp-link/qr", None),
        ("post", "/api/v1/tenant/whatsapp-link/disconnect", None),
        ("get", "/api/v1/me/export", None),
        ("post", "/api/v1/me/export", None),
        ("post", "/api/v1/me/export/cancel", None),
        ("get", "/api/v1/me/export/download", None),
        ("get", "/api/v1/public-api-key", None),
        ("post", "/api/v1/public-api-key/regenerate", None),
        ("delete", "/api/v1/public-api-key", None),
        (
            "post",
            "/api/v1/me/delete-account",
            {"password": "demo-password", "destructive_word": "DELETE"},
        ),
    ]

    for method, path, payload in routes:
        request = getattr(client, method)
        kwargs = {"headers": headers}
        if payload is not None:
            kwargs["json"] = payload
        response = await request(path, **kwargs)
        assert response.status_code == 403, f"{method.upper()} {path}: {response.text}"
        assert response.json()["detail"] == "demo_operation_blocked"


async def test_demo_external_boundaries_are_rejected_before_side_effects(
    client, db_session, active_demo_user, master_user, monkeypatch
):
    from app.core.config import settings
    from app.models import Tenant

    tenant = await db_session.scalar(
        select(Tenant).where(Tenant.owner_user_id == active_demo_user.id)
    )
    assert tenant is not None
    monkeypatch.setattr(settings, "n8n_api_key", "test-n8n-key")

    with (
        patch(
            "app.api.v1.endpoints.integrations.mail_lookups.mailbox_config_repository.get_by_tenant",
            new=AsyncMock(),
        ) as get_mailbox,
        patch(
            "app.api.v1.endpoints.integrations.mail_lookups.get_lookup_execution_coordinator",
            new=AsyncMock(),
        ) as get_coordinator,
        patch(
            "app.services.export_service.get_current_export",
            new=AsyncMock(),
        ) as get_export,
    ):
        lookup = await client.post(
            "/api/v1/integrations/n8n/mail/lookups",
            headers={"X-API-Key": "test-n8n-key"},
            json={
                "tenant_id": str(tenant.id),
                "service_key": "generic",
                "target_email": "prospect@example.test",
            },
        )
        export = await client.get(
            f"/api/v1/tenants/{tenant.id}/export",
            headers=await _login(client, master_user.username, "master-password"),
        )

    assert lookup.status_code == 403
    assert lookup.json()["detail"] == "demo_operation_blocked"
    assert export.status_code == 403
    assert export.json()["detail"] == "demo_operation_blocked"
    get_mailbox.assert_not_awaited()
    get_coordinator.assert_not_called()
    get_export.assert_not_awaited()
