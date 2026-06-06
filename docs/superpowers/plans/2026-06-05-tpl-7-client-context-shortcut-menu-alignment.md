# TPL-7 Client Context Shortcut Menu Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align active and inactive Client Context Shortcut menus with their real backend handlers, keep contextual navigation coherent, hide phone lines for LID-only targets, and lock the behavior down with regression tests.

**Architecture:** Keep the current dispatcher and state-machine shape in `console_handlers.py`, but add focused render helpers inside `console_context_shortcut.py` so every contextual screen can be rebuilt consistently. Drive the change test-first from endpoint-level regression tests, then wire active and inactive root/detail/edit/delete/deactivate flows to return `message + current screen` or `message + updated screen` per the approved spec.

**Tech Stack:** FastAPI, SQLAlchemy async, backend i18n catalogs, pytest + pytest-asyncio, in-memory fake Redis

---

## File Structure & Proposed Changes

| Target File | Change Type | Responsibility |
|---|---|---|
| `backend/tests/test_whatsapp_client_context_shortcut.py` | Modify | Add regression helpers and endpoint/unit tests for active/inactive menu routing, TTL refresh, detail navigation, subscription handoff, delete blocking, and LID-only phone hiding. |
| `backend/app/api/v1/endpoints/integrations/console_context_shortcut.py` | Modify | Add small render helpers, align active/inactive root handlers, add inactive detail handler, fix edit/deactivate/delete success replies, and keep current-screen re-render behavior consistent. |
| `backend/app/api/v1/endpoints/integrations/console_handlers.py` | Modify | Register the new `inactive_detail` step, update imports, and pass `active_client` into the active edit-field handler so `9` can rebuild the full detail screen. |
| `backend/app/core/i18n/catalogs_es_wa.py` | Modify | Convert contextual menu/detail templates to optional phone-line placeholders and add the minimal new keys required for active delete blocking and inactive detail options. |
| `backend/app/core/i18n/catalogs_en_wa.py` | Modify | Mirror the Spanish catalog changes in English. |
| `docs/architecture/whatsapp-console-flow.md` | Modify | Update only the Client Context Shortcut section to reflect the corrected active/inactive root menus and the root-menu `9` rule. |

---

## Tasks

### Task 1: Lock Active Root Menu Regressions First

**Files:**
- Modify: `backend/tests/test_whatsapp_client_context_shortcut.py`

- [ ] **Step 1: Add focused context seeding helpers and active-root regression tests**

Extend `backend/tests/test_whatsapp_client_context_shortcut.py` with reusable helpers plus the first failing tests for the active root menu contract.

```python
from app.models import Client, Service, Tenant, User


async def _create_context_client(
    db_session,
    tenant: Tenant,
    *,
    phone: str | None,
    is_active: bool,
    full_name: str,
    username: str,
) -> Client:
    ctx_user = User(username=f"{username}_user", password_hash="x", role="client")
    db_session.add(ctx_user)
    await db_session.flush()
    ctx_client = Client(
        tenant_id=tenant.id,
        owner_user_id=ctx_user.id,
        full_name=full_name,
        username=username,
        phone=phone,
        is_active=is_active,
    )
    db_session.add(ctx_client)
    await db_session.commit()
    return ctx_client


async def _seed_shortcut_context(
    fake_mgr: _FakeManager,
    admin_phone_digits: str,
    *,
    target_phone: str | None,
    target_lid: str | None = None,
    step: str = "menu",
    ttl: int = 123,
) -> str:
    session = {
        "phone": admin_phone_digits,
        "flow": "client_shortcut",
        "step": step,
        "selected_tenant_id": None,
        "temp_data": {
            "target_phone": target_phone,
            "target_lid": target_lid,
            "target_jid": f"{target_phone or target_lid or 'unknown'}@s.whatsapp.net",
            "admin_jid": f"{admin_phone_digits}@s.whatsapp.net",
        },
        "selection_map": {},
    }
    ctx_key = f"wa:client_ctx:{admin_phone_digits}"
    await fake_mgr._redis.set(ctx_key, json.dumps(session), ex=ttl)
    return ctx_key


async def test_active_menu_option_2_enters_edit_flow(
    client, db_session, active_tenant_user
):
    tenant = await _setup_tenant_with_instance(db_session, active_tenant_user)
    admin_phone_digits = tenant.whatsapp_phone.lstrip("+")
    await _create_context_client(
        db_session,
        tenant,
        phone="12015559999",
        is_active=True,
        full_name="Context Active Client",
        username="tna01_ctx_active",
    )
    fake_mgr = _FakeManager(used_backup=False)
    await _seed_shortcut_context(fake_mgr, admin_phone_digits, target_phone="12015559999")

    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={"phone": tenant.whatsapp_phone, "message": "2", "instance": TEST_INSTANCE},
            headers={"X-API-Key": settings.n8n_api_key},
        )

    assert response.status_code == 200
    reply = response.json()["reply"]
    assert "Que campo desea editar" in reply
    assert "Nombre completo" in reply
    assert "Nombre de usuario" in reply
    assert "Seleccione un *servicio*" not in reply


async def test_active_menu_option_3_starts_subscription_flow_and_clears_shortcut(
    client, db_session, active_tenant_user
):
    tenant = await _setup_tenant_with_instance(db_session, active_tenant_user)
    admin_phone_digits = tenant.whatsapp_phone.lstrip("+")
    await _create_context_client(
        db_session,
        tenant,
        phone="12015559998",
        is_active=True,
        full_name="Subscription Client",
        username="tna01_ctx_subscription",
    )
    db_session.add(Service(tenant_id=tenant.id, name="Streaming Pro"))
    await db_session.commit()

    fake_mgr = _FakeManager(used_backup=False)
    ctx_key = await _seed_shortcut_context(fake_mgr, admin_phone_digits, target_phone="12015559998")

    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={"phone": tenant.whatsapp_phone, "message": "3", "instance": TEST_INSTANCE},
            headers={"X-API-Key": settings.n8n_api_key},
        )

    assert response.status_code == 200
    reply = response.json()["reply"]
    assert "suscripcion" in reply.lower()
    assert "Streaming Pro" in reply
    assert await fake_mgr._redis.get(ctx_key) is None

    session_raw = await fake_mgr._redis.get(f"session:admin:{admin_phone_digits}")
    assert session_raw is not None
    session = json.loads(session_raw)
    assert session["flow"] == "subscriptions"
    assert session["step"] == "create_service"
    assert session["temp_data"]["client_name"] == "Subscription Client"


async def test_active_menu_option_5_blocks_delete_and_keeps_active_menu(
    client, db_session, active_tenant_user
):
    tenant = await _setup_tenant_with_instance(db_session, active_tenant_user)
    admin_phone_digits = tenant.whatsapp_phone.lstrip("+")
    await _create_context_client(
        db_session,
        tenant,
        phone="12015559997",
        is_active=True,
        full_name="Protected Active Client",
        username="tna01_ctx_protected",
    )
    fake_mgr = _FakeManager(used_backup=False)
    ctx_key = await _seed_shortcut_context(
        fake_mgr,
        admin_phone_digits,
        target_phone="12015559997",
        ttl=123,
    )

    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={"phone": tenant.whatsapp_phone, "message": "5", "instance": TEST_INSTANCE},
            headers={"X-API-Key": settings.n8n_api_key},
        )

    assert response.status_code == 200
    reply = response.json()["reply"]
    assert "No se puede eliminar" in reply
    assert "Desactivar cliente" in reply
    assert "Eliminar cliente" in reply
    assert fake_mgr._redis._ttls[ctx_key] == 300

    ctx_data = json.loads(await fake_mgr._redis.get(ctx_key))
    assert ctx_data["step"] == "active_menu"


async def test_active_menu_invalid_input_rerenders_full_menu_and_refreshes_ttl(
    client, db_session, active_tenant_user
):
    tenant = await _setup_tenant_with_instance(db_session, active_tenant_user)
    admin_phone_digits = tenant.whatsapp_phone.lstrip("+")
    await _create_context_client(
        db_session,
        tenant,
        phone="12015559996",
        is_active=True,
        full_name="Invalid Active Client",
        username="tna01_ctx_invalid",
    )
    fake_mgr = _FakeManager(used_backup=False)
    ctx_key = await _seed_shortcut_context(
        fake_mgr,
        admin_phone_digits,
        target_phone="12015559996",
        ttl=123,
    )

    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={"phone": tenant.whatsapp_phone, "message": "9", "instance": TEST_INSTANCE},
            headers={"X-API-Key": settings.n8n_api_key},
        )

    assert response.status_code == 200
    reply = response.json()["reply"]
    assert "Opcion invalida" in reply
    assert "Editar cliente" in reply
    assert "Crear suscripcion" in reply
    assert "Desactivar cliente" in reply
    assert "Eliminar cliente" in reply
    assert fake_mgr._redis._ttls[ctx_key] == 300
```

