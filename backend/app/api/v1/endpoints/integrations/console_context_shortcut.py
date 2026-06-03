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
    return getattr(tenant, "locale", "es") or "es"


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
            reply=_ctx_t(tenant, data, "wa.tenant.client_context.create.name_invalid", exc=str(exc)),
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
            reply=_ctx_t(tenant, data, "wa.tenant.client_context.create.username_empty"),
            reply_to=admin_jid,
        )

    try:
        local_username = validate_client_local_username(stripped)
    except Exception as exc:
        return WhatsAppConsoleResponse(
            reply=_ctx_t(tenant, data, "wa.tenant.client_context.create.username_invalid", exc=str(exc)),
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
            reply=_ctx_t(tenant, data, "wa.tenant.client_context.create.password_manual_prompt"),
            reply_to=admin_jid,
        )

    return WhatsAppConsoleResponse(
        reply=_ctx_t(tenant, data, "wa.tenant.client_context.create.password_choice_invalid"),
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
            reply=_ctx_t(tenant, data, "wa.tenant.client_context.create.password_too_short"),
            reply_to=admin_jid,
        )

    data["temp_data"]["password"] = password
    data["temp_data"]["password_mode"] = "manual"
    data["step"] = "creating_confirm"
    return WhatsAppConsoleResponse(reply=_creation_summary(tenant, data), reply_to=admin_jid)


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
            reply=_ctx_t(tenant, data, "wa.tenant.client_context.create.confirm_invalid") + "\n\n" + summary,
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

    Menu:
    1 Ver detalle del cliente
    2 Crear suscripcion
    0 Cerrar contexto
    """
    if msg_lower == "1":
        detail = _ctx_t(
            tenant, data, "wa.tenant.client_context.detail.body",
            client_name=client.full_name,
            username=client.username,
            phone=client.phone or "--",
            status="Activo",
        )
        data["step"] = "active_detail"
        data["temp_data"]["client_id"] = str(client.id)
        await save_ctx(refresh_ttl=True)
        return WhatsAppConsoleResponse(
            reply=detail + "\n\n" + _ctx_t(tenant, data, "wa.tenant.client_context.detail.options"),
            reply_to=admin_jid,
        )

    if msg_lower == "2":
        return await _start_context_subscription(
            client, data, admin_jid, tenant, db, save_ctx, clear_ctx
        )

    # Invalid input — show menu
    await save_ctx(refresh_ttl=False)
    return WhatsAppConsoleResponse(
        reply=_ctx_t(tenant, data, "wa.tenant.client_context.active.invalid_option", client_name=client.full_name),
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
    if is_back(msg_lower):
        data["step"] = "active_menu"
        await save_ctx(refresh_ttl=True)
        return WhatsAppConsoleResponse(
            reply=_ctx_t(tenant, data, "wa.tenant.client_context.active.menu_text", client_name=client.full_name),
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
            reply=_ctx_t(tenant, data, "wa.tenant.client_context.deactivate.confirm", client_name=client.full_name),
            reply_to=admin_jid,
        )

    await save_ctx(refresh_ttl=False)
    return WhatsAppConsoleResponse(
        reply=_ctx_t(tenant, data, "wa.tenant.client_context.detail.invalid_option"),
        reply_to=admin_jid,
    )


async def handle_ctx_active_edit_field(
    msg_lower: str,
    message: str,
    data: dict,
    admin_jid: str | None,
    tenant: _TenantModel,
) -> WhatsAppConsoleResponse | None:
    """Handle field selection for active client edit."""
    if msg_lower == "9":
        data["step"] = "active_detail"
        return WhatsAppConsoleResponse(
            reply=_ctx_t(tenant, data, "wa.tenant.client_context.detail.header"),
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
        await clear_ctx()
        return WhatsAppConsoleResponse(
            reply=f"{translate_error(_ctx_locale(tenant, data), exc)}",
            reply_to=admin_jid,
        )
    except Exception as exc:
        await clear_ctx()
        return WhatsAppConsoleResponse(
            reply=_ctx_t(tenant, data, "wa.tenant.client_context.edit.update_error", exc=str(exc)),
            reply_to=admin_jid,
        )

    if client is None:
        await clear_ctx()
        return WhatsAppConsoleResponse(
            reply=_ctx_t(tenant, data, "wa.tenant.client_context.error.client_not_found"),
            reply_to=admin_jid,
        )

    data["temp_data"].pop("edit_field", None)
    data["step"] = "active_detail"
    await save_ctx(refresh_ttl=True)
    return WhatsAppConsoleResponse(
        reply=_ctx_t(tenant, data, "wa.tenant.client_context.edit.updated_success", client_name=client.full_name),
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
    stripped = message.strip().upper()
    if stripped not in ("CONFIRMAR", "CONFIRM"):
        return WhatsAppConsoleResponse(
            reply=_ctx_t(tenant, data, "wa.tenant.client_context.deactivate.prompt_again"),
            reply_to=admin_jid,
        )

    client_id = UUID(data["temp_data"]["client_id"])
    try:
        client_service = ClientService()
        client = await client_service.deactivate_client(db, tenant.id, client_id)
    except Exception as exc:
        await clear_ctx()
        return WhatsAppConsoleResponse(
            reply=_ctx_t(tenant, data, "wa.tenant.client_context.deactivate.error", exc=str(exc)),
            reply_to=admin_jid,
        )

    if client is None:
        await clear_ctx()
        return WhatsAppConsoleResponse(
            reply=_ctx_t(tenant, data, "wa.tenant.client_context.error.client_not_found"),
            reply_to=admin_jid,
        )

    # Keep context alive so subsequent ``0`` closes target session
    data["temp_data"]["menu_variant"] = "existing_inactive"
    data["temp_data"]["target_state"] = "existing_inactive"
    data["step"] = "inactive_menu"
    await save_ctx(refresh_ttl=True)
    return WhatsAppConsoleResponse(
        reply=_ctx_t(tenant, data, "wa.tenant.client_context.deactivate.success", client_name=client.full_name),
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
    1 Reactivar
    2 Editar datos
    3 Eliminar
    0 Cerrar contexto
    """
    if msg_lower == "1":
        client_id = UUID(str(client.id))
        try:
            client_service = ClientService()
            updated = await client_service.activate_client(db, tenant.id, client_id)
        except Exception as exc:
            await clear_ctx()
            return WhatsAppConsoleResponse(
                reply=_ctx_t(tenant, data, "wa.tenant.client_context.inactive.reactivate_error", exc=str(exc)),
                reply_to=admin_jid,
            )
        if updated is None:
            await clear_ctx()
            return WhatsAppConsoleResponse(
                reply=_ctx_t(tenant, data, "wa.tenant.client_context.error.client_not_found"),
                reply_to=admin_jid,
            )
        # Keep context alive so subsequent ``0`` closes target session
        data["temp_data"]["client_id"] = str(updated.id)
        data["temp_data"]["menu_variant"] = "existing_active"
        data["temp_data"]["target_state"] = "existing_active"
        data["step"] = "active_menu"
        await save_ctx(refresh_ttl=True)
        return WhatsAppConsoleResponse(
            reply=_ctx_t(tenant, data, "wa.tenant.client_context.inactive.reactivate_success", client_name=updated.full_name),
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
        data["step"] = "inactive_delete_confirm"
        data["temp_data"]["client_id"] = str(client.id)
        await save_ctx(refresh_ttl=True)
        return WhatsAppConsoleResponse(
            reply=_ctx_t(tenant, data, "wa.tenant.client_context.inactive.delete_confirm", client_name=client.full_name),
            reply_to=admin_jid,
        )

    await save_ctx(refresh_ttl=False)
    return WhatsAppConsoleResponse(
        reply=_ctx_t(tenant, data, "wa.tenant.client_context.inactive.invalid_option", client_name=client.full_name),
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
        data["step"] = "inactive_menu"
        return WhatsAppConsoleResponse(
            reply=_ctx_t(tenant, data, "wa.tenant.client_context.inactive.menu_text", client_name=client.full_name),
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
    field = data["temp_data"].get("edit_field", "")
    new_value = message.strip()
    client_id = UUID(data["temp_data"]["client_id"])

    from app.schemas.client import ClientUpdate

    payload = ClientUpdate(**{field: new_value})
    try:
        client_service = ClientService()
        client = await client_service.update_client(db, tenant.id, client_id, payload)
    except UserFacingError as exc:
        await clear_ctx()
        return WhatsAppConsoleResponse(
            reply=f"{translate_error(_ctx_locale(tenant, data), exc)}",
            reply_to=admin_jid,
        )
    except Exception as exc:
        await clear_ctx()
        return WhatsAppConsoleResponse(
            reply=_ctx_t(tenant, data, "wa.tenant.client_context.edit.update_error", exc=str(exc)),
            reply_to=admin_jid,
        )

    if client is None:
        await clear_ctx()
        return WhatsAppConsoleResponse(
            reply=_ctx_t(tenant, data, "wa.tenant.client_context.error.client_not_found"),
            reply_to=admin_jid,
        )

    # Keep context alive so subsequent ``0`` closes target session
    data["temp_data"].pop("edit_field", None)
    data["step"] = "inactive_menu"
    await save_ctx(refresh_ttl=True)
    return WhatsAppConsoleResponse(
        reply=_ctx_t(tenant, data, "wa.tenant.client_context.edit.updated_success", client_name=client.full_name),
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
    stripped = message.strip().upper()
    if stripped not in ("CONFIRMAR", "CONFIRM"):
        return WhatsAppConsoleResponse(
            reply=_ctx_t(tenant, data, "wa.tenant.client_context.inactive.delete_prompt_again"),
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
            reply=_ctx_t(tenant, data, "wa.tenant.client_context.inactive.delete_error", exc=str(exc)),
            reply_to=admin_jid,
        )

    if not deleted:
        await clear_ctx()
        return WhatsAppConsoleResponse(
            reply=_ctx_t(tenant, data, "wa.tenant.client_context.inactive.delete_error", exc=""),
            reply_to=admin_jid,
        )

    # Client deleted — transition context to unregistered target
    data["temp_data"]["menu_variant"] = "unregistered"
    data["temp_data"]["target_state"] = "unregistered_unblocked"
    data["step"] = "menu"
    await save_ctx(refresh_ttl=True)
    return WhatsAppConsoleResponse(
        reply=_ctx_t(tenant, data, "wa.tenant.client_context.inactive.delete_success", client_name=client_name),
        reply_to=admin_jid,
    )


# ====================================================================
# Helpers
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
            reply=_ctx_t(tenant, data, "wa.tenant.client_context.error.service_unavailable"),
            reply_to=admin_jid,
        )

    session_service = WhatsAppSessionService(
        connection_manager=manager,
        ttl_seconds=settings.whatsapp_session_ttl_minutes * 60,
    )

    phone = data.get("phone", "")
    session = await session_service.create_session(f"admin:{phone}")
    session.flow = "subscriptions"
    session.step = "create_service"
    session.temp_data = {
        "client_id": str(client.id),
        "client_name": client.full_name,
    }
    await session_service.save_session(session)

    from app.services.catalog_service import CatalogService

    catalog_service = CatalogService()
    services = await catalog_service.list_services(db, tenant.id)

    if not services:
        await session_service.clear_session(f"admin:{phone}")
        await clear_ctx()
        return WhatsAppConsoleResponse(
            reply=_ctx_t(tenant, data, "wa.tenant.client_context.subscription.no_services"),
            reply_to=admin_jid,
        )

    service_lines: list[str] = []
    selection_map: dict[str, str] = {}
    for i, svc in enumerate(services, start=1):
        service_lines.append(f"{i} {svc.name}")
        selection_map[str(i)] = str(svc.id)

    session.selection_map = selection_map
    await session_service.save_session(session)

    await clear_ctx()
    locale = _ctx_locale(tenant, data)
    return WhatsAppConsoleResponse(
        reply=_ctx_t(tenant, data, "wa.tenant.client_context.subscription.creating", client_name=client.full_name)
        + "Seleccione un *servicio*:\n\n"
        + "\n".join(service_lines)
        + "\n\n0 "
        + t(locale, "wa.tenant.cancelled"),
        reply_to=admin_jid,
    )


# ====================================================================
# Menu renderer helpers
# ====================================================================


def _phone_label(phone: str | None) -> str:
    """Strip leading ``+`` from phone for display."""
    return (phone or "").lstrip("+")


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
    locale = getattr(tenant, "locale", None) or "es"
    identity = _phone_label(target_phone)

    # ── Check if target is an existing client ────────────────────────
    client = None
    if target_phone:
        client = await clients_repository.get_client_by_tenant_phone(
            db, tenant.id, target_phone
        )
    if client is not None:
        status_key = (
            "wa.tenant.clients.detail.status_active"
            if client.is_active
            else "wa.tenant.clients.detail.status_inactive"
        )
        key = (
            "wa.tenant.client_context.menu.active"
            if client.is_active
            else "wa.tenant.client_context.menu.inactive"
        )
        variant = "existing_active" if client.is_active else "existing_inactive"
        return t(
            locale,
            key,
            identity=identity,
            client_name=client.full_name,
            status=t(locale, status_key),
        ), {
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
    "handle_ctx_inactive_client_menu",
    "handle_ctx_inactive_edit_field",
    "handle_ctx_inactive_edit_value",
    "handle_ctx_inactive_delete_confirm",
    "render_initial_context_menu",
]
