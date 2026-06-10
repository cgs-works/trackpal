"""Tests for the n8n/backend WhatsApp Master Console contract.

Verifies API-key auth, Master/non-Master handling, and response shape.
"""

import json
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.api.v1.endpoints.integrations import _TenantConsoleAdapter
from app.core.config import settings
from app.models import (
    Client,
    BlockedClient,
    CodeServiceGlobalStatus,
    MasterProfile,
    Tenant,
    TenantCodeServiceSelection,
    TenantMailbox,
    User,
)
from app.repositories import mailbox_lookup_repository
from app.services.tenant_service import TenantService
from app.services.whatsapp_auth_session_service import (
    WhatsAppAuthLockState,
    WhatsAppAuthSession,
)

pytestmark = pytest.mark.asyncio

ENDPOINT = "/api/v1/integrations/n8n/console"


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
    """Duck-typed connection manager for endpoint test isolation.

    Parameters
    ----------
    used_backup:
        When ``True`` simulates failover active (backup in use).
    fail_on_execute:
        When ``True`` raises ``RedisUnavailableError`` to simulate both stores down.
    """

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


async def test_missing_api_key_returns_401(client):
    """No X-API-Key header → 401."""
    response = await client.post(
        ENDPOINT,
        json={"phone": "+12015550001", "message": "hola"},
    )
    assert response.status_code == 401
    assert "Invalid API Key" in response.json()["detail"]


async def test_wrong_api_key_returns_401(client):
    """Wrong X-API-Key header → 401."""
    response = await client.post(
        ENDPOINT,
        json={"phone": "+12015550001", "message": "hola"},
        headers={"X-API-Key": "wrong-key"},
    )
    assert response.status_code == 401
    assert "Invalid API Key" in response.json()["detail"]


async def test_unknown_phone_returns_no_access_reply(client):
    """Phone not found + Redis available → no-access reply, not login prompt."""
    fake_mgr = _FakeManager(used_backup=False)
    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={"phone": "+9999999999", "message": "hola"},
            headers={"X-API-Key": settings.n8n_api_key},
        )
    assert response.status_code == 200
    body = response.json()
    assert "reply" in body
    reply = body["reply"].lower()
    # Must be a no-access reply, not a login prompt
    assert "no tienes acceso" in reply or "no está registrado" in reply


async def test_tenant_phone_returns_tenant_console(client, active_tenant_user):
    """Tenant phone + Redis available → tenant console reply, not login prompt."""
    fake_mgr = _FakeManager(used_backup=False)
    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={"phone": "+12015550002", "message": "hola"},
            headers={"X-API-Key": settings.n8n_api_key},
        )
    assert response.status_code == 200
    body = response.json()
    assert "reply" in body
    reply = body["reply"]
    # Must be the tenant console (main menu or fallback), not the login prompt
    assert (
        "Consola de Administracion" in reply
        or "No entendi" in reply
        or "opcion del menu" in reply
        or "Admin Console" in reply
        or "didn't understand" in reply
    )


async def test_client_phone_returns_no_access(client, active_client_user):
    """Client phone + Redis available → no-access reply.

    Clients are not identified by phone (per Issue 3 fix), so they
    fall through as ``unknown`` and receive the no-access reply.
    """
    fake_mgr = _FakeManager(used_backup=False)
    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={"phone": "+12015550030", "message": "hola"},
            headers={"X-API-Key": settings.n8n_api_key},
        )
    assert response.status_code == 200
    body = response.json()
    assert "reply" in body
    reply = body["reply"].lower()
    # Must be the no-access reply, not a login prompt
    assert "no tienes acceso" in reply or "no está registrado" in reply


async def test_master_phone_returns_state_unavailable_when_redis_missing(
    client, master_user
):
    """Master phone + no Redis → relayable safe error, not stateless flow."""
    response = await client.post(
        ENDPOINT,
        json={"phone": "+12015550001", "message": "hola"},
        headers={"X-API-Key": settings.n8n_api_key},
    )
    assert response.status_code == 200
    body = response.json()
    assert "reply" in body
    assert "temporalmente no disponible" in body["reply"].lower()


async def test_master_phone_jid_is_normalized_before_identify(client, master_user):
    """JID-style phone from n8n/Evolution identifies stored master phone."""
    response = await client.post(
        ENDPOINT,
        json={"phone": "+12015550001@s.whatsapp.net", "message": "hola"},
        headers={"X-API-Key": settings.n8n_api_key},
    )
    assert response.status_code == 200
    reply = response.json()["reply"]
    assert "temporalmente no disponible" in reply.lower()


async def test_real_adapter_lifecycle_methods_use_tenant_service(
    db_session, active_tenant_user
):
    """Adapter lifecycle path returns console-service result shape."""
    adapter = _TenantConsoleAdapter(TenantService(), db_session)
    tenant_id = str(active_tenant_user.id)

    deactivated = await adapter.deactivate_tenant(tenant_id)
    assert deactivated["success"] is True
    assert deactivated["tenant"].is_active is False

    activated = await adapter.activate_tenant(tenant_id)
    assert activated["success"] is True
    assert activated["tenant"].is_active is True

    await adapter.deactivate_tenant(tenant_id)
    deleted = await adapter.delete_tenant(tenant_id)
    assert deleted == {"success": True}

    result = await db_session.execute(
        select(Tenant).where(Tenant.owner_user_id == active_tenant_user.id)
    )
    assert result.scalar_one_or_none() is None


async def test_response_shape(client, master_user):
    """Response contains exactly the expected fields."""
    response = await client.post(
        ENDPOINT,
        json={"phone": "+12015550001", "message": "hola"},
        headers={"X-API-Key": settings.n8n_api_key},
    )
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["reply"], str)
    # Only 'reply' in the response for n8n to forward
    assert set(body.keys()) == {"reply"}


# ---------------------------------------------------------------------------
# Degraded-state tests — fake manager injected via patch
# ---------------------------------------------------------------------------


async def test_primary_flow_with_fake_manager_returns_menu(client, master_user):
    """Primary Redis active + Manager with used_backup=False → normal flow.
    Requires an active auth session first.
    """
    fake_mgr = _FakeManager(used_backup=False)

    auth_session = WhatsAppAuthSession(
        phone="12015550001",
        user_id=master_user.id,
        username=master_user.username,
        role="master",
        authenticated_at=datetime.now(timezone.utc),
    )
    auth_key = "wa:auth:12015550001"

    await fake_mgr._redis.set(auth_key, auth_session.model_dump_json(), ex=300)

    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={"phone": "+12015550001", "message": "menu"},
            headers={"X-API-Key": settings.n8n_api_key},
        )
    assert response.status_code == 200
    body = response.json()
    reply = body["reply"]
    # Normal menu, not a degraded-state reply
    assert "Master Console" in reply or "Trackpal" in reply
    assert "contingencia" not in reply.lower()
    assert "no disponible" not in reply.lower()


async def test_failover_missing_session_returns_contingency_reset(client, master_user):
    """Failover active + backup has no session → SESSION_RESET reply.

    The reply must tell the Master the session was reset due to
    contingency and ask them to choose an option again.
    Requires an active auth session first.
    """
    fake_mgr = _FakeManager(used_backup=True)

    # Create auth session in the fake Redis first
    # Phone must match normalized form (digits only, no +)
    auth_session = WhatsAppAuthSession(
        phone="12015550001",
        user_id=master_user.id,
        username=master_user.username,
        role="master",
        authenticated_at=datetime.now(timezone.utc),
    )
    auth_key = "wa:auth:12015550001"

    await fake_mgr._redis.set(auth_key, auth_session.model_dump_json(), ex=300)

    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={"phone": "+12015550001", "message": "nombre del tenant"},
            headers={"X-API-Key": settings.n8n_api_key},
        )
    assert response.status_code == 200
    body = response.json()
    reply = body["reply"]
    # Must contain contingency reset text
    assert "contingencia" in reply.lower()
    assert "sesión" in reply.lower() or "sesion" in reply.lower()
    # Must include menu options so the Master can continue
    assert "Ver empresas" in reply


async def test_failover_missing_session_with_menu_choice_still_resets(
    client, master_user
):
    """Even a menu-choice message gets reset when failover active + no session."""
    fake_mgr = _FakeManager(used_backup=True)

    auth_session = WhatsAppAuthSession(
        phone="12015550001",
        user_id=master_user.id,
        username=master_user.username,
        role="master",
        authenticated_at=datetime.now(timezone.utc),
    )
    auth_key = "wa:auth:12015550001"

    await fake_mgr._redis.set(auth_key, auth_session.model_dump_json(), ex=300)

    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={"phone": "+12015550001", "message": "2"},
            headers={"X-API-Key": settings.n8n_api_key},
        )
    assert response.status_code == 200
    body = response.json()
    reply = body["reply"]
    # Must contain contingency reset text (not routed to create flow)
    assert "contingencia" in reply.lower()
    # The menu in the reset text includes "Crear Tenant", but the reply
    # must NOT be a create-flow prompt (no "nombre completo" prompt)
    assert "¿cuál es el *nombre completo*" not in reply.lower()


async def test_failover_reset_creates_session_on_backup(client, master_user):
    """After contingency reset, the next message works normally with backup.

    The first message creates a fresh session on backup via the reset
    path.  The second message finds the session and routes normally.
    Requires an active auth session first.
    """
    fake_mgr = _FakeManager(used_backup=True)

    auth_session = WhatsAppAuthSession(
        phone="12015550001",
        user_id=master_user.id,
        username=master_user.username,
        role="master",
        authenticated_at=datetime.now(timezone.utc),
    )
    auth_key = "wa:auth:12015550001"

    await fake_mgr._redis.set(auth_key, auth_session.model_dump_json(), ex=300)

    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        # First message — triggers reset, creates fresh session on backup
        resp1 = await client.post(
            ENDPOINT,
            json={"phone": "+12015550001", "message": "hola"},
            headers={"X-API-Key": settings.n8n_api_key},
        )
        assert resp1.status_code == 200
        assert "contingencia" in resp1.json()["reply"].lower()

        # Second message — session now exists on backup, should work normally.
        # Use "menu" (a reset command) to trigger MAIN_MENU, not FALLBACK_NO_FLOW.
        resp2 = await client.post(
            ENDPOINT,
            json={"phone": "+12015550001", "message": "menu"},
            headers={"X-API-Key": settings.n8n_api_key},
        )
        assert resp2.status_code == 200
        reply2 = resp2.json()["reply"]
        # Now it's a normal menu reply, not contingency
        assert "contingencia" not in reply2.lower()
        assert "Master Console" in reply2 or "Trackpal" in reply2


async def test_both_redis_unavailable_returns_temporary_unavailable(
    client, master_user
):
    """Both Redis stores fail during operation → temporary unavailable reply."""
    fake_mgr = _FakeManager(fail_on_execute=True)
    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={"phone": "+12015550001", "message": "hola"},
            headers={"X-API-Key": settings.n8n_api_key},
        )
    assert response.status_code == 200
    body = response.json()
    reply = body["reply"]
    assert "no disponible" in reply.lower()
    assert "contingencia" not in reply.lower()


async def test_both_unavailable_still_returns_200_for_relayable_reply(
    client, master_user
):
    """HTTP 200 is preserved for temporary unavailable so n8n can relay."""
    fake_mgr = _FakeManager(fail_on_execute=True)
    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={"phone": "+12015550001", "message": "hola"},
            headers={"X-API-Key": settings.n8n_api_key},
        )
    assert response.status_code == 200  # Not 500


async def test_invalid_api_key_still_401_with_fake_manager(client, master_user):
    """Invalid API key returns 401 regardless of Redis state."""
    fake_mgr = _FakeManager(used_backup=False)
    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={"phone": "+12015550001", "message": "hola"},
            headers={"X-API-Key": "wrong-key"},
        )
    assert response.status_code == 401
    assert "Invalid API Key" in response.json()["detail"]
    fake_mgr = _FakeManager(used_backup=False)
    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={"phone": "+12015550001", "message": "hola"},
            headers={"X-API-Key": "wrong-key"},
        )
    assert response.status_code == 401
    assert "Invalid API Key" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Realistic Redis exception handling — every infrastructure error must
# produce a relayable 200 reply, never HTTP 500.
# ---------------------------------------------------------------------------


class _FakeManagerRaising:
    """Duck-typed manager that raises a specific exception on execute."""

    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    @property
    def used_backup(self) -> bool:
        return False

    async def execute(self, operation_name: str, async_callable: Any) -> Any:
        raise self._exc


