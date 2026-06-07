# TPL-10 n8n Close Session Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Make successful lookup results close the Evolution Go session after send, keep recoverable results open with explicit `1 / 2 / 0` options, and make local n8n-timeout retry semantics coherent for both tenant and unauth code flows.

**Architecture:** Keep the change surgical. The workflow fix lives in `n8n/Trackpal WhatsApp Bot.json` by adding an explicit `close_after_send` flag in `Build result message` and teaching `Check close session` to read that flag from upstream result data instead of relying on the HTTP node output. Backend changes are limited to the two awaiting-result handlers so `1`/`2` remain coherent after n8n times out locally, while existing `0` cancel-close behavior is preserved.

**Tech Stack:** n8n workflow JSON, JavaScript Code nodes, Python 3.11+ / FastAPI, pytest, httpx AsyncClient, unittest.mock, project docs in `docs/architecture/`.

---

## File map

- `n8n/Trackpal WhatsApp Bot.json`
  - Source of truth for `Build result message`, `Send result`, and `Check close session`.
- `backend/tests/test_n8n_whatsapp_workflow.py` **(new)**
  - Regression tests that parse the workflow export and lock the JSON/JS contract.
- `backend/app/services/whatsapp_tenant_console_service/codigo_flow.py:289-408`
  - Tenant self-target `awaiting_result` behavior.
- `backend/tests/test_tenant_console_service.py`
  - Unit-level regression tests for tenant awaiting-result semantics.
- `backend/app/api/v1/endpoints/integrations/console_handlers.py:746-946`
  - Unauthenticated/client-sent `awaiting_result` behavior.
- `backend/tests/test_whatsapp_endpoint.py`
  - Endpoint-adjacent regression tests for unauth lookup flow behavior.
- `docs/architecture/n8n-workflow.md:118-166`
  - Document the new `close_after_send` contract and revised close guard.
- `docs/architecture/whatsapp-console-flow.md:188-200, 321-344`
  - Document retry semantics after local n8n timeout for unauth + tenant code flows.

---

### Task 1: Lock the n8n workflow contract with a dedicated regression test file

**Read before starting:**
- `superpowers:subagent-driven-development` **or** `superpowers:executing-plans`
- `superpowers:test-driven-development`
- `superpowers:verification-before-completion`
- `docs/superpowers/specs/2026-06-07-tpl-10-n8n-close-session-design.md`

**Files:**
- Create: `backend/tests/test_n8n_whatsapp_workflow.py`

- [x] **Step 1: Write the failing workflow regression tests**

Create this file:

```python
import json
from pathlib import Path

WORKFLOW_PATH = (
    Path(__file__).resolve().parents[2] / "n8n" / "Trackpal WhatsApp Bot.json"
)


def _workflow_nodes() -> dict[str, dict]:
    payload = json.loads(WORKFLOW_PATH.read_text(encoding="utf-8"))
    return {node["name"]: node for node in payload["nodes"]}


def test_build_result_message_sets_close_after_send_contract() -> None:
    js = _workflow_nodes()["Build result message"]["parameters"]["jsCode"]

    assert "close_after_send" in js
    assert "poll.result_type === 'code'" in js
    assert "poll.result_type === 'url'" in js
    assert "closeAfterSend = true" in js or "close_after_send: true" in js


def test_build_result_message_keeps_retry_options_for_failed_timeout() -> None:
    js = _workflow_nodes()["Build result message"]["parameters"]["jsCode"]

    assert "Could not complete code search" in js
    assert "No se pudo completar la búsqueda" in js
    assert "1️⃣ Retry" in js
    assert "2️⃣ Back to services" in js
    assert "0️⃣ Cancel" in js
    assert "1️⃣ Reintentar" in js
    assert "2️⃣ Volver a servicios" in js
    assert "0️⃣ Cancelar" in js


def test_check_close_session_reads_close_after_send_from_upstream_result() -> None:
    js = _workflow_nodes()["Check close session"]["parameters"]["jsCode"]

    assert "$('Build result message').first().json" in js
    assert "const shouldCloseAfterSend = data.close_after_send === true;" in js
    assert "if (hasLookupResult && !shouldCloseAfterSend)" in js
    assert "const isLogout = shouldCloseAfterSend" in js
```

