"""Pydantic schemas for the WhatsApp Master Console endpoint."""

from pydantic import BaseModel, model_serializer


class WhatsAppConsoleRequest(BaseModel):
    """Normalised inbound message from n8n transport.

    Attributes:
        phone:    Normalised phone number of the WhatsApp user.
        message:  Text of the WhatsApp message.
        instance: Optional Evolution API instance name for context.
        sender_lid: Optional LID JID string when ``remoteJid`` uses ``@lid``
            and no phone JID is resolvable (LID fallback identity).
    """

    phone: str
    message: str
    instance: str | None = None
    sender_lid: str | None = None


class WhatsAppConsoleResponse(BaseModel):
    """Reply for n8n to send back through Evolution API.

    Attributes:
        reply: Plain text reply that n8n must relay to the user.
        status: Optional status signal for n8n workflow routing
            (e.g. ``"closed"`` when user exits the console).
            Only included in the serialised response when non-``None``.
        lookup_job_id: Optional job id for code lookup polling.
            When present, n8n must send ``reply`` immediately then
            poll ``GET /api/v1/integrations/n8n/mail/lookups/{id}``
            every 4s up to 20s to get the final result.
        tenant_id: Optional tenant UUID for scoped poll requests.
            Included alongside ``lookup_job_id`` so n8n can pass
            ``tenant_id`` as a query parameter when polling.
    """

    reply: str
    status: str | None = None
    lookup_job_id: str | None = None
    tenant_id: str | None = None

    @model_serializer
    def ser_model(self) -> dict:
        d: dict = {"reply": self.reply}
        if self.status is not None:
            d["status"] = self.status
        if self.lookup_job_id is not None:
            d["lookup_job_id"] = self.lookup_job_id
        if self.tenant_id is not None:
            d["tenant_id"] = self.tenant_id
        return d
