"""Relayable reply texts for degraded Redis states.

Defines the two deterministic replies the WhatsApp Master Console
returns when Redis failover cannot recover the active session or
when both Redis stores are unavailable.
"""


class ContingencyReplyPolicy:
    """Reply texts for degraded Redis scenarios.

    All replies are plain text compatible with the existing
    ``WhatsAppConsoleResponse.reply`` schema so n8n can relay them
    without workflow changes.
    """

    SESSION_RESET = (
        "🔄 *Sesión reiniciada por contingencia*\n\n"
        "El sistema experimentó una contingencia temporal y tu sesión "
        "anterior no pudo ser recuperada.\n\n"
        "Por favor, selecciona una opción del menú para continuar:\n\n"
        "1️⃣ Ver empresas\n"
        "2️⃣ Crear empresa\n"
        "3️⃣ Desactivar empresa\n"
        "4️⃣ Eliminar empresa\n"
        "5️⃣ Ayuda\n\n"
        "0️⃣ Cancelar / Menú"
    )

    TEMPORARY_UNAVAILABLE = (
        "⚠️ Consola temporalmente no disponible. "
        "Intenta nuevamente en unos minutos."
    )
