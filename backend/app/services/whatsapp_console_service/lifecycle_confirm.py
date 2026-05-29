"""Deactivate/delete confirmation handlers for the Master Console."""

from __future__ import annotations

from . import lifecycle_messages as lc_msg
from app.services.whatsapp_master_console_facade.constants import POST_ACTION_PROMPT


async def _handle_deactivate_confirm(
    self,
    phone: str,
    msg_text: str,
    session,
    session_service,
    tenant_service,
) -> str:
    """Handle CONFIRMAR during deactivation flow."""
    stripped = msg_text.strip()

    if stripped.upper() != "CONFIRMAR":
        return self.CONFIRM_REPROMPT

    tenant_id = session.selected_tenant_id
    if not tenant_id:
        return self.EDIT_DETAIL_FALLBACK

    if tenant_service is not None and hasattr(tenant_service, "deactivate_tenant"):
        tenant_name = tenant_id
        if hasattr(tenant_service, "get_tenant"):
            tenant = await tenant_service.get_tenant(tenant_id)
            if tenant is not None:
                tenant_name = tenant.full_name

        result = await tenant_service.deactivate_tenant(tenant_id)
        if result.get("success"):
            if session_service is not None:
                await session_service.clear_session(phone)
            return (
                self._with_main_menu(
                    lc_msg.DEACTIVATE_SUCCESS_MESSAGE.format(name=tenant_name)
                )
                + POST_ACTION_PROMPT
            )
        else:
            error = result.get("error", "Error desconocido al desactivar.")
            return (
                "❌ "
                + error
                + "\n\n"
                + lc_msg.DEACTIVATE_CONFIRM_PROMPT.format(name=tenant_name)
            )

    return self.EDIT_DETAIL_FALLBACK


async def _handle_delete_confirm(
    self,
    phone: str,
    msg_text: str,
    session,
    session_service,
    tenant_service,
) -> str:
    """Handle CONFIRMAR during deletion flow."""
    stripped = msg_text.strip()

    if stripped.upper() != "CONFIRMAR":
        return self.CONFIRM_REPROMPT

    tenant_id = session.selected_tenant_id
    if not tenant_id:
        return self.EDIT_DETAIL_FALLBACK

    if tenant_service is not None and hasattr(tenant_service, "delete_tenant"):
        tenant_name = tenant_id
        if hasattr(tenant_service, "get_tenant"):
            tenant = await tenant_service.get_tenant(tenant_id)
            if tenant is not None:
                tenant_name = tenant.full_name

        result = await tenant_service.delete_tenant(tenant_id)
        if result.get("success"):
            if session_service is not None:
                await session_service.clear_session(phone)
            return (
                self._with_main_menu(
                    lc_msg.DELETE_SUCCESS_MESSAGE.format(name=tenant_name)
                )
                + POST_ACTION_PROMPT
            )
        else:
            error = result.get("error", "Error desconocido al eliminar.")
            return "❌ " + error

    return self.EDIT_DETAIL_FALLBACK
