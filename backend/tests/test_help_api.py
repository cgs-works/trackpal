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
        "tenant-admin.code-services",
        "tenant-admin.mailbox",
        "tenant-admin.access-control",
        "tenant-admin.activate-access-code-lookup",
        "tenant-admin.clients",
        "tenant-admin.catalog",
        "tenant-admin.subscriptions",
        "tenant-admin.first-pro-client",
        "tenant-admin.reminders",
        "tenant-admin.timezone",
        "tenant-admin.subscription-expirations",
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
        "tenant-admin.code-services",
        "tenant-admin.mailbox",
        "tenant-admin.access-control",
        "tenant-admin.activate-access-code-lookup",
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


async def test_pro_help_topics_are_authorized_and_safe_to_navigate(
    client, active_tenant_user, db_session
):
    headers = await _login(client, "tenant", "tenant-password")

    index_response = await client.get("/api/v1/help", headers=headers)
    clients_topic = await client.get(
        "/api/v1/help/topics/tenant-admin.clients", headers=headers
    )
    first_client_topic = await client.get(
        "/api/v1/help/topics/tenant-admin.first-pro-client", headers=headers
    )
    reminders_topic = await client.get(
        "/api/v1/help/topics/tenant-admin.reminders", headers=headers
    )
    expiration_topic = await client.get(
        "/api/v1/help/topics/tenant-admin.subscription-expirations", headers=headers
    )

    assert index_response.status_code == 200
    assert {topic["id"] for topic in index_response.json()["topics"]} >= {
        "tenant-admin.clients",
        "tenant-admin.catalog",
        "tenant-admin.subscriptions",
        "tenant-admin.first-pro-client",
    }
    assert clients_topic.status_code == 200
    assert clients_topic.json()["safe_navigation"] == {
        "route": "/admin/clients",
        "settings_category": None,
    }
    assert first_client_topic.status_code == 200
    first_client_data = first_client_topic.json()
    assert [
        first_client_data["safe_navigation"]["route"],
        *(link["route"] for link in first_client_data["safe_links"]),
    ] == [
        "/admin/catalog",
        "/admin/clients",
        "/admin/subscriptions",
    ]
    assert reminders_topic.status_code == 200
    assert reminders_topic.json()["safe_navigation"] == {
        "route": "/admin/settings",
        "settings_category": "reminders",
    }
    assert expiration_topic.status_code == 200
    assert expiration_topic.json()["safe_links"] == [
        {"route": "/admin/settings", "settings_category": "timezone"},
        {"route": "/admin/settings", "settings_category": "reminders"},
    ]

    tenant = (
        await db_session.execute(
            select(Tenant).where(Tenant.owner_user_id == active_tenant_user.id)
        )
    ).scalar_one()
    tenant.plan = "starter"
    await db_session.commit()

    starter_index = await client.get("/api/v1/help", headers=headers)
    starter_topic = await client.get(
        "/api/v1/help/topics/tenant-admin.clients", headers=headers
    )
    starter_search = await client.get(
        "/api/v1/help/search", params={"q": "canonical login"}, headers=headers
    )
    starter_reminders = await client.get(
        "/api/v1/help/topics/tenant-admin.reminders", headers=headers
    )
    starter_timezone = await client.get(
        "/api/v1/help/topics/tenant-admin.timezone", headers=headers
    )
    starter_expirations = await client.get(
        "/api/v1/help/topics/tenant-admin.subscription-expirations", headers=headers
    )
    starter_expirations_search = await client.get(
        "/api/v1/help/search", params={"q": "warning days"}, headers=headers
    )

    assert starter_index.status_code == 200
    assert "tenant-admin.clients" not in {
        topic["id"] for topic in starter_index.json()["topics"]
    }
    assert starter_topic.status_code == 404
    assert starter_reminders.status_code == 404
    assert starter_timezone.status_code == 404
    assert starter_expirations.status_code == 404
    assert starter_search.status_code == 200
    assert starter_search.json()["results"] == []
    assert starter_expirations_search.status_code == 200
    assert starter_expirations_search.json()["results"] == []


async def test_subscription_help_search_exposes_lifecycle_and_reminder_terms(
    client, active_tenant_user
):
    headers = await _login(client, "tenant", "tenant-password")

    lifecycle = await client.get(
        "/api/v1/help/search", params={"q": "reactivar"}, headers=headers
    )
    reminders = await client.get(
        "/api/v1/help/search", params={"q": "opt-in"}, headers=headers
    )

    assert lifecycle.status_code == 200
    assert "tenant-admin.subscriptions" in {
        result["id"] for result in lifecycle.json()["results"]
    }
    assert reminders.status_code == 200
    assert [result["id"] for result in reminders.json()["results"]] == [
        "tenant-admin.reminders",
    ]


async def test_help_topics_are_searchable_with_safe_cross_module_links(
    client, active_tenant_user
):
    headers = await _login(client, "tenant", "tenant-password")

    search_response = await client.get(
        "/api/v1/help/search", params={"q": "revocado"}, headers=headers
    )
    topic_response = await client.get(
        "/api/v1/help/topics/tenant-admin.activate-access-code-lookup",
        headers=headers,
    )

    assert search_response.status_code == 200
    assert [result["id"] for result in search_response.json()["results"]] == [
        "tenant-admin.mailbox"
    ]
    assert topic_response.status_code == 200
    assert topic_response.json()["safe_navigation"] == {
        "route": "/admin/settings",
        "settings_category": "code-services",
    }
    assert topic_response.json()["help_targets"] == ["admin.settings"]


async def test_help_search_returns_only_authorized_private_content(
    client, active_tenant_user
):
    headers = await _login(client, "tenant", "tenant-password")

    response = await client.get(
        "/api/v1/help/search", params={"q": "buzón"}, headers=headers
    )

    assert response.status_code == 200
    result_ids = [result["id"] for result in response.json()["results"]]
    assert "tenant-admin.dashboard" in result_ids
    result = next(
        result
        for result in response.json()["results"]
        if result["id"] == "tenant-admin.dashboard"
    )
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
        "tenant-admin.clients",
        "tenant-admin.dashboard",
        "tenant-admin.first-pro-client",
        "tenant-admin.subscription-expirations",
        "tenant-admin.subscriptions",
        "tenant-admin.timezone",
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
