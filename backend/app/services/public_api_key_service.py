from __future__ import annotations

import secrets
from urllib.parse import urlparse
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import restore_rls_context
from app.core.demo_guardrail import assert_demo_operation_allowed
from app.core.tenant_plan import TENANT_PLAN_PRO
from app.models import TenantApiKey
from app.repositories import (
    catalog_repository,
    tenant_api_keys_repository,
    tenants_repository,
)
from app.schemas.public_api_key import (
    PublicCatalogPlan,
    PublicCatalogResponse,
    PublicCatalogService,
)

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
        raise ValueError(
            "Allowed origin must be an exact http(s) origin such as https://example.com"
        )
    return f"{parsed.scheme}://{parsed.netloc}"


def normalize_allowed_origins(origins: list[str]) -> list[str]:
    return list(dict.fromkeys(validate_allowed_origin(origin) for origin in origins))


class PublicApiKeyService:
    async def get_config(
        self, db: AsyncSession, tenant_id: UUID
    ) -> TenantApiKey | None:
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
            try:
                row = TenantApiKey(
                    tenant_id=tenant_id,
                    api_key=_new_api_key(),
                    allowed_origins=allowed_origins,
                )
                db.add(row)
                await db.commit()
            except IntegrityError:
                await db.rollback()
                row = await tenant_api_keys_repository.get_by_tenant_id(db, tenant_id)
                # ponytail: row is guaranteed to exist after the conflict
                row.allowed_origins = allowed_origins
                await db.commit()
        else:
            row.allowed_origins = allowed_origins
            await db.commit()
        await restore_rls_context(db)
        await db.refresh(row)
        return row

    async def regenerate(self, db: AsyncSession, tenant_id: UUID) -> TenantApiKey:
        row = await tenant_api_keys_repository.get_by_tenant_id(db, tenant_id)
        if row is None:
            raise ValueError("Public API key not found")
        row.api_key = _new_api_key()
        await db.commit()
        await restore_rls_context(db)
        await db.refresh(row)
        return row

    async def revoke(self, db: AsyncSession, tenant_id: UUID) -> None:
        await tenant_api_keys_repository.delete_by_tenant_id(db, tenant_id)
        await db.commit()
        await restore_rls_context(db)

    async def build_public_catalog(
        self,
        db: AsyncSession,
        *,
        api_key: str | None,
        origin: str | None,
    ) -> tuple[PublicCatalogResponse, str] | None:
        if not api_key or not origin:
            return None

        key = await tenant_api_keys_repository.get_by_api_key(db, api_key)
        if key is None:
            return None

        if origin not in key.allowed_origins:
            return None

        tenant = await tenants_repository.get_active(db, key.tenant_id)
        if tenant is None or tenant.plan != TENANT_PLAN_PRO:
            return None
        assert_demo_operation_allowed(tenant, operation="public_catalog")

        services = await catalog_repository.list_services(db, key.tenant_id)
        service_list: list[PublicCatalogService] = []
        for svc in services:
            plans = await catalog_repository.list_plans(db, key.tenant_id, svc.id)
            service_list.append(
                PublicCatalogService(
                    id=svc.id,
                    name=svc.name,
                    plans=[PublicCatalogPlan(id=p.id, name=p.name) for p in plans],
                )
            )

        return PublicCatalogResponse(services=service_list), origin
