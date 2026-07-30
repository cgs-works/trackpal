"""WhatsApp Tenant Admin Console service — conversation flow routing."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.i18n import t as _i18n_t
from app.core.redis_client import RedisUnavailableError
from app.services.contingency_reply_policy import ContingencyReplyPolicy
from app.services.whatsapp_navigation import is_cancel
from app.services.whatsapp_session_service import WhatsAppSessionService
from app.services.tenant_console_protocols import (
    CatalogServiceProtocol,
    ClientServiceProtocol,
    SubscriptionServiceProtocol,
)

from . import _context as ctx
from ._const_mixin import _ConstMixin

logger = logging.getLogger(__name__)


class WhatsAppTenantConsoleService(
    _ConstMixin,
    # Handler assignments injected via _assignments module below
):
    """Route incoming WhatsApp messages for the Tenant Admin Console."""

    # -- Inject all handler/formatter/static assignments ------------------
    # These are defined in _assignments.py and injected into this class's
    # namespace via class-level attribute assignment below.

    from . import _assignments as _  # noqa: E402

    # fmt: off
    _t = _._t
    _with_main_menu = _._with_main_menu
    _post_action_prompt = _._post_action_prompt
    _format_client_list = _._format_client_list
    _format_client_detail = _._format_client_detail
    _format_service_list = _._format_service_list
    _format_service_detail = _._format_service_detail
    _format_plan_list = _._format_plan_list
    _format_plan_detail = _._format_plan_detail
    _format_profile_detail = _._format_profile_detail
    _format_subscription_list = _._format_subscription_list
    _format_subscription_detail = _._format_subscription_detail
    _safe_uuid = _._safe_uuid
    _format_subscription_duration = _._format_subscription_duration
    _format_short_date = _._format_short_date
    _calculate_subscription_expiry = _._calculate_subscription_expiry
    _parse_iso_date = _._parse_iso_date
    _start_clients_flow = _._start_clients_flow
    _handle_client_list_selection = _._handle_client_list_selection
    _handle_client_select = _._handle_client_select
    _handle_client_detail_action = _._handle_client_detail_action
    _start_client_create = _._start_client_create
    _handle_client_create_full_name = _._handle_client_create_full_name
    _handle_client_create_phone = _._handle_client_create_phone
    _handle_client_create_username = _._handle_client_create_username
    _handle_client_create_password = _._handle_client_create_password
    _handle_client_create_confirm = _._handle_client_create_confirm
    _start_client_edit = _._start_client_edit
    _handle_client_edit_field = _._handle_client_edit_field
    _handle_client_edit_value = _._handle_client_edit_value
    _handle_client_deactivate_confirm = _._handle_client_deactivate_confirm
    _handle_client_delete_confirm = _._handle_client_delete_confirm
    _handle_clients_block_list = _._handle_clients_block_list
    _handle_clients_block_unblock = _._handle_clients_block_unblock
    _start_catalog_flow = _._start_catalog_flow
    _catalog_menu_reply = _._catalog_menu_reply
    _set_post_action = _._set_post_action
    _fetch_service_list = _._fetch_service_list
    _handle_catalog_menu = _._handle_catalog_menu
    _show_catalog_service_list = _._show_catalog_service_list
    _handle_catalog_service_select = _._handle_catalog_service_select
    _handle_catalog_service_action = _._handle_catalog_service_action
    _handle_catalog_edit_service = _._handle_catalog_edit_service
    _handle_catalog_plan_select = _._handle_catalog_plan_select
    _handle_catalog_plan_action = _._handle_catalog_plan_action
    _handle_catalog_edit_plan = _._handle_catalog_edit_plan
    _handle_catalog_create_service_name = _._handle_catalog_create_service_name
    _handle_catalog_create_plan_name = _._handle_catalog_create_plan_name
    _handle_catalog_empty_plan_menu = _._handle_catalog_empty_plan_menu
    _handle_catalog_post_action = _._handle_catalog_post_action
    _show_catalog_delete_service_list = _._show_catalog_delete_service_list
    _handle_catalog_delete_service_select = _._handle_catalog_delete_service_select
    _render_service_delete_warning = _._render_service_delete_warning
    _handle_catalog_delete_service_confirm = _._handle_catalog_delete_service_confirm
    _show_catalog_delete_plan_list = _._show_catalog_delete_plan_list
    _handle_catalog_delete_plan_select = _._handle_catalog_delete_plan_select
    _render_plan_delete_warning = _._render_plan_delete_warning
    _handle_catalog_delete_plan_confirm = _._handle_catalog_delete_plan_confirm
    _format_catalog_subscription_warning_row = _._format_catalog_subscription_warning_row
    _catalog_count = _._catalog_count
    _paginate = _._paginate
    _start_profile_flow = _._start_profile_flow
    _handle_profile_action = _._handle_profile_action
    _show_profile = _._show_profile
    _start_profile_edit = _._start_profile_edit
    _handle_profile_edit_field = _._handle_profile_edit_field
    _handle_profile_edit_value = _._handle_profile_edit_value
    _start_profile_change_password = _._start_profile_change_password
    _handle_profile_change_password_old = _._handle_profile_change_password_old
    _handle_profile_change_password_new = _._handle_profile_change_password_new
    _start_profile_change_locale = _._start_profile_change_locale
    _handle_profile_change_locale_select = _._handle_profile_change_locale_select
    _start_subscriptions_flow = _._start_subscriptions_flow
    _handle_subscriptions_menu = _._handle_subscriptions_menu
    _query_subscriptions_by_filter = _._query_subscriptions_by_filter
    _handle_subscriptions_filter = _._handle_subscriptions_filter
    _handle_subscriptions_list = _._handle_subscriptions_list
    _handle_subscriptions_select = _._handle_subscriptions_select
    _handle_subscriptions_action = _._handle_subscriptions_action
    _start_subscriptions_create = _._start_subscriptions_create
    _handle_subscriptions_create_client = _._handle_subscriptions_create_client
    _handle_subscriptions_create_service = _._handle_subscriptions_create_service
    _handle_subscriptions_create_plan = _._handle_subscriptions_create_plan
    _handle_subscriptions_create_email = _._handle_subscriptions_create_email
    _handle_subscriptions_create_password = _._handle_subscriptions_create_password
    _handle_subscriptions_create_password_confirm = _._handle_subscriptions_create_password_confirm
    _handle_subscriptions_create_profile_option = _._handle_subscriptions_create_profile_option
    _handle_subscriptions_create_profile_name = _._handle_subscriptions_create_profile_name
    _handle_subscriptions_create_pin = _._handle_subscriptions_create_pin
    _handle_subscriptions_create_pin_confirm = _._handle_subscriptions_create_pin_confirm
    _handle_subscriptions_create_duration = _._handle_subscriptions_create_duration
    _handle_subscriptions_create_custom_date = _._handle_subscriptions_create_custom_date
    _handle_subscriptions_create_confirm = _._handle_subscriptions_create_confirm
    _handle_subscriptions_edit_field = _._handle_subscriptions_edit_field
    _handle_subscriptions_edit_value = _._handle_subscriptions_edit_value
    _handle_subscriptions_edit_password_confirm = _._handle_subscriptions_edit_password_confirm
    _handle_subscriptions_edit_pin_confirm = _._handle_subscriptions_edit_pin_confirm
    _handle_subscriptions_cancel_confirm = _._handle_subscriptions_cancel_confirm
    _handle_subscriptions_reactivate_duration = _._handle_subscriptions_reactivate_duration
    _handle_subscriptions_reactivate_custom_date = _._handle_subscriptions_reactivate_custom_date
    _handle_subscriptions_reactivate_confirm = _._handle_subscriptions_reactivate_confirm
    _handle_subscriptions_renew_duration = _._handle_subscriptions_renew_duration
    _handle_subscriptions_renew_custom_date = _._handle_subscriptions_renew_custom_date
    _handle_subscriptions_renew_confirm = _._handle_subscriptions_renew_confirm
    _get_selected_subscription = _._get_selected_subscription
    _apply_subscription_update = _._apply_subscription_update
    _build_subscription_create_confirm = _._build_subscription_create_confirm
    _build_subscription_reactivate_confirm = _._build_subscription_reactivate_confirm
    _build_subscription_renew_confirm = _._build_subscription_renew_confirm
    _route_clients_flow = _._route_clients_flow
    _route_catalog_flow = _._route_catalog_flow
    _route_profile_flow = _._route_profile_flow
    _route_subscriptions_flow = _._route_subscriptions_flow
    _route_codigo_flow = _._route_codigo_flow
    _route_access_control_flow = _._route_access_control_flow
    _start_codigo_flow = _._start_codigo_flow
    _handle_codigo_service = _._handle_codigo_service
    _handle_codigo_email = _._handle_codigo_email
    _handle_codigo_email_confirm = _._handle_codigo_email_confirm
    _handle_codigo_awaiting_result = _._handle_codigo_awaiting_result
    _start_access_control_flow = _._start_access_control_flow
    _handle_access_control_menu = _._handle_access_control_menu
    _handle_access_control_block_phone = _._handle_access_control_block_phone
    # fmt: on

    # ------------------------------------------------------------------
    # Constructor
    # ------------------------------------------------------------------

    def __init__(
        self,
        client_service: ClientServiceProtocol | None = None,
        catalog_service: CatalogServiceProtocol | None = None,
        profile_service: Any = None,
        subscription_service: SubscriptionServiceProtocol | None = None,
    ) -> None:
        self._client_service = client_service
        self._catalog_service = catalog_service
        self._profile_service = profile_service
        self._subscription_service = subscription_service

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def process_message(
        self,
        phone: str,
        message: str,
        *,
        tenant_id: UUID | None = None,
        user_id: UUID | None = None,
        db: AsyncSession | None = None,
        session_service: WhatsAppSessionService | None = None,
        locale: str | None = None,
        tenant_plan: str = "pro",
    ) -> str:
        if locale is not None:
            _token = ctx.set_locale(locale)
        else:
            _token = None
        msg = message.strip()

        try:
            session = None
            if session_service is not None:
                session = await session_service.get_session(f"admin:{phone}")
            has_active_flow = session is not None and bool(session.flow)

            # ── Active flow routing (before reset check) ──────────────
            # Route active flows first so that flow-specific handlers
            # can process "9" (back / pagination) before the global
            # RESET_COMMANDS check intercepts it.
            if has_active_flow:
                assert session is not None
                # ── Strict-flow bypass for codigo email_confirm ────
                # During email_confirm we want text aliases like
                # "cancelar", "salir", "menu" to be treated as
                # invalid options by the flow handler, not as global
                # reset commands.
                strict_codigo_confirm = False
                if session.flow == self.CODIGO_FLOW:
                    strict_codigo_confirm = (
                        session.step == self.CODIGO_STEP_EMAIL_CONFIRM
                    )

                if not strict_codigo_confirm and (
                    is_cancel(msg)
                    or msg.lower()
                    in (
                        "menu",
                        "menú",
                        "/menu",
                    )
                ):
                    if session_service is not None:
                        await session_service.clear_session(f"admin:{phone}")
                    if msg == "0":
                        # n8n closes Evolution session, so no menu appended
                        return _i18n_t(ctx.get_locale(), "wa.tenant.goodbye")
                    return self._with_main_menu(
                        _i18n_t(ctx.get_locale(), "wa.tenant.cancelled")
                    )
                if not strict_codigo_confirm and msg.lower() in self.HELP_COMMANDS:
                    return self._t(self.KEY_HELP_TEXT)
                return await self._route_active_flow(
                    phone,
                    msg,
                    session,
                    session_service,
                    tenant_id,
                    user_id,
                    db,
                )

            # ── No active flow ───────────────────────────────────────
            menu_key = (
                "wa.tenant.main_menu.starter"
                if tenant_plan == "starter"
                else "wa.tenant.main_menu.pro"
            )

            if msg.lower() in self.RESET_COMMANDS:
                if session_service is not None:
                    await session_service.clear_session(f"admin:{phone}")
                if msg == "0":
                    return self._with_main_menu(
                        _i18n_t(ctx.get_locale(), "wa.tenant.goodbye")
                    )
                return self._t(menu_key)

            if (
                session is None
                and session_service is not None
                and session_service.used_backup
                and msg.lower() not in self.RESET_COMMANDS
            ):
                await session_service.create_session(f"admin:{phone}")
                return ContingencyReplyPolicy.SESSION_RESET

            if msg.lower() in self.HELP_COMMANDS:
                return self._t(self.KEY_HELP_TEXT)

            if not msg:
                return self._t(menu_key)

            if tenant_plan == "starter":
                if msg == "1":
                    return await self._start_profile_flow(
                        phone, session_service, user_id, db
                    )
                if msg == "2" or msg.lower() in ("codigo", "código", "code"):
                    return await self._start_codigo_flow(
                        phone,
                        session_service,
                        tenant_id,
                        db,
                        started_from_menu=msg == "2",
                        role="tenant",
                    )
                if msg == "3":
                    return await self._start_access_control_flow(phone, session_service)
                if msg == "4":
                    return self._t(self.KEY_HELP_TEXT)
                return self._t(self.KEY_FALLBACK_NO_FLOW)

            # Pro plan routing
            if msg == "1":
                return await self._start_clients_flow(
                    phone, session_service, tenant_id, db
                )
            if msg == "2":
                return await self._start_catalog_flow(
                    phone, session_service, tenant_id, db
                )
            if msg == "3":
                return await self._start_profile_flow(
                    phone, session_service, user_id, db
                )
            if msg == "4":
                return await self._start_subscriptions_flow(
                    phone, session_service, tenant_id, db
                )
            if msg == "5":
                return await self._start_access_control_flow(phone, session_service)
            if msg == "6":
                return self._t(self.KEY_HELP_TEXT)
            if msg == "7" or msg.lower() in ("codigo", "código", "code"):
                return await self._start_codigo_flow(
                    phone,
                    session_service,
                    tenant_id,
                    db,
                    started_from_menu=msg == "7",
                    role="tenant",
                )
            return self._t(self.KEY_FALLBACK_NO_FLOW)

        except RedisUnavailableError:
            return ContingencyReplyPolicy.TEMPORARY_UNAVAILABLE
        finally:
            if _token is not None:
                ctx.reset_locale(_token)

    async def _route_active_flow(
        self,
        phone,
        msg,
        session,
        session_service,
        tenant_id,
        user_id,
        db,
    ) -> str:
        flow = session.flow
        step = session.step

        if flow == self.CLIENTS_FLOW:
            return await self._route_clients_flow(
                phone,
                msg,
                step,
                session,
                session_service,
                tenant_id,
                db,
            )
        if flow == self.CATALOG_FLOW:
            return await self._route_catalog_flow(
                phone,
                msg,
                step,
                session,
                session_service,
                tenant_id,
                db,
            )
        if flow == self.PROFILE_FLOW:
            return await self._route_profile_flow(
                phone,
                msg,
                step,
                session,
                session_service,
                user_id,
                db,
            )
        if flow == self.SUBSCRIPTIONS_FLOW:
            return await self._route_subscriptions_flow(
                phone,
                msg,
                step,
                session,
                session_service,
                tenant_id,
                db,
            )
        if flow == self.CODIGO_FLOW:
            return await self._route_codigo_flow(
                phone,
                msg,
                step,
                session,
                session_service,
                tenant_id,
                db,
            )
        if flow == self.ACCESS_CONTROL_FLOW:
            return await self._route_access_control_flow(
                phone,
                msg,
                step,
                session,
                session_service,
                tenant_id,
                db,
            )
        return self._t(self.KEY_FALLBACK_ACTIVE_FLOW)
