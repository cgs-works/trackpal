"""Lifecycle (deactivate/delete) prompts for the Master Console."""

DEACTIVATE_CONFIRM_PROMPT = (
    "⚠️ *Desactivar Tenant*\n\n"
    "¿Estás seguro de que deseas desactivar a *{name}*?\n\n"
    "Este tenant:\n"
    "• Estado actual: ✅ Activo\n"
    "• No podrá iniciar sesión ni ser identificado después "
    "de la desactivación.\n\n"
    "Escribe *CONFIRMAR* para desactivar el tenant.\n"
    "Escribe *9* para cancelar."
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
    "Escribe *9* para cancelar."
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
    "✅ *Tenant Reactivado*\n\nEl tenant *{name}* ha sido reactivado exitosamente."
)

DEACTIVATE_SUCCESS_MESSAGE = (
    "✅ *Tenant Desactivado*\n\nEl tenant *{name}* ha sido desactivado exitosamente."
)

DELETE_SUCCESS_MESSAGE = (
    "✅ *Tenant Eliminado*\n\nEl tenant *{name}* ha sido eliminado permanentemente."
)

EDIT_SUCCESS_MESSAGE = (
    "✅ *Tenant actualizado exitosamente*\n\n"
    "El tenant *{name}* ha sido actualizado correctamente."
)

CONFIRM_REPROMPT = (
    "❌ Para confirmar, escribe *CONFIRMAR* (en mayúsculas o minúsculas)."
)
