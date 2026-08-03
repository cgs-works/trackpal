import re
from uuid import UUID

import pytest
from sqlalchemy import select

from app.models import TenantSettings

pytestmark = pytest.mark.asyncio


async def _create_tenant(client, auth_headers, **overrides):
    payload = {
        "full_name": "Tenant One",
        "phone": "+12015550004",
        "username": "tenant_one",
        "password": "tenant-password",
        "plan": "pro",
    }
    payload.update(overrides)
    payload.setdefault("evolution_instance_name", f"{payload['username']}-instance")
    return await client.post("/api/v1/tenants/", json=payload, headers=auth_headers)


async def test_create_tenant(client, auth_headers, db_session):
    response = await _create_tenant(client, auth_headers, locale="es")

    assert response.status_code == 201
    data = response.json()
    assert data["full_name"] == "Tenant One"
    assert "email" not in data
    assert data["phone"] == "12015550004"  # canonical: no + prefix
    assert re.fullmatch(r"[a-z][a-z0-9]{0,4}", data["client_prefix"])
    assert data["username"] == "tenant_one"
    assert data["is_active"] is True
    assert data["plain_password"] is None
    assert data["id"]
    assert data["created_at"]
    tenant_settings = (
        await db_session.execute(
            select(TenantSettings).where(TenantSettings.tenant_id == UUID(data["id"]))
        )
    ).scalar_one()
    assert tenant_settings.locale == "es"


async def test_create_tenant_rejects_invalid_locale(client, auth_headers):
    response = await _create_tenant(client, auth_headers, locale="fr")

    assert response.status_code == 422
    assert "locale" in response.text.lower()


async def test_create_tenant_auto_password(client, auth_headers):
    response = await _create_tenant(
        client,
        auth_headers,
        username="tenant_auto",
        phone="+12015550005",
        password=None,
    )

    assert response.status_code == 201
    data = response.json()
    assert data["plain_password"]
    assert len(data["plain_password"]) >= 6
    assert re.fullmatch(r"[a-z][a-z0-9]{0,4}", data["client_prefix"])


