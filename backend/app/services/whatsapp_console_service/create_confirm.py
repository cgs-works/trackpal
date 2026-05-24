"""Create tenant confirmation handler for the Master Console."""

from __future__ import annotations

from . import messages as msg
from . import formatters as fmt


async def _handle_create_confirm(
    self,
    phone: str,
    msg_text: str,
    session,
    session_service,
    tenant_service,
) -> str:
    """Handle confirmation: create the tenant or show errors."""
    stripped = msg_text.strip()

    if stripped.upper() != "CONFIRMAR":
        return (
            "❌ Para confirmar, escribe *CONFIRMAR* (en mayúsculas o minúsculas).\n\n"
            + await self._build_create_summary(session)
        )

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

    if tenant_service is not None and hasattr(tenant_service, "create_tenant"):
        result = await tenant_service.create_tenant(payload)
        if result.get("success"):
            tenant = result.get("tenant")
            auto_password = result.get("auto_password")

            if session_service is not None:
                await session_service.clear_session(phone)

            reply = (
                "✅ *Tenant creado exitosamente*\n\n"
                f"*Nombre:* {tenant.full_name}\n"
                f"*Usuario:* {tenant.username}\n"
                f"*Email:* {tenant.email or '—'}\n"
                f"*Teléfono:* {tenant.phone or '—'}\n"
            )
            if auto_password:
                reply += (
                    f"\n🔑 *Contraseña generada:*\n`{auto_password}`\n\n"
                    "⚠️  Guarda esta contraseña en un lugar seguro. "
                    "No podrás volver a verla."
                )
            else:
                reply += "\n🔑 Contraseña configurada manualmente.\n"

            return self._with_main_menu(reply)
        else:
            error = result.get("error", "Error desconocido al crear el tenant.")
            error_lower = error.lower()
            if "phone" in error_lower or "teléfono" in error_lower:
                session.step = self.CREATE_STEP_PHONE
                if session_service is not None:
                    await session_service.save_session(session)
                return "❌ " + error + "\n\n" + msg.CREATE_PROMPT_PHONE
            if "username" in error_lower or "usuario" in error_lower:
                session.step = self.CREATE_STEP_USERNAME
                if session_service is not None:
                    await session_service.save_session(session)
                return "❌ " + error + "\n\n" + msg.CREATE_PROMPT_USERNAME
            return (
                "❌ " + error + "\n\n"
                + await self._build_create_summary(session)
            )

    return "❌ No se pudo crear el tenant. Servicio no disponible."
