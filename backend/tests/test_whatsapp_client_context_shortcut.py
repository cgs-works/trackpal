"""Tests for WhatsApp client context shortcut behavior.

This module houses repository/model contract tests that the WhatsApp
client shortcut flow relies on. The first test guards the renamed
`blocked_clients` model so the shortcut path can confidently import
the new symbols.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.i18n import t
from app.models import Client, Service, Tenant, User

pytestmark = pytest.mark.asyncio

ENDPOINT = "/api/v1/integrations/n8n/console"
TEST_INSTANCE = "test-tenant-instance"


# ---------------------------------------------------------------------------
# Fakes for Redis-dependent endpoint tests
# ---------------------------------------------------------------------------


class _FakeRedis:
    """Minimal in-memory dict store for endpoint test fakes."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}
        self._ttls: dict[str, int] = {}

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def set(
        self, key: str, value: str, ex: int | None = None, keepttl: bool = False
    ) -> None:
        self._store[key] = value
        if ex is not None:
            self._ttls[key] = ex
        elif not keepttl:
            self._ttls.pop(key, None)
        # keepttl=True: leave existing TTL untouched

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
    """Duck-typed connection manager for endpoint test isolation."""

    def __init__(
        self,
        *,
        used_backup: bool = False,
        fail_on_execute: bool = False,
    ) -> None:
        from app.core.redis_client import RedisUnavailableError

        self._redis = _FakeRedis()
        self._used_backup = used_backup
        self._fail_on_execute = fail_on_execute
        self._RedisUnavailableError = RedisUnavailableError

    @property
    def used_backup(self) -> bool:
        return self._used_backup

    async def execute(self, operation_name: str, async_callable: Any) -> Any:
        if self._fail_on_execute:
            raise self._RedisUnavailableError("Both Redis stores unavailable")
        return await async_callable(self._redis)


async def _setup_tenant_with_instance(db_session, active_tenant_user) -> Tenant:
    """Set up a tenant with an Evolution instance and Spanish locale."""
    result = await db_session.execute(
        select(Tenant).where(Tenant.owner_user_id == active_tenant_user.id)
    )
    tenant = result.scalar_one_or_none()
    assert tenant is not None
    tenant.evolution_instance_name = TEST_INSTANCE
    tenant.locale = "es"
    await db_session.commit()
    return tenant


# ---------------------------------------------------------------------------
# Context helpers
# ---------------------------------------------------------------------------


async def _create_context_client(
    db_session,
    tenant: Tenant,
    *,
    phone: str | None,
    is_active: bool,
    full_name: str,
    username: str,
) -> Client:
    ctx_user = User(username=f"{username}_user", password_hash="dummy-hash", role="client")
    db_session.add(ctx_user)
    await db_session.flush()
    ctx_client = Client(
        tenant_id=tenant.id,
        owner_user_id=ctx_user.id,
        full_name=full_name,
        username=username,
        phone=phone,
        is_active=is_active,
    )
    db_session.add(ctx_client)
    await db_session.commit()
    return ctx_client


async def _seed_shortcut_context(
    fake_mgr: _FakeManager,
    admin_phone_digits: str,
    *,
    target_phone: str | None,
    target_lid: str | None = None,
    step: str = "menu",
    ttl: int = 123,
) -> str:
    session = {
        "phone": admin_phone_digits,
        "flow": "client_shortcut",
        "step": step,
        "selected_tenant_id": None,
        "temp_data": {
            "target_phone": target_phone,
            "target_lid": target_lid,
            "target_jid": f"{target_phone or target_lid or 'unknown'}@s.whatsapp.net",
            "admin_jid": f"{admin_phone_digits}@s.whatsapp.net",
        },
        "selection_map": {},
    }
    ctx_key = f"wa:client_ctx:{admin_phone_digits}"
    await fake_mgr._redis.set(ctx_key, json.dumps(session), ex=ttl)
    return ctx_key


# ---------------------------------------------------------------------------
# Repository / model contract tests
# ---------------------------------------------------------------------------


def test_blocked_clients_repository_uses_new_table_name() -> None:
    """The renamed repository's model must bind to the new table name.

    This guards the migration: the SQLAlchemy ``__tablename__`` must be
    ``blocked_clients`` so the rename migration has something to point at.
    """
    from app.models.blocked_client import BlockedClient

    assert BlockedClient.__tablename__ == "blocked_clients"


