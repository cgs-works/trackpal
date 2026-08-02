"""Regression tests for Task 3 review findings."""

import imaplib
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app.netflix.r2_diagnostics import R2Diagnostics
from app.netflix.resolver import NetflixResolver, extract_netflix_verify_code
from app.pipeline.email_message import EmailMessage
from app.pipeline.models import LookupCommand
from app.pipeline.runner import execute_lookup
from app.providers.errors import NonTransientProviderError, TransientProviderError
from app.providers.gmail_imap import fetch_gmail_messages

NOW = datetime(2026, 8, 1, tzinfo=UTC)


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


def _email(
    message_id: str,
    received_at: datetime,
    body: str = "Enter this code 654321",
    subject: str = "Your Spotify login code",
) -> EmailMessage:
    return EmailMessage(
        subject=subject,
        body=body,
        received_at=received_at,
        message_id=message_id,
        sender="noreply@spotify.com",
        to_recipients=("client@example.com",),
    )


@pytest.mark.asyncio
async def test_login_abort_is_retryable() -> None:
    class AbortedLogin:
        def __init__(self, host: str, port: int) -> None:
            pass

        def login(self, username: str, password: str) -> tuple[str, list[bytes]]:
            raise imaplib.IMAP4.abort("connection dropped while logging in")

        def logout(self) -> tuple[str, list[bytes]]:
            return "BYE", []

    with pytest.raises(TransientProviderError):
        await fetch_gmail_messages(
            "codes@example.com",
            "app-password",
            5,
            imap_factory=AbortedLogin,
            now=NOW,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error_message",
    [
        "[AUTHENTICATIONFAILED] Invalid credentials",
        "[ALERT] Invalid credentials",
        "Login failed",
    ],
)
async def test_explicit_credential_rejection_is_terminal(error_message: str) -> None:
    class RejectedLogin:
        def __init__(self, host: str, port: int) -> None:
            pass

        def login(self, username: str, password: str) -> tuple[str, list[bytes]]:
            raise imaplib.IMAP4.error(error_message)

        def logout(self) -> tuple[str, list[bytes]]:
            return "BYE", []

    with pytest.raises(NonTransientProviderError) as error:
        await fetch_gmail_messages(
            "codes@example.com",
            "app-password",
            5,
            imap_factory=RejectedLogin,
            now=NOW,
        )

    assert error.value.error_code == "auth_failed"
    assert error_message not in str(error.value)
    assert "app-password" not in str(error.value)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error_message",
    [
        "temporary authentication service failure",
        "authentication service unavailable",
        "temporary IMAP service failure",
        "Login failed: timeout",
    ],
)
async def test_transient_authentication_service_error_is_retryable(
    error_message: str,
) -> None:
    class TemporaryLoginFailure:
        def __init__(self, host: str, port: int) -> None:
            pass

        def login(self, username: str, password: str) -> tuple[str, list[bytes]]:
            raise imaplib.IMAP4.error(error_message)

        def logout(self) -> tuple[str, list[bytes]]:
            return "BYE", []

    with pytest.raises(TransientProviderError):
        await fetch_gmail_messages(
            "codes@example.com",
            "app-password",
            5,
            imap_factory=TemporaryLoginFailure,
            now=NOW,
        )


@pytest.mark.asyncio
async def test_authentication_failed_server_unavailable_is_retryable() -> None:
    class ServerUnavailable:
        def __init__(self, host: str, port: int) -> None:
            pass

        def login(self, username: str, password: str) -> tuple[str, list[bytes]]:
            raise imaplib.IMAP4.error("authentication failed: server unavailable")

        def logout(self) -> tuple[str, list[bytes]]:
            return "BYE", []

    with pytest.raises(TransientProviderError):
        await fetch_gmail_messages(
            "codes@example.com",
            "app-password",
            5,
            imap_factory=ServerUnavailable,
            now=NOW,
        )


