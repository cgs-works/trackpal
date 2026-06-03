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


class SessionLifecyclePolicy:
    """Defines when a session TTL should be refreshed vs preserved.

    TTL refreshes only on session creation, valid step advance, or valid
    flow data update.  Noise, invalid input, fallback, help display, and
    access-denied replies do NOT refresh TTL.

    The policy is applied by the service via the ``touch_ttl`` parameter
    on ``save_session()``.
    """

    def __init__(self, ttl_seconds: int = 300) -> None:
        self.ttl_seconds = ttl_seconds


class WhatsAppSessionService:
    """Manage ephemeral WhatsApp conversation state in Redis.

    Each session is stored as a JSON blob under ``session:{phone}``
    with a configurable TTL (default 5 minutes, 300s).
    """

    SESSION_KEY_PREFIX = "session:"

    def __init__(
        self,
        connection_manager: Any,
        ttl_seconds: int = 300,
    ) -> None:
        """Initialise the service.

        Args:
            connection_manager: An object with an ``execute(operation_name,
                async_callable)`` method that routes operations to the
                active Redis store through the failover policy.
            ttl_seconds: TTL applied on every session write when
                ``touch_ttl`` is ``True`` (default).
        """
        self._manager = connection_manager
        self._ttl = ttl_seconds

    # ------------------------------------------------------------------
    # Signals
    # ------------------------------------------------------------------

    @property
    def used_backup(self) -> bool:
        """``True`` when the connection manager is using the backup Redis store.

        Delegates to the manager's ``used_backup`` property.  Returns
        ``False`` when the manager does not expose this property (e.g.
        legacy or test fakes without the signal).
        """
        if hasattr(self._manager, "used_backup"):
            return self._manager.used_backup
        return False

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
        key = self._session_key(phone)

        async def _get(client: Any) -> str | None:
            return await client.get(key)

        raw = await self._manager.execute("get_session", _get)
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

    async def save_session(
        self,
        session: ConversationSession,
        *,
        touch_ttl: bool = True,
    ) -> ConversationSession:
        """Persist *session* to Redis.

        Args:
            session: The session to persist.
            touch_ttl: When ``True`` (default), extend TTL to
                ``self._ttl`` seconds.  When ``False``, write the
                data with ``KEEPTTL`` so the existing TTL is preserved
                and not accidentally dropped.
        """
        key = self._session_key(session.phone)
        raw = self._serialise(session)

        async def _set(client: Any) -> None:
            if touch_ttl:
                await client.set(key, raw, ex=self._ttl)
            else:
                # KEEPTTL preserves any existing TTL on the key.
                # Without it, SET with no expiry would remove the TTL.
                await client.set(key, raw, keepttl=True)

        await self._manager.execute("save_session", _set)
        return session

    async def update_session(
        self,
        phone: str,
        *,
        touch_ttl: bool = True,
        **fields: Any,
    ) -> ConversationSession | None:
        """Update one or more fields of an existing session.

        Accepts any ``ConversationSession`` field as a keyword argument.
        Returns ``None`` when no session exists for *phone*.

        Args:
            phone: The phone key of the session.
            touch_ttl: Passed through to :meth:`save_session`.
        """
        session = await self.get_session(phone)
        if session is None:
            return None

        for field, value in fields.items():
            if hasattr(session, field):
                setattr(session, field, value)

        await self.save_session(session, touch_ttl=touch_ttl)
        return session

    async def clear_session(self, phone: str) -> None:
        """Delete the session for *phone* (if any)."""
        key = self._session_key(phone)

        async def _delete(client: Any) -> None:
            await client.delete(key)

        await self._manager.execute("clear_session", _delete)
