"""Behavior tests for resuming suspended n8n lookup executions."""

from __future__ import annotations

import json

import httpx
import pytest

from app.services.lookup_resume_notifier import HttpLookupResumeNotifier


@pytest.mark.asyncio
async def test_notifier_retries_until_n8n_wait_is_ready() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        status = 404 if len(requests) == 1 else 202
        return httpx.Response(status, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        notifier = HttpLookupResumeNotifier(
            auth_token="resume-secret",
            client=client,
            retry_delays=(0.0, 0.0),
        )
        delivered = await notifier.notify(
            "https://n8n.example.com/waiting-webhook/secret",
            {"job_id": "job-1", "status": "completed", "result_type": "code"},
        )

    assert delivered is True
    assert len(requests) == 2
    assert requests[0].headers["X-API-Key"] == "resume-secret"
    assert json.loads(requests[1].content) == {
        "job_id": "job-1",
        "status": "completed",
        "result_type": "code",
    }


@pytest.mark.asyncio
async def test_default_retries_cover_wait_webhook_activation_race(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        status = 404 if len(requests) < 6 else 202
        return httpx.Response(status, request=request)

    async def no_sleep(_: float) -> None:
        return None

    monkeypatch.setattr("app.services.lookup_resume_notifier.asyncio.sleep", no_sleep)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        notifier = HttpLookupResumeNotifier(
            auth_token="resume-secret",
            client=client,
        )
        delivered = await notifier.notify(
            "https://n8n.example.com/waiting-webhook/secret",
            {"job_id": "job-1", "status": "completed", "result_type": "code"},
        )

    assert delivered is True
    assert len(requests) == 6


@pytest.mark.asyncio
async def test_notifier_returns_false_after_bounded_failures() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(503, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        notifier = HttpLookupResumeNotifier(
            auth_token="resume-secret",
            client=client,
            retry_delays=(0.0, 0.0),
        )
        delivered = await notifier.notify(
            "https://n8n.example.com/waiting-webhook/secret",
            {"job_id": "job-1", "status": "failed"},
        )

    assert delivered is False
    assert attempts == 3
