"""Client Context Shortcut creation flow and active/inactive client menus.

Called from ``console_handlers._handle_active_client_context`` for the
Item 6 responsibilities:
- Creating a new Client from an unregistered target (with phone skip or
  LID-only phone prompt)
- Active client detail/actions menu (except phone editing)
- Inactive client reactivate/edit/delete menu (no "Crear suscripción")
- Subscription shortcut (skip client selection)
"""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import string

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.i18n import t
from app.core.errors import UserFacingError, translate_error
from app.core.input_validation import (
    validate_client_local_username,
    validate_full_name as _validate_full_name,
    validate_phone as _validate_phone,
)
from app.models import Client as _ClientModel
from app.models import Tenant as _TenantModel
from app.repositories import blocked_clients_repository, clients_repository
from app.schemas.client import ClientCreate
from app.schemas.whatsapp import WhatsAppConsoleResponse
from app.services.client_service import ClientService
from app.services.whatsapp_navigation import is_back
from app.services.whatsapp_session_service import (
    WhatsAppSessionService,
)

logger = logging.getLogger(__name__)


def _ctx_locale(tenant: _TenantModel, data: dict | None = None) -> str:
    if data:
        temp_data = data.get("temp_data", {})
        if temp_data.get("locale"):
            return temp_data["locale"]
    settings = getattr(tenant, "settings", None)
    return getattr(settings, "locale", None) or "es"


def _ctx_t(tenant: _TenantModel, data: dict, key: str, **kwargs) -> str:
    return t(_ctx_locale(tenant, data), key, **kwargs)


def _generate_client_password(length: int = 14) -> str:
    alphabet = string.ascii_letters + string.digits + "_-"
    return "".join(secrets.choice(alphabet) for _ in range(length))


# ====================================================================
# Context shortcut: Client creation flow (unregistered targets)
# ====================================================================


async def handle_ctx_creating_first(
    data: dict,
    tenant: _TenantModel,
    db: AsyncSession,
    admin_jid: str | None,
) -> WhatsAppConsoleResponse:
    """First entry into the creating flow.

    Called when the admin selects ``1`` from the unblocked unregistered
    target menu.  Checks if ``target_phone`` exists in ``temp_data``:
    if yes, prefill the phone and skip to the name prompt; if only
    ``target_lid`` exists, ask for the phone first.
    """
    temp_data = data["temp_data"]
    target_phone = temp_data.get("target_phone", "")

    if target_phone:
        temp_data["phone"] = target_phone
        data["step"] = "creating_name"
        reply = _ctx_t(
            tenant,
            data,
            "wa.tenant.client_context.create.phone_prefilled",
            identity=target_phone,
        )
    else:
        data["step"] = "creating_phone"
        reply = _ctx_t(tenant, data, "wa.tenant.client_context.create.phone_prompt")

    return WhatsAppConsoleResponse(reply=reply, reply_to=admin_jid)


async def handle_ctx_creating_phone(
    msg_lower: str,
    message: str,
    data: dict,
    admin_jid: str | None,
    tenant: _TenantModel,
) -> WhatsAppConsoleResponse:
    """Handle phone input in the creating flow."""
    stripped = message.strip()
    try:
        normalized = _validate_phone(stripped)
        data["temp_data"]["phone"] = normalized
    except Exception:
        return WhatsAppConsoleResponse(
            reply=_ctx_t(tenant, data, "wa.tenant.client_context.create.phone_invalid"),
            reply_to=admin_jid,
        )

    data["step"] = "creating_name"
    return WhatsAppConsoleResponse(
        reply=_ctx_t(tenant, data, "wa.tenant.client_context.create.phone_registered"),
        reply_to=admin_jid,
    )


async def handle_ctx_creating_name(
    msg_lower: str,
    message: str,
    data: dict,
    admin_jid: str | None,
    tenant: _TenantModel,
) -> WhatsAppConsoleResponse:
    """Handle full name input in the creating flow."""
    stripped = message.strip()
    if not stripped:
        return WhatsAppConsoleResponse(
            reply=_ctx_t(tenant, data, "wa.tenant.client_context.create.name_empty"),
            reply_to=admin_jid,
        )

    try:
        name = _validate_full_name(stripped)
    except Exception as exc:
        return WhatsAppConsoleResponse(
            reply=_ctx_t(
                tenant,
                data,
                "wa.tenant.client_context.create.name_invalid",
                exc=str(exc),
            ),
            reply_to=admin_jid,
        )

    data["temp_data"]["full_name"] = name
    data["step"] = "creating_username"
    return WhatsAppConsoleResponse(
        reply=_ctx_t(tenant, data, "wa.tenant.client_context.create.name_registered"),
        reply_to=admin_jid,
    )


async def handle_ctx_creating_username(
    msg_lower: str,
    message: str,
    data: dict,
    admin_jid: str | None,
    tenant: _TenantModel,
) -> WhatsAppConsoleResponse:
    """Handle local username input in the creating flow."""
    stripped = message.strip()
    if not stripped:
        return WhatsAppConsoleResponse(
            reply=_ctx_t(
                tenant, data, "wa.tenant.client_context.create.username_empty"
            ),
            reply_to=admin_jid,
        )

    try:
        local_username = validate_client_local_username(stripped)
    except Exception as exc:
        return WhatsAppConsoleResponse(
            reply=_ctx_t(
                tenant,
                data,
                "wa.tenant.client_context.create.username_invalid",
                exc=str(exc),
            ),
            reply_to=admin_jid,
        )

    data["temp_data"]["local_username"] = local_username
    data["step"] = "creating_password_choice"
    return WhatsAppConsoleResponse(
        reply=_ctx_t(tenant, data, "wa.tenant.client_context.create.password_choice"),
        reply_to=admin_jid,
    )


async def handle_ctx_creating_password_choice(
    msg_lower: str,
    data: dict,
    admin_jid: str | None,
    tenant: _TenantModel,
) -> WhatsAppConsoleResponse:
    """Handle password mode selection in the creating flow."""
    if msg_lower == "1":
        data["temp_data"]["password"] = _generate_client_password()
        data["temp_data"]["password_mode"] = "generated"
        data["step"] = "creating_confirm"
        return WhatsAppConsoleResponse(
            reply=_creation_summary(tenant, data),
            reply_to=admin_jid,
        )

    if msg_lower == "2":
        data["step"] = "creating_password_manual"
        return WhatsAppConsoleResponse(
            reply=_ctx_t(
                tenant, data, "wa.tenant.client_context.create.password_manual_prompt"
            ),
            reply_to=admin_jid,
        )

    return WhatsAppConsoleResponse(
        reply=_ctx_t(
            tenant, data, "wa.tenant.client_context.create.password_choice_invalid"
        ),
        reply_to=admin_jid,
    )


async def handle_ctx_creating_password_manual(
    msg_lower: str,
    message: str,
    data: dict,
    admin_jid: str | None,
    tenant: _TenantModel,
) -> WhatsAppConsoleResponse:
    """Handle manual password input in the creating flow."""
    password = message.strip()
    if len(password) < 8:
        return WhatsAppConsoleResponse(
            reply=_ctx_t(
                tenant, data, "wa.tenant.client_context.create.password_too_short"
            ),
            reply_to=admin_jid,
        )

    data["temp_data"]["password"] = password
    data["temp_data"]["password_mode"] = "manual"
    data["step"] = "creating_confirm"
    return WhatsAppConsoleResponse(
        reply=_creation_summary(tenant, data), reply_to=admin_jid
    )


def _creation_summary(tenant: _TenantModel, data: dict) -> str:
    td = data["temp_data"]
    return _ctx_t(
        tenant,
        data,
        "wa.tenant.client_context.create.summary",
        full_name=td.get("full_name", ""),
        local_username=td.get("local_username", ""),
        phone=td.get("phone", "--"),
    )


