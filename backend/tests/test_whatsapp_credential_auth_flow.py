"""Tests for WhatsApp conversational credential auth flow.

Covers login prompt sequence, successful auth, error paths, lockout,
and global commands during unauthenticated state.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from app.core.config import settings
from app.services.auth_service import AuthService
from app.services.whatsapp_auth_session_service import (
    WhatsAppAuthSessionService,
    WhatsAppAuthLockState,
    WhatsAppAuthSession,
)
from app.services.whatsapp_console_service import WhatsAppConsoleService
from app.services.whatsapp_session_service import (
    ConversationSession,
    WhatsAppSessionService,
)
from app.core.security import get_password_hash


# ---------------------------------------------------------------------------
# Fake Redis + Manager (same pattern as test_whatsapp_menu_flow)
# ---------------------------------------------------------------------------

class FakeRedis:
    """Minimal in-memory fake for redis.asyncio.Redis."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}
        self._ttls: dict[str, int] = {}

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None, keepttl: bool = False) -> None:
        self._store[key] = value
        if ex is not None:
            self._ttls[key] = ex
        elif not keepttl:
            self._ttls.pop(key, None)

    async def expire(self, key: str, time: int) -> int:
        if key in self._store:
            self._ttls[key] = time
            return 1
        return 0

    async def delete(self, key: str) -> int:
        self._ttls.pop(key, None)
        return 1 if self._store.pop(key, None) is not None else 0

    def get_ttl(self, key: str) -> int | None:
        return self._ttls.get(key)


class FakeManager:
    """Duck-typed connection manager that delegates execute() to FakeRedis."""

    def __init__(self, fake_redis: FakeRedis | None = None) -> None:
        self._redis = fake_redis or FakeRedis()
        self._used_backup = False

    @property
    def used_backup(self) -> bool:
        return self._used_backup

    async def execute(self, operation_name: str, async_callable: Any) -> Any:
        return await async_callable(self._redis)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def fake_redis() -> FakeRedis:
    return FakeRedis()


@pytest.fixture
def fake_manager(fake_redis: FakeRedis) -> FakeManager:
    return FakeManager(fake_redis=fake_redis)


@pytest.fixture
def session_service(fake_manager: FakeManager) -> WhatsAppSessionService:
    return WhatsAppSessionService(
        connection_manager=fake_manager,
        ttl_seconds=settings.whatsapp_session_ttl_minutes * 60,
    )


@pytest.fixture
def auth_session_service(fake_manager: FakeManager) -> WhatsAppAuthSessionService:
    return WhatsAppAuthSessionService(
        connection_manager=fake_manager,
        session_ttl_seconds=settings.whatsapp_session_ttl_minutes * 60,
        fail_threshold=settings.whatsapp_auth_fail_threshold,
        lock_minutes=settings.whatsapp_auth_lock_minutes,
        fail_window_minutes=settings.whatsapp_auth_fail_window_minutes,
    )


@pytest.fixture
def console_service() -> WhatsAppConsoleService:
    return WhatsAppConsoleService()


# ---------------------------------------------------------------------------
# Tests: Login prompt sequence (happy path)
# ---------------------------------------------------------------------------

pytestmark = pytest.mark.asyncio


def _make_facade(
    console_service: WhatsAppConsoleService,
    session_service: WhatsAppSessionService,
    auth_session_service: WhatsAppAuthSessionService,
    tenant_service: Any = None,
):
    from app.services.whatsapp_master_console_facade import (
        WhatsAppMasterConsoleFacade,
    )

    return WhatsAppMasterConsoleFacade(
        console_service=console_service,
        session_service=session_service,
        auth_session_service=auth_session_service,
        tenant_service=tenant_service,
    )


