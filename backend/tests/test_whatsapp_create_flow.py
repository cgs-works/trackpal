"""Tests for the WhatsApp Master Console create Tenant flow.

Verifies guided Tenant creation: full name, optional email, optional phone,
username, Evolution Instance, password mode, confirmation, and the original
regression where the full-name step returned to main menu instead of
continuing to the email step.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.services.whatsapp_console_service import WhatsAppConsoleService
from app.services.whatsapp_session_service import (
    ConversationSession,
    WhatsAppSessionService,
)


# ---------------------------------------------------------------------------
# Fake Redis — dict-based async double
# ---------------------------------------------------------------------------

class FakeRedis:
    """Minimal in-memory fake for redis.asyncio.Redis."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}
        self._ttls: dict[str, int] = {}

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self._store[key] = value
        if ex is not None:
            self._ttls[key] = ex

    async def delete(self, key: str) -> int:
        self._ttls.pop(key, None)
        return 1 if self._store.pop(key, None) is not None else 0

    async def exists(self, key: str) -> int:
        return 1 if key in self._store else 0

    def get_ttl(self, key: str) -> int | None:
        """Return the TTL set for *key* (test helper)."""
        return self._ttls.get(key)

    def __getattr__(self, name: str) -> Any:
        raise AttributeError(f"FakeRedis does not implement '{name}'")


class FakeManager:
    """Duck-typed connection manager that delegates execute() to FakeRedis."""

    def __init__(self, fake_redis: FakeRedis | None = None) -> None:
        self._redis = fake_redis or FakeRedis()

    async def execute(self, operation_name: str, async_callable: Any) -> Any:
        return await async_callable(self._redis)


# ---------------------------------------------------------------------------
# Fake tenant service with create support
# ---------------------------------------------------------------------------

class FakeTenant:
    """Minimal tenant data object."""

    def __init__(
        self,
        id: str = "new-tenant-id",
        full_name: str = "",
        is_active: bool = True,
        email: str | None = None,
        phone: str | None = None,
        username: str = "",
        evolution_instance_name: str = "",
        password: str | None = None,
    ) -> None:
        self.id = id
        self.full_name = full_name
        self.is_active = is_active
        self.email = email
        self.phone = phone
        self.username = username
        self.evolution_instance_name = evolution_instance_name
        self.password = password


class FakeTenantService:
    """In-memory fake for the tenant data provider.

    Implements ``get_tenants()``, ``get_tenant(id)``, and ``create_tenant()``.
    """

    def __init__(self, existing_usernames: set[str] | None = None) -> None:
        self._tenants: dict[str, FakeTenant] = {}
        self._existing_usernames: set[str] = existing_usernames or set()
        self._existing_phones: set[str] = set()

    async def get_tenants(self) -> list[FakeTenant]:
        return list(self._tenants.values())

    async def get_tenant(self, tenant_id: str) -> FakeTenant | None:
        return self._tenants.get(tenant_id)

    async def get_tenant_by_username(self, username: str) -> FakeTenant | None:
        """Return tenant whose username matches, or None."""
        if username in self._existing_usernames:
            return FakeTenant(username=username)
        return None

    async def create_tenant(self, payload: dict) -> dict:
        """Simulate TenantService.create_tenant.

        Returns:
            Success dict:  {'success': True, 'tenant': FakeTenant, 'auto_password': ...}
            Error dict:    {'success': False, 'error': '...'}
        """
        username = payload.get("username", "")
        phone = payload.get("phone")
        full_name = payload.get("full_name", "")
        evolution_instance_name = payload.get("evolution_instance_name", "")
        password = payload.get("password")

        # Validate required fields
        if not full_name or not full_name.strip():
            return {"success": False, "error": "El nombre completo es obligatorio"}
        if not username or not username.strip():
            return {"success": False, "error": "El nombre de usuario es obligatorio"}
        if not evolution_instance_name or not evolution_instance_name.strip():
            return {
                "success": False,
                "error": "El nombre de instancia Evolution es obligatorio",
            }

        # Duplicate username check
        if username in self._existing_usernames:
            return {"success": False, "error": "Username already registered"}

        # Duplicate phone check
        if phone and phone in self._existing_phones:
            return {"success": False, "error": "Phone already registered"}

        # Password validation
        if password is not None and len(password) < 6:
            return {
                "success": False,
                "error": "Password must be at least 6 characters",
            }

        # Auto-generate password if not provided
        auto_generated = password is None
        if password is None:
            password = "auto-gen-pass-123"

        # Create the tenant
        tenant_id = f"tenant-{username}"
        tenant = FakeTenant(
            id=tenant_id,
            full_name=full_name,
            is_active=True,
            email=payload.get("email"),
            phone=phone,
            username=username,
            evolution_instance_name=evolution_instance_name,
            password=password,
        )
        self._tenants[tenant_id] = tenant
        self._existing_usernames.add(username)
        if phone:
            self._existing_phones.add(phone)

        return {
            "success": True,
            "tenant": tenant,
            "auto_password": password if auto_generated else None,
        }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def fake_redis() -> FakeRedis:
    return FakeRedis()


@pytest.fixture
def session_service(fake_redis: FakeRedis) -> WhatsAppSessionService:
    return WhatsAppSessionService(
        connection_manager=FakeManager(fake_redis=fake_redis),
        ttl_seconds=900,
    )


@pytest.fixture
def console_service() -> WhatsAppConsoleService:
    return WhatsAppConsoleService()


@pytest.fixture
def tenant_service() -> FakeTenantService:
    svc = FakeTenantService(existing_usernames={"existinguser"})
    # Also seed the tenants dict so get_tenants() returns the existing user
    existing = FakeTenant(
        id="existing-id",
        full_name="Existing User",
        username="existinguser",
        evolution_instance_name="inst-existing",
    )
    svc._tenants["existing-id"] = existing
    return svc


# ===========================================================================
# Tests
# ===========================================================================

