"""Server-authoritative Demo Tenant authentication lifecycle operations."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import set_internal_rls_context
from app.models import DemoTenantStatus, Tenant, User
from app.repositories import sessions_repository

DEMO_DURATION = timedelta(hours=48)


class DemoAuthError(Exception):
    """Stable error codes exposed by Demo authentication endpoints."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def server_time() -> datetime:
    return datetime.now(timezone.utc)


async def get_demo_for_user(db: AsyncSession, user_id: UUID) -> Tenant | None:
    statement = select(Tenant).where(
        Tenant.owner_user_id == user_id,
        Tenant.is_demo.is_(True),
    )
    return (await db.execute(statement)).scalar_one_or_none()


async def delete_expired_demo(db: AsyncSession, user: User) -> None:
    """Delete an expired Demo Tenant and its authentication identity."""
    await set_internal_rls_context(db)
    await sessions_repository.revoke_all_for_user(db, user.id)
    await db.delete(user)
    await db.commit()
    raise DemoAuthError("demo_ended")


async def ensure_demo_request(
    db: AsyncSession,
    user: User,
    *,
    credential_version: int | None = None,
) -> Tenant | None:
    """Validate the current Demo lifecycle before serving a request."""
    tenant = await get_demo_for_user(db, user.id)
    if tenant is None:
        return None

    if tenant.get_demo_status(server_time()) is DemoTenantStatus.EXPIRED:
        await delete_expired_demo(db, user)

    if (
        credential_version is not None
        and credential_version != tenant.demo_credentials_version
    ):
        raise DemoAuthError("demo_credentials_replaced")
    return tenant


async def activate_demo_for_login(db: AsyncSession, user: User) -> Tenant | None:
    """Atomically start a pending Demo Tenant's fixed 48-hour evaluation."""
    tenant = await ensure_demo_request(db, user)
    if (
        tenant is None
        or tenant.get_demo_status(server_time()) is not DemoTenantStatus.PENDING
    ):
        return tenant

    activated_at = server_time()
    expires_at = activated_at + DEMO_DURATION
    result = await db.execute(
        update(Tenant)
        .where(
            Tenant.id == tenant.id,
            Tenant.is_demo.is_(True),
            Tenant.demo_activated_at.is_(None),
            Tenant.demo_expires_at.is_(None),
        )
        .values(
            demo_activated_at=activated_at,
            demo_expires_at=expires_at,
        )
    )
    if result.rowcount:
        tenant.demo_activated_at = activated_at
        tenant.demo_expires_at = expires_at
    else:
        await db.refresh(tenant)
    return tenant


def _utc(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=timezone.utc)


def lifecycle_metadata(
    tenant: Tenant | None, *, now: datetime | None = None
) -> dict[str, object | None]:
    """Return authentication-only metadata; never include workspace data."""
    current_time = now or server_time()
    if tenant is None or not tenant.is_demo:
        return {
            "is_demo": False,
            "demo_tenant_id": None,
            "demo_name": None,
            "tenant_plan": None,
            "demo_status": None,
            "demo_activated_at": None,
            "demo_expires_at": None,
            "demo_credentials_version": None,
            "server_time": current_time,
        }
    return {
        "is_demo": True,
        "demo_tenant_id": tenant.id,
        "demo_name": tenant.name,
        "tenant_plan": tenant.plan,
        "demo_status": tenant.get_demo_status(current_time),
        "demo_activated_at": _utc(tenant.demo_activated_at),
        "demo_expires_at": _utc(tenant.demo_expires_at),
        "demo_credentials_version": tenant.demo_credentials_version,
        "server_time": current_time,
    }


__all__ = [
    "DEMO_DURATION",
    "DemoAuthError",
    "activate_demo_for_login",
    "ensure_demo_request",
    "get_demo_for_user",
    "lifecycle_metadata",
    "server_time",
]
