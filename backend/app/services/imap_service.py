"""IMAP connection test utility — validate IMAP credentials."""

import asyncio
import imaplib
import logging
from contextlib import suppress

logger = logging.getLogger(__name__)

IMAP_TEST_TIMEOUT = 10  # seconds


class ImapConnectionError(Exception):
    """Base class for safe IMAP connection-test failures."""


class ImapAuthenticationError(ImapConnectionError):
    """The server rejected the supplied username or credential."""


class ImapTimeoutError(ImapConnectionError):
    """The connection attempt exceeded the configured timeout."""


class ImapUnavailableError(ImapConnectionError):
    """The server could not be reached or the connection failed."""


async def test_imap_connection(
    host: str,
    port: int,
    ssl: bool,
    username: str,
    password: str,
    timeout: int = IMAP_TEST_TIMEOUT,
) -> None:
    """Test IMAP connection and authentication.

    Connects to the IMAP server, logs in, and immediately logs out.

    Raises ``ImapConnectionError`` with a descriptive message on failure.
    """
    try:
        connected = await asyncio.wait_for(
            _connect_and_login(host, port, ssl, username, password),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        raise ImapTimeoutError(
            f"Connection timed out after {timeout}s connecting to {host}:{port}"
        ) from None
    except ImapConnectionError:
        raise
    except Exception as exc:
        logger.warning("Unexpected IMAP test error: %s", exc)
        raise ImapUnavailableError(f"Connection failed: {exc}") from exc

    if not connected:
        raise ImapUnavailableError("IMAP connection closed unexpectedly")


async def _connect_and_login(
    host: str, port: int, ssl: bool, username: str, password: str
) -> bool:
    """Connect and login to IMAP server in a thread."""
    loop = asyncio.get_running_loop()

    def _sync_imap() -> bool:
        conn: imaplib.IMAP4 | imaplib.IMAP4_SSL | None = None
        try:
            if ssl:
                conn = imaplib.IMAP4_SSL(host, port)
            else:
                conn = imaplib.IMAP4(host, port)

            result = conn.login(username, password)
            if result[0] != "OK":
                raise ImapAuthenticationError(
                    "Authentication failed"
                )
            return True
        except ImapConnectionError:
            raise
        except imaplib.IMAP4.error as exc:
            raise ImapAuthenticationError("Authentication failed") from exc
        except Exception as exc:
            if conn is None:
                raise ImapUnavailableError(
                    f"Cannot connect to {host}:{port}: {exc}"
                ) from exc
            raise ImapUnavailableError(f"Login failed: {exc}") from exc
        finally:
            if conn is not None:
                with suppress(Exception):
                    conn.logout()

    return await loop.run_in_executor(None, _sync_imap)
