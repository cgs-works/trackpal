"""Tests for the standalone Gmail IMAP provider."""

from datetime import UTC, datetime
from email.message import EmailMessage as MimeMessage
from typing import ClassVar

import pytest

from app.providers.errors import NonTransientProviderError, TransientProviderError
from app.providers.gmail_imap import fetch_gmail_messages


class FakeImap:
    search_args: ClassVar[tuple[object, ...] | None] = None
    fetched_ids: ClassVar[list[bytes]] = []

    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        type(self).fetched_ids = []

    def login(self, username: str, password: str) -> tuple[str, list[bytes]]:
        assert username == "codes@example.com"
        assert password == "app-password"
        return "OK", [b"logged in"]

    def select(self, mailbox: str) -> tuple[str, list[bytes]]:
        assert mailbox == "INBOX"
        return "OK", [b"25"]

    def search(self, *args: object) -> tuple[str, list[bytes]]:
        type(self).search_args = args
        return "OK", [b"1 2 3"]

    def fetch(
        self, message_id: bytes, query: str
    ) -> tuple[str, list[tuple[bytes, bytes]]]:
        assert query == "(BODY.PEEK[])"
        type(self).fetched_ids.append(message_id)
        return "OK", [(b"header", _raw_message())]

    def logout(self) -> tuple[str, list[bytes]]:
        return "BYE", [b"logged out"]


def _raw_message() -> bytes:
    message = MimeMessage()
    message["Subject"] = "=?utf-8?q?Your_codes?="
    message["Message-ID"] = "<msg-1>"
    message["From"] = "sender@example.com"
    message["To"] = "Client <client@example.com>"
    message["Cc"] = "client@example.com, other@example.com"
    message["Date"] = "Sat, 01 Aug 2026 00:00:00 +0000"
    message.set_content("Enter code 654321")
    return message.as_bytes()


@pytest.mark.asyncio
async def test_fetch_uses_exact_timestamp_and_newest_bounded_messages() -> None:
    now = datetime(2026, 8, 1, tzinfo=UTC)
    FakeImap.search_args = None

    messages = await fetch_gmail_messages(
        mailbox_email="codes@example.com",
        app_password="app-password",
        window_minutes=5,
        imap_factory=FakeImap,
        now=now,
    )

    assert FakeImap.search_args == (None, "X-GM-RAW", '"after:1785542100"')
    assert FakeImap.fetched_ids == [b"1", b"2", b"3"]
    assert messages[0].to_recipients == (
        "client@example.com",
        "other@example.com",
    )
    assert messages[0].subject == "Your codes"
    assert messages[0].body == "Enter code 654321\n"
    assert messages[0].message_id == "msg-1"


@pytest.mark.asyncio
async def test_fetch_only_reads_twenty_newest_ids() -> None:
    class BoundedImap(FakeImap):
        def search(self, *args: object) -> tuple[str, list[bytes]]:
            return "OK", [b" ".join(str(i).encode() for i in range(1, 26))]

    await fetch_gmail_messages(
        "codes@example.com",
        "app-password",
        5,
        imap_factory=BoundedImap,
        now=datetime(2026, 8, 1, tzinfo=UTC),
    )

    assert BoundedImap.fetched_ids == [str(i).encode() for i in range(6, 26)]


@pytest.mark.asyncio
async def test_login_failure_is_non_transient_and_safe() -> None:
    class AuthFailure(FakeImap):
        def login(self, username: str, password: str) -> tuple[str, list[bytes]]:
            return "NO", [b"password app-password is invalid"]

    with pytest.raises(NonTransientProviderError) as error:
        await fetch_gmail_messages(
            "codes@example.com",
            "app-password",
            5,
            imap_factory=AuthFailure,
            now=datetime(2026, 8, 1, tzinfo=UTC),
        )

    assert error.value.error_code == "auth_failed"
    assert "app-password" not in str(error.value)


@pytest.mark.asyncio
async def test_connection_failure_is_transient() -> None:
    def failing_factory(host: str, port: int) -> object:
        raise OSError("connection refused")

    with pytest.raises(TransientProviderError):
        await fetch_gmail_messages(
            "codes@example.com",
            "app-password",
            5,
            imap_factory=failing_factory,
            now=datetime(2026, 8, 1, tzinfo=UTC),
        )
