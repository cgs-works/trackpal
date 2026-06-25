from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.models import Tenant

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
