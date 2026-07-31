"""Tests for IMAP connection testing service."""

import asyncio
import imaplib
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.services.imap_service import ImapAuthenticationError
from app.services.imap_service import ImapConnectionError
from app.services.imap_service import ImapTimeoutError
from app.services.imap_service import ImapUnavailableError
from app.services.imap_service import test_imap_connection as _test_imap_connection


# ─── IMAP Service ─────────────────────────────────────────────────────────


class TestImapService:
    """IMAP connection test — mock imaplib."""

    @pytest.mark.asyncio
    async def test_imap_connection_timeout(self):
        """Timeout raises ImapConnectionError."""
        with (
            patch(
                "app.services.imap_service._connect_and_login",
                new_callable=Mock,
                return_value=True,
            ),
            patch(
                "app.services.imap_service.asyncio.wait_for",
                side_effect=asyncio.TimeoutError,
            ),
            pytest.raises(ImapTimeoutError, match="timed out"),
        ):
            await _test_imap_connection(
                host="imap.example.com",
                port=993,
                ssl=True,
                username="user",
                password="pass",
                timeout=1,
            )

    @pytest.mark.asyncio
    async def test_imap_connection_failure_raises_imap_error(self):
        """Connection error raises ImapConnectionError."""
        with (
            patch(
                "app.services.imap_service._connect_and_login",
                side_effect=ImapUnavailableError("Cannot connect"),
            ),
            pytest.raises(ImapConnectionError, match="Cannot connect"),
        ):
            await _test_imap_connection(
                host="bad.host",
                port=993,
                ssl=True,
                username="u",
                password="p",
            )

    @pytest.mark.asyncio
    async def test_imap_connection_success(self):
        """Successful connect+login returns without error."""
        with patch(
            "app.services.imap_service._connect_and_login",
            new_callable=AsyncMock,
            return_value=True,
        ):
            result = await _test_imap_connection(
                host="imap.gmail.com",
                port=993,
                ssl=True,
                username="test@gmail.com",
                password="app-pass",
            )
            assert result is None

    @pytest.mark.asyncio
    async def test_imap_connection_auth_failure(self):
        """Failed login raises ImapConnectionError."""
        with (
            patch(
                "app.services.imap_service._connect_and_login",
                side_effect=ImapAuthenticationError("Authentication failed"),
            ),
            pytest.raises(ImapConnectionError, match="Authentication failed"),
        ):
            await _test_imap_connection(
                host="imap.example.com",
                port=993,
                ssl=True,
                username="user",
                password="wrong",
            )

    def test_imap_error_subclasses_inherit_from_base(self):
        """All typed IMAP errors inherit from ImapConnectionError."""
        assert issubclass(ImapAuthenticationError, ImapConnectionError)
        assert issubclass(ImapTimeoutError, ImapConnectionError)
        assert issubclass(ImapUnavailableError, ImapConnectionError)

    @pytest.mark.asyncio
    async def test_imap_constructor_error_becomes_unavailable(self):
        """imaplib.IMAP4.error during construction must be ImapUnavailableError.

        The SSL constructor failing (e.g. DNS failure, connection refused)
        is an availability problem, not an authentication problem.
        """
        with (
            patch(
                "app.services.imap_service.imaplib.IMAP4_SSL",
                side_effect=imaplib.IMAP4.error("Connection refused"),
            ),
            pytest.raises(ImapUnavailableError, match="Cannot connect"),
        ):
            await _test_imap_connection(
                host="unreachable.host",
                port=993,
                ssl=True,
                username="user",
                password="pass",
            )

    @pytest.mark.asyncio
    async def test_imap_login_error_becomes_auth_error(self):
        """imaplib.IMAP4.error from login() must be ImapAuthenticationError.

        Only a credential failure during login should be classified as
        authentication error.  Connection success + login failure is the
        distinguishing signal.
        """
        mock_conn = Mock()
        mock_conn.login.side_effect = imaplib.IMAP4.error("Invalid credentials")
        with (
            patch(
                "app.services.imap_service.imaplib.IMAP4_SSL",
                return_value=mock_conn,
            ),
            pytest.raises(ImapAuthenticationError, match="Authentication failed"),
        ):
            await _test_imap_connection(
                host="imap.gmail.com",
                port=993,
                ssl=True,
                username="user",
                password="wrong",
            )