async def handle_ctx_creating_confirm(
    msg_lower: str,
    message: str,
    data: dict,
    admin_jid: str | None,
    tenant: _TenantModel,
    db: AsyncSession,
    target_phone_norm: str | None,
    target_lid: str | None,
    clear_ctx,
) -> WhatsAppConsoleResponse:
    """Handle confirmation in the creating flow.

    Creates the client, clears any matching blocks, and clears the
    context.  Returns the success (or failure) reply.
    """
    stripped = message.strip().upper()
    if stripped not in ("CONFIRMAR", "CONFIRM"):
        td = data["temp_data"]
        summary = _creation_summary(tenant, data)
        return WhatsAppConsoleResponse(
            reply=_ctx_t(
                tenant, data, "wa.tenant.client_context.create.confirm_invalid"
            )
            + "\n\n"
            + summary,
            reply_to=admin_jid,
        )

    td = data["temp_data"]
    payload = ClientCreate(
        full_name=td.get("full_name", ""),
        local_username=td.get("local_username", ""),
        phone=td.get("phone"),
        password=td.get("password", ""),
    )

    try:
        client_service = ClientService()
        client = await client_service.create_client(db, tenant.id, payload)
    except UserFacingError as exc:
        data["temp_data"]["_ctx_cleared"] = True
        await clear_ctx()
        return WhatsAppConsoleResponse(
            reply=f"{translate_error(_ctx_locale(tenant, data), exc)}",
            reply_to=admin_jid,
        )
    except Exception:
        logger.exception("Context shortcut client creation failed")
        data["temp_data"]["_ctx_cleared"] = True
        await clear_ctx()
        return WhatsAppConsoleResponse(
            reply=_ctx_t(tenant, data, "wa.tenant.client_context.create.error"),
            reply_to=admin_jid,
        )

    if client is None:
        data["temp_data"]["_ctx_cleared"] = True
        await clear_ctx()
        return WhatsAppConsoleResponse(
            reply=_ctx_t(tenant, data, "wa.tenant.client_context.create.error"),
            reply_to=admin_jid,
        )

    # Clear any matching blocks for the identity
    try:
        await blocked_clients_repository.clear_identity(
            db,
            tenant_id=tenant.id,
            phone=target_phone_norm,
            whatsapp_lid=None,
        )
        await db.commit()
    except Exception:
        logger.exception("Failed to clear blocks after context shortcut creation")

    data["temp_data"]["client_id"] = str(client.id)
    data["step"] = "post_create_menu"
    password_line = ""
    if td.get("password_mode") == "generated":
        password_line = _ctx_t(
            tenant,
            data,
            "wa.tenant.client_context.create.success.generated_password_line",
            password=td.get("password", ""),
        )
    return WhatsAppConsoleResponse(
        reply=_ctx_t(
            tenant,
            data,
            "wa.tenant.client_context.create.success",
            full_name=client.full_name,
            username=client.username,
            phone=client.phone or "--",
            password_line=password_line,
        ),
        reply_to=admin_jid,
    )


# ====================================================================
# Context shortcut: Active client menu
# ====================================================================


async def handle_ctx_active_client_menu(
    msg_lower: str,
    message: str,
    data: dict,
    admin_jid: str | None,
    client: _ClientModel,
    tenant: _TenantModel,
    db: AsyncSession,
    save_ctx,
    clear_ctx,
) -> WhatsAppConsoleResponse:
    """Handle messages for a target that is an existing active Client.

    Menu (canonical):
    1 Ver detalle
    2 Editar cliente
    3 Crear suscripcion
    4 Desactivar cliente
    5 Eliminar cliente
    0 Cancelar
    """
    locale = _ctx_locale(tenant, data)
    target_phone = data.get("temp_data", {}).get("target_phone")

    if msg_lower == "1":
        data["step"] = "active_detail"
        data["temp_data"]["client_id"] = str(client.id)
        await save_ctx(refresh_ttl=True)
        return WhatsAppConsoleResponse(
            reply=_render_active_client_detail_text(locale, target_phone, client),
            reply_to=admin_jid,
        )

    if msg_lower == "2":
        data["step"] = "active_edit_field"
        data["temp_data"]["client_id"] = str(client.id)
        await save_ctx(refresh_ttl=True)
        return WhatsAppConsoleResponse(
            reply=_ctx_t(tenant, data, "wa.tenant.client_context.edit.field_prompt"),
            reply_to=admin_jid,
        )

    if msg_lower == "3":
        data["step"] = "active_view_subscriptions"
        await save_ctx(refresh_ttl=True)
        return await handle_ctx_active_view_subscriptions(
            msg_lower,
            message,
            data,
            admin_jid,
            client,
            tenant,
            db,
            save_ctx,
            clear_ctx,
        )

    if msg_lower == "4":
        data["step"] = "active_deactivate_confirm"
        await save_ctx(refresh_ttl=True)
        return WhatsAppConsoleResponse(
            reply=_ctx_t(
                tenant,
                data,
                "wa.tenant.client_context.deactivate.confirm",
                client_name=client.full_name,
            ),
            reply_to=admin_jid,
        )

    if msg_lower == "5":
        await save_ctx(refresh_ttl=True)
        return WhatsAppConsoleResponse(
            reply=_with_current_screen_message(
                _ctx_t(
                    tenant,
                    data,
                    "wa.tenant.client_context.active.delete_blocked",
                    client_name=client.full_name,
                    phone_line=_client_phone_line(locale, target_phone or client.phone),
                ),
                _render_active_client_menu_text(locale, target_phone, client),
            ),
            reply_to=admin_jid,
        )

    await save_ctx(refresh_ttl=True)
    return WhatsAppConsoleResponse(
        reply=_with_current_screen_message(
            _ctx_t(tenant, data, "wa.tenant.client_context.invalid_option"),
            _render_active_client_menu_text(locale, target_phone, client),
        ),
        reply_to=admin_jid,
    )


async def handle_ctx_active_detail(
    msg_lower: str,
    message: str,
    data: dict,
    admin_jid: str | None,
    client: _ClientModel,
    tenant: _TenantModel,
    db: AsyncSession,
    save_ctx,
    clear_ctx,
) -> WhatsAppConsoleResponse:
    """Handle actions from active client detail view."""
    locale = _ctx_locale(tenant, data)
    target_phone = data.get("temp_data", {}).get("target_phone")

    if is_back(msg_lower):
        data["step"] = "active_menu"
        await save_ctx(refresh_ttl=True)
        return WhatsAppConsoleResponse(
            reply=_render_active_client_menu_text(locale, target_phone, client),
            reply_to=admin_jid,
        )

    if msg_lower == "1":
        data["step"] = "active_edit_field"
        await save_ctx(refresh_ttl=True)
        return WhatsAppConsoleResponse(
            reply=_ctx_t(tenant, data, "wa.tenant.client_context.edit.field_prompt"),
            reply_to=admin_jid,
        )

    if msg_lower == "2":
        data["step"] = "active_deactivate_confirm"
        await save_ctx(refresh_ttl=True)
        return WhatsAppConsoleResponse(
            reply=_ctx_t(
                tenant,
                data,
                "wa.tenant.client_context.deactivate.confirm",
                client_name=client.full_name,
            ),
            reply_to=admin_jid,
        )

    await save_ctx(refresh_ttl=False)
    return WhatsAppConsoleResponse(
        reply=_with_current_screen_message(
            _ctx_t(tenant, data, "wa.tenant.client_context.invalid_option"),
            _render_active_client_detail_text(locale, target_phone, client),
        ),
        reply_to=admin_jid,
    )


async def handle_ctx_active_edit_field(
    msg_lower: str,
    message: str,
    data: dict,
    admin_jid: str | None,
    tenant: _TenantModel,
    client: _ClientModel | None = None,
) -> WhatsAppConsoleResponse | None:
    """Handle field selection for active client edit."""
    if is_back(msg_lower):
        locale = _ctx_locale(tenant, data)
        target_phone = data.get("temp_data", {}).get("target_phone")
        data["step"] = "active_detail"
        return WhatsAppConsoleResponse(
            reply=_render_active_client_detail_text(locale, target_phone, client)
            if client
            else _ctx_t(tenant, data, "wa.tenant.client_context.detail.header"),
            reply_to=admin_jid,
        )

    if msg_lower == "1":
        data["temp_data"]["edit_field"] = "full_name"
        data["step"] = "active_edit_value"
        return WhatsAppConsoleResponse(
            reply=_ctx_t(tenant, data, "wa.tenant.client_context.edit.name_prompt"),
            reply_to=admin_jid,
        )

    if msg_lower == "2":
        data["temp_data"]["edit_field"] = "local_username"
        data["step"] = "active_edit_value"
        return WhatsAppConsoleResponse(
            reply=_ctx_t(tenant, data, "wa.tenant.client_context.edit.username_prompt"),
            reply_to=admin_jid,
        )

    return WhatsAppConsoleResponse(
        reply=_ctx_t(tenant, data, "wa.tenant.client_context.edit.field_invalid"),
        reply_to=admin_jid,
    )


