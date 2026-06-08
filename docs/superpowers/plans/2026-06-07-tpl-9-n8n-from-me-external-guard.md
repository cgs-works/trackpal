# TPL-9 n8n fromMe External Guard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent `fromMe=true` external non-menu messages from calling the TrackPal backend or keeping an Evolution Go session open, while preserving `/menu` / `menu` Client Context Shortcut behavior and normal inbound code lookup.

**Architecture:** Keep the fix isolated to `n8n/Trackpal WhatsApp Bot.json`, plus workflow-contract tests and doc updates. Per user decision, place the guard **after `Config` and before `Console call`** so both branches can keep using the existing `Config` node references; the true branch goes directly to `Check close session`, and the false branch continues through the current backend path unchanged. `Check close session` must also become tolerant of the new guard branch, because `Merge & lookup data` will not execute on guarded items.

**Tech Stack:** n8n workflow JSON, JavaScript Code nodes, pytest, Ruff, project docs in `docs/architecture/`.

---

## File map

- `n8n/Trackpal WhatsApp Bot.json`
  - Source of truth for the WhatsApp Bot workflow. This change adds the guard Code node, the IF routing node, rewires connections, and hardens `Check close session` for the guarded branch.
- `backend/tests/test_n8n_whatsapp_workflow.py`
  - Regression tests that parse the workflow export and lock the new guard contract, routing, and close-session tolerance.
- `docs/architecture/n8n-workflow.md`
  - Workflow architecture doc that must describe the new pre-backend guard and the guarded close path.
- `docs/architecture/whatsapp-console-flow.md`
  - Console routing doc that must explain that external `from_me` non-menu messages are now stopped in n8n before backend routing.
- `docs/superpowers/specs/2026-06-07-tpl-9-n8n-from-me-external-guard-design.md`
  - Design spec to keep open while implementing; do not modify it during this plan.

---

### Task 1: Lock the workflow guard contract with failing regression tests

**Read before starting:**
- `superpowers:subagent-driven-development` **or** `superpowers:executing-plans`
- `superpowers:test-driven-development`
- `superpowers:verification-before-completion`
- `n8n-code-javascript`
- `docs/superpowers/specs/2026-06-07-tpl-9-n8n-from-me-external-guard-design.md`

**Files:**
- Modify: `backend/tests/test_n8n_whatsapp_workflow.py`
- Test: `backend/tests/test_n8n_whatsapp_workflow.py`

- [x] **Step 1: Replace the helper block at the top of `backend/tests/test_n8n_whatsapp_workflow.py`**

Change the helper section to this exact code so the tests can inspect both nodes and connections:

```python
import json
from pathlib import Path

WORKFLOW_PATH = (
    Path(__file__).resolve().parents[2] / "n8n" / "Trackpal WhatsApp Bot.json"
)


def _workflow_payload() -> dict:
    return json.loads(WORKFLOW_PATH.read_text(encoding="utf-8"))


def _workflow_nodes() -> dict[str, dict]:
    payload = _workflow_payload()
    return {node["name"]: node for node in payload["nodes"]}


def _workflow_connections() -> dict[str, dict]:
    return _workflow_payload()["connections"]
```

- [x] **Step 2: Append the new failing guard tests after the existing close-session test**

Append these tests exactly:

```python
def test_guard_from_me_external_non_menu_sets_skip_and_close_contract() -> None:
    js = _workflow_nodes()["Guard fromMe external non-menu"]["parameters"]["jsCode"]

    assert "const canonicalJid = (value) => {" in js
    assert "const isMenuCommand = message === '/menu' || message === 'menu';" in js
    assert "const shouldSkipBackend = Boolean(" in js
    assert "fromMe &&" in js
    assert "!isSelfTarget" in js
    assert "!isMenuCommand" in js
    assert "skip_console_call: true" in js
    assert "no_reply: true" in js
    assert "status: 'closed'" in js
    assert "close_jid: targetJid" in js
    assert "close_jids: [targetJid]" in js
    assert "guard_reason: 'from_me_external_non_menu'" in js


def test_guard_keeps_menu_self_target_and_missing_target_on_backend_path() -> None:
    js = _workflow_nodes()["Guard fromMe external non-menu"]["parameters"]["jsCode"]

    assert "const isSelfTarget = Boolean(" in js
    assert "targetJid &&" in js
    assert "targetJid === adminJid" in js
    assert "targetJid === remoteJid && adminJid === remoteJid" in js
    assert "return [{ json: { ...input, skip_console_call: false } }];" in js


def test_if_skip_console_call_routes_guarded_items_to_close_path() -> None:
    node = _workflow_nodes()["IF skip console call"]
    condition = node["parameters"]["conditions"]["conditions"][0]

    assert condition["leftValue"] == "={{ $json.skip_console_call }}"
    assert condition["operator"]["type"] == "boolean"
    assert condition["operator"]["operation"] == "true"


def test_guard_connections_bypass_console_call_on_true_branch() -> None:
    connections = _workflow_connections()

    assert connections["Config"]["main"][0][0]["node"] == "Guard fromMe external non-menu"
    assert connections["Guard fromMe external non-menu"]["main"][0][0]["node"] == "IF skip console call"
    assert connections["IF skip console call"]["main"][0][0]["node"] == "Check close session"
    assert connections["IF skip console call"]["main"][1][0]["node"] == "Console call"


def test_check_close_session_tolerates_guard_branch_without_merge_data() -> None:
    js = _workflow_nodes()["Check close session"]["parameters"]["jsCode"]

    assert "let fallback = {};" in js
    assert "fallback = $('Merge & lookup data').first().json;" in js
    assert "resultData = $('Build result message').first().json;" in js
    assert "const data = { ...fallback, ...resultData, ...$json };" in js
```

These tests should fail against the current workflow because the guard node, IF node, and rewired connections do not exist yet, and `Check close session` still assumes `Merge & lookup data` always executed.

- [x] **Step 3: Run the focused workflow tests and verify they fail for the expected reason**

Run:

```bash
cd backend && uv run pytest tests/test_n8n_whatsapp_workflow.py -q
```

Expected: FAIL with a `KeyError` or assertion failure mentioning `Guard fromMe external non-menu`, `IF skip console call`, or missing guarded-branch fallback handling.

- [x] **Step 4: Commit the red tests**

```bash
git add backend/tests/test_n8n_whatsapp_workflow.py
git commit -m "test: lock tpl-9 n8n guard contract"
```

---

### Task 2: Implement the n8n guard, routing, and guarded close-session path

**Read before starting:**
- `superpowers:test-driven-development`
- `superpowers:verification-before-completion`
- `n8n-workflow-patterns`
- `n8n-code-javascript`
- `n8n-expression-syntax`
- `n8n-node-configuration`
- `n8n-validation-expert`
- `n8n-mcp-tools-expert` **only if you choose to edit the live workflow through MCP instead of editing the repo JSON directly**

**Files:**
- Modify: `n8n/Trackpal WhatsApp Bot.json`
- Test: `backend/tests/test_n8n_whatsapp_workflow.py`

- [x] **Step 1: Insert the new guard Code node after `Config` in the `nodes` array**

Add this node object to `n8n/Trackpal WhatsApp Bot.json`:

```json
{
  "parameters": {
    "jsCode": "const input = $json;\n\nconst canonicalJid = (value) => {\n  const raw = String(value || '').trim();\n  if (!raw) return '';\n  if (!raw.includes('@')) return raw;\n  const [local, domain] = raw.split('@', 2);\n  return `${local.split(':', 1)[0]}@${domain}`;\n};\n\nconst message = String(input.message || '').trim().toLowerCase();\nconst fromMe = input.fromMe === true;\nconst targetJid = canonicalJid(input.targetJid);\nconst adminJid = canonicalJid(input.adminJid);\nconst remoteJid = canonicalJid(input.remoteJid);\n\nconst isMenuCommand = message === '/menu' || message === 'menu';\nconst isSelfTarget = Boolean(\n  targetJid &&\n  ((adminJid && targetJid === adminJid) || (remoteJid && targetJid === remoteJid && adminJid === remoteJid))\n);\n\nconst shouldSkipBackend = Boolean(\n  fromMe &&\n  targetJid &&\n  !isSelfTarget &&\n  !isMenuCommand\n);\n\nif (shouldSkipBackend) {\n  return [{\n    json: {\n      ...input,\n      reply: '',\n      no_reply: true,\n      status: 'closed',\n      close_jid: targetJid,\n      close_jids: [targetJid],\n      skip_console_call: true,\n      guard_reason: 'from_me_external_non_menu',\n    },\n  }];\n}\n\nreturn [{ json: { ...input, skip_console_call: false } }];"
  },
  "id": "f0a76839-519f-4f9e-b7d0-2f0a4f5d9001",
  "name": "Guard fromMe external non-menu",
  "type": "n8n-nodes-base.code",
  "typeVersion": 2,
  "position": [
    720,
    -384
  ]
}
```

