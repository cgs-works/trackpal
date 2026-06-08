# TPL-11 Email Confirmation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a strict email confirmation step before mailbox lookup creation in both tenant-admin and unauthenticated `codigo` flows.

**Architecture:** Keep the tenant-admin and unauthenticated lookup engines separate. Insert a new intermediate `email_confirm` step in each flow, validate email input with `app.core.input_validation.validate_email(required=True)`, then force `.lower()` before persisting it in session state or sending it to `MailLookupJob`. For tenant-admin, also bypass the global active-flow reset/help interception while the session is in `codigo/email_confirm` so text aliases become invalid options instead of cancelling the flow.

**Tech Stack:** Python 3.11, FastAPI endpoint handlers, Redis-backed `WhatsAppSessionService`, pytest + pytest-asyncio, i18n WhatsApp catalogs

---

## File Map

- Modify: `backend/app/services/whatsapp_tenant_console_service/constants.py:198-206` — add `CODIGO_STEP_EMAIL_CONFIRM` and new i18n key constants.
- Modify: `backend/app/services/whatsapp_tenant_console_service/_const_mixin.py:257-272` — expose the new step and keys on `WhatsAppTenantConsoleService`.
- Modify: `backend/app/services/whatsapp_tenant_console_service/_routers.py:352-364` — route `email_confirm` to a dedicated handler.
- Modify: `backend/app/services/whatsapp_tenant_console_service/service.py:204-226` — bypass global reset/help interception while `flow=codigo` and `step=email_confirm`.
- Modify: `backend/app/services/whatsapp_tenant_console_service/codigo_flow.py:233-280,327-380` — replace manual email checks with `validate_email`, store lowercase email, add the tenant-admin confirm handler, and keep the retry/back/cancel contract unchanged after lookup results.
- Modify: `backend/app/api/v1/endpoints/integrations/console_handlers.py:61-65,529-545,657-753` — add unauth `email_confirm` state, validate/lowercase email, create jobs only on confirm `1`, and preserve Evolution close semantics on confirm-step cancel.
- Modify: `backend/app/core/i18n/catalogs_es_wa.py:211-229` — add Spanish prompt and invalid-option copy for email confirmation.
- Modify: `backend/app/core/i18n/catalogs_en_wa.py:211-229` — add English prompt and invalid-option copy for email confirmation.
- Modify: `backend/tests/test_tenant_console_service.py:2008-2492` — add tenant-admin coverage for email confirmation state, lowercase persistence, strict numeric navigation, and pending lookup intent timing.
- Modify: `backend/tests/test_whatsapp_endpoint.py:995-1160` — update unauth multistep coverage and add confirm-step edge-case tests.
- Modify: `docs/architecture/whatsapp-console-flow.md:312-342` — document `email -> email_confirm -> awaiting_result` for both code paths and the strict `1/2/9/0` confirm contract.

---

### Task 1: Tenant Admin `codigo` email confirmation

**Files:**
- Modify: `backend/tests/test_tenant_console_service.py:2008-2492`
- Modify: `backend/app/services/whatsapp_tenant_console_service/constants.py:198-206`
- Modify: `backend/app/services/whatsapp_tenant_console_service/_const_mixin.py:257-272`
- Modify: `backend/app/services/whatsapp_tenant_console_service/_routers.py:352-364`
- Modify: `backend/app/services/whatsapp_tenant_console_service/service.py:204-226`
- Modify: `backend/app/services/whatsapp_tenant_console_service/codigo_flow.py:233-280,327-380`
- Modify: `backend/app/core/i18n/catalogs_es_wa.py:211-229`
- Modify: `backend/app/core/i18n/catalogs_en_wa.py:211-229`
- Test: `backend/tests/test_tenant_console_service.py`

**Skills to read before starting this task:**
- `test-driven-development` — required process skill for this feature change; write failing tests first, then implement the minimum fix.
- `python-pro` — for typed Python async/session-state changes and pytest patterns.
- `verification-before-completion` — before marking the task done, run the listed pytest command and confirm the output.
- Plus one execution skill from the plan header: `subagent-driven-development` (recommended) or `executing-plans`.

- [ ] **Step 1: Write the failing tenant-admin tests**

