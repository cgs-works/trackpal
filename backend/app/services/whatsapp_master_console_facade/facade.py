"""Orchestrator for the WhatsApp Master Console.

Handles login flow, lockout, auth session verification, logout
orchestration, and delegates to ``WhatsAppConsoleService`` for
authenticated CRUD operations.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.phone import normalize_phone
from app.services.evolution_client import evolution_client

from . import constants as c
from . import login_flow as lf

logger = logging.getLogger(__name__)


class WhatsAppMasterConsoleFacade:
    """Orchestrate auth-gated WhatsApp Master Console access.

    1. Checks lockout state → returns lockout reply when locked.
    2. Checks auth session → delegates to ``WhatsAppConsoleService``
       when an active master session exists.
    3. Otherwise runs the conversational login flow using the
       existing ``WhatsAppSessionService`` for multi-step state.
    """

    def __init__(
        self,
        console_service,
        session_service,
        auth_session_service,
        tenant_service: Any | None,
    ) -> None:
        self._console_service = console_service
        self._session_service = session_service
        self._auth_session_service = auth_session_service
        self._tenant_service = tenant_service

    # -- Public API --------------------------------------------------------

    # Assigned from login_flow module
    _run_login_flow = lf._run_login_flow
    _handle_username_step = lf._handle_username_step
    _handle_password_step = lf._handle_password_step
    _record_failure_and_check_lockout = lf._record_failure_and_check_lockout
    _compute_remaining_minutes = staticmethod(lf._compute_remaining_minutes)

    async def process_message(
        self,
        phone: str,
        message: str,
        *,
        instance: str | None = None,
        db: AsyncSession | None = None,
    ) -> str:
        """Process a WhatsApp message through the auth-gated console.

        Args:
            phone: Normalised phone number of the sender.
            message: Text of the WhatsApp message.
            instance: Optional Evolution API instance name for context.
                      Used to close the chat session on logout.
            db: Database session (required for credential verification).

        Returns:
            Reply text that n8n will send through Evolution API.
        """
        # 1. Check lockout
        lock_state = await self._auth_session_service.get_lock_state(phone)
        if lock_state is not None and lock_state.is_locked:
            remaining = self._compute_remaining_minutes(lock_state)
            return c.LOCKOUT_TEMPLATE.format(minutes=remaining)

        # 2. Check auth session
        auth_session = await self._auth_session_service.get_auth_session(phone)
        if auth_session is not None and auth_session.role == "master":
            msg_stripped = message.strip()

            # 2a. Contextual "0" handling
            if msg_stripped == "0":
                conv_session = await self._session_service.get_session(phone)
                has_active_flow = conv_session is not None and bool(conv_session.flow)

                if has_active_flow:
                    await self._auth_session_service.touch_auth_session(phone)
                    return await self._console_service.process_message(
                        phone=phone,
                        message=message,
                        is_master=True,
                        session_service=self._session_service,
                        tenant_service=self._tenant_service,
                    )
                elif self._session_service.used_backup:
                    await self._auth_session_service.touch_auth_session(phone)
                    return self._console_service._with_main_menu(
                        "🚫 Operación cancelada."
                    )
                else:
                    return await self._perform_logout(
                        phone=phone,
                        instance=instance,
                    )

            # 2b. Normal authenticated message
            await self._auth_session_service.touch_auth_session(phone)
            return await self._console_service.process_message(
                phone=phone,
                message=message,
                is_master=True,
                session_service=self._session_service,
                tenant_service=self._tenant_service,
            )

        # 3. No auth session → run login flow
        return await self._run_login_flow(phone, message, db)

    # ------------------------------------------------------------------
    # Logout
    # ------------------------------------------------------------------

    async def _perform_logout(self, phone: str, instance: str | None) -> str:
        """Perform a full logout: clear Redis keys and optionally close Evolution session."""
        await self._auth_session_service.clear_auth_session(phone)
        await self._session_service.clear_session(phone)

        if instance is not None:
            digits = normalize_phone(phone)
            if digits:
                remote_jid = f"{digits}@s.whatsapp.net"
                try:
                    await evolution_client.close_chat_session(
                        instance=instance,
                        remote_jid=remote_jid,
                    )
                except httpx.HTTPError:
                    logger.warning(
                        "Evolution API call failed during logout for phone=%s instance=%s",
                        phone,
                        instance,
                        exc_info=True,
                    )
            else:
                logger.warning(
                    "Cannot close Evolution session: normalize_phone returned no digits for phone=%s",
                    phone,
                )

        return c.LOGOUT_CONFIRMATION
