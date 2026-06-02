# Ralph Progress

## Iteration 1 — 2026-06-01 21:49

### Selected Item
Item 1: Extend the backend WhatsApp console API contract for contextual routing and silent responses.

### Why this item was chosen
Per prioritization strategy: public schemas first as they unblock later routing, session, facade, and n8n items. Item 1 adds the request/response fields without modifying any routing behavior.

### Changed files
- `backend/app/schemas/whatsapp.py` — Added `from_me`, `admin_phone`, `admin_jid`, `target_jid`, `target_phone`, `target_lid` to `WhatsAppConsoleRequest`. Added `reply_to`, `no_reply` to `WhatsAppConsoleResponse` with conditional serialization.
- `backend/tests/test_whatsapp_endpoint.py` — Added 5 tests proving new fields accepted, legacy backward compatibility, and conditional response serialization.

### Verification commands and results
1. `cd backend && uv run pytest -n 8 --dist loadscope --no-header -q --tb=short -p no:cacheprovider` — 1101 passed, 1 skipped in 29s ✓
2. `cd frontend && npm run build` — Build successful ✓
3. `python -c "import json; json.load(open('../n8n/Trackpal WhatsApp Bot.json', encoding='utf-8')); print('valid')"` — Valid JSON ✓

### Fix applied
Sequential pytest took ~165s, exceeding the harness timeout. Installed `pytest-xdist` and switched to
parallel execution with `-n auto --dist loadscope` (keeps per-file tests on same worker to avoid
SQLite shared-state races), reducing runtime to ~33s. The verification gate command was updated
in `.ralph/items.json` accordingly. Further refined to `-n 8 --no-header -q` to minimize
output piping overhead, achieving ~29s runtime.

Also replaced `python -m json.tool` (which pretty-prints the entire 21K file to stdout,
overflowing the harness pipe buffer) with a silent Python one-liner that just validates
and prints "valid".

Restored original Spanish accents (`código`, `menú`) in item 3 and 7 descriptions
that were lost during a full-file JSON rewrite.

### Next-iteration notes
Item 2 (Client Messaging Block persistence) is the next dependency. The request/response contract is now ready for routing and block enforcement.

## Iteration 2 — 2026-06-01 22:46

### Selected Item
Item 2: Add persistent Client Messaging Block storage and service behavior for unregistered WhatsApp identities.

### Why this item was chosen
Per prioritization strategy: persistence before routing/session/facade. Item 1 (schemas) completed the public contract. Item 2 adds the storage layer that blocks — and the downstream clear-on-creation hook — unblocks Items 3 (code lookup enforcement), 5 (shortcut block/unblock), 7 (console block management), and 9 (documentation).

### Changed files
- `backend/app/models/client_messaging_block.py` — New model: `ClientMessagingBlock` with tenant_id, phone, whatsapp_lid, is_active, timestamps. Tenant-scoped indexes on (tenant_id, phone) and (tenant_id, whatsapp_lid).
- `backend/app/models/__init__.py` — Registered `ClientMessagingBlock` export.
- `backend/alembic/versions/ce10fe74caa10_add_client_messaging_blocks_table.py` — Alembic migration creating the `client_messaging_blocks` table with indexes.
- `backend/app/repositories/client_messaging_block_repository.py` — Repository with `create`, `list_active`, `find_active`, `unblock`, `clear_identity` functions. Enforces at-least-one-identity-field invariant via ValueError.
- `backend/tests/test_client_messaging_block_repository.py` — 32 tests covering create (phone/LID/both/identity-required), find_active (by phone/LID/none/unblocked), tenant isolation (4 cross-tenant scenarios), list_active (empty/only-active/ordering), unblock (active/already/nonexistent), clear_identity (phone/LID/all-matching/no-args/no-match/idempotent), persistence (across sessions/until-unblocked/in-list/recreate-after-clear), and Client-creation clear integration.

### Verification commands and results
1. `cd backend && uv run pytest -n 8 --dist loadscope --no-header -q --tb=short -p no:cacheprovider` — 1133 passed, 1 skipped in ~28s ✓
2. `cd frontend && npm run build` — Build successful ✓
3. `cd backend && python -c "import json; json.load(open('../n8n/Trackpal WhatsApp Bot.json', encoding='utf-8')); print('valid')"` — Valid JSON ✓

### Next-iteration notes
Item 3 (unauthenticated code lookup with block enforcement) is the next dependency. The persistence layer now supports is-blocked checks and clear-on-Client-creation, which Item 3 needs for blocked codigo/código/code detection and silent replies.

## Iteration 3 — 2026-06-01 23:41