```python
async def test_codigo_email_valid_moves_to_email_confirm(
    self,
    console_service: WhatsAppTenantConsoleService,
) -> None:
    from unittest.mock import AsyncMock

    mock_session_service = AsyncMock()
    mock_session = AsyncMock()
    mock_session.temp_data = {
        "service_key": "netflix",
        "service_label": "Netflix",
    }
    mock_session.flow = console_service.CODIGO_FLOW
    mock_session.step = console_service.CODIGO_STEP_EMAIL

    reply = await console_service._handle_codigo_email(
        phone="+10000000000",
        msg="User@Example.COM",
        session=mock_session,
        session_service=mock_session_service,
        tenant_id=uuid4(),
        db=AsyncMock(),
    )

    assert "confirm" in reply.lower() or "confirmar" in reply.lower()
    assert "user@example.com" in reply
    assert mock_session.step == console_service.CODIGO_STEP_EMAIL_CONFIRM
    assert mock_session.temp_data["target_email"] == "user@example.com"
    assert "pending_lookup_intent" not in mock_session.temp_data
    mock_session_service.save_session.assert_awaited_once_with(mock_session)


async def test_codigo_email_confirm_yes_sets_pending_lookup_intent(
    self,
    console_service: WhatsAppTenantConsoleService,
) -> None:
    from unittest.mock import AsyncMock

    mock_session_service = AsyncMock()
    mock_session = AsyncMock()
    mock_session.temp_data = {
        "service_key": "netflix",
        "service_label": "Netflix",
        "target_email": "user@example.com",
    }
    mock_session.flow = console_service.CODIGO_FLOW
    mock_session.step = console_service.CODIGO_STEP_EMAIL_CONFIRM

    reply = await console_service._handle_codigo_email_confirm(
        phone="+10000000000",
        msg="1",
        session=mock_session,
        session_service=mock_session_service,
        tenant_id=uuid4(),
        db=AsyncMock(),
    )

    assert "buscando" in reply.lower() or "searching" in reply.lower()
    assert mock_session.step == console_service.CODIGO_STEP_AWAITING_RESULT
    assert mock_session.temp_data["pending_lookup_intent"] == "true"


async def test_codigo_email_confirm_text_cancel_is_invalid_option(
    self,
    console_service: WhatsAppTenantConsoleService,
    session_service: WhatsAppSessionService,
) -> None:
    session = await session_service.create_session("admin:+10000000000")
    session.flow = console_service.CODIGO_FLOW
    session.step = console_service.CODIGO_STEP_EMAIL_CONFIRM
    session.temp_data = {
        "service_key": "netflix",
        "service_label": "Netflix",
        "target_email": "user@example.com",
        "codigo_effective_keys": ["netflix"],
        "codigo_current_page": 0,
    }
    await session_service.save_session(session)

    reply = await console_service.process_message(
        phone="+10000000000",
        message="cancelar",
        tenant_id=uuid4(),
        db=AsyncMock(),
        session_service=session_service,
    )

    assert "opcion invalida" in reply.lower() or "invalid option" in reply.lower()
    saved = await session_service.get_session("admin:+10000000000")
    assert saved is not None
    assert saved.step == console_service.CODIGO_STEP_EMAIL_CONFIRM
```

- [ ] **Step 2: Run the tenant-admin tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_tenant_console_service.py -k "codigo_email_confirm" -v`
Expected: FAIL with missing `CODIGO_STEP_EMAIL_CONFIRM` / missing `_handle_codigo_email_confirm` and one failure showing `cancelar` is treated as a global cancel instead of an invalid confirm option.

- [ ] **Step 3: Write the minimal tenant-admin implementation**

```python
# backend/app/services/whatsapp_tenant_console_service/constants.py
CODIGO_FLOW = "codigo"
CODIGO_STEP_SERVICE = "service"
CODIGO_STEP_EMAIL = "email"
CODIGO_STEP_EMAIL_CONFIRM = "email_confirm"
CODIGO_STEP_AWAITING_RESULT = "awaiting_result"