class TestLoginFlow:
    """Conversational login — first message, username prompt, password prompt, success."""

    async def test_first_message_returns_username_prompt(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        auth_session_service: WhatsAppAuthSessionService,
    ) -> None:
        """Fresh phone with no auth session → username prompt."""
        facade = _make_facade(console_service, session_service, auth_session_service)

        reply = await facade.process_message(
            phone="+9999999999",
            message="hola",
            db=None,
        )

        assert "usuario" in reply.lower()
        assert "contraseña" not in reply.lower()

    async def test_username_provided_returns_password_prompt(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        auth_session_service: WhatsAppAuthSessionService,
    ) -> None:
        """After sending username → password prompt."""
        facade = _make_facade(console_service, session_service, auth_session_service)

        # First message triggers username prompt
        await facade.process_message(phone="+9999999999", message="hola", db=None)

        # Send a username
        reply = await facade.process_message(
            phone="+9999999999",
            message="master",
            db=None,
        )

        assert "contraseña" in reply.lower()
        assert "master" in reply

    async def test_correct_password_returns_main_menu(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        auth_session_service: WhatsAppAuthSessionService,
        db_session,
    ) -> None:
        """Valid master credentials → main menu + auth session created."""
        # Create a master user in the test DB
        from app.models import User, MasterProfile

        user = User(
            username="master",
            password_hash=get_password_hash("master-password"),
            role="master",
        )
        db_session.add(user)
        await db_session.flush()
        db_session.add(MasterProfile(id=user.id, name="Master User", phone="+12015550001"))
        await db_session.commit()

        facade = _make_facade(console_service, session_service, auth_session_service)

        # First message → username prompt
        await facade.process_message(phone="+12015550001", message="hola", db=db_session)

        # Send username
        await facade.process_message(phone="+12015550001", message="master", db=db_session)

        # Send password
        reply = await facade.process_message(
            phone="+12015550001",
            message="master-password",
            db=db_session,
        )

        assert "Master Console" in reply or "Trackpal" in reply
        assert "menú" in reply.lower() or "menu" in reply.lower()

        # Verify auth session was created
        auth_session = await auth_session_service.get_auth_session("+12015550001")
        assert auth_session is not None
        assert auth_session.role == "master"
        assert auth_session.username == "master"

    async def test_mixed_case_password_preserves_case(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        auth_session_service: WhatsAppAuthSessionService,
        db_session,
    ) -> None:
        """Password with mixed case must NOT be lowercased before auth.

        Regression test for S1 finding: facade must preserve exact
        password case when passing to AuthService.authenticate().
        """
        from app.models import User, MasterProfile

        user = User(
            username="master",
            password_hash=get_password_hash("MyP@ssw0rd!"),
            role="master",
        )
        db_session.add(user)
        await db_session.flush()
        db_session.add(MasterProfile(id=user.id, name="Master User", phone="+12015550001"))
        await db_session.commit()

        facade = _make_facade(console_service, session_service, auth_session_service)

        # Start login flow
        await facade.process_message(phone="+12015550001", message="hola", db=db_session)
        await facade.process_message(phone="+12015550001", message="master", db=db_session)

        # Send mixed-case password
        reply = await facade.process_message(
            phone="+12015550001",
            message="MyP@ssw0rd!",
            db=db_session,
        )

        assert "Master Console" in reply or "Trackpal" in reply

        # Verify auth session was created
        auth_session = await auth_session_service.get_auth_session("+12015550001")
        assert auth_session is not None

        # Verifying lowercased version does NOT work
        await auth_session_service.clear_auth_session("+12015550001")
        await facade.process_message(phone="+12015550001", message="hola", db=db_session)
        await facade.process_message(phone="+12015550001", message="master", db=db_session)
        reply2 = await facade.process_message(
            phone="+12015550001",
            message="myp@ssw0rd!",
            db=db_session,
        )
        assert "contraseña incorrecta" in reply2.lower() or "incorrecta" in reply2.lower()


