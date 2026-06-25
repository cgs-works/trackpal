from __future__ import annotations

import datetime
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.core.security import get_password_hash
from app.models import Client, RefreshSession, Tenant, User

pytestmark = pytest.mark.asyncio


async def _create_tenant(client, auth_headers, **overrides):
    payload = {
        "full_name": "Plan Tenant",
        "email": "plan@example.com",
        "phone": "+12015550100",
        "username": "plan_tenant",
        "password": "tenant-password",
        "evolution_instance_name": "plan-tenant-instance",
        "plan": "starter",
    }
    payload.update(overrides)
    return await client.post("/api/v1/tenants/", json=payload, headers=auth_headers)


async def test_create_tenant_requires_plan(client, auth_headers):
    response = await _create_tenant(client, auth_headers, plan=None)
    assert response.status_code == 422
    assert "plan" in response.text.lower()


async def test_create_tenant_accepts_starter_plan(client, auth_headers, db_session):
    response = await _create_tenant(client, auth_headers)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["plan"] == "starter"

    row = await db_session.execute(select(Tenant).where(Tenant.id == uuid.UUID(body["id"])))
    tenant = row.scalar_one()
    assert tenant.plan == "starter"


async def test_update_tenant_preserves_plan_when_omitted(client, auth_headers):
    created = await _create_tenant(client, auth_headers, username="preserve_plan", phone="+12015550101", plan="pro")
    assert created.status_code == 201, created.text
    tenant_id = created.json()["id"]

    updated = await client.put(
        f"/api/v1/tenants/{tenant_id}",
        json={"full_name": "Renamed Tenant"},
        headers=auth_headers,
    )

    assert updated.status_code == 200, updated.text
    assert updated.json()["full_name"] == "Renamed Tenant"
    assert updated.json()["plan"] == "pro"


async def test_update_tenant_can_change_plan(client, auth_headers):
    created = await _create_tenant(client, auth_headers, username="change_plan", phone="+12015550102", plan="pro")
    assert created.status_code == 201, created.text

    updated = await client.put(
        f"/api/v1/tenants/{created.json()['id']}",
        json={"plan": "starter"},
        headers=auth_headers,
    )

    assert updated.status_code == 200, updated.text
    assert updated.json()["plan"] == "starter"


async def test_list_tenants_includes_plan(client, auth_headers, active_tenant_user):
    response = await client.get("/api/v1/tenants/", headers=auth_headers)
    assert response.status_code == 200, response.text
    assert response.json()["data"][0]["plan"] == "pro"


# ── Task 2: Auth responses, client auth block, Pro gate ──────────────────


async def _login(client, username: str, password: str) -> dict:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()


async def test_auth_responses_include_tenant_plan(client, auth_headers, active_tenant_user):
    tenant_login = await _login(client, "tenant", "tenant-password")
    assert tenant_login["tenant_plan"] == "pro"

    master_login = await _login(client, "master", "master-password")
    assert master_login["tenant_plan"] is None

    switch = await client.post(
        "/api/v1/auth/switch-tenant",
        json={"tenant_id": tenant_login["active_tenant_id"]},
        headers={"Authorization": f"Bearer {master_login['access_token']}"},
    )
    assert switch.status_code == 200, switch.text
    assert switch.json()["tenant_plan"] == "pro"


async def test_starter_tenant_gets_404_for_pro_endpoints(client, auth_headers, active_tenant_user):
    tenant = await client.put(
        f"/api/v1/tenants/{active_tenant_user.id}",
        json={"plan": "starter"},
        headers=auth_headers,
    )
    assert tenant.status_code == 200, tenant.text

    login = await _login(client, "tenant", "tenant-password")
    headers = {"Authorization": f"Bearer {login['access_token']}"}

    for path in ("/api/v1/clients", "/api/v1/catalog/services", "/api/v1/subscriptions", "/api/v1/subscription-settings"):
        response = await client.get(path, headers=headers)
        assert response.status_code == 404, path + response.text


