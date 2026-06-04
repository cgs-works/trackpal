# WhatsApp Console Flow Architecture

Trackpal has three WhatsApp conversational consoles:
- **Master Console** for tenant lifecycle management
- **Tenant Console** for tenant admins to manage clients, catalog, profile, and subscriptions
- **Client Console** (read-only) for tenant clients

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
| 0 | Cerrar sesión | Global exit |

## Client Console

Client WhatsApp console provides **read-only** access for clients registered under a tenant. Clients cannot perform mutations (no create/update/delete). This was added in 2026-05.

### Instance-first routing

The console endpoint now routes by **WhatsApp instance** before resolving identity:

1. Read `MASTER_WHATSAPP_INSTANCE` env var.
2. If `instance == MASTER_WHATSAPP_INSTANCE` → master flow only.
3. If instance belongs to a tenant → resolve tenant by `evolution_instance_name`.
4. Within tenant context:
   - If ``from_me=true`` → route via ``_handle_from_me_routing`` (see below).
   - Match `tenant.whatsapp_phone` (or `tenant.whatsapp_lid`) → tenant admin flow (after checking active Client Context Shortcut).
   - Match `(tenant_id, phone)` or `(tenant_id, whatsapp_lid)` in `clients` → client flow.
   - Unregistered identity → check for active unauthenticated code lookup session, check Client Messaging Blocks, route to code lookup for ``codigo``/``código``/``code``, or return ``not_registered`` message with ``status="closed"`` and ``close_jid`` (tells unregistered contacts to send ``code``/``código`` for access codes and closes their Evolution session).

### LID-aware identity path

When Evolution sends `@lid` identifiers:
- n8n forwards `sender_lid` and avoids deriving `phone` from LID digits.
- Backend resolves identity phone-first, then falls back to `whatsapp_lid`.
- Progressive fill: when both `phone` and `sender_lid` arrive, backend stores `whatsapp_lid` in matched Master/Tenant/Client rows for future LID-only resolution.

### Ambiguity handling

If the same phone matches both `tenant.whatsapp_phone` and a `client` record within the same tenant:
- System **prompts** the user to choose mode: `1) Tenant` or `2) Cliente`.
- Selection is persisted in Redis at key `wa:mode:{phone}` for the current session.
- Special shortcut: messages `codigo|código|code` skip ambiguity prompt and route directly to tenant `codigo` flow.
- When a dual-role user sends a cancel command (``0``, ``salir``, ``cancelar``), the ambiguity handler clears both sessions, the stored mode, and returns ``wa.client.mode_exit`` with ``status="closed"`` and ``close_jid`` set.
- When user exits through tenant console (``0``), the response includes ``status="closed"`` and ``close_jid`` (canonical phone JID), so n8n closes the correct Evolution session.

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
| 0 | Cancelar | Exit, returns `status="closed"` |

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

## Request/Response Contract

### `WhatsAppConsoleRequest` — Inbound payload

The request schema has been extended to support contextual routing and private administrative responses.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `phone` | string | yes | Normalised phone number of the WhatsApp user |
| `message` | string | yes | Text of the WhatsApp message |
| `instance` | string | no | Evolution API instance name for tenant resolution |
| `sender_lid` | string | no | LID JID string when ``remoteJid`` uses ``@lid`` and no phone JID is resolvable |
| `from_me` | boolean | no | ``true`` when the message was sent by the admin from their own chat (outgoing trigger) |
| `admin_phone` | string | no | Phone number of the admin who sent the outgoing trigger |
| `admin_jid` | string | no | JID of the admin who sent the outgoing trigger; used as ``reply_to`` for contextual replies |
| `target_jid` | string | no | JID the admin selected as the shortcut target (the client or unregistered contact) |
| `target_phone` | string | no | Phone number of the shortcut target (never derived from a ``@lid`` value) |
| `target_lid` | string | no | LID JID of the shortcut target, when only identified via ``@lid`` |

### `WhatsAppConsoleResponse` — Outbound payload

The response schema now includes fields for private routing and silent replies.