class TestLoginErrors:
    """Error paths: unknown username, wrong password, role not allowed."""

    async def test_unknown_username_returns_error(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        auth_session_service: WhatsAppAuthSessionService,
        db_session,
    ) -> None:
        """Submit unknown username → error message, stays on username step."""
        # Create a master user (but we'll use a different username)
        from app.models import User, MasterProfile

        user = User(
            username="master",
            password_hash=get_password_hash("master-password"),
            role="master",
        )
        db_session.add(user)
        await db_session.flush()
        db_session.add(MasterProfile(id=user.id, name="Master User", phone="+12015550001"))
        await db_session.commit()

        facade = _make_facade(console_service, session_service, auth_session_service)

        # Start login flow
        await facade.process_message(phone="+12015550001", message="hola", db=db_session)

        # Submit a non-existent username — rejected at username step
        reply = await facade.process_message(
            phone="+12015550001",
            message="nonexistent_user",
            db=db_session,
        )

        # Should get error immediately, stay on username step
        assert "no existe" in reply.lower()
        assert "nonexistent_user" in reply.lower()
        assert "contraseña" not in reply.lower()

        # Can correct and try a valid username
        reply = await facade.process_message(
            phone="+12015550001",
            message="master",
            db=db_session,
        )

        # Should advance to password prompt
        assert "contraseña" in reply.lower()
        assert "master" in reply

    async def test_wrong_password_returns_error(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        auth_session_service: WhatsAppAuthSessionService,
        db_session,
    ) -> None:
        """Correct username but wrong password → error message, stays in login."""
        from app.models import User, MasterProfile

        user = User(
            username="master",
            password_hash=get_password_hash("master-password"),
            role="master",
        )
        db_session.add(user)
        await db_session.flush()
        db_session.add(MasterProfile(id=user.id, name="Master User", phone="+12015550001"))
        await db_session.commit()

        facade = _make_facade(console_service, session_service, auth_session_service)

        # Start login flow
        await facade.process_message(phone="+12015550001", message="hola", db=db_session)
        # Enter username
        await facade.process_message(phone="+12015550001", message="master", db=db_session)

        # Send wrong password
        reply = await facade.process_message(
            phone="+12015550001",
            message="wrong-password",
            db=db_session,
        )

        assert "incorrecta" in reply.lower()
        assert "master" in reply

    async def test_role_not_allowed_returns_error(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        auth_session_service: WhatsAppAuthSessionService,
        db_session,
    ) -> None:
        """Tenant credentials → role not allowed error, no auth session."""
        from app.models import User, TenantProfile

        user = User(
            username="tenant",
            password_hash=get_password_hash("tenant-password"),
            role="tenant",
        )
        db_session.add(user)
        await db_session.flush()
        db_session.add(
            TenantProfile(
                id=user.id,
                full_name="Tenant User",
                phone="+12015550002",
                is_active=True,
            )
        )
        await db_session.commit()

        facade = _make_facade(console_service, session_service, auth_session_service)

        # Start login flow
        await facade.process_message(phone="+12015550002", message="hola", db=db_session)
        # Enter username
        await facade.process_message(phone="+12015550002", message="tenant", db=db_session)

        # Send correct password (but tenant role)
        reply = await facade.process_message(
            phone="+12015550002",
            message="tenant-password",
            db=db_session,
        )

        assert "solo los usuarios con rol master" in reply.lower() or "master" in reply.lower()

        # No auth session should exist
        auth_session = await auth_session_service.get_auth_session("+12015550002")
        assert auth_session is None


class TestResetDuringLogin:
    """Global reset commands during login return to username prompt."""

    async def test_reset_during_username_step_returns_username_prompt(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        auth_session_service: WhatsAppAuthSessionService,
    ) -> None:
        """Sending '0' during username prompt → username prompt."""
        facade = _make_facade(console_service, session_service, auth_session_service)

        # Start login flow
        await facade.process_message(phone="+9999999999", message="hola", db=None)

        # Send reset command
        reply = await facade.process_message(
            phone="+9999999999",
            message="0",
            db=None,
        )

        assert "usuario" in reply.lower()

    async def test_reset_during_password_step_returns_username_prompt(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        auth_session_service: WhatsAppAuthSessionService,
    ) -> None:
        """Sending 'menu' during password step → username prompt (not main menu)."""
        facade = _make_facade(console_service, session_service, auth_session_service)

        # Start login flow and enter username
        await facade.process_message(phone="+9999999999", message="hola", db=None)
        await facade.process_message(phone="+9999999999", message="master", db=None)

        # Send reset command during password step
        reply = await facade.process_message(
            phone="+9999999999",
            message="menu",
            db=None,
        )

        assert "usuario" in reply.lower()
        # Must NOT be the main menu (no menu options)
        assert "Ver Tenants" not in reply
        assert "Crear Tenant" not in reply


