"""Behavior tests for the standalone lookup pipeline."""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from app.pipeline import runner as runner_module
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
        "timeout_seconds": 5,
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
    async def resolve(
        self, url: str, *, upload_diagnostics: bool = False
    ) -> str | None:
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
async def test_execute_lookup_uses_fixed_search_after_after_worker_delay() -> None:
    requested_at = NOW
    email = _email(received_at=requested_at - timedelta(minutes=10))

    outcome = await execute_lookup(
        _command(search_after=requested_at - timedelta(minutes=15)),
        FakeProvider([email]),
        FakeNetflix(),
        now=requested_at + timedelta(minutes=10),
    )

    assert outcome.kind == "found"
    assert outcome.result_value == "654321"


@pytest.mark.asyncio
async def test_execute_lookup_caps_budget_after_sixty_second_cold_start(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Clock:
        elapsed = 0.0

        def monotonic(self) -> float:
            return self.elapsed

        async def sleep(self, seconds: float) -> None:
            self.elapsed += seconds

    clock = Clock()
    monkeypatch.setattr(runner_module, "monotonic", clock.monotonic)
    monkeypatch.setattr(runner_module.asyncio, "sleep", clock.sleep)

    outcome = await execute_lookup(
        _command(
            timeout_seconds=120,
            deadline_at=NOW + timedelta(seconds=120),
        ),
        FakeProvider([]),
        FakeNetflix(),
        now=NOW + timedelta(seconds=60),
    )

    assert outcome.kind == "not_found"
    assert clock.elapsed == 60


@pytest.mark.asyncio
async def test_execute_lookup_filters_by_target_email_before_extraction() -> None:
    outcome = await execute_lookup(
        _command(timeout_seconds=1),
        FakeProvider([_email(to_recipients=("someone-else@example.com",))]),
        FakeNetflix(),
        now=NOW,
    )

    assert outcome.kind == "not_found"


@pytest.mark.asyncio
async def test_execute_lookup_waits_for_code_that_arrives_during_timeout() -> None:
    class DelayedProvider:
        attempts = 0

        async def fetch(self, command: LookupCommand) -> list[EmailMessage]:
            self.attempts += 1
            return [] if self.attempts == 1 else [_email()]

    class Clock:
        elapsed = 0.0

        def monotonic(self) -> float:
            return self.elapsed

        async def sleep(self, seconds: float) -> None:
            self.elapsed += seconds

    clock = Clock()
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(runner_module, "monotonic", clock.monotonic, raising=False)
    monkeypatch.setattr(runner_module.asyncio, "sleep", clock.sleep)
    try:
        provider = DelayedProvider()
        outcome = await execute_lookup(
            _command(timeout_seconds=8), provider, FakeNetflix(), now=NOW
        )
    finally:
        monkeypatch.undo()

    assert provider.attempts == 2
    assert outcome.kind == "found"
    assert outcome.result_value == "654321"


@pytest.mark.asyncio
async def test_execute_lookup_skips_delivered_code_and_waits_for_new_one() -> None:
    old_email = _email()
    new_email = _email(
        body="Enter this code 777888",
        message_id="msg-2",
        received_at=NOW + timedelta(seconds=1),
    )
    old_fingerprint = compute_fingerprint(
        service_key="spotify",
        message_id=old_email.message_id,
        sender=old_email.sender,
        received_at_iso=old_email.received_at.isoformat(),
        subject=old_email.subject,
        payload_normalized="654321",
    )

    class DelayedProvider:
        attempts = 0

        async def fetch(self, command: LookupCommand) -> list[EmailMessage]:
            self.attempts += 1
            return [old_email] if self.attempts == 1 else [old_email, new_email]

    class Clock:
        elapsed = 0.0

        def monotonic(self) -> float:
            return self.elapsed

        async def sleep(self, seconds: float) -> None:
            self.elapsed += seconds

    clock = Clock()
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(runner_module, "monotonic", clock.monotonic)
    monkeypatch.setattr(runner_module.asyncio, "sleep", clock.sleep)
    try:
        provider = DelayedProvider()
        outcome = await execute_lookup(
            _command(
                timeout_seconds=8,
                excluded_deliveries=[
                    {"message_id": old_email.message_id, "fingerprint": old_fingerprint}
                ],
            ),
            provider,
            FakeNetflix(),
            now=NOW,
        )
    finally:
        monkeypatch.undo()

    assert provider.attempts == 2
    assert clock.elapsed == 4
    assert outcome.kind == "found"
    assert outcome.result_value == "777888"
    assert outcome.message_id == "msg-2"


@pytest.mark.asyncio
async def test_execute_lookup_returns_not_found_after_only_delivered_codes() -> None:
    old_email = _email()
    old_fingerprint = compute_fingerprint(
        service_key="spotify",
        message_id=old_email.message_id,
        sender=old_email.sender,
        received_at_iso=old_email.received_at.isoformat(),
        subject=old_email.subject,
        payload_normalized="654321",
    )

    class Clock:
        elapsed = 0.0

        def monotonic(self) -> float:
            return self.elapsed

        async def sleep(self, seconds: float) -> None:
            self.elapsed += seconds

    clock = Clock()
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(runner_module, "monotonic", clock.monotonic)
    monkeypatch.setattr(runner_module.asyncio, "sleep", clock.sleep)
    try:
        provider = FakeProvider([old_email])
        outcome = await execute_lookup(
            _command(
                timeout_seconds=8,
                excluded_deliveries=[
                    {"message_id": old_email.message_id, "fingerprint": old_fingerprint}
                ],
            ),
            provider,
            FakeNetflix(),
            now=NOW,
        )
    finally:
        monkeypatch.undo()

    assert clock.elapsed == 8
    assert outcome.kind == "not_found"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("same_message_id", "same_fingerprint"),
    [(True, False), (False, True)],
)
async def test_execute_lookup_excludes_only_exact_delivery_pair(
    same_message_id: bool,
    same_fingerprint: bool,
) -> None:
    email = _email()
    fingerprint = compute_fingerprint(
        service_key="spotify",
        message_id=email.message_id,
        sender=email.sender,
        received_at_iso=email.received_at.isoformat(),
        subject=email.subject,
        payload_normalized="654321",
    )
    excluded_delivery = {
        "message_id": email.message_id if same_message_id else "different-message",
        "fingerprint": fingerprint if same_fingerprint else "different-fingerprint",
    }
    outcome = await execute_lookup(
        _command(excluded_deliveries=[excluded_delivery]),
        FakeProvider([email]),
        FakeNetflix(),
        now=NOW,
    )

    assert outcome.kind == "found"
    assert outcome.result_value == "654321"