Do not change `Parse input`. The guard should consume the merged output of `Config`, so the guarded branch can still reuse the existing `Config` references downstream.

- [x] **Step 2: Insert the new IF node that routes guarded items around `Console call`**

Add this node object immediately after the guard node:

```json
{
  "parameters": {
    "conditions": {
      "combinator": "and",
      "conditions": [
        {
          "leftValue": "={{ $json.skip_console_call }}",
          "rightValue": true,
          "operator": {
            "type": "boolean",
            "operation": "true",
            "singleValue": true
          },
          "id": "condition-ifskipconsole-001"
        }
      ],
      "options": {
        "version": 2,
        "leftValue": "",
        "caseSensitive": true,
        "typeValidation": "strict"
      }
    },
    "options": {}
  },
  "id": "f0a76839-519f-4f9e-b7d0-2f0a4f5d9002",
  "name": "IF skip console call",
  "type": "n8n-nodes-base.if",
  "typeVersion": 2.3,
  "position": [
    928,
    -384
  ]
}
```

- [x] **Step 3: Replace the `Check close session` JavaScript so the guard branch works even when `Merge & lookup data` never ran**

Replace the current `jsCode` for `Check close session` with this exact code:

```javascript
let fallback = {};
try {
  fallback = $('Merge & lookup data').first().json;
} catch (e) {
  fallback = {};
}

let resultData = {};
try {
  resultData = $('Build result message').first().json;
} catch (e) {
  resultData = {};
}

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

Do not change `Close session`. The point of placing the guard after `Config` is to keep the existing `$('Config').first()` references intact.

- [x] **Step 4: Rewire the workflow connections so guarded items skip `Console call` and go straight to `Check close session`**

Update the `connections` object to this shape for the affected blocks:

```json
"Config": {
  "main": [
    [
      {
        "node": "Guard fromMe external non-menu",
        "type": "main",
        "index": 0
      }
    ]
  ]
},
"Guard fromMe external non-menu": {
  "main": [
    [
      {
        "node": "IF skip console call",
        "type": "main",
        "index": 0
      }
    ]
  ]
},
"IF skip console call": {
  "main": [
    [
      {
        "node": "Check close session",
        "type": "main",
        "index": 0
      }
    ],
    [
      {
        "node": "Console call",
        "type": "main",
        "index": 0
      }
    ]
  ]
}
```

Leave `Console call -> Merge & lookup data`, `Merge & lookup data -> IF no reply`, and all lookup nodes unchanged.

- [x] **Step 5: Verify the workflow JSON still parses after the edits**

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

- [x] **Step 6: Re-run the focused workflow regression tests and verify they pass**

Run:

```bash
cd backend && uv run pytest tests/test_n8n_whatsapp_workflow.py -q
```

Expected: PASS.

- [x] **Step 7: Commit the workflow implementation**

```bash
git add n8n/Trackpal\ WhatsApp\ Bot.json backend/tests/test_n8n_whatsapp_workflow.py
git commit -m "fix: guard from_me external non-menu in n8n"
```

---

### Task 3: Update the architecture docs so the new workflow behavior is discoverable

**Read before starting:**
- `superpowers:verification-before-completion`
- `docs/SUMMARY.md`
- `docs/architecture/n8n-workflow.md`
- `docs/architecture/whatsapp-console-flow.md`

**Files:**
- Modify: `docs/architecture/n8n-workflow.md`
- Modify: `docs/architecture/whatsapp-console-flow.md`

- [x] **Step 1: Replace the top WhatsApp Bot flow diagram in `docs/architecture/n8n-workflow.md`**

Replace the current overview block with this exact text:

```markdown
Evolution Go (inbound or outgoing trigger)
    |  webhook POST
