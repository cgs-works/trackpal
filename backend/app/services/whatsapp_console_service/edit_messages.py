"""Edit-flow specific prompts and constants for the Master Console."""

EDIT_FLOW = "edit_tenant"
EDIT_STEP_SELECT_FIELD = "select_field"
EDIT_STEP_NEW_VALUE = "new_value"

EDIT_PROMPT_SELECT_FIELD = (
    "✏️ *Editar empresa*",
    "",
    "¿Qué campo deseas editar?",
    "",
    "1️⃣ Nombre completo",
    "2️⃣ Email",
    "3️⃣ Teléfono",
    "4️⃣ Instancia Evolution",
    "9️⃣ Volver al menú",
)

EDIT_FIELD_MAP = {
    "1": "full_name",
    "2": "email",
    "3": "phone",
    "4": "evolution_instance_name",
}

EDIT_FIELD_PROMPTS = {
    "full_name": ("✏️ *Editar empresa*\n\n¿Cuál es el *nuevo nombre completo*?"),
    "email": ("✏️ *Editar empresa*\n\n¿Cuál es el *nuevo email*?"),
    "phone": ("✏️ *Editar empresa*\n\n¿Cuál es el *nuevo teléfono*?"),
    "evolution_instance_name": (
        "✏️ *Editar empresa*\n\n¿Cuál es el *nuevo nombre de instancia Evolution*?"
    ),
}

EDIT_ERROR_INVALID_FIELD = (
    "❌ Opción inválida. Responde con un número del *1* al *4* "
    "para elegir el campo a editar, o *9* para volver al menú."
)

EDIT_ERROR_UPDATE_FAILED = (
    "❌ No se pudo actualizar el campo. Intenta de nuevo o escribe *0* para cancelar."
)

EDIT_DETAIL_FALLBACK = (
    "❌ Opción inválida. Responde con un número de las "
    "acciones disponibles o *9* para volver al menú."
)
