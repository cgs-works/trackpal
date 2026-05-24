"""Shared helpers for tenant operations."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import tenants_repository
from app.models.tenant import _default_client_prefix


async def generate_unique_client_prefix(db: AsyncSession) -> str:
    for _ in range(20):
        candidate = _default_client_prefix()
        if not await tenants_repository.client_prefix_exists(db, candidate):
            return candidate
    raise ValueError("Unable to generate unique client prefix")
