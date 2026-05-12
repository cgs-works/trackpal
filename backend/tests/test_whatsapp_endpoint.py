"""Tests for the n8n/backend WhatsApp Master Console contract.

Verifies API-key auth, Master/non-Master handling, and response shape.
"""

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.api.v1.endpoints.integrations import _TenantConsoleAdapter
from app.models import TenantProfile
from app.services.tenant_service import TenantService

pytestmark = pytest.mark.asyncio

ENDPOINT = "/api/v1/integrations/n8n/console"


async def test_missing_api_key_returns_401(client):
    """No X-API-Key header → 401."""
    response = await client.post(
        ENDPOINT,
        json={"phone": "+10000000000", "message": "hola"},
    )
    assert response.status_code == 401
    assert "Invalid API Key" in response.json()["detail"]


async def test_wrong_api_key_returns_401(client):
    """Wrong X-API-Key header → 401."""
    response = await client.post(
        ENDPOINT,
        json={"phone": "+10000000000", "message": "hola"},
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
        json={"phone": "+10000000000", "message": "hola"},
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
        json={"phone": "+10000000000@s.whatsapp.net", "message": "hola"},
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
        json={"phone": "+10000000000", "message": "hola"},
        headers={"X-API-Key": settings.n8n_api_key},
    )
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["reply"], str)
    # Only 'reply' in the response for n8n to forward
    assert set(body.keys()) == {"reply"}
