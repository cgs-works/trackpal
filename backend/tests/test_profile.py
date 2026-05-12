import pytest

pytestmark = pytest.mark.asyncio


async def _login(client, username: str, password: str) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/login", json={"username": username, "password": password}
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def test_get_profile_master(client, master_user):
    headers = await _login(client, "master", "master-password")

    response = await client.get("/api/v1/me", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "master"
    assert data["username"] == "master"
    assert data["name"] == "Master User"
    assert data["phone"] == "+10000000000"
    assert data["created_at"] is not None
    assert data["updated_at"] is not None


async def test_get_profile_tenant(client, active_tenant_user):
    headers = await _login(client, "tenant", "tenant-password")

    response = await client.get("/api/v1/me", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "tenant"
    assert data["username"] == "tenant"
    assert data["full_name"] == "Active Tenant"
    assert data["phone"] == "+20000000000"
    assert data["is_active"] is True


async def test_update_profile_phone_conflict(client, master_user, active_tenant_user):
    master_headers = await _login(client, "master", "master-password")

    # Try to update master's phone to tenant's existing phone
    response = await client.put(
        "/api/v1/me",
        json={"phone": "+20000000000"},
        headers=master_headers,
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Phone already registered"


async def test_update_profile_phone_same_value(client, master_user):
    master_headers = await _login(client, "master", "master-password")

    # Update with same phone (no conflict)
    response = await client.put(
        "/api/v1/me",
        json={"phone": "+10000000000"},
        headers=master_headers,
    )

    assert response.status_code == 200
    assert response.json()["phone"] == "+10000000000"


async def test_update_profile(client, master_user, active_tenant_user):
    master_headers = await _login(client, "master", "master-password")
    tenant_headers = await _login(client, "tenant", "tenant-password")

    master_response = await client.put(
        "/api/v1/me", json={"name": "Updated Master"}, headers=master_headers
    )
    tenant_response = await client.put(
        "/api/v1/me", json={"full_name": "Updated Tenant"}, headers=tenant_headers
    )

    assert master_response.status_code == 200
    assert master_response.json()["name"] == "Updated Master"
    assert tenant_response.status_code == 200
    assert tenant_response.json()["full_name"] == "Updated Tenant"


async def test_change_password(client, active_tenant_user):
    headers = await _login(client, "tenant", "tenant-password")

    response = await client.put(
        "/api/v1/me/password",
        json={"old_password": "tenant-password", "new_password": "new-password"},
        headers=headers,
    )

    assert response.status_code == 200
    new_headers = await _login(client, "tenant", "new-password")
    assert new_headers["Authorization"].startswith("Bearer ")


async def test_change_password_wrong_old(client, active_tenant_user):
    headers = await _login(client, "tenant", "tenant-password")

    response = await client.put(
        "/api/v1/me/password",
        json={"old_password": "wrong-password", "new_password": "new-password"},
        headers=headers,
    )

    assert response.status_code == 400


async def test_dashboard_master(
    client, master_user, active_tenant_user, deactivated_tenant_user
):
    headers = await _login(client, "master", "master-password")

    response = await client.get("/api/v1/dashboard", headers=headers)

    assert response.status_code == 200
    assert response.json() == {
        "total_tenants": 2,
        "active_tenants": 1,
        "inactive_tenants": 1,
    }


async def test_dashboard_tenant(client, active_tenant_user):
    headers = await _login(client, "tenant", "tenant-password")

    response = await client.get("/api/v1/dashboard", headers=headers)

    assert response.status_code == 200
    assert response.json() == {
        "message": "Dashboard en construccion",
        "full_name": "Active Tenant",
        "email": None,
    }
