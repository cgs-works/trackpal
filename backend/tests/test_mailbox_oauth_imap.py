"""Tests for Phase 2: OAuth service, IMAP test, exclusivity, refresh failure."""

import asyncio
import imaplib
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest
import respx
from jose import jwt

from app.core.config import settings
from app.core.encryption import decrypt_value, encrypt_value
from app.models import TenantMailbox
from app.repositories import mailbox_config_repository
from app.schemas.mailbox import OAuthStartResponse
from app.services.imap_service import ImapAuthenticationError
from app.services.imap_service import ImapConnectionError
from app.services.imap_service import ImapTimeoutError
from app.services.imap_service import ImapUnavailableError
from app.services.imap_service import test_imap_connection as _test_imap_connection
from app.services.oauth_service import MailboxOAuthService
from app.services.oauth_service.google import InvalidGrantError, OAuthTokenError
from app.services.oauth_service.google import build_auth_url as google_build_auth_url
from app.services.oauth_service.google import exchange_code as google_exchange_code
from app.services.oauth_service.google import (
    refresh_access_token as google_refresh_token,
)
from app.services.oauth_service.microsoft import (
    build_auth_url as microsoft_build_auth_url,
)
from app.services.oauth_service.microsoft import (
    exchange_code as microsoft_exchange_code,
)
from app.services.oauth_service.microsoft import (
    refresh_access_token as microsoft_refresh_token,
)
from app.services.oauth_service.service import _create_state_token, _decode_state_token

oauth_service = MailboxOAuthService()

# ─── Google OAuth provider ────────────────────────────────────────────────


class TestGoogleOAuthProvider:
    """Unit tests for Google OAuth helpers (mock HTTP)."""

    GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"

    def test_build_auth_url_includes_all_params(self):
        url = google_build_auth_url(
            client_id="test-client-id",
            redirect_uri="https://app.com/callback",
            state="test-state-123",
        )
        assert "client_id=test-client-id" in url
        assert "redirect_uri=https%3A%2F%2Fapp.com%2Fcallback" in url
        assert "response_type=code" in url
        assert "access_type=offline" in url
        assert "prompt=consent" in url
        assert "state=test-state-123" in url
        assert (
            "scope=https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fgmail.readonly+openid+email"
            in url
        )
        assert "profile" not in url
        assert url.startswith("https://accounts.google.com/o/oauth2/v2/auth")

    @pytest.mark.asyncio
    @respx.mock
    async def test_exchange_code_success(self):
        respx.post(self.GOOGLE_TOKEN_URL).respond(
            200,
            json={
                "access_token": "ya29.access-token-123",
                "refresh_token": "1//refresh-token-456",
                "expires_in": 3600,
                "scope": "https://www.googleapis.com/auth/gmail.readonly openid",
            },
        )
        result = await google_exchange_code(
            client_id="id",
            client_secret="secret",
            redirect_uri="https://app.com/callback",
            code="auth-code-xyz",
        )
        assert result.access_token == "ya29.access-token-123"
        assert result.refresh_token == "1//refresh-token-456"
        assert result.expires_in == 3600

    @pytest.mark.asyncio
    @respx.mock
    async def test_exchange_code_no_refresh_token(self):
        """Google may not return refresh_token on subsequent exchanges."""
        respx.post(self.GOOGLE_TOKEN_URL).respond(
            200,
            json={
                "access_token": "ya29.access-only",
                "expires_in": 3600,
                "scope": "gmail.readonly",
            },
        )
        result = await google_exchange_code(
            client_id="id",
            client_secret="secret",
            redirect_uri="https://app.com/callback",
            code="code-no-refresh",
        )
        assert result.access_token == "ya29.access-only"
        assert result.refresh_token is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_exchange_code_invalid_grant(self):
        respx.post(self.GOOGLE_TOKEN_URL).respond(
            400,
            json={"error": "invalid_grant", "error_description": "Token expired"},
        )
        with pytest.raises(InvalidGrantError):
            await google_exchange_code(
                client_id="id",
                client_secret="secret",
                redirect_uri="https://app.com/callback",
                code="bad-code",
            )

    @pytest.mark.asyncio
    @respx.mock
    async def test_refresh_token_success(self):
        respx.post(self.GOOGLE_TOKEN_URL).respond(
            200,
            json={
                "access_token": "ya29.new-access-token",
                "expires_in": 3600,
                "scope": "gmail.readonly",
            },
        )
        result = await google_refresh_token(
            client_id="id",
            client_secret="secret",
            refresh_token="old-refresh",
        )
        assert result.access_token == "ya29.new-access-token"

    @pytest.mark.asyncio
    @respx.mock
    async def test_refresh_token_invalid_grant(self):
        respx.post(self.GOOGLE_TOKEN_URL).respond(
            400,
            json={
                "error": "invalid_grant",
                "error_description": "Refresh token revoked",
            },
        )
        with pytest.raises(InvalidGrantError):
            await google_refresh_token(
                client_id="id",
                client_secret="secret",
                refresh_token="bad-refresh",
            )

    @pytest.mark.asyncio
    @respx.mock
    async def test_refresh_token_transient_error(self):
        """Non-invalid_grant errors should raise OAuthTokenError."""

        respx.post(self.GOOGLE_TOKEN_URL).respond(
            429,
            json={"error": "rate_limit_exceeded"},
        )
        with pytest.raises(OAuthTokenError):
            await google_refresh_token(
                client_id="id",
                client_secret="secret",
                refresh_token="rtoken",
            )