@pytest.mark.asyncio
class TestCreateFlowStart:
    """Main menu option 2 starts the create tenant flow."""

    async def test_option_2_starts_create_flow(
        self,
        console_service: WhatsAppConsoleService,
    ) -> None:
        reply = await console_service.process_message(
            phone="+10000000000",
            message="2",
            is_master=True,
        )
        # Should NOT return main menu anymore
        assert "Trackpal Master Console" not in reply
        assert "nombre completo" in reply.lower()
        assert "crear" in reply.lower()

    async def test_option_2_creates_session(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        await console_service.process_message(
            phone="+10000000000",
            message="2",
            is_master=True,
            session_service=session_service,
        )
        session = await session_service.get_session("+10000000000")
        assert session is not None
        assert session.flow == "create_tenant"
        assert session.step == "full_name"

    async def test_option_2_without_session_service_still_prompts(
        self,
        console_service: WhatsAppConsoleService,
    ) -> None:
        """Without session persistence, the flow still works statelessly."""
        reply = await console_service.process_message(
            phone="+10000000000",
            message="2",
            is_master=True,
        )
        assert "nombre completo" in reply.lower()


# ===========================================================================
# REGRESSION TEST: Full name → email continuation (the original bug)
# ===========================================================================

@pytest.mark.asyncio
class TestFullNameStepRegression:
    """Critical regression: full-name input must continue to email step.

    This covers the original bug where after sending the full name,
    the reply returned the main menu instead of asking for the email.
    """

    async def _start_create_flow(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        await console_service.process_message(
            phone="+10000000000",
            message="2",
            is_master=True,
            session_service=session_service,
        )

    async def test_full_name_continues_to_email(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        """REGRESSION: After sending full name, response must ask for email,
        NOT return to main menu."""
        await self._start_create_flow(console_service, session_service)

        reply = await console_service.process_message(
            phone="+10000000000",
            message="Juan Pérez",
            is_master=True,
            session_service=session_service,
        )

        # MUST NOT contain main menu
        assert "Trackpal Master Console" not in reply

        # MUST ask for email
        assert "email" in reply.lower() or "correo" in reply.lower()

        # Session must be updated
        session = await session_service.get_session("+10000000000")
        assert session is not None
        assert session.step == "email"
        assert session.temp_data.get("full_name") == "Juan Pérez"

    async def test_full_name_empty_reprompts(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        await self._start_create_flow(console_service, session_service)

        reply = await console_service.process_message(
            phone="+10000000000",
            message="   ",
            is_master=True,
            session_service=session_service,
        )

        # Should reprompt for full name
        assert "nombre completo" in reply.lower()
        session = await session_service.get_session("+10000000000")
        assert session is not None
        assert session.step == "full_name"

    async def test_full_name_with_session_persistence(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        """Verify full name is stored and persists across calls."""
        await self._start_create_flow(console_service, session_service)

        await console_service.process_message(
            phone="+10000000000",
            message="María García",
            is_master=True,
            session_service=session_service,
        )

        session = await session_service.get_session("+10000000000")
        assert session is not None
        assert session.temp_data == {"full_name": "María García"}

    async def test_full_name_wo_session_service_still_works(
        self,
        console_service: WhatsAppConsoleService,
    ) -> None:
        """Without session service, the flow still processes statelessly
        (no state to continue from, but no crash)."""
        # No session service, just start the flow
        reply1 = await console_service.process_message(
            phone="+10000000000",
            message="2",
            is_master=True,
        )
        assert "nombre completo" in reply1.lower()

        # Without session service, a name would still get processed
        reply2 = await console_service.process_message(
            phone="+10000000000",
            message="Juan Pérez",
            is_master=True,
        )
        # Without session, there's no flow state, so it falls to no-flow handling
        assert isinstance(reply2, str)

    async def test_cancel_during_full_name(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        await self._start_create_flow(console_service, session_service)

        reply = await console_service.process_message(
            phone="+10000000000",
            message="cancelar",
            is_master=True,
            session_service=session_service,
        )
        assert "Trackpal Master Console" in reply
        session = await session_service.get_session("+10000000000")
        assert session is None

    async def test_help_during_full_name(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        await self._start_create_flow(console_service, session_service)

        reply = await console_service.process_message(
            phone="+10000000000",
            message="ayuda",
            is_master=True,
            session_service=session_service,
        )
        assert "Ayuda" in reply
        assert "comandos disponibles" in reply

    async def test_full_name_with_punctuation_rejected(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        """Full name with punctuation must be rejected, stay on step."""
        await self._start_create_flow(console_service, session_service)

        reply = await console_service.process_message(
            phone="+10000000000",
            message="Juan Pérez!",
            is_master=True,
            session_service=session_service,
        )
        assert "letras" in reply.lower() or "solo" in reply.lower()
        session = await session_service.get_session("+10000000000")
        assert session is not None
        assert session.step == "full_name"
        assert "full_name" not in session.temp_data

    async def test_full_name_leading_space_normalized(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        """Full name with leading space is stripped by message layer;
        validation accepts stripped value and advances to email step."""
        await self._start_create_flow(console_service, session_service)

        reply = await console_service.process_message(
            phone="+10000000000",
            message="  Juan Pérez",
            is_master=True,
            session_service=session_service,
        )
        # Stripped value is valid, advances to email
        assert "email" in reply.lower() or "correo" in reply.lower()
        session = await session_service.get_session("+10000000000")
        assert session is not None
        assert session.step == "email"
        assert session.temp_data["full_name"] == "Juan Pérez"

    async def test_full_name_trailing_space_normalized(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        """Full name with trailing space is stripped by message layer;
        validation accepts stripped value and advances."""
        await self._start_create_flow(console_service, session_service)

        reply = await console_service.process_message(
            phone="+10000000000",
            message="Juan Pérez ",
            is_master=True,
            session_service=session_service,
        )
        assert "email" in reply.lower() or "correo" in reply.lower()
        session = await session_service.get_session("+10000000000")
        assert session is not None
        assert session.step == "email"
        assert session.temp_data["full_name"] == "Juan Pérez"

    async def test_full_name_multiple_internal_spaces_collapsed(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        """Internal multiple spaces collapse to one in stored value."""
        await self._start_create_flow(console_service, session_service)

        reply = await console_service.process_message(
            phone="+10000000000",
            message="Juan   Pérez",
            is_master=True,
            session_service=session_service,
        )
        assert "email" in reply.lower()
        session = await session_service.get_session("+10000000000")
        assert session is not None
        assert session.temp_data["full_name"] == "Juan Pérez"


# ===========================================================================
# Email step
# ===========================================================================

@pytest.mark.asyncio
class TestEmailStep:
    """Optional email collection with skip semantics."""

    async def _start_and_set_name(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        name: str = "Juan Pérez",
    ) -> None:
        await console_service.process_message(
            phone="+10000000000",
            message="2",
            is_master=True,
            session_service=session_service,
        )
        await console_service.process_message(
            phone="+10000000000",
            message=name,
            is_master=True,
            session_service=session_service,
        )

    async def test_email_transitions_to_phone(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        await self._start_and_set_name(console_service, session_service)

        reply = await console_service.process_message(
            phone="+10000000000",
            message="juan@example.com",
            is_master=True,
            session_service=session_service,
        )
        assert "teléfono" in reply.lower()
        session = await session_service.get_session("+10000000000")
        assert session is not None
        assert session.step == "phone"
        assert session.temp_data["email"] == "juan@example.com"

    async def test_email_skip_with_dash(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        await self._start_and_set_name(console_service, session_service)

        reply = await console_service.process_message(
            phone="+10000000000",
            message="—",
            is_master=True,
            session_service=session_service,
        )
        assert "teléfono" in reply.lower()
        session = await session_service.get_session("+10000000000")
        assert session is not None
        assert session.temp_data["email"] is None

    async def test_email_skip_with_skip_word(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        await self._start_and_set_name(console_service, session_service)

        reply = await console_service.process_message(
            phone="+10000000000",
            message="skip",
            is_master=True,
            session_service=session_service,
        )
        assert "teléfono" in reply.lower()
        session = await session_service.get_session("+10000000000")
        assert session is not None
        assert session.temp_data["email"] is None

    async def test_email_empty_skips(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        await self._start_and_set_name(console_service, session_service)

        reply = await console_service.process_message(
            phone="+10000000000",
            message="",
            is_master=True,
            session_service=session_service,
        )
        assert "teléfono" in reply.lower()
        session = await session_service.get_session("+10000000000")
        assert session is not None
        assert session.temp_data["email"] is None

    async def test_email_invalid_rejected(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        """Invalid email must be rejected, stay on email step,
        preserve previously collected full_name."""
        await self._start_and_set_name(console_service, session_service)

        reply = await console_service.process_message(
            phone="+10000000000",
            message="not-an-email",
            is_master=True,
            session_service=session_service,
        )
        assert "email" in reply.lower() or "correo" in reply.lower()
        session = await session_service.get_session("+10000000000")
        assert session is not None
        assert session.step == "email"
        assert "email" not in session.temp_data
        # Previously collected full_name must be preserved
        assert session.temp_data.get("full_name") == "Juan Pérez"

    async def test_email_with_spaces_rejected(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        """Email with spaces must be rejected."""
        await self._start_and_set_name(console_service, session_service)

        reply = await console_service.process_message(
            phone="+10000000000",
            message="juan @example.com",
            is_master=True,
            session_service=session_service,
        )
        assert "email" in reply.lower() or "correo" in reply.lower()
        session = await session_service.get_session("+10000000000")
        assert session is not None
        assert session.step == "email"

    async def test_email_normalized(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        """Valid email with mixed case is normalized to lowercase."""
        await self._start_and_set_name(console_service, session_service)

        reply = await console_service.process_message(
            phone="+10000000000",
            message="Juan.Perez@Example.COM",
            is_master=True,
            session_service=session_service,
        )
        assert "teléfono" in reply.lower()
        session = await session_service.get_session("+10000000000")
        assert session is not None
        assert session.temp_data["email"] == "Juan.Perez@example.com"

    async def test_email_invalid_then_correction_advances(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        """Invalid email stays on step with prior fields preserved;
        corrected email advances to phone step."""
        await self._start_and_set_name(console_service, session_service)

        # Send invalid email
        reply = await console_service.process_message(
            phone="+10000000000",
            message="not-an-email",
            is_master=True,
            session_service=session_service,
        )
        assert "email" in reply.lower() or "correo" in reply.lower()

        session = await session_service.get_session("+10000000000")
        assert session is not None
        assert session.step == "email"
        assert "email" not in session.temp_data
        # Prior full_name preserved
        assert session.temp_data.get("full_name") == "Juan Pérez"

        # Send corrected email
        reply = await console_service.process_message(
            phone="+10000000000",
            message="juan.corrected@example.com",
            is_master=True,
            session_service=session_service,
        )
        assert "teléfono" in reply.lower()

        session = await session_service.get_session("+10000000000")
        assert session is not None
        assert session.step == "phone"
        assert session.temp_data["email"] == "juan.corrected@example.com"
        # full_name still preserved
        assert session.temp_data.get("full_name") == "Juan Pérez"


# ===========================================================================
# Phone step
# ===========================================================================

@pytest.mark.asyncio
class TestPhoneStep:
    """Optional phone collection with skip semantics."""

    async def _start_through_email(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        await console_service.process_message(
            phone="+10000000000",
            message="2",
            is_master=True,
            session_service=session_service,
        )
        await console_service.process_message(
            phone="+10000000000",
            message="Juan Pérez",
            is_master=True,
            session_service=session_service,
        )
        await console_service.process_message(
            phone="+10000000000",
            message="juan@example.com",
            is_master=True,
            session_service=session_service,
        )

    async def test_phone_transitions_to_username(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        await self._start_through_email(console_service, session_service)

        reply = await console_service.process_message(
            phone="+10000000000",
            message="+525512345678",
            is_master=True,
            session_service=session_service,
        )
        assert "usuario" in reply.lower()
        session = await session_service.get_session("+10000000000")
        assert session is not None
        assert session.step == "username"
        # Phone is stored canonical digits-only (no +)
        assert session.temp_data["phone"] == "525512345678"

    async def test_phone_skip_with_dash(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        await self._start_through_email(console_service, session_service)

        reply = await console_service.process_message(
            phone="+10000000000",
            message="—",
            is_master=True,
            session_service=session_service,
        )
        assert "usuario" in reply.lower()
        session = await session_service.get_session("+10000000000")
        assert session is not None
        assert session.temp_data["phone"] is None

    async def test_phone_empty_skips(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        await self._start_through_email(console_service, session_service)

        reply = await console_service.process_message(
            phone="+10000000000",
            message="",
            is_master=True,
            session_service=session_service,
        )
        assert "usuario" in reply.lower()
        session = await session_service.get_session("+10000000000")
        assert session is not None
        assert session.temp_data["phone"] is None

    async def test_phone_invalid_rejected(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        """Non-numeric phone must be rejected, stay on phone step,
        preserve previously collected email."""
        await self._start_through_email(console_service, session_service)

        reply = await console_service.process_message(
            phone="+10000000000",
            message="abc",
            is_master=True,
            session_service=session_service,
        )
        assert "teléfono" in reply.lower() or "telefono" in reply.lower()
        session = await session_service.get_session("+10000000000")
        assert session is not None
        assert session.step == "phone"
        assert "phone" not in session.temp_data
        # Previously collected email must be preserved
        assert session.temp_data.get("email") == "juan@example.com"

    async def test_phone_no_country_code_rejected(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        """Phone without international country code must be rejected."""
        await self._start_through_email(console_service, session_service)

        reply = await console_service.process_message(
            phone="+10000000000",
            message="1234567890",
            is_master=True,
            session_service=session_service,
        )
        assert "teléfono" in reply.lower() or "internacional" in reply.lower()
        session = await session_service.get_session("+10000000000")
        assert session is not None
        assert session.step == "phone"

    async def test_phone_canonical_digits_only(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        """Valid phone with + is stored as digits-only."""
        await self._start_through_email(console_service, session_service)

        reply = await console_service.process_message(
            phone="+10000000000",
            message="+525512345678",
            is_master=True,
            session_service=session_service,
        )
        assert "usuario" in reply.lower()
        session = await session_service.get_session("+10000000000")
        assert session is not None
        # Stored canonical digits-only (no +)
        assert session.temp_data["phone"] == "525512345678"

    async def test_phone_without_plus_stored_digits_only(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        """Valid phone without + prefix is stored as digits-only."""
        await self._start_through_email(console_service, session_service)

        reply = await console_service.process_message(
            phone="+10000000000",
            message="525512345678",
            is_master=True,
            session_service=session_service,
        )
        assert "usuario" in reply.lower()
        session = await session_service.get_session("+10000000000")
        assert session is not None
        assert session.temp_data["phone"] == "525512345678"


# ===========================================================================
# Username step
# ===========================================================================

@pytest.mark.asyncio
class TestUsernameStep:
    """Username collection with duplicate validation."""

    async def _start_through_phone(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        phone: str = "+525512345678",
    ) -> None:
        await console_service.process_message(
            phone="+10000000000",
            message="2",
            is_master=True,
            session_service=session_service,
        )
        await console_service.process_message(
            phone="+10000000000",
            message="Juan Pérez",
            is_master=True,
            session_service=session_service,
        )
        await console_service.process_message(
            phone="+10000000000",
            message="juan@example.com",
            is_master=True,
            session_service=session_service,
        )
        await console_service.process_message(
            phone="+10000000000",
            message=phone,
            is_master=True,
            session_service=session_service,
        )

    async def test_username_transitions_to_evolution_instance(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        await self._start_through_phone(console_service, session_service)

        reply = await console_service.process_message(
            phone="+10000000000",
            message="juanperez",
            is_master=True,
            session_service=session_service,
        )
        assert "evolution" in reply.lower()
        session = await session_service.get_session("+10000000000")
        assert session is not None
        assert session.step == "evolution_instance"
        assert session.temp_data["username"] == "juanperez"

    async def test_username_duplicate_error(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        await self._start_through_phone(console_service, session_service)

        reply = await console_service.process_message(
            phone="+10000000000",
            message="existinguser",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )
        # Should show error about duplicate username
        assert "registrado" in reply.lower() or "duplicate" in reply.lower() or "already" in reply.lower()
        # Should NOT reset flow — stay on username step
        session = await session_service.get_session("+10000000000")
        assert session is not None
        assert session.step == "username"
        # temp_data should NOT have username set
        assert "username" not in session.temp_data
        # Prior collected fields must be preserved
        assert session.temp_data.get("full_name") == "Juan Pérez"
        assert session.temp_data.get("email") == "juan@example.com"
        assert session.temp_data.get("phone") == "525512345678"

    async def test_username_duplicate_then_valid(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        """After duplicate error, user can send a different valid username."""
        await self._start_through_phone(console_service, session_service)

        # Send duplicate username
        await console_service.process_message(
            phone="+10000000000",
            message="existinguser",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )

        # Send valid username
        reply = await console_service.process_message(
            phone="+10000000000",
            message="newvaliduser",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )
        assert "evolution" in reply.lower()
        session = await session_service.get_session("+10000000000")
        assert session is not None
        assert session.step == "evolution_instance"
        assert session.temp_data["username"] == "newvaliduser"

    async def test_username_empty_reprompts(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        # Progress to username step manually
        await console_service.process_message(
            phone="+10000000000", message="2", is_master=True,
            session_service=session_service,
        )
        await console_service.process_message(
            phone="+10000000000", message="Juan Pérez", is_master=True,
            session_service=session_service,
        )
        await console_service.process_message(
            phone="+10000000000", message="juan@example.com", is_master=True,
            session_service=session_service,
        )
        await console_service.process_message(
            phone="+10000000000", message="—", is_master=True,
            session_service=session_service,
        )

        reply = await console_service.process_message(
            phone="+10000000000",
            message="   ",
            is_master=True,
            session_service=session_service,
        )
        assert "usuario" in reply.lower()
        session = await session_service.get_session("+10000000000")
        assert session is not None
        assert session.step == "username"

    # ------------------------------------------------------------------
    # REGRESSION: Invalid username patterns from PRD
    # ------------------------------------------------------------------

    async def _progress_to_username(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        """Helper: progress to the username step with basic valid data."""
        await console_service.process_message(
            phone="+10000000000", message="2", is_master=True,
            session_service=session_service,
        )
        await console_service.process_message(
            phone="+10000000000", message="Test User", is_master=True,
            session_service=session_service,
        )
        await console_service.process_message(
            phone="+10000000000", message="test@example.com", is_master=True,
            session_service=session_service,
        )
        await console_service.process_message(
            phone="+10000000000", message="—", is_master=True,
            session_service=session_service,
        )

    async def test_username_slash_menu_rejected(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        """REGRESSION: '/menu' must be rejected as username, stay on step."""
        await self._progress_to_username(console_service, session_service)

        reply = await console_service.process_message(
            phone="+10000000000",
            message="/menu",
            is_master=True,
            session_service=session_service,
        )
        assert "letra" in reply.lower() or "minúscula" in reply.lower()
        session = await session_service.get_session("+10000000000")
        assert session is not None
        assert session.step == "username"
        assert "username" not in session.temp_data

    async def test_username_zero_rejected(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        """REGRESSION: '0' is a global reset command; returns to menu
        instead of being accepted as username."""
        await self._progress_to_username(console_service, session_service)

        reply = await console_service.process_message(
            phone="+10000000000",
            message="0",
            is_master=True,
            session_service=session_service,
        )
        # '0' triggers global reset, returns main menu
        assert "Trackpal Master Console" in reply
        # Session cleared
        session = await session_service.get_session("+10000000000")
        assert session is None

    async def test_username_uppercase_rejected(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        """REGRESSION: Uppercase username must be rejected."""
        await self._progress_to_username(console_service, session_service)

        reply = await console_service.process_message(
            phone="+10000000000",
            message="TestUser",
            is_master=True,
            session_service=session_service,
        )
        assert "letra" in reply.lower() or "minúscula" in reply.lower()
        session = await session_service.get_session("+10000000000")
        assert session is not None
        assert session.step == "username"

    async def test_username_with_spaces_rejected(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        """REGRESSION: Username with spaces must be rejected."""
        await self._progress_to_username(console_service, session_service)

        reply = await console_service.process_message(
            phone="+10000000000",
            message="hola mundo",
            is_master=True,
            session_service=session_service,
        )
        assert "letra" in reply.lower() or "minúscula" in reply.lower()
        session = await session_service.get_session("+10000000000")
        assert session is not None
        assert session.step == "username"

    async def test_username_with_punctuation_rejected(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        """REGRESSION: Username with punctuation must be rejected."""
        await self._progress_to_username(console_service, session_service)

        reply = await console_service.process_message(
            phone="+10000000000",
            message="admin!",
            is_master=True,
            session_service=session_service,
        )
        assert "letra" in reply.lower() or "minúscula" in reply.lower()
        session = await session_service.get_session("+10000000000")
        assert session is not None
        assert session.step == "username"

    async def test_username_too_long_rejected(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        """Username exceeding 20 chars must be rejected."""
        await self._progress_to_username(console_service, session_service)

        reply = await console_service.process_message(
            phone="+10000000000",
            message="abcdefghij1234567890extra",
            is_master=True,
            session_service=session_service,
        )
        assert "20" in reply or "máximo" in reply.lower() or "larga" in reply.lower()
        session = await session_service.get_session("+10000000000")
        assert session is not None
        assert session.step == "username"

    async def test_username_starts_with_number_rejected(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        """Username starting with digit must be rejected."""
        await self._progress_to_username(console_service, session_service)

        reply = await console_service.process_message(
            phone="+10000000000",
            message="1testuser",
            is_master=True,
            session_service=session_service,
        )
        assert "letra" in reply.lower() or "minúscula" in reply.lower()
        session = await session_service.get_session("+10000000000")
        assert session is not None
        assert session.step == "username"

    async def test_username_cancelar_returns_to_menu(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        """REGRESSION: 'cancelar' triggers global reset, returns to menu,
        NOT persisted as username."""
        await self._progress_to_username(console_service, session_service)

        reply = await console_service.process_message(
            phone="+10000000000",
            message="cancelar",
            is_master=True,
            session_service=session_service,
        )
        # Global reset returns main menu
        assert "Trackpal Master Console" in reply
        # Session cleared
        session = await session_service.get_session("+10000000000")
        assert session is None

    async def test_username_invalid_syntax_does_not_persist_in_temp_data(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        """REGRESSION: /menu is rejected by syntax validation, not stored."""
        await self._progress_to_username(console_service, session_service)

        await console_service.process_message(
            phone="+10000000000",
            message="/menu",
            is_master=True,
            session_service=session_service,
        )

        # username must not be in temp_data
        session = await session_service.get_session("+10000000000")
        assert session is not None
        assert "username" not in session.temp_data
        # Prior fields must remain intact
        assert session.temp_data.get("full_name") == "Test User"
        assert session.temp_data.get("email") == "test@example.com"

    async def test_invalid_username_does_not_call_duplicate_check(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        """Invalid syntax must NOT trigger duplicate lookup."""
        await self._progress_to_username(console_service, session_service)

        # '/menu' is syntactically invalid, not a duplicate
        reply = await console_service.process_message(
            phone="+10000000000",
            message="/menu",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )
        # Should show syntax error, NOT duplicate error
        assert "letra" in reply.lower() or "minúscula" in reply.lower()
        assert "registrado" not in reply.lower()
        session = await session_service.get_session("+10000000000")
        assert session is not None
        assert session.step == "username"

    async def test_valid_username_with_underscore_accepted(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        """Username with underscore is valid."""
        await self._progress_to_username(console_service, session_service)

        reply = await console_service.process_message(
            phone="+10000000000",
            message="test_user",
            is_master=True,
            session_service=session_service,
        )
        assert "evolution" in reply.lower()
        session = await session_service.get_session("+10000000000")
        assert session is not None
        assert session.step == "evolution_instance"
        assert session.temp_data["username"] == "test_user"


# ===========================================================================
# Evolution Instance step
# ===========================================================================

@pytest.mark.asyncio
class TestEvolutionInstanceStep:
    """Evolution Instance name collection."""

    async def _start_through_username(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service=None,
    ) -> None:
        await console_service.process_message(
            phone="+10000000000",
            message="2",
            is_master=True,
            session_service=session_service,
        )
        await console_service.process_message(
            phone="+10000000000",
            message="Juan Pérez",
            is_master=True,
            session_service=session_service,
        )
        await console_service.process_message(
            phone="+10000000000",
            message="juan@example.com",
            is_master=True,
            session_service=session_service,
        )
        await console_service.process_message(
            phone="+10000000000",
            message="+525512345678",
            is_master=True,
            session_service=session_service,
        )
        await console_service.process_message(
            phone="+10000000000",
            message="juanperez",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )

    async def test_evolution_instance_transitions_to_password_mode(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        await self._start_through_username(console_service, session_service)

        reply = await console_service.process_message(
            phone="+10000000000",
            message="inst-juan",
            is_master=True,
            session_service=session_service,
        )
        assert "contraseña" in reply.lower() or "password" in reply.lower()
        session = await session_service.get_session("+10000000000")
        assert session is not None
        assert session.step == "password_mode"
        assert session.temp_data["evolution_instance_name"] == "inst-juan"

    async def test_evolution_instance_empty_reprompts(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        await self._start_through_username(console_service, session_service)

        reply = await console_service.process_message(
            phone="+10000000000",
            message="",
            is_master=True,
            session_service=session_service,
        )
        assert "evolution" in reply.lower()
        session = await session_service.get_session("+10000000000")
        assert session is not None
        assert session.step == "evolution_instance"


# ===========================================================================
# Password mode step
# ===========================================================================

@pytest.mark.asyncio
class TestPasswordModeStep:
    """Password mode selection: automatic vs manual."""

    async def _start_through_instance(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service=None,
    ) -> None:
        await console_service.process_message(
            phone="+10000000000",
            message="2",
            is_master=True,
            session_service=session_service,
        )
        await console_service.process_message(
            phone="+10000000000",
            message="Juan Pérez",
            is_master=True,
            session_service=session_service,
        )
        await console_service.process_message(
            phone="+10000000000",
            message="juan@example.com",
            is_master=True,
            session_service=session_service,
        )
        await console_service.process_message(
            phone="+10000000000",
            message="+525512345678",
            is_master=True,
            session_service=session_service,
        )
        await console_service.process_message(
            phone="+10000000000",
            message="juanperez",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )
        await console_service.process_message(
            phone="+10000000000",
            message="inst-juan",
            is_master=True,
            session_service=session_service,
        )

    async def test_auto_password_transitions_to_confirm(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        await self._start_through_instance(console_service, session_service)

        reply = await console_service.process_message(
            phone="+10000000000",
            message="1",
            is_master=True,
            session_service=session_service,
        )
        # Should show summary with CONFIRMAR
        assert "CONFIRMAR" in reply or "confirmar" in reply
        assert "Juan Pérez" in reply
        session = await session_service.get_session("+10000000000")
        assert session is not None
        assert session.step == "confirm"
        assert session.temp_data.get("password_mode") == "auto"

    async def test_manual_password_transitions_to_password_entry(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        await self._start_through_instance(console_service, session_service)

        reply = await console_service.process_message(
            phone="+10000000000",
            message="2",
            is_master=True,
            session_service=session_service,
        )
        # Should ask for manual password
        assert "contraseña" in reply.lower()
        assert "manualmente" in reply.lower() or "manual" in reply.lower()
        session = await session_service.get_session("+10000000000")
        assert session is not None
        assert session.step == "manual_password"

    async def test_invalid_password_mode_reprompts(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        await self._start_through_instance(console_service, session_service)

        reply = await console_service.process_message(
            phone="+10000000000",
            message="3",
            is_master=True,
            session_service=session_service,
        )
        assert "contraseña" in reply.lower() or "password" in reply.lower()
        session = await session_service.get_session("+10000000000")
        assert session is not None
        assert session.step == "password_mode"


# ===========================================================================
# Manual password step
# ===========================================================================

@pytest.mark.asyncio
class TestManualPasswordStep:
    """Manual password entry after selecting manual mode."""

    async def _start_through_mode(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service=None,
    ) -> None:
        await console_service.process_message(
            phone="+10000000000",
            message="2",
            is_master=True,
            session_service=session_service,
        )
        await console_service.process_message(
            phone="+10000000000",
            message="Juan Pérez",
            is_master=True,
            session_service=session_service,
        )
        await console_service.process_message(
            phone="+10000000000",
            message="juan@example.com",
            is_master=True,
            session_service=session_service,
        )
        await console_service.process_message(
            phone="+10000000000",
            message="+525512345678",
            is_master=True,
            session_service=session_service,
        )
        await console_service.process_message(
            phone="+10000000000",
            message="juanperez",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )
        await console_service.process_message(
            phone="+10000000000",
            message="inst-juan",
            is_master=True,
            session_service=session_service,
        )
        await console_service.process_message(
            phone="+10000000000",
            message="2",
            is_master=True,
            session_service=session_service,
        )

    async def test_manual_password_transitions_to_confirm(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        await self._start_through_mode(console_service, session_service)

        reply = await console_service.process_message(
            phone="+10000000000",
            message="MiPassword123",
            is_master=True,
            session_service=session_service,
        )
        # Should show summary with CONFIRMAR
        assert "CONFIRMAR" in reply or "confirmar" in reply
        assert "Juan Pérez" in reply
        session = await session_service.get_session("+10000000000")
        assert session is not None
        assert session.step == "confirm"
        assert session.temp_data.get("password") == "MiPassword123"

    async def test_manual_password_short_reprompts(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        await self._start_through_mode(console_service, session_service)

        reply = await console_service.process_message(
            phone="+10000000000",
            message="abc12",
            is_master=True,
            session_service=session_service,
        )
        # Should show error and reprompt
        assert "6 caracteres" in reply.lower() or "corta" in reply.lower() or "password" in reply.lower()
        session = await session_service.get_session("+10000000000")
        assert session is not None
        assert session.step == "manual_password"

    async def test_manual_password_empty_reprompts(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        await self._start_through_mode(console_service, session_service)

        reply = await console_service.process_message(
            phone="+10000000000",
            message="   ",
            is_master=True,
            session_service=session_service,
        )
        assert "contraseña" in reply.lower()
        session = await session_service.get_session("+10000000000")
        assert session is not None
        assert session.step == "manual_password"


# ===========================================================================
# Confirmation step
# ===========================================================================

@pytest.mark.asyncio
class TestConfirmationStep:
    """Tenant creation summary and CONFIRMAR."""

    async def _start_through_auto(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service=None,
    ) -> None:
        await console_service.process_message(
            phone="+10000000000",
            message="2",
            is_master=True,
            session_service=session_service,
        )
        await console_service.process_message(
            phone="+10000000000",
            message="Juan Pérez",
            is_master=True,
            session_service=session_service,
        )
        await console_service.process_message(
            phone="+10000000000",
            message="juan@example.com",
            is_master=True,
            session_service=session_service,
        )
        await console_service.process_message(
            phone="+10000000000",
            message="+525512345678",
            is_master=True,
            session_service=session_service,
        )
        await console_service.process_message(
            phone="+10000000000",
            message="juanperez",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )
        await console_service.process_message(
            phone="+10000000000",
            message="inst-juan",
            is_master=True,
            session_service=session_service,
        )
        await console_service.process_message(
            phone="+10000000000",
            message="1",
            is_master=True,
            session_service=session_service,
        )

    async def test_summary_shows_all_fields(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        await self._start_through_auto(console_service, session_service)

        # The summary is already the reply from selecting auto mode
        # But we can verify the session state
        session = await session_service.get_session("+10000000000")
        assert session is not None
        assert session.step == "confirm"
        assert session.temp_data["full_name"] == "Juan Pérez"
        assert session.temp_data["email"] == "juan@example.com"
        # Phone stored canonical digits-only (no + prefix)
        assert session.temp_data["phone"] == "525512345678"
        assert session.temp_data["username"] == "juanperez"
        assert session.temp_data["evolution_instance_name"] == "inst-juan"
        assert session.temp_data["password_mode"] == "auto"

    async def test_confirmar_creates_tenant(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        await self._start_through_auto(
            console_service, session_service, tenant_service
        )

        reply = await console_service.process_message(
            phone="+10000000000",
            message="CONFIRMAR",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )

        # Should show success message
        assert "creado" in reply.lower() or "éxito" in reply.lower() or "exitoso" in reply.lower()
        assert "Juan Pérez" in reply

        # Session should be cleared after success
        session = await session_service.get_session("+10000000000")
        assert session is None

        # Tenant should actually be created in the fake service
        # (we can check by looking for the tenant)
        tenants = await tenant_service.get_tenants()
        usernames = [t.username for t in tenants]
        assert "juanperez" in usernames

    async def test_confirmar_case_insensitive(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        await self._start_through_auto(
            console_service, session_service, tenant_service
        )

        reply = await console_service.process_message(
            phone="+10000000000",
            message="confirmar",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )

        assert "creado" in reply.lower() or "éxito" in reply.lower()

    async def test_cancel_during_confirm(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        await self._start_through_auto(console_service, session_service)

        reply = await console_service.process_message(
            phone="+10000000000",
            message="cancelar",
            is_master=True,
            session_service=session_service,
        )
        assert "Trackpal Master Console" in reply
        session = await session_service.get_session("+10000000000")
        assert session is None

    async def test_invalid_confirmation_reprompts(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        await self._start_through_auto(console_service, session_service)

        reply = await console_service.process_message(
            phone="+10000000000",
            message="no",
            is_master=True,
            session_service=session_service,
        )
        assert "CONFIRMAR" in reply or "confirmar" in reply
        session = await session_service.get_session("+10000000000")
        assert session is not None
        assert session.step == "confirm"


# ===========================================================================
# Full flow success
# ===========================================================================

@pytest.mark.asyncio
class TestFullCreateFlow:
    """End-to-end create flow with all options."""

    async def test_full_flow_auto_password(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        """Complete flow with auto-generated password."""
        # Step 1: Start
        reply = await console_service.process_message(
            phone="+10000000000",
            message="2",
            is_master=True,
            session_service=session_service,
        )
        assert "nombre completo" in reply.lower()

        # Step 2: Full name
        reply = await console_service.process_message(
            phone="+10000000000",
            message="María García",
            is_master=True,
            session_service=session_service,
        )
        assert "email" in reply.lower()
        assert "Trackpal Master Console" not in reply  # REGRESSION CHECK

        # Step 3: Email (optional, skip)
        reply = await console_service.process_message(
            phone="+10000000000",
            message="—",
            is_master=True,
            session_service=session_service,
        )
        assert "teléfono" in reply.lower()

        # Step 4: Phone (optional, provide)
        reply = await console_service.process_message(
            phone="+10000000000",
            message="+529999999999",
            is_master=True,
            session_service=session_service,
        )
        assert "usuario" in reply.lower()

        # Step 5: Username
        reply = await console_service.process_message(
            phone="+10000000000",
            message="mariagarcia",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )
        assert "evolution" in reply.lower()

        # Step 6: Evolution Instance
        reply = await console_service.process_message(
            phone="+10000000000",
            message="inst-maria",
            is_master=True,
            session_service=session_service,
        )
        assert "contraseña" in reply.lower() or "password" in reply.lower()

        # Step 7: Password mode (auto)
        reply = await console_service.process_message(
            phone="+10000000000",
            message="1",
            is_master=True,
            session_service=session_service,
        )
        assert "CONFIRMAR" in reply or "confirmar" in reply
        assert "María García" in reply

        # Step 8: Confirm
        reply = await console_service.process_message(
            phone="+10000000000",
            message="CONFIRMAR",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )
        assert "creado" in reply.lower() or "éxito" in reply.lower()

        # Session cleared
        session = await session_service.get_session("+10000000000")
        assert session is None

    async def test_full_flow_manual_password(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        """Complete flow with manual password entry."""
        # Step 1: Start
        reply = await console_service.process_message(
            phone="+10000000000",
            message="2",
            is_master=True,
            session_service=session_service,
        )
        assert "nombre completo" in reply.lower()

        # Step 2: Full name
        reply = await console_service.process_message(
            phone="+10000000000",
            message="Carlos López",
            is_master=True,
            session_service=session_service,
        )
        assert "email" in reply.lower()
        assert "Trackpal Master Console" not in reply  # REGRESSION CHECK

        # Step 3: Email
        reply = await console_service.process_message(
            phone="+10000000000",
            message="carlos@example.com",
            is_master=True,
            session_service=session_service,
        )
        assert "teléfono" in reply.lower()

        # Step 4: Phone (skip)
        reply = await console_service.process_message(
            phone="+10000000000",
            message="—",
            is_master=True,
            session_service=session_service,
        )
        assert "usuario" in reply.lower()

        # Step 5: Username
        reply = await console_service.process_message(
            phone="+10000000000",
            message="carloslopez",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )
        assert "evolution" in reply.lower()

        # Step 6: Evolution Instance
        reply = await console_service.process_message(
            phone="+10000000000",
            message="inst-carlos",
            is_master=True,
            session_service=session_service,
        )
        assert "contraseña" in reply.lower()

        # Step 7: Password mode (manual)
        reply = await console_service.process_message(
            phone="+10000000000",
            message="2",
            is_master=True,
            session_service=session_service,
        )
        assert "manualmente" in reply.lower() or "manual" in reply.lower()

        # Step 8: Manual password
        reply = await console_service.process_message(
            phone="+10000000000",
            message="MiSegura2024!",
            is_master=True,
            session_service=session_service,
        )
        assert "CONFIRMAR" in reply or "confirmar" in reply
        assert "Carlos López" in reply

        # Step 9: Confirm
        reply = await console_service.process_message(
            phone="+10000000000",
            message="CONFIRMAR",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )
        assert "creado" in reply.lower() or "éxito" in reply.lower()

        # Session cleared
        session = await session_service.get_session("+10000000000")
        assert session is None

    async def test_duplicate_username_then_success(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        """Duplicate username error keeps user on username step, then success."""
        await console_service.process_message(
            phone="+10000000000",
            message="2",
            is_master=True,
            session_service=session_service,
        )
        await console_service.process_message(
            phone="+10000000000",
            message="Test User",
            is_master=True,
            session_service=session_service,
        )
        await console_service.process_message(
            phone="+10000000000",
            message="test@example.com",
            is_master=True,
            session_service=session_service,
        )
        await console_service.process_message(
            phone="+10000000000",
            message="—",
            is_master=True,
            session_service=session_service,
        )

        # Send duplicate username
        reply = await console_service.process_message(
            phone="+10000000000",
            message="existinguser",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )
        assert "registrado" in reply.lower() or "duplicate" in reply.lower()

        # Send valid username
        reply = await console_service.process_message(
            phone="+10000000000",
            message="uniqueuser",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )
        assert "evolution" in reply.lower()

        # Continue with rest of flow
        await console_service.process_message(
            phone="+10000000000",
            message="inst-unique",
            is_master=True,
            session_service=session_service,
        )
        await console_service.process_message(
            phone="+10000000000",
            message="1",
            is_master=True,
            session_service=session_service,
        )
        reply = await console_service.process_message(
            phone="+10000000000",
            message="CONFIRMAR",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )
        assert "creado" in reply.lower() or "éxito" in reply.lower()

    async def test_duplicate_phone_during_creation(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        """Duplicate phone error during creation is handled."""
        # First, create a tenant with a phone (canonical digits-only)
        tenant_service._existing_phones.add("525511111111")

        await console_service.process_message(
            phone="+10000000000",
            message="2",
            is_master=True,
            session_service=session_service,
        )
        await console_service.process_message(
            phone="+10000000000",
            message="Test User",
            is_master=True,
            session_service=session_service,
        )
        await console_service.process_message(
            phone="+10000000000",
            message="test@example.com",
            is_master=True,
            session_service=session_service,
        )
        await console_service.process_message(
            phone="+10000000000",
            message="+525511111111",
            is_master=True,
            session_service=session_service,
        )
        await console_service.process_message(
            phone="+10000000000",
            message="newuser",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )
        await console_service.process_message(
            phone="+10000000000",
            message="inst-new",
            is_master=True,
            session_service=session_service,
        )
        await console_service.process_message(
            phone="+10000000000",
            message="1",
            is_master=True,
            session_service=session_service,
        )

        # Confirm with duplicate phone
        reply = await console_service.process_message(
            phone="+10000000000",
            message="CONFIRMAR",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )
        # Should show error about duplicate phone
        assert "ya registrado" in reply.lower() or "duplicate" in reply.lower() or "phone" in reply.lower()
        # Session might still exist - let the user know what happened
        # Actually, since the duplicate phone was collected at the phone step
        # and the validation happens at creation time, we need to handle this.
        # But this depends on implementation - either validate at phone step
        # or at confirmation time.
        session = await session_service.get_session("+10000000000")
        assert session is not None
        assert session.step == WhatsAppConsoleService.CREATE_STEP_PHONE
        assert session.temp_data["username"] == "newuser"

        # Correct phone and complete without restarting.
        await console_service.process_message(
            phone="+10000000000",
            message="+529999999999",
            is_master=True,
            session_service=session_service,
        )
        await console_service.process_message(
            phone="+10000000000",
            message="fixeduser",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )
        await console_service.process_message(
            phone="+10000000000",
            message="inst-fixed",
            is_master=True,
            session_service=session_service,
        )
        await console_service.process_message(
            phone="+10000000000",
            message="1",
            is_master=True,
            session_service=session_service,
        )
        reply = await console_service.process_message(
            phone="+10000000000",
            message="CONFIRMAR",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )
        assert "creado" in reply.lower() or "éxito" in reply.lower()

    async def test_create_time_duplicate_username_returns_to_username_step(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        """Create-time duplicate username can be corrected in-flow."""
        await console_service.process_message(
            phone="+10000000000", message="2", is_master=True,
            session_service=session_service,
        )
        await console_service.process_message(
            phone="+10000000000", message="Test User", is_master=True,
            session_service=session_service,
        )
        await console_service.process_message(
            phone="+10000000000", message="test@example.com", is_master=True,
            session_service=session_service,
        )
        await console_service.process_message(
            phone="+10000000000", message="—", is_master=True,
            session_service=session_service,
        )
        await console_service.process_message(
            phone="+10000000000", message="raceuser", is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )
        await console_service.process_message(
            phone="+10000000000", message="inst-race", is_master=True,
            session_service=session_service,
        )
        await console_service.process_message(
            phone="+10000000000", message="1", is_master=True,
            session_service=session_service,
        )
        tenant_service._existing_usernames.add("raceuser")

        reply = await console_service.process_message(
            phone="+10000000000", message="CONFIRMAR", is_master=True,
            session_service=session_service, tenant_service=tenant_service,
        )

        assert "username" in reply.lower() or "usuario" in reply.lower()
        session = await session_service.get_session("+10000000000")
        assert session is not None
        assert session.step == WhatsAppConsoleService.CREATE_STEP_USERNAME
        assert session.temp_data["full_name"] == "Test User"

        await console_service.process_message(
            phone="+10000000000", message="raceuser2", is_master=True,
            session_service=session_service, tenant_service=tenant_service,
        )
        await console_service.process_message(
            phone="+10000000000", message="inst-race2", is_master=True,
            session_service=session_service,
        )
        await console_service.process_message(
            phone="+10000000000", message="1", is_master=True,
            session_service=session_service,
        )
        reply = await console_service.process_message(
            phone="+10000000000", message="CONFIRMAR", is_master=True,
            session_service=session_service, tenant_service=tenant_service,
        )
        assert "creado" in reply.lower() or "éxito" in reply.lower()

    async def test_auto_password_shows_generated_password(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        """Auto-generated password is shown in the success message."""
        await console_service.process_message(
            phone="+10000000000",
            message="2",
            is_master=True,
            session_service=session_service,
        )
        await console_service.process_message(
            phone="+10000000000",
            message="Ana Torres",
            is_master=True,
            session_service=session_service,
        )
        await console_service.process_message(
            phone="+10000000000",
            message="ana@example.com",
            is_master=True,
            session_service=session_service,
        )
        await console_service.process_message(
            phone="+10000000000",
            message="—",
            is_master=True,
            session_service=session_service,
        )
        await console_service.process_message(
            phone="+10000000000",
            message="anatorres",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )
        await console_service.process_message(
            phone="+10000000000",
            message="inst-ana",
            is_master=True,
            session_service=session_service,
        )
        await console_service.process_message(
            phone="+10000000000",
            message="1",
            is_master=True,
            session_service=session_service,
        )

        reply = await console_service.process_message(
            phone="+10000000000",
            message="CONFIRMAR",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )
        # Auto-generated password should be shown (from FakeTenantService: "auto-gen-pass-123")
        assert "contraseña" in reply.lower() or "password" in reply.lower()
        # The actual auto password
        assert "auto-gen-pass-123" in reply

    async def test_cancellation_during_flow_clears_session(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        """Cancel at any step clears session and returns to menu."""
        await console_service.process_message(
            phone="+10000000000",
            message="2",
            is_master=True,
            session_service=session_service,
        )
        await console_service.process_message(
            phone="+10000000000",
            message="Test User",
            is_master=True,
            session_service=session_service,
        )

        # Cancel during email step
        reply = await console_service.process_message(
            phone="+10000000000",
            message="cancelar",
            is_master=True,
            session_service=session_service,
        )
        assert "Trackpal Master Console" in reply
        assert "cancelada" in reply.lower() or "cancelado" in reply.lower()
        session = await session_service.get_session("+10000000000")
        assert session is None

    async def test_full_flow_normalized_values(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        tenant_service: FakeTenantService,
    ) -> None:
        """Full create flow normalizes mixed-case email, phone without +,
        and full name with multiple internal spaces.

        The created FakeTenant must store canonical forms.
        """
        # Step 1: Start
        reply = await console_service.process_message(
            phone="+10000000000",
            message="2",
            is_master=True,
            session_service=session_service,
        )
        assert "nombre completo" in reply.lower()

        # Step 2: Full name with multiple internal spaces
        reply = await console_service.process_message(
            phone="+10000000000",
            message="María   García   Ana",  # multiple spaces
            is_master=True,
            session_service=session_service,
        )
        assert "email" in reply.lower()

        # Step 3: Email with mixed case
        reply = await console_service.process_message(
            phone="+10000000000",
            message="Maria.Garcia@Example.COM",  # mixed case
            is_master=True,
            session_service=session_service,
        )
        assert "teléfono" in reply.lower()

        # Step 4: Phone without + prefix
        reply = await console_service.process_message(
            phone="+10000000000",
            message="525511112233",  # no +
            is_master=True,
            session_service=session_service,
        )
        assert "usuario" in reply.lower()

        # Step 5: Username
        reply = await console_service.process_message(
            phone="+10000000000",
            message="mariagarcia",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )
        assert "evolution" in reply.lower()

        # Step 6: Evolution Instance
        reply = await console_service.process_message(
            phone="+10000000000",
            message="inst-maria",
            is_master=True,
            session_service=session_service,
        )
        assert "contraseña" in reply.lower()

        # Step 7: Password mode (auto)
        reply = await console_service.process_message(
            phone="+10000000000",
            message="1",
            is_master=True,
            session_service=session_service,
        )
        assert "CONFIRMAR" in reply or "confirmar" in reply

        # Step 8: Confirm
        reply = await console_service.process_message(
            phone="+10000000000",
            message="CONFIRMAR",
            is_master=True,
            session_service=session_service,
            tenant_service=tenant_service,
        )
        assert "creado" in reply.lower() or "éxito" in reply.lower()

        # Verify the created tenant has normalized values
        tenants = await tenant_service.get_tenants()
        created = [t for t in tenants if t.username == "mariagarcia"]
        assert len(created) == 1
        tenant = created[0]

        # Canonical assertions
        assert tenant.full_name == "María García Ana"  # spaces collapsed
        assert tenant.email == "Maria.Garcia@example.com"  # domain lowercased
        assert tenant.phone == "525511112233"  # digits-only, no +


# ===========================================================================
# Error handling during creation
# ===========================================================================

@pytest.mark.asyncio
class TestCreateErrorHandling:
    """Error handling during the create flow."""

    async def test_creation_error_shows_message(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        """If TenantService raises an error during create, the error is
        shown to the user and the session state is handled gracefully."""
        # Use a tenant service that always fails
        class FailingTenantService(FakeTenantService):
            async def create_tenant(self, payload: dict) -> dict:
                return {
                    "success": False,
                    "error": "Error de prueba al crear tenant",
                }

        failing_service = FailingTenantService()

        await console_service.process_message(
            phone="+10000000000",
            message="2",
            is_master=True,
            session_service=session_service,
        )
        await console_service.process_message(
            phone="+10000000000",
            message="Test User",
            is_master=True,
            session_service=session_service,
        )
        await console_service.process_message(
            phone="+10000000000",
            message="test@example.com",
            is_master=True,
            session_service=session_service,
        )
        await console_service.process_message(
            phone="+10000000000",
            message="—",
            is_master=True,
            session_service=session_service,
        )
        await console_service.process_message(
            phone="+10000000000",
            message="testuser",
            is_master=True,
            session_service=session_service,
            tenant_service=failing_service,
        )
        await console_service.process_message(
            phone="+10000000000",
            message="inst-test",
            is_master=True,
            session_service=session_service,
        )
        await console_service.process_message(
            phone="+10000000000",
            message="1",
            is_master=True,
            session_service=session_service,
        )

        # Confirm with failing service
        reply = await console_service.process_message(
            phone="+10000000000",
            message="CONFIRMAR",
            is_master=True,
            session_service=session_service,
            tenant_service=failing_service,
        )
        assert "Error de prueba" in reply

    async def test_invalid_input_during_create_flow(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
    ) -> None:
        """Invalid input (non-step-related) during create flow shows
        flow-specific handling rather than generic fallback."""
        await console_service.process_message(
            phone="+10000000000",
            message="2",
            is_master=True,
            session_service=session_service,
        )

        # Send random text that isn't a valid full name
        # Actually, any non-empty text is a valid full name for the full_name step
        # Let's test during username step
        await console_service.process_message(
            phone="+10000000000",
            message="Test User",
            is_master=True,
            session_service=session_service,
        )
        await console_service.process_message(
            phone="+10000000000",
            message="test@example.com",
            is_master=True,
            session_service=session_service,
        )
        await console_service.process_message(
            phone="+10000000000",
            message="+525512345678",
            is_master=True,
            session_service=session_service,
        )

        # Now on username step, send invalid (empty)
        reply = await console_service.process_message(
            phone="+10000000000",
            message="",
            is_master=True,
            session_service=session_service,
        )
        assert "usuario" in reply.lower()


# ---------------------------------------------------------------------------
# TTL noise guards during create flow
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestTTLNoiseDuringCreateFlow:
    """Invalid/noise input during create flow must not extend TTL."""

    async def test_invalid_password_mode_does_not_refresh_ttl(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        fake_redis: FakeRedis,
    ) -> None:
        """Invalid selection at password_mode step must not reset TTL."""
        # Progress to password_mode step
        await console_service.process_message(
            phone="+10000000000", message="2", is_master=True,
            session_service=session_service,
        )
        await console_service.process_message(
            phone="+10000000000", message="Test User", is_master=True,
            session_service=session_service,
        )
        await console_service.process_message(
            phone="+10000000000", message="test@example.com", is_master=True,
            session_service=session_service,
        )
        await console_service.process_message(
            phone="+10000000000", message="+525512345678", is_master=True,
            session_service=session_service,
        )
        await console_service.process_message(
            phone="+10000000000", message="testuser", is_master=True,
            session_service=session_service,
        )
        await console_service.process_message(
            phone="+10000000000", message="inst-test", is_master=True,
            session_service=session_service,
        )

        key = session_service._session_key("+10000000000")
        # TTL was refreshed on last valid step — now simulate elapsed time
        fake_redis._ttls[key] = 400

        # Send invalid password mode input
        reply = await console_service.process_message(
            phone="+10000000000",
            message="3",
            is_master=True,
            session_service=session_service,
        )
        assert "inválida" in reply.lower() or "Opción" in reply

        # TTL should NOT have been refreshed
        assert fake_redis.get_ttl(key) == 400, (
            f"Expected TTL 400 (unchanged), got {fake_redis.get_ttl(key)}"
        )

    async def test_invalid_confirm_does_not_refresh_ttl(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        fake_redis: FakeRedis,
    ) -> None:
        """Non-CONFIRMAR at confirm step must not extend TTL."""
        # Progress to confirm step with auto password
        await console_service.process_message(
            phone="+10000000000", message="2", is_master=True,
            session_service=session_service,
        )
        await console_service.process_message(
            phone="+10000000000", message="Test User", is_master=True,
            session_service=session_service,
        )
        await console_service.process_message(
            phone="+10000000000", message="test@example.com", is_master=True,
            session_service=session_service,
        )
        await console_service.process_message(
            phone="+10000000000", message="+525512345678", is_master=True,
            session_service=session_service,
        )
        await console_service.process_message(
            phone="+10000000000", message="testuser", is_master=True,
            session_service=session_service,
        )
        await console_service.process_message(
            phone="+10000000000", message="inst-test", is_master=True,
            session_service=session_service,
        )
        await console_service.process_message(
            phone="+10000000000", message="1", is_master=True,
            session_service=session_service,
        )

        key = session_service._session_key("+10000000000")
        fake_redis._ttls[key] = 300

        # Send invalid confirmation
        reply = await console_service.process_message(
            phone="+10000000000",
            message="no",
            is_master=True,
            session_service=session_service,
        )
        assert "CONFIRMAR" in reply or "confirmar" in reply

        # TTL unchanged
        assert fake_redis.get_ttl(key) == 300

    async def test_empty_input_during_username_does_not_refresh_ttl(
        self,
        console_service: WhatsAppConsoleService,
        session_service: WhatsAppSessionService,
        fake_redis: FakeRedis,
    ) -> None:
        """Empty/whitespace at username step must not extend TTL."""
        # Progress to username step
        await console_service.process_message(
            phone="+10000000000", message="2", is_master=True,
            session_service=session_service,
        )
        await console_service.process_message(
            phone="+10000000000", message="Test User", is_master=True,
            session_service=session_service,
        )
        await console_service.process_message(
            phone="+10000000000", message="test@example.com", is_master=True,
            session_service=session_service,
        )
        await console_service.process_message(
            phone="+10000000000", message="+525512345678", is_master=True,
            session_service=session_service,
        )

        key = session_service._session_key("+10000000000")
        fake_redis._ttls[key] = 500

        # Send empty input at username step
        reply = await console_service.process_message(
            phone="+10000000000",
            message="",
            is_master=True,
            session_service=session_service,
        )
        assert "usuario" in reply.lower()

        # TTL unchanged
        assert fake_redis.get_ttl(key) == 500