def test_blocked_clients_repository_module_is_importable() -> None:
    """The new repository module must exist and expose the expected API."""
    from app.repositories import blocked_clients_repository

    expected = {"create", "list_active", "find_active", "unblock", "clear_identity"}
    assert expected.issubset(set(dir(blocked_clients_repository)))


def test_models_package_exports_blocked_client() -> None:
    """The models package should re-export the renamed ``BlockedClient``."""
    from app import models

    assert hasattr(models, "BlockedClient")
    assert "BlockedClient" in models.__all__
    assert "ClientMessagingBlock" not in models.__all__


def test_client_context_i18n_keys_exist_in_en_and_es():
    params = {"identity": "34123456789", "client_name": "Ana", "status": "Activo", "phone": "34123456789", "phone_line": "Phone: 34123456789\n"}
    keys = [
        "wa.tenant.client_context.menu.unregistered_with_phone",
        "wa.tenant.client_context.menu.unregistered_lid_only",
        "wa.tenant.client_context.menu.blocked_with_phone",
        "wa.tenant.client_context.menu.blocked_lid_only",
        "wa.tenant.client_context.menu.active",
        "wa.tenant.client_context.menu.inactive",
        "wa.tenant.client_context.closed",
        "wa.tenant.client_context.collision",
        "wa.tenant.client_context.invalid_option",
        "wa.tenant.client_context.create.phone_prefilled",
        "wa.tenant.client_context.create.phone_prompt",
        "wa.tenant.client_context.block_access.success",
        "wa.tenant.client_context.unblock_access.success",
        "wa.tenant.client_context.phone_line",
        "wa.tenant.client_context.active.delete_blocked",
        "wa.tenant.client_context.inactive.detail.options",
    ]
    for locale in ("en", "es"):
        for key in keys:
            rendered = t(locale, key, **params)
            assert rendered != key
            assert "Gestion del cliente" in rendered or "Client management" in rendered or key.endswith(("closed", "collision", "invalid_option", "success", "phone_prompt", "phone_prefilled", "phone_line", "delete_blocked", "detail.options"))


# ---------------------------------------------------------------------------
# Real contextual menu on /menu start
# ---------------------------------------------------------------------------


async def test_from_me_shortcut_renders_contextual_menu_for_unregistered(
    client, db_session, active_tenant_user
):
    """`from_me` shortcut against an external phone must render the i18n
    contextual menu (unregistered variant) — not the legacy generic
    message. The reply must include the contextual menu markers and
    reply_to for the admin's private chat.
    """
    tenant = await _setup_tenant_with_instance(db_session, active_tenant_user)
    admin_phone = tenant.whatsapp_phone  # "+12015550002"
    target_external_phone = "+12015559999"

    fake_mgr = _FakeManager(used_backup=False)
    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={
                "phone": "",
                "message": "/menu",
                "instance": TEST_INSTANCE,
                "from_me": True,
                "admin_phone": admin_phone,
                "admin_jid": "12015550002@s.whatsapp.net",
                "target_phone": target_external_phone,
                "target_jid": "12015559999@s.whatsapp.net",
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )

    assert response.status_code == 200
    body = response.json()

    # The reply must be the i18n-rendered contextual menu, not the legacy
    # generic "Contexto de cliente iniciado" message.
    assert "reply" in body
    reply = body["reply"]
    assert "Contexto de cliente iniciado" not in reply
    # Spanish (tenant.locale = "es") contextual menu markers.
    assert "Gestion del cliente" in reply
    assert "Crear cliente para este numero" in reply
    # reply_to must point at the admin's private JID.
    assert body.get("reply_to") == "12015550002@s.whatsapp.net"