### Selected Item
Item 3: Implement unauthenticated client-side code lookup for unregistered identities with Client Messaging Block enforcement.

### Why this item was chosen
Per prioritization strategy: the persistence layer (Item 2) is complete; Item 3 is the next dependency that uses it — it enables code lookup for unregistered identities and enforces blocks. This unblocks Items 4 (contextual routing), 5 (shortcut session lifecycle), and 9 (documentation).

### Changed files
- `backend/app/api/v1/endpoints/integrations/console.py` — Added `_handle_unauthenticated_codigo` import, `client_messaging_block_repository` import. Replaced final `access_denied` in `_route_by_instance` with unregistered identity handling: existing codigo session continuation, block check, codigo keyword routing, and fallback access_denied.
- `backend/app/api/v1/endpoints/integrations/console_handlers.py` — Added `_i18n_t` import, `code_services_repository` import. Added unauthenticated codigo constants, `_unauth_session_key()` helper. Added `_handle_unauthenticated_codigo()` entry point (starts or continues multi-step dialog under `session:unreg:...`). Added `_handle_unauth_codigo_service()` for service selection step. Added `_handle_unauth_codigo_email()` for email input step that creates a lookup job and returns `lookup_job_id`/`tenant_id`.
- `backend/tests/test_whatsapp_endpoint.py` — Added `_FakeRedis.lpush()`. Added `_setup_tenant_for_codigo()` helper. Added 5 tests: codigo flow start, multistep full flow (service→email→job_id), blocked identity no_reply=true, blocked identity /menu no_reply=true, non-codigo access_denied.

### Verification commands and results
1. `cd backend && uv run pytest -n 8 --dist loadscope --no-header -q --tb=short -p no:cacheprovider` — 1138 passed, 1 skipped in ~29s ✓
2. `cd frontend && npm run build` — Build successful ✓
3. `cd backend && python -c "import json; json.load(open('../n8n/Trackpal WhatsApp Bot.json', encoding='utf-8')); print('valid')"` — Valid JSON ✓

## Iteration 4 — 2026-06-01

### Selected Item
Item 4: Implement instance-first contextual routing for outgoing from_me=true /menu triggers.

### Why this item was chosen
Per prioritization strategy: public schemas (Item 1), persistence (Item 2), and code lookup (Item 3) are complete. Item 4 adds the from_me routing layer that routes self-target triggers to Tenant console and non-self-target triggers to the Client Context Shortcut with reply_to and context collision detection. This unblocks Items 5 (shortcut session lifecycle) and 6 (management flows).

### Changed files
- `backend/app/api/v1/endpoints/integrations/console.py` — Added `Tenant` import, `WhatsAppSessionService` import. Added `from_me`, `admin_phone`, `admin_jid`, `target_jid`, `target_phone`, `target_lid` parameters to `_route_by_instance`. Added `_handle_from_me_routing()` function that resolves admin identity (from admin_phone or tenant.whatsapp_phone fallback), checks self-target by phone/JID match, routes to Tenant console for self-target or Client Context Shortcut with context collision detection. Context sessions stored under `wa:client_ctx:{admin_phone}` with 5-minute TTL.
- `backend/tests/test_whatsapp_endpoint.py` — Added `_setup_tenant_with_instance()` helper. Added 7 tests: self-target by phone routes to Tenant console, self-target by JID routes to Tenant console, non-self-target routes to shortcut with reply_to, owner fallback without admin_phone, context collision rejection with no_reply=true, no-admin-phone without fallback returns no_reply, context stored in Redis.

### Verification commands and results
1. `cd backend && uv run pytest -n 8 --dist loadscope --no-header -q --tb=short -p no:cacheprovider` — 1145 passed, 1 skipped in ~28s ✓
2. `cd frontend && npm run build` — Build successful ✓
3. `cd backend && python -c "import json; json.load(open('../n8n/Trackpal WhatsApp Bot.json', encoding='utf-8')); print('valid')"` — Valid JSON ✓

### Next-iteration notes
Item 5 (Client Context Shortcut session lifecycle and unregistered target menus) is the next dependency. The from_me routing infrastructure now detects self-target vs non-self-target, creates a basic context session, and rejects collisions. Item 5 needs to add the menu facades, TTL behavior, input handling, and proper shortcuts for unregistered, blocked, and client targets.

## Iteration 5 — 2026-06-01

### Selected Item
Item 5: Implement Client Context Shortcut session lifecycle and unregistered target menus.

