"""MailboxOAuthService — orchestrate Google/Microsoft OAuth flows."""

import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.demo_guardrail import assert_demo_operation_allowed
from app.core.encryption import decrypt_value, encrypt_value
from app.core.metrics import metrics
from app.models import TenantMailbox
from app.repositories import mailbox_config_repository, tenants_repository
from app.schemas.mailbox import OAuthStartResponse

from .google import InvalidGrantError
from .google import build_auth_url as google_auth_url
from .google import exchange_code as google_exchange
from .google import fetch_user_info as google_user_info
from .google import refresh_access_token as google_refresh
from .microsoft import build_auth_url as microsoft_auth_url
from .microsoft import exchange_code as microsoft_exchange
from .microsoft import fetch_user_info as microsoft_user_info
from .microsoft import refresh_access_token as microsoft_refresh

STATE_ALGORITHM = "HS256"
STATE_EXPIRE_MINUTES = 10


def _create_state_token(tenant_id: UUID, provider: str) -> str:
    """Create a signed JWT state token encoding tenant+provider context."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=STATE_EXPIRE_MINUTES)
    payload = {
        "tenant_id": str(tenant_id),
        "provider": provider,
        "nonce": secrets.token_urlsafe(16),
        "exp": expire,
        "type": "oauth_state",
    }
    return jwt.encode(payload, settings.secret_key, algorithm=STATE_ALGORITHM)


def _decode_state_token(state: str) -> dict | None:
    """Decode and validate a state token. Returns payload or ``None``."""
    try:
        payload = jwt.decode(state, settings.secret_key, algorithms=[STATE_ALGORITHM])
        if payload.get("type") != "oauth_state":
            return None
        return payload
    except JWTError:
        return None


class MailboxOAuthService:
    """Orchestrate OAuth flows for tenant mailbox connections."""

    async def start_oauth(
        self,
        db: AsyncSession | None,
        tenant_id: UUID,
        provider: str,
    ) -> OAuthStartResponse | None:
        """Generate OAuth authorization URL for the given provider.

        Returns ``None`` if provider is unsupported.
        """
        state = _create_state_token(tenant_id, provider)

        if provider == "google":
            url = google_auth_url(
                settings.google_oauth_client_id,
                settings.google_oauth_redirect_uri,
                state,
            )
        elif provider == "microsoft":
            url = microsoft_auth_url(
                settings.microsoft_oauth_client_id,
                settings.microsoft_oauth_redirect_uri,
                state,
            )
        else:
            return None

        metrics.inc("oauth_start_total", provider=provider)
        return OAuthStartResponse(auth_url=url, state=state)

    async def complete_oauth(
        self,
        db: AsyncSession,
        provider: str,
        code: str,
        state: str,
    ) -> TenantMailbox:
        """Complete OAuth callback: validate state, exchange code, store tokens."""
        payload = _decode_state_token(state)
        if payload is None:
            raise ValueError("Invalid or expired OAuth state token")

        tenant_id = UUID(payload["tenant_id"])
        state_provider = payload["provider"]
        if state_provider != provider:
            raise ValueError(f"State provider mismatch: {state_provider} != {provider}")

        tenant = await tenants_repository.get(db, tenant_id)
        if tenant is not None:
            assert_demo_operation_allowed(tenant, operation="mailbox_oauth_callback")

        mailbox = await mailbox_config_repository.get_by_tenant(db, tenant_id)

        if provider == "google":
            token_info = await google_exchange(
                settings.google_oauth_client_id,
                settings.google_oauth_client_secret,
                settings.google_oauth_redirect_uri,
                code,
            )
            try:
                user_info = await google_user_info(token_info.access_token)
            except Exception:
                user_info = None
        elif provider == "microsoft":
            token_info = await microsoft_exchange(
                settings.microsoft_oauth_client_id,
                settings.microsoft_oauth_client_secret,
                settings.microsoft_oauth_redirect_uri,
                code,
            )
            try:
                user_info = await microsoft_user_info(token_info.access_token)
            except Exception:
                user_info = None
        else:
            raise ValueError(f"Unsupported OAuth provider: {provider}")

        mailbox_email: str | None = None
        provider_user_id: str | None = None
        if user_info is not None:
            mailbox_email = user_info.email
            provider_user_id = user_info.user_id
        elif mailbox is not None:
            mailbox_email = mailbox.mailbox_email
            provider_user_id = mailbox.oauth_provider_user_id

        if not mailbox_email:
            raise ValueError("OAuth provider did not return mailbox email")
        expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=token_info.expires_in
        )

        if mailbox is None:
            mailbox = TenantMailbox(
                tenant_id=tenant_id,
                mailbox_email=mailbox_email,
                provider=provider,
                auth_method="oauth",
                status="connected",
                oauth_provider_user_id=provider_user_id,
                oauth_provider_email=mailbox_email,
                oauth_access_token_encrypted=encrypt_value(token_info.access_token),
                oauth_refresh_token_encrypted=encrypt_value(token_info.refresh_token),
                oauth_token_expires_at=expires_at,
                oauth_scope=token_info.scope,
                last_connection_error=None,
            )
            await mailbox_config_repository.create(db, tenant_id, mailbox)
        else:
            await mailbox_config_repository.update(
                db,
                mailbox,
                mailbox_email=mailbox_email,
                provider=provider,
                auth_method="oauth",
                status="connected",
                imap_host=None,
                imap_port=None,
                imap_ssl=None,
                imap_password_encrypted=None,
                oauth_provider_user_id=provider_user_id,
                oauth_provider_email=mailbox_email,
                oauth_access_token_encrypted=encrypt_value(token_info.access_token),
                oauth_refresh_token_encrypted=encrypt_value(token_info.refresh_token),
                oauth_token_expires_at=expires_at,
                oauth_scope=token_info.scope,
                last_connection_error=None,
            )

        metrics.inc("oauth_complete_total", provider=provider, status="connected")
        return mailbox

    async def refresh_token(
        self, db: AsyncSession, mailbox: TenantMailbox
    ) -> TenantMailbox:
        """Refresh an OAuth access token.

        On success: updates ``oauth_access_token_encrypted`` and ``expires_at``.
        On ``invalid_grant``: marks mailbox as ``revoked``, clears tokens.

        Returns updated mailbox, or ``None`` if mailbox doesn't use OAuth.
        """
        if mailbox.auth_method != "oauth":
            return mailbox

        refresh_token = decrypt_value(mailbox.oauth_refresh_token_encrypted)
        if not refresh_token:
            await mailbox_config_repository.update_status(
                db, mailbox, "revoked", error="No refresh token available"
            )
            return mailbox

        try:
            if mailbox.provider == "google":
                result = await google_refresh(
                    settings.google_oauth_client_id,
                    settings.google_oauth_client_secret,
                    refresh_token,
                )
            elif mailbox.provider == "microsoft":
                result = await microsoft_refresh(
                    settings.microsoft_oauth_client_id,
                    settings.microsoft_oauth_client_secret,
                    refresh_token,
                )
            else:
                return mailbox
        except InvalidGrantError as exc:
            # Refresh token invalid/revoked → mark mailbox revoked
            await mailbox_config_repository.update(
                db,
                mailbox,
                status="revoked",
                oauth_access_token_encrypted=None,
                oauth_refresh_token_encrypted=None,
                oauth_token_expires_at=None,
                last_connection_error=str(exc),
            )
            metrics.inc(
                "oauth_refresh_total", provider=mailbox.provider, status="revoked"
            )
            return mailbox

        expires_at = datetime.now(timezone.utc) + timedelta(seconds=result.expires_in)
        await mailbox_config_repository.update(
            db,
            mailbox,
            oauth_access_token_encrypted=encrypt_value(result.access_token),
            oauth_token_expires_at=expires_at,
            oauth_scope=result.scope,
            last_connection_error=None,
        )
        metrics.inc("oauth_refresh_total", provider=mailbox.provider, status="ok")
        return mailbox

    async def disconnect(
        self, db: AsyncSession, mailbox: TenantMailbox
    ) -> TenantMailbox:
        """Disconnect mailbox: clear all secrets, reset to disconnected."""
        await mailbox_config_repository.update(
            db,
            mailbox,
            status="disconnected",
            oauth_access_token_encrypted=None,
            oauth_refresh_token_encrypted=None,
            oauth_token_expires_at=None,
            oauth_scope=None,
            oauth_provider_user_id=None,
            oauth_provider_email=None,
            imap_password_encrypted=None,
            last_connection_error=None,
        )
        metrics.inc("oauth_disconnect_total", provider=mailbox.provider)
        return mailbox
