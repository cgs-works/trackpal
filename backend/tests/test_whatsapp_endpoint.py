"""Tests for the n8n/backend WhatsApp Master Console contract.

Verifies API-key auth, Master/non-Master handling, and response shape.
"""

import pytest

from app.core.config import settings

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


async def test_master_phone_returns_reply(client, master_user):
    """Master phone → 200 with a valid reply from the console service."""
    response = await client.post(
        ENDPOINT,
        json={"phone": "+10000000000", "message": "hola"},
        headers={"X-API-Key": settings.n8n_api_key},
    )
    assert response.status_code == 200
    body = response.json()
    assert "reply" in body
    assert len(body["reply"]) > 0


async def test_master_reply_includes_menu_content(client, master_user):
    """Master reply contains expected main-menu keywords."""
    response = await client.post(
        ENDPOINT,
        json={"phone": "+10000000000", "message": "hola"},
        headers={"X-API-Key": settings.n8n_api_key},
    )
    assert response.status_code == 200
    reply = response.json()["reply"]
    # The main menu should mention at least one of these categories
    keywords = ["tenant", "crear", "ayuda", "menú", "cancelar"]
    assert any(kw in reply.lower() for kw in keywords), (
        f"Reply missing expected menu keywords: {reply}"
    )


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
