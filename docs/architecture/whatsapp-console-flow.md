# WhatsApp Master Console Flow Architecture

The WhatsApp Master Console is a conversational interface that lets a Master user manage tenants via WhatsApp messages, relayed through n8n and Evolution API.

## Message Flow

```
User WhatsApp
    ↓ (message)
Evolution API
    ↓ (webhook)
n8n Workflow → POST /api/v1/integrations/n8n/console
    ↓
Trackpal Backend
    ↓
WhatsAppMasterConsoleFacade.process_message()
    ↓
Redis Session State (WhatsAppSessionService / WhatsAppAuthSessionService)
    ↓
WhatsAppConsoleService.process_message()
    ↓
Reply text → n8n → Evolution API → User WhatsApp
```

## Orchestration — `WhatsAppMasterConsoleFacade`

The facade in `app/services/whatsapp_master_console_facade.py` orchestrates auth-gated access:

1. **Lockout check** — Check `wa:auth:lock:{phone}` key; returns lockout reply if locked
2. **Auth session check** — Check `wa:auth:{phone}` key for existing master auth session
3. **Authenticated path** — If authenticated, delegates to `WhatsAppConsoleService.process_message()` with `is_master=True`
4. **Login flow** — If not authenticated, runs conversational username/password login

### Contextual Logout

When an authenticated user sends "0":
- **Inside an active flow** → cancels the flow (no logout)
- **At top level** → performs full logout: clears auth session, clears conversation session, optionally calls Evolution API to close the chat session

### Login Flow Steps

1. Send username prompt
2. Receive username, validate existence via DB lookup, record failure if unknown
3. Send password prompt
4. Receive password, authenticate via `AuthService.authenticate()`
5. On success: create `WhatsAppAuthSession` in Redis, clear conversation session
6. On failure: record failed attempt, lock out after threshold (5 attempts, 5-minute lock)

## Session Services

### `WhatsAppSessionService` (conversation state)

Stores per-phone multi-step flow state as JSON under `session:{phone}` with configurable TTL (default 15 minutes).

Key fields on `ConversationSession`:
- `phone`, `flow`, `step`, `selected_tenant_id`
- `temp_data` — form data being collected across steps
- `selection_map` — maps displayed numbers to tenant UUIDs

TTL refresh policy: Only refreshes on session creation, valid step advance, or valid flow data update. Noise, invalid input, and fallback replies do NOT refresh TTL.

### `WhatsAppAuthSessionService` (auth + lockout)

Three Redis primitives:
- `wa:auth:{phone}` — Authenticated session with user metadata (TTL: session TTL, default 15 min)
- `wa:auth:fail:{phone}` — Consecutive failure counter with timestamps (TTL: failure window, default 15 min)
- `wa:auth:lock:{phone}` — Temporary lockout marker (TTL: lock duration, default 5 min)

No passwords are ever stored in Redis.

## Console Service — `WhatsAppConsoleService`

Handles conversation state transitions, menu routing, and CRUD decisions.

### Menu Options

| # | Action | Description |
|---|--------|-------------|
| 1 | Ver Tenants | Lists all tenants with status; user selects one for detail |
| 2 | Crear Tenant | Multi-step form: name, email, phone, username, Evolution instance, password |
| 3 | Desactivar Tenant | Starts deactivation flow requiring CONFIRMAR |
| 4 | Eliminar Tenant | Deletes inactive tenant with CONFIRMAR |
| 5 | Ayuda | Show help text |
| 0 | Cerrar sesión / Cancelar | Contextual: cancel flow or logout |

### Create Flow Steps

1. `full_name` → `email` → `phone` → `username` → `evolution_instance` → `password_mode` → (optional `manual_password`) → `confirm`
- All fields validated against centralized input validation policy
- Username checked for duplicates before advancing
- On creation failure, user is returned to the offending field

### Edit Flow

From tenant detail screen: select field to edit (full_name, email, phone, Evolution instance), enter new value, validated against input policy, persisted via `TenantService`.

### Lifecycle Flows

- **Deactivate**: Detail screen → option 2 → CONFIRMAR → deactivation + session revocation
- **Reactivate**: Detail screen (inactive) → option 2 → immediate reactivation
- **Delete**: Detail screen (inactive only) → option 3 → CONFIRMAR → deletion + Evolution instance cleanup

## Contingency Behavior

- **No Redis configured** → Returns `"Temporalmente no disponible"` (maintains HTTP 200)
- **Failover active + session missing** → Returns `SESSION_RESET` with inline menu, creates fresh session on backup
- **Redis infrastructure error** → Caught in endpoint, returns safe `TEMPORARY_UNAVAILABLE` reply
