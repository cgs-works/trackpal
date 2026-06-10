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
        from_me:  When ``true``, the message was sent by the admin from
            their own chat (outgoing trigger). Only the tenant instance
            owning the admin processes ``from_me`` triggers.
        admin_phone: Phone number of the admin who sent the outgoing
            trigger (``from_me=true``). Used to identify which tenant
            admin originated the message.
        admin_jid: JID of the admin who sent the outgoing trigger.
            Used as ``reply_to`` target for contextual administrative
            replies so they remain private to the admin chat.
        target_jid: The JID that the admin selected as the shortcut
            target (the client or unregistered contact).
        target_phone: Phone number of the shortcut target, when
            available as a phone JID.  Never derived from a ``@lid``
            value.
        target_lid: LID JID of the shortcut target, when the target
            was only identified via ``@lid``.
    """

    phone: str
    message: str
    instance: str | None = None
    sender_lid: str | None = None
    from_me: bool | None = None
    admin_phone: str | None = None
    admin_jid: str | None = None
    target_jid: str | None = None
    target_phone: str | None = None
    target_lid: str | None = None


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
            every 4s up to 60s to get the final result.
        tenant_id: Optional tenant UUID for scoped poll requests.
            Included alongside ``lookup_job_id`` so n8n can pass
            ``tenant_id`` as a query parameter when polling.
        reply_to: Optional JID the n8n workflow should use as the
            destination when sending the reply.  When present, n8n
            sends to this JID instead of the ``phone`` field.
        no_reply: When ``true``, n8n must not send any Evolution API
            message at all.  Used for silent administrative replies
            or blocked attempts where no user-facing message should
            be sent.
        close_jid: Optional legacy single JID n8n must close in Evolution.
        close_jids: Optional list of all Evolution sessions to close when
            ``status`` requests session close. Client Context Shortcut uses
            this to close both admin private chat and original target chat.
    """

    reply: str
    status: str | None = None
    lookup_job_id: str | None = None
    tenant_id: str | None = None
    reply_to: str | None = None
    no_reply: bool | None = None
    close_jid: str | None = None
    close_jids: list[str] | None = None

    @model_serializer
    def ser_model(self) -> dict:
        d: dict = {"reply": self.reply}
        if self.status is not None:
            d["status"] = self.status
        if self.lookup_job_id is not None:
            d["lookup_job_id"] = self.lookup_job_id
        if self.tenant_id is not None:
            d["tenant_id"] = self.tenant_id
        if self.reply_to is not None:
            d["reply_to"] = self.reply_to
        if self.no_reply is not None:
            d["no_reply"] = self.no_reply
        if self.close_jid is not None:
            d["close_jid"] = self.close_jid
        if self.close_jids is not None:
            d["close_jids"] = self.close_jids
        return d
