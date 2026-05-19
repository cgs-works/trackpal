"""WhatsApp Tenant Admin Console service — conversation flow routing.

Owns conversation state transitions, menu routing, help, fallback,
global reset commands, and CRUD decisions for Client, Catalog, and
Profile within the tenant scope.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis_client import RedisUnavailableError
from app.services.contingency_reply_policy import ContingencyReplyPolicy
from app.services.whatsapp_session_service import WhatsAppSessionService
from app.services.tenant_console_protocols import (
    CatalogServiceProtocol,
    ClientServiceProtocol,
)

logger = logging.getLogger(__name__)


class WhatsAppTenantConsoleService:
    """Route incoming WhatsApp messages for the Tenant Admin Console.

    Owns conversation state transitions, menu routing, and CRUD
    decisions for tenant-scoped clients, catalog items, and profile.
    """

    # ------------------------------------------------------------------
    # Reply templates (Spanish)
    # ------------------------------------------------------------------

    MAIN_MENU = (
        "🤖 *Trackpal Consola de Administración*\n\n"
        "1️⃣ Clientes\n"
        "2️⃣ Catálogo\n"
        "3️⃣ Mi Perfil\n"
        "4️⃣ Ayuda\n\n"
        "0️⃣ Salir\n\n"
        "Responde con el número de la opción deseada."
    )

    HELP_TEXT = (
        "🤖 *Ayuda - Consola de Administración*\n\n"
        "Los comandos disponibles son:\n\n"
        "1️⃣ *Clientes* — Gestiona los clientes de tu empresa.\n"
        "    • Ver lista de clientes\n"
        "    • Ver detalle de un cliente\n"
        "    • Crear, editar, desactivar o eliminar clientes\n"
        "2️⃣ *Catálogo* — Consulta y edita tus servicios y planes.\n"
        "    • Ver servicios y sus planes\n"
        "    • Editar nombre de servicios y planes\n"
        "3️⃣ *Mi Perfil* — Consulta y edita tu perfil.\n"
        "    • Ver datos de perfil\n"
        "    • Editar nombre, email o teléfono\n"
        "    • Cambiar contraseña\n"
        "4️⃣ *Ayuda* — Muestra este mensaje.\n"
        "0️⃣ *Salir* — Cierra la sesión de la consola.\n\n"
        "En el menú principal, escribe *0* para salir.\n"
        "Dentro de un flujo, *0* o *cancelar* cancelan la operación.\n"
        "Escribe *menu* para volver al menú principal."
    )

    FALLBACK_NO_FLOW = (
        "❌ No entendí tu mensaje.\n\n"
        "Responde con:\n"
        "• Un número del *1* al *4* para elegir una opción del menú\n"
        "• *menu* para volver al menú principal\n"
        "• *0* para salir\n"
        "• *ayuda* para ver los comandos disponibles"
    )

    FALLBACK_ACTIVE_FLOW = (
        "❌ No entendí tu mensaje.\n\n"
        "Estás en medio de un flujo. Responde con la información "
        "solicitada o escribe *0* para cancelar y volver al menú "
        "principal."
    )

    RESET_COMMANDS = {"0", "menu", "menú", "cancelar"}
    HELP_COMMANDS = {"4", "ayuda"}

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

    # -- Client messages --------------------------------------------------

    CLIENTS_MENU = (
        "👥 *Clientes*\n\n"
        "1️⃣ Ver clientes\n"
        "2️⃣ Crear cliente\n"
        "0️⃣ Volver al menú principal"
    )

    CLIENT_NO_CLIENTS = "📭 No hay clientes registrados."

    CLIENT_SELECT_PROMPT = (
        "Responde con el número del cliente para ver sus detalles."
    )

    CLIENT_DETAIL_ACTIVE_ACTIONS = (
        "*Acciones disponibles:*\n"
        "1️⃣ Editar\n"
        "2️⃣ Desactivar\n"
        "3️⃣ Eliminar (solo inactivos)\n"
        "0️⃣ Volver"
    )

    CLIENT_DETAIL_INACTIVE_ACTIONS = (
        "*Acciones disponibles:*\n"
        "1️⃣ Editar\n"
        "2️⃣ Reactivar\n"
        "3️⃣ Eliminar\n"
        "0️⃣ Volver"
    )

    CLIENT_CREATE_PROMPT_FULL_NAME = (
        "✏️ *Crear Cliente*\n\n"
        "¿Cuál es el *nombre completo* del cliente?"
    )

    CLIENT_CREATE_PROMPT_PHONE = (
        "✏️ *Crear Cliente*\n\n"
        "¿Cuál es el *teléfono* del cliente?\n\n"
        "(Opcional — escribe *—* para omitir)"
    )

    CLIENT_CREATE_PROMPT_USERNAME = (
        "✏️ *Crear Cliente*\n\n"
        "¿Cuál es el *nombre de usuario local* del cliente?\n\n"
        "Se usará junto con el prefijo del tenant para formar "
        "el nombre de usuario completo."
    )

    CLIENT_CREATE_PROMPT_PASSWORD = (
        "✏️ *Crear Cliente*\n\n"
        "Escribe la *contraseña* para el cliente.\n\n"
        "⚠️ Ten en cuenta que estás enviando una contraseña "
        "a través de WhatsApp.\n\n"
        "La contraseña debe tener al menos *6 caracteres*."
    )

    CLIENT_CREATE_CONFIRM_TEMPLATE = (
        "📋 *Resumen de Creación*\n\n"
        "*Nombre:* {name}\n"
        "*Usuario local:* {username}\n"
        "*Teléfono:* {phone}\n\n"
        "¿Todo está correcto? Escribe *CONFIRMAR* para crear el cliente.\n"
        "Escribe *0* para cancelar."
    )

    CLIENT_CREATE_SUCCESS = (
        "✅ *Cliente creado exitosamente*\n\n"
        "*Nombre:* {name}\n"
        "*Usuario:* {username_full}\n"
        "*Teléfono:* {phone}\n"
    )

    CLIENT_CREATE_ERROR_PHONE = (
        "❌ Teléfono inválido o ya registrado. "
        "Intenta de nuevo o escribe *—* para omitir."
    )

    CLIENT_EDIT_FIELD_PROMPT = (
        "✏️ *Editar Cliente*\n\n"
        "¿Qué campo deseas editar?\n\n"
        "1️⃣ Nombre completo\n"
        "2️⃣ Teléfono\n"
        "3️⃣ Nombre de usuario local\n"
        "0️⃣ Volver"
    )

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

    CLIENT_EDIT_ERROR_INVALID_FIELD = (
        "❌ Opción inválida. Responde con un número del *1* al *3* "
        "o *0* para volver."
    )

    CLIENT_DEACTIVATE_CONFIRM_TEMPLATE = (
        "⚠️ *Desactivar Cliente*\n\n"
        "¿Estás seguro de que deseas desactivar a *{name}*?\n\n"
        "Escribe *CONFIRMAR* para desactivar.\n"
        "Escribe *0* para cancelar."
    )

    CLIENT_DELETE_CONFIRM_TEMPLATE = (
        "⚠️ *Eliminar Cliente*\n\n"
        "¿Estás seguro de que deseas eliminar permanentemente "
        "a *{name}*?\n\n"
        "Esta acción no se puede deshacer.\n\n"
        "Escribe *CONFIRMAR* para eliminar.\n"
        "Escribe *0* para cancelar."
    )

    CLIENT_CANT_DELETE_ACTIVE = (
        "❌ No se puede eliminar un cliente activo.\n\n"
        "Desactívalo primero y luego intenta eliminarlo."
    )

    CLIENT_DEACTIVATE_SUCCESS = (
        "✅ Cliente *{name}* desactivado exitosamente."
    )

    CLIENT_REACTIVATE_SUCCESS = (
        "✅ Cliente *{name}* reactivado exitosamente."
    )

    CLIENT_DELETE_SUCCESS = (
        "✅ Cliente *{name}* eliminado permanentemente."
    )

    CLIENT_EDIT_SUCCESS = (
        "✅ Cliente *{name}* actualizado exitosamente."
    )

    CLIENT_CONFIRM_REPROMPT = (
        "❌ Para confirmar, escribe *CONFIRMAR* (en mayúsculas "
        "o minúsculas)."
    )

    CLIENT_INVALID_SELECTION = (
        "❌ Número inválido. Responde con un número de la lista "
        "o escribe *0* para volver al menú principal."
    )

    CLIENT_NAME_REQUIRED = "❌ El nombre completo no puede estar vacío."

    CLIENT_USERNAME_REQUIRED = "❌ El nombre de usuario no puede estar vacío."

    CLIENT_SHORT_PASSWORD = (
        "❌ La contraseña debe tener al menos 6 caracteres.\n\n"
        "Intenta de nuevo."
    )

    CLIENT_SKIP_WORDS = {"—", "skip", "ninguno", "none", "-"}

    # -- Catalog messages -------------------------------------------------

    CATALOG_MENU = (
        "📦 *Catálogo*\n\n"
        "1️⃣ Ver servicios\n"
        "0️⃣ Volver al menú principal"
    )

    CATALOG_NO_SERVICES = "📭 No hay servicios registrados."

    CATALOG_SERVICE_PROMPT = (
        "Responde con el número del servicio para ver sus detalles."
    )

    CATALOG_SERVICE_ACTIONS = (
        "*Acciones disponibles:*\n"
        "1️⃣ Editar nombre\n"
        "2️⃣ Ver planes\n"
        "0️⃣ Volver"
    )

    CATALOG_SERVICE_EDIT_PROMPT = (
        "✏️ *Editar Servicio*\n\n"
        "¿Cuál es el *nuevo nombre* del servicio?"
    )

    CATALOG_SERVICE_EDIT_SUCCESS = (
        "✅ Nombre del servicio actualizado a *{name}*."
    )

    CATALOG_PLAN_ACTIONS = (
        "*Acciones disponibles:*\n"
        "1️⃣ Editar nombre\n"
        "0️⃣ Volver"
    )

    CATALOG_NO_PLANS = "📭 No hay planes para este servicio."

    CATALOG_PLAN_PROMPT = (
        "Responde con el número del plan para ver sus detalles."
    )

    CATALOG_PLAN_EDIT_PROMPT = (
        "✏️ *Editar Plan*\n\n"
        "¿Cuál es el *nuevo nombre* del plan?"
    )

    CATALOG_PLAN_EDIT_SUCCESS = (
        "✅ Nombre del plan actualizado a *{name}*."
    )

    CATALOG_INVALID_SELECTION = (
        "❌ Número inválido. Responde con un número de la lista "
        "o escribe *0* para volver."
    )

    CATALOG_NAME_REQUIRED = "❌ El nombre no puede estar vacío."

    # -- Profile messages -------------------------------------------------

    PROFILE_MENU = (
        "👤 *Mi Perfil*\n\n"
        "1️⃣ Ver perfil\n"
        "2️⃣ Editar perfil\n"
        "3️⃣ Cambiar contraseña\n"
        "0️⃣ Volver al menú principal"
    )

    PROFILE_EDIT_FIELD_PROMPT = (
        "✏️ *Editar Perfil*\n\n"
        "¿Qué campo deseas editar?\n\n"
        "1️⃣ Nombre completo\n"
        "2️⃣ Email\n"
        "3️⃣ Teléfono\n"
        "0️⃣ Volver"
    )

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

    PROFILE_EDIT_ERROR_INVALID_FIELD = (
        "❌ Opción inválida. Responde con un número del *1* al *3* "
        "o *0* para volver."
    )

    PROFILE_EDIT_SUCCESS = "✅ Perfil actualizado exitosamente."

    PROFILE_CHANGE_PASSWORD_PROMPT_OLD = (
        "🔑 *Cambiar Contraseña*\n\n"
        "Escribe tu *contraseña actual*."
    )

    PROFILE_CHANGE_PASSWORD_PROMPT_NEW = (
        "🔑 *Cambiar Contraseña*\n\n"
        "Escribe tu *nueva contraseña*.\n\n"
        "La contraseña debe tener al menos *6 caracteres*."
    )

    PROFILE_CHANGE_PASSWORD_ERROR_OLD = (
        "❌ La contraseña actual no es correcta.\n\n"
        "Intenta de nuevo o escribe *0* para cancelar."
    )

    PROFILE_CHANGE_PASSWORD_SUCCESS = (
        "✅ *Contraseña cambiada exitosamente.*"
    )

    # ------------------------------------------------------------------
    # Constructor
    # ------------------------------------------------------------------

    def __init__(
        self,
        client_service: ClientServiceProtocol | None = None,
        catalog_service: CatalogServiceProtocol | None = None,
        profile_service: Any = None,
    ) -> None:
        self._client_service = client_service
        self._catalog_service = catalog_service
        self._profile_service = profile_service

    # ------------------------------------------------------------------
    # Reply composition helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _with_main_menu(message: str) -> str:
        """Append the ``MAIN_MENU`` to *message*."""
        return message.rstrip() + "\n\n" + WhatsAppTenantConsoleService.MAIN_MENU

    @staticmethod
    def _format_client_list(clients: list[Any]) -> tuple[str, dict[str, str]]:
        entries: list[str] = []
        selection_map: dict[str, str] = {}
        active_count = 0
        for i, c in enumerate(clients, start=1):
            num = str(i)
            status = "Activo" if c.is_active else "Inactivo"
            entries.append(f"{num}️⃣ {c.full_name} ({status})")
            selection_map[num] = str(c.id)
            if c.is_active:
                active_count += 1
        inactive_count = len(clients) - active_count
        header = (
            "📋 *Lista de Clientes*\n"
            f"Activos: {active_count} | Inactivos: {inactive_count}\n\n"
        )
        return header + "\n".join(entries), selection_map

    @staticmethod
    def _format_client_detail(client: Any) -> str:
        status_emoji = "✅ Activo" if client.is_active else "❌ Inactivo"
        actions = (
            WhatsAppTenantConsoleService.CLIENT_DETAIL_ACTIVE_ACTIONS
            if client.is_active
            else WhatsAppTenantConsoleService.CLIENT_DETAIL_INACTIVE_ACTIONS
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
            f"👤 *Detalle del Cliente*\n\n"
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
    def _safe_uuid(value: str | None) -> UUID | None:
        """Convert *value* to ``UUID`` or return ``None`` on failure."""
        if value is None:
            return None
        try:
            return UUID(value)
        except (ValueError, AttributeError):
            return None

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
    ) -> str:
        """Process a WhatsApp message and return the reply text.

        Args:
            phone: Normalised phone number of the sender.
            message: Text of the WhatsApp message.
            tenant_id: Resolved tenant UUID for scoped operations.
            user_id: Resolved user UUID for profile operations.
            db: Database session for CRUD operations.
            session_service: ``WhatsAppSessionService`` for persistence.

        Returns:
            Reply text that n8n will send through Evolution API.
        """
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
                        return self._with_main_menu("🚫 Operación cancelada.")
                    return self._with_main_menu("🚫 Operación cancelada.")
                if msg == "0":
                    return self._with_main_menu("👋 Has salido de la consola.")
                return self.MAIN_MENU

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
                return self.HELP_TEXT

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
                return self.MAIN_MENU

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
            return self.FALLBACK_NO_FLOW

        except RedisUnavailableError:
            return ContingencyReplyPolicy.TEMPORARY_UNAVAILABLE

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
                return self.CLIENTS_MENU  # catalog menu placeholder
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

        return self.FALLBACK_ACTIVE_FLOW

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
        return self.CLIENTS_MENU

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
                return self.CLIENT_NO_CLIENTS
            clients = await self._client_service.list_clients(db, tenant_id)
            if not clients:
                return self._with_main_menu(self.CLIENT_NO_CLIENTS)
            reply, selection_map = self._format_client_list(clients)
            reply += "\n\n" + self.CLIENT_SELECT_PROMPT
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
                    return self.CLIENT_INVALID_SELECTION
                parsed_id = self._safe_uuid(client_id)
                if parsed_id is None:
                    return self.CLIENT_INVALID_SELECTION
                client = await self._client_service.get_client(db, tenant_id, parsed_id)
                if client:
                    reply = self._format_client_detail(client)
                    if session_service is not None:
                        session.selected_tenant_id = client_id
                        session.step = self.CLIENTS_STEP_DETAIL_ACTION
                        await session_service.save_session(session)
                    return reply
            return self.CLIENT_INVALID_SELECTION

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
                return self.CLIENT_INVALID_SELECTION
            parsed_id = self._safe_uuid(client_id)
            if parsed_id is None:
                return self.CLIENT_INVALID_SELECTION
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
        return self.CLIENT_INVALID_SELECTION

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
            return self.CLIENT_INVALID_SELECTION

        parsed_id = self._safe_uuid(client_id)
        if parsed_id is None:
            return self.CLIENT_INVALID_SELECTION

        if msg == "1":
            # Edit flow
            return await self._start_client_edit(phone, session, session_service)
        elif msg == "2":
            # Deactivate or reactivate
            if db is None or self._client_service is None:
                return self.CLIENT_INVALID_SELECTION
            client = await self._client_service.get_client(db, tenant_id, parsed_id)
            if client is None:
                return self.CLIENT_INVALID_SELECTION
            if client.is_active:
                session.flow = self.CLIENTS_FLOW
                session.step = self.CLIENTS_STEP_DEACTIVATE_CONFIRM
                if session_service is not None:
                    await session_service.save_session(session)
                return self.CLIENT_DEACTIVATE_CONFIRM_TEMPLATE.format(name=client.full_name)
            else:
                # Reactivate immediately
                await self._client_service.activate_client(db, tenant_id, parsed_id)
                if session_service is not None:
                    await session_service.clear_session(f"admin:{phone}")
                return self._with_main_menu(
                    self.CLIENT_REACTIVATE_SUCCESS.format(name=client.full_name)
                )
        elif msg == "3":
            # Delete
            if db is None or self._client_service is None:
                return self.CLIENT_INVALID_SELECTION
            client = await self._client_service.get_client(db, tenant_id, parsed_id)
            if client is None:
                return self.CLIENT_INVALID_SELECTION
            if client.is_active:
                return self.CLIENT_CANT_DELETE_ACTIVE
            session.flow = self.CLIENTS_FLOW
            session.step = self.CLIENTS_STEP_DELETE_CONFIRM
            if session_service is not None:
                await session_service.save_session(session)
            return self.CLIENT_DELETE_CONFIRM_TEMPLATE.format(name=client.full_name)
        elif msg == "0":
            if session_service is not None:
                await session_service.clear_session(f"admin:{phone}")
            return self.MAIN_MENU
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
        return self.CLIENT_CREATE_PROMPT_FULL_NAME

    async def _handle_client_create_full_name(
        self,
        phone: str,
        msg: str,
        session: Any,
        session_service: WhatsAppSessionService | None,
    ) -> str:
        name = msg.strip()
        if not name:
            return self.CLIENT_NAME_REQUIRED
        session.temp_data["full_name"] = name
        session.step = self.CLIENTS_STEP_CREATE_PHONE
        if session_service is not None:
            await session_service.save_session(session)
        return self.CLIENT_CREATE_PROMPT_PHONE

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
                return self.CLIENT_CREATE_ERROR_PHONE
        session.step = self.CLIENTS_STEP_CREATE_USERNAME
        if session_service is not None:
            await session_service.save_session(session)
        return self.CLIENT_CREATE_PROMPT_USERNAME

    async def _handle_client_create_username(
        self,
        phone: str,
        msg: str,
        session: Any,
        session_service: WhatsAppSessionService | None,
    ) -> str:
        username = msg.strip()
        if not username:
            return self.CLIENT_USERNAME_REQUIRED
        session.temp_data["local_username"] = username.lower()
        session.step = self.CLIENTS_STEP_CREATE_PASSWORD
        if session_service is not None:
            await session_service.save_session(session)
        return self.CLIENT_CREATE_PROMPT_PASSWORD

    async def _handle_client_create_password(
        self,
        phone: str,
        msg: str,
        session: Any,
        session_service: WhatsAppSessionService | None,
    ) -> str:
        password = msg.strip()
        if len(password) < 6:
            return self.CLIENT_SHORT_PASSWORD
        session.temp_data["password"] = password
        session.step = self.CLIENTS_STEP_CREATE_CONFIRM
        if session_service is not None:
            await session_service.save_session(session)
        data = session.temp_data
        return self.CLIENT_CREATE_CONFIRM_TEMPLATE.format(
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
        if stripped.upper() != "CONFIRMAR":
            data = session.temp_data
            return (
                self.CLIENT_CONFIRM_REPROMPT + "\n\n"
                + self.CLIENT_CREATE_CONFIRM_TEMPLATE.format(
                    name=data.get("full_name", ""),
                    username=data.get("local_username", ""),
                    phone=data.get("phone") or "—",
                )
            )
        data = session.temp_data
        if tenant_id is None or db is None or self._client_service is None:
            return "❌ No se pudo crear el cliente. Servicio no disponible."

        from app.schemas.client import ClientCreate

        payload = ClientCreate(
            full_name=data.get("full_name", ""),
            local_username=data.get("local_username", ""),
            phone=data.get("phone"),
            password=data.get("password", ""),
        )
        try:
            client = await self._client_service.create_client(db, tenant_id, payload)
        except ValueError as exc:
            error = str(exc)
            if "phone" in error.lower() or "teléfono" in error.lower():
                session.step = self.CLIENTS_STEP_CREATE_PHONE
                if session_service is not None:
                    await session_service.save_session(session)
                return "❌ " + error + "\n\n" + self.CLIENT_CREATE_PROMPT_PHONE
            if "username" in error.lower() or "usuario" in error.lower():
                session.step = self.CLIENTS_STEP_CREATE_USERNAME
                if session_service is not None:
                    await session_service.save_session(session)
                return "❌ " + error + "\n\n" + self.CLIENT_CREATE_PROMPT_USERNAME
            return "❌ " + error

        if client is None:
            return "❌ Error al crear el cliente."

        if session_service is not None:
            await session_service.clear_session(f"admin:{phone}")

        full_username = getattr(client.user, "username", data.get("local_username", ""))
        return self._with_main_menu(
            self.CLIENT_CREATE_SUCCESS.format(
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
        return self.CLIENT_EDIT_FIELD_PROMPT

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
            return self.MAIN_MENU
        field = self.CLIENT_EDIT_FIELD_MAP.get(msg)
        if field is None:
            return self.CLIENT_EDIT_ERROR_INVALID_FIELD
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
            return "❌ No se pudo actualizar el cliente."
        parsed_id = self._safe_uuid(client_id)
        if parsed_id is None:
            return "❌ No se pudo actualizar el cliente."

        from app.schemas.client import ClientUpdate
        payload = ClientUpdate(**{field: new_value})
        try:
            client = await self._client_service.update_client(
                db, tenant_id, parsed_id, payload
            )
        except ValueError as exc:
            return "❌ " + str(exc)
        except Exception as exc:
            return "❌ " + str(exc)

        if client is None:
            return "❌ Cliente no encontrado."

        if session_service is not None:
            await session_service.clear_session(f"admin:{phone}")
        return self._with_main_menu(
            self.CLIENT_EDIT_SUCCESS.format(name=client.full_name)
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
        if stripped.upper() != "CONFIRMAR":
            return self.CLIENT_CONFIRM_REPROMPT
        client_id = session.selected_tenant_id
        if not client_id or tenant_id is None or db is None or self._client_service is None:
            return "❌ No se pudo desactivar el cliente."
        parsed_id = self._safe_uuid(client_id)
        if parsed_id is None:
            return "❌ No se pudo desactivar el cliente."
        client = await self._client_service.deactivate_client(db, tenant_id, parsed_id)
        if client is None:
            return "❌ Cliente no encontrado."
        if session_service is not None:
            await session_service.clear_session(f"admin:{phone}")
        return self._with_main_menu(
            self.CLIENT_DEACTIVATE_SUCCESS.format(name=client.full_name)
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
        if stripped.upper() != "CONFIRMAR":
            return self.CLIENT_CONFIRM_REPROMPT
        client_id = session.selected_tenant_id
        if not client_id or tenant_id is None or db is None or self._client_service is None:
            return "❌ No se pudo eliminar el cliente."
        parsed_id = self._safe_uuid(client_id)
        if parsed_id is None:
            return "❌ No se pudo eliminar el cliente."
        client_name = client_id  # fallback
        client = await self._client_service.get_client(db, tenant_id, parsed_id)
        if client:
            client_name = client.full_name
        deleted = await self._client_service.delete_client(db, tenant_id, parsed_id)
        if not deleted:
            return "❌ No se pudo eliminar el cliente."
        if session_service is not None:
            await session_service.clear_session(f"admin:{phone}")
        return self._with_main_menu(
            self.CLIENT_DELETE_SUCCESS.format(name=client_name)
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
            return self._with_main_menu(self.CATALOG_NO_SERVICES)
        if session_service is not None:
            session = await session_service.get_session(f"admin:{phone}")
            if session is None:
                session = await session_service.create_session(f"admin:{phone}")
            session.flow = self.CATALOG_FLOW
            session.step = self.CATALOG_STEP_SERVICE_SELECT
            session.selection_map = selection_map
            await session_service.save_session(session)
        return reply + "\n\n" + self.CATALOG_SERVICE_PROMPT

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
            return self.MAIN_MENU
        service_id = session.selection_map.get(msg)
        if not service_id or tenant_id is None or db is None or self._catalog_service is None:
            return self.CATALOG_INVALID_SELECTION
        parsed_id = self._safe_uuid(service_id)
        if parsed_id is None:
            return self.CATALOG_INVALID_SELECTION
        service = await self._catalog_service.get_service(db, tenant_id, parsed_id)
        if service is None:
            return self.CATALOG_INVALID_SELECTION
        session.flow = self.CATALOG_FLOW
        session.step = self.CATALOG_STEP_SERVICE_ACTION
        session.selected_tenant_id = service_id
        if session_service is not None:
            await session_service.save_session(session)
        return (
            self._format_service_detail(service) + "\n"
            + self.CATALOG_SERVICE_ACTIONS
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
            return self.CATALOG_INVALID_SELECTION
        if msg == "1":
            # Edit service name
            session.flow = self.CATALOG_FLOW
            session.step = self.CATALOG_STEP_EDIT_SERVICE
            if session_service is not None:
                await session_service.save_session(session)
            return self.CATALOG_SERVICE_EDIT_PROMPT
        elif msg == "2":
            # View plans
            if tenant_id is None or db is None or self._catalog_service is None:
                return self.CATALOG_NO_PLANS
            parsed_id = self._safe_uuid(service_id)
            if parsed_id is None:
                return self.CATALOG_INVALID_SELECTION
            plans = await self._catalog_service.list_plans(db, tenant_id, parsed_id)
            if not plans:
                return self._with_main_menu(self.CATALOG_NO_PLANS)
            reply, selection_map = self._format_plan_list(plans)
            session.flow = self.CATALOG_FLOW
            session.step = self.CATALOG_STEP_PLAN_SELECT
            session.selection_map = selection_map
            if session_service is not None:
                await session_service.save_session(session)
            return reply + "\n\n" + self.CATALOG_PLAN_PROMPT
        elif msg == "0":
            if session_service is not None:
                await session_service.clear_session(f"admin:{phone}")
            return self.MAIN_MENU
        return self.CATALOG_INVALID_SELECTION

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
            return self.CATALOG_NAME_REQUIRED
        service_id = session.selected_tenant_id
        if not service_id or tenant_id is None or db is None or self._catalog_service is None:
            return "❌ No se pudo actualizar el servicio."
        parsed_id = self._safe_uuid(service_id)
        if parsed_id is None:
            return "❌ No se pudo actualizar el servicio."
        from app.schemas.catalog import ServiceUpdate
        try:
            service = await self._catalog_service.update_service(
                db, tenant_id, parsed_id, ServiceUpdate(name=name)
            )
        except ValueError as exc:
            return "❌ " + str(exc)
        if service is None:
            return "❌ Servicio no encontrado."
        if session_service is not None:
            await session_service.clear_session(f"admin:{phone}")
        return self._with_main_menu(
            self.CATALOG_SERVICE_EDIT_SUCCESS.format(name=service.name)
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
                return self.MAIN_MENU
            session.flow = self.CATALOG_FLOW
            session.step = self.CATALOG_STEP_SERVICE_SELECT
            session.selection_map = selection_map
            if session_service is not None:
                await session_service.save_session(session)
            return reply + "\n\n" + self.CATALOG_SERVICE_PROMPT
        plan_id = session.selection_map.get(msg)
        if not plan_id or tenant_id is None or db is None or self._catalog_service is None:
            return self.CATALOG_INVALID_SELECTION
        # We need the service_id from the session
        service_id = session.selected_tenant_id
        if service_id is None:
            return self.CATALOG_INVALID_SELECTION
        parsed_service_id = self._safe_uuid(service_id)
        parsed_plan_id = self._safe_uuid(plan_id)
        if parsed_service_id is None or parsed_plan_id is None:
            return self.CATALOG_INVALID_SELECTION
        plan = await self._catalog_service.get_plan(
            db, tenant_id, parsed_service_id, parsed_plan_id
        )
        if plan is None:
            return self.CATALOG_INVALID_SELECTION
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
            + self.CATALOG_PLAN_ACTIONS
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
            return self.CATALOG_INVALID_SELECTION
        if msg == "1":
            session.flow = self.CATALOG_FLOW
            session.step = self.CATALOG_STEP_EDIT_PLAN
            if session_service is not None:
                await session_service.save_session(session)
            return self.CATALOG_PLAN_EDIT_PROMPT
        elif msg == "0":
            # Back to service list
            reply, selection_map = await self._fetch_service_list(tenant_id, db)
            if reply is None:
                if session_service is not None:
                    await session_service.clear_session(f"admin:{phone}")
                return self.MAIN_MENU
            session.flow = self.CATALOG_FLOW
            session.step = self.CATALOG_STEP_SERVICE_SELECT
            session.selection_map = selection_map
            if session_service is not None:
                await session_service.save_session(session)
            return reply + "\n\n" + self.CATALOG_SERVICE_PROMPT
        return self.CATALOG_INVALID_SELECTION

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
            return self.CATALOG_NAME_REQUIRED
        plan_id = session.selected_tenant_id
        service_id = session.temp_data.get("service_id")
        if not plan_id or not service_id or tenant_id is None or db is None or self._catalog_service is None:
            return "❌ No se pudo actualizar el plan."
        parsed_service_id = self._safe_uuid(service_id)
        parsed_plan_id = self._safe_uuid(plan_id)
        if parsed_service_id is None or parsed_plan_id is None:
            return "❌ No se pudo actualizar el plan."
        from app.schemas.catalog import PlanUpdate
        try:
            plan = await self._catalog_service.update_plan(
                db, tenant_id, parsed_service_id, parsed_plan_id, PlanUpdate(name=name)
            )
        except ValueError as exc:
            return "❌ " + str(exc)
        if plan is None:
            return "❌ Plan no encontrado."
        if session_service is not None:
            await session_service.clear_session(f"admin:{phone}")
        return self._with_main_menu(
            self.CATALOG_PLAN_EDIT_SUCCESS.format(name=plan.name)
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
        return self.PROFILE_MENU

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
        elif msg == "0":
            return self._with_main_menu("")
        return self.FALLBACK_NO_FLOW

    async def _show_profile(
        self,
        phone: str,
        session_service: WhatsAppSessionService | None,
        user_id: UUID | None,
        db: AsyncSession | None,
    ) -> str:
        if user_id is None or db is None or self._profile_service is None:
            return "❌ No se pudo obtener el perfil."
        from app.crud import users as user_crud
        user = await user_crud.get(db, user_id)
        if user is None:
            return "❌ Usuario no encontrado."
        profile = await self._profile_service.get_profile(db, user)
        if profile is None:
            return "❌ Perfil no encontrado."
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
        return self.PROFILE_EDIT_FIELD_PROMPT

    async def _handle_profile_edit_field(
        self,
        phone: str,
        msg: str,
        session: Any,
        session_service: WhatsAppSessionService | None,
    ) -> str:
        if msg == "0":
            await session_service.clear_session(f"admin:{phone}")
            return self.MAIN_MENU
        field = self.PROFILE_EDIT_FIELD_MAP.get(msg)
        if field is None:
            return self.PROFILE_EDIT_ERROR_INVALID_FIELD
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
            return "❌ No se pudo actualizar el perfil."
        from app.crud import users as user_crud
        user = await user_crud.get(db, user_id)
        if user is None:
            return "❌ Usuario no encontrado."
        from app.schemas.me import ProfileUpdate
        payload = ProfileUpdate(**{field: new_value})
        try:
            profile = await self._profile_service.update_profile(db, user, payload)
        except ValueError as exc:
            return "❌ " + str(exc)
        if profile is None:
            return "❌ No se pudo actualizar el perfil."
        if session_service is not None:
            await session_service.clear_session(f"admin:{phone}")
        return self._with_main_menu(self.PROFILE_EDIT_SUCCESS)

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
        return self.PROFILE_CHANGE_PASSWORD_PROMPT_OLD

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
            return self.PROFILE_CHANGE_PASSWORD_PROMPT_OLD
        session.temp_data["old_password"] = old_password
        session.step = self.PROFILE_STEP_CHANGE_PASSWORD_NEW
        if session_service is not None:
            await session_service.save_session(session)
        return self.PROFILE_CHANGE_PASSWORD_PROMPT_NEW

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
            return "❌ La contraseña debe tener al menos 6 caracteres.\n\n" + self.PROFILE_CHANGE_PASSWORD_PROMPT_NEW
        if user_id is None or db is None or self._profile_service is None:
            return "❌ No se pudo cambiar la contraseña."
        from app.crud import users as user_crud
        user = await user_crud.get(db, user_id)
        if user is None:
            return "❌ Usuario no encontrado."
        success = await self._profile_service.change_password(db, user, old_password, new_password)
        if not success:
            return self.PROFILE_CHANGE_PASSWORD_ERROR_OLD
        if session_service is not None:
            await session_service.clear_session(f"admin:{phone}")
        return self._with_main_menu(self.PROFILE_CHANGE_PASSWORD_SUCCESS)