KEY_CODIGO_MENU = "wa.tenant.codigo.menu"
KEY_CODIGO_SERVICE_PROMPT = "wa.tenant.codigo.service_prompt"
KEY_CODIGO_EMAIL_PROMPT = "wa.tenant.codigo.email_prompt"
KEY_CODIGO_EMAIL_CONFIRM_PROMPT = "wa.tenant.codigo.email_confirm_prompt"
KEY_CODIGO_INVALID_EMAIL_CONFIRM_OPTION = (
    "wa.tenant.codigo.invalid_email_confirm_option"
)
```

```python
# backend/app/services/whatsapp_tenant_console_service/_const_mixin.py
CODIGO_FLOW = c.CODIGO_FLOW
CODIGO_STEP_SERVICE = c.CODIGO_STEP_SERVICE
CODIGO_STEP_EMAIL = c.CODIGO_STEP_EMAIL
CODIGO_STEP_EMAIL_CONFIRM = c.CODIGO_STEP_EMAIL_CONFIRM
CODIGO_STEP_AWAITING_RESULT = c.CODIGO_STEP_AWAITING_RESULT
STREAMING_SERVICE_KEYS = c.STREAMING_SERVICE_KEYS
KEY_CODIGO_MENU = c.KEY_CODIGO_MENU
KEY_CODIGO_SERVICE_PROMPT = c.KEY_CODIGO_SERVICE_PROMPT
KEY_CODIGO_EMAIL_PROMPT = c.KEY_CODIGO_EMAIL_PROMPT
KEY_CODIGO_EMAIL_CONFIRM_PROMPT = c.KEY_CODIGO_EMAIL_CONFIRM_PROMPT
KEY_CODIGO_INVALID_EMAIL_CONFIRM_OPTION = c.KEY_CODIGO_INVALID_EMAIL_CONFIRM_OPTION
```

```python
# backend/app/services/whatsapp_tenant_console_service/_routers.py
if step == self.CODIGO_STEP_SERVICE:
    return await self._handle_codigo_service(
        phone, msg, session, session_service, tenant_id, db
    )
elif step == self.CODIGO_STEP_EMAIL:
    return await self._handle_codigo_email(
        phone, msg, session, session_service, tenant_id, db
    )
elif step == self.CODIGO_STEP_EMAIL_CONFIRM:
    return await self._handle_codigo_email_confirm(
        phone, msg, session, session_service, tenant_id, db
    )
elif step == self.CODIGO_STEP_AWAITING_RESULT:
    return await self._handle_codigo_awaiting_result(
        phone, msg, session, session_service, tenant_id, db
    )
```

```python
# backend/app/services/whatsapp_tenant_console_service/service.py
if has_active_flow:
    assert session is not None
    strict_codigo_confirm = (
        session.flow == self.CODIGO_FLOW
        and session.step == self.CODIGO_STEP_EMAIL_CONFIRM
    )
    if not strict_codigo_confirm and (
        is_cancel(msg) or msg.lower() in ("menu", "menú", "/menu")
    ):
        if session_service is not None:
            await session_service.clear_session(f"admin:{phone}")
        if msg == "0":
            return _i18n_t(ctx.get_locale(), "wa.tenant.goodbye")
        return self._with_main_menu(_i18n_t(ctx.get_locale(), "wa.tenant.cancelled"))
    if not strict_codigo_confirm and msg.lower() in self.HELP_COMMANDS:
        return self._t(self.KEY_HELP_TEXT)
    return await self._route_active_flow(
        phone,
        msg,
        session,
        session_service,
        tenant_id,
        user_id,
        db,
    )
```

```python
# backend/app/services/whatsapp_tenant_console_service/codigo_flow.py
from app.core.input_validation import InputValidationError, validate_email

async def _handle_codigo_email(
    self,
    phone: str,
    msg: str,
    session: Any,
    session_service: Any,
    tenant_id: Any,
    db: Any,
) -> str:
    loc = ctx.get_locale()

    if is_cancel(msg):
        await session_service.clear_session(f"admin:{phone}")
        return _i18n_t(loc, "wa.tenant.cancelled")

    try:
        normalized_email = validate_email(msg, required=True)
    except InputValidationError:
        return _i18n_t(loc, "wa.tenant.codigo.invalid_email")

    service_key = session.temp_data.get("service_key")
    service_label = session.temp_data.get("service_label")
    if not service_key or not service_label:
        await session_service.clear_session(f"admin:{phone}")
        return self._with_main_menu(_i18n_t(loc, "wa.tenant.cancelled"), locale=loc)

    target_email = normalized_email.lower()
    session.temp_data["target_email"] = target_email
    session.temp_data.pop("pending_lookup_intent", None)
    session.temp_data.pop("lookup_job_id", None)
    session.step = self.CODIGO_STEP_EMAIL_CONFIRM
    await session_service.save_session(session)

    return self._t(
        self.KEY_CODIGO_EMAIL_CONFIRM_PROMPT,
        service_label=service_label,
        target_email=target_email,
    )


