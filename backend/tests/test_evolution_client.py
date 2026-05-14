"""Tests for EvolutionClient.close_chat_session()."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.evolution_client import EvolutionClient


# ---------------------------------------------------------------------------
# Tests for close_chat_session
# ---------------------------------------------------------------------------

pytestmark = pytest.mark.asyncio


class TestCloseChatSession:
    """Cover request shape, missing config guard, non-2xx handling."""

    async def test_sends_post_to_correct_path(self) -> None:
        """close_chat_session sends POST to /n8n/changeStatus/{instance}."""
        from unittest.mock import MagicMock

        client = EvolutionClient(base_url="https://evo.test", api_key="test-key-123")

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_httpx:
            mock_ctx = AsyncMock()
            mock_httpx.return_value.__aenter__.return_value = mock_ctx
            mock_ctx.post.return_value = mock_response

            await client.close_chat_session(
                instance="inst-test", remote_jid="1234567890@s.whatsapp.net"
            )

            mock_ctx.post.assert_called_once()
            call_args = mock_ctx.post.call_args
            url = call_args[0][0] if call_args[0] else call_args[1].get("url", "")
            assert "/n8n/changeStatus/inst-test" in str(url)

    async def test_payload_includes_remote_jid_and_status_closed(self) -> None:
        """Payload contains remoteJid and status=closed."""
        from unittest.mock import MagicMock

        client = EvolutionClient(base_url="https://evo.test", api_key="test-key-123")

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_httpx:
            mock_ctx = AsyncMock()
            mock_httpx.return_value.__aenter__.return_value = mock_ctx
            mock_ctx.post.return_value = mock_response

            await client.close_chat_session(
                instance="inst-test", remote_jid="9998887777@s.whatsapp.net"
            )

            mock_ctx.post.assert_called_once()
            _, kwargs = mock_ctx.post.call_args
            payload = kwargs.get("json", {})
            assert payload.get("remoteJid") == "9998887777@s.whatsapp.net"
            assert payload.get("status") == "closed"

    async def test_noop_when_api_key_empty(self) -> None:
        """When api_key is empty, method returns without calling httpx."""
        client = EvolutionClient(base_url="https://evo.test", api_key="")

        with patch("httpx.AsyncClient") as mock_httpx:
            await client.close_chat_session(
                instance="inst-test", remote_jid="1234@s.whatsapp.net"
            )

            mock_httpx.assert_not_called()

    async def test_noop_when_base_url_empty(self) -> None:
        """When base_url is empty, method returns without calling httpx."""
        client = EvolutionClient(base_url="", api_key="test-key")

        with patch("httpx.AsyncClient") as mock_httpx:
            await client.close_chat_session(
                instance="inst-test", remote_jid="1234@s.whatsapp.net"
            )

            mock_httpx.assert_not_called()

    async def test_raises_on_non_2xx(self) -> None:
        """Non-2xx response raises HTTPStatusError."""
        from unittest.mock import MagicMock
        import httpx

        client = EvolutionClient(base_url="https://evo.test", api_key="test-key")

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = (
            httpx.HTTPStatusError(
                "Not Found",
                request=httpx.Request("POST", "http://test/"),
                response=httpx.Response(404),
            )
        )

        with patch("httpx.AsyncClient") as mock_httpx:
            mock_ctx = AsyncMock()
            mock_httpx.return_value.__aenter__.return_value = mock_ctx
            mock_ctx.post.return_value = mock_response

            with pytest.raises(httpx.HTTPStatusError):
                await client.close_chat_session(
                    instance="inst-nonexistent", remote_jid="1234@s.whatsapp.net"
                )

    async def test_passes_headers(self) -> None:
        """Request includes Content-Type and apikey headers."""
        from unittest.mock import MagicMock

        client = EvolutionClient(base_url="https://evo.test", api_key="secret-api-key")

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_httpx:
            mock_ctx = AsyncMock()
            mock_httpx.return_value.__aenter__.return_value = mock_ctx
            mock_ctx.post.return_value = mock_response

            await client.close_chat_session(
                instance="inst-test", remote_jid="1234@s.whatsapp.net"
            )

            mock_ctx.post.assert_called_once()
            _, kwargs = mock_ctx.post.call_args
            headers = kwargs.get("headers", {})
            assert headers.get("apikey") == "secret-api-key"
            assert headers.get("Content-Type") == "application/json"