async def handle_ctx_active_edit_value(
    msg_lower: str,
    message: str,
    data: dict,
    admin_jid: str | None,
    tenant: _TenantModel,
    db: AsyncSession,
    save_ctx,
    clear_ctx,
) -> WhatsAppConsoleResponse:
    """Handle new value input for active client edit."""
    if is_back(msg_lower):
        data["step"] = "active_edit_field"
        await save_ctx(refresh_ttl=True)
        return WhatsAppConsoleResponse(
            reply=_ctx_t(tenant, data, "wa.tenant.client_context.edit.field_prompt"),
            reply_to=admin_jid,
        )

    field = data["temp_data"].get("edit_field", "")
    new_value = message.strip()
    client_id = UUID(data["temp_data"]["client_id"])

    from app.schemas.client import ClientUpdate

    payload = ClientUpdate(**{field: new_value})
    try:
        client_service = ClientService()
        client = await client_service.update_client(db, tenant.id, client_id, payload)
    except UserFacingError as exc:
        await save_ctx(refresh_ttl=True)
        locale = _ctx_locale(tenant, data)
        prompt_key = (
            "wa.tenant.client_context.edit.name_prompt"
            if field == "full_name"
            else "wa.tenant.client_context.edit.username_prompt"
        )
        return WhatsAppConsoleResponse(
            reply=_with_current_screen_message(
                translate_error(locale, exc),
                _ctx_t(tenant, data, prompt_key),
            ),
            reply_to=admin_jid,
        )
    except Exception as exc:
        await clear_ctx()
        return WhatsAppConsoleResponse(
            reply=_ctx_t(
                tenant, data, "wa.tenant.client_context.edit.update_error", exc=str(exc)
            ),
            reply_to=admin_jid,
        )

    if client is None:
        await clear_ctx()
        return WhatsAppConsoleResponse(
            reply=_ctx_t(
                tenant, data, "wa.tenant.client_context.error.client_not_found"
            ),
            reply_to=admin_jid,
        )

    data["temp_data"].pop("edit_field", None)
    data["step"] = "active_detail"
    await save_ctx(refresh_ttl=True)
    return WhatsAppConsoleResponse(
        reply=_with_current_screen_message(
            _ctx_t(
                tenant,
                data,
                "wa.tenant.client_context.edit.updated_success",
                client_name=client.full_name,
            ),
            _render_active_client_detail_text(
                _ctx_locale(tenant, data),
                data.get("temp_data", {}).get("target_phone"),
                client,
            ),
        ),
        reply_to=admin_jid,
    )


async def handle_ctx_active_deactivate_confirm(
    msg_lower: str,
    message: str,
    data: dict,
    admin_jid: str | None,
    tenant: _TenantModel,
    db: AsyncSession,
    save_ctx,
    clear_ctx,
) -> WhatsAppConsoleResponse:
    """Handle deactivation confirmation for active client."""
    if is_back(msg_lower):
        data["step"] = "active_menu"
        await save_ctx(refresh_ttl=True)
        locale = _ctx_locale(tenant, data)
        target_phone = data.get("temp_data", {}).get("target_phone")
        client_id = UUID(data["temp_data"]["client_id"])
        try:
            client_service = ClientService()
            client = await client_service.get_client(db, tenant.id, client_id)
        except Exception:
            logger.exception("failed to reload client on back from deactivate confirm")
            await clear_ctx()
            return WhatsAppConsoleResponse(
                reply=_ctx_t(
                    tenant, data, "wa.tenant.client_context.error.client_not_found"
                ),
                reply_to=admin_jid,
            )
        if client:
            return WhatsAppConsoleResponse(
                reply=_render_active_client_menu_text(locale, target_phone, client),
                reply_to=admin_jid,
            )
        await clear_ctx()
        return WhatsAppConsoleResponse(
            reply=_ctx_t(
                tenant, data, "wa.tenant.client_context.error.client_not_found"
            ),
            reply_to=admin_jid,
        )

    stripped = message.strip().upper()
    if stripped not in ("CONFIRMAR", "CONFIRM"):
        return WhatsAppConsoleResponse(
            reply=_ctx_t(
                tenant, data, "wa.tenant.client_context.deactivate.prompt_again"
            ),
            reply_to=admin_jid,
        )

    client_id = UUID(data["temp_data"]["client_id"])
    try:
        client_service = ClientService()
        client = await client_service.deactivate_client(db, tenant.id, client_id)
    except Exception as exc:
        await clear_ctx()
        return WhatsAppConsoleResponse(
            reply=_ctx_t(
                tenant, data, "wa.tenant.client_context.deactivate.error", exc=str(exc)
            ),
            reply_to=admin_jid,
        )

    if client is None:
        await clear_ctx()
        return WhatsAppConsoleResponse(
            reply=_ctx_t(
                tenant, data, "wa.tenant.client_context.error.client_not_found"
            ),
            reply_to=admin_jid,
        )

    locale = _ctx_locale(tenant, data)
    target_phone = data.get("temp_data", {}).get("target_phone")
    # Keep context alive so subsequent ``0`` closes target session
    data["temp_data"]["menu_variant"] = "existing_inactive"
    data["temp_data"]["target_state"] = "existing_inactive"
    data["step"] = "inactive_menu"
    await save_ctx(refresh_ttl=True)
    return WhatsAppConsoleResponse(
        reply=_with_current_screen_message(
            _ctx_t(
                tenant,
                data,
                "wa.tenant.client_context.deactivate.success",
                client_name=client.full_name,
            ),
            _render_inactive_client_menu_text(locale, target_phone, client),
        ),
        reply_to=admin_jid,
    )


# ====================================================================
# Context shortcut: Inactive client menu
# ====================================================================


async def handle_ctx_inactive_client_menu(
    msg_lower: str,
    message: str,
    data: dict,
    admin_jid: str | None,
    client: _ClientModel,
    tenant: _TenantModel,
    db: AsyncSession,
    save_ctx,
    clear_ctx,
) -> WhatsAppConsoleResponse:
    """Handle messages for a target that is an existing inactive Client.

    Menu:
    1 Ver detalle
    2 Editar cliente
    3 Reactivar cliente
    4 Eliminar cliente
    0 Cancelar
    """
    locale = _ctx_locale(tenant, data)
    target_phone = data.get("temp_data", {}).get("target_phone")

    if msg_lower == "1":
        data["step"] = "inactive_detail"
        data["temp_data"]["client_id"] = str(client.id)
        await save_ctx(refresh_ttl=True)
        return WhatsAppConsoleResponse(
            reply=_render_inactive_client_detail_text(locale, target_phone, client),
            reply_to=admin_jid,
        )

    if msg_lower == "2":
        data["step"] = "inactive_edit_field"
        data["temp_data"]["client_id"] = str(client.id)
        await save_ctx(refresh_ttl=True)
        return WhatsAppConsoleResponse(
            reply=_ctx_t(tenant, data, "wa.tenant.client_context.edit.field_prompt"),
            reply_to=admin_jid,
        )

    if msg_lower == "3":
        return await _reactivate_context_client(
            client, data, admin_jid, tenant, db, save_ctx, clear_ctx
        )

    if msg_lower == "4":
        data["step"] = "inactive_delete_confirm"
        data["temp_data"]["client_id"] = str(client.id)
        await save_ctx(refresh_ttl=True)
        return WhatsAppConsoleResponse(
            reply=_ctx_t(
                tenant,
                data,
                "wa.tenant.client_context.inactive.delete_confirm",
                client_name=client.full_name,
            ),
            reply_to=admin_jid,
        )

    await save_ctx(refresh_ttl=True)
    return WhatsAppConsoleResponse(
        reply=_with_current_screen_message(
            _ctx_t(tenant, data, "wa.tenant.client_context.invalid_option"),
            _render_inactive_client_menu_text(locale, target_phone, client),
        ),
        reply_to=admin_jid,
    )


