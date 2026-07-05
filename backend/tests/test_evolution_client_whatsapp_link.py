"""Tests for EvolutionClient WhatsApp instance lifecycle methods.

These tests cover instance-token auth (never global API key),
route contracts, response normalization, and error mapping.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services.evolution_client import EvolutionClient, EvolutionClientError


class TestGetInstanceStatus:
    """GET /instance/status with instance-token auth."""
    pytestmark = pytest.mark.asyncio

    async def test_uses_instance_token_auth_not_global_key(self) -> None:
        """Assert the request uses instance-token apikey, never the global key."""
        client = EvolutionClient(base_url="https://evo.test", api_key="global-key")
        response = MagicMock()
        response.json.return_value = {
            "data": {"connected": True, "loggedIn": True},
        }
        response.status_code = 200
        response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_httpx:
            mock_ctx = AsyncMock()
            mock_httpx.return_value.__aenter__.return_value = mock_ctx
            mock_ctx.request.return_value = response

            result = await client.get_instance_status(
                instance_name="acme",
                instance_token="inst-token-123",
            )

        call_args, call_kwargs = mock_ctx.request.call_args
        assert call_kwargs["headers"]["apikey"] == "inst-token-123"
        assert call_kwargs["headers"]["apikey"] != client.api_key
        assert call_args[1] == "/instance/status"
        assert call_args[0] == "GET"
        assert result == {"connected": True, "loggedIn": True}

    async def test_returns_normalized_data(self) -> None:
        """Assert _response_data unwraps the Evolution data envelope."""
        client = EvolutionClient(base_url="https://evo.test", api_key="global-key")
        response = MagicMock()
        response.json.return_value = {
            "message": "success",
            "data": {"connected": False, "loggedIn": False, "phone": "already-set"},
        }
        response.status_code = 200
        response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_httpx:
            mock_ctx = AsyncMock()
            mock_httpx.return_value.__aenter__.return_value = mock_ctx
            mock_ctx.request.return_value = response

            result = await client.get_instance_status(
                instance_name="acme", instance_token="tok"
            )

        assert result == {"connected": False, "loggedIn": False, "phone": "already-set"}

    @pytest.mark.parametrize("status_code", [401, 403])
    async def test_401_403_maps_to_invalid_instance_token(self, status_code: int) -> None:
        client = EvolutionClient(base_url="https://evo.test", api_key="global-key")
        response = MagicMock()
        response.status_code = status_code
        response.content = b""

        with patch("httpx.AsyncClient") as mock_httpx:
            mock_ctx = AsyncMock()
            mock_httpx.return_value.__aenter__.return_value = mock_ctx
            mock_ctx.request.return_value = response

            with pytest.raises(EvolutionClientError) as exc_info:
                await client.get_instance_status(instance_name="acme", instance_token="bad")
            assert exc_info.value.code == "invalid_instance_token"

    @pytest.mark.parametrize("status_code", [500, 502, 503])
    async def test_5xx_maps_to_service_unavailable(self, status_code: int) -> None:
        client = EvolutionClient(base_url="https://evo.test", api_key="global-key")
        response = MagicMock()
        response.status_code = status_code
        response.content = b""

        with patch("httpx.AsyncClient") as mock_httpx:
            mock_ctx = AsyncMock()
            mock_httpx.return_value.__aenter__.return_value = mock_ctx
            mock_ctx.request.return_value = response

            with pytest.raises(EvolutionClientError) as exc_info:
                await client.get_instance_status(instance_name="acme", instance_token="tok")
            assert exc_info.value.code == "service_unavailable"

    async def test_network_error_maps_to_service_unavailable(self) -> None:
        client = EvolutionClient(base_url="https://evo.test", api_key="global-key")
        with patch("httpx.AsyncClient") as mock_httpx:
            mock_ctx = AsyncMock()
            mock_httpx.return_value.__aenter__.return_value = mock_ctx
            mock_ctx.request.side_effect = httpx.RequestError("Connection refused")

            with pytest.raises(EvolutionClientError) as exc_info:
                await client.get_instance_status(instance_name="acme", instance_token="tok")
            assert exc_info.value.code == "service_unavailable"

    async def test_missing_base_url_raises_service_unavailable(self) -> None:
        client = EvolutionClient(base_url="", api_key="")
        with pytest.raises(EvolutionClientError) as exc_info:
            await client.get_instance_status(instance_name="acme", instance_token="tok")
        assert exc_info.value.code == "service_unavailable"

    async def test_empty_evolution_response_returns_empty_dict(self) -> None:
        """TRIANGULATE: Empty response from Evolution returns {} after unwrap."""
        client = EvolutionClient(base_url="https://evo.test", api_key="global-key")
        response = MagicMock()
        response.json.return_value = {}
        response.status_code = 200
        response.raise_for_status = MagicMock()
        response.content = b"{}"

        with patch("httpx.AsyncClient") as mock_httpx:
            mock_ctx = AsyncMock()
            mock_httpx.return_value.__aenter__.return_value = mock_ctx
            mock_ctx.request.return_value = response

            result = await client.get_instance_status(instance_name="acme", instance_token="tok")
        assert result == {}  # _response_data returns {} as-is (no "data" key)


class TestGetQrCode:
    """GET /instance/qr with instance-token auth and response normalization."""
    pytestmark = pytest.mark.asyncio

    async def test_uses_instance_token_auth(self) -> None:
        """Assert request uses instance-token and hits the correct route."""
        client = EvolutionClient(base_url="https://evo.test", api_key="global-key")
        response = MagicMock()
        response.json.return_value = {"data": {"qrcode": "base64pixeldata=="}}
        response.status_code = 200
        response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_httpx:
            mock_ctx = AsyncMock()
            mock_httpx.return_value.__aenter__.return_value = mock_ctx
            mock_ctx.request.return_value = response

            result = await client.get_qr_code(
                instance_name="acme", instance_token="inst-token-456"
            )

        call_args, call_kwargs = mock_ctx.request.call_args
        assert call_kwargs["headers"]["apikey"] == "inst-token-456"
        assert call_kwargs["headers"]["apikey"] != client.api_key
        assert call_args[1] == "/instance/qr"
        assert call_args[0] == "GET"
        assert result == {"qrcode": "base64pixeldata=="}

    async def test_normalizes_qr_field(self) -> None:
        """Assert 'qrcode' is normalized from 'qr' or 'base64' fields."""
        client = EvolutionClient(base_url="https://evo.test", api_key="global-key")

        for raw_field, value in [("qr", "qr-data"), ("base64", "b64-data")]:
            response = MagicMock()
            response.json.return_value = {"data": {raw_field: value}}
            response.status_code = 200
            response.raise_for_status = MagicMock()

            with patch("httpx.AsyncClient") as mock_httpx:
                mock_ctx = AsyncMock()
                mock_httpx.return_value.__aenter__.return_value = mock_ctx
                mock_ctx.request.return_value = response

                result = await client.get_qr_code(
                    instance_name="acme", instance_token="tok"
                )
            assert result == {"qrcode": value}, f"Failed to normalize {raw_field}"

    async def test_preserves_qrcode_field(self) -> None:
        """Assert when Evolution returns 'qrcode' directly, it's preserved."""
        client = EvolutionClient(base_url="https://evo.test", api_key="global-key")
        response = MagicMock()
        response.json.return_value = {"data": {"qrcode": "img-base64-data"}}
        response.status_code = 200
        response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_httpx:
            mock_ctx = AsyncMock()
            mock_httpx.return_value.__aenter__.return_value = mock_ctx
            mock_ctx.request.return_value = response

            result = await client.get_qr_code(
                instance_name="acme", instance_token="tok"
            )
        assert result == {"qrcode": "img-base64-data"}

    async def test_empty_response_returns_fallback_qrcode(self) -> None:
        """TRIANGULATE: When Evolution returns an empty dict, returns fallback."""
        client = EvolutionClient(base_url="https://evo.test", api_key="global-key")
        response = MagicMock()
        response.json.return_value = {"data": {}}
        response.status_code = 200
        response.raise_for_status = MagicMock()
        response.content = b'{"data": {}}'

        with patch("httpx.AsyncClient") as mock_httpx:
            mock_ctx = AsyncMock()
            mock_httpx.return_value.__aenter__.return_value = mock_ctx
            mock_ctx.request.return_value = response

            result = await client.get_qr_code(
                instance_name="acme", instance_token="tok"
            )
        assert result == {"qrcode": ""}

    async def test_response_without_data_envelope(self) -> None:
        """TRIANGULATE: Evolution returns data without {data: ...} wrapper."""
        client = EvolutionClient(base_url="https://evo.test", api_key="global-key")
        response = MagicMock()
        response.json.return_value = {"qrcode": "direct-qr"}
        response.status_code = 200
        response.raise_for_status = MagicMock()
        response.content = b'{"qrcode": "direct-qr"}'

        with patch("httpx.AsyncClient") as mock_httpx:
            mock_ctx = AsyncMock()
            mock_httpx.return_value.__aenter__.return_value = mock_ctx
            mock_ctx.request.return_value = response

            result = await client.get_qr_code(
                instance_name="acme", instance_token="tok"
            )
        assert result == {"qrcode": "direct-qr"}

    @pytest.mark.parametrize(
        ("status_code", "expected_code"),
        [(401, "invalid_instance_token"), (403, "invalid_instance_token"),
         (500, "service_unavailable"), (503, "service_unavailable")],
    )
    async def test_error_mapping(self, status_code: int, expected_code: str) -> None:
        client = EvolutionClient(base_url="https://evo.test", api_key="global-key")
        response = MagicMock()
        response.status_code = status_code
        response.content = b""

        with patch("httpx.AsyncClient") as mock_httpx:
            mock_ctx = AsyncMock()
            mock_httpx.return_value.__aenter__.return_value = mock_ctx
            mock_ctx.request.return_value = response

            with pytest.raises(EvolutionClientError) as exc_info:
                await client.get_qr_code(instance_name="acme", instance_token="tok")
            assert exc_info.value.code == expected_code