- [ ] **Step 2: Run the new active-root tests and confirm they fail for the right reasons**

Run:

```bash
cd backend && uv run pytest tests/test_whatsapp_client_context_shortcut.py -k "active_menu_option_2 or active_menu_option_3 or active_menu_option_5 or active_menu_invalid_input" -v
```

Expected:
- `test_active_menu_option_2_enters_edit_flow` fails because option `2` still starts subscription.
- `test_active_menu_option_3_starts_subscription_flow_and_clears_shortcut` fails because option `3` is still invalid.
- `test_active_menu_option_5_blocks_delete_and_keeps_active_menu` fails because option `5` is still invalid.
- `test_active_menu_invalid_input_rerenders_full_menu_and_refreshes_ttl` fails because root-menu invalid input still uses the old short menu and preserves the old TTL.

- [ ] **Step 3: Implement active-root render helpers, active root handler alignment, and minimal catalog changes**

Modify `backend/app/api/v1/endpoints/integrations/console_context_shortcut.py` to add small render helpers near `_phone_label()` and update `handle_ctx_active_client_menu()` to use them.

```python
def _client_phone_line(locale: str, phone: str | None) -> str:
    if not phone:
        return ""
    return t(locale, "wa.tenant.client_context.phone_line", phone=_phone_label(phone))


def _render_active_client_menu_text(
    locale: str,
    target_phone: str | None,
    client: _ClientModel,
) -> str:
    return t(
        locale,
        "wa.tenant.client_context.menu.active",
        client_name=client.full_name,
        phone_line=_client_phone_line(locale, target_phone or client.phone),
        status=t(locale, "wa.tenant.clients.detail.status_active"),
    )


def _render_inactive_client_menu_text(
    locale: str,
    target_phone: str | None,
    client: _ClientModel,
) -> str:
    return t(
        locale,
        "wa.tenant.client_context.menu.inactive",
        client_name=client.full_name,
        phone_line=_client_phone_line(locale, target_phone or client.phone),
        status=t(locale, "wa.tenant.clients.detail.status_inactive"),
    )


def _render_active_client_detail_text(
    locale: str,
    target_phone: str | None,
    client: _ClientModel,
) -> str:
    body = t(
        locale,
        "wa.tenant.client_context.detail.body",
        client_name=client.full_name,
        username=client.username,
        phone_line=_client_phone_line(locale, target_phone or client.phone),
        status=t(locale, "wa.tenant.clients.detail.status_active"),
    )
    return body + "\n" + t(locale, "wa.tenant.client_context.detail.options")


def _with_current_screen_message(message: str, screen_text: str) -> str:
    return f"{message}\n\n{screen_text}".strip()


async def handle_ctx_active_client_menu(
    msg_lower: str,
    message: str,
    data: dict,
    admin_jid: str | None,
    client: _ClientModel,
    tenant: _TenantModel,
    db: AsyncSession,
    save_ctx,
    clear_ctx,
) -> WhatsAppConsoleResponse:
    locale = _ctx_locale(tenant, data)
    target_phone = data.get("temp_data", {}).get("target_phone")

    if msg_lower == "1":
        data["step"] = "active_detail"
        data["temp_data"]["client_id"] = str(client.id)
        await save_ctx(refresh_ttl=True)
        return WhatsAppConsoleResponse(
            reply=_render_active_client_detail_text(locale, target_phone, client),
            reply_to=admin_jid,
        )

    if msg_lower == "2":
        data["step"] = "active_edit_field"
        data["temp_data"]["client_id"] = str(client.id)
        await save_ctx(refresh_ttl=True)
        return WhatsAppConsoleResponse(
            reply=_ctx_t(tenant, data, "wa.tenant.client_context.edit.field_prompt"),
            reply_to=admin_jid,
        )

    if msg_lower == "3":
        return await _start_context_subscription(
            client, data, admin_jid, tenant, db, save_ctx, clear_ctx
        )

    if msg_lower == "4":
        data["step"] = "active_deactivate_confirm"
        await save_ctx(refresh_ttl=True)
        return WhatsAppConsoleResponse(
            reply=_ctx_t(
                tenant,
                data,
                "wa.tenant.client_context.deactivate.confirm",
                client_name=client.full_name,
            ),
            reply_to=admin_jid,
        )

    if msg_lower == "5":
        await save_ctx(refresh_ttl=True)
        return WhatsAppConsoleResponse(
            reply=_with_current_screen_message(
                _ctx_t(
                    tenant,
                    data,
                    "wa.tenant.client_context.active.delete_blocked",
                    client_name=client.full_name,
                    phone_line=_client_phone_line(locale, target_phone or client.phone),
                ),
                _render_active_client_menu_text(locale, target_phone, client),
            ),
            reply_to=admin_jid,
        )

    await save_ctx(refresh_ttl=True)
    return WhatsAppConsoleResponse(
        reply=_with_current_screen_message(
            _ctx_t(tenant, data, "wa.tenant.client_context.invalid_option"),
            _render_active_client_menu_text(locale, target_phone, client),
        ),
        reply_to=admin_jid,
    )
```

Update the active/inactive menu templates in both catalogs so the phone line becomes optional and add the new active delete-blocking key.

