"""WhatsApp Master Console service — conversation flow routing.

Owns conversation state transitions, menu routing, help, fallback, global
reset commands, and CRUD decisions.  Concrete Tenant CRUD flows are added
in Phases 5–8.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.core.redis_client import RedisUnavailableError
from app.services.contingency_reply_policy import ContingencyReplyPolicy


class WhatsAppConsoleService:
    """Route incoming WhatsApp messages for the Master Console.

    Owns conversation state transitions, menu routing, and CRUD decisions.
    """

    # ------------------------------------------------------------------
    # Reply templates
    # ------------------------------------------------------------------

    MAIN_MENU = (
        "🤖 *Trackpal Master Console*\n\n"
        "1️⃣ Ver Tenants\n"
        "2️⃣ Crear Tenant\n"
        "3️⃣ Desactivar Tenant\n"
        "4️⃣ Eliminar Tenant\n"
        "5️⃣ Ayuda\n\n"
        "0️⃣ Cancelar / Menú\n\n"
        "Responde con el número de la opción deseada."
    )

    ACCESS_DENIED = (
        "⚠️ Este servicio solo está disponible para el Master de Trackpal."
    )

    HELP_TEXT = (
        "🤖 *Ayuda - Trackpal Master Console*\n\n"
        "Los comandos disponibles son:\n\n"
        "1️⃣ *Ver Tenants* — Muestra la lista de tenants.\n"
        "2️⃣ *Crear Tenant* — Inicia el flujo de creación.\n"
        "3️⃣ *Desactivar Tenant* — Desactiva un tenant activo.\n"
        "4️⃣ *Eliminar Tenant* — Elimina un tenant inactivo.\n"
        "5️⃣ *Ayuda* — Muestra este mensaje de ayuda.\n"
        "0️⃣ *Cancelar / Menú* — Vuelve al menú principal.\n\n"
        "En cualquier momento puedes enviar \"0\", \"menu\", \"menú\" "
        "o \"cancelar\" para volver al menú principal."
    )

    FALLBACK_NO_FLOW = (
        "❌ No entendí tu mensaje.\n\n"
        "Responde con:\n"
        "• Un número del *1* al *5* para elegir una opción del menú\n"
        "• *0* o *menu* para volver al menú principal\n"
        "• *ayuda* para ver los comandos disponibles"
    )

    FALLBACK_ACTIVE_FLOW = (
        "❌ No entendí tu mensaje.\n\n"
        "Estás en medio de un flujo. Responde con la información "
        "solicitada o escribe *0* para cancelar y volver al menú "
        "principal."
    )

    RESET_COMMANDS = {"0", "menu", "menú", "cancelar"}
    HELP_COMMANDS = {"5", "ayuda"}

    # Flow identifiers
    LIST_FLOW = "list_tenants"
    SELECT_STEP = "select"
    DETAIL_FLOW = "tenant_detail"
    ACTIONS_STEP = "actions"
    CREATE_FLOW = "create_tenant"
    DEACTIVATE_FLOW = "deactivate_tenant"
    DELETE_FLOW = "delete_tenant"
    CONFIRM_DEACTIVATE_STEP = "confirm_deactivate"
    CONFIRM_DELETE_STEP = "confirm_delete"

    # Create flow steps
    CREATE_STEP_FULL_NAME = "full_name"
    CREATE_STEP_EMAIL = "email"
    CREATE_STEP_PHONE = "phone"
    CREATE_STEP_USERNAME = "username"
    CREATE_STEP_EVOLUTION_INSTANCE = "evolution_instance"
    CREATE_STEP_PASSWORD_MODE = "password_mode"
    CREATE_STEP_MANUAL_PASSWORD = "manual_password"
    CREATE_STEP_CONFIRM = "confirm"

    TENANT_DETAIL_ACTIVE_ACTIONS = (
        "*Acciones disponibles:*\n"
        "1️⃣ Editar\n"
        "2️⃣ Desactivar\n"
        "3️⃣ Eliminar (solo inactivos)\n"
        "0️⃣ Volver al menú"
    )

    TENANT_DETAIL_INACTIVE_ACTIONS = (
        "*Acciones disponibles:*\n"
        "1️⃣ Editar\n"
        "2️⃣ Reactivar\n"
        "3️⃣ Eliminar\n"
        "0️⃣ Volver al menú"
    )

    INVALID_SELECTION = (
        "❌ Número inválido. Responde con un número de la lista "
        "o escribe *0* para volver al menú principal."
    )

    NO_TENANTS = "📭 No hay tenants registrados."

    # Create flow prompts
    CREATE_PROMPT_FULL_NAME = (
        "✏️ *Crear Tenant*\n\n"
        "Vamos a crear un nuevo tenant.\n\n"
        "¿Cuál es el *nombre completo* del tenant?"
    )

    CREATE_PROMPT_EMAIL = (
        "✏️ *Crear Tenant*\n\n"
        "¿Cuál es el *email* del tenant?\n\n"
        "(Opcional — escribe *—* para omitir)"
    )

    CREATE_PROMPT_PHONE = (
        "✏️ *Crear Tenant*\n\n"
        "¿Cuál es el *teléfono* del tenant?\n\n"
        "(Opcional — escribe *—* para omitir)"
    )

    CREATE_PROMPT_USERNAME = (
        "✏️ *Crear Tenant*\n\n"
        "¿Cuál es el *nombre de usuario* para el tenant?\n\n"
        "(Se usará para iniciar sesión en Trackpal)"
    )

    CREATE_PROMPT_EVOLUTION_INSTANCE = (
        "✏️ *Crear Tenant*\n\n"
        "¿Cuál es el *nombre de la instancia de Evolution*?"
    )

    CREATE_PROMPT_PASSWORD_MODE = (
        "✏️ *Crear Tenant*\n\n"
        "¿Cómo deseas generar la contraseña?\n\n"
        "1️⃣ *Automática* (recomendado)\n"
        "2️⃣ *Manual* (tú la escribes)"
    )

    CREATE_PROMPT_MANUAL_PASSWORD = (
        "✏️ *Crear Tenant*\n\n"
        "Escribe la *contraseña* manualmente.\n\n"
        "⚠️  Ten en cuenta que estás enviando una contraseña "
        "a través de WhatsApp. Asegúrate de estar en un "
        "entorno seguro.\n\n"
        "La contraseña debe tener al menos *6 caracteres*."
    )

    CREATE_PROMPT_INVALID_PASSWORD_MODE = (
        "❌ Opción inválida. Responde *1* para contraseña automática "
        "o *2* para escribirla manualmente."
    )

    CREATE_ERROR_SHORT_PASSWORD = (
        "❌ La contraseña debe tener al menos 6 caracteres.\n\n"
        "Intenta de nuevo con una contraseña más larga."
    )

    CREATE_ERROR_USERNAME_EMPTY = (
        "❌ El nombre de usuario no puede estar vacío.\n\n"
        "Intenta de nuevo."
    )

    CREATE_ERROR_INSTANCE_EMPTY = (
        "❌ El nombre de instancia Evolution no puede estar vacío.\n\n"
        "Intenta de nuevo."
    )

    SKIP_WORDS = {"—", "skip", "ninguno", "none", "-"}

    # Edit flow identifiers
    EDIT_FLOW = "edit_tenant"
    EDIT_STEP_SELECT_FIELD = "select_field"
    EDIT_STEP_NEW_VALUE = "new_value"

    EDIT_PROMPT_SELECT_FIELD = (
        "✏️ *Editar Tenant*",
        "",
        "¿Qué campo deseas editar?",
        "",
        "1️⃣ Nombre completo",
        "2️⃣ Email",
        "3️⃣ Teléfono",
        "4️⃣ Instancia Evolution",
        "0️⃣ Volver al menú",
    )

    EDIT_FIELD_MAP = {
        "1": "full_name",
        "2": "email",
        "3": "phone",
        "4": "evolution_instance_name",
    }

    EDIT_FIELD_PROMPTS = {
        "full_name": (
            "✏️ *Editar Tenant*\n\n"
            "¿Cuál es el *nuevo nombre completo*?"
        ),
        "email": (
            "✏️ *Editar Tenant*\n\n"
            "¿Cuál es el *nuevo email*?"
        ),
        "phone": (
            "✏️ *Editar Tenant*\n\n"
            "¿Cuál es el *nuevo teléfono*?"
        ),
        "evolution_instance_name": (
            "✏️ *Editar Tenant*\n\n"
            "¿Cuál es el *nuevo nombre de instancia Evolution*?"
        ),
    }

    EDIT_ERROR_INVALID_FIELD = (
        "❌ Opción inválida. Responde con un número del *1* al *4* "
        "para elegir el campo a editar, o *0* para volver al menú."
    )

    EDIT_ERROR_UPDATE_FAILED = (
        "❌ No se pudo actualizar el campo. Intenta de nuevo o "
        "escribe *0* para cancelar."
    )

    EDIT_DETAIL_FALLBACK = (
        "❌ Opción inválida. Responde con un número de las "
        "acciones disponibles o *0* para volver al menú."
    )

    # Lifecycle flow prompts
    DEACTIVATE_CONFIRM_PROMPT = (
        "⚠️ *Desactivar Tenant*\n\n"
        "¿Estás seguro de que deseas desactivar a *{name}*?\n\n"
        "Este tenant:\n"
        "• Estado actual: ✅ Activo\n"
        "• No podrá iniciar sesión ni ser identificado después "
        "de la desactivación.\n\n"
        "Escribe *CONFIRMAR* para desactivar el tenant.\n"
        "Escribe *0* para cancelar."
    )

    DELETE_CONFIRM_PROMPT = (
        "⚠️ *Eliminar Tenant*\n\n"
        "¿Estás seguro de que deseas eliminar permanentemente "
        "a *{name}*?\n\n"
        "Este tenant:\n"
        "• Estado actual: ❌ Inactivo\n"
        "• Esta acción no se puede deshacer.\n\n"
        "Escribe *CONFIRMAR* para eliminar el tenant "
        "permanentemente.\n"
        "Escribe *0* para cancelar."
    )

    CANT_DELETE_ACTIVE_MESSAGE = (
        "❌ No se puede eliminar un tenant activo.\n\n"
        "Desactiva el tenant primero usando la opción "
        "*Desactivar* y luego intenta eliminarlo."
    )

    ALREADY_INACTIVE_MESSAGE = (
        "ℹ️ El tenant *{name}* ya está inactivo.\n\n"
        "Puedes reactivarlo desde la pantalla de detalle."
    )

    REACTIVATE_SUCCESS_MESSAGE = (
        "✅ *Tenant Reactivado*\n\n"
        "El tenant *{name}* ha sido reactivado exitosamente."
    )

    DEACTIVATE_SUCCESS_MESSAGE = (
        "✅ *Tenant Desactivado*\n\n"
        "El tenant *{name}* ha sido desactivado exitosamente."
    )

    DELETE_SUCCESS_MESSAGE = (
        "✅ *Tenant Eliminado*\n\n"
        "El tenant *{name}* ha sido eliminado permanentemente."
    )

    CONFIRM_REPROMPT = (
        "❌ Para confirmar, escribe *CONFIRMAR* (en mayúsculas "
        "o minúsculas)."
    )

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

        msg = message.strip()

        try:
            # ------------------------------------------------------------------
            # Global reset — always works regardless of session state
            # ------------------------------------------------------------------
            if msg.lower() in self.RESET_COMMANDS:
                if session_service is not None:
                    await session_service.clear_session(phone)
                return self.MAIN_MENU

            # ------------------------------------------------------------------
            # Retrieve current session (if available)
            # ------------------------------------------------------------------
            session = None
            if session_service is not None:
                session = await session_service.get_session(phone)

            has_active_flow = (
                session is not None
                and bool(session.flow)
            )

            # ------------------------------------------------------------------
            # Contingency reset — failover active, session missing on backup
            # ------------------------------------------------------------------
            if (
                session is None
                and session_service is not None
                and session_service.used_backup
                and msg.lower() not in self.RESET_COMMANDS
            ):
                # Create fresh session on backup so the next message does not
                # loop back to the reset reply.
                await session_service.create_session(phone)
                return ContingencyReplyPolicy.SESSION_RESET

            # ------------------------------------------------------------------
            # Help — reachable from any state
            # ------------------------------------------------------------------
            if msg.lower() in self.HELP_COMMANDS:
                return self.HELP_TEXT

            # ------------------------------------------------------------------
            # Active flow routing
            # ------------------------------------------------------------------
            if has_active_flow:
                if session.flow == self.LIST_FLOW and session.step == self.SELECT_STEP:
                    return await self._handle_list_selection(
                        phone, msg, session, session_service, tenant_service
                    )
                elif session.flow == self.CREATE_FLOW:
                    return await self._handle_create_step(
                        phone, msg, session, session_service, tenant_service
                    )
                elif session.flow == self.DETAIL_FLOW and session.step == self.ACTIONS_STEP:
                    return await self._handle_detail_action(
                        phone, msg, session, session_service, tenant_service
                    )
                elif session.flow == self.EDIT_FLOW:
                    return await self._handle_edit_step(
                        phone, msg, session, session_service, tenant_service
                    )
                elif session.flow == self.DEACTIVATE_FLOW and session.step == self.CONFIRM_DEACTIVATE_STEP:
                    return await self._handle_deactivate_confirm(
                        phone, msg, session, session_service, tenant_service
                    )
                elif session.flow == self.DELETE_FLOW and session.step == self.CONFIRM_DELETE_STEP:
                    return await self._handle_delete_confirm(
                        phone, msg, session, session_service, tenant_service
                    )
                return self.FALLBACK_ACTIVE_FLOW

            # ------------------------------------------------------------------
            # No active flow
            # ------------------------------------------------------------------

            # Empty/blank input — show the menu
            if not msg:
                return self.MAIN_MENU

            # Menu options 1-4 — when tenant_service is available, options 1,
            # 3, and 4 trigger the list flow.  Option 2 starts the create flow.
            # Without tenant_service, all numeric options return the main menu
            # (backward compatible).
            if msg in {"1", "2", "3", "4"}:
                if msg in {"1", "3", "4"} and tenant_service is not None:
                    return await self._handle_list_tenants(
                        phone, session_service, tenant_service
                    )
                if msg == "2":
                    return await self._start_create_flow(
                        phone, session_service
                    )
                return self.MAIN_MENU

            # Truly unrecognised input
            return self.FALLBACK_NO_FLOW

        except RedisUnavailableError:
            return ContingencyReplyPolicy.TEMPORARY_UNAVAILABLE

    # ------------------------------------------------------------------
    # Tenant list helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _format_tenant_list(tenants: list[Any]) -> tuple[str, dict[str, str]]:
        """Format a list of tenants as a numbered WhatsApp message.

        Returns:
            Tuple of (formatted_message, selection_map).
            ``selection_map`` maps displayed numbers (``"1"``) to UUID strings.
        """
        entries: list[str] = []
        selection_map: dict[str, str] = {}
        active_count = 0
        inactive_count = 0

        for i, tenant in enumerate(tenants, start=1):
            num = str(i)
            status = "Activo" if tenant.is_active else "Inactivo"
            entries.append(
                f"{num}️⃣ {tenant.full_name} ({status})"
            )
            selection_map[num] = str(tenant.id)
            if tenant.is_active:
                active_count += 1
            else:
                inactive_count += 1

        header = (
            "📋 *Lista de Tenants*\n"
            f"Activos: {active_count} | Inactivos: {inactive_count}\n\n"
        )
        body = "\n".join(entries)
        footer = "\n\nResponde con el número del tenant para ver sus detalles."

        return header + body + footer, selection_map

    @staticmethod
    def _format_tenant_detail(tenant: Any) -> str:
        """Format a single tenant as a detailed WhatsApp message."""
        status_emoji = "✅ Activo" if tenant.is_active else "❌ Inactivo"
        actions = (
            WhatsAppConsoleService.TENANT_DETAIL_ACTIVE_ACTIONS
            if tenant.is_active
            else WhatsAppConsoleService.TENANT_DETAIL_INACTIVE_ACTIONS
        )

        # Format created_at if available
        created = ""
        if tenant.created_at:
            if isinstance(tenant.created_at, datetime):
                created = tenant.created_at.strftime("%Y-%m-%d")
            else:
                created = str(tenant.created_at)

        return (
            f"👤 *Detalle del Tenant*\n\n"
            f"*Nombre:* {tenant.full_name}\n"
            f"*Usuario:* {tenant.username}\n"
            f"*Email:* {tenant.email or '—'}\n"
            f"*Teléfono:* {tenant.phone or '—'}\n"
            f"*Instancia Evolution:* {tenant.evolution_instance_name or '—'}\n"
            f"*Estado:* {status_emoji}\n"
            f"*Creado:* {created}\n\n"
            f"{actions}"
        )

    # ------------------------------------------------------------------
    # List tenants flow
    # ------------------------------------------------------------------

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

        reply, selection_map = self._format_tenant_list(tenants)

        # Store selection map in session
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
        msg: str,
        session,
        session_service,
        tenant_service,
    ) -> str:
        """Handle a numeric selection during the tenant list flow."""
        # Check if input is a number in the selection map
        if msg in session.selection_map:
            tenant_id = session.selection_map[msg]

            if tenant_service is not None:
                tenant = await tenant_service.get_tenant(tenant_id)
                if tenant is not None:
                    # Show detail screen and update session
                    reply = self._format_tenant_detail(tenant)
                    if session_service is not None:
                        session.flow = self.DETAIL_FLOW
                        session.step = self.ACTIONS_STEP
                        session.selected_tenant_id = tenant_id
                        session.selection_map = {}
                        await session_service.save_session(session)
                    return reply

            # Tenant not found or service unavailable
            return self.INVALID_SELECTION

        # Check for reset commands (already handled before this)
        # Check for help (already handled before this)
        # Anything else is invalid
        return self.INVALID_SELECTION

    # ------------------------------------------------------------------
    # Create tenant flow
    # ------------------------------------------------------------------

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

        return self.CREATE_PROMPT_FULL_NAME

    async def _handle_create_step(
        self,
        phone: str,
        msg: str,
        session,
        session_service,
        tenant_service,
    ) -> str:
        """Dispatch to the correct create flow step handler based on session.step."""
        if session.step == self.CREATE_STEP_FULL_NAME:
            return await self._handle_create_full_name(
                phone, msg, session, session_service
            )
        elif session.step == self.CREATE_STEP_EMAIL:
            return await self._handle_create_email(
                phone, msg, session, session_service
            )
        elif session.step == self.CREATE_STEP_PHONE:
            return await self._handle_create_phone(
                phone, msg, session, session_service
            )
        elif session.step == self.CREATE_STEP_USERNAME:
            return await self._handle_create_username(
                phone, msg, session, session_service, tenant_service
            )
        elif session.step == self.CREATE_STEP_EVOLUTION_INSTANCE:
            return await self._handle_create_evolution_instance(
                phone, msg, session, session_service
            )
        elif session.step == self.CREATE_STEP_PASSWORD_MODE:
            return await self._handle_create_password_mode(
                phone, msg, session, session_service
            )
        elif session.step == self.CREATE_STEP_MANUAL_PASSWORD:
            return await self._handle_create_manual_password(
                phone, msg, session, session_service
            )
        elif session.step == self.CREATE_STEP_CONFIRM:
            return await self._handle_create_confirm(
                phone, msg, session, session_service, tenant_service
            )
        return self.FALLBACK_ACTIVE_FLOW

    async def _handle_create_full_name(
        self,
        phone: str,
        msg: str,
        session,
        session_service,
    ) -> str:
        """Store full name and transition to email prompt."""
        full_name = msg.strip()
        if not full_name:
            return (
                "❌ El nombre completo no puede estar vacío.\n\n"
                + self.CREATE_PROMPT_FULL_NAME
            )

        session.temp_data["full_name"] = full_name
        session.step = self.CREATE_STEP_EMAIL
        if session_service is not None:
            await session_service.save_session(session)

        return self.CREATE_PROMPT_EMAIL

    async def _handle_create_email(
        self,
        phone: str,
        msg: str,
        session,
        session_service,
    ) -> str:
        """Store email (or None if skipped) and transition to phone prompt."""
        stripped = msg.strip()
        if not stripped or stripped.lower() in self.SKIP_WORDS:
            session.temp_data["email"] = None
        else:
            session.temp_data["email"] = stripped

        session.step = self.CREATE_STEP_PHONE
        if session_service is not None:
            await session_service.save_session(session)

        return self.CREATE_PROMPT_PHONE

    async def _handle_create_phone(
        self,
        phone: str,
        msg: str,
        session,
        session_service,
    ) -> str:
        """Store phone (or None if skipped) and transition to username prompt."""
        stripped = msg.strip()
        if not stripped or stripped.lower() in self.SKIP_WORDS:
            session.temp_data["phone"] = None
        else:
            session.temp_data["phone"] = stripped

        session.step = self.CREATE_STEP_USERNAME
        if session_service is not None:
            await session_service.save_session(session)

        return self.CREATE_PROMPT_USERNAME

    async def _handle_create_username(
        self,
        phone: str,
        msg: str,
        session,
        session_service,
        tenant_service,
    ) -> str:
        """Store username and transition to evolution instance prompt.

        If a ``tenant_service`` is available, the username is validated for
        duplicates *before* advancing the flow.  When the username is a
        duplicate, the error is shown and the step stays at ``username``.
        """
        username = msg.strip()
        if not username:
            return self.CREATE_ERROR_USERNAME_EMPTY

        # Validate duplicate username if tenant_service is available
        if tenant_service is not None and hasattr(tenant_service, "get_tenants"):
            # Check against existing usernames via a tenant lookup
            existing_tenants = await tenant_service.get_tenants()
            existing_usernames = {
                t.username for t in existing_tenants
            } if existing_tenants else set()
            if username in existing_usernames:
                return (
                    "❌ El nombre de usuario *" + username + "* ya está registrado.\n\n"
                    "Por favor, elige otro nombre de usuario."
                )

        session.temp_data["username"] = username
        session.step = self.CREATE_STEP_EVOLUTION_INSTANCE
        if session_service is not None:
            await session_service.save_session(session)

        return self.CREATE_PROMPT_EVOLUTION_INSTANCE

    async def _handle_create_evolution_instance(
        self,
        phone: str,
        msg: str,
        session,
        session_service,
    ) -> str:
        """Store evolution instance name and transition to password mode prompt."""
        instance = msg.strip()
        if not instance:
            return self.CREATE_ERROR_INSTANCE_EMPTY

        session.temp_data["evolution_instance_name"] = instance
        session.step = self.CREATE_STEP_PASSWORD_MODE
        if session_service is not None:
            await session_service.save_session(session)

        return self.CREATE_PROMPT_PASSWORD_MODE

    async def _handle_create_password_mode(
        self,
        phone: str,
        msg: str,
        session,
        session_service,
    ) -> str:
        """Handle password mode selection: auto or manual."""
        choice = msg.strip()

        if choice == "1":
            session.temp_data["password_mode"] = "auto"
            session.step = self.CREATE_STEP_CONFIRM
            if session_service is not None:
                await session_service.save_session(session)
            return await self._build_create_summary(session)

        elif choice == "2":
            session.temp_data["password_mode"] = "manual"
            session.step = self.CREATE_STEP_MANUAL_PASSWORD
            if session_service is not None:
                await session_service.save_session(session)
            return self.CREATE_PROMPT_MANUAL_PASSWORD

        else:
            return self.CREATE_PROMPT_INVALID_PASSWORD_MODE

    async def _handle_create_manual_password(
        self,
        phone: str,
        msg: str,
        session,
        session_service,
    ) -> str:
        """Store manual password and transition to confirmation."""
        password = msg.strip()
        if not password:
            return (
                "❌ La contraseña no puede estar vacía.\n\n"
                + self.CREATE_PROMPT_MANUAL_PASSWORD
            )
        if len(password) < 6:
            return self.CREATE_ERROR_SHORT_PASSWORD

        session.temp_data["password"] = password
        session.step = self.CREATE_STEP_CONFIRM
        if session_service is not None:
            await session_service.save_session(session)

        return await self._build_create_summary(session)

    async def _build_create_summary(
        self,
        session,
    ) -> str:
        """Build the creation summary with all collected data."""
        data = session.temp_data
        password_info = (
            "🔑 Automática (se generará automáticamente)"
            if data.get("password_mode") == "auto"
            else "🔑 Manual (la proporcionaste durante el flujo)"
        )

        return (
            "📋 *Resumen de Creación*\n\n"
            f"*Nombre completo:* {data.get('full_name', '—')}\n"
            f"*Email:* {data.get('email', '—') or '—'}\n"
            f"*Teléfono:* {data.get('phone', '—') or '—'}\n"
            f"*Usuario:* {data.get('username', '—')}\n"
            f"*Instancia Evolution:* {data.get('evolution_instance_name', '—')}\n"
            f"*Contraseña:* {password_info}\n\n"
            "¿Todo está correcto? Escribe *CONFIRMAR* para crear el tenant.\n"
            "Escribe *0* para cancelar y volver al menú principal."
        )

    async def _handle_create_confirm(
        self,
        phone: str,
        msg: str,
        session,
        session_service,
        tenant_service,
    ) -> str:
        """Handle confirmation: create the tenant or show errors."""
        stripped = msg.strip()

        if stripped.upper() != "CONFIRMAR":
            # Not confirmation — reprompt
            return (
                "❌ Para confirmar, escribe *CONFIRMAR* (en mayúsculas o minúsculas).\n\n"
                + await self._build_create_summary(session)
            )

        # Build the creation payload
        data = session.temp_data
        payload = {
            "full_name": data.get("full_name", ""),
            "email": data.get("email"),
            "phone": data.get("phone"),
            "username": data.get("username", ""),
            "evolution_instance_name": data.get("evolution_instance_name", ""),
        }

        if data.get("password_mode") == "manual":
            payload["password"] = data.get("password")

        # Attempt creation if tenant_service is available
        if tenant_service is not None and hasattr(tenant_service, "create_tenant"):
            result = await tenant_service.create_tenant(payload)
            if result.get("success"):
                tenant = result.get("tenant")
                auto_password = result.get("auto_password")

                # Clear session on success
                if session_service is not None:
                    await session_service.clear_session(phone)

                msg = (
                    "✅ *Tenant creado exitosamente*\n\n"
                    f"*Nombre:* {tenant.full_name}\n"
                    f"*Usuario:* {tenant.username}\n"
                    f"*Email:* {tenant.email or '—'}\n"
                    f"*Teléfono:* {tenant.phone or '—'}\n"
                )
                if auto_password:
                    msg += (
                        f"\n🔑 *Contraseña generada:*\n`{auto_password}`\n\n"
                        "⚠️  Guarda esta contraseña en un lugar seguro. "
                        "No podrás volver a verla."
                    )
                else:
                    msg += "\n🔑 Contraseña configurada manualmente.\n"

                return msg
            else:
                # Creation failed — keep collected data and return to the
                # field that the user can correct in-flow.
                error = result.get("error", "Error desconocido al crear el tenant.")
                error_lower = error.lower()
                if "phone" in error_lower or "teléfono" in error_lower:
                    session.step = self.CREATE_STEP_PHONE
                    if session_service is not None:
                        await session_service.save_session(session)
                    return "❌ " + error + "\n\n" + self.CREATE_PROMPT_PHONE
                if "username" in error_lower or "usuario" in error_lower:
                    session.step = self.CREATE_STEP_USERNAME
                    if session_service is not None:
                        await session_service.save_session(session)
                    return "❌ " + error + "\n\n" + self.CREATE_PROMPT_USERNAME
                return (
                    "❌ " + error + "\n\n"
                    + await self._build_create_summary(session)
                )

        # No tenant_service available
        return "❌ No se pudo crear el tenant. Servicio no disponible."

    # ------------------------------------------------------------------
    # Detail screen actions
    # ------------------------------------------------------------------

    async def _handle_detail_action(
        self,
        phone: str,
        msg: str,
        session,
        session_service,
        tenant_service,
    ) -> str:
        """Handle an action from the Tenant detail screen.

        Detail actions:
        1 → Start edit flow
        2 → Deactivate (active) or Reactivate (inactive)
        3 → Delete (inactive only)
        0 → Return to main menu
        """
        tenant_id = session.selected_tenant_id
        if not tenant_id:
            return self.EDIT_DETAIL_FALLBACK

        if msg == "1":
            return await self._start_edit_flow(
                phone, session, session_service, tenant_service
            )
        elif msg == "2":
            return await self._handle_detail_deactivate_reactivate(
                phone, tenant_id, session, session_service, tenant_service
            )
        elif msg == "3":
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

        If the tenant is active, start the deactivation confirmation flow.
        If the tenant is inactive, immediately reactivate.
        """
        if tenant_service is None or not hasattr(tenant_service, "get_tenant"):
            return self.EDIT_DETAIL_FALLBACK

        tenant = await tenant_service.get_tenant(tenant_id)
        if tenant is None:
            return self.INVALID_SELECTION

        if tenant.is_active:
            # Start deactivation flow — requires CONFIRMAR
            session.flow = self.DEACTIVATE_FLOW
            session.step = self.CONFIRM_DEACTIVATE_STEP
            if session_service is not None:
                await session_service.save_session(session)
            return self.DEACTIVATE_CONFIRM_PROMPT.format(name=tenant.full_name)
        else:
            # Immediately reactivate (no CONFIRMAR needed)
            if hasattr(tenant_service, "activate_tenant"):
                result = await tenant_service.activate_tenant(tenant_id)
                if result.get("success"):
                    if session_service is not None:
                        await session_service.clear_session(phone)
                    return self.REACTIVATE_SUCCESS_MESSAGE.format(name=tenant.full_name)
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

        If the tenant is active, block with explanation.
        If the tenant is inactive, start the deletion confirmation flow.
        """
        if tenant_service is None or not hasattr(tenant_service, "get_tenant"):
            return self.EDIT_DETAIL_FALLBACK

        tenant = await tenant_service.get_tenant(tenant_id)
        if tenant is None:
            return self.INVALID_SELECTION

        if tenant.is_active:
            return self.CANT_DELETE_ACTIVE_MESSAGE
        else:
            # Start deletion flow — requires CONFIRMAR
            session.flow = self.DELETE_FLOW
            session.step = self.CONFIRM_DELETE_STEP
            if session_service is not None:
                await session_service.save_session(session)
            return self.DELETE_CONFIRM_PROMPT.format(name=tenant.full_name)

    # ------------------------------------------------------------------
    # Lifecycle flow confirm handlers
    # ------------------------------------------------------------------

    async def _handle_deactivate_confirm(
        self,
        phone: str,
        msg: str,
        session,
        session_service,
        tenant_service,
    ) -> str:
        """Handle CONFIRMAR during deactivation flow."""
        stripped = msg.strip()

        if stripped.upper() != "CONFIRMAR":
            return self.CONFIRM_REPROMPT

        tenant_id = session.selected_tenant_id
        if not tenant_id:
            return self.EDIT_DETAIL_FALLBACK

        if tenant_service is not None and hasattr(tenant_service, "deactivate_tenant"):
            # Fetch tenant name for the success message
            tenant_name = tenant_id  # fallback
            if hasattr(tenant_service, "get_tenant"):
                tenant = await tenant_service.get_tenant(tenant_id)
                if tenant is not None:
                    tenant_name = tenant.full_name

            result = await tenant_service.deactivate_tenant(tenant_id)
            if result.get("success"):
                if session_service is not None:
                    await session_service.clear_session(phone)
                return self.DEACTIVATE_SUCCESS_MESSAGE.format(name=tenant_name)
            else:
                error = result.get("error", "Error desconocido al desactivar.")
                return "❌ " + error + "\n\n" + self.DEACTIVATE_CONFIRM_PROMPT.format(name=tenant_name)

        return self.EDIT_DETAIL_FALLBACK

    async def _handle_delete_confirm(
        self,
        phone: str,
        msg: str,
        session,
        session_service,
        tenant_service,
    ) -> str:
        """Handle CONFIRMAR during deletion flow."""
        stripped = msg.strip()

        if stripped.upper() != "CONFIRMAR":
            return self.CONFIRM_REPROMPT

        tenant_id = session.selected_tenant_id
        if not tenant_id:
            return self.EDIT_DETAIL_FALLBACK

        if tenant_service is not None and hasattr(tenant_service, "delete_tenant"):
            # Fetch tenant name for the success message
            tenant_name = tenant_id  # fallback
            if hasattr(tenant_service, "get_tenant"):
                tenant = await tenant_service.get_tenant(tenant_id)
                if tenant is not None:
                    tenant_name = tenant.full_name

            result = await tenant_service.delete_tenant(tenant_id)
            if result.get("success"):
                if session_service is not None:
                    await session_service.clear_session(phone)
                return self.DELETE_SUCCESS_MESSAGE.format(name=tenant_name)
            else:
                error = result.get("error", "Error desconocido al eliminar.")
                return "❌ " + error

        return self.EDIT_DETAIL_FALLBACK

    # ------------------------------------------------------------------
    # Edit tenant flow
    # ------------------------------------------------------------------

    async def _start_edit_flow(
        self,
        phone: str,
        session,
        session_service,
        tenant_service,
    ) -> str:
        """Start the edit tenant flow: store edit state and prompt for field selection."""
        session.flow = self.EDIT_FLOW
        session.step = self.EDIT_STEP_SELECT_FIELD
        session.temp_data = {}
        if session_service is not None:
            await session_service.save_session(session)

        return self._get_edit_field_selection_prompt()

    async def _handle_edit_step(
        self,
        phone: str,
        msg: str,
        session,
        session_service,
        tenant_service,
    ) -> str:
        """Dispatch to the correct edit flow step handler."""
        if session.step == self.EDIT_STEP_SELECT_FIELD:
            return await self._handle_edit_select_field(
                phone, msg, session, session_service, tenant_service
            )
        elif session.step == self.EDIT_STEP_NEW_VALUE:
            return await self._handle_edit_new_value(
                phone, msg, session, session_service, tenant_service
            )
        return self.FALLBACK_ACTIVE_FLOW

    @staticmethod
    def _get_edit_field_selection_prompt() -> str:
        """Build the edit field selection menu."""
        return (
            "✏️ *Editar Tenant*\n\n"
            "¿Qué campo deseas editar?\n\n"
            "1️⃣ Nombre completo\n"
            "2️⃣ Email\n"
            "3️⃣ Teléfono\n"
            "4️⃣ Instancia Evolution\n"
            "0️⃣ Volver al menú"
        )

    async def _handle_edit_select_field(
        self,
        phone: str,
        msg: str,
        session,
        session_service,
        tenant_service,
    ) -> str:
        """Handle field selection for editing."""
        if msg in self.EDIT_FIELD_MAP:
            field_name = self.EDIT_FIELD_MAP[msg]
            session.temp_data["edit_field"] = field_name
            session.step = self.EDIT_STEP_NEW_VALUE
            if session_service is not None:
                await session_service.save_session(session)
            return self.EDIT_FIELD_PROMPTS[field_name]

        return self.EDIT_ERROR_INVALID_FIELD

    async def _handle_edit_new_value(
        self,
        phone: str,
        msg: str,
        session,
        session_service,
        tenant_service,
    ) -> str:
        """Handle the new value for the field being edited.

        Validates, updates via tenant_service, and returns the updated
        Tenant detail screen on success.  On validation error, reprompts
        without losing the selected tenant context.
        """
        field = session.temp_data.get("edit_field")
        if not field:
            return self.EDIT_ERROR_UPDATE_FAILED

        new_value = msg.strip()

        # Validate required fields
        if field == "full_name" and not new_value:
            return (
                "❌ El nombre completo no puede estar vacío.\n\n"
                + self.EDIT_FIELD_PROMPTS["full_name"]
            )
        if field == "evolution_instance_name" and not new_value:
            return (
                "❌ El nombre de instancia Evolution no puede estar vacío.\n\n"
                + self.EDIT_FIELD_PROMPTS["evolution_instance_name"]
            )

        tenant_id = session.selected_tenant_id
        if not tenant_id:
            return self.EDIT_ERROR_UPDATE_FAILED

        # Build update payload
        payload = {field: new_value}

        # Attempt update if tenant_service supports update_tenant
        if tenant_service is not None and hasattr(tenant_service, "update_tenant"):
            result = await tenant_service.update_tenant(tenant_id, payload)
            if result.get("success"):
                updated_tenant = result.get("tenant")
                if updated_tenant is not None:
                    # Transition back to detail screen
                    session.flow = self.DETAIL_FLOW
                    session.step = self.ACTIONS_STEP
                    session.temp_data = {}
                    if session_service is not None:
                        await session_service.save_session(session)
                    return self._format_tenant_detail(updated_tenant)

            # Update failed — show error and reprompt
            error = result.get("error", "Error desconocido al actualizar.")
            return (
                "❌ " + error + "\n\n"
                + self.EDIT_FIELD_PROMPTS.get(field, self.EDIT_ERROR_UPDATE_FAILED)
            )

        # No tenant_service available
        return self.EDIT_ERROR_UPDATE_FAILED
