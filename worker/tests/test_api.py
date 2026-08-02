import asyncio
import time
from uuid import UUID

import httpx
import pytest

from app.config import ExecutorSettings
from app.main import create_app
from app.pipeline.models import LookupCommand, LookupOutcome
from app.protocol.crypto import derive_protocol_keys, encrypt_payload, sign_request
from app.runtime import ExecutorRuntime

EXECUTOR_ID = UUID("00000000-0000-0000-0000-000000000001")
JOB_ID = UUID("00000000-0000-0000-0000-000000000010")
LEASE_ID = UUID("00000000-0000-0000-0000-000000000011")
SECRET = "executor-secret"


def _settings(capacity: int = 1) -> ExecutorSettings:
    return ExecutorSettings(
        executor_id=EXECUTOR_ID,
        executor_secret=SECRET,
        max_concurrency=capacity,
    )


def _signed_request(
    path: str,
    payload: dict[str, object],
    *,
    nonce: str,
    signature_secret: str = SECRET,
) -> tuple[bytes, dict[str, str]]:
    timestamp = int(time.time())
    keys = derive_protocol_keys(signature_secret)
    body = encrypt_payload(payload, keys.encryption)
    body_bytes = body.model_dump_json().encode()
    headers = {
        "X-TrackPal-Executor-Id": str(EXECUTOR_ID),
        "X-TrackPal-Key-Version": "1",
        "X-TrackPal-Timestamp": str(timestamp),
        "X-TrackPal-Nonce": nonce,
        "X-TrackPal-Signature": sign_request(
            "POST",
            path,
            EXECUTOR_ID,
            1,
            timestamp,
            nonce,
            body_bytes,
            keys.signing,
        ),
        "Content-Type": "application/json",
    }
    return body_bytes, headers


def _command_payload(
    *,
    job_id: UUID = JOB_ID,
    lease_id: UUID = LEASE_ID,
) -> dict[str, object]:
    return {
        "mailbox_email": "codes@example.com",
        "app_password": "app-password",
        "service_key": "spotify",
        "target_email": "client@example.com",
        "job_id": str(job_id),
        "lease_id": str(lease_id),
        "callback_url": "https://backend.example.test/callback",
    }


@pytest.mark.asyncio
async def test_health_challenge_echoes_challenge_and_runtime_capabilities() -> None:
    settings = _settings(capacity=2)
    runtime = ExecutorRuntime(settings, pipeline=_pipeline)
    app = create_app(settings, runtime)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://worker"
    ) as client:
        body, headers = _signed_request(
            "/v1/health/challenge",
            {"challenge": "challenge-1"},
            nonce="challenge-nonce",
        )
        response = await client.post(
            "/v1/health/challenge", content=body, headers=headers
        )

    assert response.status_code == 200
    assert response.json() == {
        "challenge": "challenge-1",
        "protocol_version": 1,
        "runtime_version": "0.1.0",
        "max_concurrency": 2,
    }


@pytest.mark.asyncio
async def test_execute_rejects_invalid_signature_before_decryption() -> None:
    settings = _settings()
    runtime = ExecutorRuntime(settings, pipeline=_pipeline)
    app = create_app(settings, runtime)
    body, headers = _signed_request(
        "/v1/jobs/execute",
        _command_payload(),
        nonce="invalid-signature-nonce",
        signature_secret="wrong-secret",
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://worker"
    ) as client:
        response = await client.post("/v1/jobs/execute", content=body, headers=headers)

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_execute_accepts_command_and_returns_lease() -> None:
    settings = _settings()
    runtime = ExecutorRuntime(settings, pipeline=_pipeline)
    app = create_app(settings, runtime)
    body, headers = _signed_request(
        "/v1/jobs/execute", _command_payload(), nonce="accepted-nonce"
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://worker"
    ) as client:
        response = await client.post("/v1/jobs/execute", content=body, headers=headers)

    assert response.status_code == 202
    assert response.json() == {"accepted": True, "lease_id": str(LEASE_ID)}


@pytest.mark.asyncio
async def test_execute_returns_conflict_for_duplicate_leases_and_busy_for_capacity() -> (
    None
):
    started = asyncio.Event()
    release = asyncio.Event()

    async def pipeline(command: LookupCommand) -> LookupOutcome:
        started.set()
        await release.wait()
        return LookupOutcome.not_found()

    settings = _settings()
    runtime = ExecutorRuntime(settings, pipeline=pipeline)
    app = create_app(settings, runtime)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://worker"
    ) as client:
        first_body, first_headers = _signed_request(
            "/v1/jobs/execute", _command_payload(), nonce="first-nonce"
        )
        first_task = asyncio.create_task(
            client.post("/v1/jobs/execute", content=first_body, headers=first_headers)
        )
        await started.wait()

        same_body, same_headers = _signed_request(
            "/v1/jobs/execute", _command_payload(), nonce="same-nonce"
        )
        same = await client.post(
            "/v1/jobs/execute", content=same_body, headers=same_headers
        )

        different_body, different_headers = _signed_request(
            "/v1/jobs/execute",
            _command_payload(lease_id=UUID("00000000-0000-0000-0000-000000000012")),
            nonce="different-nonce",
        )
        different = await client.post(
            "/v1/jobs/execute", content=different_body, headers=different_headers
        )

        busy_body, busy_headers = _signed_request(
            "/v1/jobs/execute",
            _command_payload(job_id=UUID("00000000-0000-0000-0000-000000000013")),
            nonce="busy-nonce",
        )
        busy = await client.post(
            "/v1/jobs/execute", content=busy_body, headers=busy_headers
        )
        release.set()
        first = await first_task

    assert first.status_code == 202
    assert same.status_code == 409
    assert different.status_code == 409
    assert busy.status_code == 429


async def _pipeline(command: LookupCommand) -> LookupOutcome:
    return LookupOutcome.not_found()
