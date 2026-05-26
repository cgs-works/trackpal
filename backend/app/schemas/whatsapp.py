"""Pydantic schemas for the WhatsApp Master Console endpoint."""

from pydantic import BaseModel, model_serializer


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
        status: Optional status signal for n8n workflow routing
            (e.g. ``"closed"`` when user exits the console).
            Only included in the serialised response when non-``None``.
    """

    reply: str
    status: str | None = None

    @model_serializer
    def ser_model(self) -> dict:
        d: dict = {"reply": self.reply}
        if self.status is not None:
            d["status"] = self.status
        return d
