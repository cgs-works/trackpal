"""Detail-screen action handlers for the Master Console."""

from __future__ import annotations

from . import lifecycle_messages as lc_msg


async def _handle_detail_action(
    self,
    phone: str,
    msg_text: str,
    session,
    session_service,
    tenant_service,
) -> str:
    """Handle an action from the Tenant detail screen.

    1 → Start edit flow
    2 → Deactivate (active) or Reactivate (inactive)
    3 → Delete (inactive only)
    0 → Return to main menu
    """
    tenant_id = session.selected_tenant_id
    if not tenant_id:
        return self.EDIT_DETAIL_FALLBACK

    if msg_text == "1":
        return await self._start_edit_flow(
            phone, session, session_service, tenant_service
        )
    elif msg_text == "2":
        return await self._handle_detail_deactivate_reactivate(
            phone, tenant_id, session, session_service, tenant_service
        )
    elif msg_text == "3":
        return await self._handle_detail_delete(
            phone, tenant_id, session, session_service, tenant_service
        )
    return self.EDIT_DETAIL_FALLBACK


async def _handle_detail_deactivate_reactivate(
    self,
    phone: str,
    tenant_id: str,
    session,
    session_service,
    tenant_service,
) -> str:
    """Handle detail screen option 2.

    Active → deactivation confirmation flow.
    Inactive → immediately reactivate.
    """
    if tenant_service is None or not hasattr(tenant_service, "get_tenant"):
        return self.EDIT_DETAIL_FALLBACK

    tenant = await tenant_service.get_tenant(tenant_id)
    if tenant is None:
        return self.INVALID_SELECTION

    if tenant.is_active:
        session.flow = self.DEACTIVATE_FLOW
        session.step = self.CONFIRM_DEACTIVATE_STEP
        if session_service is not None:
            await session_service.save_session(session)
        return lc_msg.DEACTIVATE_CONFIRM_PROMPT.format(name=tenant.full_name)
    else:
        if hasattr(tenant_service, "activate_tenant"):
            result = await tenant_service.activate_tenant(tenant_id)
            if result.get("success"):
                if session_service is not None:
                    await session_service.clear_session(phone)
                return self._with_main_menu(
                    lc_msg.REACTIVATE_SUCCESS_MESSAGE.format(name=tenant.full_name)
                )
            error = result.get("error", "Error desconocido al reactivar.")
            return "❌ " + error
        return self.EDIT_DETAIL_FALLBACK


async def _handle_detail_delete(
    self,
    phone: str,
    tenant_id: str,
    session,
    session_service,
    tenant_service,
) -> str:
    """Handle detail screen option 3.

    Active → block with explanation.
    Inactive → start deletion confirmation flow.
    """
    if tenant_service is None or not hasattr(tenant_service, "get_tenant"):
        return self.EDIT_DETAIL_FALLBACK

    tenant = await tenant_service.get_tenant(tenant_id)
    if tenant is None:
        return self.INVALID_SELECTION

    if tenant.is_active:
        return lc_msg.CANT_DELETE_ACTIVE_MESSAGE
    else:
        session.flow = self.DELETE_FLOW
        session.step = self.CONFIRM_DELETE_STEP
        if session_service is not None:
            await session_service.save_session(session)
        return lc_msg.DELETE_CONFIRM_PROMPT.format(name=tenant.full_name)