async def test_from_me_self_menu_routes_to_tenant_console(
    client, db_session, active_tenant_user
):
    """from_me /menu in admin's own chat must route to Tenant console."""
    from app.core.config import settings
    from app.models import Tenant
    from sqlalchemy import select

    result = await db_session.execute(
        select(Tenant).where(Tenant.owner_user_id == active_tenant_user.id)
    )
    tenant = result.scalar_one_or_none()
    assert tenant is not None
    tenant.evolution_instance_name = "test-tenant-instance"
    tenant.locale = "es"
    await db_session.commit()

    admin_phone = tenant.whatsapp_phone
    admin_jid = f"{admin_phone}@s.whatsapp.net"

    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=_FakeManager(used_backup=False),
    ):
        response = await client.post(
            "/api/v1/integrations/n8n/console",
            json={
                "phone": "",
                "message": "/menu",
                "instance": "test-tenant-instance",
                "from_me": True,
                "admin_phone": admin_phone,
                "admin_jid": admin_jid,
                "target_jid": admin_jid,  # self-target
                "target_phone": admin_phone,  # self-target
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )

    assert response.status_code == 200
    body = response.json()
    # Must NOT show the client context menu
    assert "Gestion del cliente" not in body.get("reply", "")


async def test_context_close_cleans_redis_session(
    client, db_session, active_tenant_user
):
    """Closing a client context via option 0 must delete the Redis
    session key so future /menu triggers don't collide."""
    tenant = await _setup_tenant_with_instance(db_session, active_tenant_user)
    admin_phone = tenant.whatsapp_phone
    admin_jid = f"{admin_phone}@s.whatsapp.net"
    target_external_phone = "+12015559999"
    ctx_key = f"wa:client_ctx:{admin_phone}"

    fake_mgr = _FakeManager(used_backup=False)

    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        # First /menu creates the context
        resp1 = await client.post(
            "/api/v1/integrations/n8n/console",
            json={
                "phone": admin_phone,
                "message": "/menu",
                "instance": "test-tenant-instance",
                "from_me": True,
                "admin_phone": admin_phone,
                "admin_jid": admin_jid,
                "target_phone": target_external_phone,
                "target_jid": f"{target_external_phone}@s.whatsapp.net",
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )
        assert resp1.status_code == 200
        assert "close_jid" in resp1.json()
        close_jid = resp1.json()["close_jid"]

        # Send option 0 to close (simulating admin response in private chat)
        resp2 = await client.post(
            "/api/v1/integrations/n8n/console",
            json={
                "phone": admin_phone,
                "message": "0",
                "instance": "test-tenant-instance",
                "from_me": True,
                "admin_phone": admin_phone,
                "admin_jid": close_jid,
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )
        assert resp2.status_code == 200

    # After close, the Redis key must be gone
    remaining = await fake_mgr._redis.get(ctx_key)
    assert remaining is None, "Redis session key should be deleted on close"


async def test_active_context_invalid_input_uses_i18n(
    client, db_session, active_tenant_user
):
    """Invalid input in context menu must use i18n key."""
    from app.core.config import settings
    from app.models import Tenant
    from sqlalchemy import select
    from unittest.mock import patch

    result = await db_session.execute(
        select(Tenant).where(Tenant.owner_user_id == active_tenant_user.id)
    )
    tenant = result.scalar_one_or_none()
    assert tenant is not None
    tenant.evolution_instance_name = "test-tenant-instance"
    tenant.locale = "es"
    await db_session.commit()

    admin_phone = tenant.whatsapp_phone
    admin_jid = f"{admin_phone}@s.whatsapp.net"

    fake_mgr = _FakeManager(used_backup=False)
    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        await client.post(
            "/api/v1/integrations/n8n/console",
            json={
                "phone": admin_phone,
                "message": "/menu",
                "instance": "test-tenant-instance",
                "from_me": True,
                "admin_phone": admin_phone,
                "admin_jid": admin_jid,
                "target_phone": "+34999999999",
                "target_jid": "34999999999@s.whatsapp.net",
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )

        # Now send invalid input via normal console path
        resp = await client.post(
            "/api/v1/integrations/n8n/console",
            json={
                "phone": admin_phone,
                "message": "texto invalido",
                "instance": "test-tenant-instance",
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data.get("reply_to") == admin_jid
    # Must NOT route to Tenant console (no "Trackpal" in reply)
    assert "Trackpal" not in data.get("reply", "")
    # Must use the i18n invalid_option text
    assert "Opcion invalida" in data.get("reply", "")


# ---------------------------------------------------------------------------
# Active root menu regressions (Task 1 TPL-7)
# ---------------------------------------------------------------------------


async def test_active_menu_option_2_enters_edit_flow(
    client, db_session, active_tenant_user
):
    """Option 2 on active root menu must enter edit field selection."""
    tenant = await _setup_tenant_with_instance(db_session, active_tenant_user)
    admin_phone_digits = tenant.whatsapp_phone.lstrip("+")
    await _create_context_client(
        db_session,
        tenant,
        phone="12015559999",
        is_active=True,
        full_name="Context Active Client",
        username="tna01_ctx_active",
    )
    fake_mgr = _FakeManager(used_backup=False)
    await _seed_shortcut_context(fake_mgr, admin_phone_digits, target_phone="12015559999")

    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={"phone": tenant.whatsapp_phone, "message": "2", "instance": TEST_INSTANCE},
            headers={"X-API-Key": settings.n8n_api_key},
        )

    assert response.status_code == 200
    reply = response.json()["reply"]
    assert "Que campo desea editar" in reply
    assert "Nombre completo" in reply
    assert "Nombre de usuario" in reply
    assert "Seleccione un *servicio*" not in reply


async def test_active_menu_option_3_starts_subscription_flow_and_clears_shortcut(
    client, db_session, active_tenant_user
):
    """Option 3 on active root menu must start subscription creation and clear shortcut."""
    tenant = await _setup_tenant_with_instance(db_session, active_tenant_user)
    admin_phone_digits = tenant.whatsapp_phone.lstrip("+")
    await _create_context_client(
        db_session,
        tenant,
        phone="12015559998",
        is_active=True,
        full_name="Subscription Client",
        username="tna01_ctx_subscription",
    )
    db_session.add(Service(tenant_id=tenant.id, name="Streaming Pro"))
    await db_session.commit()

    fake_mgr = _FakeManager(used_backup=False)
    ctx_key = await _seed_shortcut_context(fake_mgr, admin_phone_digits, target_phone="12015559998")

    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ), patch(
        "app.core.redis_client.get_redis_manager",
        return_value=fake_mgr,
    ), patch(
        "app.core.redis_client.lifespan.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={"phone": tenant.whatsapp_phone, "message": "3", "instance": TEST_INSTANCE},
            headers={"X-API-Key": settings.n8n_api_key},
        )

    assert response.status_code == 200
    reply = response.json()["reply"]
    assert "suscripcion" in reply.lower()
    assert "Streaming Pro" in reply
    assert "[1]" in reply  # bracket service notation
    assert "*Cliente:*" in reply
    assert "*Telefono:*" in reply
    assert "Subscription Client" in reply
    assert "12015559998" in reply
    # Nav: only 9 (back) and 0 (cancel) appear since only 1 service (<=7)
    assert "9" in reply  # back nav
    assert "0" in reply  # cancel nav
    # 8 (next) is not shown with <=7 services
    assert await fake_mgr._redis.get(ctx_key) is None

    session_raw = await fake_mgr._redis.get(f"session:admin:{admin_phone_digits}")
    assert session_raw is not None
    session = json.loads(session_raw)
    assert session["flow"] == "subscriptions"
    assert session["step"] == "create_service"
    assert session["temp_data"]["client_name"] == "Subscription Client"
    assert "starts_at" in session["temp_data"]  # needed by _build_subscription_create_confirm


async def test_active_menu_option_5_blocks_delete_and_keeps_active_menu(
    client, db_session, active_tenant_user
):
    """Option 5 on active root menu must block deletion and stay in active_menu."""
    tenant = await _setup_tenant_with_instance(db_session, active_tenant_user)
    admin_phone_digits = tenant.whatsapp_phone.lstrip("+")
    await _create_context_client(
        db_session,
        tenant,
        phone="12015559997",
        is_active=True,
        full_name="Protected Active Client",
        username="tna01_ctx_protected",
    )
    fake_mgr = _FakeManager(used_backup=False)
    ctx_key = await _seed_shortcut_context(
        fake_mgr,
        admin_phone_digits,
        target_phone="12015559997",
        ttl=123,
    )

    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={"phone": tenant.whatsapp_phone, "message": "5", "instance": TEST_INSTANCE},
            headers={"X-API-Key": settings.n8n_api_key},
        )

    assert response.status_code == 200
    reply = response.json()["reply"]
    assert "No se puede eliminar" in reply
    assert "Desactivar cliente" in reply
    assert "Eliminar cliente" in reply
    assert fake_mgr._redis._ttls[ctx_key] == 300

    ctx_data = json.loads(await fake_mgr._redis.get(ctx_key))
    assert ctx_data["step"] == "active_menu"


async def test_active_menu_invalid_input_rerenders_full_menu_and_refreshes_ttl(
    client, db_session, active_tenant_user
):
    """Invalid input on active root menu must re-render full menu and refresh TTL."""
    tenant = await _setup_tenant_with_instance(db_session, active_tenant_user)
    admin_phone_digits = tenant.whatsapp_phone.lstrip("+")
    await _create_context_client(
        db_session,
        tenant,
        phone="12015559996",
        is_active=True,
        full_name="Invalid Active Client",
        username="tna01_ctx_invalid",
    )
    fake_mgr = _FakeManager(used_backup=False)
    ctx_key = await _seed_shortcut_context(
        fake_mgr,
        admin_phone_digits,
        target_phone="12015559996",
        ttl=123,
    )

    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={"phone": tenant.whatsapp_phone, "message": "9", "instance": TEST_INSTANCE},
            headers={"X-API-Key": settings.n8n_api_key},
        )

    assert response.status_code == 200
    reply = response.json()["reply"]
    assert "Opcion invalida" in reply
    assert "Editar cliente" in reply
    assert "Crear suscripcion" in reply
    assert "Desactivar cliente" in reply
    assert "Eliminar cliente" in reply
    assert fake_mgr._redis._ttls[ctx_key] == 300


# ---------------------------------------------------------------------------
# Active detail/edit/deactivate screen re-rendering (Task 2 TPL-7)
# ---------------------------------------------------------------------------


async def test_active_detail_back_rerenders_active_root_menu(
    client, db_session, active_tenant_user
):
    """Back from active detail must re-render the full active root menu."""
    tenant = await _setup_tenant_with_instance(db_session, active_tenant_user)
    admin_phone_digits = tenant.whatsapp_phone.lstrip("+")
    await _create_context_client(
        db_session,
        tenant,
        phone="12015559995",
        is_active=True,
        full_name="Back Active Client",
        username="tna01_ctx_back",
    )
    fake_mgr = _FakeManager(used_backup=False)
    await _seed_shortcut_context(
        fake_mgr,
        admin_phone_digits,
        target_phone="12015559995",
        step="active_detail",
    )

    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={"phone": tenant.whatsapp_phone, "message": "9", "instance": TEST_INSTANCE},
            headers={"X-API-Key": settings.n8n_api_key},
        )

    reply = response.json()["reply"]
    assert "Editar cliente" in reply
    assert "Crear suscripcion" in reply
    assert "Desactivar cliente" in reply


async def test_active_edit_field_back_returns_full_active_detail(
    client, db_session, active_tenant_user
):
    """Back from edit field must return the full active detail screen."""
    tenant = await _setup_tenant_with_instance(db_session, active_tenant_user)
    admin_phone_digits = tenant.whatsapp_phone.lstrip("+")
    await _create_context_client(
        db_session,
        tenant,
        phone="12015559994",
        is_active=True,
        full_name="Editable Active Client",
        username="tna01_ctx_edit_back",
    )
    fake_mgr = _FakeManager(used_backup=False)
    await _seed_shortcut_context(
        fake_mgr,
        admin_phone_digits,
        target_phone="12015559994",
        step="active_edit_field",
    )

    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={"phone": tenant.whatsapp_phone, "message": "9", "instance": TEST_INSTANCE},
            headers={"X-API-Key": settings.n8n_api_key},
        )

    reply = response.json()["reply"]
    assert "Editable Active Client" in reply
    assert "Usuario:" in reply
    assert "1 Editar datos" in reply
    assert "2 Desactivar" in reply


