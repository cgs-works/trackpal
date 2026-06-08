"""Create tenant flow step handlers for the Master Console."""

from __future__ import annotations


from app.core.input_validation import (
    InputValidationError,
    validate_email,
    validate_full_name,
    validate_phone,
    validate_username,
)

from . import messages as msg
from . import formatters as fmt


async def _handle_create_full_name(
    self,
    phone: str,
    msg_text: str,
    session,
    session_service,
) -> str:
    """Validate full name, store normalized, transition to email."""
    try:
        normalized = validate_full_name(msg_text)
    except InputValidationError as exc:
        return fmt._validation_error_reply(exc, msg.CREATE_PROMPT_FULL_NAME)

    session.temp_data["full_name"] = normalized
    session.step = self.CREATE_STEP_EMAIL
    if session_service is not None:
        await session_service.save_session(session)

    return msg.CREATE_PROMPT_EMAIL


async def _handle_create_email(
    self,
    phone: str,
    msg_text: str,
    session,
    session_service,
) -> str:
    """Validate email, store normalized (or None if skipped), transition to phone."""
    stripped = msg_text.strip()
    if not stripped or stripped.lower() in self.SKIP_WORDS:
        session.temp_data["email"] = None
    else:
        try:
            normalized = validate_email(stripped, required=False)
        except InputValidationError as exc:
            return fmt._validation_error_reply(exc, msg.CREATE_PROMPT_EMAIL)
        session.temp_data["email"] = normalized

    session.step = self.CREATE_STEP_PHONE
    if session_service is not None:
        await session_service.save_session(session)

    return msg.CREATE_PROMPT_PHONE


async def _handle_create_phone(
    self,
    phone: str,
    msg_text: str,
    session,
    session_service,
) -> str:
    """Validate phone, store canonical digits-only (or None if skipped)."""
    stripped = msg_text.strip()
    if not stripped or stripped.lower() in self.SKIP_WORDS:
        session.temp_data["phone"] = None
    else:
        try:
            normalized = validate_phone(stripped, required=False)
        except InputValidationError as exc:
            return fmt._validation_error_reply(exc, msg.CREATE_PROMPT_PHONE)
        session.temp_data["phone"] = normalized

    session.step = self.CREATE_STEP_USERNAME
    if session_service is not None:
        await session_service.save_session(session)

    return msg.CREATE_PROMPT_USERNAME


async def _handle_create_username(
    self,
    phone: str,
    msg_text: str,
    session,
    session_service,
    tenant_service,
) -> str:
    """Validate username, check duplicates, transition to evolution instance."""
    try:
        normalized = validate_username(msg_text)
    except InputValidationError as exc:
        return fmt._validation_error_reply(exc, msg.CREATE_PROMPT_USERNAME)

    if tenant_service is not None and hasattr(tenant_service, "get_tenant_by_username"):
        existing = await tenant_service.get_tenant_by_username(normalized)
        if existing is not None:
            return (
                "❌ El nombre de usuario *" + normalized + "* ya está registrado.\n\n"
                "Por favor, elige otro nombre de usuario."
            )

    session.temp_data["username"] = normalized
    session.step = self.CREATE_STEP_EVOLUTION_INSTANCE
    if session_service is not None:
        await session_service.save_session(session)

    return msg.CREATE_PROMPT_EVOLUTION_INSTANCE


async def _handle_create_evolution_instance(
    self,
    phone: str,
    msg_text: str,
    session,
    session_service,
) -> str:
    """Store evolution instance name and transition to password mode prompt."""
    instance = msg_text.strip()
    if not instance:
        return msg.CREATE_ERROR_INSTANCE_EMPTY

    session.temp_data["evolution_instance_name"] = instance
    session.step = self.CREATE_STEP_PASSWORD_MODE
    if session_service is not None:
        await session_service.save_session(session)

    return msg.CREATE_PROMPT_PASSWORD_MODE


async def _handle_create_password_mode(
    self,
    phone: str,
    msg_text: str,
    session,
    session_service,
) -> str:
    """Handle password mode selection: auto or manual."""
    choice = msg_text.strip()

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
        return msg.CREATE_PROMPT_MANUAL_PASSWORD

    else:
        return msg.CREATE_PROMPT_INVALID_PASSWORD_MODE


async def _handle_create_manual_password(
    self,
    phone: str,
    msg_text: str,
    session,
    session_service,
) -> str:
    """Store manual password and transition to confirmation."""
    password = msg_text.strip()
    if not password:
        return (
            "❌ La contraseña no puede estar vacía.\n\n"
            + msg.CREATE_PROMPT_MANUAL_PASSWORD
        )
    if len(password) < 6:
        return msg.CREATE_ERROR_SHORT_PASSWORD

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
        "¿Todo está correcto? Escribe *CONFIRMAR* para crear la empresa.\n"
        "Escribe *0* para cancelar y volver al menú principal."
    )
