"""Google Gmail OAuth2 helpers — auth URL, token exchange, refresh."""

from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_SCOPES = "https://www.googleapis.com/auth/gmail.readonly openid email profile"


@dataclass
class GoogleTokenResult:
    access_token: str
    refresh_token: str | None
    expires_in: int
    scope: str


def build_auth_url(client_id: str, redirect_uri: str, state: str) -> str:
    """Build Google OAuth authorization URL for Gmail read-only access.

    Uses ``access_type=offline`` and ``prompt=consent`` to ensure a
    refresh token is returned on first authorization.
    """
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": GOOGLE_SCOPES,
        "access_type": "offline",
        "state": state,
        "prompt": "consent",
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


async def exchange_code(
    client_id: str, client_secret: str, redirect_uri: str, code: str
) -> GoogleTokenResult:
    """Exchange authorization code for tokens via Google token endpoint."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
                "code": code,
            },
            headers={"Accept": "application/json"},
        )
        try:
            data = resp.json()
        except ValueError as exc:
            raise OAuthTokenError(f"Invalid token response body: {resp.text}") from exc

    _check_token_error(data)
    resp.raise_for_status()
    return GoogleTokenResult(
        access_token=data["access_token"],
        refresh_token=data.get("refresh_token"),
        expires_in=data.get("expires_in", 3600),
        scope=data.get("scope", ""),
    )


async def refresh_access_token(
    client_id: str, client_secret: str, refresh_token: str
) -> GoogleTokenResult:
    """Refresh an expired access token using the refresh token.

    Raises ``InvalidGrantError`` when the refresh token is invalid/revoked.
    """
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
            headers={"Accept": "application/json"},
        )
        try:
            data = resp.json()
        except ValueError as exc:
            raise OAuthTokenError(f"Invalid token response body: {resp.text}") from exc

    _check_token_error(data)
    resp.raise_for_status()

    return GoogleTokenResult(
        access_token=data["access_token"],
        refresh_token=data.get("refresh_token"),
        expires_in=data.get("expires_in", 3600),
        scope=data.get("scope", ""),
    )


def _check_token_error(data: dict) -> None:
    """Raise domain-specific exceptions for token endpoint errors."""
    error = data.get("error")
    if error is None:
        return
    desc = data.get("error_description", error)
    if error == "invalid_grant":
        raise InvalidGrantError(desc)
    raise OAuthTokenError(desc)


class InvalidGrantError(Exception):
    """Refresh token is invalid, revoked, or expired.

    Callers should mark the associated mailbox as ``revoked``.
    """


class OAuthTokenError(Exception):
    """Transient or provider-level token error (not invalid_grant)."""