async def handle_ctx_inactive_detail(
    msg_lower: str,
    message: str,
    data: dict,
    admin_jid: str | None,
    client: _ClientModel,
    tenant: _TenantModel,
    db: AsyncSession,
    save_ctx,
    clear_ctx,
) -> WhatsAppConsoleResponse:
    locale = _ctx_locale(tenant, data)
    target_phone = data.get("temp_data", {}).get("target_phone")

    if is_back(msg_lower):
        data["step"] = "inactive_menu"
        await save_ctx(refresh_ttl=True)
        return WhatsAppConsoleResponse(
            reply=_render_inactive_client_menu_text(locale, target_phone, client),
            reply_to=admin_jid,
        )

    if msg_lower == "1":
        data["step"] = "inactive_edit_field"
        await save_ctx(refresh_ttl=True)
        return WhatsAppConsoleResponse(
            reply=_ctx_t(tenant, data, "wa.tenant.client_context.edit.field_prompt"),
            reply_to=admin_jid,
        )

    if msg_lower == "2":
        return await _reactivate_context_client(
            client, data, admin_jid, tenant, db, save_ctx, clear_ctx
        )

    if msg_lower == "3":
        data["step"] = "inactive_delete_confirm"
        await save_ctx(refresh_ttl=True)
        return WhatsAppConsoleResponse(
            reply=_ctx_t(
                tenant,
                data,
                "wa.tenant.client_context.inactive.delete_confirm",
                client_name=client.full_name,
            ),
            reply_to=admin_jid,
        )

    await save_ctx(refresh_ttl=False)
    return WhatsAppConsoleResponse(
        reply=_with_current_screen_message(
            _ctx_t(tenant, data, "wa.tenant.client_context.invalid_option"),
            _render_inactive_client_detail_text(locale, target_phone, client),
        ),
        reply_to=admin_jid,
    )


async def handle_ctx_inactive_edit_field(
    msg_lower: str,
    message: str,
    data: dict,
    admin_jid: str | None,
    tenant: _TenantModel,
    client: _ClientModel,
) -> WhatsAppConsoleResponse | None:
    """Handle field selection for inactive client edit."""
    if is_back(msg_lower):
        locale = _ctx_locale(tenant, data)
        target_phone = data.get("temp_data", {}).get("target_phone")
        data["step"] = "inactive_detail"
        return WhatsAppConsoleResponse(
            reply=_render_inactive_client_detail_text(locale, target_phone, client),
            reply_to=admin_jid,
        )

    if msg_lower == "1":
        data["temp_data"]["edit_field"] = "full_name"
        data["step"] = "inactive_edit_value"
        return WhatsAppConsoleResponse(
            reply=_ctx_t(tenant, data, "wa.tenant.client_context.edit.name_prompt"),
            reply_to=admin_jid,
        )

    if msg_lower == "2":
        data["temp_data"]["edit_field"] = "local_username"
        data["step"] = "inactive_edit_value"
        return WhatsAppConsoleResponse(
            reply=_ctx_t(tenant, data, "wa.tenant.client_context.edit.username_prompt"),
            reply_to=admin_jid,
        )

    return WhatsAppConsoleResponse(
        reply=_ctx_t(tenant, data, "wa.tenant.client_context.edit.field_invalid"),
        reply_to=admin_jid,
    )


async def handle_ctx_inactive_edit_value(
    msg_lower: str,
    message: str,
    data: dict,
    admin_jid: str | None,
    tenant: _TenantModel,
    db: AsyncSession,
    save_ctx,
    clear_ctx,
) -> WhatsAppConsoleResponse:
    """Handle new value input for inactive client edit."""
    if is_back(msg_lower):
        data["step"] = "inactive_edit_field"
        await save_ctx(refresh_ttl=True)
        return WhatsAppConsoleResponse(
            reply=_ctx_t(tenant, data, "wa.tenant.client_context.edit.field_prompt"),
            reply_to=admin_jid,
        )

    field = data["temp_data"].get("edit_field", "")
    new_value = message.strip()
    client_id = UUID(data["temp_data"]["client_id"])
    locale = _ctx_locale(tenant, data)
    target_phone = data.get("temp_data", {}).get("target_phone")
    prompt_key = (
        "wa.tenant.client_context.edit.name_prompt"
        if field == "full_name"
        else "wa.tenant.client_context.edit.username_prompt"
    )

    from app.schemas.client import ClientUpdate

    payload = ClientUpdate(**{field: new_value})
    try:
        client_service = ClientService()
        client = await client_service.update_client(db, tenant.id, client_id, payload)
    except UserFacingError as exc:
        await save_ctx(refresh_ttl=True)
        return WhatsAppConsoleResponse(
            reply=_with_current_screen_message(
                translate_error(locale, exc),
                _ctx_t(tenant, data, prompt_key),
            ),
            reply_to=admin_jid,
        )
    except Exception as exc:
        await clear_ctx()
        return WhatsAppConsoleResponse(
            reply=_ctx_t(
                tenant, data, "wa.tenant.client_context.edit.update_error", exc=str(exc)
            ),
            reply_to=admin_jid,
        )

    if client is None:
        await clear_ctx()
        return WhatsAppConsoleResponse(
            reply=_ctx_t(
                tenant, data, "wa.tenant.client_context.error.client_not_found"
            ),
            reply_to=admin_jid,
        )

    data["temp_data"].pop("edit_field", None)
    data["step"] = "inactive_detail"
    await save_ctx(refresh_ttl=True)
    return WhatsAppConsoleResponse(
        reply=_with_current_screen_message(
            _ctx_t(
                tenant,
                data,
                "wa.tenant.client_context.edit.updated_success",
                client_name=client.full_name,
            ),
            _render_inactive_client_detail_text(locale, target_phone, client),
        ),
        reply_to=admin_jid,
    )


async def handle_ctx_inactive_delete_confirm(
    msg_lower: str,
    message: str,
    data: dict,
    admin_jid: str | None,
    tenant: _TenantModel,
    db: AsyncSession,
    save_ctx,
    clear_ctx,
) -> WhatsAppConsoleResponse:
    """Handle delete confirmation for inactive client."""
    if is_back(msg_lower):
        data["step"] = "inactive_menu"
        await save_ctx(refresh_ttl=True)
        locale = _ctx_locale(tenant, data)
        target_phone = data.get("temp_data", {}).get("target_phone")
        client_id = UUID(data["temp_data"]["client_id"])
        try:
            client_service = ClientService()
            client = await client_service.get_client(db, tenant.id, client_id)
        except Exception:
            logger.exception(
                "failed to reload client on back from inactive delete confirm"
            )
            await clear_ctx()
            return WhatsAppConsoleResponse(
                reply=_ctx_t(
                    tenant, data, "wa.tenant.client_context.error.client_not_found"
                ),
                reply_to=admin_jid,
            )
        if client:
            return WhatsAppConsoleResponse(
                reply=_render_inactive_client_menu_text(locale, target_phone, client),
                reply_to=admin_jid,
            )
        await clear_ctx()
        return WhatsAppConsoleResponse(
            reply=_ctx_t(
                tenant, data, "wa.tenant.client_context.error.client_not_found"
            ),
            reply_to=admin_jid,
        )

    stripped = message.strip().upper()
    if stripped not in ("CONFIRMAR", "CONFIRM"):
        return WhatsAppConsoleResponse(
            reply=_ctx_t(
                tenant, data, "wa.tenant.client_context.inactive.delete_prompt_again"
            ),
            reply_to=admin_jid,
        )

    client_id = UUID(data["temp_data"]["client_id"])
    client_name = ""
    client_service = ClientService()

    try:
        existing = await client_service.get_client(db, tenant.id, client_id)
        if existing:
            client_name = existing.full_name
    except Exception:
        pass

    try:
        deleted = await client_service.delete_client(db, tenant.id, client_id)
    except UserFacingError as exc:
        await clear_ctx()
        return WhatsAppConsoleResponse(
            reply=f"{translate_error(_ctx_locale(tenant, data), exc)}",
            reply_to=admin_jid,
        )
    except Exception as exc:
        await clear_ctx()
        return WhatsAppConsoleResponse(
            reply=_ctx_t(
                tenant,
                data,
                "wa.tenant.client_context.inactive.delete_error",
                exc=str(exc),
            ),
            reply_to=admin_jid,
        )

    if not deleted:
        await clear_ctx()
        return WhatsAppConsoleResponse(
            reply=_ctx_t(
                tenant, data, "wa.tenant.client_context.inactive.delete_error", exc=""
            ),
            reply_to=admin_jid,
        )

    data["temp_data"]["menu_variant"] = "unregistered"
    data["temp_data"]["target_state"] = "unregistered_unblocked"
    data["step"] = "menu"

    unregistered_menu, metadata = await render_initial_context_menu(
        db=db,
        tenant=tenant,
        target_phone=data.get("temp_data", {}).get("target_phone"),
        target_lid=data.get("temp_data", {}).get("target_lid"),
        target_jid=data.get("temp_data", {}).get("target_jid"),
    )
    data["temp_data"].update(metadata)
    await save_ctx(refresh_ttl=True)
    return WhatsAppConsoleResponse(
        reply=_with_current_screen_message(
            _ctx_t(
                tenant,
                data,
                "wa.tenant.client_context.inactive.delete_success",
                client_name=client_name,
            ),
            unregistered_menu,
        ),
        reply_to=admin_jid,
    )


