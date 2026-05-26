"""Tests for EvolutionClient Evolution Go contracts."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.evolution_client import EvolutionClient

pytestmark = pytest.mark.asyncio


class TestCreateInstance:
    async def test_create_uses_evolution_go_payload_and_returns_token(self) -> None:
        client = EvolutionClient(base_url="https://evo.test", api_key="global-key")
        create_response = MagicMock()
        create_response.json.return_value = {"message": "success", "data": {"id": "inst-id"}}
        create_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_httpx, patch(
            "app.services.evolution_client.client.secrets.token_urlsafe",
            return_value="instance-token",
        ):
            mock_ctx = AsyncMock()
            mock_httpx.return_value.__aenter__.return_value = mock_ctx
            mock_ctx.post.return_value = create_response

            result = await client.create_instance("acme")

        mock_ctx.post.assert_called_once_with(
            "/instance/create",
            json={"name": "tenant-acme", "token": "instance-token"},
            headers={"Content-Type": "application/json", "apikey": "global-key"},
        )
        assert result == {"instance_id": "inst-id", "instance_token": "instance-token"}

    async def test_create_resolves_instance_id_from_instance_all(self) -> None:
        client = EvolutionClient(base_url="https://evo.test", api_key="global-key")
        create_response = MagicMock()
        create_response.json.return_value = {"message": "success", "data": {"name": "tenant-acme"}}
        create_response.raise_for_status = MagicMock()
        list_response = MagicMock()
        list_response.json.return_value = {
            "message": "success",
            "data": [{"id": "resolved-id", "name": "tenant-acme"}],
        }
        list_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_httpx, patch(
            "app.services.evolution_client.client.secrets.token_urlsafe",
            return_value="instance-token",
        ):
            mock_ctx = AsyncMock()
            mock_httpx.return_value.__aenter__.return_value = mock_ctx
            mock_ctx.post.return_value = create_response
            mock_ctx.get.return_value = list_response

            result = await client.create_instance("acme")

        mock_ctx.get.assert_called_once_with(
            "/instance/all",
            headers={"Content-Type": "application/json", "apikey": "global-key"},
        )
        assert result == {"instance_id": "resolved-id", "instance_token": "instance-token"}


class TestRegisterWebhook:
    async def test_register_webhook_create_payload(self) -> None:
        client = EvolutionClient(base_url="https://evo.test", api_key="global-key")
        create_response = MagicMock(status_code=200)

        with patch("httpx.AsyncClient") as mock_httpx:
            mock_ctx = AsyncMock()
            mock_httpx.return_value.__aenter__.return_value = mock_ctx
            mock_ctx.post.return_value = create_response

            await client.register_webhook("inst-id")

        _, kwargs = mock_ctx.post.call_args
        assert mock_ctx.post.call_args.args[0] == "/webhook/create/inst-id"
        assert kwargs["headers"]["apikey"] == "global-key"
        assert kwargs["json"] == {
            "enabled": True,
            "webhookUrl": "https://rs-n8n.wilfredocamacho.dev/webhook/trackpalmastertenantclient",
            "triggerType": "keyword",
            "triggerOperator": "startsWith",
            "triggerValue": "/menu",
            "isTrusted": True,
        }

    async def test_register_webhook_updates_existing_wrapped_data(self) -> None:
        client = EvolutionClient(base_url="https://evo.test", api_key="global-key")
        create_response = MagicMock(status_code=409)
        find_response = MagicMock()
        find_response.json.return_value = {
            "message": "success",
            "data": [
                {
                    "id": "webhook-id",
                    "webhookUrl": "https://rs-n8n.wilfredocamacho.dev/webhook/trackpalmastertenantclient",
                }
            ],
        }
        find_response.raise_for_status = MagicMock()
        update_response = MagicMock()
        update_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_httpx:
            mock_ctx = AsyncMock()
            mock_httpx.return_value.__aenter__.return_value = mock_ctx
            mock_ctx.post.return_value = create_response
            mock_ctx.get.return_value = find_response
            mock_ctx.put.return_value = update_response

            await client.register_webhook("inst-id")

        mock_ctx.get.assert_called_once_with(
            "/webhook/find/inst-id",
            headers={"Content-Type": "application/json", "apikey": "global-key"},
        )
        assert mock_ctx.put.call_args.args[0] == "/webhook/update/webhook-id"
        update_response.raise_for_status.assert_called_once()


class TestCloseChatSession:
    async def test_noop_logs_warning_and_returns(self) -> None:
        client = EvolutionClient(base_url="https://evo.test", api_key="test-key-123")

        with patch("httpx.AsyncClient") as mock_httpx:
            await client.close_chat_session(
                instance="inst-test", remote_jid="1234567890@s.whatsapp.net"
            )

        mock_httpx.assert_not_called()