These tests should fail against the current workflow because:
- `Build result message` does not emit `close_after_send`
- `failed`/`timeout` do not include `1/2/0`
- `Check close session` does not read from `Build result message`

- [x] **Step 2: Run the new workflow tests and verify they fail**

Run:

```bash
cd backend && uv run pytest tests/test_n8n_whatsapp_workflow.py -q
```

Expected: FAIL on missing `close_after_send` / missing retry text / missing upstream lookup-result read.

- [x] **Step 3: Commit the red workflow tests**

```bash
git add backend/tests/test_n8n_whatsapp_workflow.py
git commit -m "test: lock n8n lookup close-session contract"
```

---

### Task 2: Implement the workflow-side close-after-send behavior

**Read before starting:**
- `superpowers:test-driven-development`
- `superpowers:verification-before-completion`
- `n8n-code-javascript`
- `n8n-expression-syntax`
- `docs/architecture/n8n-workflow.md`

**Files:**
- Modify: `n8n/Trackpal WhatsApp Bot.json` (nodes `Build result message`, `Check close session`)
- Test: `backend/tests/test_n8n_whatsapp_workflow.py`

- [x] **Step 1: Update `Build result message` to emit `close_after_send` and recoverable failure text**

Replace the current result-building logic with the same structure plus an explicit flag. The important shape is:

```javascript
const poll = $json;
const base = $('Merge & lookup data').first().json;
const seedReply = String(base.reply || '');

const looksEnglish = /searching code|you'll receive|code found|open link|error/i.test(seedReply);

const t = looksEnglish
  ? {
      codeFound: (v) => `✅ *Code found*\n\n📋 *${v}*\n\nThis code is time-sensitive. Use it soon.`,
      urlFound: (v) => `✅ *Link found*\n\n🔗 ${v}\n\nOpen link to continue.`,
      notFound: '❌ *Code not found*\n\nNo access-code emails found in last 5 minutes.\n\nRequest a new code and wait 15 seconds before trying again.\n\n1️⃣ Retry\n2️⃣ Back to services\n0️⃣ Cancel',
      failed: '❌ *Could not complete code search*\n\nAn error occurred or the search timed out.\n\n1️⃣ Retry\n2️⃣ Back to services\n0️⃣ Cancel',
    }
  : {
      codeFound: (v) => `✅ *Código encontrado*\n\n📋 *${v}*\n\nEste código es válido por tiempo limitado. Úsalo pronto.`,
      urlFound: (v) => `✅ *Enlace encontrado*\n\n🔗 ${v}\n\nAbre enlace para continuar.`,
      notFound: '❌ *No se encontró código*\n\nNo hay correos con códigos de acceso en últimos 5 minutos.\n\nSolicita nuevo código y espera 15 segundos antes de intentar de nuevo.\n\n1️⃣ Reintentar\n2️⃣ Volver a servicios\n0️⃣ Cancelar',
      failed: '❌ *No se pudo completar la búsqueda*\n\nOcurrió un error o se agotó el tiempo al buscar el código.\n\n1️⃣ Reintentar\n2️⃣ Volver a servicios\n0️⃣ Cancelar',
    };

let finalMessage;
let closeAfterSend = false;

if (poll.result_type === 'code') {
  finalMessage = t.codeFound(String(poll.result_value || ''));
  closeAfterSend = true;
} else if (poll.result_type === 'url') {
  finalMessage = t.urlFound(String(poll.result_value || ''));
  closeAfterSend = true;
} else if (poll.result_type === 'not_found' || poll.result_type === 'duplicate_suppressed') {
  finalMessage = t.notFound;
} else if (poll.status === 'failed' || poll.status === 'timeout' || poll.error_code) {
  finalMessage = t.failed;
} else {
  finalMessage = t.notFound;
}

return {
  json: {
    ...base,
    ...poll,
    reply: finalMessage,
    close_after_send: closeAfterSend,
  },
};
```

