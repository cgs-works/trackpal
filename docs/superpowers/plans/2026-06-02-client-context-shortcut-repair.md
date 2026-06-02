# Client Context Shortcut Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix Tenant `/menu` contextual routing so self-chat opens the normal Tenant menu, external chats open an intuitive private client-management menu, `0` closes all Tenant-side state and the correct Evolution chat, Redis reads are reduced, and all shortcut messages use i18n.

**Architecture:** Backend owns routing, target-state resolution, i18n rendering, and close semantics. n8n remains pure transport and only obeys `reply_to`, `no_reply`, `status`, and new `close_jid`. Context payload stores stable metadata so active-context paths avoid duplicated Redis/session reads.

**Tech Stack:** FastAPI, Pydantic v2, SQLAlchemy async, Redis session service, backend i18n catalogs, n8n JSON workflow, pytest.

---

## File Structure

- Modify `backend/app/schemas/whatsapp.py`: add `close_jid` to response schema/serializer.
- Modify `backend/app/api/v1/endpoints/integrations/console.py`: self-target hardening, initial menu rendering, context metadata write.
- Modify `backend/app/api/v1/endpoints/integrations/console_handlers.py`: active context read/close flow, Tenant session delete, `close_jid` response.
- Modify `backend/app/api/v1/endpoints/integrations/console_context_shortcut.py`: i18n-backed menu/reply helpers; remove user-facing hardcoded shortcut strings.
- Modify `backend/app/core/i18n/catalogs_en_wa.py` and `backend/app/core/i18n/catalogs_es_wa.py`: add `wa.tenant.client_context.*` keys.
- Create migration under `backend/alembic/versions/`: rename `client_messaging_blocks` to `blocked_clients` and preserve indexes/constraints.
- Modify repositories/models/imports currently named for client messaging blocks to use blocked clients terminology.
- Modify `n8n/Trackpal WhatsApp Bot.json`: preserve `close_jid`; Close Session uses `close_jid || reply_to || remoteJid`.
- Modify `docs/superpowers/prds/client-context-shortcut.md`: sync approved behavior.
- Test `backend/tests/test_whatsapp_endpoint.py` and/or new `backend/tests/test_whatsapp_client_context_shortcut.py`: routing, menu variants, close semantics, i18n.

---

### Task 1: Response contract adds `close_jid`

**Files:**
- Modify: `backend/app/schemas/whatsapp.py`
- Test: `backend/tests/test_whatsapp_endpoint.py`

- [x] **Step 1: Write failing serializer test**

Append test:

```python
from app.schemas.whatsapp import WhatsAppConsoleResponse


def test_whatsapp_console_response_serializes_close_jid():
    response = WhatsAppConsoleResponse(
        reply="cerrado",
        status="closed",
        reply_to="34111111111@s.whatsapp.net",
        close_jid="34111111111@s.whatsapp.net",
    )

    assert response.model_dump() == {
        "reply": "cerrado",
        "status": "closed",
        "reply_to": "34111111111@s.whatsapp.net",
        "close_jid": "34111111111@s.whatsapp.net",
    }
```

- [x] **Step 2: Run failing test**

```bash
cd backend
uv run pytest tests/test_whatsapp_endpoint.py::test_whatsapp_console_response_serializes_close_jid -v
```

Expected: fail because `close_jid` is unexpected/missing.

- [x] **Step 3: Implement schema field**

In `WhatsAppConsoleResponse`, add field and serializer branch:

```python
    close_jid: str | None = None
```

```python
        if self.close_jid is not None:
            d["close_jid"] = self.close_jid
```

Update docstring with:

```python
        close_jid: Optional JID n8n must close in Evolution when
            ``status`` requests session close. This disambiguates
            admin private chat from target/client chat.
```

- [x] **Step 4: Verify**

```bash
cd backend
uv run pytest tests/test_whatsapp_endpoint.py::test_whatsapp_console_response_serializes_close_jid -v
```

Expected: pass.

- [x] **Step 5: Commit**

