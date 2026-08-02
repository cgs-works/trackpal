"""Behavior tests for the standalone lookup pipeline."""

from datetime import UTC, datetime

import pytest

from app.pipeline.email_message import EmailMessage
from app.pipeline.fingerprint import compute_fingerprint
from app.pipeline.models import LookupCommand
from app.pipeline.runner import execute_lookup
from app.providers.errors import NonTransientProviderError, TransientProviderError

NOW = datetime.now(UTC)


def _command(**overrides: object) -> LookupCommand:
    values: dict[str, object] = {
        "mailbox_email": "codes@example.com",
        "app_password": "app-password",
        "service_key": "spotify",
        "target_email": "client@example.com",
        "window_minutes": 5,
    }
    values.update(overrides)
    return LookupCommand(**values)


def _email(**overrides: object) -> EmailMessage:
    values: dict[str, object] = {
        "subject": "Your Spotify login code",
        "body": "Enter this code 654321",
        "received_at": NOW,
        "message_id": "msg-1",
        "sender": "noreply@spotify.com",
        "to_recipients": ("client@example.com",),
    }
    values.update(overrides)
    return EmailMessage(**values)


class FakeProvider:
    def __init__(self, emails: list[EmailMessage]) -> None:
        self.emails = emails

    async def fetch(self, command: LookupCommand) -> list[EmailMessage]:
        assert command.app_password == "app-password"
        return self.emails


class FakeNetflix:
    async def resolve(self, url: str) -> str | None:
        return None


@pytest.mark.asyncio
async def test_execute_lookup_returns_normalized_found_outcome() -> None:
    outcome = await execute_lookup(
        _command(),
        FakeProvider([_email()]),
        FakeNetflix(),
        now=NOW,
    )

    expected_fingerprint = compute_fingerprint(
        service_key="spotify",
        message_id="msg-1",
        sender="noreply@spotify.com",
        received_at_iso=NOW.isoformat(),
        subject="Your Spotify login code",
        payload_normalized="654321",
    )
    assert outcome.kind == "found"
    assert outcome.result_type == "code"
    assert outcome.result_value == "654321"
    assert outcome.message_id == "msg-1"
    assert outcome.fingerprint == expected_fingerprint
    assert "app-password" not in outcome.model_dump_json()
    assert "Enter this code" not in outcome.model_dump_json()


@pytest.mark.asyncio
async def test_execute_lookup_filters_by_target_email_before_extraction() -> None:
    outcome = await execute_lookup(
        _command(),
        FakeProvider([_email(to_recipients=("someone-else@example.com",))]),
        FakeNetflix(),
        now=NOW,
    )

    assert outcome.kind == "not_found"


@pytest.mark.asyncio
async def test_execute_lookup_returns_not_found_without_matching_email() -> None:
    outcome = await execute_lookup(
        _command(),
        FakeProvider([]),
        FakeNetflix(),
        now=NOW,
    )

    assert outcome.kind == "not_found"
    assert outcome.result_value is None


@pytest.mark.asyncio
async def test_execute_lookup_retries_provider_failures() -> None:
    class FailingProvider:
        attempts = 0

        async def fetch(self, command: LookupCommand) -> list[EmailMessage]:
            self.attempts += 1
            raise TransientProviderError("secret should not escape")

    provider = FailingProvider()
    outcome = await execute_lookup(_command(), provider, FakeNetflix())

    assert provider.attempts == 3
    assert outcome.kind == "retryable_failure"
    assert outcome.error_code == "fetch_failed"
    assert outcome.error_detail == "Email fetch failed after retries"
    assert "secret should not escape" not in outcome.model_dump_json()


@pytest.mark.asyncio
async def test_execute_lookup_maps_non_transient_provider_failure() -> None:
    class AuthFailureProvider:
        async def fetch(self, command: LookupCommand) -> list[EmailMessage]:
            raise NonTransientProviderError(
                "password app-password is invalid", error_code="auth_failed"
            )

    outcome = await execute_lookup(_command(), AuthFailureProvider(), FakeNetflix())

    assert outcome.kind == "terminal_failure"
    assert outcome.error_code == "auth_failed"
    assert outcome.error_detail == "Authentication failed — check mailbox credentials"
    assert "app-password" not in outcome.model_dump_json()


@pytest.mark.asyncio
async def test_execute_lookup_resolves_netflix_url_before_returning_result() -> None:
    url = "https://www.netflix.com/account/travel/verify?nftoken=token"

    class Netflix:
        async def resolve(self, value: str) -> str | None:
            assert value == url
            return "839201"

    email = _email(
        subject="Your Netflix temporary access code",
        body=f"Verify: [{url}]({url})",
        sender="noreply@netflix.com",
    )
    outcome = await execute_lookup(
        _command(service_key="netflix"), FakeProvider([email]), Netflix(), now=NOW
    )

    assert outcome.kind == "found"
    assert outcome.result_type == "code"
    assert outcome.result_value == "839201"


@pytest.mark.asyncio
async def test_netflix_resolution_failure_is_not_found() -> None:
    url = "https://www.netflix.com/account/travel/verify?nftoken=token"

    class Netflix:
        async def resolve(self, value: str) -> str | None:
            return None

    outcome = await execute_lookup(
        _command(service_key="netflix"),
        FakeProvider(
            [
                _email(
                    subject="Your Netflix temporary access code", body=f"[{url}]({url})"
                )
            ]
        ),
        Netflix(),
        now=NOW,
    )

    assert outcome.kind == "not_found"
