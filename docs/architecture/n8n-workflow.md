# n8n Workflow Architecture

Trackpal uses two n8n workflows: the **WhatsApp Bot** bridges Evolution API webhooks with the backend WhatsApp consoles (Master + Tenant), and the **Subscription Reminders** scheduler handles daily expiry reminder dispatch. The workflow receives inbound messages, normalises them, calls the backend, and relays the reply back through Evolution API.

## WhatsApp Bot Workflow

### Workflow Overview

```
Evolution API (inbound message)
    |  webhook POST
n8n Webhook Node
    ↓
Parse Input (Code Node) — normalises phone, message, instance
    ↓
[Config (Set Node)] — supplies config vars from node fields
    ↓
Console Call (HTTP Request Node) — POST /api/v1/integrations/n8n/console
    ↓
Merge Reply (Code Node) — merges reply with original input
    ↓
Evolution API Send (HTTP Request Node) — POST /message/sendText/{instance}
    ↓
User WhatsApp receives reply
```

## Workflow File

**File**: `n8n/Trackpal WhatsApp Bot.json`

- **Name**: `Trackpal WhatsApp Bot`
- **Active**: `true`
- **n8n version**: Compatible with n8n v1.x (nodes use typeVersion 2.1–4.4)
- **Execution order**: `v1` (sequential)

## Nodes

### 1. Webhook

| Property | Value |
|----------|-------|
| Type | `n8n-nodes-base.webhook` (v2.1) |
| HTTP Method | POST |
| Path | `trackpal-whatsapp-bot` |
| Response Mode | `lastNode` (returns last node output to caller) |
| Webhook ID | `a9978bf7-c6b1-4abb-9e40-b375cb55eb60` |

Receives inbound WhatsApp messages forwarded by Evolution API.

The full webhook URL is:
`https://rs-n8n.wilfredocamacho.dev/webhook/trackpal-whatsapp-bot`

This URL is configured in `EvolutionClient.setup_n8n_integration()` in the backend, which registers it with Evolution API per-instance at tenant creation time. Evolution API only forwards messages that start with `/menu` (keyword trigger).

### 2. Parse Input (Code Node)

JavaScript code that normalises the raw Evolution API payload into a consistent `{ phone, message, instance }` structure.

**Input**: Raw webhook payload from Evolution API.

**Normalisation logic**:
- Extracts `body.chatInput`, `body.remoteJid`, `body.instanceName`
- Falls back to `data.message.from`, `data.message.key.remoteJid`, `data.message.body`, `data.message.conversation`
- Strips JID suffixes (`@c.us`, `@s.whatsapp.net`, etc.) and device suffixes (`:N`)
- Strips `+` prefix from phone numbers
- Defaults `instance` to `'default'` if not present

**Output**: `{ phone, message, instance, raw }`

### 3. Config (Set Node)

A **Set** node (typeVersion 3.4) that injects configuration values into the workflow as named fields. This is an n8n community-edition pattern that works around the missing "variables" UI for workflow-level config.

**Fields**:

| Name | Value | Purpose |
|------|-------|---------|
| `trackpal_backend_url` | `https://trackpal-backend.onrender.com` | Backend API base URL |
| `trackpal_n8n_api_key` | (set via n8n field) | Shared secret for X-API-Key header |
| `evolution_api_url` | `https://rs-evoapi.wilfredocamacho.dev` | Evolution API base URL |
| `evolution_api_key` | (set via n8n field) | API key for Evolution API |
| `default_instance` | `Sublify` | Fallback Evolution instance name |

The node is positioned off the main flow line (y=-272 vs y=-112). Its `includeOtherFields` setting preserves all upstream data and adds the config fields as top-level properties. Downstream nodes reference config values using `$('Config').first().json.<field_name>`.

### 4. Console Call (HTTP Request Node)

Calls the backend WhatsApp Master Console endpoint.

| Property | Value |
|----------|-------|
| Type | `n8n-nodes-base.httpRequest` (v4.4) |
| Method | POST |
| URL | `{{ $('Config').first().json.trackpal_backend_url }}/api/v1/integrations/n8n/console` |
| Headers | `X-API-Key: {{ $('Config').first().json.trackpal_n8n_api_key }}` |
| Body | `{"phone": "...", "message": "...", "instance": "..."}` |
| Never Error | `true` (backend errors return safe replies, never 5xx) |

**Response handling**: `neverError: true` ensures any HTTP status is treated as a regular response. The backend always returns HTTP 200 with a `reply` field.

### 5. Merge Reply (Code Node)

Small JavaScript that takes the backend response and merges it with the parsed input.

**Logic**: If `$json.reply` is a non-empty string, use it; otherwise return the fallback Spanish message `"Servicio temporalmente no disponible. Intenta nuevamente."`

**Output**: Spread of original `{ phone, message, instance }` plus `{ reply }`.

### 6. Evolution API Send (HTTP Request Node)

Sends the reply text back to the user via Evolution API.

| Property | Value |
|----------|-------|
| Type | `n8n-nodes-base.httpRequest` (v4.4) |
| Method | POST |
| URL | `{{ $('Config').first().json.evolution_api_url }}/message/sendText/{{ instance or default_instance }}` |
| Headers | `apikey: {{ $('Config').first().json.evolution_api_key }}` |
| Body | `{"number": "phone_without_plus", "text": "reply_text"}` |
| Never Error | `true` |

## Data Flow Detail