```bash
git add backend/app/schemas/whatsapp.py backend/tests/test_whatsapp_endpoint.py
git commit -m "feat: add WhatsApp close_jid response contract"
```

---

### Task 2: Rename access-blocking table to `blocked_clients`

**Files:**
- Create: `backend/alembic/versions/<revision>_rename_client_messaging_blocks_to_blocked_clients.py`
- Modify: model/repository files that currently define `client_messaging_blocks`
- Test: `backend/tests/test_whatsapp_client_context_shortcut.py`

- [x] **Step 1: Locate current model/repository names**
- [x] **Step 2: Write failing terminology/import test**
- [x] **Step 3: Create migration**
- [x] **Step 4: Rename code symbols**
- [x] **Step 5: Verify**
- [x] **Step 6: Commit** (09f5d98)

---

### Task 3: Add Client Context i18n catalog keys

**Files:**
- Modify: `backend/app/core/i18n/catalogs_en_wa.py`
- Modify: `backend/app/core/i18n/catalogs_es_wa.py`
- Test: `backend/tests/test_whatsapp_client_context_shortcut.py`

- [x] **Step 1: Write failing i18n key test**

Create/append:

```python
from app.core.i18n import t


def test_client_context_i18n_keys_exist_in_en_and_es():
    params = {"identity": "34123456789", "client_name": "Ana", "status": "Activo"}
    keys = [
        "wa.tenant.client_context.menu.unregistered_with_phone",
        "wa.tenant.client_context.menu.unregistered_lid_only",
        "wa.tenant.client_context.menu.blocked_with_phone",
        "wa.tenant.client_context.menu.blocked_lid_only",
        "wa.tenant.client_context.menu.active",
        "wa.tenant.client_context.menu.inactive",
        "wa.tenant.client_context.closed",
        "wa.tenant.client_context.collision",
        "wa.tenant.client_context.invalid_option",
        "wa.tenant.client_context.create.phone_prefilled",
        "wa.tenant.client_context.create.phone_prompt",
        "wa.tenant.client_context.block_access.success",
        "wa.tenant.client_context.unblock_access.success",
    ]
    for locale in ("en", "es"):
        for key in keys:
            rendered = t(locale, key, **params)
            assert rendered != key
            assert "Gestión del cliente" in rendered or "Client management" in rendered or key.endswith(("closed", "collision", "invalid_option", "success", "phone_prompt", "phone_prefilled"))
```

- [x] **Step 2: Run failing test**

```bash
cd backend
uv run pytest tests/test_whatsapp_client_context_shortcut.py::test_client_context_i18n_keys_exist_in_en_and_es -v
```

Expected: fail because keys missing.

- [x] **Step 3: Add EN keys**

Insert in `_CATALOG_EN_WA` near tenant client keys:

```python
    "wa.tenant.client_context.menu.unregistered_with_phone": "📌 *Client management*\n\nThis contact is not a client yet.\nThe client cannot see this menu.\n\nPhone number: {identity}\n\nChoose an option:\n1️⃣ Create client for this number\n2️⃣ Block access\n0️⃣ Cancel",
    "wa.tenant.client_context.menu.unregistered_lid_only": "📌 *Client management*\n\nThis contact is not a client yet.\nThe client cannot see this menu.\n\nChoose an option:\n1️⃣ Create client\n2️⃣ Block access\n0️⃣ Cancel",
    "wa.tenant.client_context.menu.blocked_with_phone": "📌 *Client management*\n\nThis contact is blocked from accessing the system.\nThey cannot request codes, view profile, or check subscriptions.\n\nPhone number: {identity}\n\nChoose an option:\n1️⃣ Unblock access\n0️⃣ Cancel",
    "wa.tenant.client_context.menu.blocked_lid_only": "📌 *Client management*\n\nThis contact is blocked from accessing the system.\nThey cannot request codes, view profile, or check subscriptions.\n\nChoose an option:\n1️⃣ Unblock access\n0️⃣ Cancel",
    "wa.tenant.client_context.menu.active": "📌 *Client management*\n\nYou are managing this client from your private panel.\nThe client cannot see this menu.\n\nClient: {client_name}\nPhone number: {identity}\nStatus: {status}\n\nChoose an option:\n1️⃣ View details\n2️⃣ Edit client\n3️⃣ Create subscription\n4️⃣ Deactivate client\n5️⃣ Delete client\n0️⃣ Cancel",
    "wa.tenant.client_context.menu.inactive": "📌 *Client management*\n\nYou are managing this client from your private panel.\nThe client cannot see this menu.\n\nClient: {client_name}\nPhone number: {identity}\nStatus: {status}\n\nChoose an option:\n1️⃣ View details\n2️⃣ Edit client\n3️⃣ Reactivate client\n4️⃣ Delete client\n0️⃣ Cancel",
    "wa.tenant.client_context.closed": "✅ Client management closed. Tenant console session was also closed.",
    "wa.tenant.client_context.collision": "⚠️ You already have a client management session open. Send *0* in your private Tenant chat before opening another one.",
    "wa.tenant.client_context.invalid_option": "❌ Invalid option. Reply with one of the menu numbers or *0* to cancel.",
    "wa.tenant.client_context.create.phone_prefilled": "Phone prefilled: {identity}\n\nType the client's *full name* or *0* to cancel:",
    "wa.tenant.client_context.create.phone_prompt": "Type the client's phone number to link it to this chat.\n\n0️⃣ Cancel",
    "wa.tenant.client_context.block_access.success": "✅ Access blocked for *{identity}*.",
    "wa.tenant.client_context.unblock_access.success": "✅ Access unblocked for *{identity}*.",
```

- [x] **Step 4: Add ES keys**

Insert equivalent in `_CATALOG_ES_WA`:

```python
    "wa.tenant.client_context.menu.unregistered_with_phone": "📌 *Gestión del cliente*\n\nEste contacto todavía no existe como cliente.\nEl cliente no ve este menú.\n\nNúmero de teléfono: {identity}\n\nElige una opción:\n1️⃣ Crear cliente para este número\n2️⃣ Bloquear acceso\n0️⃣ Cancelar",
    "wa.tenant.client_context.menu.unregistered_lid_only": "📌 *Gestión del cliente*\n\nEste contacto todavía no existe como cliente.\nEl cliente no ve este menú.\n\nElige una opción:\n1️⃣ Crear cliente\n2️⃣ Bloquear acceso\n0️⃣ Cancelar",
    "wa.tenant.client_context.menu.blocked_with_phone": "📌 *Gestión del cliente*\n\nEste contacto tiene bloqueado el acceso al sistema.\nNo puede pedir códigos, ver perfil ni consultar suscripciones.\n\nNúmero de teléfono: {identity}\n\nElige una opción:\n1️⃣ Desbloquear acceso\n0️⃣ Cancelar",
    "wa.tenant.client_context.menu.blocked_lid_only": "📌 *Gestión del cliente*\n\nEste contacto tiene bloqueado el acceso al sistema.\nNo puede pedir códigos, ver perfil ni consultar suscripciones.\n\nElige una opción:\n1️⃣ Desbloquear acceso\n0️⃣ Cancelar",
    "wa.tenant.client_context.menu.active": "📌 *Gestión del cliente*\n\nEstás administrando este cliente desde tu panel privado.\nEl cliente no ve este menú.\n\nCliente: {client_name}\nNúmero de teléfono: {identity}\nEstado: {status}\n\nElige una opción:\n1️⃣ Ver detalle\n2️⃣ Editar cliente\n3️⃣ Crear suscripción\n4️⃣ Desactivar cliente\n5️⃣ Eliminar cliente\n0️⃣ Cancelar",
    "wa.tenant.client_context.menu.inactive": "📌 *Gestión del cliente*\n\nEstás administrando este cliente desde tu panel privado.\nEl cliente no ve este menú.\n\nCliente: {client_name}\nNúmero de teléfono: {identity}\nEstado: {status}\n\nElige una opción:\n1️⃣ Ver detalle\n2️⃣ Editar cliente\n3️⃣ Reactivar cliente\n4️⃣ Eliminar cliente\n0️⃣ Cancelar",
    "wa.tenant.client_context.closed": "✅ Gestión del cliente cancelada. También se cerró la sesión de consola del tenant.",
    "wa.tenant.client_context.collision": "⚠️ Ya tienes una gestión del cliente abierta. Envía *0* en tu chat privado de Tenant antes de abrir otra.",
    "wa.tenant.client_context.invalid_option": "❌ Opción inválida. Responde con un número del menú o *0* para cancelar.",
    "wa.tenant.client_context.create.phone_prefilled": "Teléfono prefijado: {identity}\n\nEscribe el *nombre completo* del cliente o *0* para cancelar:",
    "wa.tenant.client_context.create.phone_prompt": "Escribe el número de teléfono del cliente para asociarlo a este chat.\n\n0️⃣ Cancelar",
    "wa.tenant.client_context.block_access.success": "✅ Acceso bloqueado para *{identity}*.",
    "wa.tenant.client_context.unblock_access.success": "✅ Acceso desbloqueado para *{identity}*.",
```

