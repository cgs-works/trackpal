"""Mode persistence and ambiguity handling for WhatsApp console routing."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.i18n import t
from app.core.redis_client import RedisConnectionManager
from app.schemas.whatsapp import WhatsAppConsoleResponse
from app.services.whatsapp_navigation import is_cancel, is_back
from app.services.whatsapp_session_service import WhatsAppSessionService

MODE_KEY_PREFIX = "wa:mode:"
MODE_TTL = 300


async def _get_mode(manager: RedisConnectionManager, phone: str) -> str | None:
    key = f"{MODE_KEY_PREFIX}{phone}"

    async def _get(client: Any) -> str | None:
        raw = await client.get(key)
        if raw is None:
            return None
        return raw.decode() if isinstance(raw, bytes) else raw

    return await manager.execute("get_mode", _get)


async def _set_mode(manager: RedisConnectionManager, phone: str, mode: str) -> None:
    key = f"{MODE_KEY_PREFIX}{phone}"

    async def _set(client: Any) -> None:
        await client.set(key, mode, ex=MODE_TTL)

    await manager.execute("set_mode", _set)


async def _clear_mode(manager: RedisConnectionManager, phone: str) -> None:
    mode_key = f"{MODE_KEY_PREFIX}{phone}"

    async def _del(client: Any) -> None:
        await client.delete(mode_key)

    await manager.execute("clear_mode", _del)


async def _handle_ambiguity(
    phone: str,
    message: str,
    instance: str,
    manager: RedisConnectionManager,
    db: AsyncSession,
    tenant: Any,
    client: Any,
    close_jid: str | None = None,
) -> WhatsAppConsoleResponse:
    """Handle phone matching both tenant admin and client."""
    from app.api.v1.endpoints.integrations.console import _tl
    from app.api.v1.endpoints.integrations.console_handlers import (
        _handle_client_console,
        _handle_tenant_console,
    )

    locale = _tl(tenant)
    msg = message.strip()
    msg_lower = msg.lower()

    if is_back(msg):
        prompt = t(locale, "wa.client.mode_prompt")
        return WhatsAppConsoleResponse(reply=prompt)

    if is_cancel(msg):
        await _clear_mode(manager, phone)
        cleanup_svc = WhatsAppSessionService(
            connection_manager=manager,
            ttl_seconds=settings.whatsapp_session_ttl_minutes * 60,
        )
        await cleanup_svc.clear_session(f"admin:{phone}")
        await cleanup_svc.clear_session(f"client:{phone}")
        resp = WhatsAppConsoleResponse(
            reply=t(locale, "wa.client.mode_exit"), status="closed"
        )
        if close_jid:
            resp.close_jid = close_jid
            resp.reply_to = close_jid
        return resp

    stored_mode = await _get_mode(manager, phone)

    if msg_lower in ("codigo", "código", "code"):
        await _set_mode(manager, phone, "tenant")
        return await _handle_tenant_console(
            phone=phone,
            message=message,
            instance=instance,
            manager=manager,
            db=db,
            close_jid=close_jid,
        )

    if msg_lower in ("menu", "/menu"):
        if stored_mode == "tenant":
            return await _handle_tenant_console(
                phone=phone,
                message=message,
                instance=instance,
                manager=manager,
                db=db,
                close_jid=close_jid,
            )
        if stored_mode == "client":
            return await _handle_client_console(
                phone=phone,
                message=message,
                instance=instance,
                manager=manager,
                db=db,
                identity=_client_identity(client, tenant),
                locale=locale,
                close_jid=close_jid,
            )

        await _clear_mode(manager, phone)
        prompt = t(locale, "wa.client.mode_prompt")
        return WhatsAppConsoleResponse(reply=prompt)

    if stored_mode == "tenant":
        return await _handle_tenant_console(
            phone=phone,
            message=message,
            instance=instance,
            manager=manager,
            db=db,
            close_jid=close_jid,
        )
    if stored_mode == "client":
        return await _handle_client_console(
            phone=phone,
            message=message,
            instance=instance,
            manager=manager,
            db=db,
            identity=_client_identity(client, tenant),
            locale=locale,
            close_jid=close_jid,
        )

    if msg == "1":
        await _set_mode(manager, phone, "tenant")
        return await _handle_tenant_console(
            phone=phone,
            message="",
            instance=instance,
            manager=manager,
            db=db,
            close_jid=close_jid,
        )
    if msg == "2":
        await _set_mode(manager, phone, "client")
        return await _handle_client_console(
            phone=phone,
            message="",
            instance=instance,
            manager=manager,
            db=db,
            identity=_client_identity(client, tenant),
            locale=locale,
            close_jid=close_jid,
        )

    return WhatsAppConsoleResponse(reply=t(locale, "wa.client.mode_prompt"))


def _client_identity(client: Any, tenant: Any) -> dict[str, str]:
    return {
        "user_id": str(client.owner_user_id),
        "role": "client",
        "username": client.username,
        "client_id": str(client.id),
        "tenant_id": str(tenant.id),
    }
