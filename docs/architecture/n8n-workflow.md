# n8n WhatsApp Workflow

> **Architecture (Phase 3+, 2026-05-12):** For the WhatsApp Master Console, n8n is **transport-only**. The backend owns conversation logic, menu routing, Redis-backed session state with active-passive HA, and circuit-breaker failover (see ADR-0004). n8n only: receive message → call backend console endpoint → send reply — without interpreting product logic.

## Overview

Single n8n workflow that transports WhatsApp messages between Evolution API and the Trackpal backend for the Master Console.

- **Instance**: `https://rs-n8n.wilfredocamacho.dev`
- **Workflow**: `Trackpal WhatsApp Bot` (ID: `mN3k0vVO9kgBYQtV`)
- **Webhook**: `POST /webhook/trackpal-whatsapp-bot`
- **Workflow export**: `n8n/Trackpal WhatsApp Bot.json`

## Node flow — Transport-only (Phase 3+)

```
WhatsApp → Evolution API (n8n integration, keyword trigger: "/menu")
             ↓
       Webhook (1)
             ↓
       Parse input (2) [Code]
         → Extracts: phone, message, instance name
             ↓
       Console call (3) [HTTP POST]
         → POST /api/v1/integrations/n8n/console
         → Body: { phone, message, instance }
         → Header: X-API-Key
             ↓
       Merge reply (4) [Code]
         → Combines original input with backend reply
             ↓
       Evolution API Send (5) [HTTP POST]
         → POST /message/sendText/{instance}
         → Body: { number, text }

       Config node (0) [Set] — sibling, not in data-flow graph
         → Holds operational values consumed by nodes 3 and 5
         → Referenced via `$('Config').first().json.*`
```

## Node details

### 1. Webhook
- Method: `POST`
- Path: `trackpal-whatsapp-bot`
- Response mode: `lastNode`

### 2. Parse input (Code)
Normalises the inbound Evolution API payload into a consistent shape.

```javascript
const payload = $json;

// Evolution API n8n integration format (n8n/create endpoint)
const body = payload.body || {};
const chatInput = body.chatInput || '';
const remoteJid = body.remoteJid || '';
const instanceName = body.instanceName || '';

// Generic webhook format (fallback)
const data = payload.data || {};
const msg = data.message || {};
const from = msg.from || msg.key?.remoteJid || '';

const phone = remoteJid || String(from).replace('@c.us','').replace('@s.whatsapp.net','');
const message = chatInput || String(msg.body || msg.message?.conversation || '').trim();
const instance = instanceName || data.instance || payload.instance || 'default';

return [{ json: { phone, message, instance, raw: payload } }];
```

### 3. Console call (HTTP POST)
Calls the backend WhatsApp Master Console endpoint. The backend handles all auth, session state, menu routing, and CRUD logic.

- URL: `{{$('Config').first().json.trackpal_backend_url}}/api/v1/integrations/n8n/console`
- Method: `POST`
- Headers: `X-API-Key` (value from `{{$('Config').first().json.trackpal_n8n_api_key}}`), `Content-Type: application/json`
- Body: `{ phone, message, instance }`
- Response: `{ reply }`

### 4. Merge reply (Code)
Merges the original parse output (phone, instance) with the backend reply so the send node has all required fields.

```javascript
const input = $("Parse input").first().json;
const reply = $json.reply || '';
return [{ json: { ...input, reply } }];
```

### 5. Evolution API Send (HTTP POST)
Sends the backend reply text back to the WhatsApp user through Evolution API.

- URL: `{{$('Config').first().json.evolution_api_url}}/message/sendText/{{$json.instance}}`
- Method: `POST`
- Headers: `apikey` (value from `{{$('Config').first().json.evolution_api_key}}`)
- Body: `{ number, text }`

## Evolution API integration

The workflow is triggered via Evolution API's **n8n integration** (not the generic webhook). Configured per instance:

```
POST /n8n/create/{instanceName}
{
  "enabled": true,
  "webhookUrl": "https://rs-n8n.wilfredocamacho.dev/webhook/trackpal-whatsapp-bot",
  "triggerType": "keyword",
  "triggerOperator": "startsWith",
  "triggerValue": "/menu"
}
```

Only messages starting with `/menu` are sent to n8n, reducing unnecessary traffic.

## Configuration — Config Set node pattern

> **Community-license constraint:** The self-hosted n8n community edition does not expose the Environment Variables UI (Settings → Environment Variables). That feature requires a commercial n8n license (pro/enterprise). To keep the workflow portable without a paid license, the live workflow uses an in-workflow **Config Set node** (type: `n8n-nodes-base.set`) to hold operational values instead of `$env.*` expressions.

The Config node is a sibling node (not connected in the data-flow graph). Other nodes reference its values via `$('Config').first().json.*` expressions. This keeps secrets and URLs out of the node parameter exports while working on any n8n edition.

### Config node values

