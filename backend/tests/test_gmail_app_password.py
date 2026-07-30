"""Tests for Gmail app-password validation module."""

from unittest.mock import AsyncMock

import pytest

from app.services import gmail_app_password


def test_normalize_app_password_removes_grouping_spaces() -> None:
    assert gmail_app_password.normalize_app_password(" abcd efgh ijkl mnop ") == (
        "abcdefghijklmnop"
    )


@pytest.mark.asyncio
async def test_validate_uses_fixed_gmail_settings(monkeypatch) -> None:
    connect = AsyncMock(return_value=None)
    monkeypatch.setattr(gmail_app_password, "test_imap_connection", connect)

    normalized = await gmail_app_password.validate_gmail_app_password(
        "codes@example.com", "abcd efgh ijkl mnop"
    )

    assert normalized == "abcdefghijklmnop"
    connect.assert_awaited_once_with(
        host="imap.gmail.com",
        port=993,
        ssl=True,
        username="codes@example.com",
        password="abcdefghijklmnop",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error_type,expected_code",
    [
        (gmail_app_password.ImapAuthenticationError, "authentication_rejected"),
        (gmail_app_password.ImapTimeoutError, "timeout"),
        (gmail_app_password.ImapUnavailableError, "unavailable"),
    ],
)
async def test_validate_maps_imap_failures(monkeypatch, error_type, expected_code) -> None:
    monkeypatch.setattr(
        gmail_app_password,
        "test_imap_connection",
        AsyncMock(side_effect=error_type("provider detail that must not escape")),
    )

    with pytest.raises(gmail_app_password.GmailAppPasswordError) as captured:
        await gmail_app_password.validate_gmail_app_password(
            "codes@example.com", "abcdefghijklmnop"
        )

    assert captured.value.code == expected_code
    assert "provider detail" not in str(captured.value)
