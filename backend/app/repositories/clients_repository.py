"""Client repository — client table queries."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Client, Tenant, User


async def get(
    db: AsyncSession, tenant_id: UUID, client_id: UUID
) -> Client | None:
    """Get a client by tenant and client id, with user and tenant loaded."""
    result = await db.execute(
        select(Client)
        .options(selectinload(Client.user), selectinload(Client.tenant))
        .where(Client.tenant_id == tenant_id, Client.id == client_id)
    )
    return result.scalar_one_or_none()


async def get_active_client_tenant_join(
    db: AsyncSession, user_id: UUID
) -> tuple[Client, Tenant] | None:
    """Get active client + tenant for a user (auth flow)."""
    result = await db.execute(
        select(Client, Tenant)
        .join(Tenant, Tenant.id == Client.tenant_id)
        .where(
            Client.owner_user_id == user_id,
            Client.is_active,
            Tenant.is_active,
        )
    )
    return result.first()


async def get_active_client_in_tenant(
    db: AsyncSession, user_id: UUID, tenant_id: UUID
) -> Client | None:
    """Check if a user has an active client profile inside an active tenant."""
    result = await db.execute(
        select(Client)
        .join(Tenant, Tenant.id == Client.tenant_id)
        .where(
            Client.owner_user_id == user_id,
            Client.is_active,
            Tenant.id == tenant_id,
            Tenant.is_active,
        )
    )
    return result.scalar_one_or_none()


async def list_clients(
    db: AsyncSession, tenant_id: UUID
) -> list[Client]:
    """List all clients for a tenant, newest first."""
    result = await db.execute(
        select(Client)
        .options(selectinload(Client.user), selectinload(Client.tenant))
        .where(Client.tenant_id == tenant_id)
        .order_by(Client.created_at.desc())
    )
    return list(result.scalars().all())


async def local_username_exists(
    db: AsyncSession,
    tenant_id: UUID,
    canonical_username: str,
    exclude_id: UUID | None = None,
) -> bool:
    """Check if a canonical username is taken within a tenant."""
    stmt = select(Client.id).where(
        Client.tenant_id == tenant_id,
        func.lower(Client.username) == canonical_username.lower(),
    )
    if exclude_id is not None:
        stmt = stmt.where(Client.id != exclude_id)
    return (await db.execute(stmt)).first() is not None


async def phone_exists(
    db: AsyncSession,
    tenant_id: UUID,
    phone: str,
    exclude_id: UUID | None = None,
) -> bool:
    """Check if a phone is taken within a tenant."""
    stmt = select(Client.id).where(
        Client.tenant_id == tenant_id, Client.phone == phone
    )
    if exclude_id is not None:
        stmt = stmt.where(Client.id != exclude_id)
    return (await db.execute(stmt)).first() is not None


async def get_clients_with_user(
    db: AsyncSession, tenant_id: UUID
) -> list[Client]:
    """Get clients with their user loaded, ordered by creation time."""
    result = await db.execute(
        select(Client)
        .options(selectinload(Client.user))
        .where(Client.tenant_id == tenant_id)
        .order_by(Client.created_at.asc())
    )
    return list(result.scalars().all())


__all__ = [
    "get",
    "get_active_client_tenant_join",
    "get_active_client_in_tenant",
    "list_clients",
    "local_username_exists",
    "phone_exists",
    "get_clients_with_user",
]
