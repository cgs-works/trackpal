# n8n WhatsApp Workflow

## Overview

Single n8n workflow that orchestrates the Master's interaction with Trackpal via WhatsApp.

- **Instance**: `https://rs-n8n.wilfredocamacho.dev`
- **Workflow**: `Trackpal WhatsApp Bot` (ID: `mN3k0vVO9kgBYQtV`)
- **Webhook**: `POST /webhook/trackpal-whatsapp-bot`
- **Workflow export**: `n8n/Trackpal WhatsApp Bot.json`

## Node flow

```
WhatsApp → Evolution API (n8n integration, keyword trigger: "/menu")
             ↓
       Webhook (1)
             ↓
       Parse input (2) [Code]
         → Extracts: phone, message, instance name
             ↓
       Is Sublify? (12) [IF]
         → Checks $json.instance === "Sublify"
         ├─ true → Continue to identify
         └─ false → Workflow ends silently
             ↓
       Identify user (3) [HTTP GET]
         → GET YOUR_TRACKPAL_API_URL/api/v1/integrations/n8n/identify?phone=
         → Header: X-API-Key
             ↓
       Merge identity (4) [Code]
         → Combines original input + identity data
         → Sets allowed = (role === "master")
             ↓
       Route by role (5) [IF]
         ├─ true (master) → Menu router (7) [Code]
         │    → Generates interactive menu or routes by step
         │    → Detects numeric menu options (1-8)
         │    → Manages multi-turn flows via session object
         │      ↓
         │   Is list action? (9) [IF]
         │    ├─ true → List tenants API (10) [HTTP GET]
         │    │           → Format list (11) [Code]
         │    │             ↓
         │    │       Evolution API Send (8)
         │    └─ false → Evolution API Send (8)
         └─ false → Access denied (6) [Code]
                      ↓
               Evolution API Send (8)
```

## Instance filtering

The workflow is restricted to the **"Sublify"** Evolution instance only. Messages from other instances (e.g., future tenant instances) are silently ignored — they will have their own workflows later.

```javascript
// Node "Is Sublify?" (IF)
condition: $json.instance === "Sublify"
```

## Menu options (Master)

| Option | Action | Description |
|---|---|---|
| 1 | Crear tenant | Multi-step: full_name → email → username → password choice → create |
| 2 | Listar tenants | GET /api/v1/tenants, returns formatted list |
| 3 | Ver tenant | Asks for tenant ID, then GET /tenants/{id} |
| 4 | Editar tenant | Asks for tenant ID, then edit fields |
| 5 | Desactivar tenant | PATCH /tenants/{id}/deactivate |
| 6 | Reactivar tenant | PATCH /tenants/{id}/activate |
| 7 | Eliminar tenant | DELETE /tenants/{id} (only if inactive) |
| 8 | Ayuda | Shows help text |

## Session management (multi-step flows)

Multi-step flows (create, edit) use a `session` object passed through the workflow JSON. The object contains:

```json
{
  "phone": "+521234567890",
  "step": "awaiting_full_name",
  "temp_data": "{}"
}
```

- On each message, the workflow checks the session step
- If no session exists, the user sees the main menu
- Session state is not persisted across workflow executions (stateless per webhook call)

## Configuration

To deploy this workflow, replace the placeholders in the JSON with your actual values:

| Placeholder | Description |
|---|---|
| `YOUR_TRACKPAL_API_URL` | Trackpal backend URL (e.g. `https://trackpal-backend.onrender.com`) |
| `YOUR_TRACKPAL_API_KEY` | N8N_API_KEY from backend config |
| `YOUR_EVOLUTION_API_URL` | Evolution API URL (e.g. `https://rs-evoapi.wilfredocamacho.dev`) |
| `YOUR_EVOLUTION_API_KEY` | Evolution API key |
| `YOUR_N8N_URL` | n8n instance URL |

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

## Phone number format

Evolution API sends phone numbers with `@c.us` or `@s.whatsapp.net` suffix. The workflow strips these. The Evolution API Send node also strips the `+` prefix before sending replies.