n8n Webhook Node
    ↓
Parse Input (Code Node) — normalises phone, message, instance, apiKey, remoteJid,
    sender_lid, fromMe, adminJid, targetJid, targetPhone, targetLid
    ↓
Config (Set Node) — supplies config vars from node fields
    ↓
Guard fromMe external non-menu (Code Node) — classifies external `fromMe=true`
    non-menu traffic before backend routing
    ↓
IF skip_console_call?
   ├─ Yes → Check Close Session → Close Session
   └─ No  → Console Call (HTTP Request Node) — POST /api/v1/integrations/n8n/console
              ↓
         Merge & lookup data (Code Node) — merges reply + control fields
              ↓
         IF no_reply=true?
           ├─ Yes → Check Close Session (skip all Evolution sends)
           └─ No  → IF has lookup_job_id?
                     ├─ No  → Evolution Go Send → Check Close Session
                     └─ Yes → Send "buscando..." → Wait 4s loop → Poll status
                                → Build result message → Send result → Check Close Session
```

- [x] **Step 2: Add the new guard node and IF node sections to `docs/architecture/n8n-workflow.md`**

Insert this exact documentation after `### 3. Config (Set Node)` and before `### 4. Console Call (HTTP Request Node)`:

````markdown
### 3a. Guard fromMe external non-menu (Code Node)

A Code node that runs after `Config` and before `Console call`.

**Purpose**: stop accidental backend dispatch for outgoing tenant-admin messages that target an external chat but are not intentional Client Context Shortcut commands.

**Classification**:
- canonicalize `adminJid`, `targetJid`, and `remoteJid` by stripping device suffixes such as `:81`
- allow `/menu` and `menu` to continue
- allow self-target traffic to continue
- allow missing-`targetJid` traffic to continue defensively
- when `fromMe=true`, `targetJid` is external, and the message is not `/menu` or `menu`, emit:

```json
{
  "reply": "",
  "no_reply": true,
  "status": "closed",
  "close_jid": "<targetJid>",
  "close_jids": ["<targetJid>"],
  "skip_console_call": true,
  "guard_reason": "from_me_external_non_menu"
}
```

This keeps the fix text-agnostic and closes the accidental Evolution session immediately.

### 3b. IF skip console call (IF Node)

Routes the guard output:
- **true branch** → `Check close session`
- **false branch** → existing `Console call` path

This means guarded items skip both backend traffic and all Evolution send nodes.
````

- [x] **Step 3: Update the `Check Close Session` description and add the guarded outgoing example**

In `docs/architecture/n8n-workflow.md`, replace the `### 7. Check Close Session (Code Node)` logic paragraph with this exact text:

```markdown
### 7. Check Close Session (Code Node)

JavaScript that conditionally triggers session close.

**Logic**: `Check Close Session` now tolerates two upstream shapes:
1. the normal backend path (`Merge & lookup data`, optionally `Build result message`), and
2. the guarded path where `Guard fromMe external non-menu` sends the item directly here and `Merge & lookup data` never ran.

The node closes when either:
1. `status === "closed"` from backend or guard output,
2. lookup result flow has `close_after_send === true`, or
3. message is logout command (`0`/`salir`) and reply text matches close semantic.

When `close_jids` is present, the node emits one item per JID so `Close session` processes each one.
```

Then add this new example section after the existing `/menu` outgoing example:

````markdown
### Outgoing external non-menu trigger (admin → external chat, from_me=true)