async def _handle_codigo_email_confirm(
    self,
    phone: str,
    msg: str,
    session: Any,
    session_service: Any,
    tenant_id: Any,
    db: Any,
) -> str:
    loc = ctx.get_locale()
    raw = msg.strip()

    if raw == "1":
        session.temp_data["pending_lookup_intent"] = "true"
        session.step = self.CODIGO_STEP_AWAITING_RESULT
        await session_service.save_session(session)
        return _i18n_t(loc, "wa.tenant.codigo.buscando")

    if raw == "2":
        service_label = session.temp_data.get("service_label", "")
        session.temp_data.pop("target_email", None)
        session.temp_data.pop("pending_lookup_intent", None)
        session.step = self.CODIGO_STEP_EMAIL
        await session_service.save_session(session)
        return self._t(self.KEY_CODIGO_EMAIL_PROMPT, service_label=service_label)

    if raw == "9":
        effective_keys = session.temp_data.get("codigo_effective_keys", [])
        if not effective_keys and tenant_id is not None and db is not None:
            effective_keys = await code_services_repository.get_effective_service_keys(
                db, tenant_id
            )
        if not effective_keys:
            await session_service.clear_session(f"admin:{phone}")
            return self._t(self.KEY_CODIGO_NO_CODE_SERVICES_TENANT)

        for key in (
            "service_key",
            "service_label",
            "target_email",
            "pending_lookup_intent",
            "lookup_job_id",
        ):
            session.temp_data.pop(key, None)
        session.temp_data["codigo_effective_keys"] = effective_keys
        session.temp_data["codigo_current_page"] = 0
        session.step = self.CODIGO_STEP_SERVICE
        await session_service.save_session(session)

        service_list = _build_service_page(
            effective_keys,
            0,
            loc,
            session.temp_data.get("codigo_started_from_menu") == "true",
        )
        return self._t(self.KEY_CODIGO_SERVICE_PROMPT, service_list=service_list)

    if raw == "0":
        await session_service.clear_session(f"admin:{phone}")
        return _i18n_t(loc, "wa.tenant.cancelled")

    return self._t(self.KEY_CODIGO_INVALID_EMAIL_CONFIRM_OPTION)
```

```python
# backend/app/core/i18n/catalogs_es_wa.py
"wa.tenant.codigo.email_confirm_prompt": "✉️ *Confirmar email*\n\nServicio: *{service_label}*\nEmail: *{target_email}*\n\n¿El correo ingresado es correcto?\n\n1️⃣ Sí\n2️⃣ Corregir email\n9️⃣ Volver a servicios\n0️⃣ Cancelar",
"wa.tenant.codigo.invalid_email_confirm_option": "❌ Opción inválida. Responde *1* para confirmar, *2* para corregir el email, *9* para volver a servicios o *0* para cancelar.",

# backend/app/core/i18n/catalogs_en_wa.py
"wa.tenant.codigo.email_confirm_prompt": "✉️ *Confirm email*\n\nService: *{service_label}*\nEmail: *{target_email}*\n\nIs this email correct?\n\n1️⃣ Yes\n2️⃣ Correct email\n9️⃣ Back to services\n0️⃣ Cancel",
"wa.tenant.codigo.invalid_email_confirm_option": "❌ Invalid option. Reply *1* to confirm, *2* to correct the email, *9* to go back to services, or *0* to cancel.",
```

- [ ] **Step 4: Run the tenant-admin tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_tenant_console_service.py -k "codigo_email_confirm" -v`
Expected: PASS for the new tenant-admin confirmation tests.

- [ ] **Step 5: Commit**

```bash
git add backend/tests/test_tenant_console_service.py \
  backend/app/services/whatsapp_tenant_console_service/constants.py \
  backend/app/services/whatsapp_tenant_console_service/_const_mixin.py \
  backend/app/services/whatsapp_tenant_console_service/_routers.py \
  backend/app/services/whatsapp_tenant_console_service/service.py \
  backend/app/services/whatsapp_tenant_console_service/codigo_flow.py \
  backend/app/core/i18n/catalogs_es_wa.py \
  backend/app/core/i18n/catalogs_en_wa.py

git commit -m "feat: add tenant codigo email confirmation"
```

### Task 2: Unauthenticated `codigo` email confirmation

**Files:**
- Modify: `backend/tests/test_whatsapp_endpoint.py:995-1160`
- Modify: `backend/app/api/v1/endpoints/integrations/console_handlers.py:61-65,529-545,657-753`
- Modify: `backend/app/core/i18n/catalogs_es_wa.py:211-229`
- Modify: `backend/app/core/i18n/catalogs_en_wa.py:211-229`
- Test: `backend/tests/test_whatsapp_endpoint.py`

