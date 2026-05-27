"""Tests for the n8n/backend WhatsApp Master Console contract.

Verifies API-key auth, Master/non-Master handling, and response shape.
"""

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.api.v1.endpoints.integrations import _TenantConsoleAdapter
from app.models import MasterProfile, Tenant
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
        "Consola de Administración" in reply
        or "No entendí" in reply
        or "opción del menú" in reply
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

    await fake_mgr._redis.set(auth_key, auth_session.model_dump_json(), ex=900)

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

    await fake_mgr._redis.set(auth_key, auth_session.model_dump_json(), ex=900)

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
    assert "Ver Tenants" in reply


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

    await fake_mgr._redis.set(auth_key, auth_session.model_dump_json(), ex=900)

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

    await fake_mgr._redis.set(auth_key, auth_session.model_dump_json(), ex=900)

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


async def test_instance_value_does_not_affect_auth_session_lookup(client, master_user):
    """Different instance values → same phone gets same auth session."""
    fake_mgr = _FakeManager(used_backup=False)

    auth_session = WhatsAppAuthSession(
        phone="12015550001",
        user_id=master_user.id,
        username=master_user.username,
        role="master",
        authenticated_at=datetime.now(timezone.utc),
    )
    auth_key = "wa:auth:12015550001"

    await fake_mgr._redis.set(auth_key, auth_session.model_dump_json(), ex=900)

    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        # Request with instance A
        resp_a = await client.post(
            ENDPOINT,
            json={
                "phone": "+12015550001",
                "message": "menu",
                "instance": "evolution-instance-a",
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )
        assert resp_a.status_code == 200
        reply_a = resp_a.json()["reply"]

        # Request with instance B
        resp_b = await client.post(
            ENDPOINT,
            json={
                "phone": "+12015550001",
                "message": "menu",
                "instance": "evolution-instance-b",
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )
        assert resp_b.status_code == 200
        reply_b = resp_b.json()["reply"]

    # Both replies must be the same (menu from auth session, not login prompt)
    assert reply_a == reply_b
    assert "Master Console" in reply_a or "Trackpal" in reply_a
    assert "usuario" not in reply_a.lower()


async def test_instance_value_does_not_affect_lockout_lookup(client, master_user):
    """Different instance values → same phone shares the same lockout state."""
    fake_mgr = _FakeManager(used_backup=False)

    # Create lock state using the same serialisation as the service
    lock_key = "wa:auth:lock:12015550001"
    lock_state = WhatsAppAuthLockState(
        locked_until=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    await fake_mgr._redis.set(lock_key, lock_state.model_dump_json(), ex=300)

    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        # Request with instance A
        resp_a = await client.post(
            ENDPOINT,
            json={"phone": "+12015550001", "message": "hola", "instance": "instance-x"},
            headers={"X-API-Key": settings.n8n_api_key},
        )
        assert resp_a.status_code == 200
        reply_a = resp_a.json()["reply"]

        # Request with instance B
        resp_b = await client.post(
            ENDPOINT,
            json={"phone": "+12015550001", "message": "hola", "instance": "instance-y"},
            headers={"X-API-Key": settings.n8n_api_key},
        )
        assert resp_b.status_code == 200
        reply_b = resp_b.json()["reply"]

    # Both replies must be the same (lockout message)
    assert reply_a == reply_b
    assert "demasiados intentos" in reply_a.lower() or "espera" in reply_a.lower()


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
        "wa:auth:12015550001", auth_session.model_dump_json(), ex=900
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
        "wa:auth:12015550001", auth_session.model_dump_json(), ex=900
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