### Why this item was chosen
Per prioritization strategy: routing/session behavior after schemas, persistence, code lookup, and from_me routing. Item 4 (from_me routing) created the context session but didn't implement menu facades, block/unblock actions, TTL management, or input handling. Item 5 adds the full session lifecycle: intercepting admin replies, showing context-appropriate menus, handling block creation/unblock, cleanup on 0, and proper TTL refresh/no-refresh behavior. This unblocks Item 6 (contextual client creation/management flows).

### Changed files
- `backend/app/api/v1/endpoints/integrations/console.py` — Added `_handle_active_client_context` import. Added context session check in `_route_by_instance` before routing to Tenant console.
- `backend/app/api/v1/endpoints/integrations/console_handlers.py` — Added `normalize_phone`, `client_messaging_block_repository`, `clients_repository` imports. Added `_handle_active_client_context()` entry point that checks for active context, handles registered client fall-through, and routes by step. Added `_handle_ctx_unblocked_menu()` for unregistered unblocked targets (Crear cliente, Bloquear mensajes, 0 Cancelar). Added `_handle_ctx_blocked_menu()` for blocked targets (Desbloquear mensajes, 0 Cancelar). All menu functions enforce TTL refresh on valid input and no refresh on invalid input.
- `backend/tests/test_whatsapp_endpoint.py` — Added `_setup_context()` helper. Added 10 tests: context intercepts admin message, no context falls through, unblocked menu shows options, blocked menu shows unblock, Crear cliente advances step, Bloquear creates block, Desbloquear unblocks, 0 closes context, invalid input does not refresh TTL, valid input refreshes TTL.

### Verification commands and results
1. `cd backend && uv run pytest -n 8 --dist loadscope --no-header -q --tb=short -p no:cacheprovider` — 1155 passed, 1 skipped in ~28s ✓
2. `cd frontend && npm run build` — Build successful ✓
3. `cd backend && python -c "import json; json.load(open('../n8n/Trackpal WhatsApp Bot.json', encoding='utf-8')); print('valid')"` — Valid JSON ✓

### Next-iteration notes
Item 6 (contextual Client creation and existing Client management flows) is the next dependency. The context shortcut lifecycle and menu infrastructure (Item 5) now intercepts admin messages, shows unregistered-target menus, handles block/unblock, and manages TTL. Item 6 needs to implement the multi-step client creation flow, active/inactive client menus, subscription shortcut, and all management actions.

## Iteration 6 — 2026-06-01

### Selected Item
Item 6: Implement contextual Client creation and existing Client management flows.

### Why this item was chosen
Per prioritization strategy: facades after routing/session behavior. Items 1-5 (schemas, persistence, code lookup, from_me routing, shortcut lifecycle) are complete. Item 6 adds the contextual client creation flow (phone skip, LID-only prompt), active client menu (detail/edit/deactivate/subscription), and inactive client menu (reactivate/edit/delete). This unblocks Items 7 (console block management), 8 (n8n workflow), and 9 (documentation).

### Changed files
- `backend/app/repositories/clients_repository.py` — Added `get_client_by_tenant_phone()` and `get_client_by_tenant_lid()` (no active filter) for inactive client detection.
- `backend/app/api/v1/endpoints/integrations/console_context_shortcut.py` — New file: context shortcut creating flow (multi-step: phone→name→username→password→confirm), active client menu (detail, edit except phone, deactivate, subscription shortcut), inactive client menu (reactivate, edit except phone, delete), subscription shortcut with client pre-selected.
- `backend/app/api/v1/endpoints/integrations/console_handlers.py` — Integrated new context shortcut handlers. Replaced active client fall-through with active/inactive client menu routing. Added step routing for creating*, active_*, inactive_* steps. Modified unblocked menu "1" to delegate to creating flow.
- `backend/tests/test_whatsapp_endpoint.py` — Added `Client` and `User` model imports. Added 5 tests: creating phone skip, LID-only phone prompt, active client menu, inactive client menu, inactive client prevents duplicate creation.

### Verification commands and results
1. `cd backend && uv run pytest -n 8 --dist loadscope --no-header -q --tb=short -p no:cacheprovider` — 1160 passed, 1 skipped in ~28s ✓
2. `cd frontend && npm run build` — Build successful ✓
3. `cd backend && python -c "import json; json.load(open('../n8n/Trackpal WhatsApp Bot.json', encoding='utf-8')); print('valid')"` — Valid JSON ✓

### Next-iteration notes
Item 7 (Tenant console Client Messaging Blocks management and 9 back behavior) is the next dependency. Items 2 and 6 add the blocks persistence and context-shortcut block/unblock, but Item 7 exposes block management in the regular Tenant console and fixes the Clients submenu 9 back behavior.
