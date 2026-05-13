"""Tests for the n8n/backend WhatsApp Master Console contract.

Verifies API-key auth, Master/non-Master handling, and response shape.
"""

from typing import Any
from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.api.v1.endpoints.integrations import _TenantConsoleAdapter
from app.models import TenantProfile
from app.services.tenant_service import TenantService

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

    async def set(self, key: str, value: str, ex: int | None = None, keepttl: bool = False) -> None:
        self._store[key] = value
        if ex is not None:
            self._ttls[key] = ex
        elif not keepttl:
            self._ttls.pop(key, None)
        # keepttl=True: leave existing TTL untouched

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
        When ``True`` raises ``RuntimeError`` to simulate both stores down.
    """

    def __init__(
        self,
        *,
        used_backup: bool = False,
        fail_on_execute: bool = False,
    ) -> None:
        self._redis = _FakeRedis()
        self._used_backup = used_backup
        self._fail_on_execute = fail_on_execute

    @property
    def used_backup(self) -> bool:
        return self._used_backup

    async def execute(self, operation_name: str, async_callable: Any) -> Any:
        if self._fail_on_execute:
            raise RuntimeError("Both Redis stores unavailable")
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


async def test_unknown_phone_returns_access_denied(client):
    """Phone not found → 200 with access-denied reply n8n can relay."""
    response = await client.post(
        ENDPOINT,
        json={"phone": "+9999999999", "message": "hola"},
        headers={"X-API-Key": settings.n8n_api_key},
    )
    assert response.status_code == 200
    body = response.json()
    assert "reply" in body
    reply = body["reply"].lower()
    assert "master" in reply or "solo" in reply or "disponible" in reply


async def test_tenant_phone_returns_access_denied(client, active_tenant_user):
    """Tenant phone → 200 with access-denied reply, no CRUD action."""
    response = await client.post(
        ENDPOINT,
        json={"phone": "+20000000000", "message": "hola"},
        headers={"X-API-Key": settings.n8n_api_key},
    )
    assert response.status_code == 200
    body = response.json()
    assert "reply" in body
    reply = body["reply"].lower()
    assert "master" in reply or "solo" in reply or "disponible" in reply


async def test_master_phone_returns_state_unavailable_when_redis_missing(client, master_user):
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


async def test_real_adapter_lifecycle_methods_use_tenant_service(db_session, active_tenant_user):
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
        select(TenantProfile).where(TenantProfile.id == active_tenant_user.id)
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
    """Primary Redis active + Manager with used_backup=False → normal flow."""
    fake_mgr = _FakeManager(used_backup=False)
    with patch("app.api.v1.endpoints.integrations.get_redis_manager", return_value=fake_mgr):
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
    """
    fake_mgr = _FakeManager(used_backup=True)
    with patch("app.api.v1.endpoints.integrations.get_redis_manager", return_value=fake_mgr):
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


async def test_failover_missing_session_with_menu_choice_still_resets(client, master_user):
    """Even a menu-choice message gets reset when failover active + no session."""
    fake_mgr = _FakeManager(used_backup=True)
    with patch("app.api.v1.endpoints.integrations.get_redis_manager", return_value=fake_mgr):
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
    """
    fake_mgr = _FakeManager(used_backup=True)
    with patch("app.api.v1.endpoints.integrations.get_redis_manager", return_value=fake_mgr):
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


async def test_both_redis_unavailable_returns_temporary_unavailable(client, master_user):
    """Both Redis stores fail during operation → temporary unavailable reply."""
    fake_mgr = _FakeManager(fail_on_execute=True)
    with patch("app.api.v1.endpoints.integrations.get_redis_manager", return_value=fake_mgr):
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


async def test_both_unavailable_still_returns_200_for_relayable_reply(client, master_user):
    """HTTP 200 is preserved for temporary unavailable so n8n can relay."""
    fake_mgr = _FakeManager(fail_on_execute=True)
    with patch("app.api.v1.endpoints.integrations.get_redis_manager", return_value=fake_mgr):
        response = await client.post(
            ENDPOINT,
            json={"phone": "+12015550001", "message": "hola"},
            headers={"X-API-Key": settings.n8n_api_key},
        )
    assert response.status_code == 200  # Not 500


async def test_invalid_api_key_still_401_with_fake_manager(client, master_user):
    """Invalid API key returns 401 regardless of Redis state."""
    fake_mgr = _FakeManager(used_backup=False)
    with patch("app.api.v1.endpoints.integrations.get_redis_manager", return_value=fake_mgr):
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


async def test_redis_connection_error_returns_temporary_unavailable(client, master_user):
    """ConnectionError from Redis yields relayable unavailable reply."""
    fake_mgr = _FakeManagerRaising(ConnectionError("primary Redis connection refused"))
    with patch("app.api.v1.endpoints.integrations.get_redis_manager", return_value=fake_mgr):
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
    with patch("app.api.v1.endpoints.integrations.get_redis_manager", return_value=fake_mgr):
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
    with patch("app.api.v1.endpoints.integrations.get_redis_manager", return_value=fake_mgr):
        response = await client.post(
            ENDPOINT,
            json={"phone": "+12015550001", "message": "hola"},
            headers={"X-API-Key": settings.n8n_api_key},
        )
    assert response.status_code == 200
    assert "no disponible" in response.json()["reply"].lower()


async def test_redis_generic_exception_returns_temporary_unavailable(client, master_user):
    """Any unexpected exception from Redis yields relayable unavailable reply."""
    fake_mgr = _FakeManagerRaising(RuntimeError("unexpected infrastructure error"))
    with patch("app.api.v1.endpoints.integrations.get_redis_manager", return_value=fake_mgr):
        response = await client.post(
            ENDPOINT,
            json={"phone": "+12015550001", "message": "hola"},
            headers={"X-API-Key": settings.n8n_api_key},
        )
    assert response.status_code == 200
    assert "no disponible" in response.json()["reply"].lower()


async def test_access_denied_non_master_does_not_call_redis(client, active_tenant_user):
    """Non-master phone returns access-denied without touching Redis."""
    fake_mgr = _FakeManager(fail_on_execute=True)
    with patch("app.api.v1.endpoints.integrations.get_redis_manager", return_value=fake_mgr):
        response = await client.post(
            ENDPOINT,
            json={"phone": "+20000000000", "message": "hola"},
            headers={"X-API-Key": settings.n8n_api_key},
        )
    assert response.status_code == 200
    reply = response.json()["reply"].lower()
    # Access denied, not a Redis error
    assert "master" in reply or "solo" in reply
    assert "no disponible" not in reply