async def test_active_edit_success_shows_updated_detail_screen(
    client, db_session, active_tenant_user
):
    """Successful edit must show the updated detail screen with new values."""
    tenant = await _setup_tenant_with_instance(db_session, active_tenant_user)
    admin_phone_digits = tenant.whatsapp_phone.lstrip("+")
    ctx_client = await _create_context_client(
        db_session,
        tenant,
        phone="12015559993",
        is_active=True,
        full_name="Old Active Name",
        username="tna01_ctx_edit_success",
    )
    fake_mgr = _FakeManager(used_backup=False)
    ctx_key = await _seed_shortcut_context(
        fake_mgr,
        admin_phone_digits,
        target_phone="12015559993",
        step="active_edit_value",
    )
    raw = json.loads(await fake_mgr._redis.get(ctx_key))
    raw["temp_data"]["client_id"] = str(ctx_client.id)
    raw["temp_data"]["edit_field"] = "full_name"
    await fake_mgr._redis.set(ctx_key, json.dumps(raw), ex=300)

    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={"phone": tenant.whatsapp_phone, "message": "New Active Name", "instance": TEST_INSTANCE},
            headers={"X-API-Key": settings.n8n_api_key},
        )

    reply = response.json()["reply"]
    assert "actualizado correctamente" in reply.lower()
    assert "New Active Name" in reply
    assert "1 Editar datos" in reply
    assert "2 Desactivar" in reply