# ====================================================================
# View subscriptions helpers
# ====================================================================


def _render_subscriptions_list_text(
    locale: str,
    client_name: str,
    subscriptions: list,
) -> str:
    """Render the subscriptions list screen for the context shortcut."""
    parts = [
        t(
            locale,
            "wa.tenant.client_context.subscriptions.list",
            client_name=client_name,
        )
    ]

    if not subscriptions:
        parts.append(t(locale, "wa.tenant.client_context.subscriptions.empty"))
        create_num = 1
    else:
        for i, sub in enumerate(subscriptions, start=1):
            status_label = t(locale, "wa.tenant.subscriptions.status.active")
            parts.append(
                t(
                    locale,
                    "wa.tenant.client_context.subscriptions.item_with_expiry",
                    number=i,
                    service_name=sub.service.name,
                    plan_name=sub.plan.name,
                    status=status_label,
                    expires=sub.expires_at.strftime("%Y-%m-%d")
                    if sub.expires_at
                    else "-",
                )
            )
        create_num = len(subscriptions) + 1

    parts.append("")
    parts.append(
        t(
            locale,
            "wa.tenant.client_context.subscriptions.list_nav_create",
            number=create_num,
        )
    )
    return "\n".join(parts)


def _render_subscription_detail_text(
    locale: str,
    sub,
) -> str:
    """Render a single subscription's detail for the context shortcut."""
    if sub.status == "active":
        status_label = t(locale, "wa.tenant.subscriptions.detail.status.active")
    elif sub.status == "expired":
        status_label = t(locale, "wa.tenant.subscriptions.detail.status.expired")
    elif sub.status == "cancelled":
        status_label = t(locale, "wa.tenant.subscriptions.detail.status.cancelled")
    else:
        status_label = sub.status

    detail = t(
        locale,
        "wa.tenant.client_context.subscriptions.detail",
        service_name=sub.service.name,
        plan_name=sub.plan.name,
        email=sub.streaming_email,
        status=status_label,
        started=sub.starts_at.strftime("%Y-%m-%d") if sub.starts_at else "-",
        expires=sub.expires_at.strftime("%Y-%m-%d") if sub.expires_at else "-",
    )
    return (
        detail + "\n" + t(locale, "wa.tenant.client_context.subscriptions.detail_nav")
    )


def _render_extend_duration_text(
    locale: str,
    service_name: str,
    plan_name: str,
) -> str:
    """Render the extend subscription duration selection screen."""
    return (
        f"📅 *Extender Suscripcion*\n\n"
        f"*Servicio:* {service_name}\n"
        f"*Plan:* {plan_name}\n\n"
        f"Selecciona la duracion:\n\n"
        f"1️⃣ 1 mes\n"
        f"2️⃣ 3 meses\n"
        f"3️⃣ 6 meses\n"
        f"4️⃣ 1 ano\n"
        f"9️⃣ Volver\n"
        f"0️⃣ Cancelar"
    )


def _render_extend_confirm_text(
    locale: str,
    service_name: str,
    plan_name: str,
    duration_label: str,
    expires_at_str: str,
) -> str:
    """Render the extend subscription confirmation screen."""
    return (
        f"🔄 *Confirmar Extension*\n\n"
        f"*Servicio:* {service_name}\n"
        f"*Plan:* {plan_name}\n"
        f"*Duracion:* {duration_label}\n"
        f"*Nueva expiracion:* {expires_at_str}\n\n"
        f"Escribe *CONFIRMAR* para extender la suscripcion.\n"
        f"Escribe *0* para cancelar."
    )


# ====================================================================
# View subscriptions handlers
# ====================================================================


async def handle_ctx_active_view_subscriptions(
    msg_lower: str,
    message: str,
    data: dict,
    admin_jid: str | None,
    client: _ClientModel,
    tenant: _TenantModel,
    db: AsyncSession,
    save_ctx,
    clear_ctx,
) -> WhatsAppConsoleResponse:
    """Handle the view subscriptions list screen (active client)."""
    # This handler is called both on entry (msg_lower from user selection)
    # and on subsequent messages. On entry via the menu handler,
    # msg_lower is the menu option "3", NOT a subscription selection.
    # We re-route: if msg_lower == "3" (called from menu handler's entry),
    # just render the list and return.

    locale = _ctx_locale(tenant, data)
    target_phone = data.get("temp_data", {}).get("target_phone")
    step = data.get("step", "")

    from app.models.subscription import Subscription as _Sub
    from sqlalchemy import select as _select
    from sqlalchemy.orm import selectinload as _selectinload

    async def _fetch_subs():
        stmt = (
            _select(_Sub)
            .options(_selectinload(_Sub.service), _selectinload(_Sub.plan))
            .where(
                _Sub.tenant_id == tenant.id,
                _Sub.client_id == client.id,
                _Sub.status == "active",
            )
            .order_by(_Sub.expires_at.asc())
        )
        res = await db.execute(stmt)
        return list(res.scalars().all())

    subscriptions = await _fetch_subs()
    num_subs = len(subscriptions)

    # On first entry from menu handler, just render the list
    if msg_lower == "3" and step == "active_view_subscriptions":
        data["step"] = "active_view_subscriptions"
        await save_ctx(refresh_ttl=True)
        return WhatsAppConsoleResponse(
            reply=_render_subscriptions_list_text(
                locale, client.full_name, subscriptions
            ),
            reply_to=admin_jid,
        )

    # Back navigation
    if is_back(msg_lower):
        data["step"] = "active_menu"
        await save_ctx(refresh_ttl=True)
        return WhatsAppConsoleResponse(
            reply=_render_active_client_menu_text(locale, target_phone, client),
            reply_to=admin_jid,
        )

    # Subscription selection or create option
    if msg_lower.isdigit():
        idx = int(msg_lower)
        if 1 <= idx <= num_subs:
            sub = subscriptions[idx - 1]
            data["step"] = "active_subscription_detail"
            data["temp_data"]["selected_sub_id"] = str(sub.id)
            data["temp_data"]["selected_sub_service"] = sub.service.name
            data["temp_data"]["selected_sub_plan"] = sub.plan.name
            data["temp_data"]["selected_sub_email"] = sub.streaming_email
            await save_ctx(refresh_ttl=True)
            return WhatsAppConsoleResponse(
                reply=_render_subscription_detail_text(locale, sub),
                reply_to=admin_jid,
            )

        create_option = num_subs + 1
        if idx == create_option:
            return await _start_context_subscription(
                client, data, admin_jid, tenant, db, save_ctx, clear_ctx
            )

    # Invalid option
    await save_ctx(refresh_ttl=False)
    return WhatsAppConsoleResponse(
        reply=_with_current_screen_message(
            _ctx_t(tenant, data, "wa.tenant.client_context.invalid_option"),
            _render_subscriptions_list_text(locale, client.full_name, subscriptions),
        ),
        reply_to=admin_jid,
    )


