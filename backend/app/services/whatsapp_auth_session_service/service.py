"""Redis-backed authenticated session + lockout for WhatsApp Master Console.

Debt: 203 LoC (target <=200, max 240). Trim docstrings when possible.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from pydantic import BaseModel

from .models import WhatsAppAuthSession, WhatsAppAuthFailState, WhatsAppAuthLockState


class WhatsAppAuthSessionService:
    """Manage authentication session + lockout state in Redis.

    Each piece of state is stored as JSON under dedicated key prefixes
    with appropriate TTLs.
    """

    AUTH_KEY_PREFIX = "wa:auth:"
    FAIL_KEY_PREFIX = "wa:auth:fail:"
    LOCK_KEY_PREFIX = "wa:auth:lock:"

    def __init__(
        self,
        connection_manager: Any,
        session_ttl_seconds: int = 300,
        fail_threshold: int = 5,
        lock_minutes: int = 5,
        fail_window_minutes: int = 15,
    ) -> None:
        self._manager = connection_manager
        self._session_ttl = session_ttl_seconds
        self._fail_threshold = fail_threshold
        self._lock_minutes = lock_minutes
        self._fail_window_seconds = fail_window_minutes * 60

    # ------------------------------------------------------------------
    # Key helpers
    # ------------------------------------------------------------------

    def _auth_key(self, phone: str) -> str:
        return f"{self.AUTH_KEY_PREFIX}{phone}"

    def _fail_key(self, phone: str) -> str:
        return f"{self.FAIL_KEY_PREFIX}{phone}"

    def _lock_key(self, phone: str) -> str:
        return f"{self.LOCK_KEY_PREFIX}{phone}"

    # ------------------------------------------------------------------
    # Serialisation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _serialise(model: BaseModel) -> str:
        return model.model_dump_json()

    @staticmethod
    def _deserialise(data: str | None, model_cls: type[BaseModel]) -> Any | None:
        if data is None:
            return None
        try:
            raw = json.loads(data)
            return model_cls(**raw)
        except (json.JSONDecodeError, ValueError, TypeError):
            return None

    # ------------------------------------------------------------------
    # Auth session CRUD
    # ------------------------------------------------------------------

    async def get_auth_session(self, phone: str) -> WhatsAppAuthSession | None:
        """Return the auth session for *phone*, or ``None``."""
        key = self._auth_key(phone)

        async def _get(client: Any) -> str | None:
            return await client.get(key)

        raw = await self._manager.execute("get_auth_session", _get)
        return self._deserialise(raw, WhatsAppAuthSession)

    async def set_auth_session(
        self, session: WhatsAppAuthSession
    ) -> WhatsAppAuthSession:
        """Persist an auth session with TTL."""
        key = self._auth_key(session.phone)
        raw = self._serialise(session)

        async def _set(client: Any) -> None:
            await client.set(key, raw, ex=self._session_ttl)

        await self._manager.execute("set_auth_session", _set)
        return session

    async def clear_auth_session(self, phone: str) -> None:
        """Delete the auth session for *phone* (if any)."""
        key = self._auth_key(phone)

        async def _delete(client: Any) -> None:
            await client.delete(key)

        await self._manager.execute("clear_auth_session", _delete)

    async def touch_auth_session(self, phone: str) -> None:
        """Refresh the TTL of an existing auth session (sliding window).

        Re-sets ``EX`` on the key without modifying the stored payload.
        No-op if no auth session exists for *phone*.
        """
        key = self._auth_key(phone)

        async def _touch(client: Any) -> None:
            await client.expire(key, self._session_ttl)

        await self._manager.execute("touch_auth_session", _touch)

    async def clear_fail_counter(self, phone: str) -> None:
        """Delete the fail-counter key for *phone* (if any).

        Call this on successful login to prevent accidental lockout
        from stale failure counts.
        """
        key = self._fail_key(phone)

        async def _delete(client: Any) -> None:
            await client.delete(key)

        await self._manager.execute("clear_fail_counter", _delete)

    # ------------------------------------------------------------------
    # Lockout primitives
    # ------------------------------------------------------------------

    async def get_lock_state(self, phone: str) -> WhatsAppAuthLockState | None:
        """Return the current lock state for *phone*, or ``None``."""
        key = self._lock_key(phone)

        async def _get(client: Any) -> str | None:
            return await client.get(key)

        raw = await self._manager.execute("get_lock_state", _get)
        return self._deserialise(raw, WhatsAppAuthLockState)

    async def record_failed_attempt(
        self, phone: str, *, now: datetime | None = None
    ) -> tuple[int, WhatsAppAuthLockState | None]:
        """Record a failed login attempt.

        Returns ``(count, lock_state)`` where *count* is the
        consecutive failure count *after* recording this attempt, and
        *lock_state* is the ``WhatsAppAuthLockState`` when the phone
        becomes locked out, or ``None`` otherwise.

        When *count* reaches the threshold, a lock is created and the
        fail counter is cleared.
        """
        if now is None:
            now = datetime.now(timezone.utc)

        fail_key = self._fail_key(phone)
        lock_key = self._lock_key(phone)

        async def _record(client: Any) -> tuple[int, WhatsAppAuthLockState | None]:
            raw = await client.get(fail_key)
            state: WhatsAppAuthFailState | None = self._deserialise(raw, WhatsAppAuthFailState)

            if state is None:
                state = WhatsAppAuthFailState(
                    count=1,
                    first_failed_at=now,
                    last_failed_at=now,
                )
            else:
                state.count += 1
                state.last_failed_at = now

            if state.count >= self._fail_threshold:
                locked_until = now + timedelta(minutes=self._lock_minutes)
                lock = WhatsAppAuthLockState(locked_until=locked_until)
                await client.set(lock_key, self._serialise(lock), ex=int(self._lock_minutes * 60))
                await client.delete(fail_key)
                return (state.count, lock)

            ttl_remaining = self._fail_window_seconds
            if state.first_failed_at is not None:
                elapsed = (now - state.first_failed_at).total_seconds()
                remaining = self._fail_window_seconds - elapsed
                if remaining > 0:
                    ttl_remaining = max(1, int(remaining))
                else:
                    state = WhatsAppAuthFailState(
                        count=1,
                        first_failed_at=now,
                        last_failed_at=now,
                    )
                    ttl_remaining = self._fail_window_seconds

            await client.set(fail_key, self._serialise(state), ex=ttl_remaining)
            return (state.count, None)

        return await self._manager.execute("record_failed_attempt", _record)
