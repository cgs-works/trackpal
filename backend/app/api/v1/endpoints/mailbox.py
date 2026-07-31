"""Tenant mailbox configuration endpoints."""

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import ActiveTenantId, DbDep
from app.api.v1.endpoints._mailbox_helpers import (
    handle_test_error,
    mailbox_response,
    test_mailbox_connection as _run_mailbox_test,
)
from app.core.encryption import encrypt_value
from app.core.metrics import metrics
from app.models import TenantMailbox
from app.repositories import mailbox_config_repository
from app.schemas.mailbox import (
    GmailAppPasswordConnectRequest,
    MailboxResponse,
    MailboxTestResponse,
)
from app.services.gmail_app_password import (
    GmailAppPasswordError,
    validate_gmail_app_password,
)

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
    payload: GmailAppPasswordConnectRequest,
    db: DbDep,
    tenant_id: ActiveTenantId,
):
    """Create or update mailbox configuration.

    Validates the Gmail app password before persisting. On success,
    atomically creates or replaces the mailbox row. On validation failure,
    returns a safe error code without mutating existing data.
    """
    # Validate before loading or mutating the existing mailbox
    try:
        normalized_password = await validate_gmail_app_password(
            payload.mailbox_email, payload.app_password
        )
    except GmailAppPasswordError as exc:
        if exc.code == "authentication_rejected":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="gmail_app_password_rejected",
            ) from exc
        # timeout and unavailable -> 503
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="gmail_connection_unavailable",
        ) from exc

    existing = await mailbox_config_repository.get_by_tenant(db, tenant_id)

    now = datetime.now(timezone.utc)
    values = {
        "mailbox_email": payload.mailbox_email,
        "status": "connected",
        "app_password_encrypted": encrypt_value(normalized_password),
        "last_connection_test_at": now,
        "last_connection_error": None,
    }

    if existing:
        mailbox = await mailbox_config_repository.update(db, existing, **values)
    else:
        mailbox = TenantMailbox(
            tenant_id=tenant_id,
            **values,
        )
        mailbox = await mailbox_config_repository.create(db, tenant_id, mailbox)

    await db.commit()
    await db.refresh(mailbox)
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
    except HTTPException:
        raise
    except Exception as exc:
        await handle_test_error(db, mailbox, exc)
        await db.commit()
        return MailboxTestResponse(success=False, message=str(exc))


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