- [x] **Step 5: Verify**

```bash
cd backend
uv run pytest tests/test_whatsapp_client_context_shortcut.py::test_client_context_i18n_keys_exist_in_en_and_es -v
```

Expected: pass.

- [x] **Step 6: Commit** (8461cf9)

```


---

### Task 4: Render real contextual menu on `/menu` start

**Files:**
- Modify: `backend/app/api/v1/endpoints/integrations/console.py`
- Modify: `backend/app/api/v1/endpoints/integrations/console_context_shortcut.py`
- Test: `backend/tests/test_whatsapp_client_context_shortcut.py`

- [x] **Step 1: Write failing unregistered menu test**

Add test using existing async client fixtures/patterns from `test_whatsapp_endpoint.py`:

```python
async def test_from_me_external_menu_returns_private_unregistered_context_menu(async_client, tenant, n8n_headers):
    response = await async_client.post(
        "/api/v1/integrations/n8n/console",
        headers=n8n_headers,
        json={
            "phone": tenant.whatsapp_phone,
            "message": "/menu",
            "instance": tenant.evolution_instance_name,
            "from_me": True,
            "admin_phone": tenant.whatsapp_phone,
            "admin_jid": f"{tenant.whatsapp_phone}@s.whatsapp.net",
            "target_jid": "34999999999@s.whatsapp.net",
            "target_phone": "34999999999",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["reply_to"] == f"{tenant.whatsapp_phone}@s.whatsapp.net"
    assert "Gestión del cliente" in data["reply"]
    assert "Crear cliente para este número" in data["reply"]
    assert "Número de teléfono: 34999999999" in data["reply"]
    assert "Bloquear acceso" in data["reply"]
    assert "Contexto de cliente iniciado" not in data["reply"]
```

If fixture names differ, mirror existing endpoint fixtures exactly.

- [x] **Step 2: Run failing test**

```bash
cd backend
uv run pytest tests/test_whatsapp_client_context_shortcut.py::test_from_me_external_menu_returns_private_unregistered_context_menu -v
```

Expected: fail because backend returns generic context-started text.

- [x] **Step 3: Add menu renderer helper**

In `console_context_shortcut.py`, add:

```python
from app.core.i18n import t


def _phone_label(phone: str | None) -> str:
    return (phone or "").lstrip("+")


async def render_initial_context_menu(
    *,
    db: AsyncSession,
    tenant: _TenantModel,
    target_phone: str | None,
    target_lid: str | None,
    target_jid: str | None,
) -> tuple[str, dict[str, str]]:
    locale = getattr(tenant, "locale", None) or "es"
    identity = _phone_label(target_phone)
    client = None
    if target_phone:
        client = await clients_repository.get_client_by_tenant_phone(db, tenant.id, target_phone)
    if client is None and target_lid:
        client = await clients_repository.get_client_by_tenant_lid(db, tenant.id, target_lid)

    if client is not None:
        status_key = "wa.tenant.clients.detail.status_active" if client.is_active else "wa.tenant.clients.detail.status_inactive"
        key = "wa.tenant.client_context.menu.active" if client.is_active else "wa.tenant.client_context.menu.inactive"
        variant = "existing_active" if client.is_active else "existing_inactive"
        return t(locale, key, identity=identity, client_name=client.full_name, status=t(locale, status_key)), {
            "target_state": variant,
            "menu_variant": variant,
            "client_id": str(client.id),
            "identity": identity,
            "locale": locale,
        }

    block = await blocked_clients_repository.find_active(
        db,
        tenant.id,
        phone=target_phone,
        whatsapp_lid=target_lid,
    )
    if block is not None:
        key = (
            "wa.tenant.client_context.menu.blocked_with_phone"
            if target_phone
            else "wa.tenant.client_context.menu.blocked_lid_only"
        )
        return t(locale, key, identity=identity, client_name="", status=""), {
            "target_state": "unregistered_blocked",
            "menu_variant": "blocked",
            "identity": identity,
            "locale": locale,
        }

    key = (
        "wa.tenant.client_context.menu.unregistered_with_phone"
        if target_phone
        else "wa.tenant.client_context.menu.unregistered_lid_only"
    )
    return t(locale, key, identity=identity, client_name="", status=""), {
        "target_state": "unregistered_unblocked",
        "menu_variant": "unregistered",
        "identity": identity,
        "locale": locale,
    }
```

If repository function names differ, use existing exact functions from `clients_repository.py`.

- [x] **Step 4: Call renderer when creating context**

In `_handle_from_me_routing`, replace generic reply with:

```python
    from app.api.v1.endpoints.integrations.console_context_shortcut import render_initial_context_menu

    reply, context_meta = await render_initial_context_menu(
        db=db,
        tenant=tenant,
        target_phone=target_phone_norm or target_phone,
        target_lid=target_lid,
        target_jid=target_jid,
    )

    session = ConversationSession(
        phone=resolved_admin_phone,
        flow="client_shortcut",
        step="menu",
        temp_data={
            "tenant_id": str(tenant.id),
            "target_phone": target_phone_norm or target_phone,
            "target_lid": target_lid,
            "target_jid": target_jid,
            "admin_jid": admin_jid,
            **context_meta,
        },
    )
```

Return:

```python
    return WhatsAppConsoleResponse(reply=reply, reply_to=admin_jid)
```

- [x] **Step 5: Verify**

```bash
cd backend
uv run pytest tests/test_whatsapp_client_context_shortcut.py::test_from_me_external_menu_returns_private_unregistered_context_menu -v
```

Expected: pass.

- [x] **Step 6: Commit** (d8f601f)

```

---

### Task 5: Harden self-chat `/menu` detection

**Files:**
- Modify: `backend/app/api/v1/endpoints/integrations/console.py`
- Test: `backend/tests/test_whatsapp_client_context_shortcut.py`

- [ ] **Step 1: Write failing self-chat test**

```python
async def test_from_me_self_menu_routes_to_tenant_console(async_client, tenant, n8n_headers):
    admin_jid = f"{tenant.whatsapp_phone}@s.whatsapp.net"
    response = await async_client.post(
        "/api/v1/integrations/n8n/console",
        headers=n8n_headers,
        json={
            "phone": tenant.whatsapp_phone,
            "message": "/menu",
            "instance": tenant.evolution_instance_name,
            "from_me": True,
            "admin_phone": tenant.whatsapp_phone,
            "admin_jid": admin_jid,
            "target_jid": admin_jid,
            "target_phone": tenant.whatsapp_phone,
        },
    )

    data = response.json()
    assert "Trackpal" in data["reply"] or "Consola" in data["reply"]
    assert "Gestión del cliente" not in data["reply"]
    assert "reply_to" not in data
```

- [ ] **Step 2: Run failing/passing baseline**

```bash
cd backend
uv run pytest tests/test_whatsapp_client_context_shortcut.py::test_from_me_self_menu_routes_to_tenant_console -v
```

Expected before fix may fail in current bug reproduction.

- [ ] **Step 3: Normalize JID comparison**

In `console.py`, add helper near `_tl`:

```python
def _jid_phone(value: str | None) -> str | None:
    if not value:
        return None
    return normalize_phone(value.split("@")[0])
```

Replace self-target block with:

```python
    admin_jid_phone = _jid_phone(admin_jid)
    target_jid_phone = _jid_phone(target_jid)
    tenant_phone = normalize_phone(tenant.whatsapp_phone) if tenant.whatsapp_phone else None
    resolved_admin_lid = getattr(tenant, "whatsapp_lid", None)

    is_self_target = any(
        candidate and candidate == resolved_admin_phone
        for candidate in (target_phone_norm, target_jid_phone)
    ) or any(
        candidate and tenant_phone and candidate == tenant_phone
        for candidate in (target_phone_norm, target_jid_phone, admin_jid_phone)
    ) or bool(
        admin_jid and target_jid and admin_jid == target_jid
    ) or bool(
        resolved_admin_lid and target_lid and resolved_admin_lid == target_lid
    )
```

- [x] **Step 4: Verify** (test passes without code changes per user decision)

- [x] **Step 5: Commit** (db31a42 — test only)

---

### Task 6: Close context + Tenant session + correct Evolution JID (✅ f8c4cab)

**Files:**
- Modify: `backend/app/api/v1/endpoints/integrations/console_handlers.py`
- Modify: `backend/app/api/v1/endpoints/integrations/console_context_shortcut.py`
- Test: `backend/tests/test_whatsapp_client_context_shortcut.py`

- [ ] **Step 1: Write failing close test**

```python
async def test_context_zero_closes_context_tenant_session_and_admin_jid(async_client, tenant, n8n_headers, redis_manager):
    admin_jid = f"{tenant.whatsapp_phone}@s.whatsapp.net"
    await async_client.post(
        "/api/v1/integrations/n8n/console",
        headers=n8n_headers,
        json={
            "phone": tenant.whatsapp_phone,
            "message": "/menu",
            "instance": tenant.evolution_instance_name,
            "from_me": True,
            "admin_phone": tenant.whatsapp_phone,
            "admin_jid": admin_jid,
            "target_jid": "34999999999@s.whatsapp.net",
            "target_phone": "34999999999",
        },
    )

    response = await async_client.post(
        "/api/v1/integrations/n8n/console",
        headers=n8n_headers,
        json={
            "phone": tenant.whatsapp_phone,
            "message": "0",
            "instance": tenant.evolution_instance_name,
            "sender_lid": None,
        },
    )

    data = response.json()
    assert data["status"] == "closed"
    assert data["reply_to"] == admin_jid
    assert data["close_jid"] == admin_jid
    assert "cerrada" in data["reply"].lower() or "closed" in data["reply"].lower()
```

- [ ] **Step 2: Run failing test**

```bash
cd backend
uv run pytest tests/test_whatsapp_client_context_shortcut.py::test_context_zero_closes_context_tenant_session_and_admin_jid -v
```

Expected: fail because no `close_jid`/full close.

- [ ] **Step 3: Implement close helper**

In `console_handlers.py`, inside `_handle_active_client_context`, ensure `msg_lower == "0"` path does:

```python
    locale = data.get("temp_data", {}).get("locale") or getattr(tenant, "locale", "es") or "es"
    admin_jid = data.get("temp_data", {}).get("admin_jid")

    async def _delete_keys(client):
        pipe = client.pipeline()
        pipe.delete(ctx_key)
        pipe.delete(f"session:admin:{phone}")
        await pipe.execute()

    await manager.execute("close_client_context", _delete_keys)
    return WhatsAppConsoleResponse(
        reply=_i18n_t(locale, "wa.tenant.client_context.closed"),
        status="closed",
        reply_to=admin_jid,
        close_jid=admin_jid,
    )
```

If Redis wrapper does not expose pipeline, execute two deletes in one callback with sequential `await client.delete(...)` calls.

- [ ] **Step 4: Verify**

```bash
cd backend
uv run pytest tests/test_whatsapp_client_context_shortcut.py::test_context_zero_closes_context_tenant_session_and_admin_jid -v
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/v1/endpoints/integrations/console_handlers.py backend/app/api/v1/endpoints/integrations/console_context_shortcut.py backend/tests/test_whatsapp_client_context_shortcut.py
git commit -m "fix: close client context and tenant session together"
```

---

### Task 7: Redis read optimization in active context path (✅ 46dba46)

**Files:**
- Modify: `backend/app/api/v1/endpoints/integrations/console_handlers.py`
- Test: `backend/tests/test_whatsapp_client_context_shortcut.py`

- [ ] **Step 1: Write behavioral guard test**

```python
async def test_active_context_message_does_not_route_to_normal_tenant_session(async_client, tenant, n8n_headers):
    admin_jid = f"{tenant.whatsapp_phone}@s.whatsapp.net"
    await async_client.post(
        "/api/v1/integrations/n8n/console",
        headers=n8n_headers,
        json={
            "phone": tenant.whatsapp_phone,
            "message": "/menu",
            "instance": tenant.evolution_instance_name,
            "from_me": True,
            "admin_phone": tenant.whatsapp_phone,
            "admin_jid": admin_jid,
            "target_jid": "34999999999@s.whatsapp.net",
            "target_phone": "34999999999",
        },
    )

    response = await async_client.post(
        "/api/v1/integrations/n8n/console",
        headers=n8n_headers,
        json={
            "phone": tenant.whatsapp_phone,
            "message": "texto invalido",
            "instance": tenant.evolution_instance_name,
        },
    )

    data = response.json()
    assert data.get("reply_to") == admin_jid
    assert "Opción inválida" in data["reply"] or "Invalid option" in data["reply"]
    assert "Trackpal" not in data["reply"]
```

- [ ] **Step 2: Run test**

```bash
cd backend
uv run pytest tests/test_whatsapp_client_context_shortcut.py::test_active_context_message_does_not_route_to_normal_tenant_session -v
```

Expected: pass after active context consumes invalid input; fail if normal Tenant menu consumes it.

- [ ] **Step 3: Keep active context path single-source**

In `_handle_active_client_context`, use already-loaded `data` and `temp_data` for `locale`, `target_state`, `menu_variant`, `admin_jid`, `identity`. Do not call `session_service.get_session(f"admin:{phone}")` before deciding context response. Invalid menu input returns:

```python
    return WhatsAppConsoleResponse(
        reply=_i18n_t(locale, "wa.tenant.client_context.invalid_option"),
        reply_to=admin_jid,
    )
```

Only re-query DB when selected action mutates or needs fresh record detail.

- [ ] **Step 4: Verify relevant context tests**

```bash
cd backend
uv run pytest tests/test_whatsapp_client_context_shortcut.py -v
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/v1/endpoints/integrations/console_handlers.py backend/tests/test_whatsapp_client_context_shortcut.py
git commit -m "perf: reduce Redis reads in client context routing"
```

---

### Task 8: n8n preserves `close_jid` and closes correct chat (✅ efe7041)

**Files:**
- Modify: `n8n/Trackpal WhatsApp Bot.json`

- [ ] **Step 1: Update Merge node JavaScript**

In node `Merge & lookup data`, change JS to include:

```javascript
const closeJid = responseData.close_jid || null;

return [{ json: { ...input, reply, status, lookup_job_id: lookupJobId, tenant_id: tenantId, reply_to: replyTo, no_reply: noReply, close_jid: closeJid } }];
```

- [ ] **Step 2: Update Close session node body**

In node `Close session`, change JSON body expression to:

```javascript
={{ JSON.stringify({ remoteJid: String($json.close_jid || $json.reply_to || $json.remoteJid), status: "closed" }) }}
```

- [ ] **Step 3: Validate JSON syntax**

```bash
python -m json.tool "n8n/Trackpal WhatsApp Bot.json" > /tmp/trackpal-workflow.json
```

Expected: exit 0.

- [ ] **Step 4: Inspect changed nodes**

```bash
python - <<'PY'
import json
p='n8n/Trackpal WhatsApp Bot.json'
data=json.load(open(p, encoding='utf-8'))
for n in data['nodes']:
    if n['name'] in ('Merge & lookup data', 'Close session'):
        print(n['name'])
        print(n['parameters'])
PY
```

Expected: output contains `close_jid` in Merge and `close_jid || $json.reply_to || $json.remoteJid` in Close session.

- [ ] **Step 5: Commit**

```bash
git add "n8n/Trackpal WhatsApp Bot.json"
git commit -m "fix: close contextual WhatsApp session by explicit JID"
```

---

### Task 9: Sync PRD and architecture docs (✅)

**Files:**
- Modify: `docs/superpowers/prds/client-context-shortcut.md`
- Modify: `docs/architecture/whatsapp-console-flow.md`
- Modify: `docs/architecture/n8n-workflow.md`

- [ ] **Step 1: Update PRD routing/closing/i18n sections**

Edit PRD to include:

```markdown
- Initial contextual response must be the actionable contextual menu, not a generic “context started” confirmation.
- `0` inside a contextual session performs a Tenant-side total close: clears `wa:client_ctx:{admin_phone}`, clears `session:admin:{admin_phone}`, returns `status="closed"`, and sets `close_jid=<admin_jid>`.
- All contextual shortcut messages are backend-rendered through `wa.tenant.client_context.*` i18n keys.
- `client_messaging_blocks` is renamed to `blocked_clients`; this table blocks system access for unregistered WhatsApp identities, not only messages.
- Registered clients get contextual CRUD with no phone prompt and no client selection prompt; active clients include `Desactivar cliente`.
- Implementation should reduce duplicate Redis reads by reusing context payload metadata and avoiding normal Tenant session reads when context consumes the message.
```

- [ ] **Step 2: Update architecture docs**

In WhatsApp flow response contract add:

```markdown
| `close_jid` | string | no | Exact JID n8n must close when `status="closed"`. Context shortcut close uses the Tenant admin private JID. |
```

In n8n doc update Close Session:

```markdown
Close Session uses `close_jid || reply_to || remoteJid` to avoid closing the target/client chat when a private contextual admin flow closes.
```

- [ ] **Step 3: Verify docs changed**

```bash
git diff -- docs/superpowers/prds/client-context-shortcut.md docs/architecture/whatsapp-console-flow.md docs/architecture/n8n-workflow.md
```

Expected: diff includes actionable initial menu, `blocked_clients`, registered-client contextual CRUD, total close, i18n, Redis optimization, `close_jid`.

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/prds/client-context-shortcut.md docs/architecture/whatsapp-console-flow.md docs/architecture/n8n-workflow.md
git commit -m "docs: clarify client context shortcut repair contract"
```

---

### Task 10: Full verification (✅ 368 passed)

**Files:**
- All modified files

- [x] **Step 1: Run focused backend tests (72 passed)**

```bash
cd backend
uv run pytest tests/test_whatsapp_client_context_shortcut.py tests/test_whatsapp_endpoint.py -v
```

Expected: all pass.

- [x] **Step 2: Run broader WhatsApp tests (368 passed)**

- [x] **Step 3: Validate workflow JSON (valid)**

- [x] **Step 4: Inspect final diff (19 files, 796 insertions)**

- [x] **Step 5: Final commit (0e5efb3)**

```bash
git status --short
```

If files remain modified:

```bash
git add <modified-files>
git commit -m "test: verify client context shortcut repair"
```

---

## Self-Review

Spec coverage:
- Self-chat routing: Task 5.
- External `/menu` immediate private menu: Task 4.
- Intuitive copy: Task 3 + Task 4.
- `blocked_clients` rename and access-block semantics: Task 2.
- Registered client CRUD context and deactivate option: Task 3 + Task 4 + Task 9 docs sync.
- Total close + correct Evolution JID: Task 1 + Task 6 + Task 8.
- i18n alignment: Task 3 + Task 9.
- Redis optimization general: Task 7.
- n8n pure transport: Task 8 + Task 9.
- Docs/PRD sync: Task 9.

No placeholders remain. Function/property names are consistent: `close_jid`, `reply_to`, `no_reply`, `status`.