**Skills to read before starting this task:**
- `test-driven-development` — required process skill for this feature change; add endpoint tests before changing the handler.
- `fastapi-expert` — for the FastAPI integration handler flow, response contract, and async endpoint patterns.
- `python-pro` — for typed Python async code, validation flow, and pytest updates.
- `verification-before-completion` — before marking the task done, run the listed pytest command and confirm the output.
- Plus one execution skill from the plan header: `subagent-driven-development` (recommended) or `executing-plans`.

- [ ] **Step 1: Write the failing unauth endpoint tests**

```python
async def test_unregistered_identity_codigo_multistep(
    client, db_session, active_tenant_user
):
    _tenant = await _setup_tenant_for_codigo(db_session, active_tenant_user)

    fake_mgr = _FakeManager(used_backup=False)
    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        resp1 = await client.post(
            ENDPOINT,
            json={"phone": "+12015559999", "message": "codigo", "instance": TEST_INSTANCE},
            headers={"X-API-Key": settings.n8n_api_key},
        )
        assert "Netflix" in resp1.json()["reply"]

        resp2 = await client.post(
            ENDPOINT,
            json={"phone": "+12015559999", "message": "1", "instance": TEST_INSTANCE},
            headers={"X-API-Key": settings.n8n_api_key},
        )
        assert "email" in resp2.json()["reply"].lower() or "correo" in resp2.json()["reply"].lower()

        resp3 = await client.post(
            ENDPOINT,
            json={"phone": "+12015559999", "message": "User@Example.COM", "instance": TEST_INSTANCE},
            headers={"X-API-Key": settings.n8n_api_key},
        )
        body3 = resp3.json()
        assert "confirm" in body3["reply"].lower() or "confirmar" in body3["reply"].lower()
        assert "user@example.com" in body3["reply"]
        assert "lookup_job_id" not in body3

        resp4 = await client.post(
            ENDPOINT,
            json={"phone": "+12015559999", "message": "1", "instance": TEST_INSTANCE},
            headers={"X-API-Key": settings.n8n_api_key},
        )
        body4 = resp4.json()
        assert "buscando" in body4["reply"].lower() or "searching" in body4["reply"].lower()
        assert body4["lookup_job_id"] is not None
        assert body4["tenant_id"] is not None


async def test_unregistered_identity_codigo_confirm_option_2_returns_email_prompt(
    client, db_session, active_tenant_user
):
    _tenant = await _setup_tenant_for_codigo(db_session, active_tenant_user)

    fake_mgr = _FakeManager(used_backup=False)
    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        await client.post(
            ENDPOINT,
            json={"phone": "+12015559999", "message": "codigo", "instance": TEST_INSTANCE},
            headers={"X-API-Key": settings.n8n_api_key},
        )
        await client.post(
            ENDPOINT,
            json={"phone": "+12015559999", "message": "1", "instance": TEST_INSTANCE},
            headers={"X-API-Key": settings.n8n_api_key},
        )
        await client.post(
            ENDPOINT,
            json={"phone": "+12015559999", "message": "user@example.com", "instance": TEST_INSTANCE},
            headers={"X-API-Key": settings.n8n_api_key},
        )

        resp = await client.post(
            ENDPOINT,
            json={"phone": "+12015559999", "message": "2", "instance": TEST_INSTANCE},
            headers={"X-API-Key": settings.n8n_api_key},
        )

    body = resp.json()
    assert "email" in body["reply"].lower() or "correo" in body["reply"].lower()
    assert "lookup_job_id" not in body


async def test_unregistered_identity_codigo_confirm_option_9_returns_services(
    client, db_session, active_tenant_user
):
    _tenant = await _setup_tenant_for_codigo(db_session, active_tenant_user)

    fake_mgr = _FakeManager(used_backup=False)
    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        await client.post(
            ENDPOINT,
            json={"phone": "+12015559999", "message": "codigo", "instance": TEST_INSTANCE},
            headers={"X-API-Key": settings.n8n_api_key},
        )
        await client.post(
            ENDPOINT,
            json={"phone": "+12015559999", "message": "1", "instance": TEST_INSTANCE},
            headers={"X-API-Key": settings.n8n_api_key},
        )
        await client.post(
            ENDPOINT,
            json={"phone": "+12015559999", "message": "user@example.com", "instance": TEST_INSTANCE},
            headers={"X-API-Key": settings.n8n_api_key},
        )

        resp = await client.post(
            ENDPOINT,
            json={"phone": "+12015559999", "message": "9", "instance": TEST_INSTANCE},
            headers={"X-API-Key": settings.n8n_api_key},
        )

    body = resp.json()
    assert "Netflix" in body["reply"]
    assert "lookup_job_id" not in body


async def test_unregistered_identity_codigo_confirm_option_0_closes_session(
    client, db_session, active_tenant_user
):
    _tenant = await _setup_tenant_for_codigo(db_session, active_tenant_user)

    fake_mgr = _FakeManager(used_backup=False)
    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        await client.post(
            ENDPOINT,
            json={"phone": "+12015559999", "message": "codigo", "instance": TEST_INSTANCE},
            headers={"X-API-Key": settings.n8n_api_key},
        )
        await client.post(
            ENDPOINT,
            json={"phone": "+12015559999", "message": "1", "instance": TEST_INSTANCE},
            headers={"X-API-Key": settings.n8n_api_key},
        )
        await client.post(
            ENDPOINT,
            json={"phone": "+12015559999", "message": "user@example.com", "instance": TEST_INSTANCE},
            headers={"X-API-Key": settings.n8n_api_key},
        )

        resp = await client.post(
            ENDPOINT,
            json={"phone": "+12015559999", "message": "0", "instance": TEST_INSTANCE},
            headers={"X-API-Key": settings.n8n_api_key},
        )

    body = resp.json()
    assert body["status"] == "closed"
    assert body["reply_to"] == "12015559999@s.whatsapp.net"
    assert body["close_jid"] == "12015559999@s.whatsapp.net"


async def test_unregistered_identity_codigo_confirm_invalid_option_does_not_create_job(
    client, db_session, active_tenant_user
):
    _tenant = await _setup_tenant_for_codigo(db_session, active_tenant_user)

    fake_mgr = _FakeManager(used_backup=False)
    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        await client.post(
            ENDPOINT,
            json={"phone": "+12015559999", "message": "codigo", "instance": TEST_INSTANCE},
            headers={"X-API-Key": settings.n8n_api_key},
        )
        await client.post(
            ENDPOINT,
            json={"phone": "+12015559999", "message": "1", "instance": TEST_INSTANCE},
            headers={"X-API-Key": settings.n8n_api_key},
        )
        await client.post(
            ENDPOINT,
            json={"phone": "+12015559999", "message": "user@example.com", "instance": TEST_INSTANCE},
            headers={"X-API-Key": settings.n8n_api_key},
        )

        resp = await client.post(
            ENDPOINT,
            json={"phone": "+12015559999", "message": "cancelar", "instance": TEST_INSTANCE},
            headers={"X-API-Key": settings.n8n_api_key},
        )

    body = resp.json()
    assert "opción inválida" in body["reply"].lower() or "invalid option" in body["reply"].lower()
    assert "lookup_job_id" not in body
```