| Key | Description |
|---|---|
| `trackpal_backend_url` | Trackpal backend base URL (e.g. `https://trackpal-backend.onrender.com`) |
| `trackpal_n8n_api_key` | N8N_API_KEY from backend config |
| `evolution_api_url` | Evolution API base URL (e.g. `https://rs-evoapi.wilfredocamacho.dev`) |
| `evolution_api_key` | Evolution API key |
| `default_instance` | Default Evolution API instance name |

### Setting up on a fresh n8n instance

1. Import or recreate the workflow in n8n.
2. Locate the **Config** Set node (not connected to any flow edges).
3. Open its parameters and populate the key-value pairs above with your actual values.
4. Activate the workflow.

> **Note:** The local export (`n8n/Trackpal WhatsApp Bot.json`) still uses `$env.*` expressions for portability. The live workflow on `rs-n8n.wilfredocamacho.dev` has been manually modified to use the Config node. If you re-import the JSON export, you must either (a) recreate the Config node and update the two HTTP nodes to use `$('Config').first().json.*` expressions, or (b) set the four env vars in your n8n environment if you have a commercial license.

### Verification: no secrets in export

After modifying the workflow, run this to check no real secrets remain:

```bash
# Check for any remaining production URLs or API key values
rg -n "onrender\.com|X-API-Key\"\s*:\s*\"[A-Za-z0-9]|apikey\"\s*:\s*\"[A-Za-z0-9]" "n8n/Trackpal WhatsApp Bot.json"
```

Expected: matches only for header *names*, not real secret *values*. The only `X-API-Key` or `apikey` values should be `{{$('Config').first().json.trackpal_n8n_api_key}}` and `{{$('Config').first().json.evolution_api_key}}` respectively (or `{{$env.*}}` equivalents).

## Phone number format

Evolution API sends phone numbers with `@c.us` or `@s.whatsapp.net` suffix. The workflow strips these. The Evolution API Send node also strips the `+` prefix before sending replies.

**Backend canonicalization**: The backend applies `PhoneNormalizer.normalize_phone()` on every incoming phone value. This removes `+`, all non-digits, WhatsApp JID suffixes, and device suffixes — producing a canonical digits-only string for identity lookup, Redis session keying, and database storage. The n8n workflow does not need to do full canonicalization beyond the basic suffix strip.

## Contextual meaning of `0` in the Master Console

The backend interprets command `0` differently based on context. This logic
is fully implemented in the backend's ``WhatsAppMasterConsoleFacade`` and
``WhatsAppConsoleService``. n8n is not involved in determining the meaning
of ``0`` — it only transports the message and relays the reply.

### Authenticated + at top-level (no active CRUD flow)

``0`` performs a **full logout** (see ``_perform_logout()`` in the facade):

1. Clears the Redis auth session (``wa:auth:{phone}``)
2. Clears the conversation session (``session:{phone}``)
3. Calls Evolution API ``POST /n8n/changeStatus/{instance}`` with payload
   ``{"remoteJid": "<digits>@s.whatsapp.net", "status": "closed"}``
   to mark the chat as closed for the active instance + contact
4. Returns a logout confirmation reply (``LOGOUT_CONFIRMATION``)

After logout, the user must write *menu* to log in again.

### Authenticated + inside a CRUD sub-flow (has an active conversation flow)

``0`` **cancels** the current operation:

1. Refreshes the auth session TTL (``touch_auth_session()``) so long-running
   CRUD flows don't expire the master session
2. Delegates the ``0`` message to ``WhatsAppConsoleService.process_message()``,
   which clears the conversation session and returns the main menu

The auth session **persists** — the user stays logged in. ``menu`` and
``cancelar`` also work here, but they go through the ``WhatsAppConsoleService``
RESET_COMMANDS path (which clears only the conversation session and returns the
main menu without touching the auth session).

### Unauthenticated (login flow)

``0``, *menu*, or *cancelar* resets the login flow:

1. Clears **both** the auth session (``wa:auth:{phone}``) and conversation
   session (``session:{phone}``) — a safety measure in case a stale session
   exists
2. Returns the username prompt (``USERNAME_PROMPT``)

### Summary table

| Context | ``0`` | ``menu`` / ``cancelar`` |
|---|---|---|
| Authenticated, top-level | Full logout — clears auth + conv sessions, calls Evolution API close | Clears conv session only, returns main menu (auth session stays) |
| Authenticated, sub-flow | Cancels flow — refreshes auth TTL, clears conv session, returns main menu | Same (console service handles RESET_COMMANDS) |
| Unauthenticated (login) | Clears both auth + conv sessions, returns to username prompt | Same |

## What changed from the legacy workflow

The pre-Phase-3 workflow included:
- **Identify user** (HTTP GET) — separate call to identify endpoint
- **Is Sublify?** (IF) — instance filtering
- **Route by role** (IF) — Master vs non-Master branching
- **Menu router** (Code) — multi-step menu state and CRUD logic
- **Is list action?** (IF) — action branching
- **List tenants API** (HTTP GET) — direct CRUD call
- **Format list response** (Code) — formatting tenant data
- **Access denied text** (Code) — denial message

All of these moved to the backend console endpoint in Phase 3. n8n now only transports messages and replies without interpreting product logic or owning session state.
