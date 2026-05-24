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
    assert data["phone"] == "+12015550001"
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
    assert data["phone"] == "+12015550002"
    assert data["is_active"] is True


async def test_get_profile_client(client, active_client_user):
    headers = await _login(client, active_client_user.username, "client-password")

    response = await client.get("/api/v1/me", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "client"
    assert data["username"] == active_client_user.username
    assert data["client_prefix"] == "tna01"
    assert data["tenant_name"] == "Active Tenant"


async def test_update_profile_phone_conflict(client, master_user, active_tenant_user):
    master_headers = await _login(client, "master", "master-password")

    # Try to update master's phone to tenant's existing phone
    response = await client.put(
        "/api/v1/me",
        json={"phone": "+12015550002"},
        headers=master_headers,
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Phone already registered"


async def test_update_profile_phone_same_value(client, master_user):
    master_headers = await _login(client, "master", "master-password")

    # Update with same phone (no conflict)
    response = await client.put(
        "/api/v1/me",
        json={"phone": "+12015550001"},
        headers=master_headers,
    )

    assert response.status_code == 200
    assert response.json()["phone"] == "12015550001"  # canonical: no + prefix


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


async def test_update_profile_client_forbidden(client, active_client_user):
    headers = await _login(client, active_client_user.username, "client-password")

    response = await client.put(
        "/api/v1/me",
        json={"full_name": "New Client"},
        headers=headers,
    )

    assert response.status_code == 403


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


async def test_change_password_client(client, active_client_user):
    headers = await _login(client, active_client_user.username, "client-password")

    response = await client.put(
        "/api/v1/me/password",
        json={"old_password": "client-password", "new_password": "new-client-password"},
        headers=headers,
    )

    assert response.status_code == 200
    new_headers = await _login(client, active_client_user.username, "new-client-password")
    assert new_headers["Authorization"].startswith("Bearer ")


async def test_change_password_client_uses_tenant_locale(client, active_client_user):
    tenant_headers = await _login(client, "tenant", "tenant-password")
    await client.put("/api/v1/me", json={"locale": "es"}, headers=tenant_headers)

    headers = await _login(client, active_client_user.username, "client-password")
    response = await client.put(
        "/api/v1/me/password",
        json={"old_password": "wrong-password", "new_password": "new-client-password"},
        headers=headers,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Contraseña actual incorrecta"


async def test_change_password_client_short_new_password_rejected(client, active_client_user):
    headers = await _login(client, active_client_user.username, "client-password")

    response = await client.put(
        "/api/v1/me/password",
        json={"old_password": "client-password", "new_password": "123"},
        headers=headers,
    )

    assert response.status_code == 422


async def test_change_password_client_empty_new_password_rejected(client, active_client_user):
    headers = await _login(client, active_client_user.username, "client-password")

    response = await client.put(
        "/api/v1/me/password",
        json={"old_password": "client-password", "new_password": ""},
        headers=headers,
    )

    assert response.status_code == 422


async def test_change_password_wrong_old(client, active_tenant_user):
    headers = await _login(client, "tenant", "tenant-password")

    response = await client.put(
        "/api/v1/me/password",
        json={"old_password": "wrong-password", "new_password": "new-password"},
        headers=headers,
    )

    assert response.status_code == 400


async def test_update_profile_phone_is_canonical(client, master_user, db_session):
    """Updated profile phone stored canonical without + prefix."""
    from uuid import UUID
    master_headers = await _login(client, "master", "master-password")

    response = await client.put(
        "/api/v1/me",
        json={"phone": "+12015550012"},
        headers=master_headers,
    )

    assert response.status_code == 200
    assert response.json()["phone"] == "12015550012"

    from app.models import MasterProfile
    from sqlalchemy import select
    result = await db_session.execute(
        select(MasterProfile).where(MasterProfile.id == UUID(str(master_user.id)))
    )
    profile = result.scalar_one_or_none()
    assert profile.phone == "12015550012"


async def test_update_profile_phone_jid_becomes_canonical(client, master_user, db_session):
    """JID-style phone input stored canonical."""
    from uuid import UUID
    master_headers = await _login(client, "master", "master-password")

    response = await client.put(
        "/api/v1/me",
        json={"phone": "+12015550013@s.whatsapp.net"},
        headers=master_headers,
    )

    assert response.status_code == 200
    assert response.json()["phone"] == "12015550013"

    from app.models import MasterProfile
    from sqlalchemy import select
    result = await db_session.execute(
        select(MasterProfile).where(MasterProfile.id == UUID(str(master_user.id)))
    )
    profile = result.scalar_one_or_none()
    assert profile.phone == "12015550013"


# ===========================================================================
# Phase 2: Validation policy integration tests
# ===========================================================================


async def test_update_profile_invalid_email(client, master_user):
    headers = await _login(client, "master", "master-password")

    response = await client.put(
        "/api/v1/me",
        json={"email": "not-an-email"},
        headers=headers,
    )

    assert response.status_code == 422


async def test_update_profile_invalid_phone(client, master_user):
    headers = await _login(client, "master", "master-password")

    response = await client.put(
        "/api/v1/me",
        json={"phone": "abc"},
        headers=headers,
    )

    assert response.status_code == 422


async def test_update_profile_invalid_full_name_leading_space(client, master_user):
    headers = await _login(client, "master", "master-password")

    response = await client.put(
        "/api/v1/me",
        json={"full_name": " Leading"},
        headers=headers,
    )

    assert response.status_code == 422


async def test_update_profile_invalid_full_name_trailing_space(client, master_user):
    headers = await _login(client, "master", "master-password")

    response = await client.put(
        "/api/v1/me",
        json={"full_name": "Trailing "},
        headers=headers,
    )

    assert response.status_code == 422


async def test_update_profile_invalid_name_leading_space(client, master_user):
    """Master 'name' field also rejects leading space."""
    headers = await _login(client, "master", "master-password")

    response = await client.put(
        "/api/v1/me",
        json={"name": " Leading"},
        headers=headers,
    )

    assert response.status_code == 422


async def test_update_profile_email_normalized(client, active_tenant_user):
    """Email domain lowercased when updating tenant profile."""
    headers = await _login(client, "tenant", "tenant-password")

    response = await client.put(
        "/api/v1/me",
        json={"email": "User@Example.COM"},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["email"] == "User@example.com"


async def test_update_profile_full_name_collapsed(client, active_tenant_user):
    """Multiple internal spaces collapsed when updating tenant profile."""
    headers = await _login(client, "tenant", "tenant-password")

    response = await client.put(
        "/api/v1/me",
        json={"full_name": "John   Smith"},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["full_name"] == "John Smith"


async def test_update_profile_name_valid(client, master_user):
    """Master 'name' field accepts valid names."""
    headers = await _login(client, "master", "master-password")

    response = await client.put(
        "/api/v1/me",
        json={"name": "Juan Pérez"},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Juan Pérez"


async def test_update_profile_phone_conflict_normalized(
    client, master_user, active_tenant_user, db_session
):
    """Phone conflict detected regardless of + prefix in input.

    Existing tenant phone is stored with + in fixture.  Sending the
    same phone without + must still trigger conflict.
    """
    from app.models import Tenant
    from sqlalchemy import select

    # Ensure tenant phone is known
    result = await db_session.execute(
        select(Tenant).where(Tenant.owner_user_id == active_tenant_user.id)
    )
    tenant = result.scalar_one_or_none()
    tenant_phone = tenant.phone  # "+12015550002" (has + in fixture)

    # Strip + from the phone input
    stripped_phone = tenant_phone.lstrip("+")  # "12015550002"

    master_headers = await _login(client, "master", "master-password")
    response = await client.put(
        "/api/v1/me",
        json={"phone": stripped_phone},
        headers=master_headers,
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Phone already registered"


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


# ===========================================================================
# Phase 3: Service-layer enforcement tests
# ===========================================================================


async def test_update_profile_service_normalizes_phone(db_session, master_user):
    """Direct profile service normalizes phone on update."""
    from app.schemas.me import ProfileUpdate
    from app.services.profile_service import ProfileService

    payload = ProfileUpdate(phone="+12015550060")  # with +

    service = ProfileService()
    profile = await service.update_profile(db_session, master_user, payload)

    assert profile is not None
    assert profile.phone == "12015550060"


async def test_update_profile_service_normalizes_name(db_session, master_user):
    """Direct profile service normalizes master name (collapses spaces)."""
    from app.schemas.me import ProfileUpdate
    from app.services.profile_service import ProfileService

    payload = ProfileUpdate(name="Master   Name")  # multiple spaces

    service = ProfileService()
    profile = await service.update_profile(db_session, master_user, payload)

    assert profile is not None
    assert profile.name == "Master Name"


async def test_update_profile_service_rejects_invalid_phone_direct(
    db_session, master_user
):
    """Service rejects invalid phone bypassing Pydantic."""
    from app.schemas.me import ProfileUpdate
    from app.services.profile_service import ProfileService

    payload = ProfileUpdate()
    payload.phone = "abc"  # bypass Pydantic

    service = ProfileService()
    with pytest.raises(
        ValueError, match="Phone must contain at least one digit"
    ):
        await service.update_profile(db_session, master_user, payload)


async def test_update_profile_service_rejects_invalid_full_name_direct(
    db_session, active_tenant_user
):
    """Service rejects invalid full_name bypassing Pydantic."""
    from app.schemas.me import ProfileUpdate
    from app.services.profile_service import ProfileService

    payload = ProfileUpdate()
    payload.full_name = "John/Smith"  # bypass Pydantic

    service = ProfileService()
    with pytest.raises(
        ValueError, match="Full name may only contain letters, numbers, and spaces"
    ):
        await service.update_profile(db_session, active_tenant_user, payload)


async def test_update_profile_service_rejects_invalid_name_direct(
    db_session, master_user
):
    """Service rejects invalid master 'name' field bypassing Pydantic."""
    from app.schemas.me import ProfileUpdate
    from app.services.profile_service import ProfileService

    payload = ProfileUpdate()
    payload.name = "Master!"  # bypass Pydantic

    service = ProfileService()
    with pytest.raises(
        ValueError, match="Full name may only contain letters, numbers, and spaces"
    ):
        await service.update_profile(db_session, master_user, payload)


async def test_update_profile_service_rejects_invalid_email_direct(
    db_session, active_tenant_user
):
    """Service rejects invalid email bypassing Pydantic."""
    from app.schemas.me import ProfileUpdate
    from app.services.profile_service import ProfileService

    payload = ProfileUpdate()
    payload.email = "not-an-email"  # bypass Pydantic

    service = ProfileService()
    with pytest.raises(ValueError):
        await service.update_profile(db_session, active_tenant_user, payload)
