"""Tests for mailbox API endpoints — Gmail-only connection flow."""

from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from app.core.encryption import decrypt_value
from app.models import Tenant, TenantMailbox


async def _tenant_headers(client) -> dict[str, str]:
    login = await client.post(
        "/api/v1/auth/login",
        json={"username": "tenant", "password": "tenant-password"},
    )
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


@pytest.mark.asyncio
async def test_connect_app_password_validates_before_persisting(
    client, db_session, active_tenant_user, monkeypatch
) -> None:
    validate = AsyncMock(return_value="abcdefghijklmnop")
    monkeypatch.setattr(
        "app.api.v1.endpoints.mailbox.validate_gmail_app_password", validate
    )

    response = await client.put(
        "/api/v1/tenant/mailbox/",
        json={
            "mailbox_email": "codes@example.com",
            "app_password": "abcd efgh ijkl mnop",
        },
        headers=await _tenant_headers(client),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["auth_method"] == "app_password"
    assert body["status"] == "connected"
    assert "provider" not in body
    assert "imap_host" not in body
    validate.assert_awaited_once_with("codes@example.com", "abcd efgh ijkl mnop")

    tenant_id = (
        await db_session.execute(
            select(Tenant.id).where(Tenant.owner_user_id == active_tenant_user.id)
        )
    ).scalar_one()
    db_session.expire_all()
    mailbox = (
        await db_session.execute(
            select(TenantMailbox).where(TenantMailbox.tenant_id == tenant_id)
        )
    ).scalar_one()
    assert decrypt_value(mailbox.app_password_encrypted) == "abcdefghijklmnop"


@pytest.mark.asyncio
async def test_connect_replaces_existing_mailbox_atomically(
    client, db_session, active_tenant_user, monkeypatch
) -> None:
    """When a mailbox already exists, PUT replaces it atomically (no intermediate state)."""
    # Seed an existing mailbox with old credentials
    tenant_id = (
        await db_session.execute(
            select(Tenant.id).where(Tenant.owner_user_id == active_tenant_user.id)
        )
    ).scalar_one()
    from app.core.encryption import encrypt_value

    old = TenantMailbox(
        tenant_id=tenant_id,
        mailbox_email="old@example.com",
        auth_method="oauth",
        status="connected",
        oauth_access_token_encrypted=encrypt_value("old-token"),
    )
    db_session.add(old)
    await db_session.commit()

    # Now PUT with app_password — should replace
    validate = AsyncMock(return_value="new-normalized-pw")
    monkeypatch.setattr(
        "app.api.v1.endpoints.mailbox.validate_gmail_app_password", validate
    )

    response = await client.put(
        "/api/v1/tenant/mailbox/",
        json={
            "mailbox_email": "new@example.com",
            "app_password": "new pw here",
        },
        headers=await _tenant_headers(client),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["auth_method"] == "app_password"
    assert body["status"] == "connected"
    assert body["mailbox_email"] == "new@example.com"

    # Verify old OAuth fields are cleared
    db_session.expire_all()
    mailbox = (
        await db_session.execute(
            select(TenantMailbox).where(TenantMailbox.tenant_id == tenant_id)
        )
    ).scalar_one()
    assert mailbox.oauth_access_token_encrypted is None
    assert decrypt_value(mailbox.app_password_encrypted) == "new-normalized-pw"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error_code,expected_status",
    [
        ("authentication_rejected", 400),
        ("timeout", 503),
        ("unavailable", 503),
    ],
)
async def test_connect_validation_error_does_not_mutate_existing(
    client, db_session, active_tenant_user, monkeypatch, error_code, expected_status
) -> None:
    """When validation fails, the existing mailbox is left unchanged."""
    from app.core.encryption import encrypt_value
    from app.services.gmail_app_password import GmailAppPasswordError

    tenant_id = (
        await db_session.execute(
            select(Tenant.id).where(Tenant.owner_user_id == active_tenant_user.id)
        )
    ).scalar_one()

    # Seed existing working mailbox
    old = TenantMailbox(
        tenant_id=tenant_id,
        mailbox_email="old@example.com",
        auth_method="app_password",
        status="connected",
        app_password_encrypted=encrypt_value("old-working-password"),
    )
    db_session.add(old)
    await db_session.commit()

    # Mock validation to raise error
    validate = AsyncMock(side_effect=GmailAppPasswordError(error_code))
    monkeypatch.setattr(
        "app.api.v1.endpoints.mailbox.validate_gmail_app_password", validate
    )

    response = await client.put(
        "/api/v1/tenant/mailbox/",
        json={
            "mailbox_email": "new@example.com",
            "app_password": "bad pw",
        },
        headers=await _tenant_headers(client),
    )

    assert response.status_code == expected_status
    assert response.json()["detail"] in {
        "gmail_app_password_rejected",
        "gmail_connection_unavailable",
    }

    # Existing mailbox unchanged
    db_session.expire_all()
    mailbox = (
        await db_session.execute(
            select(TenantMailbox).where(TenantMailbox.tenant_id == tenant_id)
        )
    ).scalar_one()
    assert decrypt_value(mailbox.app_password_encrypted) == "old-working-password"
    assert mailbox.mailbox_email == "old@example.com"


@pytest.mark.asyncio
async def test_get_mailbox_returns_gmail_shape(
    client, db_session, active_tenant_user
) -> None:
    """GET mailbox response does not include provider/imap_host/imap_port/imap_ssl."""
    tenant_id = (
        await db_session.execute(
            select(Tenant.id).where(Tenant.owner_user_id == active_tenant_user.id)
        )
    ).scalar_one()
    from app.core.encryption import encrypt_value

    mb = TenantMailbox(
        tenant_id=tenant_id,
        mailbox_email="user@gmail.com",
        auth_method="app_password",
        status="connected",
        app_password_encrypted=encrypt_value("secret"),
    )
    db_session.add(mb)
    await db_session.commit()

    response = await client.get(
        "/api/v1/tenant/mailbox/",
        headers=await _tenant_headers(client),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["auth_method"] == "app_password"
    assert body["status"] == "connected"
    assert "provider" not in body
    assert "imap_host" not in body
    assert "imap_port" not in body
    assert "imap_ssl" not in body