class TestLockout:
    """Lockout behavior during login."""

    async def test_lockout_after_multiple_failures(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        auth_session_service: WhatsAppAuthSessionService,
        db_session,
    ) -> None:
        """Exceed failure threshold → lockout message."""
        from app.core.config import settings
        from app.models import User, MasterProfile

        user = User(
            username="master",
            password_hash=get_password_hash("master-password"),
            role="master",
        )
        db_session.add(user)
        await db_session.flush()
        db_session.add(MasterProfile(id=user.id, name="Master User", phone="+12015550001"))
        await db_session.commit()

        facade = _make_facade(console_service, session_service, auth_session_service)

        # Start login flow
        await facade.process_message(phone="+12015550001", message="hola", db=db_session)
        await facade.process_message(phone="+12015550001", message="master", db=db_session)

        # Send wrong password multiple times to trigger lockout
        threshold = settings.whatsapp_auth_fail_threshold
        last_reply = ""
        for i in range(threshold):
            last_reply = await facade.process_message(
                phone="+12015550001",
                message="wrong-password",
                db=db_session,
            )

        assert "demasiados intentos" in last_reply.lower() or "espera" in last_reply.lower()

    async def test_unknown_username_triggers_lockout(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        auth_session_service: WhatsAppAuthSessionService,
        db_session,
    ) -> None:
        """Repeated attempts with non-existent username → lockout."""
        from app.core.config import settings
        from app.models import User, MasterProfile

        user = User(
            username="master",
            password_hash=get_password_hash("master-password"),
            role="master",
        )
        db_session.add(user)
        await db_session.flush()
        db_session.add(MasterProfile(id=user.id, name="Master User", phone="+12015550001"))
        await db_session.commit()

        facade = _make_facade(console_service, session_service, auth_session_service)

        # Start login flow — first message
        await facade.process_message(phone="+12015550001", message="hola", db=db_session)
        # Enter a non-existent username
        await facade.process_message(phone="+12015550001", message="nonexistent_user", db=db_session)

        # Send wrong password for non-existent username — each attempt counts toward lockout
        threshold = settings.whatsapp_auth_fail_threshold
        last_reply = ""
        for i in range(threshold):
            last_reply = await facade.process_message(
                phone="+12015550001",
                message="any-password",
                db=db_session,
            )

        assert "demasiados intentos" in last_reply.lower() or "espera" in last_reply.lower()

    async def test_lockout_clears_when_lock_key_removed(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        auth_session_service: WhatsAppAuthSessionService,
        fake_redis: FakeRedis,
        db_session,
    ) -> None:
        """Remove lock key → account unblocked → login prompts again."""
        from datetime import datetime, timedelta, timezone
        from app.core.config import settings
        from app.models import User, MasterProfile

        user = User(
            username="master",
            password_hash=get_password_hash("master-password"),
            role="master",
        )
        db_session.add(user)
        await db_session.flush()
        db_session.add(MasterProfile(id=user.id, name="Master User", phone="+12015550001"))
        await db_session.commit()

        facade = _make_facade(console_service, session_service, auth_session_service)

        # Start login flow
        await facade.process_message(phone="+12015550001", message="hola", db=db_session)
        await facade.process_message(phone="+12015550001", message="master", db=db_session)

        # Trigger lockout
        threshold = settings.whatsapp_auth_fail_threshold
        for i in range(threshold):
            last_reply = await facade.process_message(
                phone="+12015550001",
                message="wrong-password",
                db=db_session,
            )
        assert "demasiados intentos" in last_reply.lower() or "espera" in last_reply.lower()

        # Remove the lock key from fake redis (simulating expiry)
        lock_key = auth_session_service._lock_key("+12015550001")
        await fake_redis.delete(lock_key)

        # Now should get login prompts again
        reply = await facade.process_message(
            phone="+12015550001",
            message="hola",
            db=db_session,
        )
        assert "usuario" in reply.lower() or "iniciar sesión" in reply.lower()
        assert "demasiados intentos" not in reply.lower()

    async def test_locked_account_returns_lockout_on_first_message(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        auth_session_service: WhatsAppAuthSessionService,
        db_session,
    ) -> None:
        """Locked phone → lockout reply even before login flow starts."""
        from datetime import datetime, timedelta, timezone
        from app.services.whatsapp_auth_session_service import WhatsAppAuthLockState

        # Manually create lock state
        lock = WhatsAppAuthLockState(
            locked_until=datetime.now(timezone.utc) + timedelta(minutes=5),
        )
        fake_redis = FakeRedis()
        lock_key = f"wa:auth:lock:+12015550001"
        import json
        await fake_redis.set(lock_key, lock.model_dump_json(), ex=300)

        # Create new services using this fake_redis
        fm = FakeManager(fake_redis=fake_redis)
        local_auth_service = WhatsAppAuthSessionService(
            connection_manager=fm,
            session_ttl_seconds=settings.whatsapp_session_ttl_minutes * 60,
            fail_threshold=settings.whatsapp_auth_fail_threshold,
            lock_minutes=settings.whatsapp_auth_lock_minutes,
            fail_window_minutes=settings.whatsapp_auth_fail_window_minutes,
        )
        local_session_service = WhatsAppSessionService(
            connection_manager=fm,
            ttl_seconds=settings.whatsapp_session_ttl_minutes * 60,
        )
        facade = _make_facade(console_service, local_session_service, local_auth_service)

        reply = await facade.process_message(
            phone="+12015550001",
            message="hola",
            db=db_session,
        )

        assert "demasiados intentos" in reply.lower() or "espera" in reply.lower() or "intentos" in reply.lower()


