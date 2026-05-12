"""Redis-backed ephemeral conversation session for the WhatsApp Master Console.

Stores per-phone session state as JSON in Redis so that multi-step
WhatsApp flows survive individual webhook executions.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel


class ConversationSession(BaseModel):
    """Ephemeral conversational state keyed by Master phone number.

    Attributes:
        phone: Normalised Master phone number (Redis key basis).
        flow:  Current flow identifier, e.g. ``"create_tenant"``.
        step:  Current step *within* the flow.
        selected_tenant_id: UUID of the tenant the Master is acting on.
        temp_data: Temporary form data being collected across steps.
        selection_map: Maps displayed numbers (``"1"``) to tenant UUIDs.
    """

    phone: str
    flow: str = ""
    step: str = ""
    selected_tenant_id: str | None = None
    temp_data: dict[str, Any] = {}
    selection_map: dict[str, str] = {}


class WhatsAppSessionService:
    """Manage ephemeral WhatsApp conversation state in Redis.

    Each session is stored as a JSON blob under ``session:{phone}``
    with a configurable TTL (default 30 minutes).
    """

    SESSION_KEY_PREFIX = "session:"

    def __init__(
        self,
        redis_client: Any,
        ttl_seconds: int = 1800,
    ) -> None:
        """Initialise the service.

        Args:
            redis_client: An async Redis-like client exposing ``get``,
                ``set``, ``delete``.
            ttl_seconds: TTL applied on every session write.
        """
        self._redis = redis_client
        self._ttl = ttl_seconds

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _session_key(self, phone: str) -> str:
        return f"{self.SESSION_KEY_PREFIX}{phone}"

    @staticmethod
    def _serialise(session: ConversationSession) -> str:
        return session.model_dump_json()

    @staticmethod
    def _deserialise(data: str) -> ConversationSession | None:
        try:
            raw = json.loads(data)
            return ConversationSession(**raw)
        except (json.JSONDecodeError, ValueError, TypeError):
            return None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_session(self, phone: str) -> ConversationSession | None:
        """Return the session for *phone*, or ``None`` if absent."""
        raw = await self._redis.get(self._session_key(phone))
        if raw is None:
            return None
        return self._deserialise(raw)

    async def create_session(self, phone: str) -> ConversationSession:
        """Create a fresh session for *phone* with default values.

        Any existing session for the same phone is overwritten.
        """
        session = ConversationSession(phone=phone)
        await self.save_session(session)
        return session

    async def save_session(self, session: ConversationSession) -> ConversationSession:
        """Persist *session* to Redis, applying the configured TTL."""
        raw = self._serialise(session)
        await self._redis.set(self._session_key(session.phone), raw, ex=self._ttl)
        return session

    async def update_session(
        self,
        phone: str,
        **fields: Any,
    ) -> ConversationSession | None:
        """Update one or more fields of an existing session.

        Accepts any ``ConversationSession`` field as a keyword argument.
        Returns ``None`` when no session exists for *phone*.
        """
        session = await self.get_session(phone)
        if session is None:
            return None

        for field, value in fields.items():
            if hasattr(session, field):
                setattr(session, field, value)

        await self.save_session(session)
        return session

    async def clear_session(self, phone: str) -> None:
        """Delete the session for *phone* (if any)."""
        await self._redis.delete(self._session_key(phone))