```text
Evolution Go webhook payload (isTrusted=true, fromMe=true)
  ↓
Parse Input → Config
  ↓
Guard fromMe external non-menu
  → emits { no_reply: true, status: "closed", close_jid: targetJid,
            close_jids: [targetJid], skip_console_call: true,
            guard_reason: "from_me_external_non_menu" }
  ↓
IF skip_console_call? → Yes
  ↓
Check Close Session
  ↓
Close Session → POST /webhook/change-status for targetJid
```

Backend is not called on this path, no bot reply is sent, and the accidental external chat session is closed immediately.
````

- [x] **Step 4: Add the n8n pre-guard note to `docs/architecture/whatsapp-console-flow.md`**

Insert this exact paragraph immediately before the numbered list under `## From-me Contextual Routing`:

```markdown
Before `_handle_from_me_routing()` runs, the n8n workflow now pre-guards external `from_me=true` non-menu traffic. If the admin targets an external chat and sends anything other than `/menu` or `menu`, n8n skips the backend call, sends no reply, and closes the target Evolution session. Only allowed shortcut starters (`/menu` and `menu`) continue to backend contextual routing.
```

- [x] **Step 5: Verify the docs mention the new guard in both architecture files**

Run:

```bash
rg -n 'Guard fromMe external non-menu|IF skip console call|from_me_external_non_menu|pre-guards external `from_me=true`' docs/architecture/n8n-workflow.md docs/architecture/whatsapp-console-flow.md
```

Expected: matching lines in both files.

- [x] **Step 6: Commit the documentation update**

```bash
git add docs/architecture/n8n-workflow.md docs/architecture/whatsapp-console-flow.md
git commit -m "docs: describe tpl-9 n8n guard"
```

---

### Task 4: Run final verification and manual scenario checks before claiming completion

**Read before starting:**
- `superpowers:verification-before-completion`
- `n8n-validation-expert`
- `n8n-mcp-tools-expert` **if validating or importing through n8n MCP**

**Files:**
- Verify: `n8n/Trackpal WhatsApp Bot.json`
- Verify: `backend/tests/test_n8n_whatsapp_workflow.py`
- Verify: `docs/architecture/n8n-workflow.md`
- Verify: `docs/architecture/whatsapp-console-flow.md`

- [ ] **Step 1: Run the repo-side verification commands fresh**

Run:

```bash
python - <<'PY'
import json
from pathlib import Path
path = Path('n8n/Trackpal WhatsApp Bot.json')
json.loads(path.read_text(encoding='utf-8'))
print('workflow json ok')
PY

(cd backend && uv run pytest tests/test_n8n_whatsapp_workflow.py -q)
(cd backend && uv run ruff check tests/test_n8n_whatsapp_workflow.py)
```

Expected:
- `workflow json ok`
- pytest PASS
- Ruff exits cleanly

- [ ] **Step 2: Import the updated workflow export into n8n and run the manual TPL-9 checks**

Use `n8n/Trackpal WhatsApp Bot.json` as the import source, then verify these scenarios in order:

1. Tenant A sends `code` to Tenant B.
2. Tenant A execution shows `Guard fromMe external non-menu` with `skip_console_call=true`, `guard_reason=from_me_external_non_menu`, no `Console call`, and a `Close session` request for Tenant B `targetJid`.
3. Tenant B execution still reaches `Console call` and sends the code-service menu.
4. Tenant A does **not** answer Tenant B’s menu afterward.
5. Tenant A sends `/menu` in an external chat and the execution goes through `Console call` normally.
6. An inbound `fromMe=false` `code` message still goes through the backend path normally.

Expected: all six checks succeed.

- [ ] **Step 3: Record the verification evidence in the handoff**

Include these concrete facts in the handoff note or PR description:

```markdown
- `python` JSON parse check: passed
- `cd backend && uv run pytest tests/test_n8n_whatsapp_workflow.py -q`: passed
- `cd backend && uv run ruff check tests/test_n8n_whatsapp_workflow.py`: passed
- Manual n8n check: guarded outgoing `code` skipped backend and closed target session
- Manual n8n check: outgoing `/menu` still reached backend
- Manual n8n check: inbound `code` still reached backend
```

Do not claim the fix is complete until all of the above evidence exists.