class TestPairInstance:
    """POST /instance/pair with instance-token auth, phone payload, and response normalization."""
    pytestmark = pytest.mark.asyncio

    async def test_uses_instance_token_auth_and_sends_phone(self) -> None:
        client = EvolutionClient(base_url="https://evo.test", api_key="global-key")
        response = MagicMock()
        response.json.return_value = {"data": {"code": "12345678"}}
        response.status_code = 200
        response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_httpx:
            mock_ctx = AsyncMock()
            mock_httpx.return_value.__aenter__.return_value = mock_ctx
            mock_ctx.request.return_value = response

            result = await client.pair_instance(
                instance_name="acme",
                instance_token="inst-token-789",
                phone="+12015550002",
            )

        call_args, call_kwargs = mock_ctx.request.call_args
        assert call_kwargs["headers"]["apikey"] == "inst-token-789"
        assert call_kwargs["headers"]["apikey"] != client.api_key
        assert call_args[1] == "/instance/pair"
        assert call_args[0] == "POST"
        assert call_kwargs["json"] == {"phone": "+12015550002"}
        assert result == {"code": "12345678"}

    async def test_normalizes_pairing_code_field(self) -> None:
        """Assert 'code' is normalized from 'pairingCode' field."""
        client = EvolutionClient(base_url="https://evo.test", api_key="global-key")
        response = MagicMock()
        response.json.return_value = {"data": {"pairingCode": "87654321"}}
        response.status_code = 200
        response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_httpx:
            mock_ctx = AsyncMock()
            mock_httpx.return_value.__aenter__.return_value = mock_ctx
            mock_ctx.request.return_value = response

            result = await client.pair_instance(
                instance_name="acme", instance_token="tok", phone="+12015550002"
            )
        assert result == {"code": "87654321"}

    async def test_preserves_code_field(self) -> None:
        """Assert when Evolution returns 'code' directly, it's preserved."""
        client = EvolutionClient(base_url="https://evo.test", api_key="global-key")
        response = MagicMock()
        response.json.return_value = {"data": {"code": "11112222"}}
        response.status_code = 200
        response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_httpx:
            mock_ctx = AsyncMock()
            mock_httpx.return_value.__aenter__.return_value = mock_ctx
            mock_ctx.request.return_value = response

            result = await client.pair_instance(
                instance_name="acme", instance_token="tok", phone="+12015550002"
            )
        assert result == {"code": "11112222"}

    async def test_empty_response_returns_fallback_code(self) -> None:
        """TRIANGULATE: When Evolution returns empty dict, returns fallback."""
        client = EvolutionClient(base_url="https://evo.test", api_key="global-key")
        response = MagicMock()
        response.json.return_value = {"data": {}}
        response.status_code = 200
        response.raise_for_status = MagicMock()
        response.content = b'{"data": {}}'

        with patch("httpx.AsyncClient") as mock_httpx:
            mock_ctx = AsyncMock()
            mock_httpx.return_value.__aenter__.return_value = mock_ctx
            mock_ctx.request.return_value = response

            result = await client.pair_instance(
                instance_name="acme", instance_token="tok", phone="+12015550002"
            )
        assert result == {"code": ""}

    async def test_no_content_response_returns_fallback_code(self) -> None:
        """TRIANGULATE: Empty body response returns fallback code."""
        client = EvolutionClient(base_url="https://evo.test", api_key="global-key")
        response = MagicMock()
        response.status_code = 200
        response.content = b""

        with patch("httpx.AsyncClient") as mock_httpx:
            mock_ctx = AsyncMock()
            mock_httpx.return_value.__aenter__.return_value = mock_ctx
            mock_ctx.request.return_value = response

            result = await client.pair_instance(
                instance_name="acme", instance_token="tok", phone="+12015550002"
            )
        assert result == {"code": ""}

    @pytest.mark.parametrize(
        ("status_code", "expected_code"),
        [(401, "invalid_instance_token"), (403, "invalid_instance_token"),
         (500, "service_unavailable")],
    )
    async def test_error_mapping(self, status_code: int, expected_code: str) -> None:
        client = EvolutionClient(base_url="https://evo.test", api_key="global-key")
        response = MagicMock()
        response.status_code = status_code
        response.content = b""

        with patch("httpx.AsyncClient") as mock_httpx:
            mock_ctx = AsyncMock()
            mock_httpx.return_value.__aenter__.return_value = mock_ctx
            mock_ctx.request.return_value = response

            with pytest.raises(EvolutionClientError) as exc_info:
                await client.pair_instance(
                    instance_name="acme", instance_token="tok", phone="+12015550002"
                )
            assert exc_info.value.code == expected_code