```python
# backend/app/core/i18n/catalogs_es_wa.py
"wa.tenant.client_context.phone_line": "Numero de telefono: {phone}\n",
"wa.tenant.client_context.menu.active": "📌 *Gestion del cliente*\n\nEstas administrando este cliente desde tu panel privado.\nEl cliente no ve este menu.\n\nCliente: {client_name}\n{phone_line}Estado: {status}\n\nElige una opcion:\n1️⃣ Ver detalle\n2️⃣ Editar cliente\n3️⃣ Crear suscripcion\n4️⃣ Desactivar cliente\n5️⃣ Eliminar cliente\n0️⃣ Cancelar",
"wa.tenant.client_context.menu.inactive": "📌 *Gestion del cliente*\n\nEstas administrando este cliente desde tu panel privado.\nEl cliente no ve este menu.\n\nCliente: {client_name}\n{phone_line}Estado: {status}\n\nElige una opcion:\n1️⃣ Ver detalle\n2️⃣ Editar cliente\n3️⃣ Reactivar cliente\n4️⃣ Eliminar cliente\n0️⃣ Cancelar",
"wa.tenant.client_context.active.delete_blocked": "❌ No se puede eliminar un cliente activo.\n\nCliente: {client_name}\n{phone_line}\nDesactivalo primero y luego intenta eliminarlo.",

# backend/app/core/i18n/catalogs_en_wa.py
"wa.tenant.client_context.phone_line": "Phone number: {phone}\n",
"wa.tenant.client_context.menu.active": "📌 *Client management*\n\nYou are managing this client from your private panel.\nThe client cannot see this menu.\n\nClient: {client_name}\n{phone_line}Status: {status}\n\nChoose an option:\n1️⃣ View details\n2️⃣ Edit client\n3️⃣ Create subscription\n4️⃣ Deactivate client\n5️⃣ Delete client\n0️⃣ Cancel",
"wa.tenant.client_context.menu.inactive": "📌 *Client management*\n\nYou are managing this client from your private panel.\nThe client cannot see this menu.\n\nClient: {client_name}\n{phone_line}Status: {status}\n\nChoose an option:\n1️⃣ View details\n2️⃣ Edit client\n3️⃣ Reactivate client\n4️⃣ Delete client\n0️⃣ Cancel",
"wa.tenant.client_context.active.delete_blocked": "❌ An active client cannot be deleted.\n\nClient: {client_name}\n{phone_line}\nDeactivate the client first and then try deleting it again.",
```

Also update the active/inactive client branch in `render_initial_context_menu()` so it calls the new root render helpers instead of formatting the root menu templates with the old `identity=` placeholder.

```python
if client is not None:
    variant = "existing_active" if client.is_active else "existing_inactive"
    render_menu = (
        _render_active_client_menu_text if client.is_active else _render_inactive_client_menu_text
    )
    return render_menu(locale, target_phone, client), {
        "target_state": variant,
        "menu_variant": variant,
        "client_id": str(client.id),
        "identity": identity,
        "locale": locale,
    }
```

- [ ] **Step 4: Re-run the active-root tests and make them pass**

Run:

```bash
cd backend && uv run pytest tests/test_whatsapp_client_context_shortcut.py -k "active_menu_option_2 or active_menu_option_3 or active_menu_option_5 or active_menu_invalid_input" -v
```

Expected: all four tests PASS.

- [ ] **Step 5: Commit the active-root alignment**

```bash
git add backend/tests/test_whatsapp_client_context_shortcut.py backend/app/api/v1/endpoints/integrations/console_context_shortcut.py backend/app/core/i18n/catalogs_es_wa.py backend/app/core/i18n/catalogs_en_wa.py
git commit -m "fix(client-context): align active root menu options with rendered menu"
```


### Task 2: Fix Active Detail/Edit/Deactivate Screen Re-rendering

**Files:**
- Modify: `backend/tests/test_whatsapp_client_context_shortcut.py`
- Modify: `backend/app/api/v1/endpoints/integrations/console_context_shortcut.py`
- Modify: `backend/app/api/v1/endpoints/integrations/console_handlers.py`
- Modify: `backend/app/core/i18n/catalogs_es_wa.py`
- Modify: `backend/app/core/i18n/catalogs_en_wa.py`

- [ ] **Step 1: Add failing tests for active detail back-navigation and success-screen rendering**

Append these tests to `backend/tests/test_whatsapp_client_context_shortcut.py`.

```python
async def test_active_detail_back_rerenders_active_root_menu(
    client, db_session, active_tenant_user
):
    tenant = await _setup_tenant_with_instance(db_session, active_tenant_user)
    admin_phone_digits = tenant.whatsapp_phone.lstrip("+")
    await _create_context_client(
        db_session,
        tenant,
        phone="12015559995",
        is_active=True,
        full_name="Back Active Client",
        username="tna01_ctx_back",
    )
    fake_mgr = _FakeManager(used_backup=False)
    await _seed_shortcut_context(
        fake_mgr,
        admin_phone_digits,
        target_phone="12015559995",
        step="active_detail",
    )

    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={"phone": tenant.whatsapp_phone, "message": "9", "instance": TEST_INSTANCE},
            headers={"X-API-Key": settings.n8n_api_key},
        )

    reply = response.json()["reply"]
    assert "Editar cliente" in reply
    assert "Crear suscripcion" in reply
    assert "Desactivar cliente" in reply


async def test_active_edit_field_back_returns_full_active_detail(
    client, db_session, active_tenant_user
):
    tenant = await _setup_tenant_with_instance(db_session, active_tenant_user)
    admin_phone_digits = tenant.whatsapp_phone.lstrip("+")
    await _create_context_client(
        db_session,
        tenant,
        phone="12015559994",
        is_active=True,
        full_name="Editable Active Client",
        username="tna01_ctx_edit_back",
    )
    fake_mgr = _FakeManager(used_backup=False)
    await _seed_shortcut_context(
        fake_mgr,
        admin_phone_digits,
        target_phone="12015559994",
        step="active_edit_field",
    )

    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={"phone": tenant.whatsapp_phone, "message": "9", "instance": TEST_INSTANCE},
            headers={"X-API-Key": settings.n8n_api_key},
        )

    reply = response.json()["reply"]
    assert "Editable Active Client" in reply
    assert "Usuario:" in reply
    assert "1 Editar datos" in reply
    assert "2 Desactivar" in reply


async def test_active_edit_success_shows_updated_detail_screen(
    client, db_session, active_tenant_user
):
    tenant = await _setup_tenant_with_instance(db_session, active_tenant_user)
    admin_phone_digits = tenant.whatsapp_phone.lstrip("+")
    ctx_client = await _create_context_client(
        db_session,
        tenant,
        phone="12015559993",
        is_active=True,
        full_name="Old Active Name",
        username="tna01_ctx_edit_success",
    )
    fake_mgr = _FakeManager(used_backup=False)
    ctx_key = await _seed_shortcut_context(
        fake_mgr,
        admin_phone_digits,
        target_phone="12015559993",
        step="active_edit_value",
    )
    raw = json.loads(await fake_mgr._redis.get(ctx_key))
    raw["temp_data"]["client_id"] = str(ctx_client.id)
    raw["temp_data"]["edit_field"] = "full_name"
    await fake_mgr._redis.set(ctx_key, json.dumps(raw), ex=300)

    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={"phone": tenant.whatsapp_phone, "message": "New Active Name", "instance": TEST_INSTANCE},
            headers={"X-API-Key": settings.n8n_api_key},
        )

    reply = response.json()["reply"]
    assert "actualizado correctamente" in reply.lower()
    assert "New Active Name" in reply
    assert "1 Editar datos" in reply
    assert "2 Desactivar" in reply


async def test_active_menu_option_4_opens_deactivate_confirm(
    client, db_session, active_tenant_user
):
    tenant = await _setup_tenant_with_instance(db_session, active_tenant_user)
    admin_phone_digits = tenant.whatsapp_phone.lstrip("+")
    ctx_client = await _create_context_client(
        db_session,
        tenant,
        phone="12015559992",
        is_active=True,
        full_name="Deactivate Active Client",
        username="tna01_ctx_deactivate",
    )
    fake_mgr = _FakeManager(used_backup=False)
    ctx_key = await _seed_shortcut_context(
        fake_mgr,
        admin_phone_digits,
        target_phone="12015559992",
        step="menu",
    )
    raw = json.loads(await fake_mgr._redis.get(ctx_key))
    raw["temp_data"]["client_id"] = str(ctx_client.id)
    await fake_mgr._redis.set(ctx_key, json.dumps(raw), ex=300)

    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={"phone": tenant.whatsapp_phone, "message": "4", "instance": TEST_INSTANCE},
            headers={"X-API-Key": settings.n8n_api_key},
        )

    reply = response.json()["reply"]
    assert "desactivar" in reply.lower()
    assert "CONFIRMAR" in reply


async def test_active_deactivate_confirm_success_shows_inactive_menu(
    client, db_session, active_tenant_user
):
    tenant = await _setup_tenant_with_instance(db_session, active_tenant_user)
    admin_phone_digits = tenant.whatsapp_phone.lstrip("+")
    ctx_client = await _create_context_client(
        db_session,
        tenant,
        phone="12015559992",
        is_active=True,
        full_name="Deactivate Active Client",
        username="tna01_ctx_deactivate",
    )
    fake_mgr = _FakeManager(used_backup=False)
    ctx_key = await _seed_shortcut_context(
        fake_mgr,
        admin_phone_digits,
        target_phone="12015559992",
        step="active_deactivate_confirm",
    )
    raw = json.loads(await fake_mgr._redis.get(ctx_key))
    raw["temp_data"]["client_id"] = str(ctx_client.id)
    await fake_mgr._redis.set(ctx_key, json.dumps(raw), ex=300)

    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={"phone": tenant.whatsapp_phone, "message": "CONFIRMAR", "instance": TEST_INSTANCE},
            headers={"X-API-Key": settings.n8n_api_key},
        )

    reply = response.json()["reply"]
    assert "desactivado" in reply.lower()
    assert "Reactivar cliente" in reply
    assert "Eliminar cliente" in reply
```

