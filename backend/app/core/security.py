"""Security helpers for JWTs, password hashing, and API key validation."""

from datetime import datetime, timedelta, timezone
import secrets

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings

ALGORITHM = "HS256"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode("utf-8"), hashed_password.encode("utf-8")
    )


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def create_access_token(
    subject: str,
    role: str,
    expires_delta: timedelta | None = None,
    active_tenant_id: str | None = None,
) -> str:
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.access_token_expire_minutes)
    expire = datetime.now(timezone.utc) + expires_delta
    payload = {"sub": subject, "role": role, "exp": expire, "type": "access"}
    if active_tenant_id:
        payload["active_tenant_id"] = active_tenant_id
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def create_refresh_token(subject: str, expires_delta: timedelta | None = None) -> str:
    if expires_delta is None:
        expires_delta = timedelta(days=settings.refresh_token_expire_days)
    expire = datetime.now(timezone.utc) + expires_delta
    payload = {
        "sub": subject,
        "exp": expire,
        "type": "refresh",
        "jti": generate_secure_token(),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except JWTError:
        raise ValueError("Invalid token") from None


def generate_secure_token() -> str:
    """Generate a cryptographically secure random token for refresh session storage."""
    return secrets.token_urlsafe(32)


def verify_n8n_api_key(api_key: str) -> bool:
    return api_key == settings.n8n_api_key
