from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis_client import get_redis_manager
from app.repositories import blocked_clients_repository, mailbox_lookup_repository
from app.services.whatsapp_session_service import WhatsAppSessionService

logger = logging.getLogger(__name__)


class DuplicateAccessBlockError(ValueError):
    pass


class AccessControlService:
    async def list_blocks(self, db: AsyncSession, tenant_id: UUID):
        return await blocked_clients_repository.list_active(db, tenant_id)

    async def block_phone(self, db: AsyncSession, tenant_id: UUID, phone: str):
        existing = await blocked_clients_repository.find_active(db, tenant_id, phone=phone)
        if existing is not None:
            raise DuplicateAccessBlockError("Phone is already blocked")
        block = await blocked_clients_repository.create(db, tenant_id, phone=phone)
        await self._cancel_codigo_for_phone(db, tenant_id, phone)
        await db.commit()
        await db.refresh(block)
        return block

    async def unblock(self, db: AsyncSession, tenant_id: UUID, block_id: UUID):
        block = await blocked_clients_repository.unblock(db, tenant_id, block_id)
        if block is None:
            return None
        await db.commit()
        return block

    async def _cancel_codigo_for_phone(self, db: AsyncSession, tenant_id: UUID, phone: str) -> None:
        manager = get_redis_manager()
        if manager is None:
            return
        session_service = WhatsAppSessionService(manager)
        logical_keys = [
            f"unreg:{str(tenant_id)[:8]}:{phone}",
            f"admin:{phone}",
        ]
        for logical_key in logical_keys:
            try:
                session = await session_service.get_session(logical_key)
                if session and session.flow == "codigo":
                    lookup_job_id = (session.temp_data or {}).get("lookup_job_id")
                    if lookup_job_id:
                        try:
                            await mailbox_lookup_repository.cancel_active_job_if_present(
                                db,
                                UUID(lookup_job_id),
                                tenant_id=tenant_id,
                            )
                        except ValueError:
                            logger.warning("Invalid lookup job id while blocking phone: %s", lookup_job_id)
                    await session_service.clear_session(logical_key)
            except Exception:
                logger.warning("Failed to clear codigo session for blocked phone tenant=%s phone=%s", tenant_id, phone, exc_info=True)