- [ ] **Step 2: Run the unauth endpoint tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_whatsapp_endpoint.py -k "unregistered_identity_codigo_multistep or unregistered_identity_codigo_confirm" -v`
Expected: FAIL because the flow still creates the job on email entry, does not expose `email_confirm`, and accepts no strict confirm-step contract yet.

- [ ] **Step 3: Write the minimal unauth implementation**

```python
# backend/app/api/v1/endpoints/integrations/console_handlers.py
from app.core.input_validation import InputValidationError, validate_email

_UNAUTH_CODIGO_FLOW = "codigo"
_UNAUTH_CODIGO_STEP_SERVICE = "service"
_UNAUTH_CODIGO_STEP_EMAIL = "email"
_UNAUTH_CODIGO_STEP_EMAIL_CONFIRM = "email_confirm"
_UNAUTH_CODIGO_STEP_AWAITING_RESULT = "awaiting_result"

if session.step == _UNAUTH_CODIGO_STEP_EMAIL:
    return await _handle_unauth_codigo_email(
        msg,
        session,
        session_service,
        session_key,
        tenant,
        db,
        locale,
        manager,
        close_jid,
    )

if session.step == _UNAUTH_CODIGO_STEP_EMAIL_CONFIRM:
    return await _handle_unauth_codigo_email_confirm(
        msg,
        session,
        session_service,
        session_key,
        tenant,
        db,
        locale,
        manager,
        close_jid,
    )