class TestAuthSessionActive:
    """When auth session exists, facade delegates to console service."""

    async def test_auth_session_active_returns_menu(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        auth_session_service: WhatsAppAuthSessionService,
    ) -> None:
        """Active master auth session → menu when user asks for it."""
        from datetime import datetime, timezone

        # Manually create auth session
        auth_session = WhatsAppAuthSession(
            phone="+12015550001",
            user_id="00000000-0000-0000-0000-000000000001",
            username="master",
            role="master",
            authenticated_at=datetime.now(timezone.utc),
        )
        await auth_session_service.set_auth_session(auth_session)

        facade = _make_facade(
            console_service,
            session_service,
            auth_session_service,
        )

        reply = await facade.process_message(
            phone="+12015550001",
            message="menu",
            db=None,
        )

        # Must get main menu (not a login prompt)
        assert "Master Console" in reply or "Trackpal" in reply
        assert "usuario" not in reply.lower()

    async def test_auth_session_active_calls_console_service_with_is_master(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        auth_session_service: WhatsAppAuthSessionService,
    ) -> None:
        """Active auth session → process_message called with is_master=True."""
        from datetime import datetime, timezone

        auth_session = WhatsAppAuthSession(
            phone="+12015550001",
            user_id="00000000-0000-0000-0000-000000000001",
            username="master",
            role="master",
            authenticated_at=datetime.now(timezone.utc),
        )
        await auth_session_service.set_auth_session(auth_session)

        # Patch console_service to verify is_master=True
        original_process = console_service.process_message
        called_with_master = None

        async def tracking_process(phone, message, *, is_master=False, session_service=None, tenant_service=None):
            nonlocal called_with_master
            called_with_master = is_master
            return await original_process(phone, message, is_master=is_master, session_service=session_service, tenant_service=tenant_service)

        console_service.process_message = tracking_process

        facade = _make_facade(
            console_service,
            session_service,
            auth_session_service,
        )

        await facade.process_message(
            phone="+12015550001",
            message="menu",
            db=None,
        )

        assert called_with_master is True


