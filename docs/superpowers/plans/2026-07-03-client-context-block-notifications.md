# Client Context Block Notifications Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Send terminal block/unblock notifications to the remote contact while preserving private admin-only menu actions.

**Architecture:** Keep backend as source of truth and n8n as the only WhatsApp transport. Backend returns the normal admin reply plus a list of extra outbound messages. n8n expands the backend response into per-destination send items, then closes configured sessions.

**Tech Stack:** FastAPI, Pydantic v2, pytest, n8n workflow JSON, JavaScript Code nodes, i18n catalogs.

## Global Constraints

- Actions from Client Context Shortcut menu are accepted only from the tenant admin private chat.
- External client chat non-menu messages remain silent and do not call backend.
- Blocking and unblocking are terminal context actions.
- Admin always receives a private confirmation.
- Contact receives a generic i18n notification at the original `targetJid`.
- n8n remains the only WhatsApp transport.
- Use TDD. Watch tests fail before production changes.

---

## File Structure

- Modify: `backend/app/schemas/whatsapp.py`
  - Add an `outbound_messages` response contract.
- Modify: `backend/app/api/v1/endpoints/integrations/console_handlers.py`
  - Attach client notification messages on block and unblock.
- Modify: `backend/app/core/i18n/catalogs_es_wa.py`
  - Add Spanish generic contact notification copy.
- Modify: `backend/app/core/i18n/catalogs_en_wa.py`
  - Add English generic contact notification copy.
- Modify: `backend/tests/test_whatsapp_client_context_shortcut.py`
  - Add failing behavior tests for block and unblock response payloads.
- Modify: `backend/tests/test_n8n_whatsapp_workflow.py`
  - Add failing workflow-contract tests for fan-out send items.
- Modify: `n8n/TrackPal WhatsApp Bot.json`
  - Update Merge code to preserve `outbound_messages`.
  - Add a Code node that expands admin reply plus extra messages.
  - Route normal sends through the expanded items.
- Modify: `docs/architecture/whatsapp-console-flow.md`
  - Document terminal block/unblock notification behavior.
- Modify: `docs/architecture/n8n-workflow.md`
  - Document outbound message fan-out.
- Already modified: `backend/CONTEXT.md`, `n8n/CONTEXT.md`
  - Domain glossary updates.

---

### Task 1: Backend response contract

**Files:**
- Modify: `backend/app/schemas/whatsapp.py`
- Test: `backend/tests/test_whatsapp_client_context_shortcut.py`

**Interfaces:**
- Produces: `WhatsAppOutboundMessage(target: str, text: str)`
- Produces: `WhatsAppConsoleResponse.outbound_messages: list[WhatsAppOutboundMessage] | None`

- [ ] **Step 1: Write the failing test**

Add assertions to `test_block_access_closes_client_context_immediately`:

```python
    outbound = body.get("outbound_messages")
    assert outbound == [
        {
            "target": f"{target_external_phone}@s.whatsapp.net",
            "text": "🚫 Acceso temporalmente suspendido. No puedes usar este servicio en este momento.",
        }
    ]
```

Add assertions to `test_unblock_access_closes_client_context_immediately`:

```python
    outbound = body.get("outbound_messages")
    assert outbound == [
        {
            "target": f"{target_external_phone}@s.whatsapp.net",
            "text": "✅ Acceso restaurado. Ya puedes usar este servicio nuevamente.",
        }
    ]
```

- [ ] **Step 2: Run red test**

Run:

```bash
cd backend && uv run pytest tests/test_whatsapp_client_context_shortcut.py::test_block_access_closes_client_context_immediately tests/test_whatsapp_client_context_shortcut.py::test_unblock_access_closes_client_context_immediately -q
```

Expected: FAIL because `outbound_messages` is missing.

- [ ] **Step 3: Implement minimal schema**

Add:

```python
class WhatsAppOutboundMessage(BaseModel):
    """Additional WhatsApp message for n8n transport."""

    target: str
    text: str
```

Add to `WhatsAppConsoleResponse`:

```python
    outbound_messages: list[WhatsAppOutboundMessage] | None = None
```

Add serializer section:

```python
        if self.outbound_messages is not None:
            d["outbound_messages"] = [
                message.model_dump() for message in self.outbound_messages
            ]
```

- [ ] **Step 4: Run green test target**

Run the same pytest command. Expected: still FAIL until Task 2 adds messages.

---

### Task 2: Backend block and unblock notifications

**Files:**
- Modify: `backend/app/api/v1/endpoints/integrations/console_handlers.py`
- Modify: `backend/app/core/i18n/catalogs_es_wa.py`
- Modify: `backend/app/core/i18n/catalogs_en_wa.py`
- Test: `backend/tests/test_whatsapp_client_context_shortcut.py`

**Interfaces:**
- Consumes: `WhatsAppOutboundMessage`
- Produces: terminal responses with `outbound_messages`

- [ ] **Step 1: Add i18n keys**

Spanish:

```python
"wa.tenant.client_context.block_access.client_notice": "🚫 Acceso temporalmente suspendido. No puedes usar este servicio en este momento.",
"wa.tenant.client_context.unblock_access.client_notice": "✅ Acceso restaurado. Ya puedes usar este servicio nuevamente.",
```

English:

```python
"wa.tenant.client_context.block_access.client_notice": "🚫 Access temporarily suspended. You cannot use this service right now.",
"wa.tenant.client_context.unblock_access.client_notice": "✅ Access restored. You can use this service again.",
```

- [ ] **Step 2: Add helper**

In `console_handlers.py`:

```python
def _client_context_notification_target(temp_data: dict) -> str | None:
    target_jid = _canonical_jid(temp_data.get("target_jid"))
    if target_jid:
        return target_jid
    target_phone = normalize_phone(temp_data.get("target_phone"))
    if target_phone:
        return f"{target_phone}@s.whatsapp.net"
    target_lid = temp_data.get("target_lid")
    return _canonical_jid(target_lid)
```

- [ ] **Step 3: Attach block notification**

In `_handle_ctx_unblocked_menu`, when `msg_lower == "2"`, compute:

```python
        target_notice = _client_context_notification_target(data.get("temp_data", {}))
        outbound_messages = (
            [
                WhatsAppOutboundMessage(
                    target=target_notice,
                    text=_i18n_t(locale, "wa.tenant.client_context.block_access.client_notice"),
                )
            ]
            if target_notice
            else None
        )
```

Pass `outbound_messages=outbound_messages` into `WhatsAppConsoleResponse`.

- [ ] **Step 4: Attach unblock notification**

In `_handle_ctx_blocked_menu`, when `msg_lower == "1"`, compute:

```python
        target_notice = _client_context_notification_target(data.get("temp_data", {}))
        outbound_messages = (
            [
                WhatsAppOutboundMessage(
                    target=target_notice,
                    text=_i18n_t(locale, "wa.tenant.client_context.unblock_access.client_notice"),
                )
            ]
            if target_notice
            else None
        )
```

Pass `outbound_messages=outbound_messages` into `WhatsAppConsoleResponse`.

- [ ] **Step 5: Run focused tests**

Run:

```bash
cd backend && uv run pytest tests/test_whatsapp_client_context_shortcut.py::test_block_access_closes_client_context_immediately tests/test_whatsapp_client_context_shortcut.py::test_unblock_access_closes_client_context_immediately -q
```

Expected: PASS.

---

### Task 3: n8n fan-out contract tests

**Files:**
- Modify: `backend/tests/test_n8n_whatsapp_workflow.py`
- Modify: `n8n/TrackPal WhatsApp Bot.json`

**Interfaces:**
- Consumes: `outbound_messages: [{ target, text }]`
- Produces: send items with `send_target` and `send_text`

- [ ] **Step 1: Write failing workflow tests**

Add:

```python
def test_merge_preserves_outbound_messages_contract() -> None:
    js = _workflow_nodes()["Merge & lookup data"]["parameters"]["jsCode"]

    assert "const outboundMessages = Array.isArray(responseData.outbound_messages)" in js
    assert "outbound_messages: outboundMessages" in js


def test_prepare_evolution_sends_expands_admin_and_extra_messages() -> None:
    nodes = _workflow_nodes()
    js = nodes["Prepare Evolution sends"]["parameters"]["jsCode"]

    assert "const outboundMessages = Array.isArray(data.outbound_messages)" in js
    assert "send_target" in js
    assert "send_text" in js
    assert "target: message.target" in js
    assert "text: message.text" in js


def test_normal_reply_routes_through_prepare_evolution_sends() -> None:
    connections = _workflow_connections()

    assert connections["IF has lookup"]["main"][1][0]["node"] == "Prepare Evolution sends"
    assert connections["Prepare Evolution sends"]["main"][0][0]["node"] == "Evolution API Send"
    assert connections["Evolution API Send"]["main"][0][0]["node"] == "Check close session"
```

- [ ] **Step 2: Run red workflow tests**

Run:

```bash
cd backend && uv run pytest tests/test_n8n_whatsapp_workflow.py::test_merge_preserves_outbound_messages_contract tests/test_n8n_whatsapp_workflow.py::test_prepare_evolution_sends_expands_admin_and_extra_messages tests/test_n8n_whatsapp_workflow.py::test_normal_reply_routes_through_prepare_evolution_sends -q
```

Expected: FAIL because the node and code do not exist.

- [ ] **Step 3: Update workflow JSON**

Add Code node `Prepare Evolution sends` after `IF has lookup` false branch:

```javascript
const data = $json;
const outboundMessages = Array.isArray(data.outbound_messages)
  ? data.outbound_messages
  : [];

const results = [];
const adminTarget = data.reply_to || data.phone || data.remoteJid || '';
const adminText = String(data.reply || '');

if (adminTarget && adminText) {
  results.push({
    json: {
      ...data,
      send_target: String(adminTarget),
      send_text: adminText,
      send_role: 'primary',
    },
  });
}

for (const message of outboundMessages) {
  if (!message || !message.target || !message.text) continue;
  results.push({
    json: {
      ...data,
      send_target: String(message.target),
      send_text: String(message.text),
      send_role: 'outbound_message',
    },
  });
}

return results;
```

Update `Evolution API Send` body:

```text
={{ JSON.stringify({ number: String($json.send_target || $json.reply_to || $json.phone || $json.remoteJid || '').replace('+', ''), text: String($json.send_text || $json.reply || '') }) }}
```

- [ ] **Step 4: Run workflow tests**

Run the same workflow tests. Expected: PASS.

---

### Task 4: Docs and verification

**Files:**
- Modify: `docs/architecture/whatsapp-console-flow.md`
- Modify: `docs/architecture/n8n-workflow.md`
- Run: backend focused tests and workflow contract tests

- [ ] **Step 1: Update docs**

Document:

- external non-menu tenant messages remain silent and do not close sessions;
- private admin menu actions trigger backend;
- block and unblock return admin confirmation plus contact notification;
- n8n expands `outbound_messages` into Evolution sends.

- [ ] **Step 2: Run verification**

Run:

```bash
cd backend && uv run pytest tests/test_whatsapp_client_context_shortcut.py::test_block_access_closes_client_context_immediately tests/test_whatsapp_client_context_shortcut.py::test_unblock_access_closes_client_context_immediately tests/test_n8n_whatsapp_workflow.py -q
```

Expected: PASS.

- [ ] **Step 3: Check no debug artifacts**

Run:

```bash
rg "DEBUG-" backend n8n docs
```

Expected: no matches.

---

## Self-Review

- Spec coverage: private admin actions, terminal context close, admin confirmation, contact notification, targetJid transport, n8n-only sending, and docs are covered.
- Placeholder scan: no TBD or TODO placeholders.
- Type consistency: `WhatsAppOutboundMessage.target/text` matches n8n `message.target/message.text`.
