"""Read-only WhatsApp Client Console facade.

Provides a minimal menu for client-side users within a tenant:
- View profile info
- View active subscriptions
- Exit / close session

All user-facing text goes through i18n (``wa.client.*`` keys).
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.i18n import t as _t
from app.repositories import clients_repository
from app.services.subscription_service.queries import list_subscriptions
from app.services.whatsapp_session_service import WhatsAppSessionService

logger = logging.getLogger(__name__)


class WhatsAppClientConsoleFacade:
    """Read-only WhatsApp console for client users.

    Resolves client identity from (tenant_id, phone), then provides
    a minimal read-only menu:
      1. Ver perfil
      2. Ver suscripciones activas
      0. Salir (returns status=closed to n8n)
    """

    def __init__(
        self,
        session_service: WhatsAppSessionService,
        locale: str = "es",
    ) -> None:
        self._session_service = session_service
        self._locale = locale

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
        """Process a WhatsApp message for a client user."""
        client_id = identity.get("client_id")
        tenant_id = identity.get("tenant_id")
        if not client_id or not tenant_id:
            return _t(self._locale, "wa.client.identity_error")

        msg = message.strip()
        msg_lower = msg.lower()

        if msg in ("0", "salir"):
            return await self._perform_exit(
                phone=phone,
                instance=instance,
                tenant_id=UUID(tenant_id) if isinstance(tenant_id, str) else tenant_id,
                client_id=UUID(client_id) if isinstance(client_id, str) else client_id,
            )

        if msg_lower in ("menu", "/menu"):
            return self._main_menu()

        if not msg:
            return self._main_menu()

        if msg == "1":
            return await self._show_profile(
                tenant_id=UUID(tenant_id) if isinstance(tenant_id, str) else tenant_id,
                client_id=UUID(client_id) if isinstance(client_id, str) else client_id,
                db=db,
            )
        elif msg == "2":
            return await self._show_subscriptions(
                tenant_id=UUID(tenant_id) if isinstance(tenant_id, str) else tenant_id,
                client_id=UUID(client_id) if isinstance(client_id, str) else client_id,
                db=db,
            )
        elif msg == "3":
            return _t(self._locale, "wa.client.codigo.redirect")
        return self._main_menu()

    def _main_menu(self) -> str:
        return _t(self._locale, "wa.client.main_menu")

    # ------------------------------------------------------------------
    # Profile
    # ------------------------------------------------------------------
    async def _show_profile(
        self,
        tenant_id: UUID,
        client_id: UUID,
        db: AsyncSession | None,
    ) -> str:
        if db is None:
            return _t(self._locale, "wa.client.internal_error")
        from app.core.database import set_internal_rls_context

        await set_internal_rls_context(db)
        client = await clients_repository.get(db, tenant_id, client_id)
        if client is None:
            return _t(self._locale, "wa.client.profile.not_found")
        tenant_name = getattr(client.tenant, "name", "") if client.tenant else ""
        return self._format_client_profile(client, tenant_name)

    def _format_client_profile(self, client: Any, tenant_name: str) -> str:
        status = (
            _t(self._locale, "wa.client.profile.status_active")
            if client.is_active
            else _t(self._locale, "wa.client.profile.status_inactive")
        )
        return _t(
            self._locale,
            "wa.client.profile.body",
            full_name=client.full_name,
            tenant_name=tenant_name,
            phone=client.phone or "—",
            status=status,
        )

    # ------------------------------------------------------------------
    # Subscriptions
    # ------------------------------------------------------------------
    async def _show_subscriptions(
        self,
        tenant_id: UUID,
        client_id: UUID,
        db: AsyncSession | None,
    ) -> str:
        if db is None:
            return _t(self._locale, "wa.client.internal_error")
        from app.core.database import set_internal_rls_context

        await set_internal_rls_context(db)
        subs = await list_subscriptions(
            db, tenant_id, status="active", client_id=client_id
        )
        return self._format_subs(subs)

    def _format_subs(self, subs: list[Any]) -> str:
        if not subs:
            return _t(self._locale, "wa.client.subscriptions.empty")
        lines = [_t(self._locale, "wa.client.subscriptions.header")]
        for i, s in enumerate(subs, 1):
            svc: Any = getattr(s, "service_name", None) or getattr(s, "service", None)
            svc_name_attr = getattr(svc, "name", None)
            svc_name = (
                str(svc_name_attr)
                if svc_name_attr is not None
                else str(svc)
                if svc is not None
                else "—"
            )
            plan: Any = getattr(s, "plan_name", None) or getattr(s, "plan", None)
            plan_name_attr = getattr(plan, "name", None)
            plan_name = (
                str(plan_name_attr)
                if plan_name_attr is not None
                else str(plan)
                if plan is not None
                else "—"
            )
            start = getattr(s, "starts_at", None)
            exp = getattr(s, "expires_at", None)
            start_str = start.strftime("%d/%m/%Y") if start else "—"
            exp_str = exp.strftime("%d/%m/%Y") if exp else "—"
            status_label = (
                _t(self._locale, "wa.client.subscriptions.status_active")
                if s.status == "active"
                else _t(
                    self._locale,
                    "wa.client.subscriptions.status_other",
                    status=s.status,
                )
            )
            lines.append(
                _t(
                    self._locale,
                    "wa.client.subscriptions.item",
                    num=i,
                    service=svc_name,
                    plan=plan_name,
                    start=start_str,
                    exp=exp_str,
                    status=status_label,
                )
            )
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Exit
    # ------------------------------------------------------------------
    async def _perform_exit(
        self,
        phone: str,
        instance: str | None,
        tenant_id: UUID,
        client_id: UUID,
    ) -> str:
        """Exit — clear session. Evolution close handled by n8n."""
        await self._session_service.clear_session(f"client:{phone}")
        return _t(self._locale, "wa.client.goodbye")