class TestAuthSessionExpiry:
    """When auth session expires, user is prompted to login again."""

    async def test_expired_session_menu_returns_username_prompt(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        auth_session_service: WhatsAppAuthSessionService,
    ) -> None:
        """Auth session deleted → 'menu' returns username prompt, not main menu."""
        from datetime import datetime, timezone

        # Create auth session
        auth_session = WhatsAppAuthSession(
            phone="+12015550001",
            user_id="00000000-0000-0000-0000-000000000001",
            username="master",
            role="master",
            authenticated_at=datetime.now(timezone.utc),
        )
        await auth_session_service.set_auth_session(auth_session)

        # Delete the auth session to simulate expiry
        await auth_session_service.clear_auth_session("+12015550001")

        facade = _make_facade(console_service, session_service, auth_session_service)

        reply = await facade.process_message(
            phone="+12015550001",
            message="menu",
            db=None,
        )

        # Must prompt for login, not show main menu
        assert "usuario" in reply.lower() or "iniciar sesión" in reply.lower()
        assert "Ver Tenants" not in reply
        assert "Crear Tenant" not in reply

    async def test_expired_session_option_one_returns_username_prompt(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        auth_session_service: WhatsAppAuthSessionService,
    ) -> None:
        """Auth session deleted → '1' (list tenants) returns username prompt."""
        from datetime import datetime, timezone

        # Create auth session
        auth_session = WhatsAppAuthSession(
            phone="+12015550001",
            user_id="00000000-0000-0000-0000-000000000001",
            username="master",
            role="master",
            authenticated_at=datetime.now(timezone.utc),
        )
        await auth_session_service.set_auth_session(auth_session)

        # Delete auth session to simulate expiry
        await auth_session_service.clear_auth_session("+12015550001")

        facade = _make_facade(console_service, session_service, auth_session_service)

        reply = await facade.process_message(
            phone="+12015550001",
            message="1",
            db=None,
        )

        # Must prompt for login
        assert "usuario" in reply.lower() or "iniciar sesión" in reply.lower()
        assert "1" not in reply  # Should not show tenant list

    async def test_expired_session_clears_conversation_session(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        auth_session_service: WhatsAppAuthSessionService,
    ) -> None:
        """Auth session expired → existing CRUD conversation session is cleared."""
        from datetime import datetime, timezone

        # Create auth session
        auth_session = WhatsAppAuthSession(
            phone="+12015550001",
            user_id="00000000-0000-0000-0000-000000000001",
            username="master",
            role="master",
            authenticated_at=datetime.now(timezone.utc),
        )
        await auth_session_service.set_auth_session(auth_session)

        # Create a conversation session (simulating in-progress CRUD flow)
        conv_session = await session_service.create_session("+12015550001")
        conv_session.flow = "create_tenant"
        conv_session.step = "full_name"
        conv_session.temp_data = {"username": "newuser"}
        await session_service.save_session(conv_session)

        # Delete auth session to simulate expiry
        await auth_session_service.clear_auth_session("+12015550001")

        facade = _make_facade(console_service, session_service, auth_session_service)

        reply = await facade.process_message(
            phone="+12015550001",
            message="hola",
            db=None,
        )

        # Conversation session should now be an auth flow session
        remaining = await session_service.get_session("+12015550001")
        assert remaining is not None
        assert remaining.flow == "auth", "Old CRUD flow should be replaced with auth flow"
        # Reply should be the username prompt
        assert "usuario" in reply.lower()


