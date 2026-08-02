from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models import Plan, Service, Tenant, TenantApiKey, User

pytestmark = pytest.mark.asyncio


async def _login(
    client, username: str = "tenant", password: str = "tenant-password"
) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def _tenant_for_user(db_session, user: User) -> Tenant:
    result = await db_session.execute(
        select(Tenant).where(Tenant.owner_user_id == user.id)
    )
    return result.scalar_one()


async def _make_starter(client, auth_headers, active_tenant_user: User) -> None:
    response = await client.put(
        f"/api/v1/tenants/{active_tenant_user.id}",
        json={"plan": "starter"},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text


async def _create_public_key(client, headers, origins: list[str]) -> str:
    response = await client.put(
        "/api/v1/public-api-key",
        json={"allowed_origins": origins},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()["api_key"]


async def _seed_catalog(db_session, tenant_id):
    service = Service(
        tenant_id=tenant_id,
        name="Netflix",
        icon="simple-icons:netflix",
    )
    db_session.add(service)
    await db_session.flush()
    basic = Plan(tenant_id=tenant_id, service_id=service.id, name="Basic")
    premium = Plan(tenant_id=tenant_id, service_id=service.id, name="Premium")
    db_session.add_all([basic, premium])
    await db_session.commit()
    return service, basic, premium


async def test_public_api_key_management_lifecycle(
    client, active_tenant_user, db_session
):
    headers = await _login(client)

    empty = await client.get("/api/v1/public-api-key", headers=headers)
    assert empty.status_code == 200, empty.text
    assert empty.json() is None

    created = await client.put(
        "/api/v1/public-api-key",
        json={"allowed_origins": ["https://example.com", "http://localhost:5173"]},
        headers=headers,
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["api_key"].startswith("tpk_")
    assert body["allowed_origins"] == ["https://example.com", "http://localhost:5173"]

    tenant = await _tenant_for_user(db_session, active_tenant_user)
    row = await db_session.get(TenantApiKey, tenant.id)
    assert row is not None
    assert row.api_key == body["api_key"]

    updated = await client.put(
        "/api/v1/public-api-key",
        json={"allowed_origins": ["https://docs.example.com"]},
        headers=headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["api_key"] == body["api_key"]
    assert updated.json()["allowed_origins"] == ["https://docs.example.com"]

    regenerated = await client.post(
        "/api/v1/public-api-key/regenerate", headers=headers
    )
    assert regenerated.status_code == 200, regenerated.text
    assert regenerated.json()["api_key"] != body["api_key"]
    assert regenerated.json()["allowed_origins"] == ["https://docs.example.com"]

    deleted = await client.delete("/api/v1/public-api-key", headers=headers)
    assert deleted.status_code == 204, deleted.text

    after_delete = await client.get("/api/v1/public-api-key", headers=headers)
    assert after_delete.status_code == 200, after_delete.text
    assert after_delete.json() is None


@pytest.mark.parametrize(
    "origin",
    [
        "",
        "example.com",
        "https://*.example.com",
        "https://example.com/path",
        "ftp://example.com",
        "https://example.com?x=1",
    ],
)
async def test_public_api_key_management_rejects_invalid_origins(
    client, active_tenant_user, origin: str
):
    headers = await _login(client)
    response = await client.put(
        "/api/v1/public-api-key",
        json={"allowed_origins": [origin]},
        headers=headers,
    )
    assert response.status_code == 422, response.text


async def test_starter_tenant_cannot_manage_public_api_key(
    client, auth_headers, active_tenant_user
):
    await _make_starter(client, auth_headers, active_tenant_user)
    headers = await _login(client)

    read = await client.get("/api/v1/public-api-key", headers=headers)
    assert read.status_code == 404, read.text

    write = await client.put(
        "/api/v1/public-api-key",
        json={"allowed_origins": ["https://example.com"]},
        headers=headers,
    )
    assert write.status_code == 404, write.text


async def test_master_support_context_can_manage_starter_public_api_key(
    client, auth_headers, active_tenant_user
):
    await _make_starter(client, auth_headers, active_tenant_user)
    tenant_login = await client.post(
        "/api/v1/auth/login",
        json={"username": "tenant", "password": "tenant-password"},
    )
    tenant_id = tenant_login.json()["active_tenant_id"]
    switched = await client.post(
        "/api/v1/auth/switch-tenant",
        json={"tenant_id": tenant_id},
        headers=auth_headers,
    )
    assert switched.status_code == 200, switched.text
    headers = {"Authorization": f"Bearer {switched.json()['access_token']}"}

    response = await client.put(
        "/api/v1/public-api-key",
        json={"allowed_origins": ["https://support.example.com"]},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["allowed_origins"] == ["https://support.example.com"]


async def test_public_catalog_success_returns_nested_services_and_cors(
    client, active_tenant_user, db_session
):
    headers = await _login(client)
    tenant = await _tenant_for_user(db_session, active_tenant_user)
    service, basic, premium = await _seed_catalog(db_session, tenant.id)
    api_key = await _create_public_key(client, headers, ["https://example.com"])

    response = await client.get(
        f"/api/v1/public/catalog?api_key={api_key}",
        headers={"Origin": "https://example.com"},
    )

    assert response.status_code == 200, response.text
    assert response.headers["access-control-allow-origin"] == "https://example.com"
    assert response.headers["vary"] == "Origin"
    body = response.json()
    assert len(body["services"]) == 1
    svc = body["services"][0]
    assert svc["id"] == str(service.id)
    assert svc["name"] == "Netflix"
    assert svc["icon"] == "simple-icons:netflix"
    assert len(svc["plans"]) == 2
    plan_names = [p["name"] for p in svc["plans"]]
    assert "Basic" in plan_names
    assert "Premium" in plan_names
    # currency is null when tenant_settings.currency is not set
    assert body["currency"] is None


@pytest.mark.parametrize(
    "headers,query",
    [
        ({}, "api_key=tpk_missing_origin"),
        ({"Origin": "https://example.com"}, ""),
        ({"Origin": "https://example.com"}, "api_key=tpk_invalid"),
        ({"Origin": "https://evil.example"}, "api_key={api_key}"),
    ],
)
async def test_public_catalog_forbidden_cases(
    client, active_tenant_user, db_session, headers: dict[str, str], query: str
):
    auth_headers = await _login(client)
    api_key = await _create_public_key(client, auth_headers, ["https://example.com"])
    resolved_query = query.format(api_key=api_key)

    response = await client.get(
        f"/api/v1/public/catalog{('?' + resolved_query) if resolved_query else ''}",
        headers=headers,
    )

    assert response.status_code == 403, response.text
    assert "access-control-allow-origin" not in response.headers


async def test_public_catalog_starter_downgrade_preserves_config_but_returns_403(
    client, auth_headers, active_tenant_user, db_session
):
    tenant_headers = await _login(client)
    api_key = await _create_public_key(client, tenant_headers, ["https://example.com"])
    await _make_starter(client, auth_headers, active_tenant_user)

    response = await client.get(
        f"/api/v1/public/catalog?api_key={api_key}",
        headers={"Origin": "https://example.com"},
    )
    assert response.status_code == 403, response.text

    tenant = await _tenant_for_user(db_session, active_tenant_user)
    row = await db_session.get(TenantApiKey, tenant.id)
    assert row is not None
    assert row.api_key == api_key


# --- New tests for Task 5: price + currency ---


async def test_public_catalog_plan_price_exposed(
    client, active_tenant_user, db_session
):
    """Plans with a price value expose it in the public catalog."""
    from decimal import Decimal

    headers = await _login(client)
    tenant = await _tenant_for_user(db_session, active_tenant_user)

    service = Service(
        tenant_id=tenant.id,
        name="Spotify",
        icon="simple-icons:spotify",
    )
    db_session.add(service)
    await db_session.flush()
    plan = Plan(
        tenant_id=tenant.id,
        service_id=service.id,
        name="Family",
        price=Decimal("12.50"),
    )
    db_session.add(plan)
    await db_session.commit()

    api_key = await _create_public_key(client, headers, ["https://example.com"])

    response = await client.get(
        f"/api/v1/public/catalog?api_key={api_key}",
        headers={"Origin": "https://example.com"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    catalog_plan = body["services"][0]["plans"][0]
    assert catalog_plan["price"] == "12.50"


async def test_public_catalog_plan_price_null_when_unset(
    client, active_tenant_user, db_session
):
    """Plans without a price expose null."""
    headers = await _login(client)
    tenant = await _tenant_for_user(db_session, active_tenant_user)
    service, basic, premium = await _seed_catalog(db_session, tenant.id)
    api_key = await _create_public_key(client, headers, ["https://example.com"])

    response = await client.get(
        f"/api/v1/public/catalog?api_key={api_key}",
        headers={"Origin": "https://example.com"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    for plan in body["services"][0]["plans"]:
        assert plan["price"] is None


async def test_public_catalog_currency_from_tenant_settings(
    client, active_tenant_user, db_session
):
    """When tenant_settings.currency is set, response includes currency metadata."""
    headers = await _login(client)
    tenant = await _tenant_for_user(db_session, active_tenant_user)

    # Set currency on tenant_settings
    from app.repositories import tenant_settings_repository

    await tenant_settings_repository.update_settings(
        db_session, tenant.id, {"currency": "VES"}
    )
    await db_session.commit()

    await _seed_catalog(db_session, tenant.id)
    api_key = await _create_public_key(client, headers, ["https://example.com"])

    response = await client.get(
        f"/api/v1/public/catalog?api_key={api_key}",
        headers={"Origin": "https://example.com"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["currency"] == {"code": "VES", "symbol": "Bs.", "minor_units": 2}


async def test_public_catalog_currency_null_when_unset(
    client, active_tenant_user, db_session
):
    """When tenant_settings.currency is not set, response.currency is null."""
    headers = await _login(client)
    tenant = await _tenant_for_user(db_session, active_tenant_user)
    await _seed_catalog(db_session, tenant.id)
    api_key = await _create_public_key(client, headers, ["https://example.com"])

    response = await client.get(
        f"/api/v1/public/catalog?api_key={api_key}",
        headers={"Origin": "https://example.com"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["currency"] is None