async def handle_ctx_view_subscription_detail(
    msg_lower: str,
    message: str,
    data: dict,
    admin_jid: str | None,
    client: _ClientModel,
    tenant: _TenantModel,
    db: AsyncSession,
    save_ctx,
    clear_ctx,
) -> WhatsAppConsoleResponse:
    """Handle actions from subscription detail view (active client)."""
    locale = _ctx_locale(tenant, data)
    target_phone = data.get("temp_data", {}).get("target_phone")
    sub_id_str = data.get("temp_data", {}).get("selected_sub_id", "")
    sub_service = data.get("temp_data", {}).get("selected_sub_service", "")
    sub_plan = data.get("temp_data", {}).get("selected_sub_plan", "")

    from app.models.subscription import Subscription as _Sub
    from sqlalchemy import select as _select
    from sqlalchemy.orm import selectinload as _selectinload

    async def _fetch_sub():
        if not sub_id_str:
            return None
        stmt = (
            _select(_Sub)
            .options(_selectinload(_Sub.service), _selectinload(_Sub.plan))
            .where(
                _Sub.tenant_id == tenant.id,
                _Sub.id == UUID(sub_id_str),
            )
        )
        res = await db.execute(stmt)
        return res.scalar_one_or_none()

    async def _fetch_subs():
        stmt = (
            _select(_Sub)
            .options(_selectinload(_Sub.service), _selectinload(_Sub.plan))
            .where(
                _Sub.tenant_id == tenant.id,
                _Sub.client_id == client.id,
                _Sub.status == "active",
            )
            .order_by(_Sub.expires_at.asc())
        )
        res = await db.execute(stmt)
        return list(res.scalars().all())

    # Back: go to subscriptions list
    if is_back(msg_lower):
        data["step"] = "active_view_subscriptions"
        await save_ctx(refresh_ttl=True)
        subs = await _fetch_subs()
        return WhatsAppConsoleResponse(
            reply=_render_subscriptions_list_text(locale, client.full_name, subs),
            reply_to=admin_jid,
        )

    # Extend expiry
    if msg_lower == "1":
        sub = await _fetch_sub()
        if sub is not None:
            data["step"] = "active_extend_subs"
            data["temp_data"]["extend_sub_id"] = sub_id_str
            data["temp_data"]["extend_service_name"] = sub.service.name
            data["temp_data"]["extend_plan_name"] = sub.plan.name
            await save_ctx(refresh_ttl=True)
            return WhatsAppConsoleResponse(
                reply=_render_extend_duration_text(
                    locale, sub.service.name, sub.plan.name
                ),
                reply_to=admin_jid,
            )

    # Deactivate subscription
    if msg_lower == "2":
        data["step"] = "active_deactivate_sub_confirm"
        await save_ctx(refresh_ttl=True)
        confirm_text = _ctx_t(
            tenant, data, "wa.tenant.client_context.subscriptions.deactivate_confirm"
        )
        return WhatsAppConsoleResponse(
            reply=confirm_text,
            reply_to=admin_jid,
        )

    # Invalid
    await save_ctx(refresh_ttl=False)
    sub = await _fetch_sub()
    return WhatsAppConsoleResponse(
        reply=_with_current_screen_message(
            _ctx_t(tenant, data, "wa.tenant.client_context.invalid_option"),
            _render_subscription_detail_text(locale, sub)
            if sub
            else (_ctx_t(tenant, data, "wa.tenant.client_context.subscriptions.list")),
        ),
        reply_to=admin_jid,
    )


async def handle_ctx_active_extend_subscription(
    msg_lower: str,
    message: str,
    data: dict,
    admin_jid: str | None,
    client: _ClientModel,
    tenant: _TenantModel,
    db: AsyncSession,
    save_ctx,
    clear_ctx,
) -> WhatsAppConsoleResponse:
    """Handle extend subscription duration selection and confirmation."""
    locale = _ctx_locale(tenant, data)
    target_phone = data.get("temp_data", {}).get("target_phone")
    sub_id_str = data.get("temp_data", {}).get("extend_sub_id", "")
    service_name = data.get("temp_data", {}).get("extend_service_name", "")
    plan_name = data.get("temp_data", {}).get("extend_plan_name", "")

    from app.models.subscription import Subscription as _Sub
    from sqlalchemy import select as _select
    from sqlalchemy.orm import selectinload as _selectinload

    SUBSCRIPTIONS_DURATION_MAP = {
        "1": "1_month",
        "2": "3_months",
        "3": "6_months",
        "4": "1_year",
    }

    SUBSCRIPTIONS_DURATION_LABELS = {
        "1_month": "1 mes",
        "3_months": "3 meses",
        "6_months": "6 meses",
        "1_year": "1 ano",
    }

    async def _fetch_sub():
        if not sub_id_str:
            return None
        stmt = (
            _select(_Sub)
            .options(_selectinload(_Sub.service), _selectinload(_Sub.plan))
            .where(
                _Sub.tenant_id == tenant.id,
                _Sub.id == UUID(sub_id_str),
            )
        )
        res = await db.execute(stmt)
        return res.scalar_one_or_none()

    async def _fetch_subs():
        from app.models.subscription import Subscription as _Sub2

        stmt = (
            _select(_Sub2)
            .options(_selectinload(_Sub2.service), _selectinload(_Sub2.plan))
            .where(
                _Sub2.tenant_id == tenant.id,
                _Sub2.client_id == client.id,
                _Sub2.status == "active",
            )
            .order_by(_Sub2.expires_at.asc())
        )
        res = await db.execute(stmt)
        return list(res.scalars().all())

    # Back: go to subscription detail
    if is_back(msg_lower):
        data["step"] = "active_subscription_detail"
        await save_ctx(refresh_ttl=True)
        sub = await _fetch_sub()
        return WhatsAppConsoleResponse(
            reply=_render_subscription_detail_text(locale, sub)
            if sub
            else (
                _render_subscriptions_list_text(
                    locale, client.full_name, await _fetch_subs()
                )
            ),
            reply_to=admin_jid,
        )

    # Duration selection or confirm
    if msg_lower in SUBSCRIPTIONS_DURATION_MAP:
        duration_type = SUBSCRIPTIONS_DURATION_MAP[msg_lower]
        duration_label = SUBSCRIPTIONS_DURATION_LABELS.get(duration_type, duration_type)

        # Calculate new expiry date

        sub = await _fetch_sub()
        if sub is None:
            return WhatsAppConsoleResponse(
                reply=_ctx_t(
                    tenant, data, "wa.tenant.client_context.error.service_unavailable"
                ),
                reply_to=admin_jid,
            )

        from app.services.subscription_service.helpers import (
            calculate_expiration as _calc_exp,
        )

        new_expires = _calc_exp(sub.expires_at, duration_type, None)
        expires_str = new_expires.strftime("%Y-%m-%d") if new_expires else "-"

        data["temp_data"]["extend_duration_type"] = duration_type
        data["temp_data"]["extend_duration_label"] = duration_label
        data["temp_data"]["extend_new_expires"] = expires_str
        data["step"] = "active_extend_subs_confirm"
        await save_ctx(refresh_ttl=True)
        return WhatsAppConsoleResponse(
            reply=_render_extend_confirm_text(
                locale, service_name, plan_name, duration_label, expires_str
            ),
            reply_to=admin_jid,
        )

    # Confirmation
    if msg_lower.strip().lower() in ("confirmar", "confirm"):
        duration_type = data.get("temp_data", {}).get("extend_duration_type", "")
        if not duration_type or not sub_id_str:
            return WhatsAppConsoleResponse(
                reply=_ctx_t(
                    tenant, data, "wa.tenant.client_context.error.service_unavailable"
                ),
                reply_to=admin_jid,
            )

        from app.services.subscription_service.mutations import (
            renew_subscription as _renew,
        )

        try:
            renewed = await _renew(
                db,
                tenant.id,
                UUID(sub_id_str),
                duration_type,
            )
        except Exception:
            renewed = None

        if renewed is None:
            return WhatsAppConsoleResponse(
                reply=_ctx_t(
                    tenant, data, "wa.tenant.client_context.error.service_unavailable"
                ),
                reply_to=admin_jid,
            )

        # Success — return to subscriptions list
        data["step"] = "active_view_subscriptions"
        data["temp_data"].pop("extend_sub_id", None)
        data["temp_data"].pop("extend_duration_type", None)
        data["temp_data"].pop("extend_duration_label", None)
        data["temp_data"].pop("extend_new_expires", None)
        data["temp_data"].pop("extend_service_name", None)
        data["temp_data"].pop("extend_plan_name", None)
        await save_ctx(refresh_ttl=True)
        subs = await _fetch_subs()
        success_msg = _ctx_t(
            tenant,
            data,
            "wa.tenant.client_context.subscriptions.duplicate_extend_success",
        )
        list_text = _render_subscriptions_list_text(locale, client.full_name, subs)
        return WhatsAppConsoleResponse(
            reply=_with_current_screen_message(success_msg, list_text),
            reply_to=admin_jid,
        )

    # Invalid
    await save_ctx(refresh_ttl=False)
    return WhatsAppConsoleResponse(
        reply=_with_current_screen_message(
            _ctx_t(tenant, data, "wa.tenant.client_context.invalid_option"),
            _render_extend_duration_text(locale, service_name, plan_name),
        ),
        reply_to=admin_jid,
    )


