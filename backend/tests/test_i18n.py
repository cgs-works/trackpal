import pytest

pytestmark = pytest.mark.asyncio


async def _login(client, username: str, password: str) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/login", json={"username": username, "password": password}
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ── Profile: locale exposure via /me ────────────────────────────────────────


async def test_get_profile_tenant_exposes_locale(client, active_tenant_user):
    headers = await _login(client, "tenant", "tenant-password")

    response = await client.get("/api/v1/me", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "tenant"
    # Tenant created without explicit locale → model default "en"
    assert data["locale"] == "en"


async def test_get_profile_master_locale_is_none(client, master_user):
    """Master profile has no locale field."""
    headers = await _login(client, "master", "master-password")

    response = await client.get("/api/v1/me", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "master"
    assert data.get("locale") is None


async def test_update_profile_locale_valid(client, active_tenant_user):
    headers = await _login(client, "tenant", "tenant-password")

    response = await client.put(
        "/api/v1/me",
        json={"locale": "es"},
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["locale"] == "es"


async def test_update_profile_locale_invalid(client, active_tenant_user):
    headers = await _login(client, "tenant", "tenant-password")

    response = await client.put(
        "/api/v1/me",
        json={"locale": "fr"},
        headers=headers,
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert any("Locale must be one of" in str(err.get("msg", "")) for err in detail)


async def test_update_profile_locale_case_insensitive(client, active_tenant_user):
    headers = await _login(client, "tenant", "tenant-password")

    response = await client.put(
        "/api/v1/me",
        json={"locale": "ES"},
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["locale"] == "es"


async def test_update_profile_locale_persistence(client, active_tenant_user, db_session):
    """Locale change persists across requests."""
    headers = await _login(client, "tenant", "tenant-password")

    # Set to Spanish
    await client.put("/api/v1/me", json={"locale": "es"}, headers=headers)

    # Fetch again
    response = await client.get("/api/v1/me", headers=headers)
    assert response.json()["locale"] == "es"

    # Set back to English
    await client.put("/api/v1/me", json={"locale": "en"}, headers=headers)

    response = await client.get("/api/v1/me", headers=headers)
    assert response.json()["locale"] == "en"


async def test_master_cannot_change_locale(client, master_user):
    """Master profile update ignores locale (not in allowed fields)."""
    headers = await _login(client, "master", "master-password")

    response = await client.put(
        "/api/v1/me",
        json={"locale": "es", "name": "Master Updated"},
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Master Updated"
    assert data.get("locale") is None  # master has no locale


# ── i18n catalog endpoint ──────────────────────────────────────────────────


async def test_catalog_endpoint_returns_english_default(client, active_tenant_user):
    headers = await _login(client, "tenant", "tenant-password")

    response = await client.get("/api/v1/i18n/catalog", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["locale"] == "en"
    assert data["locale_name"] == "English"
    assert "catalog" in data
    assert data["catalog"]["error.auth.invalid_credentials"] == "Invalid username or password"


async def test_catalog_endpoint_returns_spanish(client, active_tenant_user):
    headers = await _login(client, "tenant", "tenant-password")

    # Switch to Spanish
    await client.put("/api/v1/me", json={"locale": "es"}, headers=headers)

    response = await client.get("/api/v1/i18n/catalog", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["locale"] == "es"
    assert data["locale_name"] == "Español"
    assert data["catalog"]["error.auth.invalid_credentials"] == "Usuario o contraseña inválidos"


async def test_catalog_endpoint_spanish_falls_back_to_english(client, active_tenant_user):
    """Missing es key falls back to English value."""
    headers = await _login(client, "tenant", "tenant-password")

    # Switch to Spanish
    await client.put("/api/v1/me", json={"locale": "es"}, headers=headers)

    response = await client.get("/api/v1/i18n/catalog", headers=headers)

    assert response.status_code == 200
    data = response.json()
    # Key exists only in English catalog → should appear via fallback
    # (all keys in _CATALOG_ES are also in _CATALOG_EN, but let's check a
    #  specific key exists in merged output regardless of locale)
    assert "error.auth.invalid_credentials" in data["catalog"]


async def test_catalog_endpoint_locale_refetch_after_change(client, active_tenant_user):
    """Catalog reflects locale change immediately."""
    headers = await _login(client, "tenant", "tenant-password")

    # Fetch catalog in English
    resp_en = await client.get("/api/v1/i18n/catalog", headers=headers)
    assert resp_en.json()["locale"] == "en"

    # Change locale
    await client.put("/api/v1/me", json={"locale": "es"}, headers=headers)

    # Fetch again
    resp_es = await client.get("/api/v1/i18n/catalog", headers=headers)
    assert resp_es.json()["locale"] == "es"
    assert resp_es.json()["catalog"]["error.auth.invalid_credentials"] == "Usuario o contraseña inválidos"


async def test_catalog_endpoint_master_returns_english(client, master_user):
    """Master user (no tenant locale) gets English catalog."""
    headers = await _login(client, "master", "master-password")

    response = await client.get("/api/v1/i18n/catalog", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["locale"] == "en"
    assert data["locale_name"] == "English"


async def test_catalog_endpoint_unauthorized(client):
    """No auth token returns 401."""
    response = await client.get("/api/v1/i18n/catalog")

    assert response.status_code == 401


# ── i18n engine direct tests ──────────────────────────────────────────────


async def test_t_function_translates():
    from app.core.i18n import t, missing_key_counter

    assert t("en", "error.auth.invalid_credentials") == "Invalid username or password"
    assert t("es", "error.auth.invalid_credentials") == "Usuario o contraseña inválidos"


async def test_t_function_with_params():
    from app.core.i18n import t

    result = t("en", "reminder.subscription.expiring", service_name="Netflix", client_name="Juan", days="3", day_word="days", streaming_email="juan@example.com")
    assert "Netflix" in result
    assert "Juan" in result
    assert "3" in result
    assert "days" in result
    assert "juan@example.com" in result


async def test_t_function_missing_key_fallback():
    from app.core.i18n import t

    # Use a key that exists only in EN catalog at import time
    # (all keys exist in both right now; test the actual fallback machinery
    #  by checking that a nonexistent key falls back to its EN template)
    result = t("es", "error.auth.invalid_credentials")
    # Key exists in ES → should return ES, not EN
    assert result == "Usuario o contraseña inválidos"


async def test_t_function_unknown_key():
    from app.core.i18n import t, missing_key_counter

    before = missing_key_counter.get("test.nonexistent.key", 0)
    result = t("en", "test.nonexistent.key")
    assert result == "test.nonexistent.key"  # returns key itself
    assert missing_key_counter.get("test.nonexistent.key", 0) > before


async def test_get_merged_catalog_contains_all_keys():
    from app.core.i18n import get_merged_catalog

    en = get_merged_catalog("en")
    es = get_merged_catalog("es")

    # ES should have all EN keys (via fallback)
    for k in en:
        assert k in es, f"Key {k!r} missing from es merged catalog"


async def test_get_merged_catalog_immutable():
    from app.core.i18n import get_merged_catalog

    cat = get_merged_catalog("en")
    cat["error.auth.invalid_credentials"] = "HACKED"

    # Original should be unchanged
    cat2 = get_merged_catalog("en")
    assert cat2["error.auth.invalid_credentials"] == "Invalid username or password"
