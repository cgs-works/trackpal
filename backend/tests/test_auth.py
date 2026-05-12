import pytest

from app.core.config import settings

pytestmark = pytest.mark.asyncio


async def test_login_success(client, master_user):
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "master", "password": "master-password"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["token_type"] == "bearer"
    assert body["user"]["username"] == master_user.username
    assert body["user"]["role"] == "master"


async def test_login_invalid_password(client, master_user):
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "master", "password": "wrong-password"},
    )

    assert response.status_code == 401


async def test_login_deactivated_tenant(client, deactivated_tenant_user):
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "inactive-tenant", "password": "tenant-password"},
    )

    assert response.status_code == 401


async def test_refresh_token(client, master_user):
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"username": "master", "password": "master-password"},
    )
    refresh_token = login_response.json()["refresh_token"]

    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )

    assert response.status_code == 200
    assert response.json()["access_token"]
    assert response.json()["refresh_token"]


async def test_refresh_token_rotation(client, master_user):
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"username": "master", "password": "master-password"},
    )
    old_refresh_token = login_response.json()["refresh_token"]

    first_refresh = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": old_refresh_token},
    )
    second_refresh = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": old_refresh_token},
    )

    assert first_refresh.status_code == 200
    assert second_refresh.status_code == 401


async def test_logout(client, master_user):
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"username": "master", "password": "master-password"},
    )
    refresh_token = login_response.json()["refresh_token"]

    logout_response = await client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refresh_token},
    )
    refresh_response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )

    assert logout_response.status_code == 204
    assert refresh_response.status_code == 401


async def test_identify_by_phone(client, master_user):
    response = await client.get(
        "/api/v1/integrations/n8n/identify",
        params={"phone": "+10000000000"},
        headers={"X-API-Key": settings.n8n_api_key},
    )

    assert response.status_code == 200
    assert response.json()["username"] == "master"
    assert response.json()["role"] == "master"


async def test_identify_no_phone(client, master_user):
    response = await client.get(
        "/api/v1/integrations/n8n/identify",
        params={"phone": "+99999999999"},
        headers={"X-API-Key": settings.n8n_api_key},
    )

    assert response.status_code == 404


async def test_identify_invalid_api_key(client, master_user):
    response = await client.get(
        "/api/v1/integrations/n8n/identify",
        params={"phone": "+10000000000"},
        headers={"X-API-Key": "wrong-key"},
    )

    assert response.status_code == 401


async def test_refresh_token_as_bearer_fails(client, master_user):
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"username": "master", "password": "master-password"},
    )
    refresh_token = login_response.json()["refresh_token"]

    response = await client.get(
        "/api/v1/tenants/",
        headers={"Authorization": f"Bearer {refresh_token}"},
    )

    assert response.status_code == 401


async def test_deactivated_tenant_old_access_token_fails(
    client, active_tenant_user, auth_headers
):
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"username": "tenant", "password": "tenant-password"},
    )
    old_access_token = login_response.json()["access_token"]

    # Deactivate the tenant
    await client.patch(
        f"/api/v1/tenants/{active_tenant_user.id}/deactivate",
        headers=auth_headers,
    )

    # Old access token should be rejected
    response = await client.get(
        "/api/v1/me",
        headers={"Authorization": f"Bearer {old_access_token}"},
    )

    assert response.status_code == 401


async def test_deactivated_tenant_old_refresh_token_fails(
    client, active_tenant_user, auth_headers
):
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"username": "tenant", "password": "tenant-password"},
    )
    old_refresh_token = login_response.json()["refresh_token"]

    # Deactivate the tenant
    await client.patch(
        f"/api/v1/tenants/{active_tenant_user.id}/deactivate",
        headers=auth_headers,
    )

    # Old refresh token should be rejected
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": old_refresh_token},
    )

    assert response.status_code == 401


async def test_identify_deactivated_tenant(client, deactivated_tenant_user):
    response = await client.get(
        "/api/v1/integrations/n8n/identify",
        params={"phone": "+30000000000"},
        headers={"X-API-Key": settings.n8n_api_key},
    )

    assert response.status_code == 404
