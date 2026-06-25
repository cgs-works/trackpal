"""Access control flow handlers for the Tenant Console."""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def _start_access_control_flow(
    self,
    phone: str,
    session_service: object,
) -> str:
    """Start the access control flow — show the menu."""
    if session_service is not None:
        session = await session_service.get_session(f"admin:{phone}")
        if session is None:
            session = await session_service.create_session(f"admin:{phone}")
        session.flow = self.ACCESS_CONTROL_FLOW
        session.step = self.ACCESS_CONTROL_STEP_MENU
        session.temp_data = {}
        await session_service.save_session(session)
    return self._t(self.KEY_ACCESS_CONTROL_MENU)


async def _handle_access_control_menu(
    self,
    phone: str,
    msg: str,
    session: object,
    session_service: object,
    tenant_id: object,
    db: AsyncSession | None,
) -> str:
    """Handle access control menu selection."""
    if msg == "1":
        return await self._handle_clients_block_list(
            phone, msg, session, session_service, tenant_id, db
        )
    if msg == "2":
        if session_service is not None:
            session.step = self.ACCESS_CONTROL_STEP_BLOCK_PHONE
            await session_service.save_session(session)
        return self._t(self.KEY_ACCESS_CONTROL_BLOCK_PHONE_PROMPT)
    return self._t(self.KEY_ACCESS_CONTROL_MENU)


async def _handle_access_control_block_phone(
    self,
    phone: str,
    msg: str,
    session: object,
    session_service: object,
    tenant_id: object,
    db: AsyncSession | None,
) -> str:
    """Handle phone input for blocking."""
    from app.repositories import blocked_clients_repository

    if db is None or tenant_id is None:
        return self._t(self.KEY_ACCESS_CONTROL_MENU)

    # Check if already blocked
    existing = await blocked_clients_repository.find_active(db, tenant_id, phone=msg.strip())
    if existing:
        return self._t(self.KEY_ACCESS_CONTROL_DUPLICATE)

    # Create the block
    block = await blocked_clients_repository.create(db, tenant_id, phone=msg.strip())
    try:
        await db.commit()
    except Exception:
        logger.exception("Failed to commit block for %s", msg.strip())
        return self._t(self.KEY_ACCESS_CONTROL_MENU)

    identity = block.phone or "—"

    if session_service is not None:
        await session_service.clear_session(f"admin:{phone}")

    return self._with_main_menu(
        self._t(self.KEY_ACCESS_CONTROL_BLOCK_SUCCESS, identity=identity)
    )