async def test_active_menu_option_4_opens_deactivate_confirm(
    client, db_session, active_tenant_user
):
    """Option 4 on active root menu must open deactivation confirm."""
    tenant = await _setup_tenant_with_instance(db_session, active_tenant_user)
    admin_phone_digits = tenant.whatsapp_phone.lstrip("+")
    ctx_client = await _create_context_client(
        db_session,
        tenant,
        phone="12015559992",
        is_active=True,
        full_name="Deactivate Active Client",
        username="tna01_ctx_deactivate",
    )
    fake_mgr = _FakeManager(used_backup=False)
    ctx_key = await _seed_shortcut_context(
        fake_mgr,
        admin_phone_digits,
        target_phone="12015559992",
        step="menu",
    )
    raw = json.loads(await fake_mgr._redis.get(ctx_key))
    raw["temp_data"]["client_id"] = str(ctx_client.id)
    await fake_mgr._redis.set(ctx_key, json.dumps(raw), ex=300)

    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={"phone": tenant.whatsapp_phone, "message": "4", "instance": TEST_INSTANCE},
            headers={"X-API-Key": settings.n8n_api_key},
        )

    reply = response.json()["reply"]
    assert "desactivar" in reply.lower()
    assert "CONFIRMAR" in reply


async def test_active_deactivate_confirm_success_shows_inactive_menu(
    client, db_session, active_tenant_user
):
    """Successful deactivation must show the inactive root menu."""
    tenant = await _setup_tenant_with_instance(db_session, active_tenant_user)
    admin_phone_digits = tenant.whatsapp_phone.lstrip("+")
    ctx_client = await _create_context_client(
        db_session,
        tenant,
        phone="12015559992",
        is_active=True,
        full_name="Deactivate Active Client",
        username="tna01_ctx_deactivate",
    )
    fake_mgr = _FakeManager(used_backup=False)
    ctx_key = await _seed_shortcut_context(
        fake_mgr,
        admin_phone_digits,
        target_phone="12015559992",
        step="active_deactivate_confirm",
    )
    raw = json.loads(await fake_mgr._redis.get(ctx_key))
    raw["temp_data"]["client_id"] = str(ctx_client.id)
    await fake_mgr._redis.set(ctx_key, json.dumps(raw), ex=300)

    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={"phone": tenant.whatsapp_phone, "message": "CONFIRMAR", "instance": TEST_INSTANCE},
            headers={"X-API-Key": settings.n8n_api_key},
        )

    reply = response.json()["reply"]
    assert "desactivado" in reply.lower()
    assert "Reactivar cliente" in reply
    assert "Eliminar cliente" in reply


