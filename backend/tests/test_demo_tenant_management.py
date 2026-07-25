from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
from sqlalchemy import select

from app.core.security import verify_password
from app.models import RefreshSession, Tenant, TenantSettings, User

pytestmark = pytest.mark.asyncio


async def _master_headers(client, master_user) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "master", "password": "master-password"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def _create_demo(client, headers, *, name="Acme Demo", plan="starter"):
    return await client.post(
        "/api/v1/demos/",
        json={"name": name, "plan": plan},
        headers=headers,
    )


async def _demo_by_name(db_session, name: str) -> tuple[User, Tenant]:
    result = await db_session.execute(
        select(User, Tenant)
        .join(Tenant, Tenant.owner_user_id == User.id)
        .where(Tenant.name == name)
    )
    row = result.one()
    return row[0], row[1]


async def test_master_can_create_demo_with_one_time_credentials_and_no_business_rows(
    client, db_session, master_user
):
    headers = await _master_headers(client, master_user)

    response = await _create_demo(client, headers, plan="pro")

    assert response.status_code == 201, response.text
    data = response.json()
    assert data["name"] == "Acme Demo"
    assert data["plan"] == "pro"
    assert data["status"] == "pending"
    assert re.fullmatch(r"[a-z][a-z0-9_]{0,19}", data["username"])
    assert len(data["plain_password"]) >= 24
    assert data["demo_activated_at"] is None
    assert data["demo_expires_at"] is None
    assert data["remaining_seconds"] is None
    assert set(data) == {
        "id",
        "name",
        "plan",
        "status",
        "username",
        "plain_password",
        "created_at",
        "demo_activated_at",
        "demo_expires_at",
        "server_time",
        "remaining_seconds",
    }

    user, tenant = await _demo_by_name(db_session, "Acme Demo")
    assert tenant.is_demo is True
    assert tenant.is_active is True
    assert tenant.email is None
    assert tenant.whatsapp_phone is None
    assert tenant.evolution_instance_name is None
    assert tenant.evolution_instance_token is None
    assert verify_password(data["plain_password"], user.password_hash)
    assert data["plain_password"] not in user.password_hash
    settings = await db_session.get(TenantSettings, tenant.id)
    assert settings is None


async def test_demo_creation_requires_only_name_and_explicit_valid_plan(
    client, master_user
):
    headers = await _master_headers(client, master_user)

    missing_plan = await client.post(
        "/api/v1/demos/", json={"name": "Missing Plan"}, headers=headers
    )
    invalid_plan = await client.post(
        "/api/v1/demos/",
        json={"name": "Invalid Plan", "plan": "enterprise"},
        headers=headers,
    )
    extra_field = await client.post(
        "/api/v1/demos/",
        json={"name": "Extra Field", "plan": "starter", "email": "x@example.com"},
        headers=headers,
    )
    invalid_name = await client.post(
        "/api/v1/demos/", json={"name": " name", "plan": "starter"}, headers=headers
    )

    assert missing_plan.status_code == 422
    assert invalid_plan.status_code == 422
    assert extra_field.status_code == 422
    assert invalid_name.status_code == 422


async def test_demo_list_is_lifecycle_only_and_excludes_production(
    client, db_session, master_user, active_tenant_user
):
    headers = await _master_headers(client, master_user)
    created = await _create_demo(client, headers)
    assert created.status_code == 201
    user, tenant = await _demo_by_name(db_session, "Acme Demo")
    activated_at = datetime.now(timezone.utc) - timedelta(hours=2)
    tenant.demo_activated_at = activated_at
    tenant.demo_expires_at = activated_at + timedelta(hours=48)
    await db_session.commit()

    response = await client.get("/api/v1/demos/", headers=headers)

    assert response.status_code == 200, response.text
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == str(tenant.id)
    assert data[0]["username"] == user.username
    assert data[0]["status"] == "active"
    assert data[0]["remaining_seconds"] is not None
    assert set(data[0]) == {
        "id",
        "name",
        "plan",
        "status",
        "username",
        "created_at",
        "demo_activated_at",
        "demo_expires_at",
        "server_time",
        "remaining_seconds",
    }


