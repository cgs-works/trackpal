# WhatsApp Console Flow Architecture

Trackpal has two WhatsApp conversational consoles:
- **Master Console** for tenant lifecycle management
- **Tenant Console** for tenant admins to manage clients, catalog, profile, and subscriptions

Both use n8n + Evolution + backend relay and store conversation state in Redis.

## Message Flow

```
User WhatsApp
    ↓ (message)
Evolution
    ↓ (webhook)
n8n Workflow → POST /api/v1/integrations/n8n/console
    ↓
Trackpal Backend
    ↓
WhatsApp*ConsoleFacade.process_message()
    ↓
Redis Session State (WhatsAppSessionService / WhatsAppAuthSessionService)
    ↓
Console Service.process_message()
    ↓
Reply text → n8n → Evolution → User WhatsApp
```

## Master Console

### Orchestration — `WhatsAppMasterConsoleFacade`

Package: `backend/app/services/whatsapp_master_console_facade/`. Submodules: `facade.py`, `login_flow.py`, `constants.py`, `protocols.py`.

1. Lockout check via `wa:auth:lock:{phone}`.
2. Auth session check via `wa:auth:{phone}`.
3. If authenticated, delegates to `WhatsAppConsoleService.process_message()`.
4. If not authenticated, runs username/password login.

### Login flow

1. Username prompt.
2. Username validation and existence check.
3. Password prompt.
4. Authenticate via `AuthService.authenticate()`.
5. On success, create `WhatsAppAuthSession` in Redis.
6. On failure, track attempts and lock after 5 failures.

### Menu options

| # | Action | Description |
|---|--------|-------------|
| 1 | Ver Tenants | List tenants with status and counts |
| 2 | Crear Tenant | Create tenant + Evolution instance |
| 3 | Desactivar Tenant | Deactivate tenant |
| 4 | Eliminar Tenant | Delete inactive tenant |
| 5 | Ayuda | Show help |
| 0 | Cerrar sesión / Cancelar | Contextual exit or cancel |

## Client Console

Client WhatsApp console provides **read-only** access for clients registered under a tenant. Clients cannot perform mutations (no create/update/delete). This was added in 2026-05.

### Instance-first routing

The console endpoint now routes by **WhatsApp instance** before resolving identity:

1. Read `MASTER_WHATSAPP_INSTANCE` env var.
2. If `instance == MASTER_WHATSAPP_INSTANCE` → master flow only.
3. If instance belongs to a tenant → resolve tenant by `evolution_instance_name`.
4. Within tenant context:
   - Match `tenant.whatsapp_phone` → tenant admin flow.
   - Match `(tenant_id, phone)` in `clients` table → client flow.

### Ambiguity handling

If the same phone matches both `tenant.whatsapp_phone` and a `client` record within the same tenant:
- System **prompts** the user to choose mode: `1) Tenant` or `2) Cliente`.
- Selection is persisted in Redis at key `wa:mode:{phone}` for the current session.
- A confirmation message is sent indicating the chosen mode and that it stays until exit.
- When user exits (`0`, `salir`, or `/menu`), the mode key is cleared from Redis.

### Exit contract (`status="closed"`)

When a client exits the console (option `0` / `salir`), the response includes `status="closed"` in the payload. This triggers the n8n/Evolution Go `change-status` node to close the Evolution chat session. The `status` field is omitted (serialized as `None`) for all non-exit responses to maintain backward compatibility.

### Orchestration — `WhatsAppClientConsoleFacade`

Package: `backend/app/services/whatsapp_client_console_facade/`. Submodules: `facade.py`.

1. Client is resolved by `(tenant_id, phone)` — not by global phone lookup.
2. Validates both `tenant.is_active` and `client.is_active`.
3. Locale is resolved from parent tenant.
4. All replies use i18n keys under namespace `wa.client.*`.
5. Menu is read-only.

### Menu options

| # | Action | Description |
|---|--------|-------------|
| 1 | Mi Perfil | View client profile (name, tenant, phone, status) |
| 2 | Mis Suscripciones | View active subscriptions |
| 0 | Salir | Exit, returns `status="closed"` |

### i18n namespace

