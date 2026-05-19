"""Orchestrator for the WhatsApp Tenant Admin Console.

Handles tenant identification by phone, tenant context resolution,
top-level session exit, and delegates to
``WhatsAppTenantConsoleService`` for all authenticated tenant
operations.

This facade follows the same orchestration pattern as
``WhatsAppMasterConsoleFacade`` but omits:
- Credential-based login flows (tenant admins are auto-authed by phone)
- Lockout / ``WhatsAppAuthSessionService``
- Evolution-chat close on exit
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.auth_service import AuthService
from app.services.tenant_service import TenantService
from app.services.whatsapp_session_service import WhatsAppSessionService

logger = logging.getLogger(__name__)

# ====================================================================
# Reply templates (Spanish)
# ====================================================================

NOT_TENANT_REPLY = (
    "❌ Acceso denegado. Esta consola solo está disponible "
    "para administradores de tenant."
)

INACTIVE_TENANT_REPLY = (
    "❌ Tu cuenta de administrador está desactivada. "
    "Contacta al Master de Trackpal para más información."
)

TENANT_NOT_FOUND_REPLY = (
    "❌ No se encontró un tenant asociado a tu cuenta. "
    "Contacta al Master de Trackpal."
)

GOODBYE_REPLY = (
    "👋 *Sesión cerrada*\n\n"
    "Has salido de la consola de administración.\n\n"
    "Escribe *menu* para volver a entrar."
)


class WhatsAppTenantConsoleFacade:
    """Orchestrate phone-based tenant admin WhatsApp access.

    1. Validates that the caller is a tenant admin (defense in depth).
    2. Resolves the active tenant record from the caller's identity.
    3. Handles top-level ``0`` to exit the console.
    4. Delegates all other messages to ``WhatsAppTenantConsoleService``
       with the resolved ``tenant_id``.
    """

    def __init__(
        self,
        console_service: Any,
        session_service: WhatsAppSessionService,
        tenant_service: TenantService | None = None,
    ) -> None:
        self._console_service = console_service
        self._session_service = session_service
        self._tenant_service = tenant_service or TenantService()
        self._auth_service = AuthService()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def process_message(
        self,
        phone: str,
        message: str,
        identity: dict[str, Any],
        *,
        db: AsyncSession | None = None,
    ) -> str:
        """Process a WhatsApp message for a tenant admin.

        Args:
            phone: Normalised phone number of the sender.
            message: Text of the WhatsApp message.
            identity: Pre-resolved identity dict from
                ``AuthService.identify_by_phone()`` with keys
                ``user_id``, ``role``, ``username``.
            db: Database session (required for tenant resolution).

        Returns:
            Reply text that n8n will send through Evolution API.
        """
        # 1. Defense in depth — verify tenant role
        role = identity.get("role", "")
        if role != "tenant":
            return NOT_TENANT_REPLY

        user_id = identity.get("user_id")
        if user_id is None:
            return NOT_TENANT_REPLY

        # 2. Resolve the active tenant record
        tenant_id: UUID | None = None
        if db is not None:
            tenant = await self._tenant_service.get_tenant(db, UUID(str(user_id)))
            if tenant is None:
                return TENANT_NOT_FOUND_REPLY
            if not tenant.is_active:
                return INACTIVE_TENANT_REPLY
            tenant_id = tenant.id

        # 3. Top-level "0" handling
        msg = message.strip()
        if msg == "0":
            conv_session = await self._session_service.get_session(
                self._admin_phone_key(phone)
            )
            has_active_flow = conv_session is not None and bool(conv_session.flow)

            if has_active_flow:
                # Inside active flow → cancel (delegate to service)
                return await self._console_service.process_message(
                    phone=phone,
                    message=message,
                    session_service=self._session_service,
                )
            elif self._session_service.used_backup:
                # Failover: session may be missing on backup
                return self._console_service._with_main_menu(
                    "🚫 Operación cancelada."
                )
            else:
                # Top-level → clear session and goodbye
                await self._session_service.clear_session(
                    self._admin_phone_key(phone)
                )
                return GOODBYE_REPLY

        # 4. Delegate to the tenant console service
        return await self._console_service.process_message(
            phone=phone,
            message=message,
            tenant_id=tenant_id if db is not None else None,
            user_id=UUID(str(user_id)),
            db=db,
            session_service=self._session_service,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _admin_phone_key(phone: str) -> str:
        """Return the logical phone key for tenant session isolation.

        Uses the ``admin:{phone}`` prefix so tenant conversation state
        lives under ``session:admin:{phone}``, isolated from the Master
        Console namespace.
        """
        return f"admin:{phone}"