Do not add new nodes. Keep the change inside the existing Code node.

- [x] **Step 2: Update `Check close session` to read `close_after_send` from upstream result data**

Change the close guard to this shape:

```javascript
const fallback = $('Merge & lookup data').first().json;
const resultData = $('Build result message').first().json;
const data = { ...fallback, ...resultData, ...$json };
const msg = String(data.message || fallback.message || '').trim().toLowerCase();
const reply = String(data.reply || fallback.reply || '').toLowerCase();

const hasLookupResult = Boolean(data.lookup_job_id);
const shouldCloseAfterSend = data.close_after_send === true;
if (hasLookupResult && !shouldCloseAfterSend) {
  return [];
}

const isLogoutReply =
  reply.includes('sesión cerrada') ||
  reply.includes('sesion cerrada') ||
  reply.includes('has cerrado sesión') ||
  reply.includes('has cerrado sesion') ||
  reply.includes('goodbye') ||
  reply.includes('cerrado');
const isClosedStatus = String(data.status || '').toLowerCase() === 'closed';
const isLogoutCommand = msg === '0' || msg === 'salir';
const isLogout = shouldCloseAfterSend || isClosedStatus || (isLogoutCommand && isLogoutReply);

if (!isLogout) {
  return [];
}

const closeJids = Array.isArray(data.close_jids) && data.close_jids.length
  ? data.close_jids
  : [data.close_jid || data.reply_to || data.remoteJid];
const uniqueCloseJids = [...new Set(closeJids.filter(Boolean).map(String))];

return uniqueCloseJids.map((remoteJid) => ({ json: { ...data, close_jid: remoteJid } }));
```

Do not change `Send result`. The point of this task is to stop depending on HTTP node output preservation.

- [x] **Step 3: Verify the workflow JSON still parses**

Run:

```bash
python - <<'PY'
import json
from pathlib import Path
path = Path('n8n/Trackpal WhatsApp Bot.json')
json.loads(path.read_text(encoding='utf-8'))
print('workflow json ok')
PY
```

Expected: `workflow json ok`

- [x] **Step 4: Re-run the focused workflow regression tests**

Run:

```bash
cd backend && uv run pytest tests/test_n8n_whatsapp_workflow.py -q
```

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add n8n/Trackpal\ WhatsApp\ Bot.json backend/tests/test_n8n_whatsapp_workflow.py
git commit -m "fix: close successful lookup sessions in n8n"
```

---

### Task 3: Lock the tenant awaiting-result retry contract in unit tests

**Read before starting:**
- `superpowers:test-driven-development`
- `superpowers:verification-before-completion`
- `python-pro`
- `docs/superpowers/specs/2026-06-07-tpl-10-n8n-close-session-design.md`

**Files:**
- Modify: `backend/tests/test_tenant_console_service.py`
- Test: `backend/app/services/whatsapp_tenant_console_service/codigo_flow.py`

- [x] **Step 1: Add a failing test for tenant retry after local n8n timeout UX**

Add a test near the existing codigo-flow tests:

```python
async def test_codigo_awaiting_result_retry_allows_pending_job(
    self,
    console_service: WhatsAppTenantConsoleService,
) -> None:
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, patch

    mock_session_service = AsyncMock()
    mock_session = SimpleNamespace(
        temp_data={
            "lookup_job_id": str(uuid4()),
            "service_key": "netflix",
            "target_email": "user@example.com",
        }
    )

    with patch(
        "app.services.whatsapp_tenant_console_service.codigo_flow.mailbox_lookup_repository.get_job",
        AsyncMock(return_value=SimpleNamespace(status="pending")),
    ):
        reply = await console_service._handle_codigo_awaiting_result(
            phone="+10000000000",
            msg="1",
            session=mock_session,
            session_service=mock_session_service,
            tenant_id=uuid4(),
            db=AsyncMock(),
        )

    assert "buscando" in reply.lower() or "searching" in reply.lower()
    assert mock_session.temp_data["pending_lookup_intent"] == "true"
    mock_session_service.save_session.assert_awaited_once_with(mock_session)