# ---------------------------------------------------------------------------
# Inactive root menu regressions (Task 3 TPL-7)
# ---------------------------------------------------------------------------


async def test_inactive_menu_option_1_shows_detail(
    client, db_session, active_tenant_user
):
    """Option 1 on inactive root menu must show the inactive detail screen."""
    tenant = await _setup_tenant_with_instance(db_session, active_tenant_user)
    admin_phone_digits = tenant.whatsapp_phone.lstrip("+")
    await _create_context_client(
        db_session,
        tenant,
        phone="12015559991",
        is_active=False,
        full_name="Inactive Detail Client",
        username="tna01_ctx_inactive_detail",
    )
    fake_mgr = _FakeManager(used_backup=False)
    await _seed_shortcut_context(fake_mgr, admin_phone_digits, target_phone="12015559991")

    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={"phone": tenant.whatsapp_phone, "message": "1", "instance": TEST_INSTANCE},
            headers={"X-API-Key": settings.n8n_api_key},
        )

    reply = response.json()["reply"]
    assert "Inactive Detail Client" in reply
    assert "Usuario:" in reply
    assert "Reactivar" in reply
    assert "Eliminar" in reply


async def test_inactive_menu_option_3_reactivates_and_shows_active_menu(
    client, db_session, active_tenant_user
):
    """Option 3 on inactive root menu must reactivate and show active menu."""
    tenant = await _setup_tenant_with_instance(db_session, active_tenant_user)
    admin_phone_digits = tenant.whatsapp_phone.lstrip("+")
    await _create_context_client(
        db_session,
        tenant,
        phone="12015559990",
        is_active=False,
        full_name="Reactivatable Client",
        username="tna01_ctx_reactivate",
    )
    fake_mgr = _FakeManager(used_backup=False)
    ctx_key = await _seed_shortcut_context(fake_mgr, admin_phone_digits, target_phone="12015559990")

    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={"phone": tenant.whatsapp_phone, "message": "3", "instance": TEST_INSTANCE},
            headers={"X-API-Key": settings.n8n_api_key},
        )

    reply = response.json()["reply"]
    assert "reactivado" in reply.lower()
    assert "Crear suscripcion" in reply
    ctx_data = json.loads(await fake_mgr._redis.get(ctx_key))
    assert ctx_data["step"] == "active_menu"