async def test_demo_password_replacement_revokes_sessions_and_preserves_window(
    client, db_session, master_user
):
    master_headers = await _master_headers(client, master_user)
    created = await _create_demo(client, master_headers)
    assert created.status_code == 201
    old_password = created.json()["plain_password"]
    username = created.json()["username"]

    login = await client.post(
        "/api/v1/auth/login", json={"username": username, "password": old_password}
    )
    assert login.status_code == 200
    old_refresh = login.json()["refresh_token"]
    user, tenant = await _demo_by_name(db_session, "Acme Demo")
    activated_at = tenant.demo_activated_at
    expires_at = tenant.demo_expires_at

    replaced = await client.post(
        f"/api/v1/demos/{tenant.id}/credentials", headers=master_headers
    )

    assert replaced.status_code == 200, replaced.text
    data = replaced.json()
    assert data["plain_password"] != old_password
    assert (
        data["demo_activated_at"].replace("+00:00", "").replace("Z", "")
        == activated_at.isoformat()
    )
    assert (
        data["demo_expires_at"].replace("+00:00", "").replace("Z", "")
        == expires_at.isoformat()
    )
    old_refresh_response = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": old_refresh}
    )
    assert old_refresh_response.status_code == 401
    assert old_refresh_response.json()["detail"] == "demo_credentials_replaced"

    new_login = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": data["plain_password"]},
    )
    assert (
        new_login.json()["demo_expires_at"].replace("+00:00", "").replace("Z", "")
        == expires_at.isoformat()
    )

    session_count = await db_session.execute(
        select(RefreshSession).where(RefreshSession.user_id == user.id)
    )
    sessions = list(session_count.scalars())
    assert sessions
    assert any(session.revoked for session in sessions)
    assert any(not session.revoked for session in sessions)


@pytest.mark.parametrize("status", ["pending", "active", "expired"])
async def test_demo_delete_is_idempotent_for_every_lifecycle_state(
    client, db_session, master_user, status
):
    headers = await _master_headers(client, master_user)
    created = await _create_demo(client, headers, name=f"{status.title()} Demo")
    assert created.status_code == 201
    _, tenant = await _demo_by_name(db_session, f"{status.title()} Demo")
    demo_id = tenant.id
    owner_id = tenant.owner_user_id
    if status != "pending":
        activated_at = datetime.now(timezone.utc) - timedelta(
            hours=1 if status == "active" else 49
        )
        tenant.demo_activated_at = activated_at
        tenant.demo_expires_at = activated_at + timedelta(hours=48)
        await db_session.commit()

    first = await client.delete(f"/api/v1/demos/{demo_id}", headers=headers)
    second = await client.delete(f"/api/v1/demos/{demo_id}", headers=headers)

    assert first.status_code == 204
    assert second.status_code == 204
    db_session.expire_all()
    assert await db_session.get(Tenant, demo_id) is None
    assert await db_session.get(User, owner_id) is None


async def test_production_mutation_routes_cannot_change_or_deactivate_demo(
    client, db_session, master_user
):
    headers = await _master_headers(client, master_user)
    created = await _create_demo(client, headers)
    assert created.status_code == 201
    tenant_id = created.json()["id"]

    update = await client.put(
        f"/api/v1/tenants/{tenant_id}",
        json={"full_name": "Changed", "plan": "pro"},
        headers=headers,
    )
    deactivate = await client.patch(
        f"/api/v1/tenants/{tenant_id}/deactivate", headers=headers
    )

    assert update.status_code == 409
    assert deactivate.status_code == 409
    tenant = await db_session.get(Tenant, UUID(tenant_id))
    assert tenant.name == "Acme Demo"
    assert tenant.plan == "starter"
    assert tenant.is_active is True


async def test_demo_management_is_master_only(client, active_tenant_user):
    login = await client.post(
        "/api/v1/auth/login",
        json={"username": "tenant", "password": "tenant-password"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = await client.get("/api/v1/demos/", headers=headers)

    assert response.status_code == 403


async def test_openapi_documents_demo_management_contract(client):
    openapi = (await client.get("/openapi.json")).json()

    assert "/api/v1/demos/" in openapi["paths"]
    assert "/api/v1/demos/{demo_id}" in openapi["paths"]
    assert "/api/v1/demos/{demo_id}/credentials" in openapi["paths"]
