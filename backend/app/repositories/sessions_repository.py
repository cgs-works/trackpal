"""Session repository — RefreshSession table queries."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Client, RefreshSession


async def get_valid_sessions(db: AsyncSession, user_id: UUID) -> list[RefreshSession]:
    """Get all non-revoked, non-expired sessions for a user."""
    result = await db.execute(
        select(RefreshSession).where(
            RefreshSession.user_id == user_id,
            RefreshSession.revoked == False,  # noqa: E712
            RefreshSession.expires_at > datetime.now(timezone.utc),
        )
    )
    return list(result.scalars().all())


async def get_all_unrevoked(db: AsyncSession) -> list[RefreshSession]:
    """Get all non-revoked sessions (used during logout)."""
    result = await db.execute(
        select(RefreshSession).where(
            RefreshSession.revoked == False  # noqa: E712
        )
    )
    return list(result.scalars().all())


async def revoke_all_for_user(db: AsyncSession, user_id: UUID) -> None:
    """Revoke all active sessions for a user."""
    await db.execute(
        update(RefreshSession)
        .where(
            RefreshSession.user_id == user_id,
            RefreshSession.revoked == False,  # noqa: E712
        )
        .values(revoked=True)
    )


async def revoke_all_for_tenant_clients(db: AsyncSession, tenant_id: UUID) -> None:
    """Revoke all active refresh sessions for every client user in a tenant."""
    result = await db.execute(select(Client.owner_user_id).where(Client.tenant_id == tenant_id))
    user_ids = [row[0] for row in result.all()]
    if not user_ids:
        return
    await db.execute(
        update(RefreshSession)
        .where(
            RefreshSession.user_id.in_(user_ids),
            RefreshSession.revoked == False,  # noqa: E712
        )
        .values(revoked=True)
    )


__all__ = [
    "get_valid_sessions",
    "get_all_unrevoked",
    "revoke_all_for_user",
    "revoke_all_for_tenant_clients",
]