async def test_create_tenant_duplicate_username(client, auth_headers):
    await _create_tenant(
        client, auth_headers, username="dup_user", phone="+12015550006"
    )

    response = await _create_tenant(
        client, auth_headers, username="dup_user", phone="+12015550007"
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Username already registered"


async def test_create_tenant_duplicate_phone(client, auth_headers, active_tenant_user):
    response = await _create_tenant(
        client,
        auth_headers,
        username="tenant_dup_phone",
        phone="+12015550002",
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Phone already registered"


async def test_create_tenant_explicit_client_prefix(client, auth_headers):
    response = await _create_tenant(
        client,
        auth_headers,
        username="tenant_prefix",
        phone="+12015550012",
        client_prefix="ab12",
    )

    assert response.status_code == 201
    assert response.json()["client_prefix"] == "ab12"


async def test_create_tenant_duplicate_client_prefix(client, auth_headers):
    await _create_tenant(
        client,
        auth_headers,
        username="tenant_prefix_a",
        phone="+12015550013",
        client_prefix="ab13",
    )

    response = await _create_tenant(
        client,
        auth_headers,
        username="tenant_prefix_b",
        phone="+12015550014",
        client_prefix="ab13",
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Prefijo de cliente ya registrado"


async def test_create_tenant_invalid_client_prefix(client, auth_headers):
    response = await _create_tenant(
        client,
        auth_headers,
        username="tenant_prefix_invalid",
        phone="+12015550015",
        client_prefix="1abc",
    )

    assert response.status_code == 422


async def test_list_tenants(
    client, auth_headers, active_tenant_user, deactivated_tenant_user
):
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
    assert data["id"]
    assert data["full_name"] == "Active Tenant"
    assert data["username"] == "tenant"


async def test_update_tenant(client, auth_headers, active_tenant_user):
    response = await client.put(
        f"/api/v1/tenants/{active_tenant_user.id}",
        json={
            "full_name": "Updated Tenant",
            "phone": "+12015550010",
            "evolution_instance_name": "updated-instance",
            "client_prefix": "z9",
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["full_name"] == "Updated Tenant"
    assert "email" not in data
    assert data["phone"] == "12015550010"  # canonical: no + prefix
    assert data["evolution_instance_name"] == "updated-instance"
    assert data["client_prefix"] == "z9"


async def test_update_tenant_duplicate_client_prefix(
    client, auth_headers, active_tenant_user, deactivated_tenant_user
):
    response = await client.put(
        f"/api/v1/tenants/{active_tenant_user.id}",
        json={"client_prefix": "tnb01"},
        headers=auth_headers,
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Prefijo de cliente ya registrado"


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


async def test_delete_tenant_inactive_only(
    client, auth_headers, deactivated_tenant_user, db_session
):
    from app.models import Tenant
    from sqlalchemy import select

    # Find the real tenant ID for the deactivated user
    result = await db_session.execute(
        select(Tenant).where(Tenant.owner_user_id == deactivated_tenant_user.id)
    )
    tenant = result.scalar_one_or_none()
    assert tenant is not None

    response = await client.post(
        f"/api/v1/tenants/{tenant.id}/delete",
        json={"password": "master-password", "destructive_word": "DELETE"},
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    assert response.json() == {"success": True}

    get_response = await client.get(
        f"/api/v1/tenants/{tenant.id}", headers=auth_headers
    )
    assert get_response.status_code == 404


async def test_delete_active_tenant_fails(
    client, auth_headers, active_tenant_user, db_session
):
    from app.models import Tenant
    from sqlalchemy import select

    # Find the real tenant ID for the active user
    result = await db_session.execute(
        select(Tenant).where(Tenant.owner_user_id == active_tenant_user.id)
    )
    tenant = result.scalar_one_or_none()
    assert tenant is not None

    response = await client.post(
        f"/api/v1/tenants/{tenant.id}/delete",
        json={"password": "master-password", "destructive_word": "DELETE"},
        headers=auth_headers,
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Cannot delete active tenant. Deactivate first."


async def test_create_tenant_phone_is_canonical(client, auth_headers, db_session):
    """Phone stored without + prefix when created with + input."""
    from uuid import UUID

    response = await _create_tenant(
        client,
        auth_headers,
        username="canonical_phone_test",
        phone="+12015550008",
    )

    assert response.status_code == 201
    data = response.json()
    assert data["phone"] == "12015550008"  # canonical: no + prefix

    # Verify in database directly
    from app.models import Tenant
    from sqlalchemy import select

    result = await db_session.execute(
        select(Tenant).where(Tenant.id == UUID(data["id"]))
    )
    profile = result.scalar_one_or_none()
    assert profile is not None
    assert profile.whatsapp_phone == "12015550008"


async def test_create_tenant_phone_jid_becomes_canonical(
    client, auth_headers, db_session
):
    """JID suffix phone stored as canonical digits-only."""
    from uuid import UUID

    response = await _create_tenant(
        client,
        auth_headers,
        username="canonical_jid_test",
        phone="+12015550009@s.whatsapp.net",
    )

    assert response.status_code == 201
    data = response.json()
    assert data["phone"] == "12015550009"

    from app.models import Tenant
    from sqlalchemy import select

    result = await db_session.execute(
        select(Tenant).where(Tenant.id == UUID(data["id"]))
    )
    profile = result.scalar_one_or_none()
    assert profile.whatsapp_phone == "12015550009"


async def test_update_tenant_phone_is_canonical(
    client, auth_headers, active_tenant_user, db_session
):
    """Updated phone stored without + prefix."""
    from uuid import UUID

    response = await client.put(
        f"/api/v1/tenants/{active_tenant_user.id}",
        json={
            "full_name": "Updated Tenant",
            "phone": "+12015550011",
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["phone"] == "12015550011"

    from app.models import Tenant
    from sqlalchemy import select

    result = await db_session.execute(
        select(Tenant).where(Tenant.owner_user_id == UUID(str(active_tenant_user.id)))
    )
    profile = result.scalar_one_or_none()
    assert profile.whatsapp_phone == "12015550011"


# ===========================================================================
# Phase 2: Validation policy integration tests
# ===========================================================================


async def test_create_tenant_invalid_username_slash(client, auth_headers):
    """Slash command as username returns 422."""
    response = await _create_tenant(
        client, auth_headers, username="/menu", phone="+12015550020"
    )
    assert response.status_code == 422


async def test_create_tenant_invalid_username_uppercase(client, auth_headers):
    """Uppercase/punctuation username returns 422."""
    response = await _create_tenant(
        client, auth_headers, username="Admin!", phone="+12015550021"
    )
    assert response.status_code == 422


async def test_create_tenant_invalid_username_unicode(client, auth_headers):
    """Unicode username returns 422."""
    response = await _create_tenant(
        client, auth_headers, username="\u00d1andu", phone="+12015550022"
    )
    assert response.status_code == 422


async def test_create_tenant_invalid_username_too_long(client, auth_headers):
    """Too-long username returns 422."""
    response = await _create_tenant(
        client, auth_headers, username="a" * 21, phone="+12015550023"
    )
    assert response.status_code == 422


async def test_create_tenant_rejects_removed_email_field(client, auth_headers):
    """The removed tenant email field is rejected."""
    response = await _create_tenant(
        client, auth_headers, email="not-an-email", username="invalid_email_test"
    )
    assert response.status_code == 422


async def test_create_tenant_invalid_phone(client, auth_headers):
    """Non-phone text returns 422."""
    response = await _create_tenant(
        client,
        auth_headers,
        phone="abc",
        username="invalid_phone_test",
    )
    assert response.status_code == 422


async def test_create_tenant_invalid_phone_short(client, auth_headers):
    """Too-short phone returns 422."""
    response = await _create_tenant(
        client,
        auth_headers,
        phone="123",
        username="short_phone_test",
    )
    assert response.status_code == 422


async def test_create_tenant_invalid_full_name_leading_space(client, auth_headers):
    """Leading space in full_name returns 422."""
    response = await _create_tenant(
        client,
        auth_headers,
        full_name=" Leading",
        username="fn_leading_test",
        phone="+12015550024",
    )
    assert response.status_code == 422


async def test_create_tenant_invalid_full_name_trailing_space(client, auth_headers):
    """Trailing space in full_name returns 422."""
    response = await _create_tenant(
        client,
        auth_headers,
        full_name="Trailing ",
        username="fn_trailing_test",
        phone="+12015550025",
    )
    assert response.status_code == 422


async def test_create_tenant_invalid_full_name_slash(client, auth_headers):
    """Slash in full_name returns 422."""
    response = await _create_tenant(
        client,
        auth_headers,
        full_name="John/Smith",
        username="fn_slash_test",
        phone="+12015550026",
    )
    assert response.status_code == 422


async def test_create_tenant_response_does_not_expose_email(client, auth_headers):
    response = await _create_tenant(
        client,
        auth_headers,
        username="no_email_test",
        phone="+12015550030",
    )

    assert response.status_code == 201
    assert "email" not in response.json()


async def test_create_tenant_full_name_collapsed(client, auth_headers):
    """Multiple internal spaces collapsed on create."""
    response = await _create_tenant(
        client,
        auth_headers,
        username="collapse_test",
        full_name="John   Smith   Jr",
        phone="+12015550031",
    )

    assert response.status_code == 201
    data = response.json()
    assert data["full_name"] == "John Smith Jr"


async def test_create_tenant_phone_without_plus(client, auth_headers):
    """Phone without + prefix accepted and canonicalized."""
    response = await _create_tenant(
        client,
        auth_headers,
        username="no_plus_phone",
        phone="12015550032",
    )

    assert response.status_code == 201
    data = response.json()
    assert data["phone"] == "12015550032"


async def test_create_tenant_same_logical_payload_normalized(
    client, auth_headers, db_session
):
    """Same logical payload with different formatting produces same canonical values."""
    from uuid import UUID
    from app.models import Tenant
    from sqlalchemy import select

    resp1 = await _create_tenant(
        client,
        auth_headers,
        username="logical_test_a",
        full_name="Alice   Smith",  # multiple internal spaces
        phone="+12015551001",
    )
    assert resp1.status_code == 201
    d1 = resp1.json()

    resp2 = await _create_tenant(
        client,
        auth_headers,
        username="logical_test_b",
        full_name="Alice Smith",  # single space
        phone="+12015551002",  # distinct phone
    )
    assert resp2.status_code == 201
    d2 = resp2.json()

    # Assert canonical forms for first tenant
    assert d1["full_name"] == "Alice Smith"  # collapsed
    assert d1["phone"] == "12015551001"  # digits-only

    # Assert canonical forms for second tenant
    assert d2["full_name"] == "Alice Smith"  # single space stays
    assert d2["phone"] == "12015551002"  # digits-only (no + added)

    # Verify persistence in DB
    for uid, expected_phone in [
        (d1["id"], "12015551001"),
        (d2["id"], "12015551002"),
    ]:
        result = await db_session.execute(select(Tenant).where(Tenant.id == UUID(uid)))
        profile = result.scalar_one_or_none()
        assert profile is not None
        assert profile.name == "Alice Smith"
        assert profile.whatsapp_phone == expected_phone


async def test_create_tenant_optional_phone_allowed(client, auth_headers):
    response = await _create_tenant(
        client,
        auth_headers,
        username="optional_fields",
        phone=None,
    )

    assert response.status_code == 201
    assert response.json()["phone"] is None


async def test_tenant_endpoints_require_master(client, active_tenant_user):
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"username": "tenant", "password": "tenant-password"},
    )
    headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}

    response = await client.get("/api/v1/tenants/", headers=headers)

    assert response.status_code == 403


async def test_update_tenant_rejects_removed_email_field(
    client, auth_headers, active_tenant_user
):
    """The removed tenant email field is rejected on update."""
    response = await client.put(
        f"/api/v1/tenants/{active_tenant_user.id}",
        json={"email": "not-an-email"},
        headers=auth_headers,
    )
    assert response.status_code == 422


async def test_update_tenant_invalid_phone(client, auth_headers, active_tenant_user):
    """Invalid phone in update returns 422."""
    response = await client.put(
        f"/api/v1/tenants/{active_tenant_user.id}",
        json={"phone": "abc"},
        headers=auth_headers,
    )
    assert response.status_code == 422


async def test_update_tenant_short_phone_rejected(
    client, auth_headers, active_tenant_user
):
    """Too-short phone in update returns 422."""
    response = await client.put(
        f"/api/v1/tenants/{active_tenant_user.id}",
        json={"phone": "123"},
        headers=auth_headers,
    )
    assert response.status_code == 422


async def test_update_tenant_invalid_full_name_leading_space(
    client, auth_headers, active_tenant_user
):
    """Leading space in full_name update returns 422."""
    response = await client.put(
        f"/api/v1/tenants/{active_tenant_user.id}",
        json={"full_name": " Leading"},
        headers=auth_headers,
    )
    assert response.status_code == 422


# ===========================================================================
# Phase 3: Service-layer enforcement tests
# ===========================================================================


async def test_create_tenant_service_normalizes_values(db_session):
    """Direct service call persists normalized phone and full_name."""
    from app.schemas.tenant import TenantCreate
    from app.services.tenant_service import TenantService

    payload = TenantCreate(
        username="service_test",
        full_name="John   Smith",  # multiple spaces
        phone="+12015550040",  # with +
        password="test-password",
        evolution_instance_name="service-test-instance",
        plan="pro",
    )

    service = TenantService()
    profile, _ = await service.create_tenant(db_session, payload)

    assert profile.full_name == "John Smith"  # collapsed
    assert profile.phone == "12015550040"  # canonical digits only


async def test_create_tenant_service_normalizes_phone_jid(db_session):
    """Direct service call normalizes JID-style phone."""
    from app.schemas.tenant import TenantCreate
    from app.services.tenant_service import TenantService

    payload = TenantCreate(
        username="service_jid_test",
        full_name="Test User",
        phone="+12015550041@s.whatsapp.net",
        password="test-password",
        evolution_instance_name="service-jid-instance",
        plan="pro",
    )

    service = TenantService()
    profile, _ = await service.create_tenant(db_session, payload)

    assert profile.phone == "12015550041"


async def test_create_tenant_service_rejects_invalid_username_direct(db_session):
    """Service layer rejects invalid username bypassing Pydantic."""
    from app.schemas.tenant import TenantCreate
    from app.services.tenant_service import TenantService

    payload = TenantCreate(
        username="valid_user",
        full_name="Test User",
        phone="+12015550042",
        password="test-password",
        evolution_instance_name="test-instance",
        plan="pro",
    )
    # Bypass Pydantic validation by mutating post-construction
    payload.username = "/menu"

    service = TenantService()
    with pytest.raises(ValueError, match="Username must start with a lowercase letter"):
        await service.create_tenant(db_session, payload)


async def test_create_tenant_service_rejects_invalid_phone_direct(db_session):
    """Service layer rejects invalid phone bypassing Pydantic."""
    from app.schemas.tenant import TenantCreate
    from app.services.tenant_service import TenantService

    payload = TenantCreate(
        username="phone_invalid_test",
        full_name="Test User",
        phone="+12015550043",
        password="test-password",
        evolution_instance_name="test-instance",
        plan="pro",
    )
    payload.phone = "abc"  # bypass Pydantic

    service = TenantService()
    with pytest.raises(ValueError, match="Phone must contain at least one digit"):
        await service.create_tenant(db_session, payload)


async def test_create_tenant_service_rejects_invalid_full_name_direct(db_session):
    """Service layer rejects invalid full_name bypassing Pydantic."""
    from app.schemas.tenant import TenantCreate
    from app.services.tenant_service import TenantService

    payload = TenantCreate(
        username="fn_invalid_test",
        full_name="Test User",
        phone="+12015550044",
        password="test-password",
        evolution_instance_name="test-instance",
        plan="pro",
    )
    payload.full_name = " Leading"  # bypass Pydantic

    service = TenantService()
    with pytest.raises(
        ValueError,
        match="Full name must not start or end with spaces",
    ):
        await service.create_tenant(db_session, payload)


async def test_update_tenant_service_normalizes_values(db_session, active_tenant_user):
    """Service layer normalizes full_name and phone on update."""
    from app.schemas.tenant import TenantUpdate
    from app.services.tenant_service import TenantService

    payload = TenantUpdate(
        full_name="Updated   Name",  # multiple spaces
        phone="+12015550050",  # with +
    )

    service = TenantService()
    profile = await service.update_tenant(db_session, active_tenant_user.id, payload)

    assert profile is not None
    assert profile.full_name == "Updated Name"  # collapsed
    assert profile.phone == "12015550050"  # canonical digits only


async def test_duplicate_username_service_layer(db_session):
    """Service-layer duplicate check runs after normalization."""
    from app.schemas.tenant import TenantCreate
    from app.services.tenant_service import TenantService

    payload1 = TenantCreate(
        username="dup_test",
        full_name="First",
        phone="+12015550060",
        password="test-password",
        evolution_instance_name="dup-test-1",
        plan="pro",
    )
    service = TenantService()
    await service.create_tenant(db_session, payload1)

    payload2 = TenantCreate(
        username="dup_test",  # same normalized username
        full_name="Second",
        phone="+12015550061",
        password="test-password",
        evolution_instance_name="dup-test-2",
        plan="pro",
    )
    with pytest.raises(ValueError, match="Username already registered"):
        await service.create_tenant(db_session, payload2)


async def test_duplicate_phone_service_layer(db_session):
    """Service-layer phone duplicate check runs after normalization."""
    from app.schemas.tenant import TenantCreate
    from app.services.tenant_service import TenantService

    payload1 = TenantCreate(
        username="phone_dup_test_1",
        full_name="First",
        phone="+12015550070",
        password="test-password",
        evolution_instance_name="phone-dup-1",
        plan="pro",
    )
    service = TenantService()
    await service.create_tenant(db_session, payload1)

    payload2 = TenantCreate(
        username="phone_dup_test_2",
        full_name="Second",
        phone="12015550070",  # same digits, no +
        password="test-password",
        evolution_instance_name="phone-dup-2",
        plan="pro",
    )
    with pytest.raises(ValueError, match="Phone already registered"):
        await service.create_tenant(db_session, payload2)
