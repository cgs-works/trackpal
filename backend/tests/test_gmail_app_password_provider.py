"""Tests for the Gmail app-password lookup provider."""

from datetime import datetime, timedelta, timezone

import pytest

from app.core.encryption import encrypt_value
from app.models.tenant_mailbox import TenantMailbox
from app.services.mail_lookup_worker.providers import _gmail_app_password as provider


class _FakeImapConnection:
    search_args: tuple[object, ...] | None = None

    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port

    def login(self, username: str, password: str) -> tuple[str, list[bytes]]:
        return "OK", [b"logged in"]

    def select(self, mailbox: str) -> tuple[str, list[bytes]]:
        return "OK", [b"0"]

    def search(self, *args: object) -> tuple[str, list[bytes]]:
        type(self).search_args = args
        return "OK", [b""]

    def logout(self) -> tuple[str, list[bytes]]:
        return "BYE", [b"logged out"]


@pytest.mark.asyncio
async def test_fetch_uses_exact_gmail_timestamp_query(monkeypatch) -> None:
    """The IMAP lookup must not depend on Gmail's local calendar date."""

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            value = cls(2026, 7, 31, 2, 10, tzinfo=timezone.utc)
            return value if tz is not None else value.replace(tzinfo=None)

    monkeypatch.setattr(provider, "datetime", FrozenDateTime)
    monkeypatch.setattr(provider.imaplib, "IMAP4_SSL", _FakeImapConnection)
    _FakeImapConnection.search_args = None

    mailbox = TenantMailbox(
        mailbox_email="mailbox@gmail.com",
        app_password_encrypted=encrypt_value("app-password"),
    )

    await provider.fetch_gmail_app_password_emails(mailbox, window_minutes=5)

    expected_after = int(
        (FrozenDateTime.now(timezone.utc) - timedelta(minutes=5)).timestamp()
    )
    assert _FakeImapConnection.search_args == (
        None,
        "X-GM-RAW",
        f'"after:{expected_after}"',
    )