class TestLogoutInstance:
    """POST /instance/logout with instance-token auth."""
    pytestmark = pytest.mark.asyncio

    async def test_uses_instance_token_auth(self) -> None:
        client = EvolutionClient(base_url="https://evo.test", api_key="global-key")
        response = MagicMock()
        response.status_code = 200
        response.content = b""
        response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_httpx:
            mock_ctx = AsyncMock()
            mock_httpx.return_value.__aenter__.return_value = mock_ctx
            mock_ctx.request.return_value = response

            result = await client.logout_instance(
                instance_name="acme",
                instance_token="inst-token-logout",
            )

        call_args, call_kwargs = mock_ctx.request.call_args
        assert call_kwargs["headers"]["apikey"] == "inst-token-logout"
        assert call_kwargs["headers"]["apikey"] != client.api_key
        assert call_args[1] == "/instance/logout"
        assert call_args[0] == "POST"
        assert result is None

    async def test_returns_none_when_no_content(self) -> None:
        """Assert logout returns None when Evolution returns empty body."""
        client = EvolutionClient(base_url="https://evo.test", api_key="global-key")
        response = MagicMock()
        response.status_code = 200
        response.content = b""

        with patch("httpx.AsyncClient") as mock_httpx:
            mock_ctx = AsyncMock()
            mock_httpx.return_value.__aenter__.return_value = mock_ctx
            mock_ctx.request.return_value = response

            result = await client.logout_instance(
                instance_name="acme", instance_token="tok"
            )
        assert result is None

    @pytest.mark.parametrize(
        ("status_code", "expected_code"),
        [(401, "invalid_instance_token"), (403, "invalid_instance_token"),
         (500, "service_unavailable")],
    )
    async def test_error_mapping(self, status_code: int, expected_code: str) -> None:
        client = EvolutionClient(base_url="https://evo.test", api_key="global-key")
        response = MagicMock()
        response.status_code = status_code
        response.content = b""

        with patch("httpx.AsyncClient") as mock_httpx:
            mock_ctx = AsyncMock()
            mock_httpx.return_value.__aenter__.return_value = mock_ctx
            mock_ctx.request.return_value = response

            with pytest.raises(EvolutionClientError) as exc_info:
                await client.logout_instance(
                    instance_name="acme", instance_token="tok"
                )
            assert exc_info.value.code == expected_code

    async def test_logout_with_content_still_returns_none(self) -> None:
        """TRIANGULATE: Even if Evolution returns a body, logout returns None."""
        client = EvolutionClient(base_url="https://evo.test", api_key="global-key")
        response = MagicMock()
        response.json.return_value = {"data": {"result": "logged out"}}
        response.status_code = 200
        response.raise_for_status = MagicMock()
        response.content = b'{"data": {"result": "logged out"}}'

        with patch("httpx.AsyncClient") as mock_httpx:
            mock_ctx = AsyncMock()
            mock_httpx.return_value.__aenter__.return_value = mock_ctx
            mock_ctx.request.return_value = response

            result = await client.logout_instance(
                instance_name="acme", instance_token="tok"
            )
        assert result is None


class TestEvolutionClientError:
    """EvolutionClientError exception contract."""

    def test_has_code_and_optional_status_code(self) -> None:
        err = EvolutionClientError("invalid_instance_token")
        assert err.code == "invalid_instance_token"
        assert err.status_code is None

    def test_with_status_code(self) -> None:
        err = EvolutionClientError("service_unavailable", status_code=503)
        assert err.code == "service_unavailable"
        assert err.status_code == 503

    def test_is_runtime_error_subclass(self) -> None:
        assert issubclass(EvolutionClientError, RuntimeError)
