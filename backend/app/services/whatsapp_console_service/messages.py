"""Reply templates, flow identifiers, and prompt strings for the Master Console."""

# ------------------------------------------------------------------
# Main menu & fallback
# ------------------------------------------------------------------

MAIN_MENU = (
    "🤖 *Trackpal Master Console*\n\n"
    "1️⃣ Ver Tenants\n"
    "2️⃣ Crear Tenant\n"
    "3️⃣ Desactivar Tenant\n"
    "4️⃣ Eliminar Tenant\n"
    "5️⃣ Ayuda\n\n"
    "0️⃣ Cerrar sesión\n\n"
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
    "0️⃣ *Cerrar sesión* — Cierra tu sesión en la consola Master.\n\n"
    "En el menú principal, escribe *0* para cerrar sesión.\n"
    "Dentro de un flujo, *9* o *cancelar* cancelan la operación.\n"
    "Escribe */menu* para volver al menú principal."
)

FALLBACK_NO_FLOW = (
    "❌ No entendí tu mensaje.\n\n"
    "Responde con:\n"
    "• Un número del *1* al *5* para elegir una opción del menú\n"
    "• *menu* o */menu* para volver al menú principal\n"
    "• *0* para cerrar sesión\n"
    "• *9* para volver atrás\n"
    "• *ayuda* para ver los comandos disponibles"
)

FALLBACK_ACTIVE_FLOW = (
    "❌ No entendí tu mensaje.\n\n"
    "Estás en medio de un flujo. Responde con la información "
    "solicitada o escribe *0* para cancelar y volver al menú "
    "principal."
)

# ------------------------------------------------------------------
# Flow identifiers
# ------------------------------------------------------------------

RESET_COMMANDS = {"0", "9", "menu", "menú", "/menu", "cancelar"}
HELP_COMMANDS = {"5", "ayuda"}

LIST_FLOW = "list_tenants"
SELECT_STEP = "select"
DETAIL_FLOW = "tenant_detail"
ACTIONS_STEP = "actions"
CREATE_FLOW = "create_tenant"
DEACTIVATE_FLOW = "deactivate_tenant"
DELETE_FLOW = "delete_tenant"
CONFIRM_DEACTIVATE_STEP = "confirm_deactivate"
CONFIRM_DELETE_STEP = "confirm_delete"

CREATE_STEP_FULL_NAME = "full_name"
CREATE_STEP_EMAIL = "email"
CREATE_STEP_PHONE = "phone"
CREATE_STEP_USERNAME = "username"
CREATE_STEP_EVOLUTION_INSTANCE = "evolution_instance"
CREATE_STEP_PASSWORD_MODE = "password_mode"
CREATE_STEP_MANUAL_PASSWORD = "manual_password"
CREATE_STEP_CONFIRM = "confirm"

# ------------------------------------------------------------------
# Detail action prompts
# ------------------------------------------------------------------

TENANT_DETAIL_ACTIVE_ACTIONS = (
    "*Acciones disponibles:*\n"
    "1️⃣ Editar\n"
    "2️⃣ Desactivar\n"
    "3️⃣ Eliminar (solo inactivos)\n"
    "9️⃣ Volver al menú"
)

TENANT_DETAIL_INACTIVE_ACTIONS = (
    "*Acciones disponibles:*\n"
    "1️⃣ Editar\n"
    "2️⃣ Reactivar\n"
    "3️⃣ Eliminar\n"
    "9️⃣ Volver al menú"
)

INVALID_SELECTION = (
    "❌ Número inválido. Responde con un número de la lista "
    "o escribe *9* para volver al menú principal."
)

NO_TENANTS = "📭 No hay tenants registrados."

# ------------------------------------------------------------------
# Create flow prompts
# ------------------------------------------------------------------

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

# ------------------------------------------------------------------
# Validation error templates
# ------------------------------------------------------------------

VALIDATION_MESSAGES = {
    "full_name_required": "El nombre completo no puede estar vacío.",
    "full_name_leading_trailing_spaces": (
        "El nombre completo no debe comenzar o terminar con espacios."
    ),
    "full_name_invalid_chars": (
        "El nombre completo solo puede contener letras, números y espacios."
    ),
    "email_invalid": "El email ingresado no es válido.",
    "email_required": "El email no puede estar vacío.",
    "phone_required": "El teléfono no puede estar vacío.",
    "phone_no_digits": "El teléfono debe contener al menos un dígito.",
    "phone_invalid": (
        "El teléfono ingresado no es un número internacional válido."
    ),
    "phone_parse_error": "El teléfono ingresado no pudo ser procesado.",
    "username_required": "El nombre de usuario no puede estar vacío.",
    "username_too_long": (
        "El nombre de usuario debe tener máximo 20 caracteres."
    ),
    "username_invalid": (
        "El nombre de usuario debe empezar con una letra minúscula y "
        "contener solo letras minúsculas, números y guiones bajos."
    ),
}

SKIP_WORDS = {"—", "skip", "ninguno", "none", "-"}