```

```python
# backend/app/api/v1/endpoints/integrations/console_handlers.py
async def _handle_unauth_codigo_email(
    msg: str,
    session: ConversationSession,
    session_service: WhatsAppSessionService,
    session_key: str,
    tenant: Tenant,
    db: AsyncSession,
    locale: str,
    manager: RedisConnectionManager,
    close_jid: str | None = None,
) -> WhatsAppConsoleResponse:
    if is_cancel(msg):
        await session_service.clear_session(session_key)
        return WhatsAppConsoleResponse(
            reply=_i18n_t(locale, "wa.tenant.cancelled"),
            status="closed",
            reply_to=close_jid,
            close_jid=close_jid,
        )

    try:
        normalized_email = validate_email(msg, required=True)
    except InputValidationError:
        return WhatsAppConsoleResponse(
            reply=_i18n_t(locale, "wa.tenant.codigo.invalid_email")
        )

    service_key = session.temp_data.get("service_key")
    service_label = session.temp_data.get("service_label")
    if not service_key or not service_label:
        await session_service.clear_session(session_key)
        return WhatsAppConsoleResponse(reply=_i18n_t(locale, "wa.tenant.cancelled"))

    target_email = normalized_email.lower()
    session.temp_data["target_email"] = target_email
    session.temp_data.pop("lookup_job_id", None)
    session.step = _UNAUTH_CODIGO_STEP_EMAIL_CONFIRM
    await session_service.save_session(session)

    return WhatsAppConsoleResponse(
        reply=_i18n_t(
            locale,
            "wa.tenant.codigo.email_confirm_prompt",
            service_label=service_label,
            target_email=target_email,
        )
    )


async def _handle_unauth_codigo_email_confirm(
    msg: str,
    session: ConversationSession,
    session_service: WhatsAppSessionService,
    session_key: str,
    tenant: Tenant,
    db: AsyncSession,
    locale: str,
    manager: RedisConnectionManager,
    close_jid: str | None = None,
) -> WhatsAppConsoleResponse:
    raw = msg.strip()

    if raw == "2":
        service_label = session.temp_data.get("service_label", "")
        session.temp_data.pop("target_email", None)
        session.temp_data.pop("lookup_job_id", None)
        session.step = _UNAUTH_CODIGO_STEP_EMAIL
        await session_service.save_session(session)
        return WhatsAppConsoleResponse(
            reply=_i18n_t(
                locale,
                "wa.tenant.codigo.email_prompt",
                service_label=service_label,
            )
        )

    if raw == "9":
        effective_keys = session.temp_data.get("codigo_effective_keys", [])
        if not effective_keys:
            effective_keys = await code_services_repository.get_effective_service_keys(
                db, tenant.id
            )
        if not effective_keys:
            await session_service.clear_session(session_key)
            return WhatsAppConsoleResponse(
                reply=_i18n_t(locale, "wa.tenant.codigo.no_code_services_client")
            )

        for key in ("service_key", "service_label", "target_email", "lookup_job_id"):
            session.temp_data.pop(key, None)
        session.temp_data["codigo_effective_keys"] = effective_keys
        session.temp_data["codigo_current_page"] = 0
        session.step = _UNAUTH_CODIGO_STEP_SERVICE
        await session_service.save_session(session)
        return WhatsAppConsoleResponse(
            reply=_i18n_t(
                locale,
                "wa.tenant.codigo.service_prompt",
                service_list=_build_unauth_service_page(effective_keys, 0, locale),
            )
        )

    if raw == "0":
        await session_service.clear_session(session_key)
        return WhatsAppConsoleResponse(
            reply=_i18n_t(locale, "wa.tenant.cancelled"),
            status="closed",
            reply_to=close_jid,
            close_jid=close_jid,
        )

    if raw != "1":
        return WhatsAppConsoleResponse(
            reply=_i18n_t(locale, "wa.tenant.codigo.invalid_email_confirm_option")
        )

    service_key = session.temp_data.get("service_key")
    target_email = session.temp_data.get("target_email")
    if not service_key or not target_email:
        await session_service.clear_session(session_key)
        return WhatsAppConsoleResponse(reply=_i18n_t(locale, "wa.tenant.cancelled"))

    mailbox = await mailbox_config_repository.get_by_tenant(db, tenant.id)
    if mailbox is None or mailbox.status != "connected":
        return WhatsAppConsoleResponse(
            reply=_i18n_t(locale, "wa.tenant.codigo.no_mailbox")
        )

    try:
        job = await mailbox_lookup_repository.create_job(
            db,
            tenant_id=tenant.id,
            mailbox_id=mailbox.id,
            service_key=service_key,
            target_email=target_email,
        )
        await db.flush()
        await db.commit()
        enqueued = await enqueue_job(manager, job.id) if manager is not None else False
    except Exception:
        logger.exception("Failed to create lookup job for tenant %s", tenant.id)
        return WhatsAppConsoleResponse(reply=_i18n_t(locale, "wa.tenant.codigo.error"))

    if not enqueued:
        try:
            await db.delete(job)
            await db.commit()
        except Exception:
            logger.critical("Failed to delete job %s after enqueue failure", job.id)
        return WhatsAppConsoleResponse(reply=_i18n_t(locale, "wa.tenant.codigo.error"))

    session.step = _UNAUTH_CODIGO_STEP_AWAITING_RESULT
    session.temp_data["lookup_job_id"] = str(job.id)
    await session_service.save_session(session)

    return WhatsAppConsoleResponse(
        reply=_i18n_t(locale, "wa.tenant.codigo.buscando"),
        lookup_job_id=str(job.id),
        tenant_id=str(tenant.id),
    )
