"""Helper functions and shared instance for mailbox endpoints."""

from fastapi import HTTPException, status

from app.core.encryption import decrypt_value
from app.core.metrics import metrics
from app.models import TenantMailbox
from app.repositories import mailbox_config_repository
from app.schemas.mailbox import MailboxResponse, MailboxTestResponse
from app.services.gmail_app_password import (
    GMAIL_IMAP_HOST,
    GMAIL_IMAP_PORT,
    GMAIL_IMAP_SSL,
)
from app.services.imap_service import ImapAuthenticationError, test_imap_connection
from app.services.oauth_service import MailboxOAuthService

oauth_service = MailboxOAuthService()

# Safe error messages for test connection failures — no IMAP internals.
_APP_PASSWORD_AUTH_ERROR = "gmail_app_password_rejected"
_APP_PASSWORD_CONN_ERROR = "gmail_connection_unavailable"


def mailbox_response(mb: TenantMailbox) -> MailboxResponse:
    """Convert ``TenantMailbox`` to response schema."""
    return MailboxResponse(
        id=mb.id,
        tenant_id=mb.tenant_id,
        mailbox_email=mb.mailbox_email,
        auth_method=mb.auth_method,
        status=mb.status,
        oauth_provider_user_id=mb.oauth_provider_user_id,
        oauth_provider_email=mb.oauth_provider_email,
        last_connection_test_at=mb.last_connection_test_at,
        last_connection_error=mb.last_connection_error,
        created_at=mb.created_at,
        updated_at=mb.updated_at,
    )


async def _perform_app_password_test(db, mailbox: TenantMailbox) -> MailboxTestResponse:
    """Test Gmail app-password connection using stored credentials."""
    if not mailbox.app_password_encrypted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="App password not configured",
        )
    password = decrypt_value(mailbox.app_password_encrypted)
    if password is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="App password not available",
        )
    try:
        await test_imap_connection(
            host=GMAIL_IMAP_HOST,
            port=GMAIL_IMAP_PORT,
            ssl=GMAIL_IMAP_SSL,
            username=mailbox.mailbox_email,
            password=password,
        )
    except ImapAuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_APP_PASSWORD_AUTH_ERROR,
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_APP_PASSWORD_CONN_ERROR,
        ) from exc
    return await _record_test_success(db, mailbox)


async def _perform_oauth_test(db, mailbox: TenantMailbox) -> MailboxTestResponse:
    """Test OAuth connection by attempting token refresh."""
    result = await oauth_service.refresh_token(db, mailbox)
    if result.status == "revoked":
        await mailbox_config_repository.update_connection_test(
            db,
            mailbox,
            success=False,
            error="OAuth tokens revoked",
        )
        metrics.inc("mailbox_test_total", method="oauth", status="revoked")
        return MailboxTestResponse(
            success=False,
            message="OAuth tokens revoked. Reconnect your mailbox.",
        )
    return await _record_test_success(
        db, mailbox, method="oauth", message="OAuth connection OK"
    )


async def _record_test_success(
    db,
    mailbox: TenantMailbox,
    method: str | None = None,
    message: str = "Connection successful",
) -> MailboxTestResponse:
    """Record successful test result and return response."""
    await mailbox_config_repository.update_connection_test(db, mailbox, success=True)
    metrics.inc("mailbox_test_total", method=method or mailbox.auth_method, status="ok")
    return MailboxTestResponse(success=True, message=message)


async def test_mailbox_connection(db, mailbox: TenantMailbox) -> MailboxTestResponse:
    """Route test to the correct auth method."""
    if mailbox.auth_method == "app_password":
        return await _perform_app_password_test(db, mailbox)
    if mailbox.auth_method == "oauth":
        return await _perform_oauth_test(db, mailbox)
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Unknown auth method: {mailbox.auth_method}",
    )


async def handle_test_error(db, mailbox: TenantMailbox, error: Exception) -> None:
    """Record test failure in mailbox and emit metric."""
    await mailbox_config_repository.update_connection_test(
        db, mailbox, success=False, error=str(error)
    )
    metrics.inc("mailbox_test_total", method=mailbox.auth_method, status="error")
