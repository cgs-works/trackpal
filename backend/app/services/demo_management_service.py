"""Master-only Demo Tenant identity and lifecycle management."""

from __future__ import annotations

import logging
import secrets
import string
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import restore_rls_context, set_internal_rls_context
from app.core.input_validation import validate_full_name
from app.core.security import get_password_hash
from app.core.tenant_plan import normalize_tenant_plan
from app.models import DemoTenantStatus, Tenant, User
from app.repositories import sessions_repository, tenants_repository, users_repository
from app.schemas.demo import (
    DemoTenantCreate,
    DemoTenantCredentialsResponse,
    DemoTenantResponse,
)
from app.services.demo_lifecycle_service import server_time
from app.services.tenant_service.helpers import generate_unique_client_prefix

logger = logging.getLogger(__name__)

_USERNAME_ALPHABET = string.ascii_lowercase + string.digits
_USERNAME_LENGTH = 12
_PASSWORD_LENGTH = 32


class DemoManagementError(Exception):
    """Expected lifecycle error from a Master Demo Tenant operation."""

    def __init__(self, code: str, status_code: int) -> None:
        self.code = code
        self.status_code = status_code
        super().__init__(code)


def _generate_username() -> str:
    suffix = "".join(
        secrets.choice(_USERNAME_ALPHABET) for _ in range(_USERNAME_LENGTH)
    )
    return f"demo_{suffix}"


async def _generate_unique_username(db: AsyncSession) -> str:
    for _ in range(20):
        username = _generate_username()
        if not await users_repository.username_exists(db, username):
            return username
    raise ValueError("Unable to generate unique Demo Tenant username")


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=timezone.utc)


def _remaining_seconds(tenant: Tenant, now: datetime) -> int | None:
    if tenant.get_demo_status(now) is not DemoTenantStatus.ACTIVE:
        return None
    if tenant.demo_expires_at is None:
        return None
    return max(
        0,
        int((_as_utc(tenant.demo_expires_at) - now).total_seconds()),
    )


def _response(
    tenant: Tenant, *, now: datetime, plain_password: str | None = None
) -> DemoTenantResponse | DemoTenantCredentialsResponse:
    base = {
        "id": tenant.id,
        "name": tenant.name,
        "plan": tenant.plan,
        "status": tenant.get_demo_status(now),
        "username": tenant.owner.username,
        "created_at": _as_utc(tenant.created_at),
        "demo_activated_at": _as_utc(tenant.demo_activated_at),
        "demo_expires_at": _as_utc(tenant.demo_expires_at),
        "server_time": now,
        "remaining_seconds": _remaining_seconds(tenant, now),
    }
    if plain_password is not None:
        return DemoTenantCredentialsResponse(
            **base,
            plain_password=plain_password,
        )
    return DemoTenantResponse(**base)


async def create_demo_tenant(
    db: AsyncSession, payload: DemoTenantCreate
) -> DemoTenantCredentialsResponse:
    """Create a server-only Demo Tenant identity without provisioning services."""
    name = validate_full_name(payload.name)
    plan = normalize_tenant_plan(payload.plan)
    username = await _generate_unique_username(db)
    client_prefix = await generate_unique_client_prefix(db)
    plain_password = secrets.token_urlsafe(_PASSWORD_LENGTH)

    user = User(
        username=username,
        password_hash=get_password_hash(plain_password),
        role="tenant",
    )
    db.add(user)
    await db.flush()

    tenant = Tenant(
        owner_user_id=user.id,
        client_prefix=client_prefix,
        name=name,
        plan=plan,
        is_active=True,
        is_demo=True,
    )
    db.add(tenant)
    await db.flush()
    await db.commit()
    await restore_rls_context(db)

    created = await tenants_repository.get_demo(db, tenant.id)
    if created is None:
        raise ValueError("Demo Tenant could not be created")

    logger.info("Demo Tenant created tenant=%s plan=%s", created.id, created.plan)
    now = server_time()
    result = _response(created, now=now, plain_password=plain_password)
    assert isinstance(result, DemoTenantCredentialsResponse)
    return result


async def list_demo_tenants(db: AsyncSession) -> list[DemoTenantResponse]:
    """Return lifecycle-only records for all Demo Tenants."""
    now = server_time()
    tenants = await tenants_repository.get_demos(db)
    return [
        response
        for tenant in tenants
        if isinstance(response := _response(tenant, now=now), DemoTenantResponse)
    ]


async def replace_demo_credentials(
    db: AsyncSession, tenant_id: UUID
) -> DemoTenantCredentialsResponse | None:
    """Replace a Demo Tenant password without moving its evaluation window."""
    tenant = await tenants_repository.get_demo(db, tenant_id)
    if tenant is None:
        return None
    now = server_time()
    if tenant.get_demo_status(now) is DemoTenantStatus.EXPIRED:
        raise DemoManagementError("demo_ended", 410)

    owner = tenant.owner
    if owner is None:
        raise ValueError("Demo Tenant owner could not be loaded")

    plain_password = secrets.token_urlsafe(_PASSWORD_LENGTH)
    owner.password_hash = get_password_hash(plain_password)
    tenant.demo_credentials_version += 1
    await sessions_repository.revoke_all_for_user(db, owner.id)
    await db.commit()
    await restore_rls_context(db)

    updated = await tenants_repository.get_demo(db, tenant_id)
    if updated is None:
        raise ValueError("Demo Tenant could not be loaded after credential replacement")

    logger.info("Demo Tenant credentials replaced tenant=%s", tenant_id)
    result = _response(updated, now=server_time(), plain_password=plain_password)
    assert isinstance(result, DemoTenantCredentialsResponse)
    return result


async def delete_demo_tenant(db: AsyncSession, tenant_id: UUID) -> bool:
    """Delete a Demo Tenant identity idempotently without external cleanup."""
    tenant = await tenants_repository.get_demo(db, tenant_id)
    if tenant is None:
        return False
    owner = tenant.owner
    if owner is None:
        raise ValueError("Demo Tenant owner could not be loaded")

    await set_internal_rls_context(db)
    await sessions_repository.revoke_all_for_user(db, owner.id)
    await db.delete(owner)
    await db.commit()
    await restore_rls_context(db)
    logger.info("Demo Tenant deleted tenant=%s", tenant_id)
    return True


__all__ = [
    "DemoManagementError",
    "create_demo_tenant",
    "delete_demo_tenant",
    "list_demo_tenants",
    "replace_demo_credentials",
]