class TestBypassRegression:
    """No menu/CRUD access without auth session."""

    async def test_option_one_prompts_login_when_no_auth(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        auth_session_service: WhatsAppAuthSessionService,
    ) -> None:
        """No auth session → '1' returns login prompt, not tenant list."""
        facade = _make_facade(console_service, session_service, auth_session_service)

        reply = await facade.process_message(
            phone="+12015550001",
            message="1",
            db=None,
        )

        assert "usuario" in reply.lower() or "iniciar sesión" in reply.lower()
        assert "Ver Tenants" not in reply

    async def test_option_two_prompts_login_when_no_auth(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        auth_session_service: WhatsAppAuthSessionService,
    ) -> None:
        """No auth session → '2' returns login prompt, not create flow."""
        facade = _make_facade(console_service, session_service, auth_session_service)

        reply = await facade.process_message(
            phone="+12015550001",
            message="2",
            db=None,
        )

        assert "usuario" in reply.lower() or "iniciar sesión" in reply.lower()
        assert "crear" not in reply.lower()


class TestPasswordNotPersisted:
    """Password must never be stored in Redis payloads."""

    async def test_password_not_stored_in_auth_session_on_success(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        auth_session_service: WhatsAppAuthSessionService,
        fake_redis: FakeRedis,
        db_session,
    ) -> None:
        """After successful login, auth session JSON must not contain password."""
        from app.models import User, MasterProfile
        from app.core.security import get_password_hash

        user = User(
            username="master",
            password_hash=get_password_hash("master-password"),
            role="master",
        )
        db_session.add(user)
        await db_session.flush()
        db_session.add(MasterProfile(id=user.id, name="Master User", phone="+12015550001"))
        await db_session.commit()

        facade = _make_facade(console_service, session_service, auth_session_service)

        # Complete login flow
        await facade.process_message(phone="+12015550001", message="hola", db=db_session)
        await facade.process_message(phone="+12015550001", message="master", db=db_session)
        await facade.process_message(
            phone="+12015550001",
            message="master-password",
            db=db_session,
        )

        # Inspect all stored values in fake redis—none shall contain the password
        for key, value in fake_redis._store.items():
            if isinstance(value, str):
                assert "master-password" not in value, (
                    f"Password leaked into Redis key '{key}': {value!r}"
                )

    async def test_password_not_stored_in_fail_counter_on_wrong_password(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        auth_session_service: WhatsAppAuthSessionService,
        fake_redis: FakeRedis,
        db_session,
    ) -> None:
        """After wrong password, fail counter JSON must not contain the password."""
        from app.models import User, MasterProfile
        from app.core.security import get_password_hash

        user = User(
            username="master",
            password_hash=get_password_hash("master-password"),
            role="master",
        )
        db_session.add(user)
        await db_session.flush()
        db_session.add(MasterProfile(id=user.id, name="Master User", phone="+12015550001"))
        await db_session.commit()

        facade = _make_facade(console_service, session_service, auth_session_service)

        # Complete up to password step
        await facade.process_message(phone="+12015550001", message="hola", db=db_session)
        await facade.process_message(phone="+12015550001", message="master", db=db_session)

        # Send wrong password
        await facade.process_message(
            phone="+12015550001",
            message="wrong-password",
            db=db_session,
        )

        # Inspect all stored values—none shall contain the password
        for key, value in fake_redis._store.items():
            if isinstance(value, str):
                assert "wrong-password" not in value, (
                    f"Password leaked into Redis key '{key}': {value!r}"
                )


class TestHelpDuringLogin:
    """Help commands during unauthenticated state."""

    async def test_help_during_login(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        auth_session_service: WhatsAppAuthSessionService,
    ) -> None:
        """Sending 'ayuda' during login → login help, not full console help."""
        facade = _make_facade(console_service, session_service, auth_session_service)

        # Start login flow
        await facade.process_message(phone="+9999999999", message="hola", db=None)

        # Send help
        reply = await facade.process_message(
            phone="+9999999999",
            message="ayuda",
            db=None,
        )

        assert "usuario" in reply.lower() or "contraseña" in reply.lower() or "inicio de sesión" in reply.lower()
