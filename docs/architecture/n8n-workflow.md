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

- URL: `{{YOUR_TRACKPAL_API_URL}}/api/v1/integrations/n8n/console`
- Method: `POST`
- Headers: `X-API-Key`, `Content-Type: application/json`
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

- URL: `{{YOUR_EVOLUTION_API_URL}}/message/sendText/{{$json.instance}}`
- Method: `POST`
- Headers: `apikey`
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

## Configuration

To deploy this workflow, replace the placeholders in the JSON with your actual values:

| Placeholder | Description |
|---|---|
| `YOUR_TRACKPAL_API_URL` | Trackpal backend URL (e.g. `https://trackpal-backend.onrender.com`) |
| `YOUR_TRACKPAL_API_KEY` | N8N_API_KEY from backend config |
| `YOUR_EVOLUTION_API_URL` | Evolution API URL (e.g. `https://rs-evoapi.wilfredocamacho.dev`) |
| `YOUR_EVOLUTION_API_KEY` | Evolution API key |
| `YOUR_N8N_URL` | n8n instance URL |

## Phone number format

Evolution API sends phone numbers with `@c.us` or `@s.whatsapp.net` suffix. The workflow strips these. The Evolution API Send node also strips the `+` prefix before sending replies.

**Backend canonicalization**: The backend applies `PhoneNormalizer.normalize_phone()` on every incoming phone value. This removes `+`, all non-digits, WhatsApp JID suffixes, and device suffixes — producing a canonical digits-only string for identity lookup, Redis session keying, and database storage. The n8n workflow does not need to do full canonicalization beyond the basic suffix strip.

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
