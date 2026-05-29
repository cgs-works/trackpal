"""WhatsApp Master Console service — conversation flow routing."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.core.input_validation import InputValidationError
from app.core.redis_client import RedisUnavailableError
from app.services.contingency_reply_policy import ContingencyReplyPolicy

from . import messages as msg
from . import lifecycle_messages as lc_msg
from . import edit_messages as edit_msg
from . import formatters as fmt
from . import list_flow as list_f
from . import create_handlers as ch
from . import create_confirm as cc
from . import detail_flow as df
from . import lifecycle_confirm as lc
from . import edit_handlers as eh


class WhatsAppConsoleService:
    """Route incoming WhatsApp messages for the Master Console.

    Owns conversation state transitions, menu routing, and CRUD decisions.
    """

    # -- Public API surface (constants) ----------------------------------

    MAIN_MENU = msg.MAIN_MENU
    ACCESS_DENIED = msg.ACCESS_DENIED
    HELP_TEXT = msg.HELP_TEXT
    FALLBACK_NO_FLOW = msg.FALLBACK_NO_FLOW
    FALLBACK_ACTIVE_FLOW = msg.FALLBACK_ACTIVE_FLOW
    RESET_COMMANDS = msg.RESET_COMMANDS
    HELP_COMMANDS = msg.HELP_COMMANDS
    NO_TENANTS = msg.NO_TENANTS
    INVALID_SELECTION = msg.INVALID_SELECTION
    TENANT_DETAIL_ACTIVE_ACTIONS = msg.TENANT_DETAIL_ACTIVE_ACTIONS
    TENANT_DETAIL_INACTIVE_ACTIONS = msg.TENANT_DETAIL_INACTIVE_ACTIONS
    CONFIRM_REPROMPT = lc_msg.CONFIRM_REPROMPT
    DEACTIVATE_CONFIRM_PROMPT = lc_msg.DEACTIVATE_CONFIRM_PROMPT
    DELETE_CONFIRM_PROMPT = lc_msg.DELETE_CONFIRM_PROMPT

    # -- Flow identifiers -------------------------------------------------

    LIST_FLOW = msg.LIST_FLOW
    SELECT_STEP = msg.SELECT_STEP
    DETAIL_FLOW = msg.DETAIL_FLOW
    ACTIONS_STEP = msg.ACTIONS_STEP
    CREATE_FLOW = msg.CREATE_FLOW
    DEACTIVATE_FLOW = msg.DEACTIVATE_FLOW
    DELETE_FLOW = msg.DELETE_FLOW
    CONFIRM_DEACTIVATE_STEP = msg.CONFIRM_DEACTIVATE_STEP
    CONFIRM_DELETE_STEP = msg.CONFIRM_DELETE_STEP
    CREATE_STEP_FULL_NAME = msg.CREATE_STEP_FULL_NAME
    CREATE_STEP_EMAIL = msg.CREATE_STEP_EMAIL
    CREATE_STEP_PHONE = msg.CREATE_STEP_PHONE
    CREATE_STEP_USERNAME = msg.CREATE_STEP_USERNAME
    CREATE_STEP_EVOLUTION_INSTANCE = msg.CREATE_STEP_EVOLUTION_INSTANCE
    CREATE_STEP_PASSWORD_MODE = msg.CREATE_STEP_PASSWORD_MODE
    CREATE_STEP_MANUAL_PASSWORD = msg.CREATE_STEP_MANUAL_PASSWORD
    CREATE_STEP_CONFIRM = msg.CREATE_STEP_CONFIRM

    # -- Edit flow constants ----------------------------------------------

    EDIT_FLOW = edit_msg.EDIT_FLOW
    EDIT_STEP_SELECT_FIELD = edit_msg.EDIT_STEP_SELECT_FIELD
    EDIT_STEP_NEW_VALUE = edit_msg.EDIT_STEP_NEW_VALUE
    EDIT_FIELD_MAP = edit_msg.EDIT_FIELD_MAP
    EDIT_FIELD_PROMPTS = edit_msg.EDIT_FIELD_PROMPTS
    EDIT_ERROR_INVALID_FIELD = edit_msg.EDIT_ERROR_INVALID_FIELD
    EDIT_ERROR_UPDATE_FAILED = edit_msg.EDIT_ERROR_UPDATE_FAILED
    EDIT_DETAIL_FALLBACK = edit_msg.EDIT_DETAIL_FALLBACK
    _VALIDATION_MESSAGES = msg.VALIDATION_MESSAGES
    SKIP_WORDS = msg.SKIP_WORDS

    # -- Handler methods (assigned from flow modules) ---------------------

    _format_tenant_list = staticmethod(fmt._format_tenant_list)
    _format_tenant_detail = staticmethod(fmt._format_tenant_detail)
    _with_main_menu = staticmethod(fmt._with_main_menu)
    _validation_error_reply = fmt._validation_error_reply

    _handle_list_tenants = list_f._handle_list_tenants
    _handle_list_selection = list_f._handle_list_selection
    _start_create_flow = list_f._start_create_flow
    _handle_create_step = list_f._handle_create_step

    _handle_create_full_name = ch._handle_create_full_name
    _handle_create_email = ch._handle_create_email
    _handle_create_phone = ch._handle_create_phone
    _handle_create_username = ch._handle_create_username
    _handle_create_evolution_instance = ch._handle_create_evolution_instance
    _handle_create_password_mode = ch._handle_create_password_mode
    _handle_create_manual_password = ch._handle_create_manual_password
    _build_create_summary = ch._build_create_summary
    _handle_create_confirm = cc._handle_create_confirm

    _handle_detail_action = df._handle_detail_action
    _handle_detail_deactivate_reactivate = df._handle_detail_deactivate_reactivate
    _handle_detail_delete = df._handle_detail_delete

    _handle_deactivate_confirm = lc._handle_deactivate_confirm
    _handle_delete_confirm = lc._handle_delete_confirm

    _start_edit_flow = eh._start_edit_flow
    _handle_edit_step = eh._handle_edit_step
    _get_edit_field_selection_prompt = staticmethod(eh._get_edit_field_selection_prompt)
    _handle_edit_select_field = eh._handle_edit_select_field
    _handle_edit_new_value = eh._handle_edit_new_value

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def process_message(
        self,
        phone: str,
        message: str,
        *,
        is_master: bool = False,
        session_service=None,
        tenant_service=None,
    ) -> str:
        """Process a WhatsApp message and return the reply text.

        Args:
            phone:           Normalised phone number of the sender.
            message:         Text of the WhatsApp message.
            is_master:       Whether the sender has been identified as Master.
            session_service: Optional ``WhatsAppSessionService`` for
                             session-aware routing. When ``None`` the
                             service operates without persistence.
            tenant_service:  Optional object with ``get_tenants()`` and
                             ``get_tenant(id)`` methods for fetching tenant
                             data. When ``None``, tenant-related menu options
                             fall back to the main menu.

        Returns:
            Reply text that n8n will send through Evolution API.
        """
        if not is_master:
            return self.ACCESS_DENIED

        msg_text = message.strip()

        try:
            session = None
            if session_service is not None:
                session = await session_service.get_session(phone)

            has_active_flow = session is not None and bool(session.flow)

            # ── Active flow routing (before reset check) ──────────────
            # Route active flows first so that flow-specific handlers
            # can process "9" (back) before the global RESET_COMMANDS
            # check intercepts it.
            if has_active_flow:
                # Global exit: "0" clears session + returns main menu
                if msg_text in ("0",):
                    if session_service is not None:
                        await session_service.clear_session(phone)
                    return self._with_main_menu("🚫 Operación cancelada.")
                if msg_text.lower() in ("menu", "menú", "/menu", "cancelar"):
                    if session_service is not None:
                        await session_service.clear_session(phone)
                    return self._with_main_menu("🚫 Operación cancelada.")
                if msg_text.lower() in self.HELP_COMMANDS:
                    return self.HELP_TEXT
                if session.flow == self.LIST_FLOW and session.step == self.SELECT_STEP:
                    return await self._handle_list_selection(
                        phone, msg_text, session, session_service, tenant_service
                    )
                elif session.flow == self.CREATE_FLOW:
                    return await self._handle_create_step(
                        phone, msg_text, session, session_service, tenant_service
                    )
                elif (
                    session.flow == self.DETAIL_FLOW
                    and session.step == self.ACTIONS_STEP
                ):
                    return await self._handle_detail_action(
                        phone, msg_text, session, session_service, tenant_service
                    )
                elif session.flow == self.EDIT_FLOW:
                    return await self._handle_edit_step(
                        phone, msg_text, session, session_service, tenant_service
                    )
                elif (
                    session.flow == self.DEACTIVATE_FLOW
                    and session.step == self.CONFIRM_DEACTIVATE_STEP
                ):
                    return await self._handle_deactivate_confirm(
                        phone, msg_text, session, session_service, tenant_service
                    )
                elif (
                    session.flow == self.DELETE_FLOW
                    and session.step == self.CONFIRM_DELETE_STEP
                ):
                    return await self._handle_delete_confirm(
                        phone, msg_text, session, session_service, tenant_service
                    )
                return self.FALLBACK_ACTIVE_FLOW

            # ── No active flow ───────────────────────────────────────
            # Contextual reset — no active flow
            if msg_text.lower() in self.RESET_COMMANDS:
                if session_service is not None:
                    await session_service.clear_session(phone)
                return self.MAIN_MENU

            # Contingency reset — failover active, session missing on backup
            if (
                session is None
                and session_service is not None
                and session_service.used_backup
                and msg_text.lower() not in self.RESET_COMMANDS
            ):
                await session_service.create_session(phone)
                return ContingencyReplyPolicy.SESSION_RESET

            # Help — reachable from any state
            if msg_text.lower() in self.HELP_COMMANDS:
                return self.HELP_TEXT

            # No active flow
            if not msg_text:
                return self.MAIN_MENU

            if msg_text in {"1", "2", "3", "4"}:
                if msg_text in {"1", "3", "4"} and tenant_service is not None:
                    return await self._handle_list_tenants(
                        phone, session_service, tenant_service
                    )
                if msg_text == "2":
                    return await self._start_create_flow(phone, session_service)
                return self.MAIN_MENU

            return self.FALLBACK_NO_FLOW

        except RedisUnavailableError:
            return ContingencyReplyPolicy.TEMPORARY_UNAVAILABLE