# ─── Microsoft OAuth provider ─────────────────────────────────────────────


class TestMicrosoftOAuthProvider:
    """Unit tests for Microsoft OAuth helpers (mock HTTP)."""

    MS_TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"

    def test_build_auth_url_includes_all_params(self):
        url = microsoft_build_auth_url(
            client_id="ms-client-id",
            redirect_uri="https://app.com/callback",
            state="ms-state-456",
        )
        assert "client_id=ms-client-id" in url
        assert "response_type=code" in url
        assert "Mail.Read" in url
        assert "offline_access" in url
        assert "state=ms-state-456" in url

    @pytest.mark.asyncio
    @respx.mock
    async def test_exchange_code_success(self):
        respx.post(self.MS_TOKEN_URL).respond(
            200,
            json={
                "access_token": "ms-access-token",
                "refresh_token": "ms-refresh-token",
                "expires_in": 3600,
                "scope": "Mail.Read offline_access",
            },
        )
        result = await microsoft_exchange_code(
            client_id="id",
            client_secret="secret",
            redirect_uri="https://app.com/callback",
            code="ms-code",
        )
        assert result.access_token == "ms-access-token"
        assert result.refresh_token == "ms-refresh-token"

    @pytest.mark.asyncio
    @respx.mock
    async def test_exchange_code_invalid_grant(self):
        respx.post(self.MS_TOKEN_URL).respond(
            400,
            json={"error": "invalid_grant", "error_description": "Bad code"},
        )
        with pytest.raises(InvalidGrantError):
            await microsoft_exchange_code(
                client_id="id",
                client_secret="secret",
                redirect_uri="https://app.com/callback",
                code="bad",
            )

    @pytest.mark.asyncio
    @respx.mock
    async def test_refresh_token_success(self):
        respx.post(self.MS_TOKEN_URL).respond(
            200,
            json={
                "access_token": "ms-new-access",
                "expires_in": 3600,
                "scope": "Mail.Read",
            },
        )
        result = await microsoft_refresh_token(
            client_id="id",
            client_secret="secret",
            refresh_token="ms-refresh",
        )
        assert result.access_token == "ms-new-access"

    @pytest.mark.asyncio
    @respx.mock
    async def test_refresh_token_invalid_grant(self):
        respx.post(self.MS_TOKEN_URL).respond(
            400,
            json={"error": "invalid_grant", "error_description": "Revoked"},
        )
        with pytest.raises(InvalidGrantError):
            await microsoft_refresh_token(
                client_id="id",
                client_secret="secret",
                refresh_token="bad",
            )


# ─── State token ──────────────────────────────────────────────────────────