```
wa.client.main_menu
wa.client.profile.body          # params: full_name, tenant_name, phone, status
wa.client.subscriptions.header
wa.client.subscriptions.item    # params: num, service, plan, start, exp, status
wa.client.subscriptions.empty
wa.client.goodbye
wa.client.access_denied
wa.client.mode_prompt           # ambiguity resolution
wa.client.mode_confirm_client
wa.client.mode_confirm_tenant
wa.client.mode_exit
wa.client.mode_reset
```

### Split routing architecture

To keep file size under the 240 LoC limit, the console endpoint package was split:
- `console.py` — entry point, routing, dependency injection (~214 LoC)
- `console_handlers.py` — individual handler functions (~300 LoC)
- `console_modes.py` — ambiguity mode selection logic

## Tenant Console

### Orchestration — `WhatsAppTenantConsoleFacade`

Package: `backend/app/services/whatsapp_tenant_console_facade/`. Submodules: `facade.py`.

1. Resolve caller by phone. Within tenant context, first check `tenant.whatsapp_phone` (tenant admin), then fallback to client identity.
2. Verify tenant is active.
3. Resolve tenant context + locale (`tenant.locale`, persisted column).
4. On top-level `0`, clear `session:admin:{phone}` and exit.
5. Delegate to `WhatsAppTenantConsoleService.process_message()` with resolved `locale`.

### Locale Handling

- `WhatsAppTenantConsoleFacade` resolves `tenant.locale` from DB per message
- `WhatsAppTenantConsoleService` sets a module-level `_current_locale` ContextVar at `process_message()` entry, resets in `finally`
- All handler methods call `self._t(key, **params)` which reads `_current_locale.get()` automatically — avoids threading locale through 40+ methods
- Locale switch in profile section updates `Tenant.locale` in DB, then immediately sets ContextVar for fresh locale on next reply
- Missing keys fall back to English; warning logged at 1st, 10th, 100th, 1000th occurrence
- Master console stays hardcoded Spanish (out of i18n scope)

### Session model

Tenant console uses `WhatsAppSessionService` with logical key `admin:{phone}` so Redis key becomes `session:admin:{phone}`.

### Menu options

| # | Action | Description |
|---|--------|-------------|
| 1 | Clientes | List and manage clients |
| 2 | Catálogo | View and edit service/plan names |
| 3 | Mi Perfil | View/edit profile and password |
| 4 | Suscripciones | List and manage subscriptions |
| 5 | Ayuda | Show help |
| 0 | Salir / Cancelar | Contextual exit or cancel |

### Subscription flows

The subscription list flow supports interactive pagination with 7 items per page (reserving keys 8 and 9 for navigation and 0 for exit):

1. **Filter by status**: Tenant selects a status (Active / Expired / Cancelled / All)
2. **Paginated list**: Results shown in pages of 7, with per-command:
   - `0` — Cancel and return to tenant main menu
   - `8` — Previous page (hidden if page ≤ 1)
   - `9` — Next page (hidden if page ≥ total_pages)
3. **Subscription selection**: Tenant picks a subscription by number (1–7) to view details and available actions (edit, cancel, renew, reactivate)

Page state (`page`, `status_filter`) is stored in session `temp_data` and the per-page `selection_map` maps keys `1..7` to subscription IDs. Invalid page navigation returns a localized error without changing the current page.

Additional subscription management flows:

- Create subscription
- Edit subscription
- Cancel / reactivate / renew
- Reveal credentials

### Protocol definitions

Package: `backend/app/services/tenant_console_protocols/`. Submodules: `protocols.py`.

Defines `ClientServiceProtocol`, `CatalogServiceProtocol`, and `SubscriptionServiceProtocol` for DI and to avoid circular imports.

## Shared session behavior

- Master conversation state key: `session:{phone}`
- Tenant conversation state key: `session:admin:{phone}`
- TTL: 15 minutes
- `0` at top level exits; `0` inside active flow cancels
- Invalid input does not refresh TTL

## Contingency behavior

- No Redis configured -> temporary unavailable reply.
- Failover cache miss -> session reset reply with inline menu.
- Redis infrastructure error -> safe 200 response and temporary unavailable text.