# ====================================================================
# Helpers
async def handle_ctx_active_deactivate_subscription(
    msg_lower: str,
    message: str,
    data: dict,
    admin_jid: str | None,
    client: _ClientModel,
    tenant: _TenantModel,
    db: AsyncSession,
    save_ctx,
    clear_ctx,
) -> WhatsAppConsoleResponse:
    """Handle deactivate subscription confirmation screen (active client context).

    Flow: deactivate_sub_confirm → user confirms → cancel_subscription → show success → subscriptions list
    """
    locale = _ctx_locale(tenant, data)
    sub_id_str = data.get("temp_data", {}).get("selected_sub_id", "")

    from app.models.subscription import Subscription as _Sub
    from sqlalchemy import select as _select
    from sqlalchemy.orm import selectinload as _selectinload

    async def _fetch_sub():
        if not sub_id_str:
            return None
        stmt = (
            _select(_Sub)
            .options(_selectinload(_Sub.service), _selectinload(_Sub.plan))
            .where(
                _Sub.tenant_id == tenant.id,
                _Sub.id == UUID(sub_id_str),
            )
        )
        res = await db.execute(stmt)
        return res.scalar_one_or_none()

    async def _fetch_subs():
        stmt = (
            _select(_Sub)
            .options(_selectinload(_Sub.service), _selectinload(_Sub.plan))
            .where(
                _Sub.tenant_id == tenant.id,
                _Sub.client_id == client.id,
                _Sub.status == "active",
            )
            .order_by(_Sub.expires_at.asc())
        )
        res = await db.execute(stmt)
        return list(res.scalars().all())

    # Back: go to subscription detail
    if is_back(msg_lower):
        data["step"] = "active_subscription_detail"
        await save_ctx(refresh_ttl=True)
        sub = await _fetch_sub()
        return WhatsAppConsoleResponse(
            reply=_render_subscription_detail_text(locale, sub)
            if sub
            else (
                _render_subscriptions_list_text(
                    locale, client.full_name, await _fetch_subs()
                )
            ),
            reply_to=admin_jid,
        )

    # Confirmation
    if msg_lower.strip().lower() in ("confirmar", "confirm"):
        if not sub_id_str:
            return WhatsAppConsoleResponse(
                reply=_ctx_t(
                    tenant, data, "wa.tenant.client_context.error.service_unavailable"
                ),
                reply_to=admin_jid,
            )

        from app.services.subscription_service.mutations import (
            cancel_subscription as _cancel_sub,
        )

        try:
            cancelled = await _cancel_sub(db, tenant.id, UUID(sub_id_str))
        except Exception:
            cancelled = None

        if cancelled is None:
            return WhatsAppConsoleResponse(
                reply=_ctx_t(
                    tenant, data, "wa.tenant.client_context.error.service_unavailable"
                ),
                reply_to=admin_jid,
            )

        # Success — return to subscriptions list
        data["step"] = "active_view_subscriptions"
        data["temp_data"].pop("selected_sub_id", None)
        data["temp_data"].pop("selected_sub_service", None)
        data["temp_data"].pop("selected_sub_plan", None)
        await save_ctx(refresh_ttl=True)
        subs = await _fetch_subs()
        success_msg = _ctx_t(
            tenant, data, "wa.tenant.client_context.subscriptions.deactivate_success"
        )
        list_text = _render_subscriptions_list_text(locale, client.full_name, subs)
        return WhatsAppConsoleResponse(
            reply=_with_current_screen_message(success_msg, list_text),
            reply_to=admin_jid,
        )

    # Invalid
    await save_ctx(refresh_ttl=False)
    return WhatsAppConsoleResponse(
        reply=_with_current_screen_message(
            _ctx_t(tenant, data, "wa.tenant.client_context.invalid_option"),
            _ctx_t(
                tenant,
                data,
                "wa.tenant.client_context.subscriptions.deactivate_confirm",
            ),
        ),
        reply_to=admin_jid,
    )


# ====================================================================


