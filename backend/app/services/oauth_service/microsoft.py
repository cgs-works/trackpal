"""Microsoft Graph OAuth2 helpers — auth URL, token exchange, refresh."""

from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

from app.core.config import settings
from app.services.oauth_service.google import InvalidGrantError, OAuthTokenError

MICROSOFT_AUTHORITY = "https://login.microsoftonline.com"
MICROSOFT_TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
MICROSOFT_AUTH_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
MICROSOFT_SCOPES = "Mail.Read offline_access openid profile email"


@dataclass
class MicrosoftTokenResult:
    access_token: str
    refresh_token: str | None
    expires_in: int
    scope: str


def _authority(tenant_id: str | None = None) -> str:
    """Build Microsoft authority URL from tenant ID (default: ``consumers``)."""
    tid = tenant_id or settings.microsoft_oauth_tenant_id
    return f"{MICROSOFT_AUTHORITY}/{tid}"


def build_auth_url(
    client_id: str,
    redirect_uri: str,
    state: str,
    tenant_id: str | None = None,
) -> str:
    """Build Microsoft OAuth authorization URL for Mail.Read delegated access."""
    authority = _authority(tenant_id)
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": MICROSOFT_SCOPES,
        "state": state,
        "response_mode": "query",
    }
    return f"{authority}/oauth2/v2.0/authorize?{urlencode(params)}"


async def exchange_code(
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    code: str,
    tenant_id: str | None = None,
) -> MicrosoftTokenResult:
    """Exchange authorization code for tokens via Microsoft identity platform."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            MICROSOFT_TOKEN_URL,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
                "code": code,
            },
            headers={"Accept": "application/json"},
        )
        data = resp.json()

    _check_token_error(data)
    resp.raise_for_status()
    return MicrosoftTokenResult(
        access_token=data["access_token"],
        refresh_token=data.get("refresh_token"),
        expires_in=data.get("expires_in", 3600),
        scope=data.get("scope", ""),
    )


async def refresh_access_token(
    client_id: str,
    client_secret: str,
    refresh_token: str,
    tenant_id: str | None = None,
) -> MicrosoftTokenResult:
    """Refresh an expired Microsoft access token.

    Raises ``InvalidGrantError`` when the refresh token is invalid/revoked.
    """
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            MICROSOFT_TOKEN_URL,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
            headers={"Accept": "application/json"},
        )
        data = resp.json()

    _check_token_error(data)
    resp.raise_for_status()
    return MicrosoftTokenResult(
        access_token=data["access_token"],
        refresh_token=data.get("refresh_token"),
        expires_in=data.get("expires_in", 3600),
        scope=data.get("scope", ""),
    )


def _check_token_error(data: dict) -> None:
    """Raise domain exceptions for Microsoft token endpoint errors."""
    error = data.get("error")
    if error is None:
        return
    desc = data.get("error_description", error)
    if error == "invalid_grant":
        raise InvalidGrantError(desc)
    raise OAuthTokenError(desc)
