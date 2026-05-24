"""List-flow and create-flow dispatchers for the Master Console."""

from __future__ import annotations

from typing import Any

from . import messages as msg
from . import formatters as fmt


async def _handle_list_tenants(
    self,
    phone: str,
    session_service,
    tenant_service,
) -> str:
    """Fetch tenants, format as numbered list, store selection map."""
    tenants = await tenant_service.get_tenants()

    if not tenants:
        return self.NO_TENANTS

    reply, selection_map = fmt._format_tenant_list(tenants)

    if session_service is not None:
        session = await session_service.get_session(phone)
        if session is None:
            session = await session_service.create_session(phone)
        session.flow = self.LIST_FLOW
        session.step = self.SELECT_STEP
        session.selection_map = selection_map
        await session_service.save_session(session)

    return reply


async def _handle_list_selection(
    self,
    phone: str,
    msg_text: str,
    session,
    session_service,
    tenant_service,
) -> str:
    """Handle a numeric selection during the tenant list flow."""
    if msg_text in session.selection_map:
        tenant_id = session.selection_map[msg_text]

        if tenant_service is not None:
            tenant = await tenant_service.get_tenant(tenant_id)
            if tenant is not None:
                reply = fmt._format_tenant_detail(tenant)
                if session_service is not None:
                    session.flow = self.DETAIL_FLOW
                    session.step = self.ACTIONS_STEP
                    session.selected_tenant_id = tenant_id
                    session.selection_map = {}
                    await session_service.save_session(session)
                return reply

        return self.INVALID_SELECTION

    return self.INVALID_SELECTION


async def _start_create_flow(
    self,
    phone: str,
    session_service,
) -> str:
    """Start the create tenant flow: store flow state and prompt for full name."""
    if session_service is not None:
        session = await session_service.get_session(phone)
        if session is None:
            session = await session_service.create_session(phone)
        session.flow = self.CREATE_FLOW
        session.step = self.CREATE_STEP_FULL_NAME
        session.temp_data = {}
        await session_service.save_session(session)

    return msg.CREATE_PROMPT_FULL_NAME


async def _handle_create_step(
    self,
    phone: str,
    msg_text: str,
    session,
    session_service,
    tenant_service,
) -> str:
    """Dispatch to the correct create flow step handler based on session.step."""
    if session.step == self.CREATE_STEP_FULL_NAME:
        return await self._handle_create_full_name(
            phone, msg_text, session, session_service
        )
    elif session.step == self.CREATE_STEP_EMAIL:
        return await self._handle_create_email(
            phone, msg_text, session, session_service
        )
    elif session.step == self.CREATE_STEP_PHONE:
        return await self._handle_create_phone(
            phone, msg_text, session, session_service
        )
    elif session.step == self.CREATE_STEP_USERNAME:
        return await self._handle_create_username(
            phone, msg_text, session, session_service, tenant_service
        )
    elif session.step == self.CREATE_STEP_EVOLUTION_INSTANCE:
        return await self._handle_create_evolution_instance(
            phone, msg_text, session, session_service
        )
    elif session.step == self.CREATE_STEP_PASSWORD_MODE:
        return await self._handle_create_password_mode(
            phone, msg_text, session, session_service
        )
    elif session.step == self.CREATE_STEP_MANUAL_PASSWORD:
        return await self._handle_create_manual_password(
            phone, msg_text, session, session_service
        )
    elif session.step == self.CREATE_STEP_CONFIRM:
        return await self._handle_create_confirm(
            phone, msg_text, session, session_service, tenant_service
        )
    return self.FALLBACK_ACTIVE_FLOW