```

- [ ] **Step 4: Run the unauth endpoint tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_whatsapp_endpoint.py -k "unregistered_identity_codigo_multistep or unregistered_identity_codigo_confirm" -v`
Expected: PASS for the updated multistep flow and the new `1/2/9/0` confirm-step behaviors.

- [ ] **Step 5: Commit**

```bash
git add backend/tests/test_whatsapp_endpoint.py \
  backend/app/api/v1/endpoints/integrations/console_handlers.py \
  backend/app/core/i18n/catalogs_es_wa.py \
  backend/app/core/i18n/catalogs_en_wa.py

git commit -m "feat: add unauth codigo email confirmation"
```

### Task 3: Refresh architecture docs for the new flow

**Files:**
- Modify: `docs/architecture/whatsapp-console-flow.md:312-342`
- Test: `docs/architecture/whatsapp-console-flow.md`

**Skills to read before starting this task:**
- `docs` — this task refreshes architecture documentation to match the implemented behavior.
- `verification-before-completion` — before marking the task done, run the listed `rg` verification command and confirm the expected matches.
- Plus one execution skill from the plan header: `subagent-driven-development` (recommended) or `executing-plans`.

- [ ] **Step 1: Update the WhatsApp flow architecture doc**

```md
#### Tenant self-target flow

1. Trigger by exact message `codigo`, `código`, or `code`.
2. Backend shows a paginated service list.
3. Backend asks for target email.
4. Backend validates the email with `validate_email(required=True)`, lowercases it explicitly, stores it in session, and moves to `email_confirm`.
5. In `email_confirm`, only `1`, `2`, `9`, and `0` are valid:
   - `1` confirms and sets `pending_lookup_intent`
   - `2` returns to the email prompt
   - `9` returns to the service list
   - `0` cancels
6. The integration handler creates the job only after confirm `1`.

#### Client-sent code flow (unauth codigo)

1. Trigger by `codigo`, `código`, or `code`.
2. Backend shows the paginated service list.
3. Backend asks for email.
4. Backend validates and lowercases the email, then moves to `email_confirm`.
5. In `email_confirm`, only `1`, `2`, `9`, and `0` are valid.
6. `lookup_job_id` is returned only after confirm `1` creates and enqueues the job.
```

- [ ] **Step 2: Verify the doc mentions the new confirm step and lowercase rule**

Run: `rg -n "email_confirm|validate_email|required=True|lowercase|lookup_job_id" docs/architecture/whatsapp-console-flow.md`
Expected: output includes both tenant and unauth sections with the new confirm-step language.

- [ ] **Step 3: Commit**

```bash
git add docs/architecture/whatsapp-console-flow.md
git commit -m "docs: describe codigo email confirmation flow"
```

---

## Final Verification

After Task 3, run the backend verification pass from the repo root:

```bash
cd backend && uv run pytest tests/test_tenant_console_service.py tests/test_whatsapp_endpoint.py -v
```

Expected: PASS for the tenant-admin and unauthenticated `codigo` coverage touched by this change.

If you want the broader regression pass before merging, run:

```bash
cd backend && uv run pytest
```

Expected: full backend suite PASS.