```

This should fail today because the current code returns `wa.tenant.codigo.still_checking` when the previous job is still pending.

- [x] **Step 2: Add a failing test for tenant back-to-services while the old job is still pending**

Add a second test:

```python
async def test_codigo_awaiting_result_back_reopens_services_even_if_job_pending(
    self,
    console_service: WhatsAppTenantConsoleService,
) -> None:
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, patch

    tenant_id = uuid4()
    mock_session_service = AsyncMock()
    mock_session = SimpleNamespace(temp_data={"lookup_job_id": str(uuid4())})
    new_session = SimpleNamespace(flow=None, step=None, temp_data={})
    mock_session_service.create_session.return_value = new_session

    with (
        patch(
            "app.services.whatsapp_tenant_console_service.codigo_flow.mailbox_lookup_repository.get_job",
            AsyncMock(return_value=SimpleNamespace(status="pending")),
        ),
        patch(
            "app.services.whatsapp_tenant_console_service.codigo_flow.code_services_repository.get_effective_service_keys",
            AsyncMock(return_value=["netflix"]),
        ),
    ):
        reply = await console_service._handle_codigo_awaiting_result(
            phone="+10000000000",
            msg="2",
            session=mock_session,
            session_service=mock_session_service,
            tenant_id=tenant_id,
            db=AsyncMock(),
        )

    assert "Netflix" in reply
    assert new_session.flow == console_service.CODIGO_FLOW
    assert new_session.step == console_service.CODIGO_STEP_SERVICE
```

This should fail today because the current code returns `still_checking` for `2` while the old job is pending.

- [x] **Step 3: Run just the new tenant tests and confirm they fail**

Run:

```bash
cd backend && uv run pytest tests/test_tenant_console_service.py -k "codigo_awaiting_result_retry_allows_pending_job or codigo_awaiting_result_back_reopens_services_even_if_job_pending" -q
```

Expected: FAIL.

- [x] **Step 4: Commit the red tenant tests**

```bash
git add backend/tests/test_tenant_console_service.py
git commit -m "test: lock tenant codigo pending retry behavior"
```

---

### Task 4: Implement tenant pending retry/back behavior in `codigo_flow.py`

**Read before starting:**
- `superpowers:test-driven-development`
- `superpowers:verification-before-completion`
- `python-pro`
- `docs/architecture/whatsapp-console-flow.md`

**Files:**
- Modify: `backend/app/services/whatsapp_tenant_console_service/codigo_flow.py:289-408`
- Test: `backend/tests/test_tenant_console_service.py`

- [x] **Step 1: Remove the tenant-side `job_done` blocker for explicit `1` and `2` choices**

Make the logic look like this:

```python
if msg.strip() == "1":
    service_key = session.temp_data.get("service_key", "")
    target_email = session.temp_data.get("target_email", "")
    if service_key and target_email:
        session.temp_data["pending_lookup_intent"] = "true"
        await session_service.save_session(session)
        return _i18n_t(loc, "wa.tenant.codigo.buscando")

    effective_keys = await code_services_repository.get_effective_service_keys(
        db, tenant_id
    )
    ...  # existing service-list fallback remains
```

```python
if msg.strip() == "2":
    effective_keys = await code_services_repository.get_effective_service_keys(
        db, tenant_id
    )
    if not effective_keys:
        await session_service.clear_session(f"admin:{phone}")
        return self._t(self.KEY_CODIGO_NO_CODE_SERVICES_TENANT)

    await session_service.clear_session(f"admin:{phone}")
    new_session = await session_service.create_session(f"admin:{phone}")
    new_session.flow = self.CODIGO_FLOW
    new_session.step = self.CODIGO_STEP_SERVICE
    new_session.temp_data = {
        "codigo_effective_keys": effective_keys,
        "codigo_current_page": 0,
    }
    await session_service.save_session(new_session)
    service_list = _build_service_page(
        effective_keys, 0, loc, started_from_menu=False,
    )
    return self._t(self.KEY_CODIGO_SERVICE_PROMPT, service_list=service_list)