```
Evolution webhook payload
  ↓
Parse Input:
  const phone = normalizePhone(remoteJid || from)
  const message = chatInput || msg.body || conversation
  const instance = instanceName || data.instance || 'default'
  ↓
{ phone: "1234567890", message: "1", instance: "Sublify" }
  ↓
Config node adds: { trackpal_backend_url, trackpal_n8n_api_key, evolution_api_url, evolution_api_key, default_instance }
  ↓
Console Call → POST /api/v1/integrations/n8n/console
  → Backend processes, returns { reply: "📋 *Lista de Tenants*\n..." }
  ↓
Merge Reply:
  { phone, message, instance, reply: "📋 *Lista de Tenants*\n..." }
  ↓
Evolution API Send → POST /message/sendText/Sublify
  → Body: { number: "1234567890", text: "📋 *Lista de Tenants*\n..." }
  → User receives the WhatsApp message
```

## Configuration Pattern (n8n Community Edition)

The Config Set node is a common workaround in n8n community edition (which lacks the "Variables" UI from the pro/cloud edition). All environment-specific values are collated in one node for easy editing:

- **Backend URL** — change when deploying to different environments (staging, production)
- **API keys** — set in the node, stored in the workflow JSON (note: values are visible in the exported JSON)
- **Default instance** — fallback when no instance is provided in the webhook payload

To update config values:
1. Open the n8n editor
2. Select the Config node
3. Edit the field values
4. Save the workflow

## Integration with Backend

The workflow communicates with two backend services:

1. **Trackpal Backend** (`POST /api/v1/integrations/n8n/console`):
   - Authenticated via `X-API-Key` header matching `settings.n8n_api_key`
   - Request body: `WhatsAppConsoleRequest` schema (phone, message, optional instance)
   - Response body: `WhatsAppConsoleResponse` schema (reply text)
   - See [API Layer](api-layer.md) and [WhatsApp Console Flow](whatsapp-console-flow.md)

2. **Evolution API** (`POST /message/sendText/{instance}`):
   - Authenticated via `apikey` header
   - Sends the reply text back to the WhatsApp user
   - See [Evolution Integration](evolution-integration.md)

## Error Handling

- **Backend unavailable**: The Console Call node has `neverError: true`, so the workflow continues even on non-2xx responses
- **Empty reply**: Merge Reply falls back to a static Spanish unavailability message
- **I18n scope**: n8n is pure transport — it never generates, owns, or translates strings. All user-facing messages in both WhatsApp Bot and Reminder workflows are rendered by the backend using `t()`, with tenant locale resolved server-side. n8n passes reply text verbatim to Evolution API.
- **Evolution API errors**: The Send node also has `neverError: true` to prevent workflow failures from propagating
- **n8n-level errors**: If any node throws an unhandled error, n8n marks the execution as "Error" and the user does not receive a reply


---

## Subscription Reminders Workflow

**File**: `n8n/Trackpal Subscription Reminders.json`

**Name**: `Trackpal Subscription Reminders`
**Active**: `true`
**Total nodes**: 11
**Execution order**: v1 (sequential)

A scheduled workflow that runs daily at 09:00 (server time) to fetch pending subscription reminders and send them via Evolution API.

### Workflow Overview

```
Schedule Trigger (09:00 daily)
    |
    v
Config (Set Node) -- backend URL, API keys, page limit 100, delay 2s
    |
    v
Fetch Pending Reminders (HTTP Request) -- POST /api/v1/subscriptions/reminders/pending
    |
    v
Transform Items (Code Node) -- extract items array from response
    |
    v
SplitInBatches (loop, batch size 1)
    |  (loop back arrow from end)
    v
Wait (2s delay)
    |
    v
Evolution API Send (HTTP Request) -- POST /message/sendText/{instance}
    |
    v
Evaluate Result (Code Node) -- check response status
    |
    v
Route by Success? (IF node)
    |         |
    v         v
Mark Sent    Mark Failed
(HTTP)       (HTTP)
```

### Nodes

| # | Node | Type | Purpose |
|---|------|------|---------|
| 1 | Schedule Trigger | n8n-nodes-base.scheduleTrigger | Daily trigger at 09:00 |
| 2 | Config | n8n-nodes-base.set | Config vars: backend URL, API keys, evolution URL, page limit, delay |
| 3 | Fetch Pending Reminders | n8n-nodes-base.httpRequest | POST /api/v1/subscriptions/reminders/pending with cursor pagination |
| 4 | Transform Items | n8n-nodes-base.code | Extract items array, add instance field |
| 5 | SplitInBatches | n8n-nodes-base.splitInBatches | Loop over reminders one at a time |
| 6 | Wait | n8n-nodes-base.wait | 2-second delay between sends |
| 7 | Evolution API Send | n8n-nodes-base.httpRequest | POST /message/sendText/{instance} with Spanish reminder text |
| 8 | Evaluate Result | n8n-nodes-base.code | Check response status, prepare metadata |
| 9 | Route by Success? | n8n-nodes-base.if | Split by success/failure |
| 10 | Mark Sent | n8n-nodes-base.httpRequest | POST /api/v1/subscriptions/reminders/{log_id}/mark-sent |
| 11 | Mark Failed | n8n-nodes-base.httpRequest | POST /api/v1/subscriptions/reminders/{log_id}/mark-failed |

### Endpoints Used

| Endpoint | Method | Auth |
|----------|--------|------|
| POST /api/v1/subscriptions/reminders/pending | X-API-Key | Cursor-paginated, max 100 per request |
| POST /api/v1/subscriptions/reminders/{log_id}/mark-sent | X-API-Key | Sets status=sent, sent_at=now |
| POST /api/v1/subscriptions/reminders/{log_id}/mark-failed | X-API-Key | Increments attempt, permanent fail after 3 |
| POST /api/v1/subscriptions/jobs | X-API-Key | Manual trigger: cleanup, reminders, or all |
