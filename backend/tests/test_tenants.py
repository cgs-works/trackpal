import pytest

pytestmark = pytest.mark.asyncio


async def _create_tenant(client, auth_headers, **overrides):
    payload = {
        "full_name": "Tenant One",
        "email": "tenant@example.com",
        "phone": "+15550000001",
        "username": "tenant-one",
        "password": "tenant-password",
        "evolution_instance_name": "tenant-one-instance",
    }
    payload.update(overrides)
    return await client.post("/api/v1/tenants/", json=payload, headers=auth_headers)


async def test_create_tenant(client, auth_headers):
    response = await _create_tenant(client, auth_headers)

    assert response.status_code == 201
    data = response.json()
    assert data["full_name"] == "Tenant One"
    assert data["email"] == "tenant@example.com"
    assert data["phone"] == "+15550000001"
    assert data["username"] == "tenant-one"
    assert data["is_active"] is True
    assert data["plain_password"] is None
    assert data["id"]
    assert data["created_at"]


async def test_create_tenant_auto_password(client, auth_headers):
    response = await _create_tenant(
        client,
        auth_headers,
        username="tenant-auto",
        phone="+15550000002",
        password=None,
    )

    assert response.status_code == 201
    data = response.json()
    assert data["plain_password"]
    assert len(data["plain_password"]) >= 6


async def test_create_tenant_duplicate_phone(client, auth_headers, active_tenant_user):
    response = await _create_tenant(
        client,
        auth_headers,
        username="tenant-duplicate-phone",
        phone="+20000000000",
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Phone already registered"


async def test_list_tenants(client, auth_headers, active_tenant_user, deactivated_tenant_user):
    response = await client.get("/api/v1/tenants/", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["meta"] == {"total": 2, "active": 1, "inactive": 1}
    assert len(data["data"]) == 2
    assert {tenant["username"] for tenant in data["data"]} == {
        "tenant",
        "inactive-tenant",
    }


async def test_get_tenant(client, auth_headers, active_tenant_user):
    response = await client.get(
        f"/api/v1/tenants/{active_tenant_user.id}", headers=auth_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(active_tenant_user.id)
    assert data["full_name"] == "Active Tenant"
    assert data["username"] == "tenant"


async def test_update_tenant(client, auth_headers, active_tenant_user):
    response = await client.put(
        f"/api/v1/tenants/{active_tenant_user.id}",
        json={
            "full_name": "Updated Tenant",
            "email": "updated@example.com",
            "phone": "+15550000003",
            "evolution_instance_name": "updated-instance",
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["full_name"] == "Updated Tenant"
    assert data["email"] == "updated@example.com"
    assert data["phone"] == "+15550000003"
    assert data["evolution_instance_name"] == "updated-instance"


async def test_deactivate_tenant(client, auth_headers, active_tenant_user):
    response = await client.patch(
        f"/api/v1/tenants/{active_tenant_user.id}/deactivate", headers=auth_headers
    )

    assert response.status_code == 200
    assert response.json()["is_active"] is False


async def test_activate_tenant(client, auth_headers, deactivated_tenant_user):
    response = await client.patch(
        f"/api/v1/tenants/{deactivated_tenant_user.id}/activate", headers=auth_headers
    )

    assert response.status_code == 200
    assert response.json()["is_active"] is True


async def test_delete_tenant_inactive_only(client, auth_headers, deactivated_tenant_user):
    response = await client.delete(
        f"/api/v1/tenants/{deactivated_tenant_user.id}", headers=auth_headers
    )

    assert response.status_code == 204

    get_response = await client.get(
        f"/api/v1/tenants/{deactivated_tenant_user.id}", headers=auth_headers
    )
    assert get_response.status_code == 404


async def test_delete_active_tenant_fails(client, auth_headers, active_tenant_user):
    response = await client.delete(
        f"/api/v1/tenants/{active_tenant_user.id}", headers=auth_headers
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Cannot delete active tenant. Deactivate first."


async def test_tenant_endpoints_require_master(client, active_tenant_user):
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"username": "tenant", "password": "tenant-password"},
    )
    headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}

    response = await client.get("/api/v1/tenants/", headers=headers)

    assert response.status_code == 403