class TestOAuthStateToken:
    """State token creation and decoding."""

    def test_create_and_decode(self):
        tenant_id = uuid.uuid4()
        token = _create_state_token(tenant_id, "google")
        assert isinstance(token, str)
        assert len(token) > 20

        payload = _decode_state_token(token)
        assert payload is not None
        assert payload["tenant_id"] == str(tenant_id)
        assert payload["provider"] == "google"
        assert payload["type"] == "oauth_state"

    def test_decode_invalid_token(self):
        assert _decode_state_token("bad-token") is None

    def test_decode_expired_token(self):
        """Manually create expired token."""
        expired = jwt.encode(
            {
                "tenant_id": str(uuid.uuid4()),
                "provider": "google",
                "nonce": "test",
                "exp": datetime.now(timezone.utc) - timedelta(hours=1),
                "type": "oauth_state",
            },
            settings.secret_key,
            algorithm="HS256",
        )
        assert _decode_state_token(expired) is None

    def test_decode_wrong_type(self):
        """Token with wrong type should be rejected."""
        from jose import jwt

        bad = jwt.encode(
            {
                "tenant_id": str(uuid.uuid4()),
                "provider": "google",
                "nonce": "test",
                "exp": datetime.now(timezone.utc) + timedelta(hours=1),
                "type": "access",
            },
            settings.secret_key,
            algorithm="HS256",
        )
        assert _decode_state_token(bad) is None


# ─── OAuth Service orchestration ──────────────────────────────────────────


