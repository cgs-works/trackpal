"""Edit tenant flow handlers for the Master Console."""

from __future__ import annotations

from app.core.input_validation import (
    InputValidationError,
    validate_email,
    validate_full_name,
    validate_phone,
)
from . import messages as msg
from . import lifecycle_messages as lc_msg
from . import edit_messages as edit_msg
from . import formatters as fmt


async def _start_edit_flow(
    self,
    phone: str,
    session,
    session_service,
    tenant_service,
) -> str:
    """Start the edit tenant flow."""
    session.flow = self.EDIT_FLOW
    session.step = self.EDIT_STEP_SELECT_FIELD
    session.temp_data = {}
    if session_service is not None:
        await session_service.save_session(session)

    return _get_edit_field_selection_prompt()


async def _handle_edit_step(
    self,
    phone: str,
    msg_text: str,
    session,
    session_service,
    tenant_service,
) -> str:
    """Dispatch to the correct edit flow step handler."""
    if session.step == self.EDIT_STEP_SELECT_FIELD:
        return await self._handle_edit_select_field(
            phone, msg_text, session, session_service, tenant_service
        )
    elif session.step == self.EDIT_STEP_NEW_VALUE:
        return await self._handle_edit_new_value(
            phone, msg_text, session, session_service, tenant_service
        )
    return self.FALLBACK_ACTIVE_FLOW


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
    msg_text: str,
    session,
    session_service,
    tenant_service,
) -> str:
    """Handle field selection for editing."""
    if msg_text in self.EDIT_FIELD_MAP:
        field_name = self.EDIT_FIELD_MAP[msg_text]
        session.temp_data["edit_field"] = field_name
        session.step = self.EDIT_STEP_NEW_VALUE
        if session_service is not None:
            await session_service.save_session(session)
        return self.EDIT_FIELD_PROMPTS[field_name]

    return self.EDIT_ERROR_INVALID_FIELD


async def _handle_edit_new_value(
    self,
    phone: str,
    msg_text: str,
    session,
    session_service,
    tenant_service,
) -> str:
    """Handle the new value for the field being edited."""
    field = session.temp_data.get("edit_field")
    if not field:
        return self.EDIT_ERROR_UPDATE_FAILED

    new_value = msg_text.strip()

    if field == "full_name":
        try:
            new_value = validate_full_name(msg_text)
        except InputValidationError as exc:
            return fmt._validation_error_reply(
                exc, self.EDIT_FIELD_PROMPTS["full_name"]
            )
    elif field == "email":
        if not new_value:
            new_value = None
        else:
            try:
                new_value = validate_email(new_value, required=False)
            except InputValidationError as exc:
                return fmt._validation_error_reply(
                    exc, self.EDIT_FIELD_PROMPTS["email"]
                )
    elif field == "phone":
        if not new_value:
            new_value = None
        else:
            try:
                new_value = validate_phone(new_value, required=False)
            except InputValidationError as exc:
                return fmt._validation_error_reply(
                    exc, self.EDIT_FIELD_PROMPTS["phone"]
                )
    elif field == "evolution_instance_name" and not new_value:
        return (
            "❌ El nombre de instancia Evolution no puede estar vacío.\n\n"
            + self.EDIT_FIELD_PROMPTS["evolution_instance_name"]
        )

    tenant_id = session.selected_tenant_id
    if not tenant_id:
        return self.EDIT_ERROR_UPDATE_FAILED

    payload = {field: new_value}

    if tenant_service is not None and hasattr(tenant_service, "update_tenant"):
        result = await tenant_service.update_tenant(tenant_id, payload)
        if result.get("success"):
            if session_service is not None:
                await session_service.clear_session(phone)

            updated_tenant = result.get("tenant")
            tenant_name = (
                getattr(updated_tenant, "full_name", None)
                or (isinstance(updated_tenant, dict) and updated_tenant.get("full_name"))
                or tenant_id
            )
            return self._with_main_menu(
                lc_msg.EDIT_SUCCESS_MESSAGE.format(name=tenant_name)
            )

        error = result.get("error", "Error desconocido al actualizar.")
        return (
            "❌ " + error + "\n\n"
            + self.EDIT_FIELD_PROMPTS.get(field, self.EDIT_ERROR_UPDATE_FAILED)
        )

    return self.EDIT_ERROR_UPDATE_FAILED