@pytest.mark.asyncio
async def test_execute_lookup_returns_fetch_timeout_when_provider_hangs() -> None:
    class HangingProvider:
        async def fetch(self, command: LookupCommand) -> list[EmailMessage]:
            await asyncio.Event().wait()
            return []

    outcome = await execute_lookup(
        _command(timeout_seconds=1), HangingProvider(), FakeNetflix(), now=NOW
    )

    assert outcome.kind == "retryable_failure"
    assert outcome.error_code == "fetch_timeout"


@pytest.mark.asyncio
async def test_execute_lookup_returns_not_found_after_timeout_window() -> None:
    class EmptyProvider:
        attempts = 0

        async def fetch(self, command: LookupCommand) -> list[EmailMessage]:
            self.attempts += 1
            return []

    class Clock:
        elapsed = 0.0

        def monotonic(self) -> float:
            return self.elapsed

        async def sleep(self, seconds: float) -> None:
            self.elapsed += seconds

    clock = Clock()
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(runner_module, "monotonic", clock.monotonic)
    monkeypatch.setattr(runner_module.asyncio, "sleep", clock.sleep)
    try:
        provider = EmptyProvider()
        outcome = await execute_lookup(
            _command(timeout_seconds=8), provider, FakeNetflix(), now=NOW
        )
    finally:
        monkeypatch.undo()

    assert provider.attempts == 2
    assert clock.elapsed == 8
    assert outcome.kind == "not_found"


@pytest.mark.asyncio
async def test_execute_lookup_returns_not_found_without_matching_email() -> None:
    outcome = await execute_lookup(
        _command(timeout_seconds=1),
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
        async def resolve(
            self, value: str, *, upload_diagnostics: bool = False
        ) -> str | None:
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
async def test_netflix_resolution_respects_absolute_deadline() -> None:
    url = "https://www.netflix.com/account/travel/verify?nftoken=slow"

    class SlowNetflix:
        async def resolve(
            self, value: str, *, upload_diagnostics: bool = True
        ) -> str | None:
            assert value == url
            assert upload_diagnostics is False
            await asyncio.sleep(1)
            return "839201"

    email = _email(
        subject="Your Netflix temporary access code",
        body=f"[{url}]({url})",
        sender="noreply@netflix.com",
    )
    outcome = await execute_lookup(
        _command(
            service_key="netflix",
            timeout_seconds=120,
            deadline_at=NOW + timedelta(milliseconds=10),
        ),
        FakeProvider([email]),
        SlowNetflix(),
        now=NOW,
    )

    assert outcome.kind == "retryable_failure"
    assert outcome.error_code == "resolve_timeout"


@pytest.mark.asyncio
async def test_netflix_unresolved_old_link_does_not_stop_new_code_polling() -> None:
    url = "https://www.netflix.com/account/travel/verify?nftoken=expired"
    old_email = _email(
        subject="Your Netflix temporary access code",
        body=f"[{url}]({url})",
        message_id="old-link",
    )
    new_email = _email(
        subject="Your Netflix temporary access code",
        body="Código de verificación:\n\n839201",
        message_id="new-code",
        received_at=NOW + timedelta(seconds=1),
    )

    class DelayedProvider:
        attempts = 0

        async def fetch(self, command: LookupCommand) -> list[EmailMessage]:
            self.attempts += 1
            return [old_email] if self.attempts == 1 else [old_email, new_email]

    class Netflix:
        async def resolve(
            self, value: str, *, upload_diagnostics: bool = False
        ) -> str | None:
            assert value == url
            return None

    class Clock:
        elapsed = 0.0

        def monotonic(self) -> float:
            return self.elapsed

        async def sleep(self, seconds: float) -> None:
            self.elapsed += seconds

    clock = Clock()
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(runner_module, "monotonic", clock.monotonic)
    monkeypatch.setattr(runner_module.asyncio, "sleep", clock.sleep)
    try:
        provider = DelayedProvider()
        outcome = await execute_lookup(
            _command(service_key="netflix", timeout_seconds=8),
            provider,
            Netflix(),
            now=NOW,
        )
    finally:
        monkeypatch.undo()

    assert provider.attempts == 2
    assert clock.elapsed == 4
    assert outcome.kind == "found"
    assert outcome.result_value == "839201"


@pytest.mark.asyncio
async def test_netflix_resolution_failure_is_not_found() -> None:
    url = "https://www.netflix.com/account/travel/verify?nftoken=token"

    class Netflix:
        async def resolve(
            self, value: str, *, upload_diagnostics: bool = False
        ) -> str | None:
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
