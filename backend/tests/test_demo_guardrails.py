import logging
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.models import Tenant, TenantApiKey, TenantSettings

pytestmark = pytest.mark.asyncio


async def _login(client, username: str, password: str) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/dashboard",
        "/api/v1/me",
        "/api/v1/tenant-settings",
        "/api/v1/tenant-settings/timezones",
        "/api/v1/access-control/blocks",
        "/api/v1/clients",
        "/api/v1/catalog/services",
        "/api/v1/subscriptions",
        "/api/v1/subscription-settings",
        "/api/v1/code-services/tenants/current",
        "/api/v1/tenant/mailbox/",
        "/api/v1/tenant/whatsapp-link/status",
        "/api/v1/me/export",
        "/api/v1/public-api-key",
    ],
)
async def test_demo_jwt_is_rejected_at_tenant_scoped_seams(
    client, active_demo_user, path
):
    headers = await _login(client, active_demo_user.username, "demo-password")

    response = await client.get(path, headers=headers)

    assert response.status_code == 403, response.text
    assert response.json()["detail"] == "demo_operation_blocked"


async def test_demo_allowlist_keeps_auth_help_i18n_heartbeat_and_password_usable(
    client, active_demo_user
):
    headers = await _login(client, active_demo_user.username, "demo-password")

    i18n = await client.get("/api/v1/i18n/catalog", headers=headers)
    help_index = await client.get("/api/v1/help", headers=headers)
    heartbeat = await client.post("/api/v1/auth/heartbeat", headers=headers)
    password = await client.put(
        "/api/v1/me/password",
        headers=headers,
        json={"old_password": "demo-password", "new_password": "new-demo-password"},
    )

    assert i18n.status_code == 200, i18n.text
    assert help_index.status_code == 200, help_index.text
    assert heartbeat.status_code == 200, heartbeat.text
    assert password.status_code == 200, password.text


async def test_demo_help_acknowledgement_is_not_a_persistence_allowlist(
    client, active_demo_user
):
    headers = await _login(client, active_demo_user.username, "demo-password")

    response = await client.post(
        "/api/v1/help/tour/tenant-admin-pro-1/acknowledge",
        headers=headers,
        json={"status": "completed"},
    )

    assert response.status_code == 403, response.text
    assert response.json()["detail"] == "demo_operation_blocked"


async def test_demo_guardrail_prevents_settings_persistence(
    client, db_session, active_demo_user
):
    headers = await _login(client, active_demo_user.username, "demo-password")

    response = await client.put(
        "/api/v1/tenant-settings",
        headers=headers,
        json={"locale": "es", "timezone": "America/Santo_Domingo"},
    )

    tenant = (
        await db_session.execute(
            select(Tenant).where(Tenant.owner_user_id == active_demo_user.id)
        )
    ).scalar_one()
    settings = await db_session.scalar(
        select(TenantSettings).where(TenantSettings.tenant_id == tenant.id)
    )

    assert response.status_code == 403
    assert settings is None


async def test_demo_guardrail_prevents_whatsapp_external_calls(
    client, active_demo_user
):
    headers = await _login(client, active_demo_user.username, "demo-password")

    with patch(
        "app.api.v1.endpoints.whatsapp_link.service.get_status",
        new=AsyncMock(),
    ) as get_status:
        response = await client.get(
            "/api/v1/tenant/whatsapp-link/status", headers=headers
        )

    assert response.status_code == 403
    assert response.json()["detail"] == "demo_operation_blocked"
    get_status.assert_not_awaited()


async def test_demo_master_export_is_blocked_before_export_service(
    client, db_session, master_user, active_demo_user
):
    tenant = (
        await db_session.execute(
            select(Tenant).where(Tenant.owner_user_id == active_demo_user.id)
        )
    ).scalar_one()
    headers = await _login(client, master_user.username, "master-password")

    with patch(
        "app.services.export_service.get_current_export",
        new=AsyncMock(),
    ) as get_current_export:
        response = await client.get(
            f"/api/v1/tenants/{tenant.id}/export", headers=headers
        )

    assert response.status_code == 403
    assert response.json()["detail"] == "demo_operation_blocked"
    get_current_export.assert_not_awaited()


