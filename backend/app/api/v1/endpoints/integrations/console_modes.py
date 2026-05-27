"""Mode persistence and ambiguity handling for WhatsApp console routing."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.redis_client import RedisConnectionManager
from app.core.i18n import t
from app.schemas.whatsapp import WhatsAppConsoleResponse
from app.services.whatsapp_session_service import WhatsAppSessionService

MODE_KEY_PREFIX = "wa:mode:"
MODE_PENDING_KEY_PREFIX = "wa:mode:pending:"
MODE_TTL = 900


async def _get_mode(redis_manager: RedisConnectionManager, phone: str) -> str | None:
    key = f"{MODE_KEY_PREFIX}{phone}"

    async def _get(client: Any) -> str | None:
        raw = await client.get(key)
        if raw is None:
            return None
        return raw.decode() if isinstance(raw, bytes) else raw

    return await redis_manager.execute("get_mode", _get)


async def _set_mode(
    redis_manager: RedisConnectionManager, phone: str, mode: str
) -> None:
    key = f"{MODE_KEY_PREFIX}{phone}"

    async def _set(client: Any) -> None:
        await client.set(key, mode, ex=MODE_TTL)

    await redis_manager.execute("set_mode", _set)


async def _get_mode_pending(redis_manager: RedisConnectionManager, phone: str) -> bool:
    key = f"{MODE_PENDING_KEY_PREFIX}{phone}"

    async def _get(client: Any) -> bool:
        raw = await client.get(key)
        if raw is None:
            return False
        value = raw.decode() if isinstance(raw, bytes) else str(raw)
        return value == "1"

    return await redis_manager.execute("get_mode_pending", _get)


async def _set_mode_pending(redis_manager: RedisConnectionManager, phone: str) -> None:
    key = f"{MODE_PENDING_KEY_PREFIX}{phone}"

    async def _set(client: Any) -> None:
        await client.set(key, "1", ex=MODE_TTL)

    await redis_manager.execute("set_mode_pending", _set)


async def _clear_mode(redis_manager: RedisConnectionManager, phone: str) -> None:
    mode_key = f"{MODE_KEY_PREFIX}{phone}"
    pending_key = f"{MODE_PENDING_KEY_PREFIX}{phone}"

    async def _del(client: Any) -> None:
        await client.delete(mode_key)
        await client.delete(pending_key)

    await redis_manager.execute("clear_mode", _del)


async def _handle_ambiguity(
    phone: str,
    message: str,
    instance: str,
    manager: RedisConnectionManager,
    db: AsyncSession,
    tenant: Any,
    client: Any,
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

    if msg_lower in ("0", "salir"):
        await _clear_mode(manager, phone)
        cleanup_svc = WhatsAppSessionService(
            connection_manager=manager,
            ttl_seconds=settings.whatsapp_session_ttl_minutes * 60,
        )
        await cleanup_svc.clear_session(f"admin:{phone}")
        await cleanup_svc.clear_session(f"client:{phone}")
        return WhatsAppConsoleResponse(
            reply=t(locale, "wa.client.mode_exit"), status="closed"
        )

    stored_mode = await _get_mode(manager, phone)
    mode_pending = await _get_mode_pending(manager, phone)

    if msg_lower in ("menu", "/menu"):
        if stored_mode == "tenant":
            return await _handle_tenant_console(
                phone=phone,
                message=message,
                instance=instance,
                manager=manager,
                db=db,
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
            )

        await _clear_mode(manager, phone)
        prompt = t(locale, "wa.client.mode_prompt")
        return WhatsAppConsoleResponse(reply=prompt)

    if stored_mode == "tenant":
        if mode_pending and msg == "1":
            await _clear_mode(manager, phone)
            await _set_mode(manager, phone, "tenant")
            return await _handle_tenant_console(
                phone=phone,
                message="",
                instance=instance,
                manager=manager,
                db=db,
            )
        return await _handle_tenant_console(
            phone=phone,
            message=message,
            instance=instance,
            manager=manager,
            db=db,
        )
    if stored_mode == "client":
        if mode_pending and msg == "1":
            await _clear_mode(manager, phone)
            await _set_mode(manager, phone, "client")
            return await _handle_client_console(
                phone=phone,
                message="",
                instance=instance,
                manager=manager,
                db=db,
                identity=_client_identity(client, tenant),
                locale=locale,
            )
        return await _handle_client_console(
            phone=phone,
            message=message,
            instance=instance,
            manager=manager,
            db=db,
            identity=_client_identity(client, tenant),
            locale=locale,
        )

    if msg == "1":
        await _set_mode(manager, phone, "tenant")
        await _set_mode_pending(manager, phone)
        return WhatsAppConsoleResponse(reply=t(locale, "wa.client.mode_confirm_tenant"))
    if msg == "2":
        await _set_mode(manager, phone, "client")
        await _set_mode_pending(manager, phone)
        return WhatsAppConsoleResponse(reply=t(locale, "wa.client.mode_confirm_client"))

    return WhatsAppConsoleResponse(reply=t(locale, "wa.client.mode_prompt"))


def _client_identity(client: Any, tenant: Any) -> dict[str, str]:
    return {
        "user_id": str(client.owner_user_id),
        "role": "client",
        "username": client.username,
        "client_id": str(client.id),
        "tenant_id": str(tenant.id),
    }
