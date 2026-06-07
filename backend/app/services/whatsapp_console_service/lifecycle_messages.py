"""Lifecycle (deactivate/delete) prompts for the Master Console."""

DEACTIVATE_CONFIRM_PROMPT = (
    "⚠️ *Desactivar empresa*\n\n"
    "¿Estás seguro de que deseas desactivar a *{name}*?\n\n"
    "Esta empresa:\n"
    "• Estado actual: ✅ Activo\n"
    "• No podrá iniciar sesión ni ser identificado después "
    "de la desactivación.\n\n"
    "Escribe *CONFIRMAR* para desactivar la empresa.\n"
    "Escribe *0* para cancelar."
)

DELETE_CONFIRM_PROMPT = (
    "⚠️ *Eliminar empresa*\n\n"
    "¿Estás seguro de que deseas eliminar permanentemente "
    "a *{name}*?\n\n"
    "Esta empresa:\n"
    "• Estado actual: ❌ Inactivo\n"
    "• Esta acción no se puede deshacer.\n\n"
    "Escribe *CONFIRMAR* para eliminar la empresa "
    "permanentemente.\n"
    "Escribe *0* para cancelar."
)

CANT_DELETE_ACTIVE_MESSAGE = (
    "❌ No se puede eliminar una empresa activa.\n\n"
    "Desactiva la empresa primero usando la opción "
    "*Desactivar* y luego intenta eliminarla."
)

ALREADY_INACTIVE_MESSAGE = (
    "ℹ️ La empresa *{name}* ya está inactiva.\n\n"
    "Puedes reactivarla desde la pantalla de detalle."
)

REACTIVATE_SUCCESS_MESSAGE = (
    "✅ *Empresa reactivada*\n\nLa empresa *{name}* ha sido reactivada exitosamente."
)

DEACTIVATE_SUCCESS_MESSAGE = (
    "✅ *Empresa desactivada*\n\nLa empresa *{name}* ha sido desactivada exitosamente."
)

DELETE_SUCCESS_MESSAGE = (
    "✅ *Empresa eliminada*\n\nLa empresa *{name}* ha sido eliminada permanentemente."
)

EDIT_SUCCESS_MESSAGE = (
    "✅ *Empresa actualizada exitosamente*\n\n"
    "La empresa *{name}* ha sido actualizada correctamente."
)

CONFIRM_REPROMPT = (
    "❌ Para confirmar, escribe *CONFIRMAR* (en mayúsculas o minúsculas)."
)
