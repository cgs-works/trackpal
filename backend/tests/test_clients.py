import pytest
from uuid import UUID
from sqlalchemy import select

from app.models import Client, Tenant, User

pytestmark = pytest.mark.asyncio


async def _login_tenant(
    client, username: str = "tenant", password: str = "tenant-password"
) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/login", json={"username": username, "password": password}
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def _create_client(client, headers, **overrides):
    payload = {
        "full_name": "Client One",
        "local_username": "client1",
        "phone": "+12015550030",
        "password": "client-password",
    }
    payload.update(overrides)
    return await client.post("/api/v1/clients", json=payload, headers=headers)


async def _tenant_row(db_session, owner_user_id):
    result = await db_session.execute(
        select(Tenant).where(Tenant.owner_user_id == owner_user_id)
    )
    return result.scalar_one_or_none()


async def test_create_client(client, active_tenant_user):
    headers = await _login_tenant(client)

    response = await _create_client(client, headers)

    assert response.status_code == 201
    data = response.json()
    assert data["full_name"] == "Client One"
    assert data["username"] == "tna01_client1"
    assert data["phone"] == "12015550030"
    assert data["is_active"] is True


async def test_create_client_duplicate_local_username(client, active_tenant_user):
    """UserFacingError on create returns tenant-localized (es) message.

    Locale resolved before service call so post-rollback RLS context loss
    cannot cause fallback to English.
    """
    headers = await _login_tenant(client)
    await client.put("/api/v1/me", json={"locale": "es"}, headers=headers)
    await _create_client(client, headers)

    response = await _create_client(
        client, headers, full_name="Client Two", phone="+12015550031"
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "El nombre de usuario local ya existe"


async def test_create_client_duplicate_phone(client, active_tenant_user):
    headers = await _login_tenant(client)
    await _create_client(client, headers)

    response = await _create_client(
        client,
        headers,
        full_name="Client Two",
        local_username="client2",
        phone="+12015550030",
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Phone already registered"


async def test_create_client_weak_password_rejected(client, active_tenant_user):
    headers = await _login_tenant(client)

    response = await _create_client(client, headers, password="123")

    assert response.status_code == 422


async def test_create_client_empty_password_rejected(client, active_tenant_user):
    headers = await _login_tenant(client)

    response = await _create_client(client, headers, password="")

    assert response.status_code == 422


async def test_list_get_update_client(client, active_tenant_user, db_session):
    headers = await _login_tenant(client)
    create_response = await _create_client(client, headers)
    client_id = create_response.json()["id"]
    old_username = create_response.json()["username"]

    list_response = await client.get("/api/v1/clients", headers=headers)
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    get_response = await client.get(f"/api/v1/clients/{client_id}", headers=headers)
    assert get_response.status_code == 200

    update_response = await client.put(
        f"/api/v1/clients/{client_id}",
        json={
            "full_name": "Client One Updated",
            "local_username": "clientx",
            "phone": "+12015550032",
        },
        headers=headers,
    )

    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["full_name"] == "Client One Updated"
    assert updated["username"] == "tna01_clientx"

    result = await db_session.execute(
        select(User).where(User.username == "tna01_clientx")
    )
    assert result.scalar_one_or_none() is not None


async def test_local_username_update_syncs_login_username(client, active_tenant_user):
    headers = await _login_tenant(client)
    create_response = await _create_client(client, headers)
    client_id = create_response.json()["id"]
    old_username = create_response.json()["username"]

    response = await client.put(
        f"/api/v1/clients/{client_id}",
        json={"local_username": "clientz"},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["username"] == "tna01_clientz"

    old_login = await client.post(
        "/api/v1/auth/login",
        json={"username": old_username, "password": "client-password"},
    )
    new_login = await client.post(
        "/api/v1/auth/login",
        json={"username": "tna01_clientz", "password": "client-password"},
    )

    assert old_login.status_code == 401
    assert new_login.status_code == 200


async def test_prefix_update_syncs_client_usernames(
    client, active_tenant_user, auth_headers, db_session
):
    headers = await _login_tenant(client)
    create_response = await _create_client(client, headers)
    client_id = create_response.json()["id"]
    old_username = create_response.json()["username"]

    update_tenant_response = await client.put(
        f"/api/v1/tenants/{active_tenant_user.id}",
        json={"client_prefix": "z9"},
        headers=auth_headers,
    )

    assert update_tenant_response.status_code == 200
    assert update_tenant_response.json()["client_prefix"] == "z9"

    get_response = await client.get(f"/api/v1/clients/{client_id}", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["username"] == "z9_client1"

    old_login = await client.post(
        "/api/v1/auth/login",
        json={"username": old_username, "password": "client-password"},
    )
    new_login = await client.post(
        "/api/v1/auth/login",
        json={"username": "z9_client1", "password": "client-password"},
    )

    assert old_login.status_code == 401
    assert new_login.status_code == 200

    result = await db_session.execute(select(User).where(User.username == "z9_client1"))
    assert result.scalar_one_or_none() is not None


async def test_prefix_update_syncs_inactive_tenant_client_usernames(
    client, active_tenant_user, auth_headers, db_session
):
    headers = await _login_tenant(client)
    create_response = await _create_client(client, headers)
    client_id = create_response.json()["id"]
    old_username = create_response.json()["username"]

    deactivate_response = await client.patch(
        f"/api/v1/tenants/{active_tenant_user.id}/deactivate",
        headers=auth_headers,
    )
    assert deactivate_response.status_code == 200

    update_tenant_response = await client.put(
        f"/api/v1/tenants/{active_tenant_user.id}",
        json={"client_prefix": "z8"},
        headers=auth_headers,
    )

    assert update_tenant_response.status_code == 200
    assert update_tenant_response.json()["client_prefix"] == "z8"
    result = await db_session.execute(select(User).where(User.username == "z8_client1"))
    assert result.scalar_one_or_none() is not None


async def test_deactivate_delete_client_removes_user(client, active_tenant_user):
    headers = await _login_tenant(client)
    create_response = await _create_client(client, headers)
    client_id = create_response.json()["id"]

    deactivate_response = await client.patch(
        f"/api/v1/clients/{client_id}/deactivate", headers=headers
    )
    assert deactivate_response.status_code == 200
    assert deactivate_response.json()["is_active"] is False

    delete_response = await client.delete(
        f"/api/v1/clients/{client_id}", headers=headers
    )
    assert delete_response.status_code == 204

    get_response = await client.get(f"/api/v1/clients/{client_id}", headers=headers)
    assert get_response.status_code == 404


async def test_delete_active_client_forbidden(client, active_tenant_user):
    headers = await _login_tenant(client)
    create_response = await _create_client(client, headers)
    client_id = create_response.json()["id"]

    delete_response = await client.delete(
        f"/api/v1/clients/{client_id}", headers=headers
    )
    assert delete_response.status_code == 403


async def test_cross_tenant_client_access_blocked(
    client, auth_headers, active_tenant_user
):
    tenant_headers = await _login_tenant(client)
    create_response = await _create_client(client, tenant_headers)

    other_tenant_response = await client.post(
        "/api/v1/tenants/",
        json={
            "full_name": "Tenant Two",
            "email": "tenant2@example.com",
            "phone": "+12015550040",
            "username": "tenant_two",
            "password": "tenant-password",
            "evolution_instance_name": "tenant-two-instance",
            "client_prefix": "x9",
        },
        headers=auth_headers,
    )
    assert other_tenant_response.status_code == 201

    other_tenant_id = other_tenant_response.json()["id"]
    other_headers = await client.post(
        "/api/v1/auth/login",
        json={"username": "tenant_two", "password": "tenant-password"},
    )
    assert other_headers.status_code == 200
    other_token = other_headers.json()["access_token"]

    response = await client.get(
        f"/api/v1/clients/{create_response.json()['id']}",
        headers={"Authorization": f"Bearer {other_token}"},
    )

    assert response.status_code == 404


async def test_client_cannot_access_catalog_management(client, active_client_user):
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": active_client_user.username, "password": "client-password"},
    )
    token = response.json()["access_token"]

    catalog_response = await client.get(
        "/api/v1/catalog/services",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert catalog_response.status_code == 403


async def test_tenant_delete_removes_client_users(
    client, active_tenant_user, auth_headers, db_session
):
    headers = await _login_tenant(client)
    create_response = await _create_client(client, headers)
    client_user_id = UUID(create_response.json()["owner_user_id"])
    client_id = UUID(create_response.json()["id"])

    await client.patch(
        f"/api/v1/tenants/{active_tenant_user.id}/deactivate",
        headers=auth_headers,
    )

    delete_response = await client.delete(
        f"/api/v1/tenants/{active_tenant_user.id}", headers=auth_headers
    )
    assert delete_response.status_code == 204

    result = await db_session.execute(select(User).where(User.id == client_user_id))
    assert result.scalar_one_or_none() is None

    client_row = await db_session.execute(select(Client).where(Client.id == client_id))
    assert client_row.scalar_one_or_none() is None


async def test_master_cannot_manage_clients(client, auth_headers):
    response = await client.get("/api/v1/clients", headers=auth_headers)

    assert response.status_code == 403


async def test_master_cannot_create_clients(client, auth_headers):
    response = await client.post(
        "/api/v1/clients",
        json={
            "full_name": "Client One",
            "local_username": "client1",
            "phone": "+12015550030",
            "password": "client-password",
        },
        headers=auth_headers,
    )

    assert response.status_code == 403


async def test_update_client_duplicate_local_username_spanish(
    client, active_tenant_user
):
    """UserFacingError on update returns tenant-localized (es) message.

    Locale resolved before service call, so IntegrityError rollback in
    service cannot clear RLS context before locale is consumed.
    """
    headers = await _login_tenant(client)
    await client.put("/api/v1/me", json={"locale": "es"}, headers=headers)

    # Create client A
    resp_a = await _create_client(
        client, headers, local_username="client_a", phone="+12015550030"
    )
    assert resp_a.status_code == 201
    client_a_id = resp_a.json()["id"]

    # Create client B with different local_username
    resp_b = await _create_client(
        client,
        headers,
        local_username="client_b",
        full_name="Client B",
        phone="+12015550031",
    )
    assert resp_b.status_code == 201

    # Try to update client A's local_username to client B's — triggers UserFacingError
    response = await client.put(
        f"/api/v1/clients/{client_a_id}",
        json={"local_username": "client_b"},
        headers=headers,
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "El nombre de usuario local ya existe"


async def test_delete_client_active_spanish(client, active_tenant_user):
    """UserFacingError on delete (active client) returns tenant-localized (es) message."""
    headers = await _login_tenant(client)
    await client.put("/api/v1/me", json={"locale": "es"}, headers=headers)

    create_resp = await _create_client(client, headers)
    client_id = create_resp.json()["id"]

    response = await client.delete(f"/api/v1/clients/{client_id}", headers=headers)

    assert response.status_code == 403
    assert (
        response.json()["detail"]
        == "No se puede eliminar un cliente activo. Desactívalo primero."
    )
