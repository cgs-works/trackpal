"""Formatting helpers for tenant display in the Master Console."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.core.input_validation import InputValidationError
from . import messages as msg


def _with_main_menu(message: str) -> str:
    """Append the global ``MAIN_MENU`` to *message*, separated by two newlines."""
    return message.rstrip() + "\n\n" + msg.MAIN_MENU


def _validation_error_reply(exc: InputValidationError, reprompt: str) -> str:
    """Format an ``InputValidationError`` into a Spanish reply + reprompt."""
    m = msg.VALIDATION_MESSAGES.get(exc.code, exc.message)
    return "❌ " + m + "\n\n" + reprompt


def _format_tenant_list(tenants: list[Any]) -> tuple[str, dict[str, str]]:
    """Format a list of tenants as a numbered WhatsApp message.

    Returns:
        Tuple of (formatted_message, selection_map).
        ``selection_map`` maps displayed numbers (``"1"``) to UUID strings.
    """
    entries: list[str] = []
    selection_map: dict[str, str] = {}
    active_count = 0
    inactive_count = 0

    for i, tenant in enumerate(tenants, start=1):
        num = str(i)
        status = "Activo" if tenant.is_active else "Inactivo"
        entries.append(f"{num}️⃣ {tenant.full_name} ({status})")
        selection_map[num] = str(tenant.id)
        if tenant.is_active:
            active_count += 1
        else:
            inactive_count += 1

    header = (
        "📋 *Lista de empresas*\n"
        f"Activas: {active_count} | Inactivas: {inactive_count}\n\n"
    )
    body = "\n".join(entries)
    footer = "\n\nResponde con el número de la empresa para ver sus detalles."

    return header + body + footer, selection_map


def _format_tenant_detail(tenant: Any) -> str:
    """Format a single tenant as a detailed WhatsApp message."""
    status_emoji = "✅ Activo" if tenant.is_active else "❌ Inactivo"
    actions = (
        msg.TENANT_DETAIL_ACTIVE_ACTIONS
        if tenant.is_active
        else msg.TENANT_DETAIL_INACTIVE_ACTIONS
    )

    created = ""
    if tenant.created_at:
        if isinstance(tenant.created_at, datetime):
            created = tenant.created_at.strftime("%Y-%m-%d")
        else:
            created = str(tenant.created_at)

    return (
        f"👤 *Detalle de la empresa*\n\n"
        f"*Nombre:* {tenant.full_name}\n"
        f"*Usuario:* {tenant.username}\n"
        f"*Email:* {tenant.email or '—'}\n"
        f"*Teléfono:* {tenant.phone or '—'}\n"
        f"*Instancia Evolution:* {tenant.evolution_instance_name or '—'}\n"
        f"*Estado:* {status_emoji}\n"
        f"*Creado:* {created}\n\n"
        f"{actions}"
    )