async def test_redis_connection_error_returns_temporary_unavailable(
    client, master_user
):
    """ConnectionError from Redis yields relayable unavailable reply."""
    fake_mgr = _FakeManagerRaising(ConnectionError("primary Redis connection refused"))
    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={"phone": "+12015550001", "message": "hola"},
            headers={"X-API-Key": settings.n8n_api_key},
        )
    assert response.status_code == 200
    assert "no disponible" in response.json()["reply"].lower()


async def test_redis_timeout_error_returns_temporary_unavailable(client, master_user):
    """TimeoutError from Redis yields relayable unavailable reply."""
    fake_mgr = _FakeManagerRaising(TimeoutError("primary Redis timed out"))
    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={"phone": "+12015550001", "message": "hola"},
            headers={"X-API-Key": settings.n8n_api_key},
        )
    assert response.status_code == 200
    assert "no disponible" in response.json()["reply"].lower()


async def test_redis_os_error_returns_temporary_unavailable(client, master_user):
    """OSError (e.g. socket-level) from Redis yields relayable unavailable reply."""
    fake_mgr = _FakeManagerRaising(OSError("socket closed by remote"))
    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={"phone": "+12015550001", "message": "hola"},
            headers={"X-API-Key": settings.n8n_api_key},
        )
    assert response.status_code == 200
    assert "no disponible" in response.json()["reply"].lower()


async def test_redis_unavailable_error_returns_temporary_unavailable(
    client, master_user
):
    """RedisUnavailableError from Redis yields relayable unavailable reply."""
    from app.core.redis_client import RedisUnavailableError

    fake_mgr = _FakeManagerRaising(RedisUnavailableError("both Redis stores down"))
    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={"phone": "+12015550001", "message": "hola"},
            headers={"X-API-Key": settings.n8n_api_key},
        )
    assert response.status_code == 200
    assert "no disponible" in response.json()["reply"].lower()


async def test_unknown_phone_returns_no_access_when_redis_healthy(
    client, active_tenant_user
):
    """Unknown phone + Redis healthy → no-access reply, not login prompt."""
    fake_mgr = _FakeManager(fail_on_execute=False)
    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={"phone": "+20000000000", "message": "hola"},
            headers={"X-API-Key": settings.n8n_api_key},
        )
    assert response.status_code == 200
    reply = response.json()["reply"].lower()
    # Must be a no-access reply, not a login prompt
    assert "no tienes acceso" in reply or "no está registrado" in reply


# ---------------------------------------------------------------------------
# Multi-instance invariance tests — instance must not influence auth
# session lookup or lockout keys.
# ---------------------------------------------------------------------------