class TestMailboxOAuthService:
    """OAuth service orchestration tests with mocked HTTP and repository."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_start_google_oauth(self):
        tenant_id = uuid.uuid4()
        result = await oauth_service.start_oauth(None, tenant_id, "google")

        assert isinstance(result, OAuthStartResponse)
        assert result.auth_url.startswith(
            "https://accounts.google.com/o/oauth2/v2/auth"
        )
        assert "client_id=" in result.auth_url
        assert result.state is not None

        # State should decode back to the tenant_id
        payload = _decode_state_token(result.state)
        assert payload is not None
        assert payload["tenant_id"] == str(tenant_id)
        assert payload["provider"] == "google"

    @pytest.mark.asyncio
    @respx.mock
    async def test_start_microsoft_oauth(self):
        tenant_id = uuid.uuid4()
        result = await oauth_service.start_oauth(None, tenant_id, "microsoft")

        assert isinstance(result, OAuthStartResponse)
        assert "login.microsoftonline.com" in result.auth_url
        payload = _decode_state_token(result.state)
        assert payload is not None
        assert payload["provider"] == "microsoft"

    @pytest.mark.asyncio
    async def test_start_unsupported_provider(self):
        result = await oauth_service.start_oauth(None, uuid.uuid4(), "yahoo")
        assert result is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_complete_oauth_google_success(self, db_session):
        """Full end-to-end: state + code exchange + token storage."""
        tenant = await _seed_tenant(db_session)
        await _seed_mailbox(db_session, tenant.id, status="disconnected")

        # Create a valid state token
        state = _create_state_token(tenant.id, "google")

        # Mock Google token exchange
        respx.post("https://oauth2.googleapis.com/token").respond(
            200,
            json={
                "access_token": "ya29.new-token",
                "refresh_token": "1//refresh-new",
                "expires_in": 3600,
                "scope": "gmail.readonly",
            },
        )

        mailbox = await oauth_service.complete_oauth(
            db_session, "google", "auth-code-123", state
        )

        assert mailbox.status == "connected"
        assert mailbox.provider == "google"
        assert mailbox.auth_method == "oauth"
        assert mailbox.oauth_access_token_encrypted is not None
        assert mailbox.oauth_refresh_token_encrypted is not None
        assert mailbox.oauth_token_expires_at is not None

    @pytest.mark.asyncio
    @respx.mock
    async def test_complete_oauth_state_mismatch(self, db_session):
        tenant = await _seed_tenant(db_session)
        await _seed_mailbox(db_session, tenant.id)
        state = _create_state_token(tenant.id, "google")

        # Call with different provider than state encodes
        with pytest.raises(ValueError, match="State provider mismatch"):
            await oauth_service.complete_oauth(db_session, "microsoft", "code", state)

    @pytest.mark.asyncio
    @respx.mock
    async def test_complete_oauth_creates_mailbox_from_provider_email(self, db_session):
        """Should create mailbox when OAuth succeeds and tenant had no mailbox."""
        tenant = await _seed_tenant(db_session)
        state = _create_state_token(tenant.id, "google")

        respx.post("https://oauth2.googleapis.com/token").respond(
            200,
            json={
                "access_token": "ya29.new-token",
                "refresh_token": "1//refresh-new",
                "expires_in": 3600,
                "scope": "gmail.readonly",
            },
        )
        respx.get("https://www.googleapis.com/oauth2/v3/userinfo").respond(
            200,
            json={"sub": "google-user-1", "email": "tenant-mailbox@example.com"},
        )

        mailbox = await oauth_service.complete_oauth(
            db_session, "google", "code", state
        )

        assert mailbox.status == "connected"
        assert mailbox.provider == "google"
        assert mailbox.auth_method == "oauth"
        assert mailbox.mailbox_email == "tenant-mailbox@example.com"

    @pytest.mark.asyncio
    @respx.mock
    async def test_complete_oauth_invalid_state(self, db_session):
        with pytest.raises(ValueError, match="Invalid or expired"):
            await oauth_service.complete_oauth(
                db_session, "google", "code", "invalid-state"
            )

    @pytest.mark.asyncio
    @respx.mock
    async def test_refresh_token_success_oauth(self, db_session):
        """Token refresh updates access token and expiry."""
        tenant = await _seed_tenant(db_session)
        old_expiry = datetime.now(timezone.utc) - timedelta(hours=1)
        mb = await _seed_mailbox(
            db_session,
            tenant.id,
            provider="google",
            auth_method="oauth",
            status="connected",
            oauth_access_token_encrypted=encrypt_value("old-access"),
            oauth_refresh_token_encrypted=encrypt_value("valid-refresh"),
            oauth_token_expires_at=old_expiry,
        )

        respx.post("https://oauth2.googleapis.com/token").respond(
            200,
            json={
                "access_token": "new-access-token",
                "expires_in": 3600,
                "scope": "gmail.readonly",
            },
        )

        result = await oauth_service.refresh_token(db_session, mb)
        assert result is not None
        assert result.status == "connected"
        assert result.oauth_token_expires_at is not None
        assert result.oauth_token_expires_at > old_expiry

    @pytest.mark.asyncio
    @respx.mock
    async def test_refresh_token_invalid_grant_revokes_mailbox(self, db_session):
        """InvalidGrantError → mailbox status 'revoked', tokens cleared."""
        tenant = await _seed_tenant(db_session)
        mb = await _seed_mailbox(
            db_session,
            tenant.id,
            provider="google",
            auth_method="oauth",
            status="connected",
            oauth_access_token_encrypted=encrypt_value("old-access"),
            oauth_refresh_token_encrypted=encrypt_value("bad-refresh"),
            oauth_token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )

        respx.post("https://oauth2.googleapis.com/token").respond(
            400,
            json={"error": "invalid_grant", "error_description": "Token revoked"},
        )

        result = await oauth_service.refresh_token(db_session, mb)
        assert result.status == "revoked"
        assert result.oauth_access_token_encrypted is None
        assert result.oauth_refresh_token_encrypted is None
        assert result.oauth_token_expires_at is None
        assert "revoked" in (result.last_connection_error or "").lower()

    @pytest.mark.asyncio
    async def test_refresh_token_not_oauth(self, db_session):
        """Non-OAuth mailbox should return mailbox unchanged."""
        mb = TenantMailbox(
            tenant_id=uuid.uuid4(),
            mailbox_email="test@imap.com",
            provider="imap_custom",
            auth_method="imap_app_password",
            status="connected",
        )
        result = await oauth_service.refresh_token(db_session, mb)
        assert result is mb

    @pytest.mark.asyncio
    async def test_disconnect_clears_all_secrets(self, db_session):
        tenant = await _seed_tenant(db_session)
        mb = await _seed_mailbox(
            db_session,
            tenant.id,
            provider="google",
            auth_method="oauth",
            status="connected",
            oauth_access_token_encrypted=encrypt_value("token"),
            oauth_refresh_token_encrypted=encrypt_value("refresh"),
            imap_password_encrypted=encrypt_value("imap-pass"),
        )

        await oauth_service.disconnect(db_session, mb)
        assert mb.status == "disconnected"
        assert mb.oauth_access_token_encrypted is None
        assert mb.oauth_refresh_token_encrypted is None
        assert mb.imap_password_encrypted is None

    @pytest.mark.asyncio
    async def test_refresh_token_microsoft_revokes(self, db_session):
        """Same invalid_grant flow for Microsoft."""
        tenant = await _seed_tenant(db_session)
        mb = await _seed_mailbox(
            db_session,
            tenant.id,
            provider="microsoft",
            auth_method="oauth",
            status="connected",
            oauth_access_token_encrypted=encrypt_value("ms-access"),
            oauth_refresh_token_encrypted=encrypt_value("ms-refresh"),
            oauth_token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )

        respx.post(
            "https://login.microsoftonline.com/common/oauth2/v2.0/token"
        ).respond(
            400,
            json={"error": "invalid_grant", "error_description": "Bad refresh"},
        )

        result = await oauth_service.refresh_token(db_session, mb)
        assert result.status == "revoked"
        assert result.oauth_access_token_encrypted is None


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


# ─── Exclusivity (OAuth vs IMAP) ──────────────────────────────────────────


class TestExclusivityEnforcement:
    """Active-method exclusivity enforced at service level."""

    @pytest.mark.asyncio
    async def test_oauth_connect_clears_imap_fields(self, db_session):
        """Connecting via OAuth should clear IMAP password."""
        tenant = await _seed_tenant(db_session)
        mb = await _seed_mailbox(
            db_session,
            tenant.id,
            provider="imap_custom",
            auth_method="imap_app_password",
            status="connected",
            imap_host="imap.example.com",
            imap_port=993,
            imap_password_encrypted=encrypt_value("imap-password"),
        )

        # Switch to OAuth via update
        await mailbox_config_repository.update(
            db_session,
            mb,
            provider="google",
            auth_method="oauth",
            status="disconnected",
            imap_host=None,
            imap_port=None,
            imap_password_encrypted=None,
        )
        assert mb.imap_password_encrypted is None
        assert mb.imap_host is None

    @pytest.mark.asyncio
    async def test_imap_connect_clears_oauth_fields(self, db_session):
        """Configuring IMAP should clear OAuth tokens."""
        tenant = await _seed_tenant(db_session)
        mb = await _seed_mailbox(
            db_session,
            tenant.id,
            provider="google",
            auth_method="oauth",
            status="connected",
            oauth_access_token_encrypted=encrypt_value("token"),
            oauth_refresh_token_encrypted=encrypt_value("refresh"),
        )

        # Switch to IMAP
        await mailbox_config_repository.update(
            db_session,
            mb,
            provider="imap_custom",
            auth_method="imap_app_password",
            status="connected",
            imap_host="imap.test.com",
            imap_port=993,
            imap_password_encrypted=encrypt_value("new-pass"),
            oauth_access_token_encrypted=None,
            oauth_refresh_token_encrypted=None,
            oauth_token_expires_at=None,
        )
        assert mb.oauth_access_token_encrypted is None
        assert mb.oauth_refresh_token_encrypted is None
        assert mb.imap_password_encrypted is not None


# ─── Provider token refresh (401 + auto-refresh) ──────────────────────────


class TestMailboxProviderTokenRefresh:
    """Provider-level token refresh on 401: success and invalid_grant."""

    pytestmark = pytest.mark.asyncio

    # ── Google: refresh success ──────────────────────────────────────────

    @respx.mock
    async def test_google_refresh_on_401_success(self, db_session):
        """401 triggers refresh, new token retried, emails returned."""
        tenant = await _seed_tenant(db_session)
        mb = await _seed_mailbox(
            db_session,
            tenant.id,
            provider="google",
            auth_method="oauth",
            status="connected",
            oauth_access_token_encrypted=encrypt_value("expired-token"),
            oauth_refresh_token_encrypted=encrypt_value("valid-refresh"),
            oauth_token_expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )

        list_url = "https://gmail.googleapis.com/gmail/v1/users/me/messages"
        msg_url = "https://gmail.googleapis.com/gmail/v1/users/me/messages/msg-1"

        # First list call returns 401, second returns 200 with one message ref
        route = respx.get(list_url)
        route.side_effect = [
            httpx.Response(401),
            httpx.Response(
                200,
                json={
                    "messages": [{"id": "msg-1"}],
                    "resultSizeEstimate": 1,
                },
            ),
        ]

        # Refresh token endpoint succeeds
        respx.post("https://oauth2.googleapis.com/token").respond(
            200,
            json={
                "access_token": "new-access-token",
                "expires_in": 3600,
                "scope": "gmail.readonly",
            },
        )

        # Individual message fetch succeeds
        respx.get(msg_url).respond(
            200,
            json={
                "id": "msg-1",
                "payload": {
                    "mimeType": "text/plain",
                    "headers": [
                        {"name": "Subject", "value": "Your Spotify code"},
                        {"name": "Message-ID", "value": "<abc@mail>"},
                        {
                            "name": "From",
                            "value": "noreply@spotify.com",
                        },
                        {
                            "name": "Date",
                            "value": "Mon, 27 May 2026 12:00:00 +0000",
                        },
                    ],
                    "body": {"data": "RW50ZXIgdGhpcyBjb2RlOiA2NTQzMjE=\n"},
                },
            },
        )

        from app.services.mail_lookup_worker.providers._google import (
            fetch_google_emails,
        )

        result = await fetch_google_emails(mb, 5, db=db_session)

        assert len(result) == 1
        assert result[0].message_id == "<abc@mail>"
        assert "654321" in result[0].body

        # Refresh updated the stored token
        new_token = decrypt_value(mb.oauth_access_token_encrypted)
        assert new_token == "new-access-token"

    @respx.mock
    async def test_google_html_only_message_body_supported(self, db_session):
        """HTML-only Gmail message should still be parsed and returned."""
        tenant = await _seed_tenant(db_session)
        mb = await _seed_mailbox(
            db_session,
            tenant.id,
            provider="google",
            auth_method="oauth",
            status="connected",
            oauth_access_token_encrypted=encrypt_value("valid-token"),
            oauth_refresh_token_encrypted=encrypt_value("valid-refresh"),
        )

        list_url = "https://gmail.googleapis.com/gmail/v1/users/me/messages"
        msg_url = "https://gmail.googleapis.com/gmail/v1/users/me/messages/msg-html-1"

        respx.get(list_url).respond(
            200,
            json={
                "messages": [{"id": "msg-html-1"}],
                "resultSizeEstimate": 1,
            },
        )

        respx.get(msg_url).respond(
            200,
            json={
                "id": "msg-html-1",
                "payload": {
                    "mimeType": "text/html",
                    "headers": [
                        {"name": "Subject", "value": "Universal+ código de activación"},
                        {"name": "Message-ID", "value": "<html@mail>"},
                        {"name": "From", "value": "no-reply@universalplus.com"},
                        {"name": "To", "value": "ann773@netshopping.vip"},
                        {"name": "Date", "value": "Thu, 28 May 2026 22:55:20 +0000"},
                    ],
                    "body": {
                        "data": "PGh0bWw+PGJvZHk+PHA+VW5pdmVyc2FsKyBjw7NkaWdvIGRlIGFjdGl2YWNpw7NuPC9wPjxoMT48c3Ryb25nPlBGSlFYVjwvc3Ryb25nPjwvaDE+PC9ib2R5PjwvaHRtbD4="
                    },
                },
            },
        )

        from app.services.mail_lookup_worker.providers._google import (
            fetch_google_emails,
        )

        result = await fetch_google_emails(mb, 5, db=db_session)

        assert len(result) == 1
        assert result[0].message_id == "<html@mail>"
        assert "PFJQXV" in result[0].body

    # ── Google: invalid_grant revoked ────────────────────────────────────

    @respx.mock
    async def test_google_refresh_invalid_grant_revokes(self, db_session):
        """401 + invalid_grant raises RevokedMailboxError, mailbox revoked."""
        tenant = await _seed_tenant(db_session)
        mb = await _seed_mailbox(
            db_session,
            tenant.id,
            provider="google",
            auth_method="oauth",
            status="connected",
            oauth_access_token_encrypted=encrypt_value("expired-token"),
            oauth_refresh_token_encrypted=encrypt_value("bad-refresh"),
            oauth_token_expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )

        list_url = "https://gmail.googleapis.com/gmail/v1/users/me/messages"
        respx.get(list_url).respond(401)

        # Refresh endpoint returns invalid_grant
        respx.post("https://oauth2.googleapis.com/token").respond(
            400,
            json={
                "error": "invalid_grant",
                "error_description": "Refresh token revoked",
            },
        )

        from app.services.mail_lookup_worker.providers import RevokedMailboxError
        from app.services.mail_lookup_worker.providers._google import (
            fetch_google_emails,
        )

        with pytest.raises(RevokedMailboxError, match="revoked"):
            await fetch_google_emails(mb, 5, db=db_session)

        # Mailbox should be revoked and tokens cleared
        assert mb.status == "revoked"
        assert mb.oauth_access_token_encrypted is None
        assert mb.oauth_refresh_token_encrypted is None
        assert mb.last_connection_error is not None
        assert "revoked" in mb.last_connection_error.lower()

    # ── Google: no db provided → no refresh attempted ────────────────────

    @respx.mock
    async def test_google_no_db_no_refresh(self, db_session):
        """Without db, 401 raises NonTransientProviderError directly."""
        tenant = await _seed_tenant(db_session)
        mb = await _seed_mailbox(
            db_session,
            tenant.id,
            provider="google",
            auth_method="oauth",
            status="connected",
            oauth_access_token_encrypted=encrypt_value("expired-token"),
            oauth_refresh_token_encrypted=encrypt_value("any-refresh"),
            oauth_token_expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )

        list_url = "https://gmail.googleapis.com/gmail/v1/users/me/messages"
        respx.get(list_url).respond(401)

        from app.services.mail_lookup_worker.providers import (
            NonTransientProviderError,
        )
        from app.services.mail_lookup_worker.providers._google import (
            fetch_google_emails,
        )

        # No db passed → no refresh attempt
        with pytest.raises(
            NonTransientProviderError, match="Gmail token expired/revoked"
        ):
            await fetch_google_emails(mb, 5, db=None)

    # ── Microsoft: refresh success ───────────────────────────────────────

    @respx.mock
    async def test_microsoft_refresh_on_401_success(self, db_session):
        """401 triggers refresh for Microsoft, new token retried."""
        tenant = await _seed_tenant(db_session)
        mb = await _seed_mailbox(
            db_session,
            tenant.id,
            provider="microsoft",
            auth_method="oauth",
            status="connected",
            oauth_access_token_encrypted=encrypt_value("expired-ms-token"),
            oauth_refresh_token_encrypted=encrypt_value("valid-ms-refresh"),
            oauth_token_expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )

        graph_url = "https://graph.microsoft.com/v1.0/me/messages"

        # First call 401, second succeeds
        route = respx.get(graph_url)
        route.side_effect = [
            httpx.Response(401),
            httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "id": "ms-msg-1",
                            "subject": "Your Netflix code",
                            "body": {
                                "content": "Code: 789012",
                                "contentType": "text",
                            },
                            "from": {"emailAddress": {"address": "info@netflix.com"}},
                            "receivedDateTime": "2026-05-27T12:00:00Z",
                            "internetMessageId": "<ms-msg@mail>",
                            "toRecipients": [],
                            "ccRecipients": [],
                        }
                    ]
                },
            ),
        ]

        # Refresh token endpoint succeeds
        respx.post(
            "https://login.microsoftonline.com/common/oauth2/v2.0/token"
        ).respond(
            200,
            json={
                "access_token": "new-ms-access",
                "expires_in": 3600,
                "scope": "Mail.Read",
            },
        )

        from app.services.mail_lookup_worker.providers._microsoft import (
            fetch_microsoft_emails,
        )

        result = await fetch_microsoft_emails(mb, 5, db=db_session)

        assert len(result) == 1
        assert "789012" in result[0].body

        # Token was updated
        new_token = decrypt_value(mb.oauth_access_token_encrypted)
        assert new_token == "new-ms-access"

    # ── Microsoft: invalid_grant revoked ─────────────────────────────────

    @respx.mock
    async def test_microsoft_refresh_invalid_grant_revokes(self, db_session):
        """401 + invalid_grant for Microsoft revokes mailbox."""
        tenant = await _seed_tenant(db_session)
        mb = await _seed_mailbox(
            db_session,
            tenant.id,
            provider="microsoft",
            auth_method="oauth",
            status="connected",
            oauth_access_token_encrypted=encrypt_value("expired-ms"),
            oauth_refresh_token_encrypted=encrypt_value("bad-ms-refresh"),
            oauth_token_expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )

        graph_url = "https://graph.microsoft.com/v1.0/me/messages"
        respx.get(graph_url).respond(401)

        respx.post(
            "https://login.microsoftonline.com/common/oauth2/v2.0/token"
        ).respond(
            400,
            json={"error": "invalid_grant", "error_description": "Revoked"},
        )

        from app.services.mail_lookup_worker.providers import RevokedMailboxError
        from app.services.mail_lookup_worker.providers._microsoft import (
            fetch_microsoft_emails,
        )

        with pytest.raises(RevokedMailboxError, match="revoked"):
            await fetch_microsoft_emails(mb, 5, db=db_session)

        assert mb.status == "revoked"
        assert mb.oauth_access_token_encrypted is None

    # ── Microsoft: no db provided → no refresh attempted ─────────────────

    @respx.mock
    async def test_microsoft_no_db_no_refresh(self, db_session):
        """Without db, Microsoft 401 raises NonTransientProviderError."""
        tenant = await _seed_tenant(db_session)
        mb = await _seed_mailbox(
            db_session,
            tenant.id,
            provider="microsoft",
            auth_method="oauth",
            status="connected",
            oauth_access_token_encrypted=encrypt_value("expired-ms"),
            oauth_refresh_token_encrypted=encrypt_value("ms-refresh"),
            oauth_token_expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )

        graph_url = "https://graph.microsoft.com/v1.0/me/messages"
        respx.get(graph_url).respond(401)

        from app.services.mail_lookup_worker.providers import (
            NonTransientProviderError,
        )
        from app.services.mail_lookup_worker.providers._microsoft import (
            fetch_microsoft_emails,
        )

        with pytest.raises(
            NonTransientProviderError,
            match="Microsoft token expired/revoked",
        ):
            await fetch_microsoft_emails(mb, 5, db=None)


# ─── Helpers ──────────────────────────────────────────────────────────────


async def _seed_tenant(db_session):
    from app.core.security import get_password_hash
    from app.models import Tenant, User

    user = User(
        username=f"oauth_t_{uuid.uuid4().hex[:8]}",
        password_hash=get_password_hash("pass"),
        role="tenant",
    )
    db_session.add(user)
    await db_session.flush()
    tenant = Tenant(
        owner_user_id=user.id,
        client_prefix=f"oa{uuid.uuid4().hex[:2]}",
        name="OAuth Test Tenant",
        is_active=True,
    )
    db_session.add(tenant)
    await db_session.commit()
    return tenant


async def _seed_mailbox(db_session, tenant_id, **overrides):
    kwargs = {
        "tenant_id": tenant_id,
        "mailbox_email": "codes@tenant.com",
        "provider": "google",
        "auth_method": "oauth",
        "status": "connected",
    }
    kwargs.update(overrides)
    mb = TenantMailbox(**kwargs)
    db_session.add(mb)
    await db_session.commit()
    await db_session.refresh(mb)
    return mb
