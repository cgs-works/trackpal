"""Pydantic schemas for the WhatsApp Master Console endpoint."""

from pydantic import BaseModel


class WhatsAppConsoleRequest(BaseModel):
    """Normalised inbound message from n8n transport.

    Attributes:
        phone:    Normalised phone number of the WhatsApp user.
        message:  Text of the WhatsApp message.
        instance: Optional Evolution API instance name for context.
    """

    phone: str
    message: str
    instance: str | None = None


class WhatsAppConsoleResponse(BaseModel):
    """Reply for n8n to send back through Evolution API.

    Attributes:
        reply: Plain text reply that n8n must relay to the user.
    """

    reply: str