- [ ] **Step 2: Run the active detail/edit/deactivate tests and confirm they fail**

Run:

```bash
cd backend && uv run pytest tests/test_whatsapp_client_context_shortcut.py -k "active_detail_back or active_edit_field_back or active_edit_success or active_menu_option_4 or active_deactivate_confirm_success" -v
```

Expected:
- `active_detail_back` fails because `9` still returns the old `active.menu_text` short menu.
- `active_edit_field_back` fails because `9` still returns only the detail header.
- `active_edit_success` fails because the handler currently returns success text without the refreshed detail screen.
- `active_menu_option_4_opens_deactivate_confirm` fails because root option `4` is still invalid.
- `active_deactivate_confirm_success` fails because the handler currently returns success text without the refreshed inactive root menu.

- [ ] **Step 3: Implement active detail renderers, fix `9` behavior, and return refreshed success screens**

Update `backend/app/api/v1/endpoints/integrations/console_context_shortcut.py`.

```python
async def handle_ctx_active_detail(
    msg_lower: str,
    message: str,
    data: dict,
    admin_jid: str | None,
    client: _ClientModel,
    tenant: _TenantModel,
    db: AsyncSession,
    save_ctx,
    clear_ctx,
) -> WhatsAppConsoleResponse:
    locale = _ctx_locale(tenant, data)
    target_phone = data.get("temp_data", {}).get("target_phone")

    if is_back(msg_lower):
        data["step"] = "active_menu"
        await save_ctx(refresh_ttl=True)
        return WhatsAppConsoleResponse(
            reply=_render_active_client_menu_text(locale, target_phone, client),
            reply_to=admin_jid,
        )

    if msg_lower == "1":
        data["step"] = "active_edit_field"
        await save_ctx(refresh_ttl=True)
        return WhatsAppConsoleResponse(
            reply=_ctx_t(tenant, data, "wa.tenant.client_context.edit.field_prompt"),
            reply_to=admin_jid,
        )

    if msg_lower == "2":
        data["step"] = "active_deactivate_confirm"
        await save_ctx(refresh_ttl=True)
        return WhatsAppConsoleResponse(
            reply=_ctx_t(
                tenant,
                data,
                "wa.tenant.client_context.deactivate.confirm",
                client_name=client.full_name,
            ),
            reply_to=admin_jid,
        )

    await save_ctx(refresh_ttl=False)
    return WhatsAppConsoleResponse(
        reply=_with_current_screen_message(
            _ctx_t(tenant, data, "wa.tenant.client_context.invalid_option"),
            _render_active_client_detail_text(locale, target_phone, client),
        ),
        reply_to=admin_jid,
    )


async def handle_ctx_active_edit_field(
    msg_lower: str,
    message: str,
    data: dict,
    admin_jid: str | None,
    tenant: _TenantModel,
    client: _ClientModel,
) -> WhatsAppConsoleResponse | None:
    if is_back(msg_lower):
        locale = _ctx_locale(tenant, data)
        target_phone = data.get("temp_data", {}).get("target_phone")
        data["step"] = "active_detail"
        return WhatsAppConsoleResponse(
            reply=_render_active_client_detail_text(locale, target_phone, client),
            reply_to=admin_jid,
        )

    if msg_lower == "1":
        data["temp_data"]["edit_field"] = "full_name"
        data["step"] = "active_edit_value"
        return WhatsAppConsoleResponse(
            reply=_ctx_t(tenant, data, "wa.tenant.client_context.edit.name_prompt"),
            reply_to=admin_jid,
        )

    if msg_lower == "2":
        data["temp_data"]["edit_field"] = "local_username"
        data["step"] = "active_edit_value"
        return WhatsAppConsoleResponse(
            reply=_ctx_t(tenant, data, "wa.tenant.client_context.edit.username_prompt"),
            reply_to=admin_jid,
        )

    return WhatsAppConsoleResponse(
        reply=_ctx_t(tenant, data, "wa.tenant.client_context.edit.field_invalid"),
        reply_to=admin_jid,
    )


async def handle_ctx_active_edit_value(
    msg_lower: str,
    message: str,
    data: dict,
    admin_jid: str | None,
    tenant: _TenantModel,
    db: AsyncSession,
    save_ctx,
    clear_ctx,
) -> WhatsAppConsoleResponse:
    if is_back(msg_lower):
        data["step"] = "active_edit_field"
        await save_ctx(refresh_ttl=True)
        return WhatsAppConsoleResponse(
            reply=_ctx_t(tenant, data, "wa.tenant.client_context.edit.field_prompt"),
            reply_to=admin_jid,
        )

    field = data["temp_data"].get("edit_field", "")
    new_value = message.strip()
    client_id = UUID(data["temp_data"]["client_id"])
    locale = _ctx_locale(tenant, data)
    target_phone = data.get("temp_data", {}).get("target_phone")
    prompt_key = (
        "wa.tenant.client_context.edit.name_prompt"
        if field == "full_name"
        else "wa.tenant.client_context.edit.username_prompt"
    )

    from app.schemas.client import ClientUpdate

    payload = ClientUpdate(**{field: new_value})
    try:
        client_service = ClientService()
        client = await client_service.update_client(db, tenant.id, client_id, payload)
    except UserFacingError as exc:
        await save_ctx(refresh_ttl=False)
        return WhatsAppConsoleResponse(
            reply=_with_current_screen_message(
                translate_error(locale, exc),
                _ctx_t(tenant, data, prompt_key),
            ),
            reply_to=admin_jid,
        )
    except Exception as exc:
        await clear_ctx()
        return WhatsAppConsoleResponse(
            reply=_ctx_t(tenant, data, "wa.tenant.client_context.edit.update_error", exc=str(exc)),
            reply_to=admin_jid,
        )

    if client is None:
        await clear_ctx()
        return WhatsAppConsoleResponse(
            reply=_ctx_t(tenant, data, "wa.tenant.client_context.error.client_not_found"),
            reply_to=admin_jid,
        )

    data["temp_data"].pop("edit_field", None)
    data["step"] = "active_detail"
    await save_ctx(refresh_ttl=True)
    return WhatsAppConsoleResponse(
        reply=_with_current_screen_message(
            _ctx_t(
                tenant,
                data,
                "wa.tenant.client_context.edit.updated_success",
                client_name=client.full_name,
            ),
            _render_active_client_detail_text(locale, target_phone, client),
        ),
        reply_to=admin_jid,
    )


async def handle_ctx_active_deactivate_confirm(
    msg_lower: str,
    message: str,
    data: dict,
    admin_jid: str | None,
    tenant: _TenantModel,
    db: AsyncSession,
    save_ctx,
    clear_ctx,
) -> WhatsAppConsoleResponse:
    stripped = message.strip().upper()
    if stripped not in ("CONFIRMAR", "CONFIRM"):
        return WhatsAppConsoleResponse(
            reply=_ctx_t(tenant, data, "wa.tenant.client_context.deactivate.prompt_again"),
            reply_to=admin_jid,
        )

    client_id = UUID(data["temp_data"]["client_id"])
    try:
        client_service = ClientService()
        client = await client_service.deactivate_client(db, tenant.id, client_id)
    except Exception as exc:
        await clear_ctx()
        return WhatsAppConsoleResponse(
            reply=_ctx_t(tenant, data, "wa.tenant.client_context.deactivate.error", exc=str(exc)),
            reply_to=admin_jid,
        )

    if client is None:
        await clear_ctx()
        return WhatsAppConsoleResponse(
            reply=_ctx_t(tenant, data, "wa.tenant.client_context.error.client_not_found"),
            reply_to=admin_jid,
        )

    locale = _ctx_locale(tenant, data)
    target_phone = data.get("temp_data", {}).get("target_phone")
    data["temp_data"]["menu_variant"] = "existing_inactive"
    data["temp_data"]["target_state"] = "existing_inactive"
    data["step"] = "inactive_menu"
    await save_ctx(refresh_ttl=True)
    return WhatsAppConsoleResponse(
        reply=_with_current_screen_message(
            _ctx_t(
                tenant,
                data,
                "wa.tenant.client_context.deactivate.success",
                client_name=client.full_name,
            ),
            _render_inactive_client_menu_text(locale, target_phone, client),
        ),
        reply_to=admin_jid,
    )
```