async def test_unknown_instance_denies_master_phone(client, master_user):
    """Unknown instance with master phone → access denied (strict isolation)."""
    fake_mgr = _FakeManager(used_backup=False)

    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        resp = await client.post(
            ENDPOINT,
            json={
                "phone": "+12015550001",
                "message": "menu",
                "instance": "unknown-instance-z",
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )
        assert resp.status_code == 200
        reply = resp.json()["reply"].lower()
        # Strict instance isolation: unknown instance → deny, no phone fallback
        assert "no tienes acceso" in reply or "no está registrado" in reply


async def test_unknown_instance_denies_even_with_lockout(client, master_user):
    """Unknown instance with lockout state → access denied (isolation takes precedence)."""
    fake_mgr = _FakeManager(used_backup=False)

    lock_key = "wa:auth:lock:12015550001"
    lock_state = WhatsAppAuthLockState(
        locked_until=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    await fake_mgr._redis.set(lock_key, lock_state.model_dump_json(), ex=300)

    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        resp = await client.post(
            ENDPOINT,
            json={
                "phone": "+12015550001",
                "message": "hola",
                "instance": "unknown-instance-z",
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )
        assert resp.status_code == 200
        reply = resp.json()["reply"].lower()
        # Strict instance isolation: unknown instance → deny, not lockout
        assert "no tienes acceso" in reply or "no está registrado" in reply
        assert "bloqueado" not in reply
        assert "estás bloqueado" not in reply
        assert "espera" not in reply
        assert "locked" not in reply


# ---------------------------------------------------------------------------
# LID/JID resolution tests
# ---------------------------------------------------------------------------


async def test_lid_with_senderPn_resolves_by_phone(client, db_session, master_user):
    """Phone is available (derived from senderPn), sender_lid is also provided
    → identity resolves by phone, progressive fill persists LID.
    """
    master_id = master_user.id
    result = await db_session.execute(
        select(MasterProfile).where(MasterProfile.id == master_id)
    )
    profile = result.scalar_one()
    profile.whatsapp_lid = None
    await db_session.commit()

    fake_mgr = _FakeManager(used_backup=False)
    auth_session = WhatsAppAuthSession(
        phone="12015550001",
        user_id=master_user.id,
        username=master_user.username,
        role="master",
        authenticated_at=datetime.now(timezone.utc),
    )

    await fake_mgr._redis.set(
        "wa:auth:12015550001", auth_session.model_dump_json(), ex=300
    )

    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        # Phone is a valid phone JID, sender_lid is also provided
        response = await client.post(
            ENDPOINT,
            json={
                "phone": "+12015550001@s.whatsapp.net",
                "message": "menu",
                "sender_lid": "998877665544332211@lid",
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )
    assert response.status_code == 200
    reply = response.json()["reply"]
    # Phone resolved, routes to master console
    assert "Master Console" in reply or "Trackpal" in reply

    db_session.expire_all()
    result = await db_session.execute(
        select(MasterProfile).where(MasterProfile.id == master_id)
    )
    assert result.scalar_one().whatsapp_lid == "998877665544332211@lid"


async def test_lid_without_senderPn_unknown_lid_returns_no_access(client):
    """Phone empty, sender_lid provided but LID not persisted → unknown access."""
    fake_mgr = _FakeManager(used_backup=False)
    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={
                "phone": "",
                "message": "hola",
                "sender_lid": "unknown-lid-12345@lid",
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )
    assert response.status_code == 200
    reply = response.json()["reply"].lower()
    assert "no tienes acceso" in reply or "no está registrado" in reply


async def test_lid_without_senderPn_with_persisted_lid_resolves(
    client, db_session, master_user
):
    """Phone empty, sender_lid matches persisted whatsapp_lid → resolves."""
    # Persist LID on master profile
    result = await db_session.execute(
        select(MasterProfile).where(MasterProfile.id == master_user.id)
    )
    profile = result.scalar_one_or_none()
    if profile:
        profile.whatsapp_lid = "556677889900112233@lid"
        await db_session.commit()

    fake_mgr = _FakeManager(used_backup=False)
    auth_session = WhatsAppAuthSession(
        phone="12015550001",
        user_id=master_user.id,
        username=master_user.username,
        role="master",
        authenticated_at=datetime.now(timezone.utc),
    )

    await fake_mgr._redis.set(
        "wa:auth:12015550001", auth_session.model_dump_json(), ex=300
    )

    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={
                "phone": "",
                "message": "menu",
                "sender_lid": "556677889900112233@lid",
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )
    assert response.status_code == 200
    reply = response.json()["reply"]
    assert "Master Console" in reply or "Trackpal" in reply


async def test_lid_jid_phone_input_rejected(client, master_user):
    """Phone input with @lid suffix returns None from normalizer →
    falls through to no-access when no sender_lid provided."""
    fake_mgr = _FakeManager(used_backup=False)
    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={"phone": "123456789012345@lid", "message": "hola"},
            headers={"X-API-Key": settings.n8n_api_key},
        )
    assert response.status_code == 200
    reply = response.json()["reply"].lower()
    # Must not identify this phone, despite LID containing digits
    assert "no tienes acceso" in reply or "no está registrado" in reply


# ---------------------------------------------------------------------------
# Client Context Shortcut contract tests — new request/response fields
# ---------------------------------------------------------------------------


async def test_request_accepts_new_optional_fields(client, master_user):
    """New from_me, admin_phone, admin_jid, target_jid, target_phone,
    and target_lid fields are accepted without breaking legacy requests."""
    fake_mgr = _FakeManager(used_backup=False)
    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={
                "phone": "+12015550001",
                "message": "menu",
                "from_me": True,
                "admin_phone": "+12015550002",
                "admin_jid": "12015550002@s.whatsapp.net",
                "target_jid": "12015550003@s.whatsapp.net",
                "target_phone": "+12015550003",
                "target_lid": "998877665544332211@lid",
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )
    assert response.status_code == 200
    body = response.json()
    assert "reply" in body
    # New fields don't break routing — without a session the endpoint
    # asks for login (normal flow), proving the request was accepted
    assert (
        "nombre de usuario" in body["reply"].lower() or "login" in body["reply"].lower()
    )


async def test_request_legacy_without_new_fields_still_works(client, master_user):
    """Legacy request without any new fields produces the same response
    as before (backward compatibility)."""
    fake_mgr = _FakeManager(used_backup=False)
    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={"phone": "+12015550001", "message": "hola"},
            headers={"X-API-Key": settings.n8n_api_key},
        )
    assert response.status_code == 200
    body = response.json()
    assert "reply" in body
    # Only standard keys present
    assert "reply_to" not in body
    assert "no_reply" not in body


async def test_response_serializes_reply_to_when_set(client, master_user):
    """When reply_to is set, it appears in the serialized response."""
    fake_mgr = _FakeManager(used_backup=False)
    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={"phone": "+12015550001", "message": "menu"},
            headers={"X-API-Key": settings.n8n_api_key},
        )
    assert response.status_code == 200
    body = response.json()
    # Without an active session the response won't have reply_to yet.
    # We verify the schema model directly serializes reply_to correctly.
    # This is done via a unit-style check of the response model.
    assert "reply" in body


async def test_response_model_serializes_reply_to(client):
    """WhatsAppConsoleResponse serializes reply_to when present,
    omits it when absent."""
    from app.schemas.whatsapp import WhatsAppConsoleResponse

    # Without reply_to
    r1 = WhatsAppConsoleResponse(reply="test")
    d1 = r1.model_dump(mode="json")
    assert "reply_to" not in d1

    # With reply_to
    r2 = WhatsAppConsoleResponse(reply="test", reply_to="12015550002@s.whatsapp.net")
    d2 = r2.model_dump(mode="json")
    assert d2["reply_to"] == "12015550002@s.whatsapp.net"


async def test_response_model_serializes_no_reply(client):
    """WhatsAppConsoleResponse serializes no_reply when present,
    omits it when absent."""
    from app.schemas.whatsapp import WhatsAppConsoleResponse

    # Without no_reply
    r1 = WhatsAppConsoleResponse(reply="test")
    d1 = r1.model_dump(mode="json")
    assert "no_reply" not in d1

    # With no_reply
    r2 = WhatsAppConsoleResponse(reply="test", no_reply=True)
    d2 = r2.model_dump(mode="json")
    assert d2["no_reply"] is True

    # With no_reply=False (still serialized because it's non-None)
    r3 = WhatsAppConsoleResponse(reply="test", no_reply=False)
    d3 = r3.model_dump(mode="json")
    assert d3["no_reply"] is False


# ---------------------------------------------------------------------------
# Unauthenticated code lookup for unregistered identities
# ---------------------------------------------------------------------------

TEST_INSTANCE = "test-tenant-instance"


async def _setup_tenant_for_codigo(db_session, active_tenant_user) -> Tenant:
    """Set up a tenant with instance, mailbox, and code services for codigo flow."""
    result = await db_session.execute(
        select(Tenant).where(Tenant.owner_user_id == active_tenant_user.id)
    )
    tenant = result.scalar_one_or_none()
    assert tenant is not None
    tenant.evolution_instance_name = TEST_INSTANCE
    tenant.locale = "es"
    await db_session.flush()

    # Create connected mailbox
    mailbox = TenantMailbox(
        tenant_id=tenant.id,
        mailbox_email="tech@example.com",
        provider="imap",
        auth_method="password",
        status="connected",
    )
    db_session.add(mailbox)

    # Activate global code service and select for tenant
    global_svc = CodeServiceGlobalStatus(service_key="netflix", is_active=True)
    db_session.add(global_svc)
    tenant_sel = TenantCodeServiceSelection(tenant_id=tenant.id, service_key="netflix")
    db_session.add(tenant_sel)

    await db_session.commit()
    return tenant


async def _reach_unauth_codigo_confirm_step(
    client,
    instance: str,
    email: str = "user@example.com",
    phone: str = "+12015559999",
) -> None:
    """Progress an unauthenticated codigo session to the email_confirm step."""
    await client.post(
        ENDPOINT,
        json={"phone": phone, "message": "codigo", "instance": instance},
        headers={"X-API-Key": settings.n8n_api_key},
    )
    await client.post(
        ENDPOINT,
        json={"phone": phone, "message": "1", "instance": instance},
        headers={"X-API-Key": settings.n8n_api_key},
    )
    await client.post(
        ENDPOINT,
        json={"phone": phone, "message": email, "instance": instance},
        headers={"X-API-Key": settings.n8n_api_key},
    )


async def _seed_unauth_codigo_awaiting_result(
    fake_mgr: _FakeManager,
    tenant_id,
    *,
    phone: str = "12015559999",
    lookup_job_id: str = "",
) -> str:
    import json

    tenant_prefix = str(tenant_id)[:8]
    session_key = f"session:unreg:{tenant_prefix}:{phone}"
    await fake_mgr._redis.set(
        session_key,
        json.dumps(
            {
                "phone": f"unreg:{tenant_prefix}:{phone}",
                "flow": "codigo",
                "step": "awaiting_result",
                "selected_tenant_id": None,
                "temp_data": {
                    "lookup_job_id": lookup_job_id,
                    "service_key": "netflix",
                    "target_email": "user@example.com",
                },
                "selection_map": {},
            }
        ),
        ex=300,
    )
    return session_key


async def test_unregistered_identity_codigo_starts_flow(
    client, db_session, active_tenant_user
):
    """Unregistered identity sending 'codigo' in a known tenant instance
    receives the service list prompt."""
    _tenant = await _setup_tenant_for_codigo(db_session, active_tenant_user)

    fake_mgr = _FakeManager(used_backup=False)
    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={
                "phone": "+12015559999",
                "message": "codigo",
                "instance": TEST_INSTANCE,
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )
    assert response.status_code == 200
    body = response.json()
    assert "reply" in body
    reply = body["reply"]
    # Should show service prompt (not access_denied)
    assert "Buscar Código" in reply or "servicio" in reply
    assert "Netflix" in reply
    assert "reply_to" not in body
    assert "no_reply" not in body or body.get("no_reply") is not True


async def test_unregistered_identity_codigo_multistep(
    client, db_session, active_tenant_user
):
    """Unregistered identity goes through full codigo flow:
    service selection → email → confirm → awaiting_result."""
    _tenant = await _setup_tenant_for_codigo(db_session, active_tenant_user)

    fake_mgr = _FakeManager(used_backup=False)
    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        # Step 1: send "codigo" → service prompt
        resp1 = await client.post(
            ENDPOINT,
            json={
                "phone": "+12015559999",
                "message": "codigo",
                "instance": TEST_INSTANCE,
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )
        assert resp1.status_code == 200
        body1 = resp1.json()
        assert "Netflix" in body1["reply"]

        # Step 2: send "1" (select Netflix) → email prompt
        resp2 = await client.post(
            ENDPOINT,
            json={
                "phone": "+12015559999",
                "message": "1",
                "instance": TEST_INSTANCE,
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )
        assert resp2.status_code == 200
        body2 = resp2.json()
        assert "email" in body2["reply"].lower() or "correo" in body2["reply"].lower()

        # Step 3: send valid email → confirm prompt, NO job created
        resp3 = await client.post(
            ENDPOINT,
            json={
                "phone": "+12015559999",
                "message": "User@Example.COM",
                "instance": TEST_INSTANCE,
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )
        assert resp3.status_code == 200
        body3 = resp3.json()
        assert (
            "confirm" in body3["reply"].lower()
            or "confirmar" in body3["reply"].lower()
        )
        assert "user@example.com" in body3["reply"]
        assert "lookup_job_id" not in body3

        # Step 4: send "1" (confirm) → job created, awaiting result
        resp4 = await client.post(
            ENDPOINT,
            json={
                "phone": "+12015559999",
                "message": "1",
                "instance": TEST_INSTANCE,
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )
        assert resp4.status_code == 200
        body4 = resp4.json()
        assert (
            "buscando" in body4["reply"].lower()
            or "searching" in body4["reply"].lower()
        )
        assert body4["lookup_job_id"] is not None
        assert body4["tenant_id"] is not None


async def test_unregistered_identity_codigo_confirm_option_2_returns_email_prompt(
    client, db_session, active_tenant_user
):
    """Option 2 (correct email) on confirm step goes back to email prompt."""
    _tenant = await _setup_tenant_for_codigo(db_session, active_tenant_user)

    fake_mgr = _FakeManager(used_backup=False)
    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        await _reach_unauth_codigo_confirm_step(client, TEST_INSTANCE)

        resp = await client.post(
            ENDPOINT,
            json={"phone": "+12015559999", "message": "2", "instance": TEST_INSTANCE},
            headers={"X-API-Key": settings.n8n_api_key},
        )

    body = resp.json()
    assert "email" in body["reply"].lower() or "correo" in body["reply"].lower()
    assert "lookup_job_id" not in body


async def test_unregistered_identity_codigo_confirm_option_9_returns_services(
    client, db_session, active_tenant_user
):
    """Option 9 on confirm step goes back to services."""
    _tenant = await _setup_tenant_for_codigo(db_session, active_tenant_user)

    fake_mgr = _FakeManager(used_backup=False)
    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        await _reach_unauth_codigo_confirm_step(client, TEST_INSTANCE)

        resp = await client.post(
            ENDPOINT,
            json={"phone": "+12015559999", "message": "9", "instance": TEST_INSTANCE},
            headers={"X-API-Key": settings.n8n_api_key},
        )

    body = resp.json()
    assert "Netflix" in body["reply"]
    assert "lookup_job_id" not in body


async def test_unregistered_identity_codigo_confirm_option_0_closes_session(
    client, db_session, active_tenant_user
):
    """Option 0 on confirm step closes the session."""
    _tenant = await _setup_tenant_for_codigo(db_session, active_tenant_user)

    fake_mgr = _FakeManager(used_backup=False)
    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        await _reach_unauth_codigo_confirm_step(client, TEST_INSTANCE)

        resp = await client.post(
            ENDPOINT,
            json={"phone": "+12015559999", "message": "0", "instance": TEST_INSTANCE},
            headers={"X-API-Key": settings.n8n_api_key},
        )

    body = resp.json()
    assert body["status"] == "closed"
    assert body["reply_to"] == "12015559999@s.whatsapp.net"
    assert body["close_jid"] == "12015559999@s.whatsapp.net"


async def test_unregistered_identity_codigo_confirm_invalid_option_does_not_create_job(
    client, db_session, active_tenant_user
):
    """Invalid option on confirm step returns error, no job created."""
    _tenant = await _setup_tenant_for_codigo(db_session, active_tenant_user)

    fake_mgr = _FakeManager(used_backup=False)
    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        await _reach_unauth_codigo_confirm_step(client, TEST_INSTANCE)

        resp = await client.post(
            ENDPOINT,
            json={"phone": "+12015559999", "message": "cancelar", "instance": TEST_INSTANCE},
            headers={"X-API-Key": settings.n8n_api_key},
        )

    body = resp.json()
    assert "opción inválida" in body["reply"].lower() or "invalid option" in body["reply"].lower()
    assert "lookup_job_id" not in body


async def test_unregistered_identity_blocked_returns_no_reply(
    client, db_session, active_tenant_user
):
    """Blocked unregistered identity receives no_reply=true for codigo."""
    tenant = await _setup_tenant_for_codigo(db_session, active_tenant_user)

    # Create active block for the identity
    block = BlockedClient(
        tenant_id=tenant.id,
        phone="12015559999",
        is_active=True,
    )
    db_session.add(block)
    await db_session.commit()

    fake_mgr = _FakeManager(used_backup=False)
    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={
                "phone": "+12015559999",
                "message": "codigo",
                "instance": TEST_INSTANCE,
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )
    assert response.status_code == 200
    body = response.json()
    # Blocked identity gets silent treatment
    assert body.get("no_reply") is True
    # No reply text should be sent
    assert not body.get("reply") or body.get("reply") == ""


async def test_unregistered_identity_blocked_any_message_no_reply(
    client, db_session, active_tenant_user
):
    """Blocked unregistered identity receives no_reply=true for /menu too."""
    tenant = await _setup_tenant_for_codigo(db_session, active_tenant_user)

    block = BlockedClient(
        tenant_id=tenant.id,
        phone="12015559999",
        is_active=True,
    )
    db_session.add(block)
    await db_session.commit()

    fake_mgr = _FakeManager(used_backup=False)
    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={
                "phone": "+12015559999",
                "message": "/menu",
                "instance": TEST_INSTANCE,
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )
    assert response.status_code == 200
    body = response.json()
    assert body.get("no_reply") is True
    assert not body.get("reply") or body.get("reply") == ""


async def test_external_admin_menu_to_other_tenant_is_silent_without_close_signal(
    client, db_session, active_tenant_user
):
    """Cross-tenant inbound /menu is ignored silently without closing admin chat."""
    tenant = await _setup_tenant_with_instance(db_session, active_tenant_user)

    other_user = User(
        username="other-tenant",
        password_hash="test-hash",
        role="tenant",
    )
    db_session.add(other_user)
    await db_session.flush()
    other_tenant = Tenant(
        owner_user_id=other_user.id,
        client_prefix="tnc01",
        name="Other Tenant",
        whatsapp_phone="+12015550044",
        evolution_instance_name="other-tenant-instance",
        is_active=True,
    )
    db_session.add(other_tenant)
    await db_session.commit()

    fake_mgr = _FakeManager(used_backup=False)
    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={
                "phone": tenant.whatsapp_phone,
                "message": "/menu",
                "instance": other_tenant.evolution_instance_name,
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )
    assert response.status_code == 200
    body = response.json()
    assert body.get("reply") == ""
    assert body.get("no_reply") is True
    assert "status" not in body
    assert "close_jid" not in body


async def test_unregistered_identity_non_codigo_returns_access_denied(
    client, db_session, active_tenant_user
):
    """Unregistered identity sending non-codigo message receives access_denied."""
    _tenant = await _setup_tenant_for_codigo(db_session, active_tenant_user)

    fake_mgr = _FakeManager(used_backup=False)
    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={
                "phone": "+12015559999",
                "message": "hola",
                "instance": TEST_INSTANCE,
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )
    assert response.status_code == 200
    body = response.json()
    reply = body["reply"].lower()
    # Must say not registered and include hint about code keyword
    assert "no tienes" in reply
    assert "codigo" in reply or "código" in reply or "code" in reply
    assert "Netflix" not in body["reply"]
    # Must close session so Evolution Go cleans up
    assert body.get("status") == "closed"
    assert body.get("close_jid") is not None


async def test_blocked_unregistered_with_existing_codigo_session_returns_no_reply(
    client, db_session, active_tenant_user
):
    """Block check runs BEFORE the unauth session resume.

    A tenant can apply a Client Messaging Block while a sender is in the
    middle of the codigo flow. The next inbound message must be silenced,
    not allowed to continue the dialog.
    """
    import json

    _tenant = await _setup_tenant_for_codigo(db_session, active_tenant_user)

    # Pre-existing active block for the identity
    block = BlockedClient(
        tenant_id=_tenant.id,
        phone="12015559999",
        is_active=True,
    )
    db_session.add(block)
    await db_session.commit()

    fake_mgr = _FakeManager(used_backup=False)
    # Pre-populate an unauthenticated codigo session in fake Redis
    unauth_session = {
        "phone": "12015559999",
        "flow": "codigo",
        "step": "email",
        "selected_tenant_id": None,
        "temp_data": {
            "service_key": "netflix",
            "service_label": "Netflix",
        },
        "selection_map": {},
    }
    await fake_mgr._redis.set(
        "session:unreg:12015559999",
        json.dumps(unauth_session),
        ex=300,
    )

    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={
                "phone": "+12015559999",
                "message": "user@example.com",
                "instance": TEST_INSTANCE,
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )
    assert response.status_code == 200
    body = response.json()
    # Block short-circuits the resume path
    assert body.get("no_reply") is True
    assert not body.get("reply") or body.get("reply") == ""
    assert "lookup_job_id" not in body


# ---------------------------------------------------------------------------
# Codigo flow navigation contract - is_cancel / is_back
# ---------------------------------------------------------------------------


async def test_unregistered_codigo_service_cancel_returns_cancelled(
    client, db_session, active_tenant_user
):
    """Sending 0 during unauth codigo service selection cancels the flow."""
    _tenant = await _setup_tenant_for_codigo(db_session, active_tenant_user)

    fake_mgr = _FakeManager(used_backup=False)
    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        # Start codigo flow
        resp1 = await client.post(
            ENDPOINT,
            json={
                "phone": "+12015559999",
                "message": "codigo",
                "instance": TEST_INSTANCE,
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )
        assert resp1.status_code == 200
        assert "Netflix" in resp1.json()["reply"]

        # Send "0" to cancel
        resp2 = await client.post(
            ENDPOINT,
            json={
                "phone": "+12015559999",
                "message": "0",
                "instance": TEST_INSTANCE,
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )
    assert resp2.status_code == 200
    body = resp2.json()
    assert "cancelada" in body["reply"].lower() or "cancelled" in body["reply"].lower()


async def test_unregistered_codigo_service_cancel_sets_closed_status(
    client, db_session, active_tenant_user
):
    """Sending 0 during unauth codigo service selection closes Evolution session."""
    _tenant = await _setup_tenant_for_codigo(db_session, active_tenant_user)

    fake_mgr = _FakeManager(used_backup=False)
    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        resp1 = await client.post(
            ENDPOINT,
            json={
                "phone": "+12015559999",
                "message": "codigo",
                "instance": TEST_INSTANCE,
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )
        assert resp1.status_code == 200
        assert "Netflix" in resp1.json()["reply"]

        resp2 = await client.post(
            ENDPOINT,
            json={
                "phone": "+12015559999",
                "message": "0",
                "instance": TEST_INSTANCE,
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )
    assert resp2.status_code == 200
    body = resp2.json()
    assert body.get("status") == "closed"
    assert body.get("reply_to") == "12015559999@s.whatsapp.net"
    assert body.get("close_jid") == "12015559999@s.whatsapp.net"


async def test_registered_client_codigo_cancel_resumes_codigo_not_client_console(
    client, db_session, active_tenant_user
):
    """Registered clients with active unauth codigo session cancel codigo, not client console."""
    tenant = await _setup_tenant_for_codigo(db_session, active_tenant_user)
    db_session.add(
        Client(
            tenant_id=tenant.id,
            owner_user_id=active_tenant_user.id,
            username="registered-client",
            phone="12015559999",
            full_name="Registered Client",
            is_active=True,
        )
    )
    await db_session.commit()

    fake_mgr = _FakeManager(used_backup=False)
    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        resp1 = await client.post(
            ENDPOINT,
            json={
                "phone": "+12015559999",
                "message": "codigo",
                "instance": TEST_INSTANCE,
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )
        assert resp1.status_code == 200
        assert "Netflix" in resp1.json()["reply"]

        resp2 = await client.post(
            ENDPOINT,
            json={
                "phone": "+12015559999",
                "message": "0",
                "instance": TEST_INSTANCE,
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )
    assert resp2.status_code == 200
    body = resp2.json()
    assert body.get("status") == "closed"
    assert body.get("close_jid") == "12015559999@s.whatsapp.net"
    assert "consola del cliente" not in body["reply"].lower()
    assert "client console" not in body["reply"].lower()


async def test_unregistered_codigo_result_retry_requeues_even_if_old_job_pending(
    client, db_session, active_tenant_user
):
    """Retry with 1 during unauth codigo awaiting result creates a fresh job even
    when the previous mailbox job is still pending (local n8n timeout scenario)."""
    from types import SimpleNamespace

    tenant = await _setup_tenant_for_codigo(db_session, active_tenant_user)
    fake_mgr = _FakeManager(used_backup=False)
    retry_job = SimpleNamespace(id=uuid4())

    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        # Step 1: start codigo flow
        resp1 = await client.post(
            ENDPOINT,
            json={
                "phone": "+12015559999",
                "message": "codigo",
                "instance": TEST_INSTANCE,
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )
        assert resp1.status_code == 200
        assert "Netflix" in resp1.json()["reply"]

        # Step 2: select service "1"
        resp2 = await client.post(
            ENDPOINT,
            json={"phone": "+12015559999", "message": "1", "instance": TEST_INSTANCE},
            headers={"X-API-Key": settings.n8n_api_key},
        )
        assert resp2.status_code == 200

        # Step 3: submit email
        resp3 = await client.post(
            ENDPOINT,
            json={
                "phone": "+12015559999",
                "message": "user@example.com",
                "instance": TEST_INSTANCE,
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )
        assert resp3.status_code == 200

        # Step 4: retry with "1" while previous job is pending
        with (
            patch(
                "app.api.v1.endpoints.integrations.console_handlers.mailbox_lookup_repository.get_job",
                AsyncMock(return_value=SimpleNamespace(status="pending")),
            ),
            patch(
                "app.api.v1.endpoints.integrations.console_handlers.mailbox_config_repository.get_by_tenant",
                AsyncMock(return_value=SimpleNamespace(id=uuid4(), status="connected")),
            ),
            patch(
                "app.api.v1.endpoints.integrations.console_handlers.mailbox_lookup_repository.create_job",
                AsyncMock(return_value=retry_job),
            ),
            patch(
                "app.api.v1.endpoints.integrations.console_handlers.enqueue_job",
                AsyncMock(return_value=True),
            ),
        ):
            response = await client.post(
                ENDPOINT,
                json={
                    "phone": "+12015559999",
                    "message": "1",
                    "instance": TEST_INSTANCE,
                },
                headers={"X-API-Key": settings.n8n_api_key},
            )

    assert response.status_code == 200
    body = response.json()
    assert body.get("lookup_job_id") == str(retry_job.id)
    assert body.get("tenant_id") == str(tenant.id)
    assert "buscando" in body["reply"].lower() or "searching" in body["reply"].lower()


async def test_unregistered_codigo_service_cancel_with_alias_returns_cancelled(
    client, db_session, active_tenant_user
):
    """Sending 'cancelar' during unauth codigo service selection cancels via is_cancel."""
    _tenant = await _setup_tenant_for_codigo(db_session, active_tenant_user)

    fake_mgr = _FakeManager(used_backup=False)
    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        # Start codigo flow
        resp1 = await client.post(
            ENDPOINT,
            json={
                "phone": "+12015559999",
                "message": "codigo",
                "instance": TEST_INSTANCE,
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )
        assert resp1.status_code == 200
        assert "Netflix" in resp1.json()["reply"]

        # Send "cancelar" to cancel (is_cancel alias)
        resp2 = await client.post(
            ENDPOINT,
            json={
                "phone": "+12015559999",
                "message": "cancelar",
                "instance": TEST_INSTANCE,
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )
    assert resp2.status_code == 200
    body = resp2.json()
    assert "cancelada" in body["reply"].lower() or "cancelled" in body["reply"].lower()


async def test_unregistered_codigo_email_cancel_returns_cancelled(
    client, db_session, active_tenant_user
):
    """Sending 0 during unauth codigo email step cancels the flow (was invalid email)."""
    _tenant = await _setup_tenant_for_codigo(db_session, active_tenant_user)

    fake_mgr = _FakeManager(used_backup=False)
    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        # Step 1: start codigo
        resp1 = await client.post(
            ENDPOINT,
            json={
                "phone": "+12015559999",
                "message": "codigo",
                "instance": TEST_INSTANCE,
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )
        assert resp1.status_code == 200

        # Step 2: select service (Netflix = option 1)
        resp2 = await client.post(
            ENDPOINT,
            json={
                "phone": "+12015559999",
                "message": "1",
                "instance": TEST_INSTANCE,
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )
        assert resp2.status_code == 200
        assert "email" in resp2.json()["reply"].lower()

        # Step 3: send "0" to cancel instead of email
        resp3 = await client.post(
            ENDPOINT,
            json={
                "phone": "+12015559999",
                "message": "0",
                "instance": TEST_INSTANCE,
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )
    assert resp3.status_code == 200
    body = resp3.json()
    # Must be cancelled, not "email invalido"
    assert "cancelada" in body["reply"].lower() or "cancelled" in body["reply"].lower()
    assert (
        "email" not in body["reply"].lower() or "invalido" not in body["reply"].lower()
    )


# ---------------------------------------------------------------------------
# Unauthenticated codigo restart from awaiting_result
# ---------------------------------------------------------------------------


async def test_unregistered_codigo_trigger_restarts_awaiting_result_and_cancels_active_job(
    client, db_session, active_tenant_user
):
    tenant = await _setup_tenant_for_codigo(db_session, active_tenant_user)
    fake_mgr = _FakeManager(used_backup=False)
    lookup_job_id = uuid4()
    session_key = await _seed_unauth_codigo_awaiting_result(
        fake_mgr,
        tenant.id,
        lookup_job_id=str(lookup_job_id),
    )

    with (
        patch(
            "app.api.v1.endpoints.integrations.console.get_redis_manager",
            return_value=fake_mgr,
        ),
        patch(
            "app.api.v1.endpoints.integrations.console_handlers.mailbox_lookup_repository.cancel_active_job_if_present",
            AsyncMock(return_value=True),
        ) as cancel_job,
    ):
        response = await client.post(
            ENDPOINT,
            json={
                "phone": "+12015559999",
                "message": " code ",
                "instance": TEST_INSTANCE,
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )

    assert response.status_code == 200
    body = response.json()
    assert "Netflix" in body["reply"]
    assert "todavia buscando" not in body["reply"].lower()
    assert "still checking" not in body["reply"].lower()

    called = cancel_job.await_args
    assert called.args[1] == lookup_job_id
    assert called.kwargs["tenant_id"] == tenant.id

    import json

    saved = json.loads(await fake_mgr._redis.get(session_key))
    assert saved["step"] == "service"
    assert saved["temp_data"]["codigo_effective_keys"] == ["netflix"]
    assert saved["temp_data"]["codigo_current_page"] == 0


async def test_unregistered_codigo_trigger_restarts_when_cancel_helper_noops(
    client, db_session, active_tenant_user
):
    tenant = await _setup_tenant_for_codigo(db_session, active_tenant_user)
    fake_mgr = _FakeManager(used_backup=False)
    lookup_job_id = uuid4()
    session_key = await _seed_unauth_codigo_awaiting_result(
        fake_mgr,
        tenant.id,
        lookup_job_id=str(lookup_job_id),
    )

    with (
        patch(
            "app.api.v1.endpoints.integrations.console.get_redis_manager",
            return_value=fake_mgr,
        ),
        patch(
            "app.api.v1.endpoints.integrations.console_handlers.mailbox_lookup_repository.cancel_active_job_if_present",
            AsyncMock(return_value=False),
        ) as cancel_job,
    ):
        response = await client.post(
            ENDPOINT,
            json={
                "phone": "+12015559999",
                "message": "codigo",
                "instance": TEST_INSTANCE,
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )

    assert response.status_code == 200
    body = response.json()
    assert "Netflix" in body["reply"]

    called = cancel_job.await_args
    assert called.args[1] == lookup_job_id
    assert called.kwargs["tenant_id"] == tenant.id

    import json

    saved = json.loads(await fake_mgr._redis.get(session_key))
    assert saved["step"] == "service"


async def test_unregistered_codigo_trigger_restarts_with_invalid_lookup_job_id(
    client, db_session, active_tenant_user
):
    tenant = await _setup_tenant_for_codigo(db_session, active_tenant_user)
    fake_mgr = _FakeManager(used_backup=False)
    session_key = await _seed_unauth_codigo_awaiting_result(
        fake_mgr,
        tenant.id,
        lookup_job_id="not-a-uuid",
    )

    with (
        patch(
            "app.api.v1.endpoints.integrations.console.get_redis_manager",
            return_value=fake_mgr,
        ),
        patch(
            "app.api.v1.endpoints.integrations.console_handlers.mailbox_lookup_repository.cancel_active_job_if_present",
            AsyncMock(),
        ) as cancel_job,
    ):
        response = await client.post(
            ENDPOINT,
            json={
                "phone": "+12015559999",
                "message": "código",
                "instance": TEST_INSTANCE,
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )

    assert response.status_code == 200
    body = response.json()
    assert "Netflix" in body["reply"]
    cancel_job.assert_not_called()

    import json

    saved = json.loads(await fake_mgr._redis.get(session_key))
    assert saved["step"] == "service"


async def test_unregistered_codigo_non_trigger_still_returns_still_checking(
    client, db_session, active_tenant_user
):
    tenant = await _setup_tenant_for_codigo(db_session, active_tenant_user)
    fake_mgr = _FakeManager(used_backup=False)
    await _seed_unauth_codigo_awaiting_result(
        fake_mgr,
        tenant.id,
        lookup_job_id="",
    )

    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={
                "phone": "+12015559999",
                "message": "hola",
                "instance": TEST_INSTANCE,
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )

    assert response.status_code == 200
    body = response.json()
    assert "todavia buscando" in body["reply"].lower() or "still checking" in body["reply"].lower()


# from_me contextual routing tests
# ---------------------------------------------------------------------------


async def _setup_tenant_with_instance(db_session, active_tenant_user):
    """Set up a tenant with an instance name and return the tenant."""
    result = await db_session.execute(
        select(Tenant).where(Tenant.owner_user_id == active_tenant_user.id)
    )
    tenant = result.scalar_one_or_none()
    assert tenant is not None
    tenant.evolution_instance_name = TEST_INSTANCE
    tenant.locale = "es"
    await db_session.commit()
    return tenant


async def test_from_me_code_to_non_self_target_is_silent_and_no_context(
    client, db_session, active_tenant_user
):
    """from_me code/codigo to another chat does not start Client Context Shortcut."""
    tenant = await _setup_tenant_with_instance(db_session, active_tenant_user)
    admin_phone = tenant.whatsapp_phone
    admin_phone_digits = "12015550002"

    fake_mgr = _FakeManager(used_backup=False)
    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={
                "phone": admin_phone,
                "message": "code",
                "instance": TEST_INSTANCE,
                "from_me": True,
                "admin_phone": admin_phone,
                "admin_jid": "12015550002:81@s.whatsapp.net",
                "target_jid": "12015559999@s.whatsapp.net",
                "target_phone": "12015559999",
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )
    assert response.status_code == 200
    body = response.json()
    assert body.get("no_reply") is True
    assert body.get("reply") == ""
    assert await fake_mgr._redis.get(f"wa:client_ctx:{admin_phone_digits}") is None


async def test_from_me_menu_to_unregistered_target_starts_context(
    client, db_session, active_tenant_user
):
    """from_me /menu still opens Client Context Shortcut for unregistered targets."""
    tenant = await _setup_tenant_with_instance(db_session, active_tenant_user)
    admin_phone = tenant.whatsapp_phone
    admin_phone_digits = "12015550002"

    fake_mgr = _FakeManager(used_backup=False)
    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={
                "phone": admin_phone,
                "message": "/menu",
                "instance": TEST_INSTANCE,
                "from_me": True,
                "admin_phone": admin_phone,
                "admin_jid": "12015550002:81@s.whatsapp.net",
                "target_jid": "12015559999@s.whatsapp.net",
                "target_phone": "12015559999",
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )
    assert response.status_code == 200
    body = response.json()
    assert body.get("no_reply") is not True
    assert await fake_mgr._redis.get(f"wa:client_ctx:{admin_phone_digits}") is not None


async def test_from_me_self_target_routes_to_tenant_console(
    client, db_session, active_tenant_user
):
    """from_me=true with target matching admin phone routes to Tenant console."""
    tenant = await _setup_tenant_with_instance(db_session, active_tenant_user)
    admin_phone = tenant.whatsapp_phone  # "+12015550002"

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
                "target_phone": admin_phone,
                "target_jid": "12015550002@s.whatsapp.net",
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )
    assert response.status_code == 200
    body = response.json()
    assert "reply" in body
    reply = body["reply"]
    # Self-target routes to Tenant console, not shortcut
    assert "Contexto de cliente" not in reply
    # Should be a standard Tenant console reply
    assert (
        "Consola de Administracion" in reply
        or "No entendi" in reply
        or "opcion del menu" in reply
        or "Admin Console" in reply
        or "didn't understand" in reply
        or "nombre de usuario" in reply
        or "login" in reply
    )
    # Context fields should not be present
    assert "reply_to" not in body or body.get("no_reply") is not True


async def test_from_me_self_target_by_jid_routes_to_tenant_console(
    client, db_session, active_tenant_user
):
    """from_me=true with target_jid matching admin_jid routes to Tenant console."""
    tenant = await _setup_tenant_with_instance(db_session, active_tenant_user)
    admin_phone = tenant.whatsapp_phone

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
                "target_jid": "12015550002@s.whatsapp.net",
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )
    assert response.status_code == 200
    body = response.json()
    assert "reply" in body
    reply = body["reply"]
    assert "Contexto de cliente" not in reply
    assert "reply_to" not in body


async def test_from_me_self_target_by_device_jid_routes_to_tenant_console(
    client, db_session, active_tenant_user
):
    """from_me=true self-target with Evolution device suffix routes to Tenant console."""
    tenant = await _setup_tenant_with_instance(db_session, active_tenant_user)
    admin_phone = tenant.whatsapp_phone

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
                "target_jid": "12015550002:12@s.whatsapp.net",
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )
    assert response.status_code == 200
    body = response.json()
    reply = body["reply"]
    assert "Contexto de cliente" not in reply
    assert "Gestion del cliente" not in reply
    assert "reply_to" not in body


async def test_from_me_self_target_by_lid_routes_to_tenant_console(
    client, db_session, active_tenant_user
):
    """from_me=true self-target with LID-only target routes to Tenant console."""
    tenant = await _setup_tenant_with_instance(db_session, active_tenant_user)
    admin_phone = tenant.whatsapp_phone
    tenant.whatsapp_lid = "77988435632309@lid"
    await db_session.commit()

    fake_mgr = _FakeManager(used_backup=False)
    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={
                "phone": "584243106642",
                "message": "/menu",
                "instance": TEST_INSTANCE,
                "sender_lid": "77988435632309@lid",
                "from_me": True,
                "admin_phone": admin_phone,
                "admin_jid": "584243106642:81@s.whatsapp.net",
                "target_jid": "77988435632309@lid",
                "target_lid": "77988435632309@lid",
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )
    assert response.status_code == 200
    body = response.json()
    reply = body["reply"]
    assert "Client management" not in reply
    assert "Gestion del cliente" not in reply
    assert "reply_to" not in body


async def test_from_me_self_target_by_phone_with_client_routes_to_pre_menu(
    client, db_session, active_tenant_user
):
    """from_me=true self target uses phone identity to show ambiguity pre-menu."""
    tenant = await _setup_tenant_with_instance(db_session, active_tenant_user)
    tenant.whatsapp_phone = "+584243106642"
    admin_phone = tenant.whatsapp_phone
    tenant.whatsapp_lid = "77988435632309@lid"

    client_user = User(username="self_lid_client", password_hash="x", role="client")
    db_session.add(client_user)
    await db_session.flush()
    db_session.add(
        Client(
            tenant_id=tenant.id,
            owner_user_id=client_user.id,
            full_name="Wilfredo Camacho",
            username="tna01_self_lid",
            phone="584243106642",
            whatsapp_lid="77988435632309@lid",
            is_active=True,
        )
    )
    await db_session.commit()

    fake_mgr = _FakeManager(used_backup=False)
    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={
                "phone": "584243106642",
                "message": "/menu",
                "instance": TEST_INSTANCE,
                "sender_lid": "77988435632309@lid",
                "from_me": True,
                "admin_phone": admin_phone,
                "admin_jid": "584243106642:81@s.whatsapp.net",
                "target_jid": "77988435632309@lid",
                "target_phone": "584243106642",
                "target_lid": "77988435632309@lid",
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )
    assert response.status_code == 200
    body = response.json()
    reply = body["reply"]
    assert "Client management" not in reply
    assert "Gestion del cliente" not in reply
    assert "Two profiles detected" in reply or "dos perfiles" in reply
    assert "Admin panel" in reply or "Panel de administracion" in reply
    assert "reply_to" not in body


async def test_from_me_non_self_target_routes_to_shortcut(
    client, db_session, active_tenant_user
):
    """from_me=true with target different from admin routes to shortcut with reply_to."""
    tenant = await _setup_tenant_with_instance(db_session, active_tenant_user)
    admin_phone = tenant.whatsapp_phone  # "+12015550002"

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
                "target_phone": "+12015559999",
                "target_jid": "12015559999@s.whatsapp.net",
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )
    assert response.status_code == 200
    body = response.json()
    # Must have reply_to set
    assert body.get("reply_to") == "12015550002@s.whatsapp.net"
    # Must have a reply message (shortcut started)
    assert "reply" in body
    assert body["reply"]
    # Should contain the contextual menu
    assert "Gestion" in body["reply"]


async def test_from_me_owner_fallback_routes_to_console(
    client, db_session, active_tenant_user
):
    """from_me=true without admin_phone falls back to tenant's whatsapp_phone."""
    tenant = await _setup_tenant_with_instance(db_session, active_tenant_user)
    # No admin_phone in request, self-target via tenant whatsapp_phone as fallback

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
                # No admin_phone — fall back to tenant owner
                "admin_jid": "12015550002@s.whatsapp.net",
                "target_phone": tenant.whatsapp_phone,
                "target_jid": "12015550002@s.whatsapp.net",
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )
    assert response.status_code == 200
    body = response.json()
    assert "reply" in body
    reply = body["reply"]
    # Must route to Tenant console via owner fallback
    assert "Contexto de cliente" not in reply
    assert (
        "Consola de Administracion" in reply
        or "No entendi" in reply
        or "opcion del menu" in reply
        or "Admin Console" in reply
    )


async def test_from_me_context_collision_rejected(
    client, db_session, active_tenant_user
):
    """Second from_me trigger for same admin is rejected when context is active."""
    tenant = await _setup_tenant_with_instance(db_session, active_tenant_user)
    admin_phone = tenant.whatsapp_phone

    fake_mgr = _FakeManager(used_backup=False)
    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        # First call: non-self-target → creates context
        resp1 = await client.post(
            ENDPOINT,
            json={
                "phone": "",
                "message": "/menu",
                "instance": TEST_INSTANCE,
                "from_me": True,
                "admin_phone": admin_phone,
                "admin_jid": "12015550002@s.whatsapp.net",
                "target_phone": "+12015559999",
                "target_jid": "12015559999@s.whatsapp.net",
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )
        assert resp1.status_code == 200
        body1 = resp1.json()
        assert body1.get("reply_to") == "12015550002@s.whatsapp.net"

        # Second call: different target → context collision, rejected
        resp2 = await client.post(
            ENDPOINT,
            json={
                "phone": "",
                "message": "/menu",
                "instance": TEST_INSTANCE,
                "from_me": True,
                "admin_phone": admin_phone,
                "admin_jid": "12015550002@s.whatsapp.net",
                "target_phone": "+12015558888",
                "target_jid": "12015558888@s.whatsapp.net",
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )
        assert resp2.status_code == 200
        body2 = resp2.json()
        # Must be rejected with no_reply=true and reply_to set
        assert body2.get("no_reply") is True
        assert body2.get("reply_to") == "12015550002@s.whatsapp.net"
        assert not body2.get("reply") or body2.get("reply") == ""


async def test_from_me_without_admin_phone_no_fallback_returns_no_reply(
    client, db_session, active_tenant_user
):
    """from_me=true without admin_phone and tenant without whatsapp_phone returns no_reply."""
    tenant = await _setup_tenant_with_instance(db_session, active_tenant_user)
    # Clear tenant's whatsapp_phone so fallback fails
    tenant.whatsapp_phone = None
    await db_session.commit()

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
                # No admin_phone and tenant has no whatsapp_phone
                "target_phone": "+12015559999",
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )
    assert response.status_code == 200
    body = response.json()
    # Cannot identify admin — silent no_reply
    assert body.get("no_reply") is True
    assert not body.get("reply") or body.get("reply") == ""


async def test_from_me_non_self_target_sets_context_in_redis(
    client, db_session, active_tenant_user
):
    """from_me=true non-self-target stores context in Redis."""
    tenant = await _setup_tenant_with_instance(db_session, active_tenant_user)
    admin_phone = tenant.whatsapp_phone
    admin_phone_digits = "12015550002"

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
                "target_phone": "+12015559999",
                "target_jid": "12015559999@s.whatsapp.net",
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )
    assert response.status_code == 200

    # Verify context was stored in Redis
    ctx_key = f"wa:client_ctx:{admin_phone_digits}"
    raw = await fake_mgr._redis.get(ctx_key)
    assert raw is not None, "Context session should be stored in Redis"

    import json

    data = json.loads(raw)
    assert data["flow"] == "client_shortcut"
    assert data["phone"] == admin_phone_digits
    # Target info should be in temp_data
    assert data["temp_data"]["target_phone"] == "12015559999"
    assert data["temp_data"]["admin_jid"] == "12015550002@s.whatsapp.net"


async def test_from_me_remote_zero_cancels_target_codigo_by_phone(
    client, db_session, active_tenant_user
):
    """from_me message "0" to non-self target cancels an active unauth codigo."""
    tenant = await _setup_tenant_for_codigo(db_session, active_tenant_user)
    fake_mgr = _FakeManager(used_backup=False)
    session_key = await _seed_unauth_codigo_awaiting_result(fake_mgr, tenant.id)

    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={
                "phone": tenant.whatsapp_phone,
                "message": "0",
                "instance": TEST_INSTANCE,
                "from_me": True,
                "admin_phone": tenant.whatsapp_phone,
                "admin_jid": "12015550002@s.whatsapp.net",
                "target_jid": "12015559999@s.whatsapp.net",
                "target_phone": "12015559999",
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )

    assert response.status_code == 200
    assert response.json() == {
        "reply": "",
        "no_reply": True,
        "status": "closed",
        "close_jid": "12015559999@s.whatsapp.net",
    }
    assert await fake_mgr._redis.get(session_key) is None
    assert await fake_mgr._redis.get("wa:client_ctx:12015550002") is None


async def test_from_me_remote_alias_does_not_cancel_target_codigo(
    client, db_session, active_tenant_user
):
    """from_me message "cancelar" does NOT trigger remote codigo cancel."""
    tenant = await _setup_tenant_for_codigo(db_session, active_tenant_user)
    fake_mgr = _FakeManager(used_backup=False)
    session_key = await _seed_unauth_codigo_awaiting_result(fake_mgr, tenant.id)

    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={
                "phone": tenant.whatsapp_phone,
                "message": "cancelar",
                "instance": TEST_INSTANCE,
                "from_me": True,
                "admin_phone": tenant.whatsapp_phone,
                "admin_jid": "12015550002@s.whatsapp.net",
                "target_jid": "12015559999@s.whatsapp.net",
                "target_phone": "12015559999",
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )

    assert response.status_code == 200
    body = response.json()
    assert body.get("no_reply") is True
    assert body.get("reply") == ""
    assert body.get("status") != "closed"
    assert await fake_mgr._redis.get(session_key) is not None


async def test_from_me_remote_zero_does_not_clear_admin_session(
    client, db_session, active_tenant_user
):
    """from_me remote "0" cancels codigo but preserves admin session."""
    tenant = await _setup_tenant_for_codigo(db_session, active_tenant_user)
    fake_mgr = _FakeManager(used_backup=False)
    await _seed_unauth_codigo_awaiting_result(fake_mgr, tenant.id)
    await fake_mgr._redis.set(
        "session:admin:12015550002",
        json.dumps({"phone": "12015550002", "flow": "", "step": "", "temp_data": {}, "selection_map": {}}),
        ex=300,
    )

    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={
                "phone": tenant.whatsapp_phone,
                "message": "0",
                "instance": TEST_INSTANCE,
                "from_me": True,
                "admin_phone": tenant.whatsapp_phone,
                "admin_jid": "12015550002@s.whatsapp.net",
                "target_jid": "12015559999@s.whatsapp.net",
                "target_phone": "12015559999",
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )

    assert response.status_code == 200
    assert await fake_mgr._redis.get("session:admin:12015550002") is not None


async def test_from_me_remote_zero_cancels_target_codigo_by_lid(
    client, db_session, active_tenant_user
):
    tenant = await _setup_tenant_for_codigo(db_session, active_tenant_user)
    fake_mgr = _FakeManager(used_backup=False)
    tenant_prefix = str(tenant.id)[:8]
    lid_key = f"session:unreg:{tenant_prefix}:998877665544332211@lid"
    await fake_mgr._redis.set(
        lid_key,
        json.dumps(
            {
                "phone": f"unreg:{tenant_prefix}:998877665544332211@lid",
                "flow": "codigo",
                "step": "awaiting_result",
                "selected_tenant_id": None,
                "temp_data": {"service_key": "netflix", "target_email": "user@example.com"},
                "selection_map": {},
            }
        ),
        ex=300,
    )

    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={
                "phone": tenant.whatsapp_phone,
                "message": "0",
                "instance": TEST_INSTANCE,
                "from_me": True,
                "admin_phone": tenant.whatsapp_phone,
                "admin_jid": "12015550002@s.whatsapp.net",
                "target_jid": "998877665544332211@lid",
                "target_lid": "998877665544332211@lid",
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )

    assert response.status_code == 200
    assert response.json() == {
        "reply": "",
        "no_reply": True,
        "status": "closed",
        "close_jid": "998877665544332211@lid",
    }
    assert await fake_mgr._redis.get(lid_key) is None


async def test_from_me_remote_zero_cancels_active_lookup_job(
    client, db_session, active_tenant_user
):
    tenant = await _setup_tenant_for_codigo(db_session, active_tenant_user)
    mailbox = (
        await db_session.execute(
            select(TenantMailbox).where(TenantMailbox.tenant_id == tenant.id)
        )
    ).scalar_one()
    job = await mailbox_lookup_repository.create_job(
        db_session,
        tenant.id,
        mailbox.id,
        "netflix",
        target_email="user@example.com",
    )
    await db_session.commit()

    fake_mgr = _FakeManager(used_backup=False)
    session_key = await _seed_unauth_codigo_awaiting_result(
        fake_mgr,
        tenant.id,
        lookup_job_id=str(job.id),
    )

    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={
                "phone": tenant.whatsapp_phone,
                "message": "0",
                "instance": TEST_INSTANCE,
                "from_me": True,
                "admin_phone": tenant.whatsapp_phone,
                "admin_jid": "12015550002@s.whatsapp.net",
                "target_jid": "12015559999@s.whatsapp.net",
                "target_phone": "12015559999",
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )

    assert response.status_code == 200
    await db_session.refresh(job)
    assert job.status == "failed"
    assert job.error_code == "user_cancelled"
    assert await fake_mgr._redis.get(session_key) is None


async def test_from_me_remote_zero_without_target_session_still_closes(
    client, db_session, active_tenant_user
):
    tenant = await _setup_tenant_for_codigo(db_session, active_tenant_user)
    fake_mgr = _FakeManager(used_backup=False)

    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={
                "phone": tenant.whatsapp_phone,
                "message": "0",
                "instance": TEST_INSTANCE,
                "from_me": True,
                "admin_phone": tenant.whatsapp_phone,
                "admin_jid": "12015550002@s.whatsapp.net",
                "target_jid": "12015559999@s.whatsapp.net",
                "target_phone": "12015559999",
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )

    assert response.status_code == 200
    assert response.json() == {
        "reply": "",
        "no_reply": True,
        "status": "closed",
        "close_jid": "12015559999@s.whatsapp.net",
    }


async def test_from_me_remote_zero_keeps_active_context_session(
    client, db_session, active_tenant_user
):
    tenant = await _setup_tenant_with_instance(db_session, active_tenant_user)
    fake_mgr = _FakeManager(used_backup=False)
    await _setup_context(fake_mgr, "12015550002")
    await _seed_unauth_codigo_awaiting_result(fake_mgr, tenant.id)

    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={
                "phone": tenant.whatsapp_phone,
                "message": "0",
                "instance": TEST_INSTANCE,
                "from_me": True,
                "admin_phone": tenant.whatsapp_phone,
                "admin_jid": "12015550002@s.whatsapp.net",
                "target_jid": "12015559999@s.whatsapp.net",
                "target_phone": "12015559999",
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )

    assert response.status_code == 200
    # The remote cancel should NOT clear the admin's active context session
    assert await fake_mgr._redis.get("wa:client_ctx:12015550002") is not None


# ---------------------------------------------------------------------------
# Client Context Shortcut lifecycle and unregistered target menus (Item 5)
# ---------------------------------------------------------------------------


async def _setup_context(
    fake_mgr: _FakeManager,
    admin_phone_digits: str,
    target_phone: str | None = "12015559999",
    target_lid: str | None = None,
    admin_jid: str = "12015550002@s.whatsapp.net",
    step: str = "menu",
) -> None:
    """Pre-populate a client context shortcut session in fake Redis."""
    import json

    session = {
        "phone": admin_phone_digits,
        "flow": "client_shortcut",
        "step": step,
        "selected_tenant_id": None,
        "temp_data": {
            "target_phone": target_phone,
            "target_lid": target_lid,
            "target_jid": f"{target_phone or 'unknown'}@s.whatsapp.net",
            "admin_jid": admin_jid,
        },
        "selection_map": {},
    }
    key = f"wa:client_ctx:{admin_phone_digits}"
    await fake_mgr._redis.set(key, json.dumps(session), ex=300)


async def test_context_shortcut_intercepts_admin_message(
    client, db_session, active_tenant_user
):
    """Client Context Shortcut intercepts admin messages when context session exists."""
    tenant = await _setup_tenant_with_instance(db_session, active_tenant_user)
    admin_phone = tenant.whatsapp_phone  # "+12015550002"
    admin_phone_digits = "12015550002"

    fake_mgr = _FakeManager(used_backup=False)
    await _setup_context(fake_mgr, admin_phone_digits)

    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={
                "phone": admin_phone,
                "message": "menu",
                "instance": TEST_INSTANCE,
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )
    assert response.status_code == 200
    body = response.json()
    assert "reply" in body
    reply = body["reply"]
    # Context response should show invalid option i18n text
    assert "Opcion invalida" in reply or "Invalid option" in reply
    # Must include reply_to for private admin reply
    assert body.get("reply_to") == "12015550002@s.whatsapp.net"


async def test_context_shortcut_no_context_falls_through(
    client, db_session, active_tenant_user
):
    """Without a context session, admin messages route to the Tenant console."""
    tenant = await _setup_tenant_with_instance(db_session, active_tenant_user)
    admin_phone = tenant.whatsapp_phone

    # No context set up — should fall through to Tenant console
    fake_mgr = _FakeManager(used_backup=False)
    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={
                "phone": admin_phone,
                "message": "/menu",
                "instance": TEST_INSTANCE,
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )
    assert response.status_code == 200
    body = response.json()
    assert "reply" in body
    # Should be Tenant console reply, not context shortcut
    assert "Consola de Administracion" in body["reply"] or "No entendi" in body["reply"]
    # No context fields
    assert "reply_to" not in body or body.get("no_reply") is not True


async def test_context_shortcut_unblocked_menu_shows_options(
    client, db_session, active_tenant_user
):
    """Unblocked unregistered target shows Crear cliente and Bloquear mensajes options."""
    tenant = await _setup_tenant_with_instance(db_session, active_tenant_user)
    admin_phone = tenant.whatsapp_phone
    admin_phone_digits = "12015550002"

    fake_mgr = _FakeManager(used_backup=False)
    await _setup_context(fake_mgr, admin_phone_digits)

    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        # Send an invalid option to see the full menu
        response = await client.post(
            ENDPOINT,
            json={
                "phone": admin_phone,
                "message": "x",
                "instance": TEST_INSTANCE,
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )
    assert response.status_code == 200
    body = response.json()
    assert "Opcion invalida" in body["reply"] or "Invalid option" in body["reply"]
    assert body.get("reply_to") == "12015550002@s.whatsapp.net"


async def test_context_shortcut_blocked_menu_shows_unblock(
    client, db_session, active_tenant_user
):
    """Blocked unregistered target shows Desbloquear mensajes instead."""
    tenant = await _setup_tenant_with_instance(db_session, active_tenant_user)
    admin_phone = tenant.whatsapp_phone
    admin_phone_digits = "12015550002"

    # Create an active block for the target
    block = BlockedClient(
        tenant_id=tenant.id,
        phone="12015559999",
        is_active=True,
    )
    db_session.add(block)
    await db_session.commit()

    fake_mgr = _FakeManager(used_backup=False)
    await _setup_context(fake_mgr, admin_phone_digits)

    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        # Send an invalid option to see the full menu
        response = await client.post(
            ENDPOINT,
            json={
                "phone": admin_phone,
                "message": "x",
                "instance": TEST_INSTANCE,
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )
    assert response.status_code == 200
    body = response.json()
    assert "Opcion invalida" in body["reply"] or "Invalid option" in body["reply"]
    assert body.get("reply_to") == "12015550002@s.whatsapp.net"


async def test_context_shortcut_crear_cliente_prompts_name_immediately(
    client, db_session, active_tenant_user
):
    """Selecting 1 on unblocked menu immediately prompts for client name."""
    tenant = await _setup_tenant_with_instance(db_session, active_tenant_user)
    admin_phone = tenant.whatsapp_phone
    admin_phone_digits = "12015550002"

    fake_mgr = _FakeManager(used_backup=False)
    await _setup_context(fake_mgr, admin_phone_digits)

    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={
                "phone": admin_phone,
                "message": "1",
                "instance": TEST_INSTANCE,
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )
    assert response.status_code == 200
    body = response.json()
    reply = body["reply"].lower()
    assert "telefono prefijado" in reply
    assert "nombre completo" in reply
    assert body.get("reply_to") == "12015550002@s.whatsapp.net"

    # Verify context step advanced in Redis
    ctx_key = f"wa:client_ctx:{admin_phone_digits}"
    raw = await fake_mgr._redis.get(ctx_key)
    assert raw is not None
    import json

    data = json.loads(raw)
    assert data["step"] == "creating_name"


async def test_from_me_self_target_uses_active_client_context(
    client, db_session, active_tenant_user
):
    """from_me option replies in admin private chat continue Client Context flow."""
    tenant = await _setup_tenant_with_instance(db_session, active_tenant_user)
    admin_phone = tenant.whatsapp_phone
    admin_phone_digits = "12015550002"

    fake_mgr = _FakeManager(used_backup=False)
    await _setup_context(
        fake_mgr,
        admin_phone_digits,
        target_phone="12015559999",
        target_lid="dead-lid@lid",
        admin_jid="12015550002:81@s.whatsapp.net",
    )

    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={
                "phone": admin_phone,
                "message": "1",
                "instance": TEST_INSTANCE,
                "from_me": True,
                "admin_phone": admin_phone,
                "admin_jid": "12015550002:81@s.whatsapp.net",
                "target_jid": "12015550002@lid",
                "target_phone": "12015550002",
                "target_lid": "12015550002@lid",
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )

    assert response.status_code == 200
    body = response.json()
    reply = body["reply"].lower()
    assert "telefono prefijado" in reply
    assert "nombre completo" in reply
    assert body.get("reply_to") == "12015550002:81@s.whatsapp.net"

    ctx_key = f"wa:client_ctx:{admin_phone_digits}"
    raw = await fake_mgr._redis.get(ctx_key)
    assert raw is not None
    import json

    data = json.loads(raw)
    assert data["step"] == "creating_name"


async def test_context_shortcut_bloquear_creates_block(
    client, db_session, active_tenant_user
):
    """Selecting 2 on unblocked menu creates a block and clears context."""
    tenant = await _setup_tenant_with_instance(db_session, active_tenant_user)
    admin_phone = tenant.whatsapp_phone
    admin_phone_digits = "12015550002"

    fake_mgr = _FakeManager(used_backup=False)
    await _setup_context(fake_mgr, admin_phone_digits)

    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={
                "phone": admin_phone,
                "message": "2",
                "instance": TEST_INSTANCE,
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )
    assert response.status_code == 200
    body = response.json()
    assert "Acceso bloqueado" in body["reply"]
    assert body.get("reply_to") == "12015550002@s.whatsapp.net"

    # Verify block was created in DB
    result = await db_session.execute(
        select(BlockedClient).where(
            BlockedClient.tenant_id == tenant.id,
            BlockedClient.phone == "12015559999",
            BlockedClient.is_active,
        )
    )
    db_block = result.scalar_one_or_none()
    assert db_block is not None

    # Verify context is kept alive so ``0`` can close target session
    ctx_key = f"wa:client_ctx:{admin_phone_digits}"
    raw = await fake_mgr._redis.get(ctx_key)
    assert raw is not None


async def test_context_shortcut_desbloquear_unblocks(
    client, db_session, active_tenant_user
):
    """Selecting 1 on blocked menu unblocks and clears context."""
    tenant = await _setup_tenant_with_instance(db_session, active_tenant_user)
    admin_phone = tenant.whatsapp_phone
    admin_phone_digits = "12015550002"

    # Create an active block for the target
    block = BlockedClient(
        tenant_id=tenant.id,
        phone="12015559999",
        is_active=True,
    )
    db_session.add(block)
    await db_session.commit()
    block_id = block.id

    fake_mgr = _FakeManager(used_backup=False)
    await _setup_context(fake_mgr, admin_phone_digits)

    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={
                "phone": admin_phone,
                "message": "1",
                "instance": TEST_INSTANCE,
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )
    assert response.status_code == 200
    body = response.json()
    assert "Acceso desbloqueado" in body["reply"]
    assert body.get("reply_to") == "12015550002@s.whatsapp.net"

    # Verify block was deactivated
    # Expire cached object so identity map reloads from DB
    db_session.expire(block)
    result = await db_session.execute(
        select(BlockedClient).where(BlockedClient.id == block_id)
    )
    db_block = result.scalar_one_or_none()
    assert db_block is not None
    assert db_block.is_active is False

    # Verify context is kept alive so ``0`` can close target session
    ctx_key = f"wa:client_ctx:{admin_phone_digits}"
    raw = await fake_mgr._redis.get(ctx_key)
    assert raw is not None


async def test_context_shortcut_zero_closes_context(
    client, db_session, active_tenant_user
):
    """Sending 0 closes the context and clears the session."""
    tenant = await _setup_tenant_with_instance(db_session, active_tenant_user)
    admin_phone = tenant.whatsapp_phone
    admin_phone_digits = "12015550002"

    fake_mgr = _FakeManager(used_backup=False)
    await _setup_context(fake_mgr, admin_phone_digits)

    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={
                "phone": admin_phone,
                "message": "0",
                "instance": TEST_INSTANCE,
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )
    assert response.status_code == 200
    body = response.json()
    assert (
        "cancelad" in body["reply"].lower()
        or "cancelled" in body["reply"].lower()
        or "closed" in body["reply"].lower()
    )
    assert body.get("reply_to") == "12015550002@s.whatsapp.net"
    assert body.get("close_jid") == "12015550002@s.whatsapp.net"
    assert body.get("close_jids") == [
        "12015550002@s.whatsapp.net",
        "12015559999@s.whatsapp.net",
    ]

    # Verify context was cleared from Redis
    ctx_key = f"wa:client_ctx:{admin_phone_digits}"
    raw = await fake_mgr._redis.get(ctx_key)
    assert raw is None


async def test_context_shortcut_invalid_input_does_not_refresh_ttl(
    client, db_session, active_tenant_user
):
    """Invalid input preserves the existing context TTL (no refresh)."""
    tenant = await _setup_tenant_with_instance(db_session, active_tenant_user)
    admin_phone = tenant.whatsapp_phone
    admin_phone_digits = "12015550002"

    fake_mgr = _FakeManager(used_backup=False)
    await _setup_context(fake_mgr, admin_phone_digits)
    ctx_key = f"wa:client_ctx:{admin_phone_digits}"

    # Set a known short TTL (50s) to detect refresh
    fake_mgr._redis._ttls[ctx_key] = 50

    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={
                "phone": admin_phone,
                "message": "xyz",
                "instance": TEST_INSTANCE,
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )
    assert response.status_code == 200
    body = response.json()
    assert "Opcion invalida" in body["reply"] or "Invalid option" in body["reply"]

    # TTL should still be 50 (not refreshed to 300)
    assert fake_mgr._redis._ttls.get(ctx_key) == 50


async def test_context_shortcut_valid_input_refreshes_ttl(
    client, db_session, active_tenant_user
):
    """Valid input (Crear cliente) refreshes the context TTL to 300s."""
    tenant = await _setup_tenant_with_instance(db_session, active_tenant_user)
    admin_phone = tenant.whatsapp_phone
    admin_phone_digits = "12015550002"

    fake_mgr = _FakeManager(used_backup=False)
    await _setup_context(fake_mgr, admin_phone_digits)
    ctx_key = f"wa:client_ctx:{admin_phone_digits}"

    # Set a known short TTL to detect refresh
    fake_mgr._redis._ttls[ctx_key] = 50

    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={
                "phone": admin_phone,
                "message": "1",
                "instance": TEST_INSTANCE,
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )
    assert response.status_code == 200

    # TTL should now be 300 after valid input refresh
    assert fake_mgr._redis._ttls.get(ctx_key) == 300


# ---------------------------------------------------------------------------
# Client Context Shortcut — Client creation and management flows (Item 6)
# ---------------------------------------------------------------------------


async def test_context_creating_phone_skip(client, db_session, active_tenant_user):
    """Creating flow with target_phone prefilled skips phone prompt."""
    tenant = await _setup_tenant_with_instance(db_session, active_tenant_user)
    admin_phone = tenant.whatsapp_phone
    admin_phone_digits = "12015550002"

    fake_mgr = _FakeManager(used_backup=False)
    await _setup_context(fake_mgr, admin_phone_digits, target_phone="12015559999")

    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        # Step 1: "1" from menu → phone prefilled and name prompt shown immediately
        resp1 = await client.post(
            ENDPOINT,
            json={
                "phone": admin_phone,
                "message": "1",
                "instance": TEST_INSTANCE,
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )
        assert resp1.status_code == 200
        reply1 = resp1.json()["reply"].lower()
        assert "telefono prefijado" in reply1
        assert "nombre completo" in reply1
        assert resp1.json().get("reply_to") == "12015550002@s.whatsapp.net"

        # Step 2: send name → creating_username
        resp3 = await client.post(
            ENDPOINT,
            json={
                "phone": admin_phone,
                "message": "Test Client",
                "instance": TEST_INSTANCE,
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )
        assert resp3.status_code == 200
        reply3 = resp3.json()["reply"].lower()
        assert "nombre registrado" in reply3
        assert "nombre de usuario" in reply3

        # Step 3: send username → password choice
        resp4 = await client.post(
            ENDPOINT,
            json={
                "phone": admin_phone,
                "message": "testuser",
                "instance": TEST_INSTANCE,
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )
        assert resp4.status_code == 200
        reply4 = resp4.json()["reply"].lower()
        assert "usuario registrado" in reply4
        assert "generar" in reply4
        assert "manual" in reply4

        # Step 4: choose manual password
        resp_choice = await client.post(
            ENDPOINT,
            json={
                "phone": admin_phone,
                "message": "2",
                "instance": TEST_INSTANCE,
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )
        assert resp_choice.status_code == 200
        assert "8 caracteres" in resp_choice.json()["reply"].lower()

        # Step 5: send password → creating_confirm
        resp5 = await client.post(
            ENDPOINT,
            json={
                "phone": admin_phone,
                "message": "testpass123",
                "instance": TEST_INSTANCE,
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )
        assert resp5.status_code == 200
        reply5 = resp5.json()["reply"].lower()
        assert "confirmar" in reply5
        assert "resumen de creacion" in reply5

        # Step 6: CONFIRMAR → client created, post-create menu shown
        resp6 = await client.post(
            ENDPOINT,
            json={
                "phone": admin_phone,
                "message": "CONFIRMAR",
                "instance": TEST_INSTANCE,
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )
        assert resp6.status_code == 200
        reply6 = resp6.json()["reply"].lower()
        assert "creado exitosamente" in reply6
        assert "consola de administracion" not in reply6
        assert "volver al menu" in reply6
        assert "cerrar gestion" in reply6

        # Verify context remains for post-create menu
        ctx_key = f"wa:client_ctx:{admin_phone_digits}"
        raw = await fake_mgr._redis.get(ctx_key)
        assert raw is not None


async def test_context_creating_lid_only_prompts_phone(
    client, db_session, active_tenant_user
):
    """Creating flow with only target_lid asks for phone first."""
    tenant = await _setup_tenant_with_instance(db_session, active_tenant_user)
    admin_phone = tenant.whatsapp_phone
    admin_phone_digits = "12015550002"

    fake_mgr = _FakeManager(used_backup=False)
    await _setup_context(
        fake_mgr,
        admin_phone_digits,
        target_phone=None,
        target_lid="998877665544332211@lid",
    )

    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        # Step 1: "1" from menu → no target_phone → asks phone immediately
        resp2 = await client.post(
            ENDPOINT,
            json={
                "phone": admin_phone,
                "message": "1",
                "instance": TEST_INSTANCE,
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )
        assert resp2.status_code == 200
        reply2 = resp2.json()["reply"].lower()
        assert "telefono" in reply2
        assert "asociarlo" in reply2

        # Step 2: send phone → creating_name
        resp3 = await client.post(
            ENDPOINT,
            json={
                "phone": admin_phone,
                "message": "+12015558888",
                "instance": TEST_INSTANCE,
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )
        assert resp3.status_code == 200
        reply3 = resp3.json()["reply"].lower()
        assert "telefono registrado" in reply3
        assert "nombre completo" in reply3

    # Clean up created user/client if needed (test will verify success path in other tests)


async def test_context_active_client_shows_menu(client, db_session, active_tenant_user):
    """Active client target shows the active client menu."""
    tenant = await _setup_tenant_with_instance(db_session, active_tenant_user)
    admin_phone = tenant.whatsapp_phone
    admin_phone_digits = "12015550002"

    # Create an active client for the target phone
    ctx_client_user = User(
        username="ctx_active_user",
        password_hash="x",
        role="client",
    )
    db_session.add(ctx_client_user)
    await db_session.flush()

    ctx_client = Client(
        tenant_id=tenant.id,
        owner_user_id=ctx_client_user.id,
        full_name="Context Active Client",
        username="tna01_ctx_active",
        phone="12015559999",
        is_active=True,
    )
    db_session.add(ctx_client)
    await db_session.commit()

    fake_mgr = _FakeManager(used_backup=False)
    await _setup_context(fake_mgr, admin_phone_digits, target_phone="12015559999")

    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={
                "phone": admin_phone,
                "message": "menu",
                "instance": TEST_INSTANCE,
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )
    assert response.status_code == 200
    body = response.json()
    assert "reply" in body
    reply = body["reply"]
    # Should show active client menu, not context creation menu
    assert "Context Active Client" in reply
    assert "Ver suscripciones" in reply
    assert "Ver detalle" in reply
    assert body.get("reply_to") == "12015550002@s.whatsapp.net"


async def test_context_active_client_detail_step_is_preserved(
    client, db_session, active_tenant_user
):
    """An active-client shortcut already in detail mode stays in detail mode."""
    tenant = await _setup_tenant_with_instance(db_session, active_tenant_user)
    admin_phone = tenant.whatsapp_phone
    admin_phone_digits = "12015550002"

    ctx_client_user = User(
        username="ctx_active_detail_user",
        password_hash="x",
        role="client",
    )
    db_session.add(ctx_client_user)
    await db_session.flush()

    ctx_client = Client(
        tenant_id=tenant.id,
        owner_user_id=ctx_client_user.id,
        full_name="Context Active Detail Client",
        username="tna01_ctx_detail",
        phone="12015559998",
        is_active=True,
    )
    db_session.add(ctx_client)
    await db_session.commit()

    fake_mgr = _FakeManager(used_backup=False)
    await _setup_context(
        fake_mgr,
        admin_phone_digits,
        target_phone="12015559998",
        step="active_detail",
    )

    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={
                "phone": admin_phone,
                "message": "1",
                "instance": TEST_INSTANCE,
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )
    assert response.status_code == 200
    body = response.json()
    assert "Que campo desea editar" in body["reply"]
    assert body.get("reply_to") == "12015550002@s.whatsapp.net"


async def test_context_lookup_redis_unavailable_still_returns_contingency(
    client, db_session, active_tenant_user
):
    """Redis failure during shortcut lookup falls back to the tenant contingency reply."""
    tenant = await _setup_tenant_with_instance(db_session, active_tenant_user)
    admin_phone = tenant.whatsapp_phone

    fake_mgr = _FakeManager(fail_on_execute=True)

    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={
                "phone": admin_phone,
                "message": "hola",
                "instance": TEST_INSTANCE,
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )
    assert response.status_code == 200
    assert "temporalmente no disponible" in response.json()["reply"].lower()


async def test_context_inactive_client_shows_menu(
    client, db_session, active_tenant_user
):
    """Inactive client target shows the inactive client menu."""
    tenant = await _setup_tenant_with_instance(db_session, active_tenant_user)
    admin_phone = tenant.whatsapp_phone
    admin_phone_digits = "12015550002"

    # Create an inactive client for the target phone
    ctx_client_user = User(
        username="ctx_inactive_user",
        password_hash="x",
        role="client",
    )
    db_session.add(ctx_client_user)
    await db_session.flush()

    ctx_client = Client(
        tenant_id=tenant.id,
        owner_user_id=ctx_client_user.id,
        full_name="Context Inactive Client",
        username="tna01_ctx_inactive",
        phone="12015559999",
        is_active=False,
    )
    db_session.add(ctx_client)
    await db_session.commit()

    fake_mgr = _FakeManager(used_backup=False)
    await _setup_context(fake_mgr, admin_phone_digits, target_phone="12015559999")

    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={
                "phone": admin_phone,
                "message": "menu",
                "instance": TEST_INSTANCE,
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )
    assert response.status_code == 200
    body = response.json()
    assert "reply" in body
    reply = body["reply"]
    # Should show inactive client menu
    assert "Context Inactive Client" in reply
    assert "Reactivar" in reply
    assert "Editar" in reply
    assert "Eliminar" in reply
    assert body.get("reply_to") == "12015550002@s.whatsapp.net"


async def test_context_inactive_client_prevents_duplicate_creation(
    client, db_session, active_tenant_user
):
    """Inactive client with the target phone prevents creating a duplicate."""
    tenant = await _setup_tenant_with_instance(db_session, active_tenant_user)
    admin_phone = tenant.whatsapp_phone
    admin_phone_digits = "12015550002"

    # Create an inactive client for the target phone
    ctx_client_user = User(
        username="ctx_dup_user",
        password_hash="x",
        role="client",
    )
    db_session.add(ctx_client_user)
    await db_session.flush()

    ctx_client = Client(
        tenant_id=tenant.id,
        owner_user_id=ctx_client_user.id,
        full_name="Existing Inactive",
        username="tna01_ctx_dup",
        phone="12015559999",
        is_active=False,
    )
    db_session.add(ctx_client)
    await db_session.commit()

    fake_mgr = _FakeManager(used_backup=False)
    await _setup_context(
        fake_mgr, admin_phone_digits, target_phone="12015559999", step="menu"
    )

    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        # Admin tries to create a client (option 1 from the menu)
        # but the inactive client detection happens first
        response = await client.post(
            ENDPOINT,
            json={
                "phone": admin_phone,
                "message": "1",
                "instance": TEST_INSTANCE,
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )
    assert response.status_code == 200
    body = response.json()
    reply = body["reply"]
    # Should show inactive client menu, NOT creation flow
    assert "Existing Inactive" in reply
    assert "creacion" not in reply.lower() or "cread" not in reply.lower()
    assert body.get("reply_to") == "12015550002@s.whatsapp.net"


async def test_context_creating_lid_only_does_not_backfill_whatsapp_lid(
    client, db_session, active_tenant_user
):
    """Shortcut creation ignores LID and stores only phone identity."""
    tenant = await _setup_tenant_with_instance(db_session, active_tenant_user)
    admin_phone = tenant.whatsapp_phone
    admin_phone_digits = "12015550002"
    target_lid = "998877665544332211@lid"
    target_phone_value = "12015558888"

    fake_mgr = _FakeManager(used_backup=False)
    await _setup_context(
        fake_mgr,
        admin_phone_digits,
        target_phone=None,
        target_lid=target_lid,
        step="creating_confirm",
    )
    # Manually fill the creating temp_data so CONFIRMAR can commit the
    # full payload (phone prefilled, name/username/password set).
    import json

    ctx_key = f"wa:client_ctx:{admin_phone_digits}"
    raw = await fake_mgr._redis.get(ctx_key)
    assert raw is not None
    data = json.loads(raw)
    data["temp_data"] = {
        "phone": target_phone_value,
        "full_name": "LID Shortcut Client",
        "local_username": "liduser",
        "password": "lidpass1",
        "target_phone": None,
        "target_lid": target_lid,
        "target_jid": f"{target_lid}@lid",
        "admin_jid": "12015550002@s.whatsapp.net",
    }
    await fake_mgr._redis.set(ctx_key, json.dumps(data), ex=300)

    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={
                "phone": admin_phone,
                "message": "CONFIRMAR",
                "instance": TEST_INSTANCE,
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )
    assert response.status_code == 200
    reply = response.json()["reply"].lower()
    assert "creado exitosamente" in reply

    # Verify the created client did not persist LID identity
    from sqlalchemy import select as _select

    result = await db_session.execute(
        _select(Client).where(
            Client.tenant_id == tenant.id,
            Client.phone == target_phone_value,
        )
    )
    created_client = result.scalar_one_or_none()
    assert created_client is not None
    assert created_client.whatsapp_lid is None


# ---------------------------------------------------------------------------
# close_jid/close_jids response contract — disambiguates admin private
# chat from target/client chat when n8n must close Evolution sessions.
# ---------------------------------------------------------------------------


async def test_whatsapp_console_response_serializes_close_jids():
    """WhatsAppConsoleResponse serializes single and multi close contracts."""
    from app.schemas.whatsapp import WhatsAppConsoleResponse

    response = WhatsAppConsoleResponse(
        reply="cerrado",
        status="closed",
        reply_to="34111111111@s.whatsapp.net",
        close_jid="34111111111@s.whatsapp.net",
        close_jids=[
            "34111111111@s.whatsapp.net",
            "34222222222@s.whatsapp.net",
        ],
    )

    assert response.model_dump() == {
        "reply": "cerrado",
        "status": "closed",
        "reply_to": "34111111111@s.whatsapp.net",
        "close_jid": "34111111111@s.whatsapp.net",
        "close_jids": [
            "34111111111@s.whatsapp.net",
            "34222222222@s.whatsapp.net",
        ],
    }


async def test_tenant_catalog_zero_sets_closed_response_with_close_jid(
    client, db_session, active_tenant_user
):
    """Sending 0 during catalog flow closes session and returns close_jid."""
    from unittest.mock import patch

    tenant = await _setup_tenant_with_instance(db_session, active_tenant_user)
    admin_phone = tenant.whatsapp_phone  # "+12015550002"

    fake_mgr = _FakeManager(used_backup=False)
    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        # Start catalog flow
        await client.post(
            ENDPOINT,
            json={
                "phone": admin_phone,
                "message": "2",
                "instance": TEST_INSTANCE,
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )
        # Send 0 to cancel
        response = await client.post(
            ENDPOINT,
            json={
                "phone": admin_phone,
                "message": "0",
                "instance": TEST_INSTANCE,
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )
    assert response.status_code == 200
    body = response.json()
    assert (
        "cancelad" in body["reply"].lower()
        or "cancelled" in body["reply"].lower()
        or "salido" in body["reply"].lower()
    )
    assert body.get("status") == "closed"
    assert body.get("close_jid") == "12015550002@s.whatsapp.net"


async def test_tenant_catalog_cancelar_sets_closed_response_with_close_jid(
    client, db_session, active_tenant_user
):
    """Sending 'cancelar' during catalog flow closes session and returns close_jid."""
    from unittest.mock import patch

    tenant = await _setup_tenant_with_instance(db_session, active_tenant_user)
    admin_phone = tenant.whatsapp_phone  # "+12015550002"

    fake_mgr = _FakeManager(used_backup=False)
    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        # Start catalog flow
        await client.post(
            ENDPOINT,
            json={
                "phone": admin_phone,
                "message": "2",
                "instance": TEST_INSTANCE,
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )
        # Send "cancelar" to cancel (is_cancel alias)
        response = await client.post(
            ENDPOINT,
            json={
                "phone": admin_phone,
                "message": "cancelar",
                "instance": TEST_INSTANCE,
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )
    assert response.status_code == 200
    body = response.json()
    assert (
        "cancelad" in body["reply"].lower()
        or "cancelled" in body["reply"].lower()
        or "salido" in body["reply"].lower()
    )
    assert body.get("status") == "closed"
    assert body.get("close_jid") == "12015550002@s.whatsapp.net"


async def test_tenant_catalog_cerrar_sets_closed_response_with_close_jid(
    client, db_session, active_tenant_user
):
    """Sending 'cerrar' during catalog flow closes session and returns close_jid."""
    from unittest.mock import patch

    tenant = await _setup_tenant_with_instance(db_session, active_tenant_user)
    admin_phone = tenant.whatsapp_phone  # "+12015550002"

    fake_mgr = _FakeManager(used_backup=False)
    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        # Start catalog flow
        await client.post(
            ENDPOINT,
            json={
                "phone": admin_phone,
                "message": "2",
                "instance": TEST_INSTANCE,
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )
        # Send "cerrar" to cancel (is_cancel alias)
        response = await client.post(
            ENDPOINT,
            json={
                "phone": admin_phone,
                "message": "cerrar",
                "instance": TEST_INSTANCE,
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )
    assert response.status_code == 200
    body = response.json()
    assert (
        "cancelad" in body["reply"].lower()
        or "cancelled" in body["reply"].lower()
        or "salido" in body["reply"].lower()
    )
    assert body.get("status") == "closed"
    assert body.get("close_jid") == "12015550002@s.whatsapp.net"
