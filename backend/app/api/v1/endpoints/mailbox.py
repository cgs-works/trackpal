"""Tenant mailbox configuration endpoints."""

from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import HTMLResponse

from app.api.dependencies import ActiveTenantId, DbDep
from app.core.config import settings
from app.api.v1.endpoints._mailbox_helpers import (
    derive_auth_method,
    handle_test_error,
    mailbox_response,
    oauth_service,
    test_mailbox_connection as _run_mailbox_test,
)
from app.core.encryption import encrypt_value
from app.core.metrics import metrics
from app.models import TenantMailbox
from app.repositories import mailbox_config_repository
from app.schemas.mailbox import (
    MailboxConfigUpdate,
    MailboxResponse,
    MailboxTestResponse,
    OAuthStartResponse,
)
from app.services.imap_service import ImapConnectionError

router = APIRouter(prefix="/tenant/mailbox", tags=["tenant-mailbox"])


def _frontend_dashboard_url() -> str:
    origins = [
        item.strip() for item in settings.cors_origins.split(",") if item.strip()
    ]
    base_url = origins[0] if origins else "http://localhost:5173"
    return f"{base_url.rstrip('/')}/admin/mailbox"


def _oauth_callback_html(status_value: str) -> str:
    target = f"{_frontend_dashboard_url()}?mailbox_oauth={quote(status_value)}"
    return f"""<!doctype html>
<html>
  <head>
    <meta charset=\"utf-8\" />
    <title>Mailbox OAuth</title>
  </head>
  <body>
    <script>
      (function () {{
        var target = {target!r};
        if (window.opener && !window.opener.closed) {{
          window.opener.location.assign(target);
          window.close();
          return;
        }}
        window.location.assign(target);
      }})();
    </script>
    <p>Redirecting...</p>
  </body>
</html>"""


@router.get("/", response_model=MailboxResponse)
async def get_mailbox(
    db: DbDep,
    tenant_id: ActiveTenantId,
):
    """Get current tenant's mailbox configuration."""
    mailbox = await mailbox_config_repository.get_by_tenant(db, tenant_id)
    if mailbox is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mailbox not configured",
        )
    return mailbox_response(mailbox)


@router.put("/", response_model=MailboxResponse)
async def upsert_mailbox(
    payload: MailboxConfigUpdate,
    db: DbDep,
    tenant_id: ActiveTenantId,
):
    """Create or update mailbox configuration."""
    auth_method = derive_auth_method(payload.provider.value)
    existing = await mailbox_config_repository.get_by_tenant(db, tenant_id)

    if existing:
        kwargs: dict[str, object | None] = {
            "mailbox_email": payload.mailbox_email,
            "provider": payload.provider.value,
            "auth_method": auth_method,
            "status": "disconnected",
        }
        if payload.provider.value == "imap_custom":
            # Validated by schema model_validator for imap_custom
            if payload.imap_password is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="IMAP password is required",
                )
            kwargs["imap_host"] = payload.imap_host
            kwargs["imap_port"] = payload.imap_port
            kwargs["imap_ssl"] = payload.imap_ssl
            kwargs["imap_password_encrypted"] = encrypt_value(payload.imap_password)
            kwargs["oauth_access_token_encrypted"] = None
            kwargs["oauth_refresh_token_encrypted"] = None
            kwargs["oauth_token_expires_at"] = None
        else:
            kwargs["imap_host"] = None
            kwargs["imap_port"] = None
            kwargs["imap_password_encrypted"] = None
        mailbox = await mailbox_config_repository.update(db, existing, **kwargs)
    else:
        mailbox = TenantMailbox(
            tenant_id=tenant_id,
            mailbox_email=payload.mailbox_email,
            provider=payload.provider.value,
            auth_method=auth_method,
            status="disconnected",
        )
        if payload.provider.value == "imap_custom":
            mailbox.imap_host = payload.imap_host
            mailbox.imap_port = payload.imap_port
            mailbox.imap_ssl = payload.imap_ssl
            mailbox.imap_password_encrypted = (
                encrypt_value(payload.imap_password)
                if payload.imap_password is not None
                else None
            )
        mailbox = await mailbox_config_repository.create(db, tenant_id, mailbox)

    await db.commit()
    metrics.inc("mailbox_api_request", endpoint="upsert_mailbox", status="ok")
    return mailbox_response(mailbox)


@router.post("/test", response_model=MailboxTestResponse)
async def test_mailbox_connection(
    db: DbDep,
    tenant_id: ActiveTenantId,
):
    """Test current mailbox connection."""
    mailbox = await mailbox_config_repository.get_by_tenant(db, tenant_id)
    if mailbox is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Mailbox not configured")

    if mailbox.auth_method == "oauth":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Manual test is only available for IMAP mailboxes",
        )

    try:
        result = await _run_mailbox_test(db, mailbox)
        await db.commit()
        return result
    except ImapConnectionError as exc:
        await handle_test_error(db, mailbox, exc)
        await db.commit()
        return MailboxTestResponse(success=False, message=str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        await handle_test_error(db, mailbox, exc)
        await db.commit()
        return MailboxTestResponse(success=False, message=str(exc))


@router.post("/oauth/{provider}/start", response_model=OAuthStartResponse)
async def oauth_start(
    provider: str,
    db: DbDep,
    tenant_id: ActiveTenantId,
):
    """Start OAuth flow for Google or Microsoft."""
    if provider not in ("google", "microsoft"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported OAuth provider: {provider}",
        )

    result = await oauth_service.start_oauth(db, tenant_id, provider)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to start OAuth for {provider}",
        )
    return result


@router.get("/oauth/{provider}/callback", response_class=HTMLResponse)
async def oauth_callback(
    provider: str,
    db: DbDep,
    code: str = Query(...),
    state: str = Query(...),
):
    """Handle OAuth callback from Google or Microsoft.

    Public endpoint (no bearer token). Security relies on
    state token validation which encodes tenant context.
    """
    if provider not in ("google", "microsoft"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported OAuth provider: {provider}",
        )

    try:
        await oauth_service.complete_oauth(db, provider, code, state)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    await db.commit()
    return HTMLResponse(content=_oauth_callback_html("success"))


@router.post("/disconnect", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_mailbox(
    db: DbDep,
    tenant_id: ActiveTenantId,
):
    """Disconnect mailbox by deleting tenant mailbox config."""
    mailbox = await mailbox_config_repository.get_by_tenant(db, tenant_id)
    if mailbox is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mailbox not configured",
        )

    await mailbox_config_repository.delete(db, mailbox)
    await db.commit()
