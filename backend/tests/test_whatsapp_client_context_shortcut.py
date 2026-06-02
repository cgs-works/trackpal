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
from app.models import Tenant

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
    params = {"identity": "34123456789", "client_name": "Ana", "status": "Activo"}
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
    ]
    for locale in ("en", "es"):
        for key in keys:
            rendered = t(locale, key, **params)
            assert rendered != key
            assert "Gestión del cliente" in rendered or "Client management" in rendered or key.endswith(("closed", "collision", "invalid_option", "success", "phone_prompt", "phone_prefilled"))


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
    assert "Gestión del cliente" in reply
    assert "Crear cliente para este número" in reply
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
    assert "Gestión del cliente" not in body.get("reply", "")


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