| Field | Type | Always present | Description |
|-------|------|----------------|-------------|
| `reply` | string | yes | Plain text reply that n8n relays to the user |
| `status` | string | no | Optional status signal (e.g. ``"closed"`` on exit). Only serialised when non-``None`` |
| `lookup_job_id` | string | no | Job id for code lookup polling. When present, n8n sends ``reply``, then polls |
| `tenant_id` | string | no | Tenant UUID for scoped poll requests |
| `reply_to` | string | no | JID used as the message destination. When present, n8n sends to this JID instead of ``phone`` |
| `close_jid` | string | no | Exact JID n8n must close when ``status="closed"``. Context shortcut close uses the Tenant admin private JID to avoid closing the target/client chat |
| `close_jids` | list[str] | no | When present, list of ALL Evolution sessions to close (admin JID + target JID + target phone JID). Supersedes ``close_jid`` for multi-session closure |
| `no_reply` | boolean | no | ``true`` means n8n must not send any Evolution API message. Used for silent admin replies or blocked attempts |

When ``no_reply=true``, n8n must skip all Evolution sends entirely (no call to ``/send/text``). When ``reply_to`` is present, n8n sends to that JID rather than the original sender's phone.

## Split routing architecture

To keep endpoint modules maintainable and within team size policy, the console endpoint package was split:
- `console.py` — entry point, routing, dependency injection, and ``_route_by_instance`` logic (~280 LoC)
- `console_handlers.py` — individual handler functions for master/tenant/client flow, unauthenticated code lookup, and Client Context Shortcut orchestration (~900 LoC)
- `console_modes.py` — ambiguity mode selection logic
- `console_context_shortcut.py` — Client Context Shortcut creation flow and active/inactive client menu handlers (~550 LoC)

## From-me Contextual Routing

When ``from_me=true`` in the request, the message was sent by an admin from their own WhatsApp chat (outgoing shortcut trigger). The backend routes these through ``_handle_from_me_routing()`` before the regular identity checks:

1. **Resolve admin identity**: Use ``admin_phone`` if provided, otherwise fall back to ``tenant.whatsapp_phone`` (instance owner).
2. **Determine target identity**: Normalise ``target_phone`` if available.
3. **Self-target check**: If the target (phone or JID) matches the admin's own identity, route to the standard Tenant console.
4. **Active context collision**: If a context session already exists at ``wa:client_ctx:{admin_phone}``, reject with ``no_reply=true`` and ``reply_to=<admin_jid>`` (keeps the rejection private), except ``0``/``salir``/``cerrar`` which close the active context.
5. **Shortcut gate**: Only ``/menu``/``menu`` creates a Client Context Shortcut for a non-self target. Other non-self messages, including ``code``/``codigo``/``código``, return ``no_reply=true`` and do not create context.
6. **Create context session**: Store a ``ConversationSession`` under ``wa:client_ctx:{admin_phone}`` with 5-minute TTL, setting step to ``menu`` and persisting ``target_phone``, ``target_lid``, ``target_jid``, and ``admin_jid`` in ``temp_data``.
7. **Return contextual response**: Reply with the context initiation message and ``reply_to=admin_jid`` so n8n sends the reply privately to the admin chat.

## Unauthenticated Code Lookup

Unregistered WhatsApp identities in a known tenant instance can access a limited code-retrieval dialog without authenticating:

1. Messages ``codigo``, ``código``, or ``code`` trigger the flow.
2. Backend checks for Client Messaging Blocks first — blocked identities receive ``no_reply=true``.
3. Redis lookup is guarded: if the context/session cache is unavailable, the handler falls back safely instead of failing the webhook.
4. Session stored under ``session:unreg:{tenant-prefix}:{phone}`` or ``session:unreg:{tenant-prefix}:{lid}`` for the multi-step dialog.
5. Registered clients with an active unauthenticated codigo session resume that session before the read-only Client Console, so ``0`` cancels codigo rather than exiting the Client Console.
6. Service list uses ``[N]`` bracket format (``[1] Service``, ``[2] Service``...) with emoji pagination (``8️⃣`` next, ``9️⃣`` previous, ``0️⃣`` cancel). Up to 7 services per page.
7. Steps: service selection → email input → create ``MailLookupJob`` → enqueue → return ``lookup_job_id`` + ``tenant_id``. Session transitions to ``awaiting_result`` step after job creation.
8. n8n polls the job and sends the final result. On ``not_found``, the message includes options: ``1 Retry / 2 Back to services / 0 Cancel`` (localised in ES/EN).
9. Post-result options handled by ``_handle_unauth_codigo_result``: ``1`` creates new job, ``2`` shows service list, ``0`` closes session.
10. ``0``/cancel at any step clears the Redis session and returns ``status="closed"`` with phone-based ``reply_to``/``close_jid`` when the phone is known, so Evolution Go closes the correct chat session.
11. Non-codigo messages from unregistered identities return the ``not_registered`` message (``"No tienes una cuenta registrada. Envia 'code' o 'codigo' para buscar codigos de acceso."``) with ``status="closed"`` and ``close_jid``, telling them how to access codes and closing their session.