async def test_demo_production_tenant_mutations_use_stable_guardrail_code(
    client, db_session, master_user, active_demo_user
):
    tenant = (
        await db_session.execute(
            select(Tenant).where(Tenant.owner_user_id == active_demo_user.id)
        )
    ).scalar_one()
    headers = await _login(client, master_user.username, "master-password")

    update = await client.put(
        f"/api/v1/tenants/{tenant.id}",
        headers=headers,
        json={"full_name": "Should not persist"},
    )
    deactivate = await client.patch(
        f"/api/v1/tenants/{tenant.id}/deactivate", headers=headers
    )
    delete = await client.post(
        f"/api/v1/tenants/{tenant.id}/delete",
        headers=headers,
        json={"password": "master-password", "destructive_word": "DELETE"},
    )

    assert [response.status_code for response in (update, deactivate, delete)] == [
        403,
        403,
        403,
    ]
    assert all(
        response.json()["detail"] == "demo_operation_blocked"
        for response in (update, deactivate, delete)
    )


async def test_demo_n8n_lookup_is_rejected_before_mailbox_or_queue(
    client, db_session, active_demo_user, monkeypatch
):
    from app.core.config import settings

    tenant = (
        await db_session.execute(
            select(Tenant).where(Tenant.owner_user_id == active_demo_user.id)
        )
    ).scalar_one()
    monkeypatch.setattr(settings, "n8n_api_key", "test-n8n-key")

    with (
        patch(
            "app.api.v1.endpoints.integrations.mail_lookups.mailbox_config_repository.get_by_tenant",
            new=AsyncMock(),
        ) as get_mailbox,
        patch(
            "app.api.v1.endpoints.integrations.mail_lookups.enqueue_job",
            new=AsyncMock(),
        ) as enqueue_job,
    ):
        response = await client.post(
            "/api/v1/integrations/n8n/mail/lookups",
            headers={"X-API-Key": "test-n8n-key"},
            json={
                "tenant_id": str(tenant.id),
                "service_key": "generic",
                "target_email": "prospect@example.com",
            },
        )

    assert response.status_code == 403
    assert response.json()["detail"] == "demo_operation_blocked"
    get_mailbox.assert_not_awaited()
    enqueue_job.assert_not_awaited()


async def test_demo_self_deletion_is_blocked_before_cleanup(client, active_demo_user):
    headers = await _login(client, active_demo_user.username, "demo-password")

    response = await client.post(
        "/api/v1/me/delete-account",
        headers=headers,
        json={"password": "demo-password", "destructive_word": "DELETE"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "demo_operation_blocked"


async def test_demo_guardrail_logs_only_safe_context(client, active_demo_user, caplog):
    headers = await _login(client, active_demo_user.username, "demo-password")

    with caplog.at_level(logging.INFO, logger="app.core.demo_guardrail"):
        response = await client.get("/api/v1/dashboard", headers=headers)

    messages = [record.getMessage() for record in caplog.records]
    combined = " ".join(messages)
    assert response.status_code == 403
    assert "operation=authenticated_endpoint" in combined
    assert "tenant=" in combined
    assert "demo-password" not in combined


async def test_demo_public_catalog_is_rejected_with_stable_code(
    client, db_session, active_demo_user
):
    tenant = (
        await db_session.execute(
            select(Tenant).where(Tenant.owner_user_id == active_demo_user.id)
        )
    ).scalar_one()
    db_session.add(
        TenantApiKey(
            tenant_id=tenant.id,
            api_key="tpk_demo_guardrail",
            allowed_origins=["https://example.com"],
        )
    )
    await db_session.commit()

    response = await client.get(
        "/api/v1/public/catalog?api_key=tpk_demo_guardrail",
        headers={"Origin": "https://example.com"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "demo_operation_blocked"
