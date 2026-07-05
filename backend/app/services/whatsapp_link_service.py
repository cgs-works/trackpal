"""Service orchestration for tenant WhatsApp self-linking.

Validates tenant configuration, decrypts instance tokens, checks
connection status, and orchestrates Evolution API calls through the
``evolution_client`` singleton.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import decrypt_value
from app.core.errors import UserFacingError
from app.models.tenant import Tenant
from app.repositories import tenants_repository
from app.schemas.whatsapp_link import (
    WhatsAppDisconnectResponse,
    WhatsAppLinkStatusResponse,
    WhatsAppPairResponse,
    WhatsAppQrResponse,
)
from app.services.evolution_client import EvolutionClientError, evolution_client

# ── Error code → UserFacingError code mapping ───────────────────────────

EVOLUTION_TO_USER_ERROR: dict[str, str] = {
    "invalid_instance_token": "whatsapp_link.invalid_instance_token",
    "service_unavailable": "whatsapp_link.service_unavailable",
    "request_failed": "whatsapp_link.request_failed",
}


def _map_evolution_error(exc: EvolutionClientError) -> UserFacingError:
    """Map an ``EvolutionClientError`` to a ``UserFacingError``."""
    mapped = EVOLUTION_TO_USER_ERROR.get(exc.code, "whatsapp_link.request_failed")
    return UserFacingError(mapped)


# ── Internal helpers ─────────────────────────────────────────────────────


async def _get_configured_tenant(db: AsyncSession, tenant_id: UUID) -> Tenant:
    """Fetch and validate the tenant exists, is active, and has instance config."""
    tenant = await tenants_repository.get(db, tenant_id)
    if tenant is None:
        raise UserFacingError("tenant_not_found")
    if not tenant.is_active:
        raise UserFacingError("tenant_not_found")
    if not tenant.evolution_instance_name or not tenant.evolution_instance_token:
        raise UserFacingError("whatsapp_link.instance_not_configured")
    return tenant


async def _get_instance_credentials(
    db: AsyncSession, tenant_id: UUID
) -> tuple[Tenant, str, str]:
    """Return (tenant, instance_name, decrypted_instance_token).

    Raises ``UserFacingError`` if the tenant is not configured or the
    token cannot be decrypted.
    """
    tenant = await _get_configured_tenant(db, tenant_id)

    decrypted = decrypt_value(tenant.evolution_instance_token)
    if not decrypted:
        raise UserFacingError("whatsapp_link.invalid_instance_token")

    return tenant, tenant.evolution_instance_name, decrypted


async def _ensure_not_connected(instance_name: str, instance_token: str) -> None:
    """Raise ``whatsapp_link.already_connected`` if the instance is connected."""
    try:
        status = await evolution_client.get_instance_status(
            instance_name, instance_token
        )
    except EvolutionClientError as exc:
        raise _map_evolution_error(exc) from exc

    if status.get("connected") is True and status.get("loggedIn") is True:
        raise UserFacingError("whatsapp_link.already_connected")


def _compute_connected(status: dict) -> bool:
    """True only when Evolution reports both ``connected`` and ``loggedIn`` true."""
    return status.get("connected") is True and status.get("loggedIn") is True


# ── Service class ────────────────────────────────────────────────────────


class WhatsAppLinkService:
    """Orchestrates WhatsApp instance lifecycle for a tenant."""

    async def get_status(
        self, db: AsyncSession, tenant_id: UUID
    ) -> WhatsAppLinkStatusResponse:
        """Return the current WhatsApp connection status."""
        tenant, instance_name, instance_token = await _get_instance_credentials(
            db, tenant_id
        )

        try:
            status = await evolution_client.get_instance_status(
                instance_name, instance_token
            )
        except EvolutionClientError as exc:
            raise _map_evolution_error(exc) from exc

        return WhatsAppLinkStatusResponse(
            connected=_compute_connected(status),
            phone=tenant.whatsapp_phone,
            instance_name=instance_name,
        )

    async def request_pairing_code(
        self, db: AsyncSession, tenant_id: UUID
    ) -> WhatsAppPairResponse:
        """Request an 8-digit pairing code from Evolution."""
        tenant, instance_name, instance_token = await _get_instance_credentials(
            db, tenant_id
        )

        if not tenant.whatsapp_phone:
            raise UserFacingError("whatsapp_link.phone_required")

        await _ensure_not_connected(instance_name, instance_token)

        try:
            result = await evolution_client.pair_instance(
                instance_name, instance_token, tenant.whatsapp_phone
            )
        except EvolutionClientError as exc:
            raise _map_evolution_error(exc) from exc

        return WhatsAppPairResponse(code=result.get("code", ""))

    async def get_qr_code(
        self, db: AsyncSession, tenant_id: UUID
    ) -> WhatsAppQrResponse:
        """Retrieve the QR code for WhatsApp Web linking."""
        tenant, instance_name, instance_token = await _get_instance_credentials(
            db, tenant_id
        )

        if not tenant.whatsapp_phone:
            raise UserFacingError("whatsapp_link.phone_required")

        await _ensure_not_connected(instance_name, instance_token)

        try:
            result = await evolution_client.get_qr_code(
                instance_name, instance_token
            )
        except EvolutionClientError as exc:
            raise _map_evolution_error(exc) from exc

        return WhatsAppQrResponse(qrcode=result.get("qrcode", ""))

    async def disconnect(
        self, db: AsyncSession, tenant_id: UUID
    ) -> WhatsAppDisconnectResponse:
        """Log out the WhatsApp instance without deleting it.

        The Evolution instance is preserved so the tenant can re-link later.
        Idempotent: returns 200 even if already disconnected.
        """
        _, instance_name, instance_token = await _get_instance_credentials(
            db, tenant_id
        )

        try:
            await evolution_client.logout_instance(instance_name, instance_token)
        except EvolutionClientError as exc:
            raise _map_evolution_error(exc) from exc

        return WhatsAppDisconnectResponse(connected=False)