async def test_master_switched_into_starter_bypasses_pro_gate(client, auth_headers, active_tenant_user):
    response = await client.put(
        f"/api/v1/tenants/{active_tenant_user.id}",
        json={"plan": "starter"},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text

    switched = await client.post(
        "/api/v1/auth/switch-tenant",
        json={"tenant_id": response.json()["id"]},
        headers=auth_headers,
    )
    assert switched.status_code == 200, switched.text
    headers = {"Authorization": f"Bearer {switched.json()['access_token']}"}

    pro_endpoint = await client.get("/api/v1/clients", headers=headers)
    assert pro_endpoint.status_code == 200, pro_endpoint.text


async def test_client_login_under_starter_returns_generic_401(client, db_session, auth_headers, active_tenant_user):
    result = await db_session.execute(select(Tenant).where(Tenant.owner_user_id == active_tenant_user.id))
    tenant = result.scalar_one()
    client_user = User(
        username=f"{tenant.client_prefix}_starter_client",
        password_hash=get_password_hash("client-password"),
        role="client",
    )
    db_session.add(client_user)
    await db_session.flush()
    db_session.add(
        Client(
            tenant_id=tenant.id,
            owner_user_id=client_user.id,
            full_name="Starter Client",
            username=client_user.username,
            phone="12015550199",
            is_active=True,
        )
    )
    await db_session.commit()

    changed = await client.put(
        f"/api/v1/tenants/{active_tenant_user.id}",
        json={"plan": "starter"},
        headers=auth_headers,
    )
    assert changed.status_code == 200, changed.text

    login = await client.post(
        "/api/v1/auth/login",
        json={"username": client_user.username, "password": "client-password"},
    )
    assert login.status_code == 401
    assert login.json()["detail"] == "Invalid credentials or account deactivated"


# ── Task 3: Starter timezone behavior ──────────────────────────────────


async def test_starter_tenant_settings_hides_and_blocks_timezone(client, auth_headers, active_tenant_user):
    changed = await client.put(
        f"/api/v1/tenants/{active_tenant_user.id}",
        json={"plan": "starter"},
        headers=auth_headers,
    )
    assert changed.status_code == 200, changed.text
    login = await _login(client, "tenant", "tenant-password")
    headers = {"Authorization": f"Bearer {login['access_token']}"}

    read = await client.get("/api/v1/tenant-settings", headers=headers)
    assert read.status_code == 200, read.text
    assert read.json()["locale"] in {"en", "es"}
    assert read.json()["timezone"] is None

    locale_update = await client.put("/api/v1/tenant-settings", json={"locale": "es"}, headers=headers)
    assert locale_update.status_code == 200, locale_update.text
    assert locale_update.json()["locale"] == "es"
    assert locale_update.json()["timezone"] is None

    timezone_update = await client.put("/api/v1/tenant-settings", json={"timezone": "America/Bogota"}, headers=headers)
    assert timezone_update.status_code == 404


async def test_master_switched_starter_can_see_timezone(client, auth_headers, active_tenant_user):
    changed = await client.put(
        f"/api/v1/tenants/{active_tenant_user.id}",
        json={"plan": "starter"},
        headers=auth_headers,
    )
    assert changed.status_code == 200, changed.text
    switched = await client.post(
        "/api/v1/auth/switch-tenant",
        json={"tenant_id": changed.json()["id"]},
        headers=auth_headers,
    )
    headers = {"Authorization": f"Bearer {switched.json()['access_token']}"}

    response = await client.get("/api/v1/tenant-settings", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["timezone"] == "UTC"


# ── Task 4: Downgrade side effects (pro → starter) ────────────────────


async def test_downgrade_pro_to_starter_triggers_side_effects(client, auth_headers, db_session, active_tenant_user):
    """Verify pro→downgrade revokes sessions and clears Redis admin session."""
    result = await db_session.execute(select(Tenant).where(Tenant.owner_user_id == active_tenant_user.id))
    tenant = result.scalar_one()

    # Set evolution_instance_name so the close path is triggered
    tenant.evolution_instance_name = "downgrade-test-instance"
    await db_session.commit()

    client_user = User(
        username=f"{tenant.client_prefix}_downgrade_client",
        password_hash=get_password_hash("client-password"),
        role="client",
    )
    db_session.add(client_user)
    await db_session.flush()
    db_session.add(
        Client(
            tenant_id=tenant.id,
            owner_user_id=client_user.id,
            full_name="Downgrade Client",
            username=client_user.username,
            phone="12015550201",
            is_active=True,
        )
    )
    db_session.add(
        RefreshSession(
            user_id=client_user.id,
            refresh_token_hash="hash",
            expires_at=datetime.datetime.now(datetime.timezone.utc).replace(year=2099),
            revoked=False,
        )
    )
    await db_session.commit()

    fake_manager = AsyncMock()
    fake_evo_close = AsyncMock()
    with (
        patch("app.services.tenant_service.mutations.get_redis_manager", return_value=fake_manager),
        patch("app.services.tenant_service.mutations.evolution_client.close_chat_session", new=fake_evo_close),
    ):
        response = await client.put(
            f"/api/v1/tenants/{active_tenant_user.id}",
            json={"plan": "starter"},
            headers=auth_headers,
        )

    assert response.status_code == 200, response.text
    assert response.json()["plan"] == "starter"

    # Session revocation verified
    session_row = await db_session.execute(select(RefreshSession).where(RefreshSession.user_id == client_user.id))
    assert session_row.scalar_one().revoked is True

    # Redis session clear was attempted (active_tenant_user has whatsapp_phone set)
    fake_manager.execute.assert_awaited()

    # Evolution close was attempted
    fake_evo_close.assert_awaited_once()

    # Tenant can still log in and sees starter plan
    tenant_login = await client.post(
        "/api/v1/auth/login",
        json={"username": "tenant", "password": "tenant-password"},
    )
    assert tenant_login.status_code == 200
    assert tenant_login.json()["tenant_plan"] == "starter"


# ── Task 5: Dashboard payload for Starter / Pro ───────────────────────


async def test_dashboard_returns_starter_common_widgets(client, auth_headers, active_tenant_user):
    changed = await client.put(
        f"/api/v1/tenants/{active_tenant_user.id}",
        json={"plan": "starter"},
        headers=auth_headers,
    )
    assert changed.status_code == 200, changed.text
    login = await _login(client, "tenant", "tenant-password")
    headers = {"Authorization": f"Bearer {login['access_token']}"}

    response = await client.get("/api/v1/dashboard", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["tenant_plan"] == "starter"
    assert body["mailbox_status"] in {"missing", "disconnected", "connected", "error", "revoked"}
    assert body["enabled_code_services"] == []
    assert body["access_control_count"] == 0
    assert body["active_clients"] is None
    assert body["catalog_services"] is None
    assert body["active_subscriptions"] is None
    assert body["subscriptions_expiring_soon"] is None


async def test_dashboard_returns_pro_metrics(client, active_tenant_user):
    login = await _login(client, "tenant", "tenant-password")
    headers = {"Authorization": f"Bearer {login['access_token']}"}

    response = await client.get("/api/v1/dashboard", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["tenant_plan"] == "pro"
    assert isinstance(body["active_clients"], int)
    assert isinstance(body["catalog_services"], int)
    assert isinstance(body["active_subscriptions"], int)
    assert isinstance(body["subscriptions_expiring_soon"], int)


# ── Task 7: WhatsApp Starter/Pro menus, mailbox gate, and silent blocks ──


class _FakeRedis:
    def __init__(self):
        self._store: dict[str, str] = {}
        self._ttls: dict[str, int] = {}

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None, keepttl: bool = False) -> None:
        self._store[key] = value
        if ex is not None:
            self._ttls[key] = ex
        elif not keepttl:
            self._ttls.pop(key, None)

    async def expire(self, key: str, time: int) -> int:
        if key in self._store:
            self._ttls[key] = time
            return 1
        return 0

    async def delete(self, key: str) -> int:
        self._ttls.pop(key, None)
        return 1 if self._store.pop(key, None) is not None else 0

    async def lpush(self, key: str, value: str) -> int:
        self._store[key] = value
        return 1


class _FakeManager:
    def __init__(self, *, used_backup: bool = False, fail_on_execute: bool = False):
        from app.core.redis_client import RedisUnavailableError
        self._redis = _FakeRedis()
        self._used_backup = used_backup
        self._fail_on_execute = fail_on_execute
        self._RedisUnavailableError = RedisUnavailableError

    @property
    def used_backup(self) -> bool:
        return self._used_backup

    async def execute(self, operation_name, async_callable):
        if self._fail_on_execute:
            raise self._RedisUnavailableError("Both Redis stores unavailable")
        return await async_callable(self._redis)


async def test_whatsapp_starter_menu_is_reduced(client, auth_headers, active_tenant_user):
    """Starter tenant sees reduced menu: Profile, Codigo, Access Control, Help — no Clients/Catalog/Subscriptions."""
    from app.core.config import settings

    changed = await client.put(
        f"/api/v1/tenants/{active_tenant_user.id}",
        json={"plan": "starter"},
        headers=auth_headers,
    )
    assert changed.status_code == 200, changed.text

    fake_mgr = _FakeManager()
    with patch("app.api.v1.endpoints.integrations.console.get_redis_manager", return_value=fake_mgr):
        response = await client.post(
            "/api/v1/integrations/n8n/console",
            json={"phone": "+12015550002", "message": "menu", "instance": changed.json()["evolution_instance_name"]},
            headers={"X-API-Key": settings.n8n_api_key},
        )
    assert response.status_code == 200, response.text
    reply = response.json()["reply"]
    assert "Buscar" in reply or "Find Access Code" in reply
    assert "Control" in reply or "Access Control" in reply
    assert "Clientes" not in reply and "Clients" not in reply
    assert "Suscripciones" not in reply and "Subscriptions" not in reply


async def test_whatsapp_blocked_identity_receives_no_reply(client, db_session, active_tenant_user):
    """A blocked identity always receives no_reply=true."""
    from app.core.config import settings
    from sqlalchemy import select as sa_select
    from app.models import BlockedClient, Tenant

    row = await db_session.execute(sa_select(Tenant).where(Tenant.owner_user_id == active_tenant_user.id))
    tenant = row.scalar_one()

    if not tenant.evolution_instance_name:
        tenant.evolution_instance_name = "plan-tenant-instance"
        await db_session.commit()

    db_session.add(BlockedClient(tenant_id=tenant.id, phone="12015550999", is_active=True))
    await db_session.commit()

    fake_mgr = _FakeManager()
    with patch("app.api.v1.endpoints.integrations.console.get_redis_manager", return_value=fake_mgr):
        response = await client.post(
            "/api/v1/integrations/n8n/console",
            json={"phone": "+12015550999", "message": "codigo", "instance": tenant.evolution_instance_name},
            headers={"X-API-Key": settings.n8n_api_key},
        )
    assert response.status_code == 200, response.text
    assert response.json()["no_reply"] is True
    assert response.json()["reply"] == ""


async def test_whatsapp_starter_client_denied_non_codigo(client, db_session, active_tenant_user):
    """Registered client under Starter gets access_denied for non-codigo messages."""
    from app.core.config import settings
    from sqlalchemy import select as sa_select
    from app.models import Client, Tenant, User
    from app.core.security import get_password_hash

    row = await db_session.execute(sa_select(Tenant).where(Tenant.owner_user_id == active_tenant_user.id))
    tenant = row.scalar_one()

    if not tenant.evolution_instance_name:
        tenant.evolution_instance_name = "plan-tenant-instance"
        await db_session.commit()

    # Set tenant to starter
    changed = await client.put(
        f"/api/v1/tenants/{active_tenant_user.id}",
        json={"plan": "starter"},
        headers=auth_headers,
    )
    assert changed.status_code == 200, changed.text

    # Create a registered client under this tenant
    client_user = User(
        username=f"{tenant.client_prefix}_starter_wa_client",
        password_hash=get_password_hash("client-password"),
        role="client",
    )
    db_session.add(client_user)
    await db_session.flush()
    db_session.add(
        Client(
            tenant_id=tenant.id,
            owner_user_id=client_user.id,
            full_name="Starter WA Client",
            username=client_user.username,
            phone="12015550555",
            is_active=True,
        )
    )
    await db_session.commit()

    fake_mgr = _FakeManager()
    with patch("app.api.v1.endpoints.integrations.console.get_redis_manager", return_value=fake_mgr):
        response = await client.post(
            "/api/v1/integrations/n8n/console",
            json={"phone": "+12015550555", "message": "menu", "instance": tenant.evolution_instance_name},
            headers={"X-API-Key": settings.n8n_api_key},
        )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "closed"
    assert "denied" in body["reply"].lower() or "denegado" in body["reply"].lower()


# ── Task 8: Subscription automation ignores Starter tenants ────────────


async def test_subscription_cleanup_ignores_starter_tenant(client, db_session, auth_headers, active_tenant_user):
    """Cleanup must not mutate subscriptions belonging to Starter tenants."""
    from datetime import datetime, timedelta, timezone
    from app.models import Client, Plan, Service, Subscription
    from app.services.subscription_job_service import SubscriptionJobService

    row = await db_session.execute(select(Tenant).where(Tenant.owner_user_id == active_tenant_user.id))
    tenant = row.scalar_one()
    tenant.plan = "starter"
    client_user = User(username="cleanup_client", password_hash=get_password_hash("x-password"), role="client")
    db_session.add(client_user)
    await db_session.flush()
    c = Client(tenant_id=tenant.id, owner_user_id=client_user.id, full_name="Cleanup Client", username="cleanup_client", is_active=True)
    s = Service(tenant_id=tenant.id, name="Netflix")
    db_session.add_all([c, s])
    await db_session.flush()
    p = Plan(tenant_id=tenant.id, service_id=s.id, name="Monthly")
    db_session.add(p)
    await db_session.flush()
    sub = Subscription(
        tenant_id=tenant.id,
        client_id=c.id,
        service_id=s.id,
        plan_id=p.id,
        streaming_email="viewer@example.com",
        duration_type="1_month",
        starts_at=datetime.now(timezone.utc) - timedelta(days=40),
        expires_at=datetime.now(timezone.utc) - timedelta(days=2),
        status="active",
    )
    db_session.add(sub)
    await db_session.commit()

    results = await SubscriptionJobService().run_cleanup(db_session)
    await db_session.refresh(sub)
    assert sub.status == "active"
    assert results == []