Update `detail.body` in both catalogs so it accepts `phone_line` instead of a mandatory `phone` field.

```python
# backend/app/core/i18n/catalogs_es_wa.py
"wa.tenant.client_context.detail.body": "*{client_name}*\nUsuario: {username}\n{phone_line}Estado: {status}\n",

# backend/app/core/i18n/catalogs_en_wa.py
"wa.tenant.client_context.detail.body": "*{client_name}*\nUsername: {username}\n{phone_line}Status: {status}\n",
```

Update `backend/app/api/v1/endpoints/integrations/console_handlers.py` so the active edit-field dispatcher passes `active_client` into the updated handler signature.

```python
if step == "active_edit_field":
    resp = await handle_ctx_active_edit_field(
        msg_lower,
        message,
        data,
        admin_jid,
        tenant,
        active_client,
    )
```

- [ ] **Step 4: Re-run the active detail/edit/deactivate tests**

Run:

```bash
cd backend && uv run pytest tests/test_whatsapp_client_context_shortcut.py -k "active_detail_back or active_edit_field_back or active_edit_success or active_menu_option_4 or active_deactivate_confirm_success" -v
```

Expected: all five tests PASS.

- [ ] **Step 5: Commit the active screen re-render fixes**

```bash
git add backend/tests/test_whatsapp_client_context_shortcut.py backend/app/api/v1/endpoints/integrations/console_context_shortcut.py backend/app/api/v1/endpoints/integrations/console_handlers.py backend/app/core/i18n/catalogs_es_wa.py backend/app/core/i18n/catalogs_en_wa.py
git commit -m "fix(client-context): rerender active contextual screens consistently"
```


### Task 3: Align the Inactive Root/Detail/Edit/Delete Flow

**Files:**
- Modify: `backend/tests/test_whatsapp_client_context_shortcut.py`
- Modify: `backend/app/api/v1/endpoints/integrations/console_context_shortcut.py`
- Modify: `backend/app/api/v1/endpoints/integrations/console_handlers.py`
- Modify: `backend/app/core/i18n/catalogs_es_wa.py`
- Modify: `backend/app/core/i18n/catalogs_en_wa.py`

- [ ] **Step 1: Add failing tests for inactive root/detail behavior and LID-only phone hiding**

Append these tests to `backend/tests/test_whatsapp_client_context_shortcut.py`.

