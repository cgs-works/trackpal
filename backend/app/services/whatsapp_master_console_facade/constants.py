"""Reply templates and flow constants for the Master Console auth facade."""

from __future__ import annotations

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

LOGOUT_CONFIRMATION = (
    "🔒 *Sesión cerrada*\n\n"
    "Has cerrado sesión en la consola Master.\n\n"
    "Escribe */menu* para iniciar sesión de nuevo."
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
    "• *0* o *menu* o */menu* o *cancelar* — Volver al inicio de sesión\n"
    "• *ayuda* o *5* — Mostrar esta ayuda"
)

# Flow constants
AUTH_FLOW = "auth"
AUTH_STEP_USERNAME = "username"
AUTH_STEP_PASSWORD = "password"

RESET_COMMANDS = {"0", "menu", "menú", "/menu", "cancelar"}
HELP_COMMANDS = {"5", "ayuda"}
