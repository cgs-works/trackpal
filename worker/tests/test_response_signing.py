"""Executor response authentication tests."""

from uuid import UUID

import httpx
import pytest
from test_api import _runtime, _settings, _signed_request

from app.main import create_app
from app.protocol.crypto import derive_protocol_keys, verify_response_signature

EXECUTOR_ID = UUID("00000000-0000-0000-0000-000000000001")


@pytest.mark.asyncio
async def test_challenge_response_is_signed() -> None:
    settings = _settings(capacity=2)
    runtime, _ = _runtime(settings)
    app = create_app(settings, runtime)
    body, headers = _signed_request(
        "/v1/health/challenge", {"challenge": "challenge-1"}, nonce="challenge-nonce"
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://worker"
    ) as client:
        response = await client.post(
            "/v1/health/challenge", content=body, headers=headers
        )

    assert response.status_code == 200
    verify_response_signature(
        "POST",
        "/v1/health/challenge",
        EXECUTOR_ID,
        int(response.headers["X-TrackPal-Key-Version"]),
        int(response.headers["X-TrackPal-Timestamp"]),
        response.headers["X-TrackPal-Nonce"],
        response.content,
        response.headers["X-TrackPal-Signature"],
        derive_protocol_keys("executor-secret").signing,
        now=int(response.headers["X-TrackPal-Timestamp"]),
        max_skew_seconds=0,
    )