## Client Context Shortcut

The Client Context Shortcut is a private admin flow triggered via ``from_me=true`` when an admin selects a non-self target from their WhatsApp chat. It provides contextual management without leaving the chat.

### Session lifecycle

- Session key: ``wa:client_ctx:{admin_phone}``
- TTL: 5 minutes (only refreshed on valid input)
- Invalid input does not refresh TTL
- ``0`` closes the context at any depth
- Context is checked before routing to Tenant console when the admin is the active sender

### Target resolution

When an admin enters the shortcut, the backend resolves the target identity:

| Target type | Behaviour |
|-------------|-----------|
| Unregistered, unblocked | Shows menu: ``1 Crear cliente``, ``2 Bloquear mensajes``, ``0 Cancelar`` |
| Unregistered, blocked | Shows menu: ``1 Desbloquear mensajes``, ``0 Cancelar`` |
| Existing active Client | Shows active client menu with subscription shortcut; later messages preserve detail/edit/deactivate steps |
| Existing inactive Client | Shows inactive client management menu; later messages preserve edit/delete steps |

### Creating flow (unregistered targets)

Multi-step client creation with phone skip or LID-only phone prompt:
1. ``target_phone`` exists → prefill phone, prompt for name → username → password → confirm.
2. Only ``target_lid`` exists → prompt for phone first → then proceed as above.
3. ``0`` at any step cancels creation and clears context.
4. On successful creation, matching Client Messaging Blocks are cleared automatically.
5. After an action completes (block/unblock/create/deactivate/reactivate/edit/delete), the context is **kept alive** (``save_ctx`` instead of ``clear_ctx``) so a subsequent ``0`` from the admin is caught by the universal cancel handler, which correctly closes all sessions (admin + target + phone JID) instead of falling through to the Tenant console which only closes the admin's session.

### Active client menu

| Option | Action |
|--------|--------|
| 1 | View client detail (name, username, phone, status). Submenu: 1 Edit data, 2 Deactivate, 0 Back |
| 2 | Create subscription with client pre-selected (skips client selection in Tenant console) |
| 0 | Close context (closes admin + target + phone JID sessions) |

Phone editing is disabled from the shortcut. Edit supports ``full_name`` and ``local_username`` only.

### Inactive client menu

| Option | Action |
|--------|--------|
| 1 | Reactivate client |
| 2 | Edit data (same fields as active, no phone) |
| 3 | Delete client permanently (with CONFIRMAR prompt) |
| 0 | Close context (closes admin + target + phone JID sessions) |

Inactive clients cannot be duplicated by contextual creation (they count as existing identities). The subscription shortcut is hidden until reactivation.

## Blocked Clients

Blocked Clients prevent unregistered WhatsApp identities from using the console, codes, profile, or subscriptions. They are stored in a dedicated tenant-scoped table (``blocked_clients``, renamed from ``client_messaging_blocks``) rather than on the ``Client`` model because blocks apply only to identities that are not registered as clients.

### Storage

- Table: ``blocked_clients``
- At least one identity field required (``phone`` or ``whatsapp_lid``)
- ``is_active`` boolean for soft-delete
- Tenant-scoped indexes on ``(tenant_id, phone)`` and ``(tenant_id, whatsapp_lid)``
- Created in migration ``ce10fe74caa10``, renamed in ``ce10fe74caa11``

### Repository operations (``blocked_clients_repository.py``)

| Operation | Description |
|-----------|-------------|
| ``create(db, tenant_id, phone=, whatsapp_lid=)`` | Create an active block |
| ``list_active(db, tenant_id)`` | List active blocks, newest first |
| ``find_active(db, tenant_id, phone=, whatsapp_lid=)`` | Find an active block by identity; matches by either identifier when both are provided |
| ``unblock(db, tenant_id, block_id)`` | Soft-delete a specific block (sets ``is_active=False``) |
| ``clear_identity(db, tenant_id, phone=, whatsapp_lid=)`` | Deactivate all blocks for an identity; matches by either identifier when both are provided |

