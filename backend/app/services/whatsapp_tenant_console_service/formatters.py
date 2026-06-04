"""Formatting helpers for tenant-scoped WhatsApp displays."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from app.core.i18n import t as _i18n_t

from . import _context as ctx


def _t(key: str, /, **params: Any) -> str:
    """Translate *key* in the current message locale."""
    return _i18n_t(ctx.get_locale(), key, **params)


def _with_main_menu(message: str, locale: str | None = None) -> str:
    """Append the main menu to *message*, translated to *locale*."""
    from . import constants as c

    loc = locale if locale is not None else ctx.get_locale()
    return message.rstrip() + "\n\n" + _i18n_t(loc, c.KEY_MAIN_MENU)


def _post_action_prompt() -> str:
    """Return the standardized post-action decision prompt."""
    return _i18n_t(ctx.get_locale(), "wa.tenant.post_action_prompt")


def _catalog_count(key_base: str, count: int) -> str:
    """Return pluralized catalog count string (one/other)."""
    suffix = "one" if count == 1 else "other"
    return _i18n_t(ctx.get_locale(), f"{key_base}.{suffix}", count=count)


def _format_client_list(clients: list[Any]) -> tuple[str, dict[str, str]]:
    entries: list[str] = []
    selection_map: dict[str, str] = {}
    active_count = 0
    loc = ctx.get_locale()
    for i, c in enumerate(clients, start=1):
        num = str(i)
        status = (
            _i18n_t(loc, "wa.tenant.status.active")
            if c.is_active
            else _i18n_t(loc, "wa.tenant.status.inactive")
        )
        entries.append(f"{num}️⃣ {c.full_name} ({status})")
        selection_map[num] = str(c.id)
        if c.is_active:
            active_count += 1
    inactive_count = len(clients) - active_count
    header = _i18n_t(
        loc,
        "wa.tenant.clients.list.header",
        active_count=active_count,
        inactive_count=inactive_count,
    )
    return header + "\n".join(entries), selection_map


def _format_client_detail(client: Any) -> str:
    loc = ctx.get_locale()
    from . import constants as c

    status_emoji = (
        _i18n_t(loc, "wa.tenant.clients.detail.status_active")
        if client.is_active
        else _i18n_t(loc, "wa.tenant.clients.detail.status_inactive")
    )
    actions = (
        _i18n_t(loc, c.KEY_CLIENT_DETAIL_ACTIVE_ACTIONS)
        if client.is_active
        else _i18n_t(loc, c.KEY_CLIENT_DETAIL_INACTIVE_ACTIONS)
    )
    phone = client.phone or "—"
    username = getattr(client, "username", None) or getattr(
        client.user, "username", "—"
    )
    created = ""
    if client.created_at:
        if isinstance(client.created_at, datetime):
            created = client.created_at.strftime("%Y-%m-%d")
        else:
            created = str(client.created_at)
    return (
        f"{_i18n_t(loc, 'wa.tenant.clients.detail.header')}\n\n"
        f"*Nombre:* {client.full_name}\n"
        f"*Usuario:* {username}\n"
        f"*Teléfono:* {phone}\n"
        f"*Estado:* {status_emoji}\n"
        f"*Creado:* {created}\n\n"
        f"{actions}"
    )


def _format_service_list(
    services: list[Any],
    page: int = 1,
    total_pages: int = 1,
) -> tuple[str, dict[str, str]]:
    """Format service list with plan/subscription counts and pagination nav."""
    loc = ctx.get_locale()
    entries: list[str] = []
    selection_map: dict[str, str] = {}
    for i, s in enumerate(services, start=1):
        num = str(i)
        plan_count = int(getattr(s, "plan_count", 0) or 0)
        active_count = int(getattr(s, "active_subscription_count", 0) or 0)
        entries.append(
            f"{num}️⃣ {s.name} - "
            f"{_catalog_count('wa.tenant.catalog.count.plan', plan_count)} - "
            f"{_catalog_count('wa.tenant.catalog.count.subscription_active', active_count)}"
        )
        selection_map[num] = str(s.id)
    reply = (
        _i18n_t(loc, "wa.tenant.catalog.service_list_header")
        + "\n\n"
        + "\n".join(entries)
    )
    if total_pages > 1:
        reply += "\n\n" + _i18n_t(
            loc, "wa.tenant.subscriptions.list.page_info", page=page, total=total_pages
        )
    nav: list[str] = []
    if page < total_pages:
        nav.append(_i18n_t(loc, "wa.nav.next"))
    nav.append(_i18n_t(loc, "wa.nav.back"))
    nav.append(_i18n_t(loc, "wa.nav.cancel"))
    reply += "\n" + " | ".join(nav)
    return reply, selection_map


def _format_service_detail(service: Any) -> str:
    loc = ctx.get_locale()
    header = _i18n_t(loc, "wa.tenant.catalog.service_detail_header")
    name_label = _i18n_t(loc, "wa.tenant.catalog.name_label", name=service.name)
    return f"{header}\n\n{name_label}\n"


def _format_plan_list(
    plans: list[Any],
    page: int = 1,
    total_pages: int = 1,
) -> tuple[str, dict[str, str]]:
    """Format plan list with subscription counts and pagination nav."""
    loc = ctx.get_locale()
    entries: list[str] = []
    selection_map: dict[str, str] = {}
    for i, p in enumerate(plans, start=1):
        num = str(i)
        active_count = int(getattr(p, "active_subscription_count", 0) or 0)
        entries.append(
            f"{num}️⃣ {p.name} - "
            f"{_catalog_count('wa.tenant.catalog.count.subscription_active', active_count)}"
        )
        selection_map[num] = str(p.id)
    reply = (
        _i18n_t(loc, "wa.tenant.catalog.plan_list_header") + "\n\n" + "\n".join(entries)
    )
    if total_pages > 1:
        reply += "\n\n" + _i18n_t(
            loc, "wa.tenant.subscriptions.list.page_info", page=page, total=total_pages
        )
    nav: list[str] = []
    if page < total_pages:
        nav.append(_i18n_t(loc, "wa.nav.next"))
    nav.append(_i18n_t(loc, "wa.nav.back"))
    nav.append(_i18n_t(loc, "wa.nav.cancel"))
    reply += "\n" + " | ".join(nav)
    return reply, selection_map


def _format_plan_detail(plan: Any) -> str:
    loc = ctx.get_locale()
    header = _i18n_t(loc, "wa.tenant.catalog.plan_detail_header")
    name_label = _i18n_t(loc, "wa.tenant.catalog.name_label", name=plan.name)
    return f"{header}\n\n{name_label}\n"


def _format_profile_detail(profile: Any, username: str) -> str:
    return (
        f"👤 *Mi Perfil*\n\n"
        f"*Usuario:* {username}\n"
        f"*Nombre:* {profile.full_name or profile.name or '—'}\n"
        f"*Email:* {profile.email or '—'}\n"
        f"*Teléfono:* {profile.phone or '—'}\n"
    )


def _format_catalog_subscription_warning_row(row: Any) -> str:
    """Format a single subscription warning row for delete preview."""
    expires = getattr(row, "expires_at", None)
    if hasattr(expires, "strftime"):
        expires_text = expires.strftime("%Y-%m-%d")
    else:
        expires_text = str(expires or "—")
    return (
        f"{row.streaming_email} - {row.client_name or '—'} - {row.client_phone or '—'} - "
        f"{row.service_name}/{row.plan_name} - expira {expires_text}"
    )


def _format_subscription_list(
    subscriptions: list[Any],
    show_status: bool = True,
    page: int = 1,
    total_pages: int = 1,
) -> tuple[str, dict[str, str]]:
    loc = ctx.get_locale()
    entries: list[str] = []
    selection_map: dict[str, str] = {}
    status_emoji_map = {
        "active": "✅",
        "expired": "⏰",
        "cancelled": "❌",
    }
    for i, sub in enumerate(subscriptions, start=1):
        num = str(i)
        emoji = status_emoji_map.get(sub.status, "❓")
        label = f"{emoji} {sub.streaming_email}"
        if show_status:
            status_name = _i18n_t(loc, f"wa.tenant.subscriptions.status.{sub.status}")
            label += f" ({status_name})"
        client_name = getattr(sub, "client_name", None) or getattr(
            sub, "client_full_name", ""
        )
        if client_name:
            label += f" — {client_name}"
        entries.append(f"{num}️⃣ {label}")
        selection_map[num] = str(sub.id)

    header = _i18n_t(loc, "wa.tenant.subscriptions.list.header")
    body = "\n".join(entries)

    # Build navigation line
    nav_parts: list[str] = [_i18n_t(loc, "wa.tenant.subscriptions.list.cancel")]
    if page > 1:
        nav_parts.append(_i18n_t(loc, "wa.tenant.subscriptions.list.page_prev"))
    if page < total_pages:
        nav_parts.append(_i18n_t(loc, "wa.tenant.subscriptions.list.page_next"))
    nav_line = " | ".join(nav_parts) if nav_parts else ""

    page_line = ""
    if total_pages > 1:
        page_line = _i18n_t(
            loc, "wa.tenant.subscriptions.list.page_info", page=page, total=total_pages
        )

    reply = header + body
    if page_line:
        reply += "\n\n" + page_line
    if nav_line:
        reply += "\n" + nav_line

    return reply, selection_map


def _format_subscription_detail(sub: Any, credentials: dict | None = None) -> str:
    loc = ctx.get_locale()
    status_emoji = _i18n_t(loc, f"wa.tenant.subscriptions.detail.status.{sub.status}")

    password_display = "—"
    pin_display = "—"
    if credentials:
        pwd = credentials.get("streaming_password")
        if pwd:
            password_display = pwd
        pin_val = credentials.get("profile_pin")
        if pin_val:
            pin_display = pin_val

    client_name = getattr(sub, "client_name", None) or getattr(
        sub, "client_full_name", "—"
    )
    service_name = getattr(sub, "service_name", None) or "—"
    plan_name = getattr(sub, "plan_name", None) or "—"
    profile_name = sub.profile_name or "—"

    starts_at = ""
    if sub.starts_at:
        if hasattr(sub.starts_at, "strftime"):
            starts_at = sub.starts_at.strftime("%Y-%m-%d")
        else:
            starts_at = str(sub.starts_at)

    expires_at = ""
    if sub.expires_at:
        if hasattr(sub.expires_at, "strftime"):
            expires_at = sub.expires_at.strftime("%Y-%m-%d")
        else:
            expires_at = str(sub.expires_at)

    duration_labels = {
        "1_month": "1 mes",
        "3_months": "3 meses",
        "6_months": "6 meses",
        "9_months": "9 meses",
        "1_year": "1 año",
        "custom": "Personalizada",
    }
    duration_label = duration_labels.get(sub.duration_type, sub.duration_type)

    return (
        f"{_i18n_t(loc, 'wa.tenant.subscriptions.detail.header')}"
        f"*Estado:* {status_emoji}\n"
        f"*Cliente:* {client_name}\n"
        f"*Servicio:* {service_name}\n"
        f"*Plan:* {plan_name}\n"
        f"*Email:* {sub.streaming_email}\n"
        f"*Contraseña:* {password_display}\n"
        f"*Perfil:* {profile_name}\n"
        f"*PIN:* {pin_display}\n"
        f"*Duración:* {duration_label}\n"
        f"*Inicio:* {starts_at}\n"
        f"*Expira:* {expires_at}\n"
    )
