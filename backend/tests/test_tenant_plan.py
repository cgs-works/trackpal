from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.core.security import get_password_hash
from app.models import Client, Tenant, TenantSettings, User

pytestmark = pytest.mark.asyncio


async def _create_tenant(client, auth_headers, **overrides):
    payload = {
        "full_name": "Plan Tenant",
        "email": "plan@example.com",
        "phone": "+12015550100",
        "username": "plan_tenant",
        "password": "tenant-password",
        "evolution_instance_name": "plan-tenant-instance",
        "plan": "starter",
    }
    payload.update(overrides)
    return await client.post("/api/v1/tenants/", json=payload, headers=auth_headers)


async def test_create_tenant_requires_plan(client, auth_headers):
    response = await _create_tenant(client, auth_headers, plan=None)
    assert response.status_code == 422
    assert "plan" in response.text.lower()


async def test_create_tenant_accepts_starter_plan(client, auth_headers, db_session):
    response = await _create_tenant(client, auth_headers)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["plan"] == "starter"

    row = await db_session.execute(select(Tenant).where(Tenant.id == uuid.UUID(body["id"])))
    tenant = row.scalar_one()
    assert tenant.plan == "starter"


async def test_update_tenant_preserves_plan_when_omitted(client, auth_headers):
    created = await _create_tenant(client, auth_headers, username="preserve_plan", phone="+12015550101", plan="pro")
    assert created.status_code == 201, created.text
    tenant_id = created.json()["id"]

    updated = await client.put(
        f"/api/v1/tenants/{tenant_id}",
        json={"full_name": "Renamed Tenant"},
        headers=auth_headers,
    )

    assert updated.status_code == 200, updated.text
    assert updated.json()["full_name"] == "Renamed Tenant"
    assert updated.json()["plan"] == "pro"


async def test_update_tenant_can_change_plan(client, auth_headers):
    created = await _create_tenant(client, auth_headers, username="change_plan", phone="+12015550102", plan="pro")
    assert created.status_code == 201, created.text

    updated = await client.put(
        f"/api/v1/tenants/{created.json()['id']}",
        json={"plan": "starter"},
        headers=auth_headers,
    )

    assert updated.status_code == 200, updated.text
    assert updated.json()["plan"] == "starter"


async def test_list_tenants_includes_plan(client, auth_headers, active_tenant_user):
    response = await client.get("/api/v1/tenants/", headers=auth_headers)
    assert response.status_code == 200, response.text
    assert response.json()["data"][0]["plan"] == "pro"


# ── Task 2: Auth responses, client auth block, Pro gate ──────────────────


async def _login(client, username: str, password: str) -> dict:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()


async def test_auth_responses_include_tenant_plan(client, auth_headers, active_tenant_user):
    tenant_login = await _login(client, "tenant", "tenant-password")
    assert tenant_login["tenant_plan"] == "pro"

    master_login = await _login(client, "master", "master-password")
    assert master_login["tenant_plan"] is None

    switch = await client.post(
        "/api/v1/auth/switch-tenant",
        json={"tenant_id": tenant_login["active_tenant_id"]},
        headers={"Authorization": f"Bearer {master_login['access_token']}"},
    )
    assert switch.status_code == 200, switch.text
    assert switch.json()["tenant_plan"] == "pro"


async def test_starter_tenant_gets_404_for_pro_endpoints(client, auth_headers, active_tenant_user):
    tenant = await client.put(
        f"/api/v1/tenants/{active_tenant_user.id}",
        json={"plan": "starter"},
        headers=auth_headers,
    )
    assert tenant.status_code == 200, tenant.text

    login = await _login(client, "tenant", "tenant-password")
    headers = {"Authorization": f"Bearer {login['access_token']}"}

    for path in ("/api/v1/clients", "/api/v1/catalog/services", "/api/v1/subscriptions", "/api/v1/subscription-settings"):
        response = await client.get(path, headers=headers)
        assert response.status_code == 404, path + response.text


async def test_master_switched_into_starter_bypasses_pro_gate(client, auth_headers, active_tenant_user):
    response = await client.put(
        f"/api/v1/tenants/{active_tenant_user.id}",
        json={"plan": "starter"},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text

    switched = await client.post(
        "/api/v1/auth/switch-tenant",
        json={"tenant_id": response.json()["id"]},
        headers=auth_headers,
    )
    assert switched.status_code == 200, switched.text
    headers = {"Authorization": f"Bearer {switched.json()['access_token']}"}

    pro_endpoint = await client.get("/api/v1/clients", headers=headers)
    assert pro_endpoint.status_code == 200, pro_endpoint.text


async def test_client_login_under_starter_returns_generic_401(client, db_session, auth_headers, active_tenant_user):
    result = await db_session.execute(select(Tenant).where(Tenant.owner_user_id == active_tenant_user.id))
    tenant = result.scalar_one()
    client_user = User(
        username=f"{tenant.client_prefix}_starter_client",
        password_hash=get_password_hash("client-password"),
        role="client",
    )
    db_session.add(client_user)
    await db_session.flush()
    db_session.add(
        Client(
            tenant_id=tenant.id,
            owner_user_id=client_user.id,
            full_name="Starter Client",
            username=client_user.username,
            phone="12015550199",
            is_active=True,
        )
    )
    await db_session.commit()

    changed = await client.put(
        f"/api/v1/tenants/{active_tenant_user.id}",
        json={"plan": "starter"},
        headers=auth_headers,
    )
    assert changed.status_code == 200, changed.text

    login = await client.post(
        "/api/v1/auth/login",
        json={"username": client_user.username, "password": "client-password"},
    )
    assert login.status_code == 401
    assert login.json()["detail"] == "Invalid credentials or account deactivated"
