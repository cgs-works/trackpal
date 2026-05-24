"""Login flow handlers for the WhatsApp Master Console facade."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.phone import normalize_phone
from app.repositories import users_repository
from app.services.auth_service import AuthService
from app.services.evolution_client import evolution_client
from app.services.whatsapp_auth_session_service import (
    WhatsAppAuthSession,
)

from . import constants as c

logger = logging.getLogger(__name__)


async def _run_login_flow(
    self,
    phone: str,
    message: str,
    db: AsyncSession | None,
) -> str:
    """Conversational username/password login flow."""
    msg = message.strip()
    msg_lower = msg.lower()

    if msg_lower in c.RESET_COMMANDS:
        await self._auth_session_service.clear_auth_session(phone)
        await self._session_service.clear_session(phone)
        return c.USERNAME_PROMPT

    if msg_lower in c.HELP_COMMANDS:
        return c.LOGIN_HELP

    session = await self._session_service.get_session(phone)

    if session is None or session.flow != c.AUTH_FLOW:
        session = await self._session_service.create_session(phone)
        session.flow = c.AUTH_FLOW
        session.step = c.AUTH_STEP_USERNAME
        session.temp_data = {}
        await self._session_service.save_session(session)
        return c.USERNAME_PROMPT

    if session.flow == c.AUTH_FLOW and session.step == c.AUTH_STEP_USERNAME:
        return await self._handle_username_step(phone, msg, session, db)

    if session.flow == c.AUTH_FLOW and session.step == c.AUTH_STEP_PASSWORD:
        return await self._handle_password_step(phone, msg, session, db)

    await self._session_service.clear_session(phone)
    return c.USERNAME_PROMPT


async def _handle_username_step(
    self,
    phone: str,
    msg: str,
    session: Any,
    db: AsyncSession | None,
) -> str:
    """Store lowercase username, transition to password prompt."""
    msg_stripped = msg.strip()

    if not msg_stripped:
        return c.USERNAME_PROMPT

    msg_lower = msg_stripped.lower()

    if msg_lower in c.RESET_COMMANDS:
        await self._auth_session_service.clear_auth_session(phone)
        await self._session_service.clear_session(phone)
        return c.USERNAME_PROMPT

    if msg_lower in c.HELP_COMMANDS:
        return c.LOGIN_HELP

    if db is not None:
        existing_user = await users_repository.get_by_username(db, msg_lower)
        if existing_user is None:
            lockout_reply = await self._record_failure_and_check_lockout(phone)
            if lockout_reply is not None:
                return lockout_reply
            return c.UNKNOWN_USERNAME_TEMPLATE.format(username=msg_lower)

    session.temp_data["username"] = msg_lower
    session.step = c.AUTH_STEP_PASSWORD
    await self._session_service.save_session(session)

    return c.PASSWORD_PROMPT_TEMPLATE.format(username=msg_lower)


async def _handle_password_step(
    self,
    phone: str,
    msg: str,
    session: Any,
    db: AsyncSession | None,
) -> str:
    """Verify credentials and create auth session on success."""
    msg_stripped = msg.strip()
    username = session.temp_data.get("username", "")

    if not msg_stripped:
        return c.PASSWORD_PROMPT_TEMPLATE.format(username=username)

    if msg_stripped.lower() in c.RESET_COMMANDS:
        await self._auth_session_service.clear_auth_session(phone)
        await self._session_service.clear_session(phone)
        return c.USERNAME_PROMPT

    if msg_stripped.lower() in c.HELP_COMMANDS:
        return c.LOGIN_HELP

    if db is None:
        from app.services.contingency_reply_policy import ContingencyReplyPolicy
        return ContingencyReplyPolicy.TEMPORARY_UNAVAILABLE

    auth_service = AuthService()
    user = await auth_service.authenticate(db, username, msg_stripped)

    if user is None:
        existing_user = await users_repository.get_by_username(db, username)

        if existing_user is None:
            lockout_reply = await self._record_failure_and_check_lockout(phone)
            if lockout_reply is not None:
                return lockout_reply
            return c.UNKNOWN_USERNAME_TEMPLATE.format(username=username)

        lockout_reply = await self._record_failure_and_check_lockout(phone)
        if lockout_reply is not None:
            return lockout_reply

        return c.WRONG_PASSWORD_TEMPLATE.format(username=username)

    if user.role != "master":
        lockout_reply = await self._record_failure_and_check_lockout(phone)
        await self._session_service.clear_session(phone)
        if lockout_reply is not None:
            return lockout_reply
        return c.ROLE_NOT_ALLOWED

    auth_session = WhatsAppAuthSession(
        phone=phone,
        user_id=user.id,
        username=user.username,
        role=user.role,
        authenticated_at=datetime.now(timezone.utc),
    )
    await self._auth_session_service.set_auth_session(auth_session)
    await self._session_service.clear_session(phone)
    await self._auth_session_service.clear_fail_counter(phone)

    return self._console_service.MAIN_MENU


async def _record_failure_and_check_lockout(
    self, phone: str
) -> str | None:
    """Record a failed login attempt and return lockout reply if threshold reached."""
    _, lock_state = await self._auth_session_service.record_failed_attempt(phone)
    if lock_state is not None:
        remaining = self._compute_remaining_minutes(lock_state)
        await self._session_service.clear_session(phone)
        return c.LOCKOUT_TEMPLATE.format(minutes=remaining)
    return None


@staticmethod
def _compute_remaining_minutes(lock_state: Any) -> int:
    """Compute remaining lockout minutes (minimum 1)."""
    if lock_state is None or lock_state.locked_until is None:
        return 1
    remaining = (lock_state.locked_until - datetime.now(timezone.utc)).total_seconds()
    return max(1, int(remaining // 60) + 1)
