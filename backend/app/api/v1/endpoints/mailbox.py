"""Tenant mailbox configuration endpoints."""

from fastapi import APIRouter, HTTPException, Query, status

from app.api.dependencies import ActiveTenantId, DbDep
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
            mailbox.imap_password_encrypted = encrypt_value(payload.imap_password)
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

    mailbox = await mailbox_config_repository.get_by_tenant(db, tenant_id)
    if mailbox is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Configure mailbox email before connecting OAuth",
        )

    result = await oauth_service.start_oauth(db, tenant_id, provider)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to start OAuth for {provider}",
        )
    return result


@router.get("/oauth/{provider}/callback")
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
        mailbox = await oauth_service.complete_oauth(db, provider, code, state)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    await db.commit()
    return mailbox_response(mailbox)


@router.post("/disconnect", response_model=MailboxResponse)
async def disconnect_mailbox(
    db: DbDep,
    tenant_id: ActiveTenantId,
):
    """Disconnect mailbox and clear all credentials."""
    mailbox = await mailbox_config_repository.get_by_tenant(db, tenant_id)
    if mailbox is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mailbox not configured",
        )

    await oauth_service.disconnect(db, mailbox)
    await db.commit()
    return mailbox_response(mailbox)