async def test_inactive_menu_option_4_delete_flow_shows_unregistered_menu_after_confirm(
    client, db_session, active_tenant_user
):
    """Option 4 delete flow must transition to unregistered menu after confirm."""
    tenant = await _setup_tenant_with_instance(db_session, active_tenant_user)
    admin_phone_digits = tenant.whatsapp_phone.lstrip("+")
    ctx_client = await _create_context_client(
        db_session,
        tenant,
        phone="12015559989",
        is_active=False,
        full_name="Delete Inactive Client",
        username="tna01_ctx_delete",
    )
    fake_mgr = _FakeManager(used_backup=False)
    ctx_key = await _seed_shortcut_context(
        fake_mgr,
        admin_phone_digits,
        target_phone="12015559989",
        step="inactive_menu",
    )
    raw = json.loads(await fake_mgr._redis.get(ctx_key))
    raw["temp_data"]["client_id"] = str(ctx_client.id)
    await fake_mgr._redis.set(ctx_key, json.dumps(raw), ex=300)

    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        prompt_response = await client.post(
            ENDPOINT,
            json={"phone": tenant.whatsapp_phone, "message": "4", "instance": TEST_INSTANCE},
            headers={"X-API-Key": settings.n8n_api_key},
        )
        assert "eliminar permanentemente" in prompt_response.json()["reply"].lower()

        response = await client.post(
            ENDPOINT,
            json={"phone": tenant.whatsapp_phone, "message": "CONFIRMAR", "instance": TEST_INSTANCE},
            headers={"X-API-Key": settings.n8n_api_key},
        )

    reply = response.json()["reply"]
    assert "eliminado" in reply.lower()
    assert "Crear cliente para este numero" in reply
    assert "Bloquear acceso" in reply


async def test_inactive_menu_invalid_input_rerenders_full_menu_and_refreshes_ttl(
    client, db_session, active_tenant_user
):
    """Invalid input on inactive root menu must re-render full menu and refresh TTL."""
    tenant = await _setup_tenant_with_instance(db_session, active_tenant_user)
    admin_phone_digits = tenant.whatsapp_phone.lstrip("+")
    await _create_context_client(
        db_session,
        tenant,
        phone="12015559988",
        is_active=False,
        full_name="Invalid Inactive Client",
        username="tna01_ctx_inactive_invalid",
    )
    fake_mgr = _FakeManager(used_backup=False)
    ctx_key = await _seed_shortcut_context(
        fake_mgr,
        admin_phone_digits,
        target_phone="12015559988",
        ttl=123,
    )

    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={"phone": tenant.whatsapp_phone, "message": "9", "instance": TEST_INSTANCE},
            headers={"X-API-Key": settings.n8n_api_key},
        )

    reply = response.json()["reply"]
    assert "Opcion invalida" in reply
    assert "Ver detalle" in reply
    assert "Editar cliente" in reply
    assert "Reactivar cliente" in reply
    assert "Eliminar cliente" in reply
    assert fake_mgr._redis._ttls[ctx_key] == 300


async def test_render_initial_context_menu_lid_only_hides_phone_line(
    db_session, active_tenant_user
):
    """LID-only render must not show phone number line."""
    from app.api.v1.endpoints.integrations.console_context_shortcut import render_initial_context_menu

    tenant = await _setup_tenant_with_instance(db_session, active_tenant_user)
    rendered, metadata = await render_initial_context_menu(
        db=db_session,
        tenant=tenant,
        target_phone=None,
        target_lid="998877665544@lid",
        target_jid="998877665544@lid",
    )

    assert "Numero de telefono" not in rendered
    assert metadata["menu_variant"] == "unregistered"