```

Keep `job_done` for the unknown-input fallback. Do not refactor the whole function.

- [x] **Step 2: Preserve the existing cancel path exactly**

Do not rewrite the cancel branch beyond keeping it intact:

```python
if msg.strip() == "0":
    await session_service.clear_session(f"admin:{phone}")
    return _i18n_t(loc, "wa.tenant.cancelled")
```

`_handle_tenant_console()` already adds `status="closed"` + `close_jid` when `is_cancel(message)` is true, so this task must not break that contract.

- [x] **Step 3: Re-run the targeted tenant tests**

Run:

```bash
cd backend && uv run pytest tests/test_tenant_console_service.py -k "codigo_awaiting_result_retry_allows_pending_job or codigo_awaiting_result_back_reopens_services_even_if_job_pending" -q
```

Expected: PASS.

- [x] **Step 4: Run the broader tenant console regression slice**

Run:

```bash
cd backend && uv run pytest tests/test_tenant_console_service.py -k "codigo_flow or codigo_awaiting_result or pending_lookup_intent" -q
```

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add backend/app/services/whatsapp_tenant_console_service/codigo_flow.py backend/tests/test_tenant_console_service.py
git commit -m "fix: allow tenant codigo retry after local timeout"
```

---

### Task 5: Lock the unauth awaiting-result retry contract in endpoint-adjacent tests

**Read before starting:**
- `superpowers:test-driven-development`
- `superpowers:verification-before-completion`
- `python-pro`
- `fastapi-expert`
- `docs/superpowers/specs/2026-06-07-tpl-10-n8n-close-session-design.md`

**Files:**
- Modify: `backend/tests/test_whatsapp_endpoint.py`
- Test: `backend/app/api/v1/endpoints/integrations/console_handlers.py`

- [x] **Step 1: Add a failing test for unauth retry while the previous job is still pending**

Add an endpoint-adjacent regression test close to the unauth codigo tests:

```python
async def test_unregistered_codigo_result_retry_requeues_even_if_old_job_pending(
    client, db_session, active_tenant_user
):
    from types import SimpleNamespace

    tenant = await _setup_tenant_for_codigo(db_session, active_tenant_user)
    fake_mgr = _FakeManager(used_backup=False)
    retry_job = SimpleNamespace(id=uuid4())

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

        with (
            patch(
                "app.api.v1.endpoints.integrations.console_handlers.mailbox_lookup_repository.get_job",
                AsyncMock(return_value=SimpleNamespace(status="pending")),
            ),
            patch(
                "app.api.v1.endpoints.integrations.console_handlers.mailbox_config_repository.get_by_tenant",
                AsyncMock(return_value=SimpleNamespace(id=uuid4(), status="connected")),
            ),
            patch(
                "app.api.v1.endpoints.integrations.console_handlers.mailbox_lookup_repository.create_job",
                AsyncMock(return_value=retry_job),
            ),
            patch(
                "app.api.v1.endpoints.integrations.console_handlers.enqueue_job",
                AsyncMock(return_value=True),
            ),
        ):
            response = await client.post(
                ENDPOINT,
                json={"phone": "+12015559999", "message": "1", "instance": TEST_INSTANCE},
                headers={"X-API-Key": settings.n8n_api_key},
            )

    assert response.status_code == 200
    body = response.json()
    assert body.get("lookup_job_id") == str(retry_job.id)
    assert body.get("tenant_id") == str(tenant.id)
    assert "buscando" in body["reply"].lower() or "searching" in body["reply"].lower()
```

This should fail today because the current unauth handler sends the user back to the service list instead of re-queuing with saved inputs.

- [x] **Step 2: Run the new unauth retry test and confirm it fails**

