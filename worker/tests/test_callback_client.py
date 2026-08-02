from uuid import UUID

import httpx
import pytest

from app.callback_client import CallbackClient
from app.pipeline.models import LookupOutcome
from app.protocol.crypto import decrypt_payload, derive_protocol_keys
from app.protocol.models import EncryptedBody

EXECUTOR_ID = UUID("00000000-0000-0000-0000-000000000001")
CALLBACK_URL = "https://backend.example.test/api/v1/callbacks/job-1"


@pytest.mark.asyncio
async def test_callback_client_sends_signed_encrypted_outcome() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"accepted": True})

    client = CallbackClient(
        executor_id=EXECUTOR_ID,
        executor_secret="executor-secret",
        http_client_factory=lambda: httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ),
    )

    await client.send(
        CALLBACK_URL,
        job_id=UUID("00000000-0000-0000-0000-000000000010"),
        lease_id=UUID("00000000-0000-0000-0000-000000000011"),
        outcome=LookupOutcome.not_found(),
    )

    request = requests[0]
    assert request.headers["X-TrackPal-Executor-Id"] == str(EXECUTOR_ID)
    assert request.headers["X-TrackPal-Key-Version"] == "1"
    body = EncryptedBody.model_validate_json(request.content)
    payload = decrypt_payload(body, derive_protocol_keys("executor-secret").encryption)
    assert payload["job_id"] == "00000000-0000-0000-0000-000000000010"
    assert payload["lease_id"] == "00000000-0000-0000-0000-000000000011"
    assert payload["outcome"] == {
        "kind": "not_found",
        "result_type": None,
        "result_value": None,
        "message_id": None,
        "fingerprint": None,
        "error_code": None,
        "error_detail": None,
    }


@pytest.mark.asyncio
async def test_callback_client_retries_server_errors_but_not_client_errors() -> None:
    statuses = iter([503, 200])
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(next(statuses), json={"accepted": calls == 2})

    client = CallbackClient(
        executor_id=EXECUTOR_ID,
        executor_secret="executor-secret",
        http_client_factory=lambda: httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ),
        retry_delay_seconds=0,
    )

    acknowledged = await client.send(
        CALLBACK_URL,
        job_id=UUID("00000000-0000-0000-0000-000000000010"),
        lease_id=UUID("00000000-0000-0000-0000-000000000011"),
        outcome=LookupOutcome.not_found(),
    )

    assert acknowledged is True
    assert calls == 2


@pytest.mark.asyncio
async def test_callback_client_treats_accepted_false_as_final_ack() -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"accepted": False})

    client = CallbackClient(
        executor_id=EXECUTOR_ID,
        executor_secret="executor-secret",
        http_client_factory=lambda: httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ),
        retry_delay_seconds=0,
    )

    assert (
        await client.send(
            CALLBACK_URL,
            job_id=UUID("00000000-0000-0000-0000-000000000010"),
            lease_id=UUID("00000000-0000-0000-0000-000000000011"),
            outcome=LookupOutcome.not_found(),
        )
        is True
    )
    assert calls == 1
