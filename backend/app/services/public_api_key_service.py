from __future__ import annotations

import secrets
from urllib.parse import urlparse
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import restore_rls_context
from app.models import TenantApiKey
from app.repositories import tenant_api_keys_repository

_ALLOWED_SCHEMES = {"http", "https"}


def _new_api_key() -> str:
    return f"tpk_{secrets.token_urlsafe(32)}"


def validate_allowed_origin(origin: str) -> str:
    item = origin.strip()
    parsed = urlparse(item)
    if (
        not item
        or "*" in item
        or parsed.scheme not in _ALLOWED_SCHEMES
        or not parsed.netloc
        or parsed.path
        or parsed.params
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Allowed origin must be an exact http(s) origin such as https://example.com")
    return f"{parsed.scheme}://{parsed.netloc}"


def normalize_allowed_origins(origins: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for origin in origins:
        normalized = validate_allowed_origin(origin)
        if normalized not in seen:
            cleaned.append(normalized)
            seen.add(normalized)
    return cleaned


class PublicApiKeyService:
    async def get_config(self, db: AsyncSession, tenant_id: UUID) -> TenantApiKey | None:
        return await tenant_api_keys_repository.get_by_tenant_id(db, tenant_id)

    async def upsert_origins(
        self,
        db: AsyncSession,
        tenant_id: UUID,
        origins: list[str],
    ) -> TenantApiKey:
        allowed_origins = normalize_allowed_origins(origins)
        row = await tenant_api_keys_repository.get_by_tenant_id(db, tenant_id)
        if row is None:
            row = TenantApiKey(
                tenant_id=tenant_id,
                api_key=_new_api_key(),
                allowed_origins=allowed_origins,
            )
            db.add(row)
        else:
            row.allowed_origins = allowed_origins
        await db.commit()
        await restore_rls_context(db)
        await db.refresh(row)
        return row

    async def regenerate(self, db: AsyncSession, tenant_id: UUID) -> TenantApiKey:
        row = await tenant_api_keys_repository.get_by_tenant_id(db, tenant_id)
        if row is None:
            row = TenantApiKey(tenant_id=tenant_id, api_key=_new_api_key(), allowed_origins=[])
            db.add(row)
        else:
            row.api_key = _new_api_key()
        await db.commit()
        await restore_rls_context(db)
        await db.refresh(row)
        return row

    async def revoke(self, db: AsyncSession, tenant_id: UUID) -> None:
        await tenant_api_keys_repository.delete_by_tenant_id(db, tenant_id)
        await db.commit()
        await restore_rls_context(db)