### Block enforcement

- Blocked unregistered identities receive ``no_reply=true`` for all messages (``codigo``, ``/menu``, or any other attempt).
- n8n must not send any message when ``no_reply=true``, keeping the block silent from the user's perspective.
- Blocks are created immediately without confirmation (from the Context Shortcut).
- Blocked targets can be unblocked from the Context Shortcut or from the Tenant console Clients menu.
- When a Client is successfully created for a blocked identity, blocks are cleared automatically.

### Tenant console management

The Clients menu in the Tenant console has been updated:

| Option | Action |
|--------|--------|
| 1 | Ver clientes (list clients) |
| 2 | Crear cliente (create client) |
| 3 | Bloqueos de mensajes (list and unblock identities) |
| 9 | Volver al menú principal (back to main menu) |

Option ``3`` lists active Client Messaging Blocks. Selecting a block offers to unblock it. ``9`` returns to the main tenant menu. ``0`` is global exit, not submenu back.

## Tenant Console

### Código lookup flow (`codigo|código|code`)

Tenant console has a dedicated code-retrieval dialog. Two independent code paths exist — self-target (tenant admin sends ``code`` to their own number) and client-sent (a registered/unregistered client sends ``code`` to the tenant's number). Both use the same session model but different handler modules.

#### Tenant self-target flow

1. Trigger by exact message ``codigo``, ``código``, or ``code``.
2. Backend shows a **paginated service list** with ``[N]`` bracket format for services (page-relative ``[1]`` to ``[7]``). Navigation uses emoji keycaps: ``8️⃣`` next page, ``9️⃣`` previous page, ``0️⃣`` cancel. A blank line separates services from navigation options. Up to 7 services per page (``PAGE_SIZE=7``).
3. Backend asks for target email.
4. Backend stores lookup intent in session (``service_key``, ``target_email``, ``pending_lookup_intent``). **Session is kept alive** (``flow=codigo``, ``step=awaiting_result``) instead of clearing flow state.
5. Integration handler (``_handle_tenant_console``) creates the job, commits it, enqueues to Redis, then: pops ``pending_lookup_intent``, **keeps** ``service_key`` and ``target_email`` for potential retry, and stores ``lookup_job_id`` in session temp_data.
6. Session remains in ``awaiting_result`` step. When n8n delivers the result notification (e.g. "Code not found"), the user's reply routes back to the awaiting_result handler.

#### Post-result response (``awaiting_result`` step)

| User input | Behavior |
|------------|----------|
| ``1`` | **Retry** — re-set ``pending_lookup_intent`` with same service_key/target_email. Backend creates a new lookup job. Returns "buscando...". |
| ``2`` | **Back to services** — clear session, show codigo service list again (page 0). |
| ``0`` | **Cancel** — clear session, return goodbye, n8n closes Evolution session. |
| Other | **Still checking** — keep session alive, return "Still searching..." with retry/back/cancel options. |

#### Client-sent code flow (unauth codigo)

1. Trigger by ``codigo``, ``código``, or ``code`` from a registered or unregistered client.
2. Backend shows the same **paginated service list** with ``[N]`` bracket format and emoji navigation (``8️⃣``/``9️⃣``/``0️⃣``), built by ``_build_unauth_service_page`` in ``console_handlers.py``.
3. Service selection and email input follow the same pattern as the tenant self-target flow.
4. Job creation happens **directly** in ``_handle_unauth_codigo_email`` (not delegated to the integration handler). Session transitions to ``awaiting_result`` step.
5. When the user replies to the result notification, ``_handle_unauth_codigo_result`` handles: ``1`` Retry, ``2`` Back to services, ``0`` Cancel.

#### n8n behavior for this path

- Sends immediate "buscando..."
- Polls every 4s up to 20s on ``GET /api/v1/integrations/n8n/mail/lookups/{job_id}?tenant_id=...``
- Sends final result with options appended on ``not_found``:
  - English: ``1️⃣ Retry / 2️⃣ Back to services / 0️⃣ Cancel``
  - Spanish: ``1️⃣ Reintentar / 2️⃣ Volver a servicios / 0️⃣ Cancelar``
- If user picks ``1`` (Retry), backend creates a new job and the poll cycle repeats.

#### Failure contract for orchestration

- If enqueue fails after commit, backend runs compensating delete of created job.
- If compensating delete fails, backend marks job ``failed`` with ``error_code=queue_unavailable`` and logs critical.
- In both failure branches, response must not include ``lookup_job_id``.


### Orchestration — `WhatsAppTenantConsoleFacade`

Package: `backend/app/services/whatsapp_tenant_console_facade/`. Submodules: `facade.py`.

1. Resolve caller by phone. Within tenant context, first check `tenant.whatsapp_phone` (tenant admin), then fallback to client identity.
2. Verify tenant is active.
3. Resolve tenant context + locale (`tenant.locale`, persisted column).
4. On top-level ``0`` (no active flow), clear ``session:admin:{phone}`` and exit with ``status="closed"`` and ``close_jid`` set to the canonical phone JID (e.g. ``584243106642@s.whatsapp.net``). This ensures n8n sends the phone-based JID (not a LID) to Evolution Go's ``/webhook/change-status`` endpoint.
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
| 2 | Catálogo | Service/plan CRUD. Starts with Catalog menu, supports service/plan list pagination (`8` next, `9` back, `0` close), direct create/edit, and destructive delete warnings requiring `CONFIRMAR`/`CONFIRM`. |
| 3 | Mi Perfil | View/edit profile and password |
| 4 | Suscripciones | List and manage subscriptions |
| 5 | Ayuda | Show help |
| 0 | Cancelar | Sale de la consola y cierra sesion |
| 9 | Volver | Regresa al menu anterior en flujos interactivos |
| 8 | Siguiente | Avanza a la siguiente pagina cuando hay paginacion |

Catalog delete warnings list active subscriptions ordered by expiration date and state that historical/non-active subscriptions are also deleted. `0` in Catalog closes the WhatsApp session and relies on the endpoint response contract (`status="closed"`, `close_jid`) for Evolution/n8n session closure.

### Subscription flows

The subscription list flow supports interactive pagination with 7 items per page (reserving keys 8 and 9 for navigation and 0 for exit):

1. **Filter by status**: Tenant selects a status (Active / Expired / Cancelled / All)
2. **Paginated list**: Results shown in pages of 7, with per-command:
   - `0` — Global exit
   - `8` — Next page (hidden if page ≥ total_pages)
   - `9` — Previous page/back (hidden if page ≤ 1)
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

## Global WhatsApp Navigation Contract

All WhatsApp console flows use the same strict numeric navigation contract:

| Key | Action | Description |
|-----|--------|-------------|
| `8` | Siguiente / Next | Advance to the next page or interactive screen when available |
| `9` | Regresar / Back | Return to the previous screen without cancelling the whole session |
| `0` | Cancelar / Cancel | Cancel the active flow or close the console from a main menu |

This contract applies to every console family:
- **Master Console** — tenant create/edit/list/detail/lifecycle
- **Tenant Admin Console** — clients, catalog, profile, subscriptions, access-code lookup
- **Client Console** — profile view, subscriptions lookup
- **Client Context Shortcut** — quick client management from WhatsApp
- **Ambiguity Mode** — role selection when a user has both admin and client profiles
- **Unauthenticated code lookup** — access-code lookup without login

The contract is enforced by:
- A shared `whatsapp_navigation.py` module with helper predicates (`is_cancel`, `is_back`, `is_next`) and a screen-stack API (`push_screen`, `pop_screen`, `replace_screen`, `clear_navigation`).
- Contract tests (`test_whatsapp_console_navigation_contract.py`) that scan all source and catalog files for conflicting numeric navigation patterns.
- Shared i18n labels under the `wa.nav.*` prefix in both English and Spanish catalogs.

## Shared session behavior

- Master conversation state key: `session:{phone}`
- Tenant conversation state key: `session:admin:{phone}`
- Client Context Shortcut key: `wa:client_ctx:{admin_phone}` (5-minute TTL)
- Unauthenticated code lookup key: `session:unreg:{phone}` or `session:unreg:{lid}` (standard session TTL)
- TTL: 5 minutes for all sessions (aligned with Evolution Go's 5-minute auto-close timeout)
- `0` is global exit across top-level and active flows; `9` goes back without cancelling; `8` advances to next screen when offered
- Invalid input does not refresh TTL
- Only valid contextual messages refresh contextual TTL

## Contingency behavior

- No Redis configured -> temporary unavailable reply.
- Failover cache miss -> session reset reply with inline menu.
- Redis infrastructure error -> safe 200 response and temporary unavailable text.
