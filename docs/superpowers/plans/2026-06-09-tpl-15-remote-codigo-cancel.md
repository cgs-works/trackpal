# TPL-15 Remote `codigo` Cancel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**GitHub Issue:** [#59](https://github.com/wilfredocamacho/trackpal/issues/59)
**GitHub PR:** [#60](https://github.com/wilfredocamacho/trackpal/pull/60)
**Linear:** [TPL-15](https://linear.app/trackpal/issue/TPL-15/allow-tenant-admin-to-cancel-a-target-users-active-whatsapp-flow-from) → Done

**Goal:** Permitir que un tenant admin cancele silenciosamente el flujo activo `codigo` de un usuario objetivo enviando exactamente `0` en el chat objetivo, cerrando además la sesión chatbot de Evolution para ese chat.

**Architecture:** La implementación toca tres capas ya existentes: registro de webhook Evolution, transporte n8n y routing backend `from_me`. El backend agregará una rama temprana para `from_me=true` + target no-self + `message.strip() == "0"`, reutilizando el modelo actual de sesiones `session:unreg:{tenant_prefix}:{identity}` y cancelando el `MailLookupJob` asociado cuando exista; n8n dejará de bloquear únicamente ese caso exacto y seguirá cerrando sesiones vía `status="closed"` + `close_jid`.

**Tech Stack:** FastAPI, SQLAlchemy async, Redis session store, pytest, n8n Code node JS, Evolution Go webhook integration.

---

## Confirmed assumptions

- **Fuente de verdad:** seguir el spec `docs/superpowers/specs/2026-06-09-tpl-15-remote-codigo-cancel-design.md`.
- **n8n sí cambia:** el guard actual `from_me external non-menu` debe dejar pasar únicamente el `0` exacto remoto al backend.
- **Prioridad con context activo:** si existe `wa:client_ctx:{admin_phone}`, el `0` remoto debe **cancelar el `codigo` del objetivo** y **no** cerrar esa context session.
- **No aliases:** sólo `message.strip() == "0"` activa la cancelación remota.
- **Sin mensaje saliente:** la respuesta remota exitosa debe ser `reply=""`, `no_reply=true`, `status="closed"`, `close_jid=<target>`.

## File map

- Modify: `backend/app/services/evolution_client/client.py:70-105` — agregar `listeningFromMe` al payload de `register_webhook()`.
- Modify: `backend/tests/test_evolution_client.py:87-135` — fijar el contrato del payload del webhook.
- Modify: `backend/app/api/v1/endpoints/integrations/console.py:408-615` — insertar la rama temprana de cancelación remota en `_handle_from_me_routing()` antes del manejo de context collision.
- Modify: `backend/app/api/v1/endpoints/integrations/console_handlers.py:116-176` y nueva helper cerca de los handlers de `codigo` — agregar `_cancel_target_codigo_flow(...)`.
- Modify: `backend/tests/test_whatsapp_endpoint.py` — añadir cobertura para phone path, LID path, active job, no aliases, no Redis session, admin session intacta y context activa intacta.
- Modify: `n8n/Trackpal WhatsApp Bot.json` — cambiar el nodo `Guard fromMe external non-menu` para exceptuar sólo el `0` remoto.
- Modify: `docs/architecture/whatsapp-console-flow.md` — documentar la nueva excepción del guard y la rama remota `0`.
- Modify: `docs/architecture/evolution-integration.md` — documentar `listeningFromMe=true` y el supuesto operativo del flujo remoto.

---

### Task 1: Webhook registration contract - [x]

**Skills:**
- `superpowers:test-driven-development`
- `python-pro`
- `fastapi-expert`
- `superpowers:verification-before-completion`

**Files:**
- Modify: `backend/tests/test_evolution_client.py:87-135`
- Modify: `backend/app/services/evolution_client/client.py:70-105`
- Test: `backend/tests/test_evolution_client.py`

- [x] **Step 1: Write the failing test**

Add/adjust the payload assertions so they require `listeningFromMe=True` while keeping the regex unchanged.

```python
class TestRegisterWebhook:
    async def test_register_webhook_create_payload(self) -> None:
        client = EvolutionClient(base_url="https://evo.test", api_key="global-key")
        create_response = MagicMock(status_code=200)

        with patch("httpx.AsyncClient") as mock_httpx:
            mock_ctx = AsyncMock()
            mock_httpx.return_value.__aenter__.return_value = mock_ctx
            mock_ctx.post.return_value = create_response

            await client.register_webhook("inst-id")

        _, kwargs = mock_ctx.post.call_args
        assert kwargs["json"] == {
            "enabled": True,
            "webhookUrl": "https://rs-n8n.wilfredocamacho.dev/webhook/trackpalmastertenantclient",
            "triggerType": "keyword",
            "triggerOperator": "regex",
            "triggerValue": r"(?i)^\s*(?:/menu|codigo|código|code)\b",
            "isTrusted": True,
            "listeningFromMe": True,
        }
        assert "0" not in kwargs["json"]["triggerValue"]
```

Also assert the update/upsert path reuses the same payload:

```python
_, update_kwargs = mock_ctx.put.call_args
assert update_kwargs["json"]["listeningFromMe"] is True
assert update_kwargs["json"]["triggerValue"] == r"(?i)^\s*(?:/menu|codigo|código|code)\b"
```

- [x] **Step 2: Run test to verify it fails**

Run:

```bash
cd backend && uv run pytest tests/test_evolution_client.py -q
```

Expected: FAIL because the current payload does not contain `"listeningFromMe": True`.

- [x] **Step 3: Write minimal implementation**

Update `register_webhook()` payload in `backend/app/services/evolution_client/client.py`.

```python
payload = {
    "enabled": True,
    "webhookUrl": "https://rs-n8n.wilfredocamacho.dev/webhook/trackpalmastertenantclient",
    "triggerType": "keyword",
    "triggerOperator": "regex",
    "triggerValue": r"(?i)^\s*(?:/menu|codigo|código|code)\b",
    "isTrusted": True,
    "listeningFromMe": True,
}
```

Do not change the regex, operator, URL, or upsert flow.

- [x] **Step 4: Run test to verify it passes**

Run:

```bash
cd backend && uv run pytest tests/test_evolution_client.py -q
```

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add backend/app/services/evolution_client/client.py backend/tests/test_evolution_client.py
git commit -m "feat: enable from-me webhook dispatch"
```

---

### Task 2: Backend remote cancel — phone path

**Skills:**
- `superpowers:test-driven-development`
- `python-pro`
- `fastapi-expert`
- `superpowers:verification-before-completion`

**Files:**
- Modify: `backend/tests/test_whatsapp_endpoint.py` near the current `from_me` routing block (`~1940+`)
- Modify: `backend/app/api/v1/endpoints/integrations/console.py:408-615`
- Modify: `backend/app/api/v1/endpoints/integrations/console_handlers.py` (new helper near `_unauth_session_key` and codigo helpers)
- Test: `backend/tests/test_whatsapp_endpoint.py`

- [x] **Step 1: Write the failing tests**

Add these endpoint tests first. If they are not already imported in `backend/tests/test_whatsapp_endpoint.py`, add `import json` near the top of the file.

```python
async def test_from_me_remote_zero_cancels_target_codigo_by_phone(
    client, db_session, active_tenant_user
):
    tenant = await _setup_tenant_for_codigo(db_session, active_tenant_user)
    fake_mgr = _FakeManager(used_backup=False)
    session_key = await _seed_unauth_codigo_awaiting_result(fake_mgr, tenant.id)

    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={
                "phone": tenant.whatsapp_phone,
                "message": "0",
                "instance": TEST_INSTANCE,
                "from_me": True,
                "admin_phone": tenant.whatsapp_phone,
                "admin_jid": "12015550002@s.whatsapp.net",
                "target_jid": "12015559999@s.whatsapp.net",
                "target_phone": "12015559999",
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )

    assert response.status_code == 200
    assert response.json() == {
        "reply": "",
        "no_reply": True,
        "status": "closed",
        "close_jid": "12015559999@s.whatsapp.net",
    }
    assert await fake_mgr._redis.get(session_key) is None
    assert await fake_mgr._redis.get("wa:client_ctx:12015550002") is None
```

```python
async def test_from_me_remote_alias_does_not_cancel_target_codigo(
    client, db_session, active_tenant_user
):
    tenant = await _setup_tenant_for_codigo(db_session, active_tenant_user)
    fake_mgr = _FakeManager(used_backup=False)
    session_key = await _seed_unauth_codigo_awaiting_result(fake_mgr, tenant.id)

    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={
                "phone": tenant.whatsapp_phone,
                "message": "cancelar",
                "instance": TEST_INSTANCE,
                "from_me": True,
                "admin_phone": tenant.whatsapp_phone,
                "admin_jid": "12015550002@s.whatsapp.net",
                "target_jid": "12015559999@s.whatsapp.net",
                "target_phone": "12015559999",
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )

    assert response.status_code == 200
    body = response.json()
    assert body.get("no_reply") is True
    assert body.get("reply") == ""
    assert body.get("status") != "closed"
    assert await fake_mgr._redis.get(session_key) is not None
```

```python
async def test_from_me_remote_zero_does_not_clear_admin_session(
    client, db_session, active_tenant_user
):
    tenant = await _setup_tenant_for_codigo(db_session, active_tenant_user)
    fake_mgr = _FakeManager(used_backup=False)
    await _seed_unauth_codigo_awaiting_result(fake_mgr, tenant.id)
    await fake_mgr._redis.set(
        "session:admin:12015550002",
        json.dumps({"phone": "12015550002", "flow": "", "step": "", "temp_data": {}, "selection_map": {}}),
        ex=300,
    )

    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={
                "phone": tenant.whatsapp_phone,
                "message": "0",
                "instance": TEST_INSTANCE,
                "from_me": True,
                "admin_phone": tenant.whatsapp_phone,
                "admin_jid": "12015550002@s.whatsapp.net",
                "target_jid": "12015559999@s.whatsapp.net",
                "target_phone": "12015559999",
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )

    assert response.status_code == 200
    assert await fake_mgr._redis.get("session:admin:12015550002") is not None
```

- [x] **Step 2: Run tests to verify they fail**

Run:

```bash
cd backend && uv run pytest tests/test_whatsapp_endpoint.py -q -k "remote_zero or remote_alias or does_not_clear_admin_session"
```

Expected: FAIL because `_handle_from_me_routing()` still treats non-menu non-self traffic as silent ignore and has no remote-cancel branch.

- [x] **Step 3: Write minimal implementation**

Add a helper in `backend/app/api/v1/endpoints/integrations/console_handlers.py`.

```python
async def _cancel_target_codigo_flow(
    *,
    manager: RedisConnectionManager,
    db: AsyncSession,
    tenant_id: UUID,
    target_phone: str | None,
    target_lid: str | None,
) -> bool:
    session_service = WhatsAppSessionService(
        connection_manager=manager,
        ttl_seconds=settings.whatsapp_session_ttl_minutes * 60,
    )

    candidate_keys = list(
        dict.fromkeys(
            key
            for key in (
                _unauth_session_key(target_phone, None, str(tenant_id)) if target_phone else None,
                _unauth_session_key("", target_lid, str(tenant_id)) if target_lid else None,
            )
            if key
        )
    )

    found = False
    for logical_key in candidate_keys:
        session = await session_service.get_session(logical_key)
        if session is None or session.flow != "codigo":
            continue

        found = True
        lookup_job_id = (session.temp_data or {}).get("lookup_job_id")
        if lookup_job_id:
            try:
                cancelled = await mailbox_lookup_repository.cancel_active_job_if_present(
                    db,
                    UUID(lookup_job_id),
                    tenant_id=tenant_id,
                )
                if cancelled:
                    await db.commit()
            except ValueError:
                logger.warning(
                    "Ignoring invalid lookup job id during remote codigo cancel: %s",
                    lookup_job_id,
                )
            except Exception:
                logger.exception(
                    "Failed to cancel lookup job %s during remote codigo cancel",
                    lookup_job_id,
                )
                try:
                    await db.rollback()
                except Exception:
                    logger.exception(
                        "Failed to rollback after remote codigo cancel cancellation error"
                    )

        await session_service.clear_session(logical_key)

    return found
```

Then wire the new branch in `backend/app/api/v1/endpoints/integrations/console.py` **immediately after the `is_self_target` branch and before `ctx_key = ...`**.

```python
    remote_cancel = message.strip() == "0"
    if remote_cancel:
        await _cancel_target_codigo_flow(
            manager=manager,
            db=db,
            tenant_id=tenant.id,
            target_phone=target_phone_norm,
            target_lid=target_lid,
        )
        target_close_jid = (
            _phone_close_jid(target_phone_norm)
            or _canonical_jid(target_jid)
            or target_jid
        )
        return WhatsAppConsoleResponse(
            reply="",
            no_reply=True,
            status="closed",
            close_jid=target_close_jid,
        )
```

Also update the import list in `console.py` so `_cancel_target_codigo_flow` is imported from `console_handlers`.

- [x] **Step 4: Run tests to verify they pass**

Run:

```bash
cd backend && uv run pytest tests/test_whatsapp_endpoint.py -q -k "remote_zero or remote_alias or does_not_clear_admin_session"
```

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add backend/app/api/v1/endpoints/integrations/console.py backend/app/api/v1/endpoints/integrations/console_handlers.py backend/tests/test_whatsapp_endpoint.py
git commit -m "feat: add remote codigo cancel by phone"
```

---

### Task 3: Backend remote cancel — edge cases and safety

**Skills:**
- `superpowers:test-driven-development`
- `python-pro`
- `fastapi-expert`
- `superpowers:verification-before-completion`

**Files:**
- Modify: `backend/tests/test_whatsapp_endpoint.py`
- Modify: `backend/app/api/v1/endpoints/integrations/console.py`
- Modify: `backend/app/api/v1/endpoints/integrations/console_handlers.py`
- Test: `backend/tests/test_whatsapp_endpoint.py`

- [x] **Step 1: Write the failing tests**

Add the LID path, job-cancel path, no-session path, and active-context-priority path. If any import is missing in `backend/tests/test_whatsapp_endpoint.py`, add these near the top of the file before writing the tests:

```python
import json
from sqlalchemy import select
from app.models import TenantMailbox
from app.repositories import mailbox_lookup_repository
```

```python
async def test_from_me_remote_zero_cancels_target_codigo_by_lid(
    client, db_session, active_tenant_user
):
    tenant = await _setup_tenant_for_codigo(db_session, active_tenant_user)
    fake_mgr = _FakeManager(used_backup=False)
    tenant_prefix = str(tenant.id)[:8]
    lid_key = f"session:unreg:{tenant_prefix}:998877665544332211@lid"
    await fake_mgr._redis.set(
        lid_key,
        json.dumps(
            {
                "phone": f"unreg:{tenant_prefix}:998877665544332211@lid",
                "flow": "codigo",
                "step": "awaiting_result",
                "selected_tenant_id": None,
                "temp_data": {"service_key": "netflix", "target_email": "user@example.com"},
                "selection_map": {},
            }
        ),
        ex=300,
    )

    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={
                "phone": tenant.whatsapp_phone,
                "message": "0",
                "instance": TEST_INSTANCE,
                "from_me": True,
                "admin_phone": tenant.whatsapp_phone,
                "admin_jid": "12015550002@s.whatsapp.net",
                "target_jid": "998877665544332211@lid",
                "target_lid": "998877665544332211@lid",
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )

    assert response.status_code == 200
    assert response.json() == {
        "reply": "",
        "no_reply": True,
        "status": "closed",
        "close_jid": "998877665544332211@lid",
    }
    assert await fake_mgr._redis.get(lid_key) is None
```

```python
async def test_from_me_remote_zero_cancels_active_lookup_job(
    client, db_session, active_tenant_user
):
    tenant = await _setup_tenant_for_codigo(db_session, active_tenant_user)
    mailbox = (
        await db_session.execute(
            select(TenantMailbox).where(TenantMailbox.tenant_id == tenant.id)
        )
    ).scalar_one()
    job = await mailbox_lookup_repository.create_job(
        db_session,
        tenant.id,
        mailbox.id,
        "netflix",
        target_email="user@example.com",
    )
    await db_session.commit()

    fake_mgr = _FakeManager(used_backup=False)
    session_key = await _seed_unauth_codigo_awaiting_result(
        fake_mgr,
        tenant.id,
        lookup_job_id=str(job.id),
    )

    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={
                "phone": tenant.whatsapp_phone,
                "message": "0",
                "instance": TEST_INSTANCE,
                "from_me": True,
                "admin_phone": tenant.whatsapp_phone,
                "admin_jid": "12015550002@s.whatsapp.net",
                "target_jid": "12015559999@s.whatsapp.net",
                "target_phone": "12015559999",
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )

    assert response.status_code == 200
    await db_session.refresh(job)
    assert job.status == "failed"
    assert job.error_code == "user_cancelled"
    assert await fake_mgr._redis.get(session_key) is None
```

```python
async def test_from_me_remote_zero_without_target_session_still_closes(
    client, db_session, active_tenant_user
):
    tenant = await _setup_tenant_for_codigo(db_session, active_tenant_user)
    fake_mgr = _FakeManager(used_backup=False)

    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={
                "phone": tenant.whatsapp_phone,
                "message": "0",
                "instance": TEST_INSTANCE,
                "from_me": True,
                "admin_phone": tenant.whatsapp_phone,
                "admin_jid": "12015550002@s.whatsapp.net",
                "target_jid": "12015559999@s.whatsapp.net",
                "target_phone": "12015559999",
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )

    assert response.status_code == 200
    assert response.json() == {
        "reply": "",
        "no_reply": True,
        "status": "closed",
        "close_jid": "12015559999@s.whatsapp.net",
    }
```

```python
async def test_from_me_remote_zero_keeps_active_context_session(
    client, db_session, active_tenant_user
):
    tenant = await _setup_tenant_with_instance(db_session, active_tenant_user)
    fake_mgr = _FakeManager(used_backup=False)
    await _setup_context(fake_mgr, "12015550002")
    await _seed_unauth_codigo_awaiting_result(fake_mgr, tenant.id)

    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={
                "phone": tenant.whatsapp_phone,
                "message": "0",
                "instance": TEST_INSTANCE,
                "from_me": True,
                "admin_phone": tenant.whatsapp_phone,
                "admin_jid": "12015550002@s.whatsapp.net",
                "target_jid": "12015559999@s.whatsapp.net",
                "target_phone": "12015559999",
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )

    assert response.status_code == 200
    assert await fake_mgr._redis.get("wa:client_ctx:12015550002") is not None
```

- [x] **Step 2: Run tests to verify they fail**

Run:

```bash
cd backend && uv run pytest tests/test_whatsapp_endpoint.py -q -k "cancels_target_codigo_by_lid or cancels_active_lookup_job or without_target_session_still_closes or keeps_active_context_session"
```

Expected: FAIL until the helper and route are hardened for all edge cases.

- [x] **Step 3: Finish implementation**

Refine the helper and route with these exact safeguards:

```python
# console.py
remote_cancel = message.strip() == "0"
if remote_cancel:
    await _cancel_target_codigo_flow(
        manager=manager,
        db=db,
        tenant_id=tenant.id,
        target_phone=target_phone_norm,
        target_lid=target_lid,
    )
    target_close_jid = (
        _phone_close_jid(target_phone_norm)
        or _canonical_jid(target_jid)
        or target_jid
    )
    return WhatsAppConsoleResponse(
        reply="",
        no_reply=True,
        status="closed",
        close_jid=target_close_jid,
    )
```

```python
# console_handlers.py
for logical_key in candidate_keys:
    session = await session_service.get_session(logical_key)
    if session is None or session.flow != "codigo":
        continue

    found = True
    lookup_job_id = (session.temp_data or {}).get("lookup_job_id")
    if lookup_job_id:
        try:
            cancelled = await mailbox_lookup_repository.cancel_active_job_if_present(
                db,
                UUID(lookup_job_id),
                tenant_id=tenant_id,
            )
            if cancelled:
                await db.commit()
        except ValueError:
            logger.warning(
                "Ignoring invalid lookup job id during remote codigo cancel: %s",
                lookup_job_id,
            )
        except Exception:
            logger.exception(
                "Failed to cancel lookup job %s during remote codigo cancel",
                lookup_job_id,
            )
            try:
                await db.rollback()
            except Exception:
                logger.exception(
                    "Failed to rollback after remote codigo cancel cancellation error"
                )

    await session_service.clear_session(logical_key)
```

Do **not** touch `wa:client_ctx:{admin_phone}` or `session:admin:{admin_phone}` in this path.

- [x] **Step 4: Run tests to verify they pass**

Run:

```bash
cd backend && uv run pytest tests/test_whatsapp_endpoint.py -q -k "remote_zero"
```

Then run the full endpoint file:

```bash
cd backend && uv run pytest tests/test_whatsapp_endpoint.py -q
```

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add backend/app/api/v1/endpoints/integrations/console.py backend/app/api/v1/endpoints/integrations/console_handlers.py backend/tests/test_whatsapp_endpoint.py
git commit -m "feat: handle remote codigo cancel edge cases"
```

---

### Task 4: n8n transport guard exception for exact remote `0`

**Skills:**
- `superpowers:test-driven-development`
- `n8n-code-javascript`
- `n8n-expression-syntax`
- `superpowers:verification-before-completion`

**Files:**
- Modify: `n8n/Trackpal WhatsApp Bot.json`
- Test/Verify: `n8n/Trackpal WhatsApp Bot.json`

- [x] **Step 1: Write the failing guard verification**

Before editing the workflow, prove the current node still blocks all external non-menu `from_me` traffic.

Run:

```bash
python - <<'PY'
import json, pathlib, sys
path = pathlib.Path("n8n/Trackpal WhatsApp Bot.json")
data = json.loads(path.read_text(encoding="utf-8"))
node = next(n for n in data["nodes"] if n["name"] == "Guard fromMe external non-menu")
code = node["parameters"]["jsCode"]
required = [
    "const isRemoteCancel =",
    "message === '0'",
    "!isRemoteCancel",
]
missing = [item for item in required if item not in code]
if missing:
    print("MISSING:", missing)
    sys.exit(1)
print("OK")
PY
```

Expected: FAIL with `MISSING` because the current guard has no remote-cancel exception.

- [x] **Step 2: Implement the minimal workflow change**

Edit only the code of node `Guard fromMe external non-menu`.

```javascript
const input = $json;

const canonicalJid = (value) => {
  const raw = String(value || '').trim();
  if (!raw) return '';
  if (!raw.includes('@')) return raw;
  const [local, domain] = raw.split('@', 2);
  return `${local.split(':', 1)[0]}@${domain}`;
};

const normalizePhone = (value) => String(value || '').replace(/\D/g, '');

const message = String(input.message || '').trim().toLowerCase();
const fromMe = input.fromMe === true;
const targetJid = canonicalJid(input.targetJid);
const adminJid = canonicalJid(input.adminJid);
const remoteJid = canonicalJid(input.remoteJid);
const targetPhone = normalizePhone(input.targetPhone);
const inputPhone = normalizePhone(input.phone);
const adminPhone = normalizePhone(adminJid);
const remotePhone = normalizePhone(remoteJid);
const targetPhoneJid = targetPhone ? `${targetPhone}@s.whatsapp.net` : null;

const isMenuCommand = message === '/menu' || message === 'menu';
const isRemoteCancel = message === '0';
const isSelfTarget = Boolean(
  (targetJid && ((adminJid && targetJid === adminJid) || (remoteJid && targetJid === remoteJid && adminJid === remoteJid))) ||
  (targetPhone && (targetPhone === inputPhone || targetPhone === adminPhone || targetPhone === remotePhone))
);

const shouldSkipBackend = Boolean(
  fromMe &&
  targetJid &&
  !isSelfTarget &&
  !isMenuCommand &&
  !isRemoteCancel
);

if (shouldSkipBackend) {
  const closeJid = targetPhoneJid || targetJid;
  return [{
    json: {
      ...input,
      reply: '',
      no_reply: true,
      status: 'closed',
      close_jid: closeJid,
      close_jids: [closeJid],
      skip_console_call: true,
      guard_reason: 'from_me_external_non_menu',
    },
  }];
}

return [{ json: { ...input, skip_console_call: false } }];
```

Do not change any other node, IDs, connections, or close-session logic.

- [x] **Step 3: Re-run the verification and JSON parse check**

Run:

```bash
python - <<'PY'
import json, pathlib
path = pathlib.Path("n8n/Trackpal WhatsApp Bot.json")
data = json.loads(path.read_text(encoding="utf-8"))
node = next(n for n in data["nodes"] if n["name"] == "Guard fromMe external non-menu")
code = node["parameters"]["jsCode"]
assert "const isRemoteCancel =" in code
assert "message === '0'" in code
assert "!isRemoteCancel" in code
print("OK")
PY
```

Expected: `OK`.

- [x] **Step 4: Commit**

```bash
git add "n8n/Trackpal WhatsApp Bot.json"
git commit -m "feat: allow remote zero through n8n guard"
```

---

### Task 5: Docs and full verification

**Skills:**
- `docs`
- `superpowers:verification-before-completion`
- `requesting-code-review`

**Files:**
- Modify: `docs/architecture/whatsapp-console-flow.md`
- Modify: `docs/architecture/evolution-integration.md`
- Verify: backend tests + workflow JSON parse + manual smoke checklist

- [x] **Step 1: Update the architecture docs**

In `docs/architecture/whatsapp-console-flow.md`, update the `From-me Contextual Routing` section so it says external `from_me=true` non-menu traffic is still pre-guarded by n8n **except** the exact remote `0`, which now reaches `_handle_from_me_routing()` to cancel target `codigo` silently.

Use wording along these lines:

```md
Before `_handle_from_me_routing()` runs, the n8n workflow pre-guards external `from_me=true` non-menu traffic. The only exception is the exact message `0` sent to a non-self target chat: that payload is allowed through so TrackPal can cancel the target unauthenticated `codigo` flow and return `no_reply=true` + `status="closed"` + `close_jid=<target>`.
```

In `docs/architecture/evolution-integration.md`, update webhook registration + dispatch notes.

```md
`register_webhook(instance_id)` now reconciles `listeningFromMe=true` in the webhook payload while keeping the trigger regex unchanged: `(?i)^\s*(?:/menu|codigo|código|code)\b`.
```

```md
Remote tenant-side `0` cancellation for unauthenticated `codigo` relies on an already-open chatbot session for the target chat plus `listeningFromMe=true`. TrackPal does not add `0` to the trigger; when no target chatbot session exists, the feature remains unavailable.
```

- [x] **Step 2: Run full automated verification**

Run:

```bash
cd backend && uv run pytest tests/test_evolution_client.py tests/test_whatsapp_endpoint.py -q
```

Then run a focused lint pass:

```bash
cd backend && uv run ruff check app/services/evolution_client/client.py app/api/v1/endpoints/integrations/console.py app/api/v1/endpoints/integrations/console_handlers.py tests/test_evolution_client.py tests/test_whatsapp_endpoint.py
```

Then verify the workflow JSON still parses:

```bash
python - <<'PY'
import json, pathlib
json.loads(pathlib.Path("n8n/Trackpal WhatsApp Bot.json").read_text(encoding="utf-8"))
print("workflow json ok")
PY
```

Expected: all commands PASS.

- [x] **Step 3: Run the manual smoke checklist**

Execute these manual checks against a real Evolution+n8n environment after deploying the workflow and backend changes:

```text
1. User inicia `codigo` en un tenant con servicio activo.
2. Mientras la sesión chatbot del target sigue abierta, el admin envía `0` exacto en el chat objetivo.
3. Verificar: no sale mensaje al target, no sale mensaje al admin, backend responde `no_reply=true`, n8n llama `change-status`, Redis borra `session:unreg:{tenant_prefix}:{target}`, y el chat target se cierra.
4. Repetir con target identificado sólo por `target_lid`; verificar que `close_jid` haga fallback a `target_jid` y que la sesión LID se borre.
5. Repetir sin sesión Redis activa; verificar que igual se cierre Evolution si el webhook llegó.
6. Repetir con `wa:client_ctx:{admin_phone}` activa; verificar que la ctx siga existiendo después del `0` remoto.
7. Repetir con mensaje `cancelar`; verificar que NO se borre la sesión `codigo` remota.
8. Repetir cuando la sesión chatbot target ya expiró; verificar que la limitación siga siendo real: TrackPal no recibe el evento.
```

Expected: only the exact supported scenario works; the expired-session limitation remains documented.

- [x] **Step 4: Commit**

```bash
git add docs/architecture/whatsapp-console-flow.md docs/architecture/evolution-integration.md
git commit -m "docs: document remote codigo cancel flow"
```
