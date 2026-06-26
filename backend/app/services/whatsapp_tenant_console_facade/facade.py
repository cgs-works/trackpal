"""Orchestrator for the WhatsApp Tenant Admin Console.

Handles tenant identification by phone, tenant context resolution,
top-level session exit, and delegates to
``WhatsAppTenantConsoleService`` for all authenticated tenant
operations.

This facade follows the same orchestration pattern as
``WhatsAppMasterConsoleFacade`` but omits:
- Credential-based login flows (tenant admins are auto-authed by phone)
- Lockout / ``WhatsAppAuthSessionService``
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.i18n import t as _t
from app.repositories import tenant_settings_repository
from app.services.auth_service import AuthService
from app.services.tenant_service import TenantService
from app.services.whatsapp_session_service import WhatsAppSessionService

logger = logging.getLogger(__name__)

# ====================================================================
# Reply templates
# ====================================================================

# Non-tenant callers (master, client roles) — keep fixed Spanish per plan.
NOT_TENANT_REPLY = (
    "❌ Acceso denegado. Esta consola solo está disponible "
    "para administradores de tenant."
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
        instance: str | None = None,
        db: AsyncSession | None = None,
    ) -> str:
        """Process a WhatsApp message for a tenant admin.

        Args:
            phone: Normalised phone number of the sender.
            message: Text of the WhatsApp message.
            identity: Pre-resolved identity dict from
                ``AuthService.identify_by_phone()`` with keys
                ``user_id``, ``role``, ``username``.
            instance: Optional Evolution API instance name for context.
                      Used to close the chat session on top-level exit.
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

        # 2. Resolve the active tenant record + locale
        tenant_id: UUID | None = None
        locale: str = "es"
        tenant = None
        if db is not None:
            tenant = await self._tenant_service.get_tenant(db, UUID(str(user_id)))
            if tenant is None:
                return _t("es", "wa.tenant.facade.tenant_not_found")
            if not tenant.is_active:
                settings_obj = getattr(tenant, "settings", None)
                inactive_locale = getattr(settings_obj, "locale", None) or "es"
                return _t(
                    inactive_locale,
                    "wa.tenant.facade.inactive_tenant",
                )
            tenant_id = tenant.id
            try:
                locale = await tenant_settings_repository.resolve_locale_by_owner(
                    db, tenant.owner_user_id
                )
            except AttributeError:
                # db is a fake/mock object in tests — fall back to default
                locale = "es"

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
                    locale=locale,
                )
            elif self._session_service.used_backup:
                # Failover: session may be missing on backup
                return await self._perform_exit(
                    phone=phone, instance=instance, locale=locale
                )
            else:
                # Top-level → clear session, close Evolution chat, and goodbye
                return await self._perform_exit(
                    phone=phone, instance=instance, locale=locale
                )

        # 4. Delegate to the tenant console service
        tenant_plan = "pro"
        if tenant is not None:
            tenant_plan = getattr(tenant, "plan", "pro") or "pro"

        return await self._console_service.process_message(
            phone=phone,
            message=message,
            tenant_id=tenant_id if db is not None else None,
            user_id=UUID(str(user_id)),
            db=db,
            session_service=self._session_service,
            locale=locale,
            tenant_plan=tenant_plan,
        )

    # ------------------------------------------------------------------
    # Exit
    # ------------------------------------------------------------------

    async def _perform_exit(
        self, phone: str, instance: str | None, locale: str = "es"
    ) -> str:
        """Perform a top-level exit. Evolution close is handled by n8n."""
        await self._session_service.clear_session(self._admin_phone_key(phone))
        return _t(locale, "wa.tenant.facade.goodbye")

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
