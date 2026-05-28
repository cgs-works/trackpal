"""IMAP connection test utility — validate IMAP credentials."""

import asyncio
import imaplib
import logging

logger = logging.getLogger(__name__)

IMAP_TEST_TIMEOUT = 10  # seconds


class ImapConnectionError(Exception):
    """Raised when IMAP connection or authentication fails."""


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
        raise ImapConnectionError(
            f"Connection timed out after {timeout}s connecting to {host}:{port}"
        ) from None
    except ImapConnectionError:
        raise
    except Exception as exc:
        logger.warning("Unexpected IMAP test error: %s", exc)
        raise ImapConnectionError(f"Connection failed: {exc}") from exc

    if not connected:
        raise ImapConnectionError("IMAP connection closed unexpectedly")


async def _connect_and_login(
    host: str, port: int, ssl: bool, username: str, password: str
) -> bool:
    """Connect and login to IMAP server in a thread."""
    loop = asyncio.get_running_loop()

    def _sync_imap() -> bool:
        try:
            if ssl:
                conn = imaplib.IMAP4_SSL(host, port)
            else:
                conn = imaplib.IMAP4(host, port)
        except Exception as exc:
            raise ImapConnectionError(
                f"Cannot connect to {host}:{port}: {exc}"
            ) from exc

        try:
            result = conn.login(username, password)
            if result[0] != "OK":
                raise ImapConnectionError(
                    f"Authentication failed: {result[1].decode('utf-8', errors='replace')}"
                )
            conn.logout()
            return True
        except ImapConnectionError:
            raise
        except Exception as exc:
            raise ImapConnectionError(f"Login failed: {exc}") from exc

    return await loop.run_in_executor(None, _sync_imap)