@pytest.mark.asyncio
async def test_login_timeout_is_retryable() -> None:
    class TimedOutLogin:
        def __init__(self, host: str, port: int) -> None:
            pass

        def login(self, username: str, password: str) -> tuple[str, list[bytes]]:
            raise TimeoutError("IMAP login timed out")

        def logout(self) -> tuple[str, list[bytes]]:
            return "BYE", []

    with pytest.raises(TransientProviderError):
        await fetch_gmail_messages(
            "codes@example.com",
            "app-password",
            5,
            imap_factory=TimedOutLogin,
            now=NOW,
        )


@pytest.mark.asyncio
async def test_newest_extracted_message_identity_is_preserved() -> None:
    older = _email("older", NOW - timedelta(minutes=2))
    newest = _email("newest", NOW - timedelta(minutes=1))

    class Provider:
        async def fetch(self, command: LookupCommand) -> list[EmailMessage]:
            return [older, newest]

    outcome = await execute_lookup(_command(), Provider(), object(), now=NOW)

    assert outcome.kind == "found"
    assert outcome.message_id == "newest"


@pytest.mark.asyncio
async def test_code_extracted_from_subject_keeps_source_identity() -> None:
    email = _email(
        "subject-code",
        NOW - timedelta(minutes=1),
        body="This message has no code in its body",
        subject="Tu código de inicio de sesión de Spotify: 654321",
    )

    class Provider:
        async def fetch(self, command: LookupCommand) -> list[EmailMessage]:
            return [email]

    outcome = await execute_lookup(_command(), Provider(), object(), now=NOW)

    assert outcome.kind == "found"
    assert outcome.result_value == "654321"
    assert outcome.message_id == "subject-code"


def test_diagnostic_upload_does_not_log_storage_exception(
    caplog: pytest.LogCaptureFixture,
) -> None:
    class FailingStorage:
        def put(self, key: str, body: bytes, content_type: str) -> str | None:
            raise RuntimeError("signed-url-secret-and-authorization-header")

    diagnostics = R2Diagnostics(FailingStorage())
    result = diagnostics.upload("<html>private diagnostic</html>", "token")

    assert result is None
    assert "signed-url-secret" not in caplog.text
    assert "Failed to upload Netflix diagnostic HTML" in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [200, 301, 302])
async def test_netflix_resolver_accepts_success_and_redirect_statuses(
    status_code: int,
) -> None:
    html = '<div data-uia="travel-verification-otp" class="challenge-code">839201</div>'

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(status_code, text=html)
        ),
        follow_redirects=False,
    ) as client:
        result = await NetflixResolver(client).resolve(
            "https://www.netflix.com/account/travel/verify?nftoken=token"
        )

    assert result == "839201"


def test_netflix_html_extraction_returns_the_embedded_code() -> None:
    html = '<div data-uia="travel-verification-otp" class="challenge-code">839201</div>'

    assert extract_netflix_verify_code(html) == "839201"


@pytest.mark.asyncio
async def test_netflix_resolver_retries_injected_client_failures() -> None:
    attempts = 0
    html = '<div data-uia="travel-verification-otp" class="challenge-code">839201</div>'

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise httpx.ConnectError("temporary network failure", request=request)
        return httpx.Response(200, text=html)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await NetflixResolver(client).resolve(
            "https://www.netflix.com/account/travel/verify?nftoken=token"
        )

    assert result == "839201"
    assert attempts == 2


@pytest.mark.asyncio
async def test_failed_diagnostic_upload_keeps_resolver_not_found_result() -> None:
    class FailingStorage:
        def put(self, key: str, body: bytes, content_type: str) -> str | None:
            raise RuntimeError("storage credentials must stay private")

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, text="<html>no code</html>")
        )
    ) as client:
        result = await NetflixResolver(
            client,
            R2Diagnostics(FailingStorage()),
        ).resolve("https://www.netflix.com/account/travel/verify?nftoken=token")

    assert result is None
