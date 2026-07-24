"""Random object-key generation free of account/tenant/user PII."""

from __future__ import annotations

import secrets


def generate_random_export_key() -> str:
    """Generate a random S3-compatible object key with prefix.

    The key is a UUID-like hex string under ``exports/`` and contains no
    account name, Tenant ID, username, actor ID, or any other PII.
    """
    raw = secrets.token_hex(32)  # 64 hex chars
    return f"exports/{raw[:8]}/{raw[8:24]}/{raw[24:]}"


__all__ = [
    "generate_random_export_key",
]