```python
from app.api.v1.endpoints.integrations.console_context_shortcut import render_initial_context_menu


async def test_inactive_menu_option_1_shows_detail(
    client, db_session, active_tenant_user
):
    tenant = await _setup_tenant_with_instance(db_session, active_tenant_user)
    admin_phone_digits = tenant.whatsapp_phone.lstrip("+")
    await _create_context_client(
        db_session,
        tenant,
        phone="12015559991",
        is_active=False,
        full_name="Inactive Detail Client",
        username="tna01_ctx_inactive_detail",
    )
    fake_mgr = _FakeManager(used_backup=False)
    await _seed_shortcut_context(fake_mgr, admin_phone_digits, target_phone="12015559991")

    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={"phone": tenant.whatsapp_phone, "message": "1", "instance": TEST_INSTANCE},
            headers={"X-API-Key": settings.n8n_api_key},
        )

    reply = response.json()["reply"]
    assert "Inactive Detail Client" in reply
    assert "Usuario:" in reply
    assert "Reactivar" in reply
    assert "Eliminar" in reply


async def test_inactive_menu_option_3_reactivates_and_shows_active_menu(
    client, db_session, active_tenant_user
):
    tenant = await _setup_tenant_with_instance(db_session, active_tenant_user)
    admin_phone_digits = tenant.whatsapp_phone.lstrip("+")
    await _create_context_client(
        db_session,
        tenant,
        phone="12015559990",
        is_active=False,
        full_name="Reactivatable Client",
        username="tna01_ctx_reactivate",
    )
    fake_mgr = _FakeManager(used_backup=False)
    ctx_key = await _seed_shortcut_context(fake_mgr, admin_phone_digits, target_phone="12015559990")

    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={"phone": tenant.whatsapp_phone, "message": "3", "instance": TEST_INSTANCE},
            headers={"X-API-Key": settings.n8n_api_key},
        )

    reply = response.json()["reply"]
    assert "reactivado" in reply.lower()
    assert "Crear suscripcion" in reply
    ctx_data = json.loads(await fake_mgr._redis.get(ctx_key))
    assert ctx_data["step"] == "active_menu"


async def test_inactive_menu_option_4_delete_flow_shows_unregistered_menu_after_confirm(
    client, db_session, active_tenant_user
):
    tenant = await _setup_tenant_with_instance(db_session, active_tenant_user)
    admin_phone_digits = tenant.whatsapp_phone.lstrip("+")
    ctx_client = await _create_context_client(
        db_session,
        tenant,
        phone="12015559989",
        is_active=False,
        full_name="Delete Inactive Client",
        username="tna01_ctx_delete",
    )
    fake_mgr = _FakeManager(used_backup=False)
    ctx_key = await _seed_shortcut_context(
        fake_mgr,
        admin_phone_digits,
        target_phone="12015559989",
        step="inactive_menu",
    )
    raw = json.loads(await fake_mgr._redis.get(ctx_key))
    raw["temp_data"]["client_id"] = str(ctx_client.id)
    await fake_mgr._redis.set(ctx_key, json.dumps(raw), ex=300)

    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        prompt_response = await client.post(
            ENDPOINT,
            json={"phone": tenant.whatsapp_phone, "message": "4", "instance": TEST_INSTANCE},
            headers={"X-API-Key": settings.n8n_api_key},
        )
        assert "eliminar permanentemente" in prompt_response.json()["reply"].lower()

        response = await client.post(
            ENDPOINT,
            json={"phone": tenant.whatsapp_phone, "message": "CONFIRMAR", "instance": TEST_INSTANCE},
            headers={"X-API-Key": settings.n8n_api_key},
        )

    reply = response.json()["reply"]
    assert "eliminado" in reply.lower()
    assert "Crear cliente para este numero" in reply
    assert "Bloquear acceso" in reply


async def test_inactive_menu_invalid_input_rerenders_full_menu_and_refreshes_ttl(
    client, db_session, active_tenant_user
):
    tenant = await _setup_tenant_with_instance(db_session, active_tenant_user)
    admin_phone_digits = tenant.whatsapp_phone.lstrip("+")
    await _create_context_client(
        db_session,
        tenant,
        phone="12015559988",
        is_active=False,
        full_name="Invalid Inactive Client",
        username="tna01_ctx_inactive_invalid",
    )
    fake_mgr = _FakeManager(used_backup=False)
    ctx_key = await _seed_shortcut_context(
        fake_mgr,
        admin_phone_digits,
        target_phone="12015559988",
        ttl=123,
    )

    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={"phone": tenant.whatsapp_phone, "message": "9", "instance": TEST_INSTANCE},
            headers={"X-API-Key": settings.n8n_api_key},
        )

    reply = response.json()["reply"]
    assert "Opcion invalida" in reply
    assert "Ver detalle" in reply
    assert "Editar cliente" in reply
    assert "Reactivar cliente" in reply
    assert "Eliminar cliente" in reply
    assert fake_mgr._redis._ttls[ctx_key] == 300


async def test_render_initial_context_menu_lid_only_hides_phone_line(
    db_session, active_tenant_user
):
    tenant = await _setup_tenant_with_instance(db_session, active_tenant_user)
    rendered, metadata = await render_initial_context_menu(
        db=db_session,
        tenant=tenant,
        target_phone=None,
        target_lid="998877665544@lid",
        target_jid="998877665544@lid",
    )

    assert "Numero de telefono" not in rendered
    assert metadata["menu_variant"] == "unregistered"
```

- [ ] **Step 2: Run the inactive/LID-only tests and confirm they fail**

Run:

```bash
cd backend && uv run pytest tests/test_whatsapp_client_context_shortcut.py -k "inactive_menu_option_1 or inactive_menu_option_3 or inactive_menu_option_4 or inactive_menu_invalid_input or lid_only_hides_phone_line" -v
```

Expected:
- Inactive option `1` fails because it still reactivates instead of showing detail.
- Inactive option `3` fails because it still deletes instead of reactivating.
- Inactive delete success fails because the handler still returns success text without the unregistered root menu.
- Inactive root invalid input fails because it still shows the old short inactive menu and keeps the old TTL.
- LID-only render fails if any active/inactive/detail template still hardcodes the phone label.

- [ ] **Step 3: Implement inactive detail, inactive root alignment, edit backflow, delete/reactivate success rendering, and dispatcher wiring**

In `backend/app/api/v1/endpoints/integrations/console_context_shortcut.py`, add an inactive detail renderer and a new `handle_ctx_inactive_detail()` handler.

```python
def _render_inactive_client_detail_text(
    locale: str,
    target_phone: str | None,
    client: _ClientModel,
) -> str:
    body = t(
        locale,
        "wa.tenant.client_context.detail.body",
        client_name=client.full_name,
        username=client.username,
        phone_line=_client_phone_line(locale, target_phone or client.phone),
        status=t(locale, "wa.tenant.clients.detail.status_inactive"),
    )
    return body + "\n" + t(locale, "wa.tenant.client_context.inactive.detail.options")


async def _reactivate_context_client(
    client: _ClientModel,
    data: dict,
    admin_jid: str | None,
    tenant: _TenantModel,
    db: AsyncSession,
    save_ctx,
    clear_ctx,
) -> WhatsAppConsoleResponse:
    locale = _ctx_locale(tenant, data)
    target_phone = data.get("temp_data", {}).get("target_phone")
    client_id = UUID(str(client.id))

    try:
        client_service = ClientService()
        updated = await client_service.activate_client(db, tenant.id, client_id)
    except Exception as exc:
        await clear_ctx()
        return WhatsAppConsoleResponse(
            reply=_ctx_t(tenant, data, "wa.tenant.client_context.inactive.reactivate_error", exc=str(exc)),
            reply_to=admin_jid,
        )

    if updated is None:
        await clear_ctx()
        return WhatsAppConsoleResponse(
            reply=_ctx_t(tenant, data, "wa.tenant.client_context.error.client_not_found"),
            reply_to=admin_jid,
        )

    data["temp_data"]["client_id"] = str(updated.id)
    data["temp_data"]["menu_variant"] = "existing_active"
    data["temp_data"]["target_state"] = "existing_active"
    data["step"] = "active_menu"
    await save_ctx(refresh_ttl=True)
    return WhatsAppConsoleResponse(
        reply=_with_current_screen_message(
            _ctx_t(
                tenant,
                data,
                "wa.tenant.client_context.inactive.reactivate_success",
                client_name=updated.full_name,
            ),
            _render_active_client_menu_text(locale, target_phone, updated),
        ),
        reply_to=admin_jid,
    )


async def handle_ctx_inactive_client_menu(
    msg_lower: str,
    message: str,
    data: dict,
    admin_jid: str | None,
    client: _ClientModel,
    tenant: _TenantModel,
    db: AsyncSession,
    save_ctx,
    clear_ctx,
) -> WhatsAppConsoleResponse:
    locale = _ctx_locale(tenant, data)
    target_phone = data.get("temp_data", {}).get("target_phone")

    if msg_lower == "1":
        data["step"] = "inactive_detail"
        data["temp_data"]["client_id"] = str(client.id)
        await save_ctx(refresh_ttl=True)
        return WhatsAppConsoleResponse(
            reply=_render_inactive_client_detail_text(locale, target_phone, client),
            reply_to=admin_jid,
        )

    if msg_lower == "2":
        data["step"] = "inactive_edit_field"
        data["temp_data"]["client_id"] = str(client.id)
        await save_ctx(refresh_ttl=True)
        return WhatsAppConsoleResponse(
            reply=_ctx_t(tenant, data, "wa.tenant.client_context.edit.field_prompt"),
            reply_to=admin_jid,
        )

    if msg_lower == "3":
        return await _reactivate_context_client(
            client, data, admin_jid, tenant, db, save_ctx, clear_ctx
        )

    if msg_lower == "4":
        data["step"] = "inactive_delete_confirm"
        data["temp_data"]["client_id"] = str(client.id)
        await save_ctx(refresh_ttl=True)
        return WhatsAppConsoleResponse(
            reply=_ctx_t(
                tenant,
                data,
                "wa.tenant.client_context.inactive.delete_confirm",
                client_name=client.full_name,
            ),
            reply_to=admin_jid,
        )

    await save_ctx(refresh_ttl=True)
    return WhatsAppConsoleResponse(
        reply=_with_current_screen_message(
            _ctx_t(tenant, data, "wa.tenant.client_context.invalid_option"),
            _render_inactive_client_menu_text(locale, target_phone, client),
        ),
        reply_to=admin_jid,
    )


async def handle_ctx_inactive_detail(
    msg_lower: str,
    message: str,
    data: dict,
    admin_jid: str | None,
    client: _ClientModel,
    tenant: _TenantModel,
    db: AsyncSession,
    save_ctx,
    clear_ctx,
) -> WhatsAppConsoleResponse:
    locale = _ctx_locale(tenant, data)
    target_phone = data.get("temp_data", {}).get("target_phone")

    if is_back(msg_lower):
        data["step"] = "inactive_menu"
        await save_ctx(refresh_ttl=True)
        return WhatsAppConsoleResponse(
            reply=_render_inactive_client_menu_text(locale, target_phone, client),
            reply_to=admin_jid,
        )

    if msg_lower == "1":
        data["step"] = "inactive_edit_field"
        await save_ctx(refresh_ttl=True)
        return WhatsAppConsoleResponse(
            reply=_ctx_t(tenant, data, "wa.tenant.client_context.edit.field_prompt"),
            reply_to=admin_jid,
        )

    if msg_lower == "2":
        return await _reactivate_context_client(
            client, data, admin_jid, tenant, db, save_ctx, clear_ctx
        )

    if msg_lower == "3":
        data["step"] = "inactive_delete_confirm"
        await save_ctx(refresh_ttl=True)
        return WhatsAppConsoleResponse(
            reply=_ctx_t(
                tenant,
                data,
                "wa.tenant.client_context.inactive.delete_confirm",
                client_name=client.full_name,
            ),
            reply_to=admin_jid,
        )

    await save_ctx(refresh_ttl=False)
    return WhatsAppConsoleResponse(
        reply=_with_current_screen_message(
            _ctx_t(tenant, data, "wa.tenant.client_context.invalid_option"),
            _render_inactive_client_detail_text(locale, target_phone, client),
        ),
        reply_to=admin_jid,
    )
```