async def _start_context_subscription(
    client: _ClientModel,
    data: dict,
    admin_jid: str | None,
    tenant: _TenantModel,
    db: AsyncSession,
    save_ctx,
    clear_ctx,
) -> WhatsAppConsoleResponse:
    """Start a subscription creation with client pre-selected.

    Clears the context shortcut and sets up the admin session to
    continue in the Tenant console subscription creation flow with
    the client already chosen.
    """
    from app.core.config import settings
    from app.core.redis_client import get_redis_manager as _get_redis

    manager = _get_redis()
    if manager is None:
        return WhatsAppConsoleResponse(
            reply=_ctx_t(
                tenant, data, "wa.tenant.client_context.error.service_unavailable"
            ),
            reply_to=admin_jid,
        )

    session_service = WhatsAppSessionService(
        connection_manager=manager,
        ttl_seconds=settings.whatsapp_session_ttl_minutes * 60,
    )

    # Determine tenant timezone for subscription start date
    _tz = timezone.utc
    try:
        from app.repositories import tenant_settings_repository

        _tz_name = await tenant_settings_repository.resolve_timezone(db, tenant.id)
        _tz = ZoneInfo(_tz_name)
    except Exception:
        pass

    phone = data.get("phone", "")
    session = await session_service.create_session(f"admin:{phone}")
    session.flow = "subscriptions"
    session.step = "create_service"
    session.temp_data = {
        "client_id": str(client.id),
        "client_name": client.full_name,
        "starts_at": datetime.now(_tz).isoformat(),
        "_from_ctx": True,
    }
    await session_service.save_session(session)

    from app.services.catalog_service import CatalogService

    catalog_service = CatalogService()
    services = await catalog_service.list_services(db, tenant.id)

    if not services:
        await session_service.clear_session(f"admin:{phone}")
        await clear_ctx()
        return WhatsAppConsoleResponse(
            reply=_ctx_t(
                tenant, data, "wa.tenant.client_context.subscription.no_services"
            ),
            reply_to=admin_jid,
        )

    PAGE_SIZE = 7
    page = 1
    total_pages = max(1, (len(services) + PAGE_SIZE - 1) // PAGE_SIZE)
    page_start = (page - 1) * PAGE_SIZE
    page_services = services[page_start : page_start + PAGE_SIZE]

    service_lines: list[str] = []
    selection_map: dict[str, str] = {}
    for i, svc in enumerate(page_services, start=page_start + 1):
        service_lines.append(f"[{i}] {svc.name}")
        selection_map[str(i)] = str(svc.id)

    session.selection_map = selection_map
    session.temp_data["service_page"] = page
    await session_service.save_session(session)

    # Keep context shortcut alive with step="subscription_active" so that
    # _handle_active_client_context can detect when the flow completes
    # and re-render the client context menu instead of the tenant main menu.
    data["step"] = "subscription_active"
    data["temp_data"]["client_id"] = str(client.id)
    data["temp_data"]["client_name"] = client.full_name
    data["temp_data"]["client_phone"] = client.phone or ""
    await save_ctx(refresh_ttl=True)
    locale = _ctx_locale(tenant, data)
    client_phone = _phone_label(client.phone or "")
    client_section = f"*Cliente:* {client.full_name}\n*Telefono:* {client_phone}\n"
    nav_lines: list[str] = []
    if page < total_pages:
        nav_lines.append(t(locale, "wa.nav.next"))
    nav_lines.append(t(locale, "wa.nav.back"))
    nav_lines.append(t(locale, "wa.nav.cancel"))
    nav = "\n".join(nav_lines)
    return WhatsAppConsoleResponse(
        reply=(
            _ctx_t(
                tenant,
                data,
                "wa.tenant.client_context.subscription.creating",
                client_name=client.full_name,
            )
            + client_section
            + "\n"
            + t(locale, "wa.tenant.client_context.subscription.service_prompt")
            + "\n\n"
            + "\n".join(service_lines)
            + "\n\n"
            + nav
        ),
        reply_to=admin_jid,
    )


# ====================================================================
# Menu renderer helpers
# ====================================================================


def _phone_label(phone: str | None) -> str:
    """Strip leading ``+`` from phone for display."""
    return (phone or "").lstrip("+")


def _client_phone_line(locale: str, phone: str | None) -> str:
    if not phone:
        return ""
    return t(locale, "wa.tenant.client_context.phone_line", phone=_phone_label(phone))


def _render_active_client_menu_text(
    locale: str,
    target_phone: str | None,
    client: _ClientModel,
) -> str:
    return t(
        locale,
        "wa.tenant.client_context.menu.active",
        client_name=client.full_name,
        phone_line=_client_phone_line(locale, target_phone or client.phone),
        status=t(locale, "wa.tenant.clients.detail.status_active"),
    )


def _render_inactive_client_menu_text(
    locale: str,
    target_phone: str | None,
    client: _ClientModel,
) -> str:
    return t(
        locale,
        "wa.tenant.client_context.menu.inactive",
        client_name=client.full_name,
        phone_line=_client_phone_line(locale, target_phone or client.phone),
        status=t(locale, "wa.tenant.clients.detail.status_inactive"),
    )


def _render_active_client_detail_text(
    locale: str,
    target_phone: str | None,
    client: _ClientModel,
) -> str:
    body = t(
        locale,
        "wa.tenant.client_context.detail.body",
        client_name=client.full_name,
        username=client.username,
        phone_line=_client_phone_line(locale, target_phone or client.phone),
        status=t(locale, "wa.tenant.clients.detail.status_active"),
    )
    return body + "\n" + t(locale, "wa.tenant.client_context.detail.options")


def _with_current_screen_message(message: str, screen_text: str) -> str:
    return f"{message}\n\n{screen_text}".strip()


def _render_inactive_client_detail_text(
    locale: str,
    target_phone: str | None,
    client: _ClientModel,
) -> str:
    body = t(
        locale,
        "wa.tenant.client_context.detail.body",
        client_name=client.full_name,
        username=client.username,
        phone_line=_client_phone_line(locale, target_phone or client.phone),
        status=t(locale, "wa.tenant.clients.detail.status_inactive"),
    )
    return body + "\n" + t(locale, "wa.tenant.client_context.inactive.detail.options")


async def _reactivate_context_client(
    client: _ClientModel,
    data: dict,
    admin_jid: str | None,
    tenant: _TenantModel,
    db: AsyncSession,
    save_ctx,
    clear_ctx,
) -> WhatsAppConsoleResponse:
    locale = _ctx_locale(tenant, data)
    target_phone = data.get("temp_data", {}).get("target_phone")
    client_id = UUID(str(client.id))

    try:
        client_service = ClientService()
        updated = await client_service.activate_client(db, tenant.id, client_id)
    except UserFacingError as exc:
        await clear_ctx()
        return WhatsAppConsoleResponse(
            reply=translate_error(_ctx_locale(tenant, data), exc),
            reply_to=admin_jid,
        )
    except Exception:
        logger.exception("failed to reactivate client")
        await clear_ctx()
        return WhatsAppConsoleResponse(
            reply=_ctx_t(
                tenant,
                data,
                "wa.tenant.client_context.inactive.reactivate_error",
                exc="",
            ),
            reply_to=admin_jid,
        )

    if updated is None:
        await clear_ctx()
        return WhatsAppConsoleResponse(
            reply=_ctx_t(
                tenant, data, "wa.tenant.client_context.error.client_not_found"
            ),
            reply_to=admin_jid,
        )

    data["temp_data"]["client_id"] = str(updated.id)
    data["temp_data"]["menu_variant"] = "existing_active"
    data["temp_data"]["target_state"] = "existing_active"
    data["step"] = "active_menu"
    await save_ctx(refresh_ttl=True)
    return WhatsAppConsoleResponse(
        reply=_with_current_screen_message(
            _ctx_t(
                tenant,
                data,
                "wa.tenant.client_context.inactive.reactivate_success",
                client_name=updated.full_name,
            ),
            _render_active_client_menu_text(locale, target_phone, updated),
        ),
        reply_to=admin_jid,
    )


async def render_initial_context_menu(
    *,
    db: AsyncSession,
    tenant: _TenantModel,
    target_phone: str | None,
    target_lid: str | None,
    target_jid: str | None,
) -> tuple[str, dict[str, str]]:
    """Render the initial contextual menu based on target state.

    Queries the target identity state (existing client, blocked, unregistered)
    and returns the appropriate i18n-backed menu with metadata for the
    context payload.

    Returns ``(rendered_text, metadata_dict)``.
    """
    settings = getattr(tenant, "settings", None)
    locale = getattr(settings, "locale", None) or "es"
    identity = _phone_label(target_phone)

    # ── Check if target is an existing client ────────────────────────
    client = None
    if target_phone:
        client = await clients_repository.get_client_by_tenant_phone(
            db, tenant.id, target_phone
        )
    if client is not None:
        variant = "existing_active" if client.is_active else "existing_inactive"
        render_menu = (
            _render_active_client_menu_text
            if client.is_active
            else _render_inactive_client_menu_text
        )
        return render_menu(locale, target_phone, client), {
            "target_state": variant,
            "menu_variant": variant,
            "client_id": str(client.id),
            "identity": identity,
            "locale": locale,
        }

    # ── Check if target is a blocked identity ────────────────────────
    block = await blocked_clients_repository.find_active(
        db,
        tenant.id,
        phone=target_phone,
        whatsapp_lid=None,
    )
    if block is not None:
        key = (
            "wa.tenant.client_context.menu.blocked_with_phone"
            if target_phone
            else "wa.tenant.client_context.menu.blocked_lid_only"
        )
        return t(locale, key, identity=identity, client_name="", status=""), {
            "target_state": "unregistered_blocked",
            "menu_variant": "blocked",
            "identity": identity,
            "locale": locale,
        }

    # ── Unregistered unblocked target ────────────────────────────────
    key = (
        "wa.tenant.client_context.menu.unregistered_with_phone"
        if target_phone
        else "wa.tenant.client_context.menu.unregistered_lid_only"
    )
    return t(locale, key, identity=identity, client_name="", status=""), {
        "target_state": "unregistered_unblocked",
        "menu_variant": "unregistered",
        "identity": identity,
        "locale": locale,
    }


__all__ = [
    "handle_ctx_creating_first",
    "handle_ctx_creating_phone",
    "handle_ctx_creating_name",
    "handle_ctx_creating_username",
    "handle_ctx_creating_password_choice",
    "handle_ctx_creating_password_manual",
    "handle_ctx_creating_confirm",
    "handle_ctx_active_client_menu",
    "handle_ctx_active_detail",
    "handle_ctx_active_edit_field",
    "handle_ctx_active_edit_value",
    "handle_ctx_active_deactivate_confirm",
    "handle_ctx_active_view_subscriptions",
    "handle_ctx_view_subscription_detail",
    "handle_ctx_active_extend_subscription",
    "handle_ctx_active_deactivate_subscription",
    "handle_ctx_inactive_client_menu",
    "handle_ctx_inactive_detail",
    "handle_ctx_inactive_edit_field",
    "handle_ctx_inactive_edit_value",
    "handle_ctx_inactive_delete_confirm",
    "render_initial_context_menu",
]
