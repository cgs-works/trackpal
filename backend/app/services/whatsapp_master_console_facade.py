"""Orchestrator for the WhatsApp Master Console.

Handles login flow, lockout, auth session verification, and delegates
to ``WhatsAppConsoleService`` for authenticated operations.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import users as user_crud
from app.services.auth_service import AuthService
from app.services.whatsapp_auth_session_service import (
    WhatsAppAuthSession,
    WhatsAppAuthSessionService,
)
from app.services.whatsapp_console_service import WhatsAppConsoleService
from app.services.whatsapp_session_service import WhatsAppSessionService


# ====================================================================
# Reply templates (Spanish)
# ====================================================================

USERNAME_PROMPT = (
    "🔐 *Trackpal Master Console - Acceso*\n\n"
    "Para usar la consola, primero debes iniciar sesión.\n\n"
    "¿Cuál es tu *nombre de usuario*?"
)

PASSWORD_PROMPT_TEMPLATE = (
    "🔐 *Iniciar Sesión*\n\n"
    "Introduce tu *contraseña* para *{username}*.\n\n"
    "⚠️  Ten en cuenta que estás enviando una contraseña "
    "a través de WhatsApp. Asegúrate de estar en un "
    "entorno seguro."
)

UNKNOWN_USERNAME_TEMPLATE = (
    "❌ El usuario *{username}* no existe.\n\n"
    "Intenta de nuevo o escribe *0* para cancelar."
)

WRONG_PASSWORD_TEMPLATE = (
    "❌ Contraseña incorrecta para *{username}*.\n\n"
    "Intenta de nuevo o escribe *0* para cancelar."
)

ROLE_NOT_ALLOWED = (
    "❌ Acceso denegado. Solo los usuarios con rol "
    "Master pueden usar esta consola."
)

LOCKOUT_TEMPLATE = (
    "🔒 *Demasiados intentos fallidos*\n\n"
    "Has superado el número máximo de intentos permitidos.\n\n"
    "Espera *{minutes}* minutos antes de intentar de nuevo."
)

LOGIN_HELP = (
    "🔐 *Ayuda - Inicio de Sesión*\n\n"
    "Para acceder a la consola Master, debes iniciar sesión "
    "con tu nombre de usuario y contraseña.\n\n"
    "Comandos disponibles:\n"
    "• *0* o *menu* o *cancelar* — Volver al inicio de sesión\n"
    "• *ayuda* o *5* — Mostrar esta ayuda"
)

# ====================================================================
# Flow constants
# ====================================================================

AUTH_FLOW = "auth"
AUTH_STEP_USERNAME = "username"
AUTH_STEP_PASSWORD = "password"

RESET_COMMANDS = {"0", "menu", "menú", "cancelar"}
HELP_COMMANDS = {"5", "ayuda"}


# ====================================================================
# Facade
# ====================================================================


class WhatsAppMasterConsoleFacade:
    """Orchestrate auth-gated WhatsApp Master Console access.

    1. Checks lockout state → returns lockout reply when locked.
    2. Checks auth session → delegates to ``WhatsAppConsoleService``
       when an active master session exists.
    3. Otherwise runs the conversational login flow using the
       existing ``WhatsAppSessionService`` for multi-step state.
    """

    def __init__(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        auth_session_service: WhatsAppAuthSessionService,
        tenant_service: Any,
    ) -> None:
        self._console_service = console_service
        self._session_service = session_service
        self._auth_session_service = auth_session_service
        self._tenant_service = tenant_service
        self._auth_service = AuthService()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def process_message(
        self,
        phone: str,
        message: str,
        db: AsyncSession | None = None,
    ) -> str:
        """Process a WhatsApp message through the auth-gated console.

        Args:
            phone: Normalised phone number of the sender.
            message: Text of the WhatsApp message.
            db: Database session (required for credential verification).

        Returns:
            Reply text that n8n will send through Evolution API.
        """
        # 1. Check lockout
        lock_state = await self._auth_session_service.get_lock_state(phone)
        if lock_state is not None and lock_state.is_locked:
            remaining = self._compute_remaining_minutes(lock_state)
            return LOCKOUT_TEMPLATE.format(minutes=remaining)

        # 2. Check auth session — refresh TTL on every authenticated message
        #    (sliding window: 15 min from last activity, not from login).
        auth_session = await self._auth_session_service.get_auth_session(phone)
        if auth_session is not None and auth_session.role == "master":
            await self._auth_session_service.touch_auth_session(phone)
            return await self._console_service.process_message(
                phone=phone,
                message=message,
                is_master=True,
                session_service=self._session_service,
                tenant_service=self._tenant_service,
            )

        # 3. No auth session → run login flow
        return await self._run_login_flow(phone, message, db)

    # ------------------------------------------------------------------
    # Login flow
    # ------------------------------------------------------------------

    async def _run_login_flow(
        self,
        phone: str,
        message: str,
        db: AsyncSession | None,
    ) -> str:
        """Conversational username/password login flow."""
        msg = message.strip()
        msg_lower = msg.lower()

        # Global commands always work
        if msg_lower in RESET_COMMANDS:
            await self._session_service.clear_session(phone)
            return USERNAME_PROMPT

        if msg_lower in HELP_COMMANDS:
            return LOGIN_HELP

        # Get or create conversation session
        session = await self._session_service.get_session(phone)

        if session is None or session.flow != AUTH_FLOW:
            # First message in auth flow — start with username prompt
            session = await self._session_service.create_session(phone)
            session.flow = AUTH_FLOW
            session.step = AUTH_STEP_USERNAME
            session.temp_data = {}
            await self._session_service.save_session(session)
            return USERNAME_PROMPT

        if session.flow == AUTH_FLOW and session.step == AUTH_STEP_USERNAME:
            return await self._handle_username_step(phone, msg, session, db)

        if session.flow == AUTH_FLOW and session.step == AUTH_STEP_PASSWORD:
            return await self._handle_password_step(phone, msg, session, db)

        # Fallback — shouldn't happen, but handle gracefully
        await self._session_service.clear_session(phone)
        return USERNAME_PROMPT

    async def _handle_username_step(
        self,
        phone: str,
        msg: str,
        session: Any,
        db: AsyncSession | None,
    ) -> str:
        """Store lowercase username, transition to password prompt.

        Validates username existence before advancing. If username is
        unknown, stays on username step with clear error message.
        """
        msg_stripped = msg.strip()

        if not msg_stripped:
            return USERNAME_PROMPT

        msg_lower = msg_stripped.lower()

        # Check for reset/help again (already handled in _run_login_flow,
        # but just in case)
        if msg_lower in RESET_COMMANDS:
            await self._session_service.clear_session(phone)
            return USERNAME_PROMPT

        if msg_lower in HELP_COMMANDS:
            return LOGIN_HELP

        # Validate username existence early — keep user on username step
        # if the username doesn't exist, so they can correct it immediately
        # instead of getting trapped in the password step.
        if db is not None:
            existing_user = await user_crud.get_by_username(db, msg_lower)
            if existing_user is None:
                _, lock_state = await self._auth_session_service.record_failed_attempt(phone)
                if lock_state is not None:
                    remaining = self._compute_remaining_minutes(lock_state)
                    await self._session_service.clear_session(phone)
                    return LOCKOUT_TEMPLATE.format(minutes=remaining)
                return UNKNOWN_USERNAME_TEMPLATE.format(username=msg_lower)

        session.temp_data["username"] = msg_lower
        session.step = AUTH_STEP_PASSWORD
        await self._session_service.save_session(session)

        return PASSWORD_PROMPT_TEMPLATE.format(username=msg_lower)

    async def _handle_password_step(
        self,
        phone: str,
        msg: str,
        session: Any,
        db: AsyncSession | None,
    ) -> str:
        """Verify credentials and create auth session on success."""
        msg_stripped = msg.strip()
        username = session.temp_data.get("username", "")

        if not msg_stripped:
            return PASSWORD_PROMPT_TEMPLATE.format(username=username)

        # Check for reset/help again
        if msg_stripped.lower() in RESET_COMMANDS:
            await self._session_service.clear_session(phone)
            return USERNAME_PROMPT

        if msg_stripped.lower() in HELP_COMMANDS:
            return LOGIN_HELP

        # Verify credentials
        if db is None:
            # No DB available — cannot verify; return unavailable
            from app.services.contingency_reply_policy import ContingencyReplyPolicy
            return ContingencyReplyPolicy.TEMPORARY_UNAVAILABLE

        user = await self._auth_service.authenticate(db, username, msg_stripped)

        if user is None:
            # Authentication failed — unknown username or wrong password
            # First check if username exists at all
            existing_user = await user_crud.get_by_username(db, username)

            if existing_user is None:
                # Unknown username — record failure
                _, lock_state = await self._auth_session_service.record_failed_attempt(phone)
                if lock_state is not None:
                    remaining = self._compute_remaining_minutes(lock_state)
                    await self._session_service.clear_session(phone)
                    return LOCKOUT_TEMPLATE.format(minutes=remaining)
                return UNKNOWN_USERNAME_TEMPLATE.format(username=username)

            # Wrong password — record failure
            _, lock_state = await self._auth_session_service.record_failed_attempt(phone)
            if lock_state is not None:
                remaining = self._compute_remaining_minutes(lock_state)
                # Clear conversation session
                await self._session_service.clear_session(phone)
                return LOCKOUT_TEMPLATE.format(minutes=remaining)

            return WRONG_PASSWORD_TEMPLATE.format(username=username)

        if user.role != "master":
            # Role not allowed — record failure
            _, lock_state = await self._auth_session_service.record_failed_attempt(phone)
            await self._session_service.clear_session(phone)
            if lock_state is not None:
                remaining = self._compute_remaining_minutes(lock_state)
                return LOCKOUT_TEMPLATE.format(minutes=remaining)
            return ROLE_NOT_ALLOWED

        # Success — create auth session, clear conversation session,
        # and reset fail counter to prevent accidental lockout
        auth_session = WhatsAppAuthSession(
            phone=phone,
            user_id=user.id,
            username=user.username,
            role=user.role,
            authenticated_at=datetime.now(timezone.utc),
        )
        await self._auth_session_service.set_auth_session(auth_session)
        await self._session_service.clear_session(phone)
        await self._auth_session_service.clear_fail_counter(phone)

        return self._console_service.MAIN_MENU

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_remaining_minutes(lock_state: Any) -> int:
        """Compute remaining lockout minutes (minimum 1)."""
        if lock_state is None or lock_state.locked_until is None:
            return 1
        remaining = (lock_state.locked_until - datetime.now(timezone.utc)).total_seconds()
        return max(1, int(remaining // 60) + 1)