Fix inactive edit navigation and success behavior.

```python
async def handle_ctx_inactive_edit_field(
    msg_lower: str,
    message: str,
    data: dict,
    admin_jid: str | None,
    tenant: _TenantModel,
    client: _ClientModel,
) -> WhatsAppConsoleResponse | None:
    if is_back(msg_lower):
        locale = _ctx_locale(tenant, data)
        target_phone = data.get("temp_data", {}).get("target_phone")
        data["step"] = "inactive_detail"
        return WhatsAppConsoleResponse(
            reply=_render_inactive_client_detail_text(locale, target_phone, client),
            reply_to=admin_jid,
        )

    if msg_lower == "1":
        data["temp_data"]["edit_field"] = "full_name"
        data["step"] = "inactive_edit_value"
        return WhatsAppConsoleResponse(
            reply=_ctx_t(tenant, data, "wa.tenant.client_context.edit.name_prompt"),
            reply_to=admin_jid,
        )

    if msg_lower == "2":
        data["temp_data"]["edit_field"] = "local_username"
        data["step"] = "inactive_edit_value"
        return WhatsAppConsoleResponse(
            reply=_ctx_t(tenant, data, "wa.tenant.client_context.edit.username_prompt"),
            reply_to=admin_jid,
        )

    return WhatsAppConsoleResponse(
        reply=_ctx_t(tenant, data, "wa.tenant.client_context.edit.field_invalid"),
        reply_to=admin_jid,
    )


async def handle_ctx_inactive_edit_value(
    msg_lower: str,
    message: str,
    data: dict,
    admin_jid: str | None,
    tenant: _TenantModel,
    db: AsyncSession,
    save_ctx,
    clear_ctx,
) -> WhatsAppConsoleResponse:
    if is_back(msg_lower):
        data["step"] = "inactive_edit_field"
        await save_ctx(refresh_ttl=True)
        return WhatsAppConsoleResponse(
            reply=_ctx_t(tenant, data, "wa.tenant.client_context.edit.field_prompt"),
            reply_to=admin_jid,
        )

    field = data["temp_data"].get("edit_field", "")
    new_value = message.strip()
    client_id = UUID(data["temp_data"]["client_id"])
    locale = _ctx_locale(tenant, data)
    target_phone = data.get("temp_data", {}).get("target_phone")
    prompt_key = (
        "wa.tenant.client_context.edit.name_prompt"
        if field == "full_name"
        else "wa.tenant.client_context.edit.username_prompt"
    )

    from app.schemas.client import ClientUpdate

    payload = ClientUpdate(**{field: new_value})
    try:
        client_service = ClientService()
        client = await client_service.update_client(db, tenant.id, client_id, payload)
    except UserFacingError as exc:
        await save_ctx(refresh_ttl=False)
        return WhatsAppConsoleResponse(
            reply=_with_current_screen_message(
                translate_error(locale, exc),
                _ctx_t(tenant, data, prompt_key),
            ),
            reply_to=admin_jid,
        )
    except Exception as exc:
        await clear_ctx()
        return WhatsAppConsoleResponse(
            reply=_ctx_t(tenant, data, "wa.tenant.client_context.edit.update_error", exc=str(exc)),
            reply_to=admin_jid,
        )

    if client is None:
        await clear_ctx()
        return WhatsAppConsoleResponse(
            reply=_ctx_t(tenant, data, "wa.tenant.client_context.error.client_not_found"),
            reply_to=admin_jid,
        )

    data["temp_data"].pop("edit_field", None)
    data["step"] = "inactive_detail"
    await save_ctx(refresh_ttl=True)
    return WhatsAppConsoleResponse(
        reply=_with_current_screen_message(
            _ctx_t(
                tenant,
                data,
                "wa.tenant.client_context.edit.updated_success",
                client_name=client.full_name,
            ),
            _render_inactive_client_detail_text(locale, target_phone, client),
        ),
        reply_to=admin_jid,
    )


async def handle_ctx_inactive_delete_confirm(
    msg_lower: str,
    message: str,
    data: dict,
    admin_jid: str | None,
    tenant: _TenantModel,
    db: AsyncSession,
    save_ctx,
    clear_ctx,
) -> WhatsAppConsoleResponse:
    stripped = message.strip().upper()
    if stripped not in ("CONFIRMAR", "CONFIRM"):
        return WhatsAppConsoleResponse(
            reply=_ctx_t(tenant, data, "wa.tenant.client_context.inactive.delete_prompt_again"),
            reply_to=admin_jid,
        )

    client_id = UUID(data["temp_data"]["client_id"])
    client_name = ""
    client_service = ClientService()

    try:
        existing = await client_service.get_client(db, tenant.id, client_id)
        if existing:
            client_name = existing.full_name
    except Exception:
        pass

    try:
        deleted = await client_service.delete_client(db, tenant.id, client_id)
    except UserFacingError as exc:
        await clear_ctx()
        return WhatsAppConsoleResponse(
            reply=f"{translate_error(_ctx_locale(tenant, data), exc)}",
            reply_to=admin_jid,
        )
    except Exception as exc:
        await clear_ctx()
        return WhatsAppConsoleResponse(
            reply=_ctx_t(tenant, data, "wa.tenant.client_context.inactive.delete_error", exc=str(exc)),
            reply_to=admin_jid,
        )

    if not deleted:
        await clear_ctx()
        return WhatsAppConsoleResponse(
            reply=_ctx_t(tenant, data, "wa.tenant.client_context.inactive.delete_error", exc=""),
            reply_to=admin_jid,
        )

    data["temp_data"]["menu_variant"] = "unregistered"
    data["temp_data"]["target_state"] = "unregistered_unblocked"
    data["step"] = "menu"

    unregistered_menu, metadata = await render_initial_context_menu(
        db=db,
        tenant=tenant,
        target_phone=data.get("temp_data", {}).get("target_phone"),
        target_lid=data.get("temp_data", {}).get("target_lid"),
        target_jid=data.get("temp_data", {}).get("target_jid"),
    )
    data["temp_data"].update(metadata)
    await save_ctx(refresh_ttl=True)
    return WhatsAppConsoleResponse(
        reply=_with_current_screen_message(
            _ctx_t(
                tenant,
                data,
                "wa.tenant.client_context.inactive.delete_success",
                client_name=client_name,
            ),
            unregistered_menu,
        ),
        reply_to=admin_jid,
    )
```