Run:

```bash
cd backend && uv run pytest tests/test_whatsapp_endpoint.py -k "unregistered_codigo_result_retry_requeues_even_if_old_job_pending" -q
```

Expected: FAIL.

- [x] **Step 3: Keep the existing cancel-close tests as regression coverage**

Do not rewrite these existing tests unless necessary:
- `test_unregistered_codigo_service_cancel_sets_closed_status`
- `test_registered_client_codigo_cancel_resumes_codigo_not_client_console`

They already protect the requirement that `0 Cancelar` closes the session.

- [x] **Step 4: Commit the red unauth retry test**

```bash
git add backend/tests/test_whatsapp_endpoint.py
git commit -m "test: lock unauth codigo pending retry behavior"
```

---

### Task 6: Implement unauth pending retry behavior in `console_handlers.py`

**Read before starting:**
- `superpowers:test-driven-development`
- `superpowers:verification-before-completion`
- `python-pro`
- `fastapi-expert`
- `docs/architecture/whatsapp-console-flow.md`

**Files:**
- Modify: `backend/app/api/v1/endpoints/integrations/console_handlers.py:746-946`
- Test: `backend/tests/test_whatsapp_endpoint.py`

- [x] **Step 1: Narrow the `not job_done` branch so it no longer intercepts explicit retry**

Change this part:

```python
if not job_done:
    if msg.strip() in ("1", "2"):
        await session_service.clear_session(session_key)
        ...
        return WhatsAppConsoleResponse(...service list...)
    return WhatsAppConsoleResponse(
        reply=_i18n_t(locale, "wa.tenant.codigo.still_checking"),
    )
```

into this shape:

```python
msg_clean = msg.strip()

if not job_done and msg_clean == "2":
    await session_service.clear_session(session_key)
    effective_keys = await code_services_repository.get_effective_service_keys(
        db, tenant.id
    )
    ...
    return WhatsAppConsoleResponse(
        reply=_i18n_t(
            locale,
            "wa.tenant.codigo.service_prompt",
            service_list=service_list,
        )
    )

if not job_done and msg_clean not in ("1", "2", "0"):
    return WhatsAppConsoleResponse(
        reply=_i18n_t(locale, "wa.tenant.codigo.still_checking"),
    )
```

That leaves `msg_clean == "1"` to flow into the existing retry-creation logic even when the previous job is still pending.

- [x] **Step 2: Reuse the existing retry-create path for `msg_clean == "1"`**

Do not invent a second retry path. Keep this structure and let it execute regardless of `job_done`:

```python
if msg_clean == "1":
    service_key = session.temp_data.get("service_key")
    target_email = session.temp_data.get("target_email", "")
    if service_key and target_email:
        mailbox = await mailbox_config_repository.get_by_tenant(db, tenant.id)
        ...
        job2 = await mailbox_lookup_repository.create_job(...)
        await db.flush()
        await db.commit()
        ...
        if enqueued:
            session.temp_data["lookup_job_id"] = str(job2.id)
            await session_service.save_session(session)
            return WhatsAppConsoleResponse(
                reply=_i18n_t(locale, "wa.tenant.codigo.buscando"),
                lookup_job_id=str(job2.id),
                tenant_id=str(tenant.id),
            )
```

This is the whole point of the backend change: retry with saved inputs, even when the previous DB job has not reached a terminal state yet.

- [x] **Step 3: Preserve the cancel-close branch exactly**

Keep this intact:

```python
if is_cancel(msg):
    await session_service.clear_session(session_key)
    return WhatsAppConsoleResponse(
        reply=_i18n_t(locale, "wa.tenant.cancelled"),
        status="closed",
        reply_to=close_jid,
        close_jid=close_jid,
    )
```

The user requirement is explicit: `0 Cancelar` must close, not remain open.

- [x] **Step 4: Run the focused unauth retry test**

Run:

```bash
cd backend && uv run pytest tests/test_whatsapp_endpoint.py -k "unregistered_codigo_result_retry_requeues_even_if_old_job_pending" -q
```

