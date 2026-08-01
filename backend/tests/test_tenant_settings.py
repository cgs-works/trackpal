import pytest
from sqlalchemy import select

from app.models import Tenant, TenantSettings
from app.repositories import tenant_settings_repository

pytestmark = pytest.mark.asyncio


async def _tenant_for_user(db_session, user_id):
    result = await db_session.execute(
        select(Tenant).where(Tenant.owner_user_id == user_id)
    )
    return result.scalar_one()


async def test_tenant_settings_model_defaults_persist(db_session, active_tenant_user):
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)

    result = await db_session.execute(
        select(TenantSettings).where(TenantSettings.tenant_id == tenant.id)
    )
    settings = result.scalar_one()

    assert settings.tenant_id == tenant.id
    assert settings.locale == "es"
    assert settings.timezone == "UTC"
    assert settings.created_at is not None
    assert settings.updated_at is not None


async def test_tenant_settings_can_store_locale_and_timezone(
    db_session, active_tenant_user
):
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    result = await db_session.execute(
        select(TenantSettings).where(TenantSettings.tenant_id == tenant.id)
    )
    settings = result.scalar_one()

    settings.locale = "es"
    settings.timezone = "America/Santo_Domingo"
    await db_session.commit()

    result = await db_session.execute(
        select(TenantSettings).where(TenantSettings.tenant_id == tenant.id)
    )
    persisted = result.scalar_one()
    assert persisted.locale == "es"
    assert persisted.timezone == "America/Santo_Domingo"


async def _login(client, username: str, password: str) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/login", json={"username": username, "password": password}
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def test_get_tenant_settings_returns_defaults(client, active_tenant_user):
    headers = await _login(client, "tenant", "tenant-password")

    response = await client.get("/api/v1/tenant-settings", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["locale"] == "es"
    assert data["timezone"] == "UTC"
    assert data["tenant_id"] is not None
    assert data["created_at"] is not None
    assert data["updated_at"] is not None


async def test_put_tenant_settings_updates_locale_and_timezone(
    client, active_tenant_user
):
    headers = await _login(client, "tenant", "tenant-password")

    response = await client.put(
        "/api/v1/tenant-settings",
        json={"locale": "es", "timezone": "America/Santo_Domingo"},
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["locale"] == "es"
    assert data["timezone"] == "America/Santo_Domingo"


async def test_put_tenant_settings_rejects_invalid_locale(client, active_tenant_user):
    headers = await _login(client, "tenant", "tenant-password")

    response = await client.put(
        "/api/v1/tenant-settings",
        json={"locale": "fr"},
        headers=headers,
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert any("Locale must be one of" in str(err.get("msg", "")) for err in detail)


async def test_put_tenant_settings_rejects_invalid_timezone(client, active_tenant_user):
    headers = await _login(client, "tenant", "tenant-password")

    response = await client.put(
        "/api/v1/tenant-settings",
        json={"timezone": "Not/AZone"},
        headers=headers,
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert any("valid IANA timezone" in str(err.get("msg", "")) for err in detail)


async def test_tenant_settings_timezones_endpoint(client, active_tenant_user):
    headers = await _login(client, "tenant", "tenant-password")

    response = await client.get("/api/v1/tenant-settings/timezones", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert any(item["value"] == "UTC" for item in data)


async def test_tenant_settings_repository_resolves_defaults_when_missing(
    db_session, active_tenant_user
):
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    settings = await tenant_settings_repository.get_by_tenant_id(db_session, tenant.id)
    await db_session.delete(settings)
    await db_session.commit()

    resolved = await tenant_settings_repository.resolve_timezone(db_session, tenant.id)

    assert resolved == "UTC"


async def test_tenant_settings_country_currency_default_null(
    db_session, active_tenant_user
):
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    result = await db_session.execute(
        select(TenantSettings).where(TenantSettings.tenant_id == tenant.id)
    )
    settings = result.scalar_one()
    assert settings.country is None
    assert settings.currency is None


async def test_tenant_settings_can_store_country_and_currency(
    db_session, active_tenant_user
):
    tenant = await _tenant_for_user(db_session, active_tenant_user.id)
    result = await db_session.execute(
        select(TenantSettings).where(TenantSettings.tenant_id == tenant.id)
    )
    settings = result.scalar_one()
    settings.country = "VE"
    settings.currency = "VES"
    await db_session.commit()

    # Verify the columns exist in the table schema (not just in-memory)
    column_names = {c.name for c in TenantSettings.__table__.columns}
    assert "country" in column_names
    assert "currency" in column_names

    # Verify values persisted through a refresh from DB
    await db_session.refresh(settings)
    assert settings.country == "VE"
    assert settings.currency == "VES"


# --- Task 3: country/currency API tests ---


async def test_currencies_endpoint_returns_catalog(client, active_tenant_user):
    headers = await _login(client, "tenant", "tenant-password")
    response = await client.get("/api/v1/tenant-settings/currencies", headers=headers)
    assert response.status_code == 200
    payload = response.json()
    ve = next(c for c in payload["countries"] if c["code"] == "VE")
    assert ve["currency"] == "VES"
    ves = next(c for c in payload["currencies"] if c["code"] == "VES")
    assert ves["symbol"] == "Bs."


async def test_update_tenant_settings_country_currency(client, active_tenant_user):
    headers = await _login(client, "tenant", "tenant-password")
    response = await client.put(
        "/api/v1/tenant-settings",
        json={"country": "ve", "currency": "ves", "timezone": "America/Caracas"},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["country"] == "VE"
    assert body["currency"] == "VES"


async def test_update_tenant_settings_invalid_country_conflict(
    client, active_tenant_user
):
    headers = await _login(client, "tenant", "tenant-password")
    response = await client.put(
        "/api/v1/tenant-settings", json={"country": "XX"}, headers=headers
    )
    assert response.status_code == 409


async def test_update_tenant_settings_invalid_currency_conflict(
    client, active_tenant_user
):
    headers = await _login(client, "tenant", "tenant-password")
    response = await client.put(
        "/api/v1/tenant-settings", json={"currency": "ZZZ"}, headers=headers
    )
    assert response.status_code == 409


async def test_starter_get_nulled_currency_and_timezone(
    client, auth_headers, active_tenant_user
):
    downgrade = await client.put(
        f"/api/v1/tenants/{active_tenant_user.id}",
        json={"plan": "starter"},
        headers=auth_headers,
    )
    assert downgrade.status_code == 200, downgrade.text
    headers = await _login(client, "tenant", "tenant-password")
    response = await client.get("/api/v1/tenant-settings", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["timezone"] is None
    assert body["currency"] is None


async def test_starter_put_currency_rejected_404(
    client, auth_headers, active_tenant_user
):
    downgrade = await client.put(
        f"/api/v1/tenants/{active_tenant_user.id}",
        json={"plan": "starter"},
        headers=auth_headers,
    )
    assert downgrade.status_code == 200, downgrade.text
    headers = await _login(client, "tenant", "tenant-password")
    response = await client.put(
        "/api/v1/tenant-settings", json={"currency": "VES"}, headers=headers
    )
    assert response.status_code == 404