Add the missing inactive detail options key to both catalogs.

```python
# backend/app/core/i18n/catalogs_es_wa.py
"wa.tenant.client_context.inactive.detail.options": "1 Editar datos\n2 Reactivar\n3 Eliminar\n9 Regresar\n0 Cancelar",

# backend/app/core/i18n/catalogs_en_wa.py
"wa.tenant.client_context.inactive.detail.options": "1 Edit data\n2 Reactivate\n3 Delete\n9 Back\n0 Cancel",
```

Wire the new step into `backend/app/api/v1/endpoints/integrations/console_handlers.py`.

```python
from app.api.v1.endpoints.integrations.console_context_shortcut import (  # noqa: F811
    handle_ctx_active_client_menu,
    handle_ctx_active_deactivate_confirm,
    handle_ctx_active_detail,
    handle_ctx_active_edit_field,
    handle_ctx_active_edit_value,
    handle_ctx_creating_confirm,
    handle_ctx_creating_first,
    handle_ctx_creating_name,
    handle_ctx_creating_password_choice,
    handle_ctx_creating_password_manual,
    handle_ctx_creating_phone,
    handle_ctx_creating_username,
    handle_ctx_inactive_client_menu,
    handle_ctx_inactive_delete_confirm,
    handle_ctx_inactive_detail,
    handle_ctx_inactive_edit_field,
    handle_ctx_inactive_edit_value,
    render_initial_context_menu,
)

inactive_steps = {
    "inactive_menu",
    "inactive_detail",
    "inactive_edit_field",
    "inactive_edit_value",
    "inactive_delete_confirm",
}

if step == "inactive_detail" and inactive_client is not None:
    return await handle_ctx_inactive_detail(
        msg_lower,
        message,
        data,
        admin_jid,
        inactive_client,
        tenant,
        db,
        _save_ctx,
        _clear_ctx,
    )
```

Also export the new handler from `__all__` in `console_context_shortcut.py`.

```python
__all__ = [
    "handle_ctx_creating_first",
    "handle_ctx_creating_phone",
    "handle_ctx_creating_name",
    "handle_ctx_creating_username",
    "handle_ctx_creating_password_choice",
    "handle_ctx_creating_password_manual",
    "handle_ctx_creating_confirm",
    "handle_ctx_active_client_menu",
    "handle_ctx_active_detail",
    "handle_ctx_active_edit_field",
    "handle_ctx_active_edit_value",
    "handle_ctx_active_deactivate_confirm",
    "handle_ctx_inactive_client_menu",
    "handle_ctx_inactive_detail",
    "handle_ctx_inactive_edit_field",
    "handle_ctx_inactive_edit_value",
    "handle_ctx_inactive_delete_confirm",
    "render_initial_context_menu",
]
```

- [ ] **Step 4: Re-run the inactive/LID-only tests**

Run:

```bash
cd backend && uv run pytest tests/test_whatsapp_client_context_shortcut.py -k "inactive_menu_option_1 or inactive_menu_option_3 or inactive_menu_option_4 or inactive_menu_invalid_input or lid_only_hides_phone_line" -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit the inactive-flow alignment**

```bash
git add backend/tests/test_whatsapp_client_context_shortcut.py backend/app/api/v1/endpoints/integrations/console_context_shortcut.py backend/app/api/v1/endpoints/integrations/console_handlers.py backend/app/core/i18n/catalogs_es_wa.py backend/app/core/i18n/catalogs_en_wa.py
git commit -m "fix(client-context): align inactive contextual flow and detail navigation"
```


### Task 4: Update Docs and Run Full Verification

**Files:**
- Modify: `docs/architecture/whatsapp-console-flow.md`
- Verify: `backend/tests/test_whatsapp_client_context_shortcut.py`
- Verify: `backend/` full pytest suite

- [ ] **Step 1: Update only the Client Context Shortcut section in the architecture doc**

Replace the outdated active/inactive menu tables in `docs/architecture/whatsapp-console-flow.md` with the approved contract.

```md
### Active client menu

| Option | Action |
|--------|--------|
| 1 | View client detail -> `active_detail` |
| 2 | Edit client -> `active_edit_field` |
| 3 | Create subscription with the client preselected |
| 4 | Deactivate client -> `active_deactivate_confirm` |
| 5 | Do not delete active client; explain that deactivation is required first and stay in `active_menu` |
| 0 | Close |

Root-menu notes:
- `9` is not shown in the root menu.
- If the admin sends `9` at the root menu, it is treated as invalid input.
- Invalid input at the root menu re-renders the same full contextual menu.

### Inactive client menu

| Option | Action |
|--------|--------|
| 1 | View client detail -> `inactive_detail` |
| 2 | Edit client -> `inactive_edit_field` |
| 3 | Reactivate client |
| 4 | Delete client -> `inactive_delete_confirm` |
| 0 | Close |

Inactive clients cannot be duplicated by contextual creation. The subscription shortcut remains unavailable until reactivation.
```

Keep the broader global-navigation section untouched; this task is scoped only to the Client Context Shortcut subsection.

- [ ] **Step 2: Run the focused client-context test file**

Run:

```bash
cd backend && uv run pytest tests/test_whatsapp_client_context_shortcut.py -v
```

Expected: PASS for the full shortcut regression file.

- [ ] **Step 3: Run the full backend suite required by the spec**

Run:

```bash
cd backend && uv run pytest
```

Expected: full backend suite PASS.

- [ ] **Step 4: Commit docs and any final test-driven touch-ups**

```bash
git add docs/architecture/whatsapp-console-flow.md backend/tests/test_whatsapp_client_context_shortcut.py backend/app/api/v1/endpoints/integrations/console_context_shortcut.py backend/app/api/v1/endpoints/integrations/console_handlers.py backend/app/core/i18n/catalogs_es_wa.py backend/app/core/i18n/catalogs_en_wa.py
git commit -m "docs(client-context): document aligned contextual menu contract"
```

---

## Self-Review Checklist

- Active root-menu coverage maps to Task 1.
- Active detail/edit/deactivate re-render and success-screen coverage maps to Task 2.
- Inactive root/detail/edit/delete coverage maps to Task 3.
- LID-only phone hiding maps to Task 3.
- Architecture doc update and full backend verification map to Task 4.
- No placeholder steps remain.
- Every code-changing task includes explicit file paths, code snippets, test commands, and commit commands.
