"""Pydantic V2 schemas for tenant WhatsApp self-linking API."""

from pydantic import BaseModel, ConfigDict, Field


class WhatsAppLinkStatusResponse(BaseModel):
    """Response model for GET /tenant/whatsapp-link/status."""

    connected: bool
    phone: str | None
    instance_name: str


class WhatsAppPairRequest(BaseModel):
    """Request body for POST /tenant/whatsapp-link/pair.

    The body must be empty: the phone number is sourced from
    ``tenant.whatsapp_phone``, never from the client.
    """

    model_config = ConfigDict(extra="forbid")


class WhatsAppPairResponse(BaseModel):
    """Response model for POST /tenant/whatsapp-link/pair."""

    code: str = Field(min_length=1)


class WhatsAppQrResponse(BaseModel):
    """Response model for GET /tenant/whatsapp-link/qr."""

    qrcode: str = Field(min_length=1)


class WhatsAppDisconnectResponse(BaseModel):
    """Response model for POST /tenant/whatsapp-link/disconnect."""

    connected: bool = False
