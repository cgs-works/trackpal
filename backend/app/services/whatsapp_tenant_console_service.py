"""WhatsApp Tenant Admin Console service — conversation flow routing.

Owns conversation state transitions, menu routing, help, fallback,
global reset commands, and CRUD decisions for Client, Catalog, and
Profile within the tenant scope.
"""

from __future__ import annotations

import contextvars
import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import UserFacingError, translate_error
from app.core.i18n import t as _i18n_t, LOCALE_NAMES
from app.core.redis_client import RedisUnavailableError
from app.services.contingency_reply_policy import ContingencyReplyPolicy
from app.services.whatsapp_session_service import WhatsAppSessionService
from app.services.tenant_console_protocols import (
    CatalogServiceProtocol,
    ClientServiceProtocol,
    SubscriptionServiceProtocol,
)

logger = logging.getLogger(__name__)

# ContextVar per-message locale — avoids threading locale through 40+ handler methods.
_current_locale: contextvars.ContextVar[str] = contextvars.ContextVar("wa_locale", default="es")


class WhatsAppTenantConsoleService:
    """Route incoming WhatsApp messages for the Tenant Admin Console.

    Owns conversation state transitions, menu routing, and CRUD
    decisions for tenant-scoped clients, catalog items, and profile.
    """

    # ------------------------------------------------------------------
    # Reply templates (Spanish)
    # ------------------------------------------------------------------

    KEY_MAIN_MENU = "wa.tenant.main_menu"

    KEY_HELP_TEXT = "wa.tenant.help"

    KEY_FALLBACK_NO_FLOW = "wa.tenant.fallback.no_flow"

    KEY_FALLBACK_ACTIVE_FLOW = "wa.tenant.fallback.active_flow"

    RESET_COMMANDS = {"0", "menu", "menú", "/menu", "cancelar"}
    HELP_COMMANDS = {"5", "ayuda"}

    # -- Flow identifiers -------------------------------------------------

    CLIENTS_FLOW = "clients"
    CLIENTS_STEP_LIST = "list"
    CLIENTS_STEP_SELECT = "select"
    CLIENTS_STEP_DETAIL = "detail"
    CLIENTS_STEP_DETAIL_ACTION = "detail_action"
    CLIENTS_STEP_CREATE_FULL_NAME = "create_full_name"
    CLIENTS_STEP_CREATE_PHONE = "create_phone"
    CLIENTS_STEP_CREATE_USERNAME = "create_username"
    CLIENTS_STEP_CREATE_PASSWORD = "create_password"
    CLIENTS_STEP_CREATE_CONFIRM = "create_confirm"
    CLIENTS_STEP_EDIT_FIELD = "edit_field"
    CLIENTS_STEP_EDIT_VALUE = "edit_value"
    CLIENTS_STEP_DEACTIVATE_CONFIRM = "deactivate_confirm"
    CLIENTS_STEP_DELETE_CONFIRM = "delete_confirm"

    CATALOG_FLOW = "catalog"
    CATALOG_STEP_LIST = "list"
    CATALOG_STEP_SERVICE_SELECT = "service_select"
    CATALOG_STEP_SERVICE_DETAIL = "service_detail"
    CATALOG_STEP_SERVICE_ACTION = "service_action"
    CATALOG_STEP_EDIT_SERVICE = "edit_service"
    CATALOG_STEP_PLAN_SELECT = "plan_select"
    CATALOG_STEP_PLAN_DETAIL = "plan_detail"
    CATALOG_STEP_PLAN_ACTION = "plan_action"
    CATALOG_STEP_EDIT_PLAN = "edit_plan"

    PROFILE_FLOW = "profile"
    PROFILE_STEP_ACTION = "action"
    PROFILE_STEP_EDIT_FIELD = "edit_field"
    PROFILE_STEP_EDIT_VALUE = "edit_value"
    PROFILE_STEP_CHANGE_PASSWORD_OLD = "change_password_old"
    PROFILE_STEP_CHANGE_PASSWORD_NEW = "change_password_new"
    PROFILE_STEP_CHANGE_LOCALE_SELECT = "change_locale_select"

    SUBSCRIPTIONS_FLOW = "subscriptions"
    SUBSCRIPTIONS_STEP_MENU = "menu"
    SUBSCRIPTIONS_STEP_FILTER = "filter"
    SUBSCRIPTIONS_STEP_LIST = "list"
    SUBSCRIPTIONS_STEP_SELECT = "select"
    SUBSCRIPTIONS_STEP_DETAIL = "detail"
    SUBSCRIPTIONS_STEP_ACTION = "action"
    SUBSCRIPTIONS_STEP_CREATE_CLIENT = "create_client"
    SUBSCRIPTIONS_STEP_CREATE_SERVICE = "create_service"
    SUBSCRIPTIONS_STEP_CREATE_PLAN = "create_plan"
    SUBSCRIPTIONS_STEP_CREATE_EMAIL = "create_email"
    SUBSCRIPTIONS_STEP_CREATE_PASSWORD = "create_password"
    SUBSCRIPTIONS_STEP_CREATE_PASSWORD_CONFIRM = "create_password_confirm"
    SUBSCRIPTIONS_STEP_CREATE_PROFILE_OPTION = "create_profile_option"
    SUBSCRIPTIONS_STEP_CREATE_PROFILE_NAME = "create_profile_name"
    SUBSCRIPTIONS_STEP_CREATE_PIN = "create_pin"
    SUBSCRIPTIONS_STEP_CREATE_PIN_CONFIRM = "create_pin_confirm"
    SUBSCRIPTIONS_STEP_CREATE_DURATION = "create_duration"
    SUBSCRIPTIONS_STEP_CREATE_CUSTOM_DATE = "create_custom_date"
    SUBSCRIPTIONS_STEP_CREATE_CONFIRM = "create_confirm"
    SUBSCRIPTIONS_STEP_EDIT_FIELD = "edit_field"
    SUBSCRIPTIONS_STEP_EDIT_VALUE = "edit_value"
    SUBSCRIPTIONS_STEP_EDIT_PASSWORD_CONFIRM = "edit_password_confirm"
    SUBSCRIPTIONS_STEP_EDIT_PIN_CONFIRM = "edit_pin_confirm"
    SUBSCRIPTIONS_STEP_CANCEL_CONFIRM = "cancel_confirm"
    SUBSCRIPTIONS_STEP_REACTIVATE_DURATION = "reactivate_duration"
    SUBSCRIPTIONS_STEP_REACTIVATE_CUSTOM_DATE = "reactivate_custom_date"
    SUBSCRIPTIONS_STEP_REACTIVATE_CONFIRM = "reactivate_confirm"
    SUBSCRIPTIONS_STEP_RENEW_DURATION = "renew_duration"
    SUBSCRIPTIONS_STEP_RENEW_CUSTOM_DATE = "renew_custom_date"
    SUBSCRIPTIONS_STEP_RENEW_CONFIRM = "renew_confirm"

    # -- Client messages --------------------------------------------------

    KEY_CLIENTS_MENU = "wa.tenant.clients.menu"

    KEY_CLIENT_NO_CLIENTS = "wa.tenant.clients.no_clients"

    KEY_CLIENT_SELECT_PROMPT = "wa.tenant.clients.select_prompt"

    KEY_CLIENT_DETAIL_ACTIVE_ACTIONS = "wa.tenant.clients.detail.active_actions"

    KEY_CLIENT_DETAIL_INACTIVE_ACTIONS = "wa.tenant.clients.detail.inactive_actions"

    KEY_CLIENT_CREATE_PROMPT_FULL_NAME = "wa.tenant.clients.create.full_name"

    KEY_CLIENT_CREATE_PROMPT_PHONE = "wa.tenant.clients.create.phone"

    KEY_CLIENT_CREATE_PROMPT_USERNAME = "wa.tenant.clients.create.username"

    KEY_CLIENT_CREATE_PROMPT_PASSWORD = "wa.tenant.clients.create.password"

    KEY_CLIENT_CREATE_CONFIRM_TEMPLATE = "wa.tenant.clients.create.confirm"

    KEY_CLIENT_CREATE_SUCCESS = "wa.tenant.clients.create.success"

    KEY_CLIENT_CREATE_ERROR_PHONE = "wa.tenant.clients.create.error_phone"

    KEY_CLIENT_EDIT_FIELD_PROMPT = "wa.tenant.clients.edit.field_prompt"

    CLIENT_EDIT_FIELD_MAP = {
        "1": "full_name",
        "2": "phone",
        "3": "local_username",
    }

    CLIENT_EDIT_PROMPTS = {
        "full_name": (
            "✏️ *Editar Cliente*\n\n"
            "¿Cuál es el *nuevo nombre completo*?"
        ),
        "phone": (
            "✏️ *Editar Cliente*\n\n"
            "¿Cuál es el *nuevo teléfono*?"
        ),
        "local_username": (
            "✏️ *Editar Cliente*\n\n"
            "¿Cuál es el *nuevo nombre de usuario local*?"
        ),
    }

    KEY_CLIENT_EDIT_ERROR_INVALID_FIELD = "wa.tenant.clients.edit.invalid_field"

    KEY_CLIENT_DEACTIVATE_CONFIRM_TEMPLATE = "wa.tenant.clients.deactivate.confirm"

    KEY_CLIENT_DELETE_CONFIRM_TEMPLATE = "wa.tenant.clients.delete.confirm"

    KEY_CLIENT_CANT_DELETE_ACTIVE = "wa.tenant.clients.cant_delete_active"

    KEY_CLIENT_DEACTIVATE_SUCCESS = "wa.tenant.clients.deactivate.success"

    KEY_CLIENT_REACTIVATE_SUCCESS = "wa.tenant.clients.reactivate.success"

    KEY_CLIENT_DELETE_SUCCESS = "wa.tenant.clients.delete.success"

    KEY_CLIENT_EDIT_SUCCESS = "wa.tenant.clients.edit.success"

    KEY_CLIENT_CONFIRM_REPROMPT = "wa.tenant.clients.confirm_reprompt"

    KEY_CLIENT_INVALID_SELECTION = "wa.tenant.clients.invalid_selection"

    KEY_CLIENT_NAME_REQUIRED = "wa.tenant.clients.name_required"

    KEY_CLIENT_USERNAME_REQUIRED = "wa.tenant.clients.username_required"

    KEY_CLIENT_SHORT_PASSWORD = "wa.tenant.clients.short_password"

    CLIENT_SKIP_WORDS = {"—", "skip", "ninguno", "none", "-"}

    # -- Catalog messages -------------------------------------------------

    KEY_CATALOG_MENU = "wa.tenant.catalog.menu"

    KEY_CATALOG_NO_SERVICES = "wa.tenant.catalog.no_services"

    KEY_CATALOG_SERVICE_PROMPT = "wa.tenant.catalog.service_prompt"

    KEY_CATALOG_SERVICE_ACTIONS = "wa.tenant.catalog.service_actions"

    KEY_CATALOG_SERVICE_EDIT_PROMPT = "wa.tenant.catalog.service_edit_prompt"

    KEY_CATALOG_SERVICE_EDIT_SUCCESS = "wa.tenant.catalog.service_edit_success"

    KEY_CATALOG_PLAN_ACTIONS = "wa.tenant.catalog.plan_actions"

    KEY_CATALOG_NO_PLANS = "wa.tenant.catalog.no_plans"

    KEY_CATALOG_PLAN_PROMPT = "wa.tenant.catalog.plan_prompt"

    KEY_CATALOG_PLAN_EDIT_PROMPT = "wa.tenant.catalog.plan_edit_prompt"

    KEY_CATALOG_PLAN_EDIT_SUCCESS = "wa.tenant.catalog.plan_edit_success"

    KEY_CATALOG_INVALID_SELECTION = "wa.tenant.catalog.invalid_selection"

    KEY_CATALOG_NAME_REQUIRED = "wa.tenant.catalog.name_required"

    # -- Profile messages -------------------------------------------------

    KEY_PROFILE_MENU = "wa.tenant.profile.menu"

    KEY_PROFILE_EDIT_FIELD_PROMPT = "wa.tenant.profile.edit_field_prompt"

    PROFILE_EDIT_FIELD_MAP = {
        "1": "full_name",
        "2": "email",
        "3": "phone",
    }

    PROFILE_EDIT_PROMPTS = {
        "full_name": (
            "✏️ *Editar Perfil*\n\n"
            "¿Cuál es el *nuevo nombre completo*?"
        ),
        "email": (
            "✏️ *Editar Perfil*\n\n"
            "¿Cuál es el *nuevo email*?"
        ),
        "phone": (
            "✏️ *Editar Perfil*\n\n"
            "¿Cuál es el *nuevo teléfono*?"
        ),
    }

    KEY_PROFILE_EDIT_ERROR_INVALID_FIELD = "wa.tenant.profile.edit_invalid_field"

    KEY_PROFILE_EDIT_SUCCESS = "wa.tenant.profile.edit_success"

    KEY_PROFILE_CHANGE_PASSWORD_PROMPT_OLD = "wa.tenant.profile.change_password_old"

    KEY_PROFILE_CHANGE_PASSWORD_PROMPT_NEW = "wa.tenant.profile.change_password_new"

    KEY_PROFILE_CHANGE_PASSWORD_ERROR_OLD = "wa.tenant.profile.change_password_error_old"

    KEY_PROFILE_CHANGE_PASSWORD_SUCCESS = "wa.tenant.profile.change_password_success"

    # -- Subscription messages --------------------------------------------

    KEY_SUBSCRIPTIONS_MENU = "wa.tenant.subscriptions.menu"

    KEY_SUBSCRIPTIONS_FILTER_PROMPT = "wa.tenant.subscriptions.filter_prompt"

    KEY_SUBSCRIPTIONS_NO_RESULTS = "wa.tenant.subscriptions.no_results"

    KEY_SUBSCRIPTIONS_SELECT_PROMPT = "wa.tenant.subscriptions.select_prompt"

    KEY_SUBSCRIPTION_DETAIL_ACTIONS = "wa.tenant.subscriptions.detail.actions"

    KEY_SUBSCRIPTION_DETAIL_ACTIONS_ACTIVE = "wa.tenant.subscriptions.detail.actions_active"

    # -- Create subscription prompts

    KEY_SUBSCRIPTIONS_CREATE_CLIENT_PROMPT = "wa.tenant.subscriptions.create.client_prompt"

    KEY_SUBSCRIPTIONS_CREATE_SERVICE_PROMPT = "wa.tenant.subscriptions.create.service_prompt"

    KEY_SUBSCRIPTIONS_CREATE_PLAN_PROMPT = "wa.tenant.subscriptions.create.plan_prompt"

    KEY_SUBSCRIPTIONS_CREATE_EMAIL_PROMPT = "wa.tenant.subscriptions.create.email_prompt"

    KEY_SUBSCRIPTIONS_CREATE_PASSWORD_PROMPT = "wa.tenant.subscriptions.create.password_prompt"

    KEY_SUBSCRIPTIONS_CREATE_PASSWORD_CONFIRM_PROMPT = "wa.tenant.subscriptions.create.password_confirm"

    KEY_SUBSCRIPTIONS_CREATE_PASSWORD_MISMATCH = "wa.tenant.subscriptions.create.password_mismatch"

    KEY_SUBSCRIPTIONS_CREATE_PROFILE_NAME_PROMPT = "wa.tenant.subscriptions.create.profile_name"

    KEY_SUBSCRIPTIONS_CREATE_PROFILE_OPTION_PROMPT = "wa.tenant.subscriptions.create.profile_option"

    KEY_SUBSCRIPTIONS_CREATE_PIN_PROMPT = "wa.tenant.subscriptions.create.pin_prompt"

    KEY_SUBSCRIPTIONS_CREATE_PIN_CONFIRM_PROMPT = "wa.tenant.subscriptions.create.pin_confirm"

    KEY_SUBSCRIPTIONS_CREATE_PIN_MISMATCH = "wa.tenant.subscriptions.create.pin_mismatch"

    KEY_SUBSCRIPTIONS_CREATE_PIN_REQUIRES_PROFILE = "wa.tenant.subscriptions.create.pin_requires_profile"

    KEY_SUBSCRIPTIONS_DURATION_PROMPT = "wa.tenant.subscriptions.duration_prompt"

    SUBSCRIPTIONS_DURATION_MAP = {
        "1": "1_month",
        "2": "3_months",
        "3": "6_months",
        "4": "9_months",
        "5": "1_year",
        "6": "custom",
    }

    KEY_SUBSCRIPTIONS_CUSTOM_DATE_PROMPT = "wa.tenant.subscriptions.custom_date_prompt"

    KEY_SUBSCRIPTIONS_CREATE_CONFIRM_TEMPLATE = "wa.tenant.subscriptions.create.confirm"

    KEY_SUBSCRIPTIONS_CREATE_SUCCESS = "wa.tenant.subscriptions.create.success"

    # -- Edit prompts

    KEY_SUBSCRIPTIONS_EDIT_FIELD_PROMPT = "wa.tenant.subscriptions.edit.field_prompt"

    SUBSCRIPTIONS_EDIT_FIELD_MAP = {
        "1": "client",
        "2": "service",
        "3": "plan",
        "4": "streaming_email",
        "5": "streaming_password",
        "6": "profile_name",
        "7": "profile_pin",
    }

    SUBSCRIPTIONS_EDIT_PROMPTS = {
        "streaming_email": (
            "✏️ *Editar Suscripción*\n\n"
            "¿Cuál es el *nuevo email de streaming*?"
        ),
        "streaming_password": (
            "✏️ *Editar Suscripción*\n\n"
            "¿Cuál es la *nueva contraseña de streaming*?\n\n"
            "(Escribe *—* para dejar vacía)"
        ),
        "profile_name": (
            "✏️ *Editar Suscripción*\n\n"
            "¿Cuál es el *nuevo nombre del perfil*?\n\n"
            "(Escribe *—* para dejar vacío)"
        ),
        "profile_pin": (
            "✏️ *Editar Suscripción*\n\n"
            "¿Cuál es el *nuevo PIN del perfil*?\n\n"
            "(Escribe *—* para dejar vacío)"
        ),
    }

    KEY_SUBSCRIPTIONS_EDIT_ERROR_INVALID_FIELD = "wa.tenant.subscriptions.edit.invalid_field"

    KEY_SUBSCRIPTIONS_EDIT_SUCCESS = "wa.tenant.subscriptions.edit.success"

    KEY_SUBSCRIPTIONS_EDIT_PASSWORD_CONFIRM_PROMPT = "wa.tenant.subscriptions.edit.password_confirm"

    KEY_SUBSCRIPTIONS_EDIT_PIN_CONFIRM_PROMPT = "wa.tenant.subscriptions.edit.pin_confirm"

    KEY_SUBSCRIPTIONS_EDIT_MISMATCH = "wa.tenant.subscriptions.edit.mismatch"

    # -- Other lifecycle messages

    KEY_SUBSCRIPTIONS_CANCEL_CONFIRM_TEMPLATE = "wa.tenant.subscriptions.cancel.confirm"

    KEY_SUBSCRIPTIONS_CANCEL_SUCCESS = "wa.tenant.subscriptions.cancel.success"

    KEY_SUBSCRIPTIONS_REACTIVATE_DURATION_PROMPT = "wa.tenant.subscriptions.reactivate.duration_prompt"

    KEY_SUBSCRIPTIONS_REACTIVATE_CUSTOM_DATE_PROMPT = "wa.tenant.subscriptions.reactivate.custom_date"

    KEY_SUBSCRIPTIONS_REACTIVATE_CONFIRM_TEMPLATE = "wa.tenant.subscriptions.reactivate.confirm"

    KEY_SUBSCRIPTIONS_REACTIVATE_SUCCESS = "wa.tenant.subscriptions.reactivate.success"

    KEY_SUBSCRIPTIONS_RENEW_DURATION_PROMPT = "wa.tenant.subscriptions.renew.duration_prompt"

    KEY_SUBSCRIPTIONS_RENEW_CUSTOM_DATE_PROMPT = "wa.tenant.subscriptions.renew.custom_date"

    KEY_SUBSCRIPTIONS_RENEW_CONFIRM_TEMPLATE = "wa.tenant.subscriptions.renew.confirm"

    KEY_SUBSCRIPTIONS_RENEW_SUCCESS = "wa.tenant.subscriptions.renew.success"

    KEY_SUBSCRIPTIONS_INVALID_SELECTION = "wa.tenant.subscriptions.invalid_selection"

    KEY_SUBSCRIPTIONS_CONFIRM_REPROMPT = "wa.tenant.subscriptions.confirm_reprompt"

    KEY_SUBSCRIPTIONS_EMAIL_REQUIRED = "wa.tenant.subscriptions.email_required"

    KEY_SUBSCRIPTIONS_CLIENT_REQUIRED = "wa.tenant.subscriptions.client_required"

    SUBSCRIPTIONS_SKIP_WORDS = {"—", "skip", "ninguno", "none", "-"}

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
    # i18n helper (reads locale from per-message ContextVar)
    # ------------------------------------------------------------------

    def _t(self, key: str, /, **params: Any) -> str:
        """Translate *key* in the current message locale."""
        return _i18n_t(_current_locale.get(), key, **params)

    # ------------------------------------------------------------------
    # Reply composition helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _with_main_menu(message: str, locale: str | None = None) -> str:
        """Append the main menu to *message*, translated to *locale*."""
        loc = locale if locale is not None else _current_locale.get()
        return message.rstrip() + "\n\n" + _i18n_t(loc, WhatsAppTenantConsoleService.KEY_MAIN_MENU)

    @staticmethod
    def _format_client_list(clients: list[Any]) -> tuple[str, dict[str, str]]:
        entries: list[str] = []
        selection_map: dict[str, str] = {}
        active_count = 0
        loc = _current_locale.get()
        for i, c in enumerate(clients, start=1):
            num = str(i)
            status = _i18n_t(loc, "wa.tenant.status.active") if c.is_active else _i18n_t(loc, "wa.tenant.status.inactive")
            entries.append(f"{num}️⃣ {c.full_name} ({status})")
            selection_map[num] = str(c.id)
            if c.is_active:
                active_count += 1
        inactive_count = len(clients) - active_count
        header = _i18n_t(loc, "wa.tenant.clients.list.header", active_count=active_count, inactive_count=inactive_count)
        return header + "\n".join(entries), selection_map

    @staticmethod
    def _format_client_detail(client: Any) -> str:
        loc = _current_locale.get()
        status_emoji = _i18n_t(loc, "wa.tenant.clients.detail.status_active") if client.is_active else _i18n_t(loc, "wa.tenant.clients.detail.status_inactive")
        actions = (
            _i18n_t(loc, WhatsAppTenantConsoleService.KEY_CLIENT_DETAIL_ACTIVE_ACTIONS)
            if client.is_active
            else _i18n_t(loc, WhatsAppTenantConsoleService.KEY_CLIENT_DETAIL_INACTIVE_ACTIONS)
        )
        phone = client.phone or "—"
        username = (
            getattr(client, "local_username", None)
            or getattr(client.user, "username", "—")
        )
        created = ""
        if client.created_at:
            if isinstance(client.created_at, datetime):
                created = client.created_at.strftime("%Y-%m-%d")
            else:
                created = str(client.created_at)
        return (
            f"{_i18n_t(loc, 'wa.tenant.clients.detail.header')}\n\n"
            f"*Nombre:* {client.full_name}\n"
            f"*Usuario:* {username}\n"
            f"*Teléfono:* {phone}\n"
            f"*Estado:* {status_emoji}\n"
            f"*Creado:* {created}\n\n"
            f"{actions}"
        )

    @staticmethod
    def _format_service_list(services: list[Any]) -> tuple[str, dict[str, str]]:
        entries: list[str] = []
        selection_map: dict[str, str] = {}
        for i, s in enumerate(services, start=1):
            num = str(i)
            entries.append(f"{num}️⃣ {s.name}")
            selection_map[num] = str(s.id)
        return "📋 *Servicios*\n\n" + "\n".join(entries), selection_map

    @staticmethod
    def _format_service_detail(service: Any) -> str:
        return (
            f"📦 *Servicio*\n\n"
            f"*Nombre:* {service.name}\n"
            f"*ID:* {str(service.id)[:8]}...\n"
        )

    @staticmethod
    def _format_plan_list(plans: list[Any]) -> tuple[str, dict[str, str]]:
        entries: list[str] = []
        selection_map: dict[str, str] = {}
        for i, p in enumerate(plans, start=1):
            num = str(i)
            entries.append(f"{num}️⃣ {p.name}")
            selection_map[num] = str(p.id)
        return "📋 *Planes*\n\n" + "\n".join(entries), selection_map

    @staticmethod
    def _format_plan_detail(plan: Any) -> str:
        return (
            f"📄 *Plan*\n\n"
            f"*Nombre:* {plan.name}\n"
        )

    @staticmethod
    def _format_profile_detail(profile: Any, username: str) -> str:
        return (
            f"👤 *Mi Perfil*\n\n"
            f"*Usuario:* {username}\n"
            f"*Nombre:* {profile.full_name or profile.name or '—'}\n"
            f"*Email:* {profile.email or '—'}\n"
            f"*Teléfono:* {profile.phone or '—'}\n"
        )

    @staticmethod
    def _format_subscription_list(
        subscriptions: list[Any], show_status: bool = True
    ) -> tuple[str, dict[str, str]]:
        entries: list[str] = []
        selection_map: dict[str, str] = {}
        for i, sub in enumerate(subscriptions, start=1):
            num = str(i)
            status_emoji = {
                "active": "✅",
                "expired": "⏰",
                "cancelled": "❌",
            }.get(sub.status, "❓")
            label = f"{status_emoji} {sub.streaming_email}"
            if show_status:
                status_name = {
                    "active": "Activa",
                    "expired": "Expirada",
                    "cancelled": "Cancelada",
                }.get(sub.status, sub.status)
                label += f" ({status_name})"
            # Optionally show client name
            client_name = getattr(sub, "client_name", None) or getattr(sub, "client_full_name", "")
            if client_name:
                label += f" — {client_name}"
            entries.append(f"{num}️⃣ {label}")
            selection_map[num] = str(sub.id)
        return "📋 *Suscripciones*\n\n" + "\n".join(entries), selection_map

    @staticmethod
    def _format_subscription_detail(sub: Any, credentials: dict | None = None) -> str:
        status_emoji = {
            "active": "✅ Activa",
            "expired": "⏰ Expirada",
            "cancelled": "❌ Cancelada",
        }.get(sub.status, sub.status)

        password_display = "—"
        pin_display = "—"
        if credentials:
            pwd = credentials.get("streaming_password")
            if pwd:
                password_display = pwd
            pin_val = credentials.get("profile_pin")
            if pin_val:
                pin_display = pin_val

        client_name = getattr(sub, "client_name", None) or getattr(sub, "client_full_name", "—")
        service_name = getattr(sub, "service_name", None) or "—"
        plan_name = getattr(sub, "plan_name", None) or "—"

        profile_name = sub.profile_name or "—"

        starts_at = ""
        if sub.starts_at:
            if hasattr(sub.starts_at, "strftime"):
                starts_at = sub.starts_at.strftime("%Y-%m-%d")
            else:
                starts_at = str(sub.starts_at)

        expires_at = ""
        if sub.expires_at:
            if hasattr(sub.expires_at, "strftime"):
                expires_at = sub.expires_at.strftime("%Y-%m-%d")
            else:
                expires_at = str(sub.expires_at)

        duration_labels = {
            "1_month": "1 mes",
            "3_months": "3 meses",
            "6_months": "6 meses",
            "9_months": "9 meses",
            "1_year": "1 año",
            "custom": "Personalizada",
        }
        duration_label = duration_labels.get(sub.duration_type, sub.duration_type)

        return (
            f"📺 *Detalle de Suscripción*\n\n"
            f"*Estado:* {status_emoji}\n"
            f"*Cliente:* {client_name}\n"
            f"*Servicio:* {service_name}\n"
            f"*Plan:* {plan_name}\n"
            f"*Email:* {sub.streaming_email}\n"
            f"*Contraseña:* {password_display}\n"
            f"*Perfil:* {profile_name}\n"
            f"*PIN:* {pin_display}\n"
            f"*Duración:* {duration_label}\n"
            f"*Inicio:* {starts_at}\n"
            f"*Expira:* {expires_at}\n"
        )

    @staticmethod
    def _safe_uuid(value: str | None) -> UUID | None:
        """Convert *value* to ``UUID`` or return ``None`` on failure."""
        if value is None:
            return None
        try:
            return UUID(value)
        except (ValueError, AttributeError):
            return None

    @staticmethod
    def _format_subscription_duration(duration_type: str) -> str:
        return {
            "1_month": "1 mes",
            "3_months": "3 meses",
            "6_months": "6 meses",
            "9_months": "9 meses",
            "1_year": "1 año",
            "custom": "Personalizada",
        }.get(duration_type, duration_type)

    @staticmethod
    def _format_short_date(value: Any) -> str:
        if value is None:
            return "—"
        if hasattr(value, "strftime"):
            return value.strftime("%Y-%m-%d")
        return str(value)

    @staticmethod
    def _calculate_subscription_expiry(
        starts_at: datetime,
        duration_type: str,
        custom_expires_at: datetime | None = None,
    ) -> datetime:
        if duration_type == "custom":
            if custom_expires_at is None:
                raise ValueError("custom duration requires expires_at")
            return custom_expires_at
        duration_days = {
            "1_month": 30,
            "3_months": 90,
            "6_months": 180,
            "9_months": 270,
            "1_year": 365,
        }
        return starts_at + timedelta(days=duration_days[duration_type])

    @staticmethod
    def _parse_iso_date(value: str) -> datetime | None:
        try:
            parsed = datetime.strptime(value.strip(), "%Y-%m-%d")
        except ValueError:
            return None
        return parsed.replace(tzinfo=timezone.utc)

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
    ) -> str:
        """Process a WhatsApp message and return the reply text.

        Args:
            phone: Normalised phone number of the sender.
            message: Text of the WhatsApp message.
            tenant_id: Resolved tenant UUID for scoped operations.
            user_id: Resolved user UUID for profile operations.
            db: Database session for CRUD operations.
            session_service: ``WhatsAppSessionService`` for persistence.
            locale: Tenant locale (``en`` or ``es``). Defaults to contextvar.

        Returns:
            Reply text that n8n will send through Evolution API.
        """
        # Set per-message locale context
        if locale is not None:
            _token = _current_locale.set(locale)
        else:
            _token = None
        msg = message.strip()

        try:
            # Retrieve current session
            session = None
            if session_service is not None:
                session = await session_service.get_session(f"admin:{phone}")

            has_active_flow = session is not None and bool(session.flow)

            # Contextual reset — flow-aware
            if msg.lower() in self.RESET_COMMANDS:
                if session_service is not None:
                    await session_service.clear_session(f"admin:{phone}")
                if has_active_flow:
                    if msg == "0":
                        return self._with_main_menu(_i18n_t(_current_locale.get(), "wa.tenant.cancelled"))
                    return self._with_main_menu(_i18n_t(_current_locale.get(), "wa.tenant.cancelled"))
                if msg == "0":
                    return self._with_main_menu(_i18n_t(_current_locale.get(), "wa.tenant.goodbye"))
                return self._t(self.KEY_MAIN_MENU)

            # Contingency reset — failover, session missing on backup
            if (
                session is None
                and session_service is not None
                and session_service.used_backup
                and msg.lower() not in self.RESET_COMMANDS
            ):
                await session_service.create_session(f"admin:{phone}")
                return ContingencyReplyPolicy.SESSION_RESET

            # Help — reachable from any state
            if msg.lower() in self.HELP_COMMANDS:
                return self._t(self.KEY_HELP_TEXT)

            # Active flow routing
            if has_active_flow:
                return await self._route_active_flow(
                    phone=phone,
                    msg=msg,
                    session=session,
                    session_service=session_service,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    db=db,
                )

            # No active flow — main menu
            if not msg:
                return self._t(self.KEY_MAIN_MENU)

            if msg == "1":
                return await self._start_clients_flow(
                    phone, session_service, tenant_id, db
                )
            elif msg == "2":
                return await self._start_catalog_flow(
                    phone, session_service, tenant_id, db
                )
            elif msg == "3":
                return await self._start_profile_flow(
                    phone, session_service, user_id, db
                )
            elif msg == "4":
                return await self._start_subscriptions_flow(
                    phone, session_service, tenant_id, db
                )
            return self._t(self.KEY_FALLBACK_NO_FLOW)

        except RedisUnavailableError:
            return ContingencyReplyPolicy.TEMPORARY_UNAVAILABLE
        finally:
            if _token is not None:
                _current_locale.reset(_token)

    # ------------------------------------------------------------------
    # Active flow router
    # ------------------------------------------------------------------

    async def _route_active_flow(
        self,
        phone: str,
        msg: str,
        session: Any,
        session_service: WhatsAppSessionService | None,
        tenant_id: UUID | None,
        user_id: UUID | None,
        db: AsyncSession | None,
    ) -> str:
        flow = session.flow
        step = session.step

        # -- Client flows --
        if flow == self.CLIENTS_FLOW:
            if step == self.CLIENTS_STEP_LIST:
                return await self._handle_client_list_selection(
                    phone, msg, session, session_service, tenant_id, db
                )
            elif step == self.CLIENTS_STEP_SELECT:
                return await self._handle_client_select(
                    phone, msg, session, session_service, tenant_id, db
                )
            elif step == self.CLIENTS_STEP_DETAIL_ACTION:
                return await self._handle_client_detail_action(
                    phone, msg, session, session_service, tenant_id, db
                )
            elif step == self.CLIENTS_STEP_CREATE_FULL_NAME:
                return await self._handle_client_create_full_name(
                    phone, msg, session, session_service
                )
            elif step == self.CLIENTS_STEP_CREATE_PHONE:
                return await self._handle_client_create_phone(
                    phone, msg, session, session_service
                )
            elif step == self.CLIENTS_STEP_CREATE_USERNAME:
                return await self._handle_client_create_username(
                    phone, msg, session, session_service
                )
            elif step == self.CLIENTS_STEP_CREATE_PASSWORD:
                return await self._handle_client_create_password(
                    phone, msg, session, session_service
                )
            elif step == self.CLIENTS_STEP_CREATE_CONFIRM:
                return await self._handle_client_create_confirm(
                    phone, msg, session, session_service, tenant_id, db
                )
            elif step == self.CLIENTS_STEP_EDIT_FIELD:
                return await self._handle_client_edit_field(
                    phone, msg, session, session_service
                )
            elif step == self.CLIENTS_STEP_EDIT_VALUE:
                return await self._handle_client_edit_value(
                    phone, msg, session, session_service, tenant_id, db
                )
            elif step == self.CLIENTS_STEP_DEACTIVATE_CONFIRM:
                return await self._handle_client_deactivate_confirm(
                    phone, msg, session, session_service, tenant_id, db
                )
            elif step == self.CLIENTS_STEP_DELETE_CONFIRM:
                return await self._handle_client_delete_confirm(
                    phone, msg, session, session_service, tenant_id, db
                )

        # -- Catalog flows --
        if flow == self.CATALOG_FLOW:
            if step == self.CATALOG_STEP_LIST:
                return self._t(self.KEY_CLIENTS_MENU)  # catalog menu placeholder
            elif step == self.CATALOG_STEP_SERVICE_SELECT:
                return await self._handle_catalog_service_select(
                    phone, msg, session, session_service, tenant_id, db
                )
            elif step == self.CATALOG_STEP_SERVICE_ACTION:
                return await self._handle_catalog_service_action(
                    phone, msg, session, session_service, tenant_id, db
                )
            elif step == self.CATALOG_STEP_EDIT_SERVICE:
                return await self._handle_catalog_edit_service(
                    phone, msg, session, session_service, tenant_id, db
                )
            elif step == self.CATALOG_STEP_PLAN_SELECT:
                return await self._handle_catalog_plan_select(
                    phone, msg, session, session_service, tenant_id, db
                )
            elif step == self.CATALOG_STEP_PLAN_ACTION:
                return await self._handle_catalog_plan_action(
                    phone, msg, session, session_service, tenant_id, db
                )
            elif step == self.CATALOG_STEP_EDIT_PLAN:
                return await self._handle_catalog_edit_plan(
                    phone, msg, session, session_service, tenant_id, db
                )

        # -- Profile flows --
        if flow == self.PROFILE_FLOW:
            if step == self.PROFILE_STEP_ACTION:
                return await self._handle_profile_action(
                    phone, msg, session, session_service, user_id, db
                )
            elif step == self.PROFILE_STEP_EDIT_FIELD:
                return await self._handle_profile_edit_field(
                    phone, msg, session, session_service
                )
            elif step == self.PROFILE_STEP_EDIT_VALUE:
                return await self._handle_profile_edit_value(
                    phone, msg, session, session_service, user_id, db
                )
            elif step == self.PROFILE_STEP_CHANGE_PASSWORD_OLD:
                return await self._handle_profile_change_password_old(
                    phone, msg, session, session_service, user_id, db
                )
            elif step == self.PROFILE_STEP_CHANGE_PASSWORD_NEW:
                return await self._handle_profile_change_password_new(
                    phone, msg, session, session_service, user_id, db
                )
            elif step == self.PROFILE_STEP_CHANGE_LOCALE_SELECT:
                return await self._handle_profile_change_locale_select(
                    phone, msg, session, session_service, user_id, db
                )

        # -- Subscription flows --
        if flow == self.SUBSCRIPTIONS_FLOW:
            if step == self.SUBSCRIPTIONS_STEP_MENU:
                return await self._handle_subscriptions_menu(
                    phone, msg, session, session_service, tenant_id, db
                )
            elif step == self.SUBSCRIPTIONS_STEP_FILTER:
                return await self._handle_subscriptions_filter(
                    phone, msg, session, session_service, tenant_id, db
                )
            elif step == self.SUBSCRIPTIONS_STEP_LIST:
                return await self._handle_subscriptions_list(
                    phone, msg, session, session_service, tenant_id, db
                )
            elif step == self.SUBSCRIPTIONS_STEP_SELECT:
                return await self._handle_subscriptions_select(
                    phone, msg, session, session_service, tenant_id, db
                )
            elif step == self.SUBSCRIPTIONS_STEP_ACTION:
                return await self._handle_subscriptions_action(
                    phone, msg, session, session_service, tenant_id, db
                )
            elif step == self.SUBSCRIPTIONS_STEP_CREATE_CLIENT:
                return await self._handle_subscriptions_create_client(
                    phone, msg, session, session_service, tenant_id, db
                )
            elif step == self.SUBSCRIPTIONS_STEP_CREATE_SERVICE:
                return await self._handle_subscriptions_create_service(
                    phone, msg, session, session_service, tenant_id, db
                )
            elif step == self.SUBSCRIPTIONS_STEP_CREATE_PLAN:
                return await self._handle_subscriptions_create_plan(
                    phone, msg, session, session_service, tenant_id, db
                )
            elif step == self.SUBSCRIPTIONS_STEP_CREATE_EMAIL:
                return await self._handle_subscriptions_create_email(
                    phone, msg, session, session_service
                )
            elif step == self.SUBSCRIPTIONS_STEP_CREATE_PASSWORD:
                return await self._handle_subscriptions_create_password(
                    phone, msg, session, session_service
                )
            elif step == self.SUBSCRIPTIONS_STEP_CREATE_PASSWORD_CONFIRM:
                return await self._handle_subscriptions_create_password_confirm(
                    phone, msg, session, session_service
                )
            elif step == self.SUBSCRIPTIONS_STEP_CREATE_PROFILE_OPTION:
                return await self._handle_subscriptions_create_profile_option(
                    phone, msg, session, session_service
                )
            elif step == self.SUBSCRIPTIONS_STEP_CREATE_PROFILE_NAME:
                return await self._handle_subscriptions_create_profile_name(
                    phone, msg, session, session_service
                )
            elif step == self.SUBSCRIPTIONS_STEP_CREATE_PIN:
                return await self._handle_subscriptions_create_pin(
                    phone, msg, session, session_service
                )
            elif step == self.SUBSCRIPTIONS_STEP_CREATE_PIN_CONFIRM:
                return await self._handle_subscriptions_create_pin_confirm(
                    phone, msg, session, session_service
                )
            elif step == self.SUBSCRIPTIONS_STEP_CREATE_DURATION:
                return await self._handle_subscriptions_create_duration(
                    phone, msg, session, session_service, tenant_id, db
                )
            elif step == self.SUBSCRIPTIONS_STEP_CREATE_CUSTOM_DATE:
                return await self._handle_subscriptions_create_custom_date(
                    phone, msg, session, session_service, tenant_id, db
                )
            elif step == self.SUBSCRIPTIONS_STEP_CREATE_CONFIRM:
                return await self._handle_subscriptions_create_confirm(
                    phone, msg, session, session_service, tenant_id, db
                )
            elif step == self.SUBSCRIPTIONS_STEP_EDIT_FIELD:
                return await self._handle_subscriptions_edit_field(
                    phone, msg, session, session_service, tenant_id, db
                )
            elif step == self.SUBSCRIPTIONS_STEP_EDIT_VALUE:
                return await self._handle_subscriptions_edit_value(
                    phone, msg, session, session_service, tenant_id, db
                )
            elif step == self.SUBSCRIPTIONS_STEP_EDIT_PASSWORD_CONFIRM:
                return await self._handle_subscriptions_edit_password_confirm(
                    phone, msg, session, session_service, tenant_id, db
                )
            elif step == self.SUBSCRIPTIONS_STEP_EDIT_PIN_CONFIRM:
                return await self._handle_subscriptions_edit_pin_confirm(
                    phone, msg, session, session_service, tenant_id, db
                )
            elif step == self.SUBSCRIPTIONS_STEP_CANCEL_CONFIRM:
                return await self._handle_subscriptions_cancel_confirm(
                    phone, msg, session, session_service, tenant_id, db
                )
            elif step == self.SUBSCRIPTIONS_STEP_REACTIVATE_DURATION:
                return await self._handle_subscriptions_reactivate_duration(
                    phone, msg, session, session_service, tenant_id, db
                )
            elif step == self.SUBSCRIPTIONS_STEP_REACTIVATE_CUSTOM_DATE:
                return await self._handle_subscriptions_reactivate_custom_date(
                    phone, msg, session, session_service, tenant_id, db
                )
            elif step == self.SUBSCRIPTIONS_STEP_REACTIVATE_CONFIRM:
                return await self._handle_subscriptions_reactivate_confirm(
                    phone, msg, session, session_service, tenant_id, db
                )
            elif step == self.SUBSCRIPTIONS_STEP_RENEW_DURATION:
                return await self._handle_subscriptions_renew_duration(
                    phone, msg, session, session_service, tenant_id, db
                )
            elif step == self.SUBSCRIPTIONS_STEP_RENEW_CUSTOM_DATE:
                return await self._handle_subscriptions_renew_custom_date(
                    phone, msg, session, session_service, tenant_id, db
                )
            elif step == self.SUBSCRIPTIONS_STEP_RENEW_CONFIRM:
                return await self._handle_subscriptions_renew_confirm(
                    phone, msg, session, session_service, tenant_id, db
                )

        return self._t(self.KEY_FALLBACK_ACTIVE_FLOW)

    # ==================================================================
    # CLIENT FLOWS
    # ==================================================================

    async def _start_clients_flow(
        self,
        phone: str,
        session_service: WhatsAppSessionService | None,
        tenant_id: UUID | None,
        db: AsyncSession | None,
    ) -> str:
        """Start the clients sub-menu."""
        if session_service is not None:
            session = await session_service.get_session(f"admin:{phone}")
            if session is None:
                session = await session_service.create_session(f"admin:{phone}")
            session.flow = self.CLIENTS_FLOW
            session.step = self.CLIENTS_STEP_LIST
            session.temp_data = {}
            await session_service.save_session(session)
        return self._t(self.KEY_CLIENTS_MENU)

    async def _handle_client_list_selection(
        self,
        phone: str,
        msg: str,
        session: Any,
        session_service: WhatsAppSessionService | None,
        tenant_id: UUID | None,
        db: AsyncSession | None,
    ) -> str:
        """Handle the clients sub-menu selection."""
        if msg == "1":
            # Show client list
            if tenant_id is None or db is None or self._client_service is None:
                return self._t(self.KEY_CLIENT_NO_CLIENTS)
            clients = await self._client_service.list_clients(db, tenant_id)
            if not clients:
                return self._with_main_menu(self._t(self.KEY_CLIENT_NO_CLIENTS))
            reply, selection_map = self._format_client_list(clients)
            reply += "\n\n" + self._t(self.KEY_CLIENT_SELECT_PROMPT)
            if session_service is not None:
                session.flow = self.CLIENTS_FLOW
                session.step = self.CLIENTS_STEP_SELECT
                session.selection_map = selection_map
                await session_service.save_session(session)
            return reply
        elif msg == "2":
            # Start client creation
            return await self._start_client_create(phone, session_service)
        elif msg == "0":
            return self._with_main_menu("")
        else:
            client_id = session.selection_map.get(msg)
            if client_id:
                if db is None or self._client_service is None:
                    return self._t(self.KEY_CLIENT_INVALID_SELECTION)
                parsed_id = self._safe_uuid(client_id)
                if parsed_id is None:
                    return self._t(self.KEY_CLIENT_INVALID_SELECTION)
                client = await self._client_service.get_client(db, tenant_id, parsed_id)
                if client:
                    reply = self._format_client_detail(client)
                    if session_service is not None:
                        session.selected_tenant_id = client_id
                        session.step = self.CLIENTS_STEP_DETAIL_ACTION
                        await session_service.save_session(session)
                    return reply
            return self._t(self.KEY_CLIENT_INVALID_SELECTION)

    async def _handle_client_select(
        self,
        phone: str,
        msg: str,
        session: Any,
        session_service: WhatsAppSessionService | None,
        tenant_id: UUID | None,
        db: AsyncSession | None,
    ) -> str:
        """Handle client selection from the numbered list (CLIENTS_STEP_SELECT).

        Only does selection_map lookup — no menu command checks.
        '0' is handled by the global reset in process_message().
        """
        client_id = session.selection_map.get(msg)
        if client_id:
            if db is None or self._client_service is None:
                return self._t(self.KEY_CLIENT_INVALID_SELECTION)
            parsed_id = self._safe_uuid(client_id)
            if parsed_id is None:
                return self._t(self.KEY_CLIENT_INVALID_SELECTION)
            client = await self._client_service.get_client(
                db, tenant_id, parsed_id
            )
            if client:
                reply = self._format_client_detail(client)
                if session_service is not None:
                    session.selected_tenant_id = client_id
                    session.step = self.CLIENTS_STEP_DETAIL_ACTION
                    await session_service.save_session(session)
                return reply
        return self._t(self.KEY_CLIENT_INVALID_SELECTION)

    async def _handle_client_detail_action(
        self,
        phone: str,
        msg: str,
        session: Any,
        session_service: WhatsAppSessionService | None,
        tenant_id: UUID | None,
        db: AsyncSession | None,
    ) -> str:
        """Handle action from client detail screen."""
        client_id = session.selected_tenant_id
        if not client_id:
            return self._t(self.KEY_CLIENT_INVALID_SELECTION)

        parsed_id = self._safe_uuid(client_id)
        if parsed_id is None:
            return self._t(self.KEY_CLIENT_INVALID_SELECTION)

        if msg == "1":
            # Edit flow
            return await self._start_client_edit(phone, session, session_service)
        elif msg == "2":
            # Deactivate or reactivate
            if db is None or self._client_service is None:
                return self._t(self.KEY_CLIENT_INVALID_SELECTION)
            client = await self._client_service.get_client(db, tenant_id, parsed_id)
            if client is None:
                return self._t(self.KEY_CLIENT_INVALID_SELECTION)
            if client.is_active:
                session.flow = self.CLIENTS_FLOW
                session.step = self.CLIENTS_STEP_DEACTIVATE_CONFIRM
                if session_service is not None:
                    await session_service.save_session(session)
                return self._t(self.KEY_CLIENT_DEACTIVATE_CONFIRM_TEMPLATE, name=client.full_name)
            else:
                # Reactivate immediately
                await self._client_service.activate_client(db, tenant_id, parsed_id)
                if session_service is not None:
                    await session_service.clear_session(f"admin:{phone}")
                return self._with_main_menu(
                    self._t(self.KEY_CLIENT_REACTIVATE_SUCCESS, name=client.full_name)
                )
        elif msg == "3":
            # Delete
            if db is None or self._client_service is None:
                return self._t(self.KEY_CLIENT_INVALID_SELECTION)
            client = await self._client_service.get_client(db, tenant_id, parsed_id)
            if client is None:
                return self._t(self.KEY_CLIENT_INVALID_SELECTION)
            if client.is_active:
                return self._t(self.KEY_CLIENT_CANT_DELETE_ACTIVE)
            session.flow = self.CLIENTS_FLOW
            session.step = self.CLIENTS_STEP_DELETE_CONFIRM
            if session_service is not None:
                await session_service.save_session(session)
            return self._t(self.KEY_CLIENT_DELETE_CONFIRM_TEMPLATE, name=client.full_name)
        elif msg == "0":
            if session_service is not None:
                await session_service.clear_session(f"admin:{phone}")
            return self._t(self.KEY_MAIN_MENU)
        return ""

    # -- Client create helpers --

    async def _start_client_create(
        self,
        phone: str,
        session_service: WhatsAppSessionService | None,
    ) -> str:
        if session_service is not None:
            session = await session_service.get_session(f"admin:{phone}")
            if session is None:
                session = await session_service.create_session(f"admin:{phone}")
            session.flow = self.CLIENTS_FLOW
            session.step = self.CLIENTS_STEP_CREATE_FULL_NAME
            session.temp_data = {}
            await session_service.save_session(session)
        return self._t(self.KEY_CLIENT_CREATE_PROMPT_FULL_NAME)

    async def _handle_client_create_full_name(
        self,
        phone: str,
        msg: str,
        session: Any,
        session_service: WhatsAppSessionService | None,
    ) -> str:
        name = msg.strip()
        if not name:
            return self._t(self.KEY_CLIENT_NAME_REQUIRED)
        session.temp_data["full_name"] = name
        session.step = self.CLIENTS_STEP_CREATE_PHONE
        if session_service is not None:
            await session_service.save_session(session)
        return self._t(self.KEY_CLIENT_CREATE_PROMPT_PHONE)

    async def _handle_client_create_phone(
        self,
        phone: str,
        msg: str,
        session: Any,
        session_service: WhatsAppSessionService | None,
    ) -> str:
        stripped = msg.strip()
        if not stripped or stripped.lower() in self.CLIENT_SKIP_WORDS:
            session.temp_data["phone"] = None
        else:
            from app.core.input_validation import validate_phone
            try:
                normalized = validate_phone(stripped, required=False)
                session.temp_data["phone"] = normalized
            except Exception:
                return self._t(self.KEY_CLIENT_CREATE_ERROR_PHONE)
        session.step = self.CLIENTS_STEP_CREATE_USERNAME
        if session_service is not None:
            await session_service.save_session(session)
        return self._t(self.KEY_CLIENT_CREATE_PROMPT_USERNAME)

    async def _handle_client_create_username(
        self,
        phone: str,
        msg: str,
        session: Any,
        session_service: WhatsAppSessionService | None,
    ) -> str:
        username = msg.strip()
        if not username:
            return self._t(self.KEY_CLIENT_USERNAME_REQUIRED)
        session.temp_data["local_username"] = username.lower()
        session.step = self.CLIENTS_STEP_CREATE_PASSWORD
        if session_service is not None:
            await session_service.save_session(session)
        return self._t(self.KEY_CLIENT_CREATE_PROMPT_PASSWORD)

    async def _handle_client_create_password(
        self,
        phone: str,
        msg: str,
        session: Any,
        session_service: WhatsAppSessionService | None,
    ) -> str:
        password = msg.strip()
        if len(password) < 6:
            return self._t(self.KEY_CLIENT_SHORT_PASSWORD)
        session.temp_data["password"] = password
        session.step = self.CLIENTS_STEP_CREATE_CONFIRM
        if session_service is not None:
            await session_service.save_session(session)
        data = session.temp_data
        return self._t(self.KEY_CLIENT_CREATE_CONFIRM_TEMPLATE, 
            name=data.get("full_name", ""),
            username=data.get("local_username", ""),
            phone=data.get("phone") or "—",
        )

    async def _handle_client_create_confirm(
        self,
        phone: str,
        msg: str,
        session: Any,
        session_service: WhatsAppSessionService | None,
        tenant_id: UUID | None,
        db: AsyncSession | None,
    ) -> str:
        stripped = msg.strip()
        if stripped.upper() not in ("CONFIRMAR", "CONFIRM"):
            data = session.temp_data
            return (
                self._t(self.KEY_CLIENT_CONFIRM_REPROMPT) + "\n\n"
                + self._t(self.KEY_CLIENT_CREATE_CONFIRM_TEMPLATE, 
                    name=data.get("full_name", ""),
                    username=data.get("local_username", ""),
                    phone=data.get("phone") or "—",
                )
            )
        data = session.temp_data
        if tenant_id is None or db is None or self._client_service is None:
            return self._t("wa.tenant.errors.client_create_service_unavailable")

        from app.schemas.client import ClientCreate

        payload = ClientCreate(
            full_name=data.get("full_name", ""),
            local_username=data.get("local_username", ""),
            phone=data.get("phone"),
            password=data.get("password", ""),
        )
        try:
            client = await self._client_service.create_client(db, tenant_id, payload)
        except UserFacingError as exc:
            error = translate_error(_current_locale.get(), exc)
            if exc.code in {"phone_already_registered", "client_local_username_exists", "username_already_registered"}:
                if exc.code == "phone_already_registered":
                    session.step = self.CLIENTS_STEP_CREATE_PHONE
                    if session_service is not None:
                        await session_service.save_session(session)
                    return "❌ " + error + "\n\n" + self._t(self.KEY_CLIENT_CREATE_PROMPT_PHONE)
                session.step = self.CLIENTS_STEP_CREATE_USERNAME
                if session_service is not None:
                    await session_service.save_session(session)
                return "❌ " + error + "\n\n" + self._t(self.KEY_CLIENT_CREATE_PROMPT_USERNAME)
            return "❌ " + error
        except ValueError as exc:
            error = str(exc)
            if "phone" in error.lower() or "teléfono" in error.lower():
                session.step = self.CLIENTS_STEP_CREATE_PHONE
                if session_service is not None:
                    await session_service.save_session(session)
                return "❌ " + error + "\n\n" + self._t(self.KEY_CLIENT_CREATE_PROMPT_PHONE)
            if "username" in error.lower() or "usuario" in error.lower():
                session.step = self.CLIENTS_STEP_CREATE_USERNAME
                if session_service is not None:
                    await session_service.save_session(session)
                return "❌ " + error + "\n\n" + self._t(self.KEY_CLIENT_CREATE_PROMPT_USERNAME)
            return "❌ " + error

        if client is None:
            return self._t("wa.tenant.errors.client_create_failed_generic")

        if session_service is not None:
            await session_service.clear_session(f"admin:{phone}")

        full_username = getattr(client.user, "username", data.get("local_username", ""))
        return self._with_main_menu(
            self._t(self.KEY_CLIENT_CREATE_SUCCESS, 
                name=client.full_name,
                username_full=full_username,
                phone=client.phone or "—",
            )
        )

    # -- Client edit helpers --

    async def _start_client_edit(
        self,
        phone: str,
        session: Any,
        session_service: WhatsAppSessionService | None,
    ) -> str:
        session.flow = self.CLIENTS_FLOW
        session.step = self.CLIENTS_STEP_EDIT_FIELD
        session.temp_data = {}
        if session_service is not None:
            await session_service.save_session(session)
        return self._t(self.KEY_CLIENT_EDIT_FIELD_PROMPT)

    async def _handle_client_edit_field(
        self,
        phone: str,
        msg: str,
        session: Any,
        session_service: WhatsAppSessionService | None,
    ) -> str:
        if msg == "0":
            if session_service is not None:
                await session_service.clear_session(f"admin:{phone}")
            return self._t(self.KEY_MAIN_MENU)
        field = self.CLIENT_EDIT_FIELD_MAP.get(msg)
        if field is None:
            return self._t(self.KEY_CLIENT_EDIT_ERROR_INVALID_FIELD)
        session.temp_data["field"] = field
        session.step = self.CLIENTS_STEP_EDIT_VALUE
        if session_service is not None:
            await session_service.save_session(session)
        return self.CLIENT_EDIT_PROMPTS[field]

    async def _handle_client_edit_value(
        self,
        phone: str,
        msg: str,
        session: Any,
        session_service: WhatsAppSessionService | None,
        tenant_id: UUID | None,
        db: AsyncSession | None,
    ) -> str:
        field = session.temp_data.get("field", "")
        new_value = msg.strip()
        client_id = session.selected_tenant_id
        if not client_id or tenant_id is None or db is None or self._client_service is None:
            return self._t("wa.tenant.errors.client_update_failed")
        parsed_id = self._safe_uuid(client_id)
        if parsed_id is None:
            return self._t("wa.tenant.errors.client_update_failed")

        from app.schemas.client import ClientUpdate
        payload = ClientUpdate(**{field: new_value})
        try:
            client = await self._client_service.update_client(
                db, tenant_id, parsed_id, payload
            )
        except UserFacingError as exc:
            return "❌ " + translate_error(_current_locale.get(), exc)
        except ValueError as exc:
            return "❌ " + str(exc)
        except Exception as exc:
            return "❌ " + str(exc)

        if client is None:
            return self._t("wa.tenant.errors.client_not_found")

        if session_service is not None:
            await session_service.clear_session(f"admin:{phone}")
        return self._with_main_menu(
            self._t(self.KEY_CLIENT_EDIT_SUCCESS, name=client.full_name)
        )

    # -- Client lifecycle helpers --

    async def _handle_client_deactivate_confirm(
        self,
        phone: str,
        msg: str,
        session: Any,
        session_service: WhatsAppSessionService | None,
        tenant_id: UUID | None,
        db: AsyncSession | None,
    ) -> str:
        stripped = msg.strip()
        if stripped.upper() not in ("CONFIRMAR", "CONFIRM"):
            return self._t(self.KEY_CLIENT_CONFIRM_REPROMPT)
        client_id = session.selected_tenant_id
        if not client_id or tenant_id is None or db is None or self._client_service is None:
            return self._t("wa.tenant.errors.client_deactivate_failed")
        parsed_id = self._safe_uuid(client_id)
        if parsed_id is None:
            return self._t("wa.tenant.errors.client_deactivate_failed")
        client = await self._client_service.deactivate_client(db, tenant_id, parsed_id)
        if client is None:
            return self._t("wa.tenant.errors.client_not_found")
        if session_service is not None:
            await session_service.clear_session(f"admin:{phone}")
        return self._with_main_menu(
            self._t(self.KEY_CLIENT_DEACTIVATE_SUCCESS, name=client.full_name)
        )

    async def _handle_client_delete_confirm(
        self,
        phone: str,
        msg: str,
        session: Any,
        session_service: WhatsAppSessionService | None,
        tenant_id: UUID | None,
        db: AsyncSession | None,
    ) -> str:
        stripped = msg.strip()
        if stripped.upper() not in ("CONFIRMAR", "CONFIRM"):
            return self._t(self.KEY_CLIENT_CONFIRM_REPROMPT)
        client_id = session.selected_tenant_id
        if not client_id or tenant_id is None or db is None or self._client_service is None:
            return self._t("wa.tenant.errors.client_delete_failed")
        parsed_id = self._safe_uuid(client_id)
        if parsed_id is None:
            return self._t("wa.tenant.errors.client_delete_failed")
        client_name = client_id  # fallback
        client = await self._client_service.get_client(db, tenant_id, parsed_id)
        if client:
            client_name = client.full_name
        deleted = await self._client_service.delete_client(db, tenant_id, parsed_id)
        if not deleted:
            return self._t("wa.tenant.errors.client_delete_failed")
        if session_service is not None:
            await session_service.clear_session(f"admin:{phone}")
        return self._with_main_menu(
            self._t(self.KEY_CLIENT_DELETE_SUCCESS, name=client_name)
        )

    # ==================================================================
    # CATALOG FLOWS
    # ==================================================================

    async def _start_catalog_flow(
        self,
        phone: str,
        session_service: WhatsAppSessionService | None,
        tenant_id: UUID | None,
        db: AsyncSession | None,
    ) -> str:
        """Start the catalog flow — list services immediately."""
        reply, selection_map = await self._fetch_service_list(tenant_id, db)
        if reply is None:
            return self._with_main_menu(self._t(self.KEY_CATALOG_NO_SERVICES))
        if session_service is not None:
            session = await session_service.get_session(f"admin:{phone}")
            if session is None:
                session = await session_service.create_session(f"admin:{phone}")
            session.flow = self.CATALOG_FLOW
            session.step = self.CATALOG_STEP_SERVICE_SELECT
            session.selection_map = selection_map
            await session_service.save_session(session)
        return reply + "\n\n" + self._t(self.KEY_CATALOG_SERVICE_PROMPT)

    async def _fetch_service_list(
        self, tenant_id: UUID | None, db: AsyncSession | None
    ) -> tuple[str | None, dict[str, str]]:
        if tenant_id is None or db is None or self._catalog_service is None:
            return None, {}
        services = await self._catalog_service.list_services(db, tenant_id)
        if not services:
            return None, {}
        reply, selection_map = self._format_service_list(services)
        return reply, selection_map

    async def _handle_catalog_service_select(
        self,
        phone: str,
        msg: str,
        session: Any,
        session_service: WhatsAppSessionService | None,
        tenant_id: UUID | None,
        db: AsyncSession | None,
    ) -> str:
        if msg == "0":
            if session_service is not None:
                await session_service.clear_session(f"admin:{phone}")
            return self._t(self.KEY_MAIN_MENU)
        service_id = session.selection_map.get(msg)
        if not service_id or tenant_id is None or db is None or self._catalog_service is None:
            return self._t(self.KEY_CATALOG_INVALID_SELECTION)
        parsed_id = self._safe_uuid(service_id)
        if parsed_id is None:
            return self._t(self.KEY_CATALOG_INVALID_SELECTION)
        service = await self._catalog_service.get_service(db, tenant_id, parsed_id)
        if service is None:
            return self._t(self.KEY_CATALOG_INVALID_SELECTION)
        session.flow = self.CATALOG_FLOW
        session.step = self.CATALOG_STEP_SERVICE_ACTION
        session.selected_tenant_id = service_id
        if session_service is not None:
            await session_service.save_session(session)
        return (
            self._format_service_detail(service) + "\n"
            + self._t(self.KEY_CATALOG_SERVICE_ACTIONS)
        )

    async def _handle_catalog_service_action(
        self,
        phone: str,
        msg: str,
        session: Any,
        session_service: WhatsAppSessionService | None,
        tenant_id: UUID | None,
        db: AsyncSession | None,
    ) -> str:
        service_id = session.selected_tenant_id
        if not service_id:
            return self._t(self.KEY_CATALOG_INVALID_SELECTION)
        if msg == "1":
            # Edit service name
            session.flow = self.CATALOG_FLOW
            session.step = self.CATALOG_STEP_EDIT_SERVICE
            if session_service is not None:
                await session_service.save_session(session)
            return self._t(self.KEY_CATALOG_SERVICE_EDIT_PROMPT)
        elif msg == "2":
            # View plans
            if tenant_id is None or db is None or self._catalog_service is None:
                return self._t(self.KEY_CATALOG_NO_PLANS)
            parsed_id = self._safe_uuid(service_id)
            if parsed_id is None:
                return self._t(self.KEY_CATALOG_INVALID_SELECTION)
            plans = await self._catalog_service.list_plans(db, tenant_id, parsed_id)
            if not plans:
                return self._with_main_menu(self._t(self.KEY_CATALOG_NO_PLANS))
            reply, selection_map = self._format_plan_list(plans)
            session.flow = self.CATALOG_FLOW
            session.step = self.CATALOG_STEP_PLAN_SELECT
            session.selection_map = selection_map
            if session_service is not None:
                await session_service.save_session(session)
            return reply + "\n\n" + self._t(self.KEY_CATALOG_PLAN_PROMPT)
        elif msg == "0":
            if session_service is not None:
                await session_service.clear_session(f"admin:{phone}")
            return self._t(self.KEY_MAIN_MENU)
        return self._t(self.KEY_CATALOG_INVALID_SELECTION)

    async def _handle_catalog_edit_service(
        self,
        phone: str,
        msg: str,
        session: Any,
        session_service: WhatsAppSessionService | None,
        tenant_id: UUID | None,
        db: AsyncSession | None,
    ) -> str:
        name = msg.strip()
        if not name:
            return self._t(self.KEY_CATALOG_NAME_REQUIRED)
        service_id = session.selected_tenant_id
        if not service_id or tenant_id is None or db is None or self._catalog_service is None:
            return self._t("wa.tenant.errors.service_update_failed")
        parsed_id = self._safe_uuid(service_id)
        if parsed_id is None:
            return self._t("wa.tenant.errors.service_update_failed")
        from app.schemas.catalog import ServiceUpdate
        try:
            service = await self._catalog_service.update_service(
                db, tenant_id, parsed_id, ServiceUpdate(name=name)
            )
        except UserFacingError as exc:
            return "❌ " + translate_error(_current_locale.get(), exc)
        except ValueError as exc:
            return "❌ " + str(exc)
        if service is None:
            return self._t("wa.tenant.errors.service_not_found")
        if session_service is not None:
            await session_service.clear_session(f"admin:{phone}")
        return self._with_main_menu(
            self._t(self.KEY_CATALOG_SERVICE_EDIT_SUCCESS, name=service.name)
        )

    async def _handle_catalog_plan_select(
        self,
        phone: str,
        msg: str,
        session: Any,
        session_service: WhatsAppSessionService | None,
        tenant_id: UUID | None,
        db: AsyncSession | None,
    ) -> str:
        if msg == "0":
            # Back to service list
            reply, selection_map = await self._fetch_service_list(tenant_id, db)
            if reply is None:
                if session_service is not None:
                    await session_service.clear_session(f"admin:{phone}")
                return self._t(self.KEY_MAIN_MENU)
            session.flow = self.CATALOG_FLOW
            session.step = self.CATALOG_STEP_SERVICE_SELECT
            session.selection_map = selection_map
            if session_service is not None:
                await session_service.save_session(session)
            return reply + "\n\n" + self._t(self.KEY_CATALOG_SERVICE_PROMPT)
        plan_id = session.selection_map.get(msg)
        if not plan_id or tenant_id is None or db is None or self._catalog_service is None:
            return self._t(self.KEY_CATALOG_INVALID_SELECTION)
        # We need the service_id from the session
        service_id = session.selected_tenant_id
        if service_id is None:
            return self._t(self.KEY_CATALOG_INVALID_SELECTION)
        parsed_service_id = self._safe_uuid(service_id)
        parsed_plan_id = self._safe_uuid(plan_id)
        if parsed_service_id is None or parsed_plan_id is None:
            return self._t(self.KEY_CATALOG_INVALID_SELECTION)
        plan = await self._catalog_service.get_plan(
            db, tenant_id, parsed_service_id, parsed_plan_id
        )
        if plan is None:
            return self._t(self.KEY_CATALOG_INVALID_SELECTION)
        session.flow = self.CATALOG_FLOW
        session.step = self.CATALOG_STEP_PLAN_ACTION
        session.selected_tenant_id = plan_id
        if session_service is not None:
            await session_service.save_session(session)
        session.temp_data["service_id"] = service_id  # preserve for later
        if session_service is not None:
            await session_service.save_session(session)
        return (
            self._format_plan_detail(plan) + "\n"
            + self._t(self.KEY_CATALOG_PLAN_ACTIONS)
        )

    async def _handle_catalog_plan_action(
        self,
        phone: str,
        msg: str,
        session: Any,
        session_service: WhatsAppSessionService | None,
        tenant_id: UUID | None,
        db: AsyncSession | None,
    ) -> str:
        plan_id = session.selected_tenant_id
        if not plan_id:
            return self._t(self.KEY_CATALOG_INVALID_SELECTION)
        if msg == "1":
            session.flow = self.CATALOG_FLOW
            session.step = self.CATALOG_STEP_EDIT_PLAN
            if session_service is not None:
                await session_service.save_session(session)
            return self._t(self.KEY_CATALOG_PLAN_EDIT_PROMPT)
        elif msg == "0":
            # Back to service list
            reply, selection_map = await self._fetch_service_list(tenant_id, db)
            if reply is None:
                if session_service is not None:
                    await session_service.clear_session(f"admin:{phone}")
                return self._t(self.KEY_MAIN_MENU)
            session.flow = self.CATALOG_FLOW
            session.step = self.CATALOG_STEP_SERVICE_SELECT
            session.selection_map = selection_map
            if session_service is not None:
                await session_service.save_session(session)
            return reply + "\n\n" + self._t(self.KEY_CATALOG_SERVICE_PROMPT)
        return self._t(self.KEY_CATALOG_INVALID_SELECTION)

    async def _handle_catalog_edit_plan(
        self,
        phone: str,
        msg: str,
        session: Any,
        session_service: WhatsAppSessionService | None,
        tenant_id: UUID | None,
        db: AsyncSession | None,
    ) -> str:
        name = msg.strip()
        if not name:
            return self._t(self.KEY_CATALOG_NAME_REQUIRED)
        plan_id = session.selected_tenant_id
        service_id = session.temp_data.get("service_id")
        if not plan_id or not service_id or tenant_id is None or db is None or self._catalog_service is None:
            return self._t("wa.tenant.errors.plan_update_failed")
        parsed_service_id = self._safe_uuid(service_id)
        parsed_plan_id = self._safe_uuid(plan_id)
        if parsed_service_id is None or parsed_plan_id is None:
            return self._t("wa.tenant.errors.plan_update_failed")
        from app.schemas.catalog import PlanUpdate
        try:
            plan = await self._catalog_service.update_plan(
                db, tenant_id, parsed_service_id, parsed_plan_id, PlanUpdate(name=name)
            )
        except UserFacingError as exc:
            return "❌ " + translate_error(_current_locale.get(), exc)
        except ValueError as exc:
            return "❌ " + str(exc)
        if plan is None:
            return self._t("wa.tenant.errors.plan_not_found")
        if session_service is not None:
            await session_service.clear_session(f"admin:{phone}")
        return self._with_main_menu(
            self._t(self.KEY_CATALOG_PLAN_EDIT_SUCCESS, name=plan.name)
        )

    # ==================================================================
    # SUBSCRIPTION FLOWS
    # ==================================================================

    async def _start_subscriptions_flow(
        self,
        phone: str,
        session_service: WhatsAppSessionService | None,
        tenant_id: UUID | None,
        db: AsyncSession | None,
    ) -> str:
        """Start the subscriptions sub-menu."""
        if session_service is not None:
            session = await session_service.get_session(f"admin:{phone}")
            if session is None:
                session = await session_service.create_session(f"admin:{phone}")
            session.flow = self.SUBSCRIPTIONS_FLOW
            session.step = self.SUBSCRIPTIONS_STEP_MENU
            session.temp_data = {}
            await session_service.save_session(session)
        return self._t(self.KEY_SUBSCRIPTIONS_MENU)

    async def _handle_subscriptions_menu(
        self,
        phone: str,
        msg: str,
        session: Any,
        session_service: WhatsAppSessionService | None,
        tenant_id: UUID | None,
        db: AsyncSession | None,
    ) -> str:
        if msg == "1":
            session.step = self.SUBSCRIPTIONS_STEP_FILTER
            if session_service is not None:
                await session_service.save_session(session)
            return self._t(self.KEY_SUBSCRIPTIONS_FILTER_PROMPT)
        if msg == "2":
            return await self._start_subscriptions_create(
                phone, session, session_service, tenant_id, db
            )
        return self._t(self.KEY_SUBSCRIPTIONS_INVALID_SELECTION)

    async def _handle_subscriptions_filter(
        self,
        phone: str,
        msg: str,
        session: Any,
        session_service: WhatsAppSessionService | None,
        tenant_id: UUID | None,
        db: AsyncSession | None,
    ) -> str:
        del phone
        if tenant_id is None or db is None or self._subscription_service is None:
            return self._t(self.KEY_SUBSCRIPTIONS_NO_RESULTS)

        subscriptions: list[Any]
        if msg == "1":
            subscriptions = await self._subscription_service.list_subscriptions(
                db, tenant_id, status="active"
            )
        elif msg == "2":
            subscriptions = await self._subscription_service.list_subscriptions(
                db, tenant_id, status="expired"
            )
        elif msg == "3":
            subscriptions = await self._subscription_service.list_subscriptions(
                db, tenant_id, status="cancelled"
            )
        elif msg == "4":
            active = await self._subscription_service.list_subscriptions(
                db, tenant_id, status="active"
            )
            expired = await self._subscription_service.list_subscriptions(
                db, tenant_id, status="expired"
            )
            cancelled = await self._subscription_service.list_subscriptions(
                db, tenant_id, status="cancelled"
            )
            subscriptions = [*active, *expired, *cancelled]
        else:
            return self._t(self.KEY_SUBSCRIPTIONS_INVALID_SELECTION)

        if not subscriptions:
            return self._t(self.KEY_SUBSCRIPTIONS_NO_RESULTS) + "\n\n" + self._t(self.KEY_SUBSCRIPTIONS_FILTER_PROMPT)

        reply, selection_map = self._format_subscription_list(subscriptions)
        session.selection_map = selection_map
        session.step = self.SUBSCRIPTIONS_STEP_SELECT
        if session_service is not None:
            await session_service.save_session(session)
        return reply + "\n\n" + self._t(self.KEY_SUBSCRIPTIONS_SELECT_PROMPT)

    async def _handle_subscriptions_list(
        self,
        phone: str,
        msg: str,
        session: Any,
        session_service: WhatsAppSessionService | None,
        tenant_id: UUID | None,
        db: AsyncSession | None,
    ) -> str:
        return await self._handle_subscriptions_select(
            phone, msg, session, session_service, tenant_id, db
        )

    async def _handle_subscriptions_select(
        self,
        phone: str,
        msg: str,
        session: Any,
        session_service: WhatsAppSessionService | None,
        tenant_id: UUID | None,
        db: AsyncSession | None,
    ) -> str:
        del phone
        subscription_id = session.selection_map.get(msg)
        parsed_id = self._safe_uuid(subscription_id)
        if (
            parsed_id is None
            or tenant_id is None
            or db is None
            or self._subscription_service is None
        ):
            return self._t(self.KEY_SUBSCRIPTIONS_INVALID_SELECTION)

        subscription = await self._subscription_service.get_subscription(
            db, tenant_id, parsed_id
        )
        if subscription is None:
            return self._t(self.KEY_SUBSCRIPTIONS_INVALID_SELECTION)

        credentials = await self._subscription_service.reveal_credentials(
            db, tenant_id, parsed_id
        )
        reply = self._format_subscription_detail(subscription, credentials)
        actions = (
            self._t(self.KEY_SUBSCRIPTION_DETAIL_ACTIONS)
            if subscription.status == "cancelled"
            else self._t(self.KEY_SUBSCRIPTION_DETAIL_ACTIONS_ACTIVE)
        )

        session.selected_tenant_id = str(parsed_id)
        session.step = self.SUBSCRIPTIONS_STEP_ACTION
        if session_service is not None:
            await session_service.save_session(session)
        return reply + "\n" + actions

    async def _handle_subscriptions_action(
        self,
        phone: str,
        msg: str,
        session: Any,
        session_service: WhatsAppSessionService | None,
        tenant_id: UUID | None,
        db: AsyncSession | None,
    ) -> str:
        subscription = await self._get_selected_subscription(session, tenant_id, db)
        if subscription is None:
            return self._t(self.KEY_SUBSCRIPTIONS_INVALID_SELECTION)

        if msg == "1":
            session.step = self.SUBSCRIPTIONS_STEP_EDIT_FIELD
            session.temp_data = {}
            if session_service is not None:
                await session_service.save_session(session)
            return self._t(self.KEY_SUBSCRIPTIONS_EDIT_FIELD_PROMPT)

        if msg == "2":
            session.step = self.SUBSCRIPTIONS_STEP_CANCEL_CONFIRM
            if session_service is not None:
                await session_service.save_session(session)
            client_name = getattr(subscription, "client_name", None) or getattr(
                subscription, "client_full_name", "—"
            )
            return self._t(self.KEY_SUBSCRIPTIONS_CANCEL_CONFIRM_TEMPLATE, 
                email=subscription.streaming_email,
                client_name=client_name,
            )

        if msg == "3":
            session.step = self.SUBSCRIPTIONS_STEP_RENEW_DURATION
            session.temp_data = {}
            if session_service is not None:
                await session_service.save_session(session)
            return self._t(self.KEY_SUBSCRIPTIONS_RENEW_DURATION_PROMPT)

        if msg == "4" and subscription.status == "cancelled":
            session.step = self.SUBSCRIPTIONS_STEP_REACTIVATE_DURATION
            session.temp_data = {}
            if session_service is not None:
                await session_service.save_session(session)
            return self._t(self.KEY_SUBSCRIPTIONS_REACTIVATE_DURATION_PROMPT)

        return self._t(self.KEY_SUBSCRIPTIONS_INVALID_SELECTION)

    async def _start_subscriptions_create(
        self,
        phone: str,
        session: Any,
        session_service: WhatsAppSessionService | None,
        tenant_id: UUID | None,
        db: AsyncSession | None,
    ) -> str:
        if tenant_id is None or db is None or self._client_service is None:
            return self._t(self.KEY_SUBSCRIPTIONS_CLIENT_REQUIRED)
        clients = await self._client_service.list_clients(db, tenant_id)
        if not clients:
            return self._t(self.KEY_SUBSCRIPTIONS_CLIENT_REQUIRED)

        client_list, selection_map = self._format_client_list(clients)
        session.flow = self.SUBSCRIPTIONS_FLOW
        session.step = self.SUBSCRIPTIONS_STEP_CREATE_CLIENT
        session.temp_data = {"starts_at": datetime.now(timezone.utc).isoformat()}
        session.selection_map = selection_map
        if session_service is not None:
            await session_service.save_session(session)
        return self._t(self.KEY_SUBSCRIPTIONS_CREATE_CLIENT_PROMPT, client_list=client_list)

    async def _handle_subscriptions_create_client(
        self,
        phone: str,
        msg: str,
        session: Any,
        session_service: WhatsAppSessionService | None,
        tenant_id: UUID | None,
        db: AsyncSession | None,
    ) -> str:
        del phone
        client_id = self._safe_uuid(session.selection_map.get(msg))
        if client_id is None or tenant_id is None or db is None or self._client_service is None:
            return self._t(self.KEY_SUBSCRIPTIONS_INVALID_SELECTION)
        client = await self._client_service.get_client(db, tenant_id, client_id)
        if client is None:
            return self._t(self.KEY_SUBSCRIPTIONS_INVALID_SELECTION)

        if self._catalog_service is None:
            return self._t("wa.tenant.errors.catalog_load_failed")
        services = await self._catalog_service.list_services(db, tenant_id)
        if not services:
            return self._t("wa.tenant.errors.no_services")
        service_list, selection_map = self._format_service_list(services)

        session.temp_data.update(
            {
                "client_id": str(client.id),
                "client_name": client.full_name,
            }
        )
        session.selection_map = selection_map
        session.step = self.SUBSCRIPTIONS_STEP_CREATE_SERVICE
        if session_service is not None:
            await session_service.save_session(session)
        return self._t(self.KEY_SUBSCRIPTIONS_CREATE_SERVICE_PROMPT, service_list=service_list)

    async def _handle_subscriptions_create_service(
        self,
        phone: str,
        msg: str,
        session: Any,
        session_service: WhatsAppSessionService | None,
        tenant_id: UUID | None,
        db: AsyncSession | None,
    ) -> str:
        del phone
        service_id = self._safe_uuid(session.selection_map.get(msg))
        if service_id is None or tenant_id is None or db is None or self._catalog_service is None:
            return self._t(self.KEY_SUBSCRIPTIONS_INVALID_SELECTION)
        service = await self._catalog_service.get_service(db, tenant_id, service_id)
        if service is None:
            return self._t(self.KEY_SUBSCRIPTIONS_INVALID_SELECTION)
        plans = await self._catalog_service.list_plans(db, tenant_id, service_id) or []
        if not plans:
            return self._t("wa.tenant.errors.no_plans")
        plan_list, selection_map = self._format_plan_list(plans)

        session.temp_data.update(
            {
                "service_id": str(service.id),
                "service_name": service.name,
            }
        )
        session.selection_map = selection_map
        session.step = self.SUBSCRIPTIONS_STEP_CREATE_PLAN
        if session_service is not None:
            await session_service.save_session(session)
        return self._t(self.KEY_SUBSCRIPTIONS_CREATE_PLAN_PROMPT, plan_list=plan_list)

    async def _handle_subscriptions_create_plan(
        self,
        phone: str,
        msg: str,
        session: Any,
        session_service: WhatsAppSessionService | None,
        tenant_id: UUID | None,
        db: AsyncSession | None,
    ) -> str:
        del phone
        plan_id = self._safe_uuid(session.selection_map.get(msg))
        service_id = self._safe_uuid(session.temp_data.get("service_id"))
        if (
            plan_id is None
            or service_id is None
            or tenant_id is None
            or db is None
            or self._catalog_service is None
        ):
            return self._t(self.KEY_SUBSCRIPTIONS_INVALID_SELECTION)
        plan = await self._catalog_service.get_plan(db, tenant_id, service_id, plan_id)
        if plan is None:
            return self._t(self.KEY_SUBSCRIPTIONS_INVALID_SELECTION)

        session.temp_data.update(
            {
                "plan_id": str(plan.id),
                "plan_name": plan.name,
            }
        )
        session.step = self.SUBSCRIPTIONS_STEP_CREATE_EMAIL
        if session_service is not None:
            await session_service.save_session(session)
        return self._t(self.KEY_SUBSCRIPTIONS_CREATE_EMAIL_PROMPT)

    async def _handle_subscriptions_create_email(
        self,
        phone: str,
        msg: str,
        session: Any,
        session_service: WhatsAppSessionService | None,
    ) -> str:
        del phone
        email = msg.strip()
        if not email:
            return self._t(self.KEY_SUBSCRIPTIONS_EMAIL_REQUIRED)
        session.temp_data["streaming_email"] = email
        session.step = self.SUBSCRIPTIONS_STEP_CREATE_PASSWORD
        if session_service is not None:
            await session_service.save_session(session)
        return self._t(self.KEY_SUBSCRIPTIONS_CREATE_PASSWORD_PROMPT)

    async def _handle_subscriptions_create_password(
        self,
        phone: str,
        msg: str,
        session: Any,
        session_service: WhatsAppSessionService | None,
    ) -> str:
        del phone
        value = msg.strip()
        if value.lower() in self.SUBSCRIPTIONS_SKIP_WORDS:
            session.temp_data["streaming_password"] = None
            session.temp_data.pop("streaming_password_pending", None)
            session.step = self.SUBSCRIPTIONS_STEP_CREATE_PROFILE_OPTION
            if session_service is not None:
                await session_service.save_session(session)
            return self._t(self.KEY_SUBSCRIPTIONS_CREATE_PROFILE_OPTION_PROMPT)

        session.temp_data["streaming_password_pending"] = value
        session.step = self.SUBSCRIPTIONS_STEP_CREATE_PASSWORD_CONFIRM
        if session_service is not None:
            await session_service.save_session(session)
        return self._t(self.KEY_SUBSCRIPTIONS_CREATE_PASSWORD_CONFIRM_PROMPT)

    async def _handle_subscriptions_create_password_confirm(
        self,
        phone: str,
        msg: str,
        session: Any,
        session_service: WhatsAppSessionService | None,
    ) -> str:
        del phone
        pending = session.temp_data.get("streaming_password_pending")
        if msg.strip() != pending:
            return self._t(self.KEY_SUBSCRIPTIONS_CREATE_PASSWORD_MISMATCH)
        session.temp_data["streaming_password"] = pending
        session.temp_data.pop("streaming_password_pending", None)
        session.step = self.SUBSCRIPTIONS_STEP_CREATE_PROFILE_OPTION
        if session_service is not None:
            await session_service.save_session(session)
        return self._t(self.KEY_SUBSCRIPTIONS_CREATE_PROFILE_OPTION_PROMPT)

    async def _handle_subscriptions_create_profile_option(
        self,
        phone: str,
        msg: str,
        session: Any,
        session_service: WhatsAppSessionService | None,
    ) -> str:
        del phone
        value = msg.strip()
        if value == "1":
            session.step = self.SUBSCRIPTIONS_STEP_CREATE_PROFILE_NAME
            if session_service is not None:
                await session_service.save_session(session)
            return self._t(self.KEY_SUBSCRIPTIONS_CREATE_PROFILE_NAME_PROMPT)
        if value == "2":
            session.temp_data["profile_name"] = None
            session.temp_data["profile_pin"] = None
            session.temp_data.pop("profile_pin_pending", None)
            session.step = self.SUBSCRIPTIONS_STEP_CREATE_DURATION
            if session_service is not None:
                await session_service.save_session(session)
            return self._t(self.KEY_SUBSCRIPTIONS_DURATION_PROMPT)
        return self._t(self.KEY_SUBSCRIPTIONS_INVALID_SELECTION)

    async def _handle_subscriptions_create_profile_name(
        self,
        phone: str,
        msg: str,
        session: Any,
        session_service: WhatsAppSessionService | None,
    ) -> str:
        del phone
        value = msg.strip()
        session.temp_data["profile_name"] = (
            None if value.lower() in self.SUBSCRIPTIONS_SKIP_WORDS else value
        )
        session.step = self.SUBSCRIPTIONS_STEP_CREATE_PIN
        if session_service is not None:
            await session_service.save_session(session)
        return self._t(self.KEY_SUBSCRIPTIONS_CREATE_PIN_PROMPT)

    async def _handle_subscriptions_create_pin(
        self,
        phone: str,
        msg: str,
        session: Any,
        session_service: WhatsAppSessionService | None,
    ) -> str:
        del phone
        value = msg.strip()
        if value.lower() in self.SUBSCRIPTIONS_SKIP_WORDS:
            session.temp_data["profile_pin"] = None
            session.temp_data.pop("profile_pin_pending", None)
            session.step = self.SUBSCRIPTIONS_STEP_CREATE_DURATION
            if session_service is not None:
                await session_service.save_session(session)
            return self._t(self.KEY_SUBSCRIPTIONS_DURATION_PROMPT)

        if not session.temp_data.get("profile_name"):
            return self._t(self.KEY_SUBSCRIPTIONS_CREATE_PIN_REQUIRES_PROFILE)

        session.temp_data["profile_pin_pending"] = value
        session.step = self.SUBSCRIPTIONS_STEP_CREATE_PIN_CONFIRM
        if session_service is not None:
            await session_service.save_session(session)
        return self._t(self.KEY_SUBSCRIPTIONS_CREATE_PIN_CONFIRM_PROMPT)

    async def _handle_subscriptions_create_pin_confirm(
        self,
        phone: str,
        msg: str,
        session: Any,
        session_service: WhatsAppSessionService | None,
    ) -> str:
        del phone
        pending = session.temp_data.get("profile_pin_pending")
        if msg.strip() != pending:
            return self._t(self.KEY_SUBSCRIPTIONS_CREATE_PIN_MISMATCH)
        session.temp_data["profile_pin"] = pending
        session.temp_data.pop("profile_pin_pending", None)
        session.step = self.SUBSCRIPTIONS_STEP_CREATE_DURATION
        if session_service is not None:
            await session_service.save_session(session)
        return self._t(self.KEY_SUBSCRIPTIONS_DURATION_PROMPT)

    async def _handle_subscriptions_create_duration(
        self,
        phone: str,
        msg: str,
        session: Any,
        session_service: WhatsAppSessionService | None,
        tenant_id: UUID | None,
        db: AsyncSession | None,
    ) -> str:
        del phone, tenant_id, db
        duration_type = self.SUBSCRIPTIONS_DURATION_MAP.get(msg)
        if duration_type is None:
            return self._t(self.KEY_SUBSCRIPTIONS_INVALID_SELECTION)

        session.temp_data["duration_type"] = duration_type
        if duration_type == "custom":
            session.step = self.SUBSCRIPTIONS_STEP_CREATE_CUSTOM_DATE
            if session_service is not None:
                await session_service.save_session(session)
            return self._t(self.KEY_SUBSCRIPTIONS_CUSTOM_DATE_PROMPT)

        session.temp_data["expires_at"] = None
        session.step = self.SUBSCRIPTIONS_STEP_CREATE_CONFIRM
        if session_service is not None:
            await session_service.save_session(session)
        return self._build_subscription_create_confirm(session.temp_data)

    async def _handle_subscriptions_create_custom_date(
        self,
        phone: str,
        msg: str,
        session: Any,
        session_service: WhatsAppSessionService | None,
        tenant_id: UUID | None,
        db: AsyncSession | None,
    ) -> str:
        del phone, tenant_id, db
        expires_at = self._parse_iso_date(msg)
        if expires_at is None:
            return self._t("wa.tenant.errors.invalid_date")
        session.temp_data["expires_at"] = expires_at.isoformat()
        session.step = self.SUBSCRIPTIONS_STEP_CREATE_CONFIRM
        if session_service is not None:
            await session_service.save_session(session)
        return self._build_subscription_create_confirm(session.temp_data)

    async def _handle_subscriptions_create_confirm(
        self,
        phone: str,
        msg: str,
        session: Any,
        session_service: WhatsAppSessionService | None,
        tenant_id: UUID | None,
        db: AsyncSession | None,
    ) -> str:
        if msg.strip().lower() not in ("confirmar", "confirm"):
            return self._t(self.KEY_SUBSCRIPTIONS_CONFIRM_REPROMPT)
        if tenant_id is None or db is None or self._subscription_service is None:
            return self._t("wa.tenant.errors.subscription_create_failed")

        from app.schemas.subscription import SubscriptionCreate

        data = session.temp_data
        starts_at = datetime.fromisoformat(data["starts_at"])
        expires_at_raw = data.get("expires_at")
        expires_at = (
            datetime.fromisoformat(expires_at_raw) if expires_at_raw else None
        )
        payload = SubscriptionCreate(
            client_id=UUID(data["client_id"]),
            service_id=UUID(data["service_id"]),
            plan_id=UUID(data["plan_id"]),
            streaming_email=data["streaming_email"],
            streaming_password=data.get("streaming_password"),
            profile_name=data.get("profile_name"),
            profile_pin=data.get("profile_pin"),
            duration_type=data["duration_type"],
            starts_at=starts_at,
            expires_at=expires_at,
        )
        try:
            await self._subscription_service.create_subscription(db, tenant_id, payload)
        except UserFacingError as exc:
            return "❌ " + translate_error(_current_locale.get(), exc)
        except ValueError as exc:
            return "❌ " + str(exc)

        if session_service is not None:
            await session_service.clear_session(f"admin:{phone}")
        return self._with_main_menu(self._t(self.KEY_SUBSCRIPTIONS_CREATE_SUCCESS))

    async def _handle_subscriptions_edit_field(
        self,
        phone: str,
        msg: str,
        session: Any,
        session_service: WhatsAppSessionService | None,
        tenant_id: UUID | None,
        db: AsyncSession | None,
    ) -> str:
        field = self.SUBSCRIPTIONS_EDIT_FIELD_MAP.get(msg)
        if field is None:
            return self._t(self.KEY_SUBSCRIPTIONS_EDIT_ERROR_INVALID_FIELD)
        if tenant_id is None or db is None:
            return self._t("wa.tenant.errors.subscription_load_failed")

        session.temp_data = {"field": field}

        if field == "client":
            if self._client_service is None:
                return self._t(self.KEY_SUBSCRIPTIONS_CLIENT_REQUIRED)
            clients = await self._client_service.list_clients(db, tenant_id)
            client_list, selection_map = self._format_client_list(clients)
            session.selection_map = selection_map
            session.step = self.SUBSCRIPTIONS_STEP_EDIT_VALUE
            if session_service is not None:
                await session_service.save_session(session)
            return self._t(self.KEY_SUBSCRIPTIONS_CREATE_CLIENT_PROMPT, client_list=client_list)

        if field == "service":
            if self._catalog_service is None:
                return self._t("wa.tenant.errors.catalog_load_failed")
            services = await self._catalog_service.list_services(db, tenant_id)
            service_list, selection_map = self._format_service_list(services)
            session.selection_map = selection_map
            session.step = self.SUBSCRIPTIONS_STEP_EDIT_VALUE
            if session_service is not None:
                await session_service.save_session(session)
            return self._t(self.KEY_SUBSCRIPTIONS_CREATE_SERVICE_PROMPT, service_list=service_list)

        if field == "plan":
            subscription = await self._get_selected_subscription(session, tenant_id, db)
            if subscription is None or self._catalog_service is None:
                return self._t(self.KEY_SUBSCRIPTIONS_INVALID_SELECTION)
            plans = (
                await self._catalog_service.list_plans(db, tenant_id, subscription.service_id)
                or []
            )
            plan_list, selection_map = self._format_plan_list(plans)
            session.selection_map = selection_map
            session.temp_data["service_id"] = str(subscription.service_id)
            session.step = self.SUBSCRIPTIONS_STEP_EDIT_VALUE
            if session_service is not None:
                await session_service.save_session(session)
            return self._t(self.KEY_SUBSCRIPTIONS_CREATE_PLAN_PROMPT, plan_list=plan_list)

        session.step = self.SUBSCRIPTIONS_STEP_EDIT_VALUE
        if session_service is not None:
            await session_service.save_session(session)
        return self.SUBSCRIPTIONS_EDIT_PROMPTS.get(field, self._t(self.KEY_SUBSCRIPTIONS_EDIT_FIELD_PROMPT))

    async def _handle_subscriptions_edit_value(
        self,
        phone: str,
        msg: str,
        session: Any,
        session_service: WhatsAppSessionService | None,
        tenant_id: UUID | None,
        db: AsyncSession | None,
    ) -> str:
        if tenant_id is None or db is None or self._subscription_service is None:
            return self._t("wa.tenant.errors.subscription_update_failed")
        field = session.temp_data.get("field")

        if field == "client":
            client_id = self._safe_uuid(session.selection_map.get(msg))
            if client_id is None:
                return self._t(self.KEY_SUBSCRIPTIONS_INVALID_SELECTION)
            return await self._apply_subscription_update(
                phone,
                session,
                session_service,
                tenant_id,
                db,
                client_id=client_id,
            )

        if field == "service":
            service_id = self._safe_uuid(session.selection_map.get(msg))
            if service_id is None or self._catalog_service is None:
                return self._t(self.KEY_SUBSCRIPTIONS_INVALID_SELECTION)
            service = await self._catalog_service.get_service(db, tenant_id, service_id)
            if service is None:
                return self._t(self.KEY_SUBSCRIPTIONS_INVALID_SELECTION)
            plans = await self._catalog_service.list_plans(db, tenant_id, service_id) or []
            if not plans:
                return self._t("wa.tenant.errors.no_plans")
            plan_list, selection_map = self._format_plan_list(plans)
            session.selection_map = selection_map
            session.temp_data = {
                "field": "service_plan",
                "service_id": str(service_id),
            }
            session.step = self.SUBSCRIPTIONS_STEP_EDIT_VALUE
            if session_service is not None:
                await session_service.save_session(session)
            return self._t(self.KEY_SUBSCRIPTIONS_CREATE_PLAN_PROMPT, plan_list=plan_list)

        if field == "service_plan":
            plan_id = self._safe_uuid(session.selection_map.get(msg))
            service_id = self._safe_uuid(session.temp_data.get("service_id"))
            if plan_id is None or service_id is None:
                return self._t(self.KEY_SUBSCRIPTIONS_INVALID_SELECTION)
            return await self._apply_subscription_update(
                phone,
                session,
                session_service,
                tenant_id,
                db,
                service_id=service_id,
                plan_id=plan_id,
            )

        if field == "plan":
            plan_id = self._safe_uuid(session.selection_map.get(msg))
            if plan_id is None:
                return self._t(self.KEY_SUBSCRIPTIONS_INVALID_SELECTION)
            return await self._apply_subscription_update(
                phone,
                session,
                session_service,
                tenant_id,
                db,
                plan_id=plan_id,
            )

        if field == "streaming_email":
            email = msg.strip()
            if not email:
                return self._t(self.KEY_SUBSCRIPTIONS_EMAIL_REQUIRED)
            return await self._apply_subscription_update(
                phone,
                session,
                session_service,
                tenant_id,
                db,
                streaming_email=email,
            )

        if field == "profile_name":
            value = msg.strip()
            return await self._apply_subscription_update(
                phone,
                session,
                session_service,
                tenant_id,
                db,
                profile_name=None if value.lower() in self.SUBSCRIPTIONS_SKIP_WORDS else value,
            )

        if field == "streaming_password":
            session.temp_data["pending_value"] = (
                "" if msg.strip().lower() in self.SUBSCRIPTIONS_SKIP_WORDS else msg.strip()
            )
            session.step = self.SUBSCRIPTIONS_STEP_EDIT_PASSWORD_CONFIRM
            if session_service is not None:
                await session_service.save_session(session)
            return self._t(self.KEY_SUBSCRIPTIONS_EDIT_PASSWORD_CONFIRM_PROMPT)

        if field == "profile_pin":
            subscription = await self._get_selected_subscription(session, tenant_id, db)
            if subscription is None:
                return self._t(self.KEY_SUBSCRIPTIONS_INVALID_SELECTION)
            value = "" if msg.strip().lower() in self.SUBSCRIPTIONS_SKIP_WORDS else msg.strip()
            if value and not subscription.profile_name:
                return self._t(self.KEY_SUBSCRIPTIONS_CREATE_PIN_REQUIRES_PROFILE)
            session.temp_data["pending_value"] = value
            session.step = self.SUBSCRIPTIONS_STEP_EDIT_PIN_CONFIRM
            if session_service is not None:
                await session_service.save_session(session)
            return self._t(self.KEY_SUBSCRIPTIONS_EDIT_PIN_CONFIRM_PROMPT)

        return self._t(self.KEY_SUBSCRIPTIONS_INVALID_SELECTION)

    async def _handle_subscriptions_edit_password_confirm(
        self,
        phone: str,
        msg: str,
        session: Any,
        session_service: WhatsAppSessionService | None,
        tenant_id: UUID | None,
        db: AsyncSession | None,
    ) -> str:
        pending_value = session.temp_data.get("pending_value", "")
        if msg.strip() != pending_value:
            return self._t(self.KEY_SUBSCRIPTIONS_EDIT_MISMATCH)
        return await self._apply_subscription_update(
            phone,
            session,
            session_service,
            tenant_id,
            db,
            streaming_password=pending_value,
        )

    async def _handle_subscriptions_edit_pin_confirm(
        self,
        phone: str,
        msg: str,
        session: Any,
        session_service: WhatsAppSessionService | None,
        tenant_id: UUID | None,
        db: AsyncSession | None,
    ) -> str:
        pending_value = session.temp_data.get("pending_value", "")
        if msg.strip() != pending_value:
            return self._t(self.KEY_SUBSCRIPTIONS_EDIT_MISMATCH)
        return await self._apply_subscription_update(
            phone,
            session,
            session_service,
            tenant_id,
            db,
            profile_pin=pending_value,
        )

    async def _handle_subscriptions_cancel_confirm(
        self,
        phone: str,
        msg: str,
        session: Any,
        session_service: WhatsAppSessionService | None,
        tenant_id: UUID | None,
        db: AsyncSession | None,
    ) -> str:
        if msg.strip().lower() not in ("confirmar", "confirm"):
            return self._t(self.KEY_SUBSCRIPTIONS_CONFIRM_REPROMPT)
        subscription_id = self._safe_uuid(session.selected_tenant_id)
        if (
            subscription_id is None
            or tenant_id is None
            or db is None
            or self._subscription_service is None
        ):
            return self._t("wa.tenant.errors.subscription_cancel_failed")
        cancelled = await self._subscription_service.cancel_subscription(
            db, tenant_id, subscription_id
        )
        if cancelled is None:
            return self._t(self.KEY_SUBSCRIPTIONS_INVALID_SELECTION)
        if session_service is not None:
            await session_service.clear_session(f"admin:{phone}")
        return self._with_main_menu(self._t(self.KEY_SUBSCRIPTIONS_CANCEL_SUCCESS))

    async def _handle_subscriptions_reactivate_duration(
        self,
        phone: str,
        msg: str,
        session: Any,
        session_service: WhatsAppSessionService | None,
        tenant_id: UUID | None,
        db: AsyncSession | None,
    ) -> str:
        del phone, tenant_id, db
        duration_type = self.SUBSCRIPTIONS_DURATION_MAP.get(msg)
        if duration_type is None:
            return self._t(self.KEY_SUBSCRIPTIONS_INVALID_SELECTION)
        session.temp_data = {
            "duration_type": duration_type,
            "starts_at": datetime.now(timezone.utc).isoformat(),
        }
        if duration_type == "custom":
            session.step = self.SUBSCRIPTIONS_STEP_REACTIVATE_CUSTOM_DATE
            if session_service is not None:
                await session_service.save_session(session)
            return self._t(self.KEY_SUBSCRIPTIONS_REACTIVATE_CUSTOM_DATE_PROMPT)
        session.step = self.SUBSCRIPTIONS_STEP_REACTIVATE_CONFIRM
        if session_service is not None:
            await session_service.save_session(session)
        return self._build_subscription_reactivate_confirm(session.temp_data)

    async def _handle_subscriptions_reactivate_custom_date(
        self,
        phone: str,
        msg: str,
        session: Any,
        session_service: WhatsAppSessionService | None,
        tenant_id: UUID | None,
        db: AsyncSession | None,
    ) -> str:
        del phone, tenant_id, db
        expires_at = self._parse_iso_date(msg)
        if expires_at is None:
            return self._t("wa.tenant.errors.invalid_date")
        session.temp_data["expires_at"] = expires_at.isoformat()
        session.step = self.SUBSCRIPTIONS_STEP_REACTIVATE_CONFIRM
        if session_service is not None:
            await session_service.save_session(session)
        return self._build_subscription_reactivate_confirm(session.temp_data)

    async def _handle_subscriptions_reactivate_confirm(
        self,
        phone: str,
        msg: str,
        session: Any,
        session_service: WhatsAppSessionService | None,
        tenant_id: UUID | None,
        db: AsyncSession | None,
    ) -> str:
        if msg.strip().lower() not in ("confirmar", "confirm"):
            return self._t(self.KEY_SUBSCRIPTIONS_CONFIRM_REPROMPT)
        subscription_id = self._safe_uuid(session.selected_tenant_id)
        if (
            subscription_id is None
            or tenant_id is None
            or db is None
            or self._subscription_service is None
        ):
            return self._t("wa.tenant.errors.subscription_reactivate_failed")
        duration_type = session.temp_data["duration_type"]
        starts_at = datetime.fromisoformat(session.temp_data["starts_at"])
        expires_at_raw = session.temp_data.get("expires_at")
        expires_at = (
            datetime.fromisoformat(expires_at_raw) if expires_at_raw else None
        )
        reactivated = await self._subscription_service.reactivate_subscription(
            db,
            tenant_id,
            subscription_id,
            duration_type,
            starts_at=starts_at,
            expires_at=expires_at,
        )
        if reactivated is None:
            return self._t(self.KEY_SUBSCRIPTIONS_INVALID_SELECTION)
        if session_service is not None:
            await session_service.clear_session(f"admin:{phone}")
        return self._with_main_menu(self._t(self.KEY_SUBSCRIPTIONS_REACTIVATE_SUCCESS))

    async def _handle_subscriptions_renew_duration(
        self,
        phone: str,
        msg: str,
        session: Any,
        session_service: WhatsAppSessionService | None,
        tenant_id: UUID | None,
        db: AsyncSession | None,
    ) -> str:
        del phone
        duration_type = self.SUBSCRIPTIONS_DURATION_MAP.get(msg)
        if duration_type is None:
            return self._t(self.KEY_SUBSCRIPTIONS_INVALID_SELECTION)
        session.temp_data = {"duration_type": duration_type}
        if duration_type == "custom":
            session.step = self.SUBSCRIPTIONS_STEP_RENEW_CUSTOM_DATE
            if session_service is not None:
                await session_service.save_session(session)
            return self._t(self.KEY_SUBSCRIPTIONS_RENEW_CUSTOM_DATE_PROMPT)
        session.step = self.SUBSCRIPTIONS_STEP_RENEW_CONFIRM
        if session_service is not None:
            await session_service.save_session(session)
        return await self._build_subscription_renew_confirm(session, tenant_id, db)

    async def _handle_subscriptions_renew_custom_date(
        self,
        phone: str,
        msg: str,
        session: Any,
        session_service: WhatsAppSessionService | None,
        tenant_id: UUID | None,
        db: AsyncSession | None,
    ) -> str:
        del phone
        expires_at = self._parse_iso_date(msg)
        if expires_at is None:
            return self._t("wa.tenant.errors.invalid_date")
        session.temp_data["expires_at"] = expires_at.isoformat()
        session.step = self.SUBSCRIPTIONS_STEP_RENEW_CONFIRM
        if session_service is not None:
            await session_service.save_session(session)
        return await self._build_subscription_renew_confirm(session, tenant_id, db)

    async def _handle_subscriptions_renew_confirm(
        self,
        phone: str,
        msg: str,
        session: Any,
        session_service: WhatsAppSessionService | None,
        tenant_id: UUID | None,
        db: AsyncSession | None,
    ) -> str:
        if msg.strip().lower() not in ("confirmar", "confirm"):
            return self._t(self.KEY_SUBSCRIPTIONS_CONFIRM_REPROMPT)
        subscription_id = self._safe_uuid(session.selected_tenant_id)
        if (
            subscription_id is None
            or tenant_id is None
            or db is None
            or self._subscription_service is None
        ):
            return self._t("wa.tenant.errors.subscription_renew_failed")
        duration_type = session.temp_data["duration_type"]
        expires_at_raw = session.temp_data.get("expires_at")
        expires_at = (
            datetime.fromisoformat(expires_at_raw) if expires_at_raw else None
        )
        renewed = await self._subscription_service.renew_subscription(
            db,
            tenant_id,
            subscription_id,
            duration_type,
            expires_at=expires_at,
        )
        if renewed is None:
            return self._t(self.KEY_SUBSCRIPTIONS_INVALID_SELECTION)
        if session_service is not None:
            await session_service.clear_session(f"admin:{phone}")
        return self._with_main_menu(self._t(self.KEY_SUBSCRIPTIONS_RENEW_SUCCESS))

    async def _get_selected_subscription(
        self,
        session: Any,
        tenant_id: UUID | None,
        db: AsyncSession | None,
    ) -> Any | None:
        subscription_id = self._safe_uuid(session.selected_tenant_id)
        if (
            subscription_id is None
            or tenant_id is None
            or db is None
            or self._subscription_service is None
        ):
            return None
        return await self._subscription_service.get_subscription(
            db, tenant_id, subscription_id
        )

    async def _apply_subscription_update(
        self,
        phone: str,
        session: Any,
        session_service: WhatsAppSessionService | None,
        tenant_id: UUID | None,
        db: AsyncSession | None,
        **changes: Any,
    ) -> str:
        if tenant_id is None or db is None or self._subscription_service is None:
            return self._t("wa.tenant.errors.subscription_update_failed")
        from app.schemas.subscription import SubscriptionUpdate

        selected_id = self._safe_uuid(session.selected_tenant_id)
        if selected_id is None:
            return self._t(self.KEY_SUBSCRIPTIONS_INVALID_SELECTION)

        normalized_changes = {
            key: (None if value == "" else value)
            for key, value in changes.items()
        }
        try:
            updated = await self._subscription_service.update_subscription(
                db,
                tenant_id,
                selected_id,
                SubscriptionUpdate(**normalized_changes),
            )
        except UserFacingError as exc:
            return "❌ " + translate_error(_current_locale.get(), exc)
        except ValueError as exc:
            return "❌ " + str(exc)
        if updated is None:
            return self._t(self.KEY_SUBSCRIPTIONS_INVALID_SELECTION)
        if session_service is not None:
            await session_service.clear_session(f"admin:{phone}")
        return self._with_main_menu(self._t(self.KEY_SUBSCRIPTIONS_EDIT_SUCCESS))

    def _build_subscription_create_confirm(self, data: dict[str, Any]) -> str:
        starts_at = datetime.fromisoformat(data["starts_at"])
        expires_at_raw = data.get("expires_at")
        expires_at = (
            datetime.fromisoformat(expires_at_raw)
            if expires_at_raw
            else self._calculate_subscription_expiry(starts_at, data["duration_type"])
        )
        return self._t(self.KEY_SUBSCRIPTIONS_CREATE_CONFIRM_TEMPLATE, 
            client_name=data.get("client_name", "—"),
            service_name=data.get("service_name", "—"),
            plan_name=data.get("plan_name", "—"),
            email=data.get("streaming_email", "—"),
            password=data.get("streaming_password") or "—",
            profile_name=data.get("profile_name") or "—",
            pin=data.get("profile_pin") or "—",
            duration_label=self._format_subscription_duration(data["duration_type"]),
            starts_at=self._format_short_date(starts_at),
            expires_at=self._format_short_date(expires_at),
        )

    def _build_subscription_reactivate_confirm(self, data: dict[str, Any]) -> str:
        starts_at = datetime.fromisoformat(data["starts_at"])
        expires_at_raw = data.get("expires_at")
        expires_at = (
            datetime.fromisoformat(expires_at_raw)
            if expires_at_raw
            else self._calculate_subscription_expiry(starts_at, data["duration_type"])
        )
        return self._t(self.KEY_SUBSCRIPTIONS_REACTIVATE_CONFIRM_TEMPLATE, 
            duration_label=self._format_subscription_duration(data["duration_type"]),
            starts_at=self._format_short_date(starts_at),
            expires_at=self._format_short_date(expires_at),
        )

    async def _build_subscription_renew_confirm(
        self,
        session: Any,
        tenant_id: UUID | None,
        db: AsyncSession | None,
    ) -> str:
        subscription = await self._get_selected_subscription(session, tenant_id, db)
        if subscription is None:
            return self._t(self.KEY_SUBSCRIPTIONS_INVALID_SELECTION)
        duration_type = session.temp_data["duration_type"]
        expires_at_raw = session.temp_data.get("expires_at")
        base_expires = subscription.expires_at
        if base_expires.tzinfo is None:
            base_expires = base_expires.replace(tzinfo=timezone.utc)
        expires_at = (
            datetime.fromisoformat(expires_at_raw)
            if expires_at_raw
            else self._calculate_subscription_expiry(base_expires, duration_type)
        )
        return self._t(self.KEY_SUBSCRIPTIONS_RENEW_CONFIRM_TEMPLATE, 
            duration_label=self._format_subscription_duration(duration_type),
            expires_at=self._format_short_date(expires_at),
        )

    # ==================================================================
    # PROFILE FLOWS
    # ==================================================================

    async def _start_profile_flow(
        self,
        phone: str,
        session_service: WhatsAppSessionService | None,
        user_id: UUID | None,
        db: AsyncSession | None,
    ) -> str:
        """Start the profile sub-menu."""
        if session_service is not None:
            session = await session_service.get_session(f"admin:{phone}")
            if session is None:
                session = await session_service.create_session(f"admin:{phone}")
            session.flow = self.PROFILE_FLOW
            session.step = self.PROFILE_STEP_ACTION
            session.temp_data = {}
            await session_service.save_session(session)
        return self._t(self.KEY_PROFILE_MENU)

    async def _handle_profile_action(
        self,
        phone: str,
        msg: str,
        session: Any,
        session_service: WhatsAppSessionService | None,
        user_id: UUID | None,
        db: AsyncSession | None,
    ) -> str:
        if msg == "1":
            # View profile
            return await self._show_profile(phone, session_service, user_id, db)
        elif msg == "2":
            # Edit profile
            return await self._start_profile_edit(phone, session, session_service)
        elif msg == "3":
            # Change password
            return await self._start_profile_change_password(phone, session, session_service)
        elif msg == "4":
            # Change language
            return await self._start_profile_change_locale(phone, session, session_service)
        elif msg == "0":
            return self._with_main_menu("")
        return self._t(self.KEY_FALLBACK_NO_FLOW)

    async def _show_profile(
        self,
        phone: str,
        session_service: WhatsAppSessionService | None,
        user_id: UUID | None,
        db: AsyncSession | None,
    ) -> str:
        if user_id is None or db is None or self._profile_service is None:
            return self._t("wa.tenant.errors.profile_load_failed")
        from app.crud import users as user_crud
        user = await user_crud.get(db, user_id)
        if user is None:
            return self._t("wa.tenant.errors.user_not_found")
        profile = await self._profile_service.get_profile(db, user)
        if profile is None:
            return self._t("wa.tenant.errors.profile_not_found")
        return self._format_profile_detail(profile, user.username)

    async def _start_profile_edit(
        self,
        phone: str,
        session: Any,
        session_service: WhatsAppSessionService | None,
    ) -> str:
        session.flow = self.PROFILE_FLOW
        session.step = self.PROFILE_STEP_EDIT_FIELD
        session.temp_data = {}
        if session_service is not None:
            await session_service.save_session(session)
        return self._t(self.KEY_PROFILE_EDIT_FIELD_PROMPT)

    async def _handle_profile_edit_field(
        self,
        phone: str,
        msg: str,
        session: Any,
        session_service: WhatsAppSessionService | None,
    ) -> str:
        if msg == "0":
            await session_service.clear_session(f"admin:{phone}")
            return self._t(self.KEY_MAIN_MENU)
        field = self.PROFILE_EDIT_FIELD_MAP.get(msg)
        if field is None:
            return self._t(self.KEY_PROFILE_EDIT_ERROR_INVALID_FIELD)
        session.temp_data["field"] = field
        session.step = self.PROFILE_STEP_EDIT_VALUE
        if session_service is not None:
            await session_service.save_session(session)
        return self.PROFILE_EDIT_PROMPTS[field]

    async def _handle_profile_edit_value(
        self,
        phone: str,
        msg: str,
        session: Any,
        session_service: WhatsAppSessionService | None,
        user_id: UUID | None,
        db: AsyncSession | None,
    ) -> str:
        field = session.temp_data.get("field", "")
        new_value = msg.strip()
        if user_id is None or db is None or self._profile_service is None:
            return self._t("wa.tenant.errors.profile_update_failed")
        from app.crud import users as user_crud
        user = await user_crud.get(db, user_id)
        if user is None:
            return self._t("wa.tenant.errors.user_not_found")
        from app.schemas.me import ProfileUpdate
        payload = ProfileUpdate(**{field: new_value})
        try:
            profile = await self._profile_service.update_profile(db, user, payload)
        except UserFacingError as exc:
            return "❌ " + translate_error(_current_locale.get(), exc)
        except ValueError as exc:
            return "❌ " + str(exc)
        if profile is None:
            return self._t("wa.tenant.errors.profile_update_failed")
        if session_service is not None:
            await session_service.clear_session(f"admin:{phone}")
        return self._with_main_menu(self._t(self.KEY_PROFILE_EDIT_SUCCESS))

    async def _start_profile_change_password(
        self,
        phone: str,
        session: Any,
        session_service: WhatsAppSessionService | None,
    ) -> str:
        session.flow = self.PROFILE_FLOW
        session.step = self.PROFILE_STEP_CHANGE_PASSWORD_OLD
        session.temp_data = {}
        if session_service is not None:
            await session_service.save_session(session)
        return self._t(self.KEY_PROFILE_CHANGE_PASSWORD_PROMPT_OLD)

    async def _handle_profile_change_password_old(
        self,
        phone: str,
        msg: str,
        session: Any,
        session_service: WhatsAppSessionService | None,
        user_id: UUID | None,
        db: AsyncSession | None,
    ) -> str:
        old_password = msg.strip()
        if not old_password:
            return self._t(self.KEY_PROFILE_CHANGE_PASSWORD_PROMPT_OLD)
        session.temp_data["old_password"] = old_password
        session.step = self.PROFILE_STEP_CHANGE_PASSWORD_NEW
        if session_service is not None:
            await session_service.save_session(session)
        return self._t(self.KEY_PROFILE_CHANGE_PASSWORD_PROMPT_NEW)

    async def _handle_profile_change_password_new(
        self,
        phone: str,
        msg: str,
        session: Any,
        session_service: WhatsAppSessionService | None,
        user_id: UUID | None,
        db: AsyncSession | None,
    ) -> str:
        new_password = msg.strip()
        old_password = session.temp_data.get("old_password", "")
        if len(new_password) < 6:
            return self._t("wa.tenant.errors.password_short") + "\n\n" + self._t(self.KEY_PROFILE_CHANGE_PASSWORD_PROMPT_NEW)
        if user_id is None or db is None or self._profile_service is None:
            return self._t("wa.tenant.errors.password_change_failed")
        from app.crud import users as user_crud
        user = await user_crud.get(db, user_id)
        if user is None:
            return self._t("wa.tenant.errors.user_not_found")
        success = await self._profile_service.change_password(db, user, old_password, new_password)
        if not success:
            return self._t(self.KEY_PROFILE_CHANGE_PASSWORD_ERROR_OLD)
        if session_service is not None:
            await session_service.clear_session(f"admin:{phone}")
        return self._with_main_menu(self._t(self.KEY_PROFILE_CHANGE_PASSWORD_SUCCESS))

    async def _start_profile_change_locale(
        self,
        phone: str,
        session: Any,
        session_service: WhatsAppSessionService | None,
    ) -> str:
        """Start the locale change flow."""
        current_locale = _current_locale.get()
        current_locale_name = LOCALE_NAMES.get(current_locale, current_locale)
        if session_service is not None:
            session.flow = self.PROFILE_FLOW
            session.step = self.PROFILE_STEP_CHANGE_LOCALE_SELECT
            await session_service.save_session(session)
        return self._t(self.KEY_PROFILE_LOCALE_SELECT, current_locale=current_locale_name)

    async def _handle_profile_change_locale_select(
        self,
        phone: str,
        msg: str,
        session: Any,
        session_service: WhatsAppSessionService | None,
        user_id: UUID | None,
        db: AsyncSession | None,
    ) -> str:
        """Handle locale selection."""
        if msg == "0":
            return self._with_main_menu("")
        if msg not in ("1", "2"):
            return self._t(self.KEY_FALLBACK_NO_FLOW)
        
        new_locale = "en" if msg == "1" else "es"
        
        if user_id is not None and db is not None:
            # Update tenant locale directly — ProfileService expects User, not UUID
            from app.models import Tenant
            from sqlalchemy import update as sa_update
            await db.execute(
                sa_update(Tenant).where(Tenant.owner_user_id == user_id).values(locale=new_locale)
            )
            await db.commit()
        
        if session_service is not None:
            await session_service.clear_session(f"admin:{phone}")
        
        # Show confirmation in the new locale
        token = _current_locale.set(new_locale)
        try:
            human_name = LOCALE_NAMES.get(new_locale, new_locale)
            return self._with_main_menu(_i18n_t(new_locale, "wa.tenant.profile.locale_changed", locale_name=human_name))
        finally:
            _current_locale.reset(token)