Expected: PASS.

- [x] **Step 5: Re-run the surrounding unauth codigo slice**

Run:

```bash
cd backend && uv run pytest tests/test_whatsapp_endpoint.py -k "unregistered_identity_codigo or unregistered_codigo_service_cancel or registered_client_codigo_cancel" -q
```

Expected: PASS.

- [x] **Step 6: Commit**

```bash
git add backend/app/api/v1/endpoints/integrations/console_handlers.py backend/tests/test_whatsapp_endpoint.py
git commit -m "fix: allow unauth codigo retry after local timeout"
```

---

### Task 7: Update docs and run final verification

**Read before starting:**
- `superpowers:verification-before-completion`
- `python-pro`
- `fastapi-expert`
- `docs/architecture/n8n-workflow.md`
- `docs/architecture/whatsapp-console-flow.md`

**Files:**
- Modify: `docs/architecture/n8n-workflow.md`
- Modify: `docs/architecture/whatsapp-console-flow.md`
- Test: `backend/tests/test_n8n_whatsapp_workflow.py`
- Test: `backend/tests/test_tenant_console_service.py`
- Test: `backend/tests/test_whatsapp_endpoint.py`

- [x] **Step 1: Update `docs/architecture/n8n-workflow.md` to match the new workflow contract**

Apply these documentation changes:

```md
**Logic**: `Build result message` emits `close_after_send=true` for terminal `code`/`url` results and `false` for recoverable outcomes (`not_found`, `duplicate_suppressed`, `failed`, `timeout`, unknown fallback non-success). `failed` and `timeout` messages now include `1 Retry / 2 Back to services / 0 Cancel`.
```

```md
**Logic**: `Check Close Session` closes when either:
1. `status === "closed"` from backend response, or
2. lookup result flow has `close_after_send === true`, or
3. message is logout command (`0`/`salir`) and reply text matches close semantic.

Guard: if `lookup_job_id` exists and `close_after_send !== true`, keep the session open because the lookup flow is still recoverable.
```

- [x] **Step 2: Update `docs/architecture/whatsapp-console-flow.md` to document local-timeout retry semantics**

Update both unauth and tenant sections with wording like:

```md
When n8n reaches its local poll timeout and shows retry options, reply `1` starts a fresh lookup with the saved `service_key` and `target_email` even if the previous mailbox job is still `pending` or `processing`. Reply `2` returns to the service list. Reply `0` clears the session and closes Evolution Go.
```

Do this in:
- the unauthenticated code lookup section
- the tenant `awaiting_result` section

- [x] **Step 3: Run the focused final regression set**

Run:

```bash
cd backend && uv run pytest tests/test_n8n_whatsapp_workflow.py tests/test_tenant_console_service.py tests/test_whatsapp_endpoint.py -q
```

Expected: PASS.

- [x] **Step 4: Run backend style checks only if Python files changed in this task need it**

Run:

```bash
cd backend && uv run ruff check tests/test_n8n_whatsapp_workflow.py tests/test_tenant_console_service.py tests/test_whatsapp_endpoint.py app/services/whatsapp_tenant_console_service/codigo_flow.py app/api/v1/endpoints/integrations/console_handlers.py
```

Expected: PASS.

- [x] **Step 5: Commit docs + final verification snapshot**

```bash
git add docs/architecture/n8n-workflow.md docs/architecture/whatsapp-console-flow.md
git commit -m "docs: document lookup close-session and retry semantics"
```

---

## Plan self-review

- Spec coverage: covered workflow close-after-send, failed/timeout `1/2/0`, tenant pending `1/2`, unauth pending `1`, explicit cancel-close preservation, and doc updates.
- Placeholder scan: no TBD/TODO placeholders left.
- Type consistency: uses existing names exactly as in code/spec: `close_after_send`, `lookup_job_id`, `tenant_id`, `_handle_codigo_awaiting_result`, `_handle_unauth_codigo_result`, `pending_lookup_intent`.
