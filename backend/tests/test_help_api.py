import pytest
from sqlalchemy import select

from app.core.security import create_access_token
from app.models import Tenant, TenantSettings

pytestmark = pytest.mark.asyncio


async def _login(client, username: str, password: str) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def test_tenant_admin_receives_localized_help_index_and_topic(
    client, active_tenant_user, db_session
):
    headers = await _login(client, "tenant", "tenant-password")

    index_response = await client.get("/api/v1/help", headers=headers)
    topic_response = await client.get(
        "/api/v1/help/topics/tenant-admin.dashboard", headers=headers
    )

    assert index_response.status_code == 200
    assert index_response.json()["locale"] == "es"
    assert [topic["id"] for topic in index_response.json()["topics"]] == [
        "tenant-admin.dashboard",
        "tenant-admin.language",
        "tenant-admin.whatsapp",
        "tenant-admin.profile",
        "tenant-admin.password",
    ]
    assert index_response.json()["topics"][1]["help_targets"] == [
        "admin.settings.language"
    ]
    assert index_response.json()["topics"][1]["safe_navigation"] == {
        "route": "/admin/settings",
        "settings_category": "locale",
    }
    assert topic_response.status_code == 200
    assert topic_response.json()["title"] == "Panel del negocio"
    assert "dashboard" in topic_response.json()["body"].lower()
    assert "frontmatter" not in topic_response.json()

    tenant = (
        await db_session.execute(
            select(Tenant).where(Tenant.owner_user_id == active_tenant_user.id)
        )
    ).scalar_one()
    tenant.plan = "starter"
    await db_session.commit()
    starter_index = await client.get("/api/v1/help", headers=headers)
    assert [topic["id"] for topic in starter_index.json()["topics"]] == [
        "tenant-admin.dashboard",
        "tenant-admin.language",
        "tenant-admin.whatsapp",
        "tenant-admin.profile",
        "tenant-admin.password",
    ]

    tenant = (
        await db_session.execute(
            select(Tenant).where(Tenant.owner_user_id == active_tenant_user.id)
        )
    ).scalar_one()
    settings = (
        await db_session.execute(
            select(TenantSettings).where(TenantSettings.tenant_id == tenant.id)
        )
    ).scalar_one()
    settings.locale = "en"
    await db_session.commit()

    english_topic = await client.get(
        "/api/v1/help/topics/tenant-admin.dashboard", headers=headers
    )
    assert english_topic.status_code == 200
    assert english_topic.json()["title"] == "Business Dashboard"


async def test_help_search_returns_only_authorized_private_content(
    client, active_tenant_user
):
    headers = await _login(client, "tenant", "tenant-password")

    response = await client.get(
        "/api/v1/help/search", params={"q": "buzón"}, headers=headers
    )

    assert response.status_code == 200
    result = response.json()["results"][0]
    assert result["id"] == "tenant-admin.dashboard"
    assert "buzón" in result["excerpt"].lower()
    assert set(result) == {"id", "title", "module", "route", "order", "excerpt"}


async def test_help_search_uses_locale_synonyms_and_returns_no_results(
    client, active_tenant_user, db_session
):
    headers = await _login(client, "tenant", "tenant-password")

    spanish = await client.get(
        "/api/v1/help/search", params={"q": "inicio"}, headers=headers
    )
    assert spanish.status_code == 200
    assert [result["id"] for result in spanish.json()["results"]] == [
        "tenant-admin.dashboard"
    ]

    tenant = (
        await db_session.execute(
            select(Tenant).where(Tenant.owner_user_id == active_tenant_user.id)
        )
    ).scalar_one()
    settings = (
        await db_session.execute(
            select(TenantSettings).where(TenantSettings.tenant_id == tenant.id)
        )
    ).scalar_one()
    settings.locale = "en"
    await db_session.commit()

    english = await client.get(
        "/api/v1/help/search", params={"q": "overview"}, headers=headers
    )
    empty = await client.get(
        "/api/v1/help/search", params={"q": "does-not-exist"}, headers=headers
    )
    assert english.status_code == 200
    assert english.json()["locale"] == "en"
    assert [result["id"] for result in english.json()["results"]] == [
        "tenant-admin.dashboard"
    ]
    assert empty.status_code == 200
    assert empty.json()["results"] == []


async def test_help_denies_unauthenticated_clients_and_master_support_context(
    client, active_client_user, master_user, active_tenant_user, db_session
):
    unauthenticated = await client.get("/api/v1/help")
    assert unauthenticated.status_code == 401

    client_headers = await _login(
        client, active_client_user.username, "client-password"
    )
    client_index = await client.get("/api/v1/help", headers=client_headers)
    client_search = await client.get(
        "/api/v1/help/search", params={"q": "dashboard"}, headers=client_headers
    )
    client_response = await client.get(
        "/api/v1/help/topics/tenant-admin.dashboard", headers=client_headers
    )
    assert client_index.status_code == 200
    assert client_index.json()["topics"] == []
    assert client_search.status_code == 200
    assert client_search.json()["results"] == []
    assert client_response.status_code == 404

    tenant = (
        await db_session.execute(
            select(Tenant).where(Tenant.owner_user_id == active_tenant_user.id)
        )
    ).scalar_one()
    support_token = create_access_token(
        subject=str(master_user.id),
        role="master",
        active_tenant_id=str(tenant.id),
    )
    support_response = await client.get(
        "/api/v1/help/topics/tenant-admin.dashboard",
        headers={"Authorization": f"Bearer {support_token}"},
    )
    support_search = await client.get(
        "/api/v1/help/search",
        params={"q": "dashboard"},
        headers={"Authorization": f"Bearer {support_token}"},
    )
    assert support_response.status_code == 404
    assert support_search.status_code == 404
