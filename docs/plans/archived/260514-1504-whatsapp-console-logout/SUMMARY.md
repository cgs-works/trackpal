# Implementation Plan: WhatsApp Master Console — Contextual `0` (logout vs cancel) + menu return

## Objective

Implement contextual semantics for command `0` in the WhatsApp Master Console:

- When the Master is **authenticated** and **not inside an active CRUD flow**, `0` performs a **full logout**:
  - Clears Redis **Auth Session** (`wa:auth:{phone}`)
  - Clears Redis **Console/Conversation Session** (`session:{phone}`)
  - Calls Evolution API to mark the WhatsApp session as **`closed`** for the **active instance** and **current contact**
  - Returns a clear confirmation message
- When the Master is inside a **CRUD sub-flow**, `0` performs a **contextual cancel** (not logout):
  - Clears the conversation session only
  - Returns `"<cancel message>\n\n" + MAIN_MENU` in the **same** reply
- When a CRUD flow **completes successfully**, return `"<success message>\n\n" + MAIN_MENU` in the **same** reply.
- During the **login flow**, `0` cancels the attempt and clears any lingering Auth/Console sessions, returning to the username prompt.

PRD: `docs/prds/260514-1504-whatsapp-console-logout/PRD.md`

## Scope

### In scope

- Backend-only logic changes (n8n remains transport-only).
- Add Evolution API client capability to set chat/session status to `closed` for `(instance, remoteJid)`.
- Update `WhatsAppMasterConsoleFacade` to:
  - Detect `0` + conversational context
  - Perform full logout only from authenticated “main menu context” (defined as **no active flow session**) 
  - Keep `0` as cancel inside active flows
  - Ensure login reset clears both auth + conversation state
- Update `WhatsAppConsoleService` to:
  - On cancel inside an active flow: return `CANCELLED + "\n\n" + MAIN_MENU`
  - On successful end of create/deactivate/reactivate/delete flows: append `"\n\n" + MAIN_MENU`
  - Update menu/help/fallback copy so `0` is not described as “volver al menú” when the user is at top-level
- Automated test coverage for:
  - Logout from authenticated main menu (`0`)
  - Cancel inside active flow (`0`)
  - CRUD success replies include menu
  - Login cancel clears auth + conversation sessions
  - Evolution close call is invoked on logout and **not** invoked on cancel

### Out of scope

- New commands (e.g. `/logout`) or changing n8n routing.
- Closing Evolution sessions for other instances or other contacts.
- Splitting “final message” and menu into multiple WhatsApp messages.
- Dashboard/web logout changes.

## Architecture & Approach

### Key idea

Keep the existing layering:

- `WhatsAppMasterConsoleFacade` owns **auth-gated orchestration**.
- `WhatsAppConsoleService` owns **CRUD flows and conversation routing**.

Add **logout** to the facade (because it needs to clear both auth + conversation state and trigger an external Evolution-side close). Keep **flow cancellation** and **menu composition** inside the console service.

### Context rules (implemented)

- **Authenticated + `msg == "0"` + no active flow** → logout.
- **Authenticated + `msg == "0"` + active flow** → cancel flow (no logout).
- **Unauthenticated login flow + `msg in RESET_COMMANDS`** → clear conversation + auth and return `USERNAME_PROMPT`.

> Assumption (explicit): “Main menu context” is approximated as **authenticated + no active flow in Redis**. This matches how the console currently models state (flow state only exists when inside a sub-flow).

## Phases

- **Phase 1 [M]: Evolution API close-session client** — add an `EvolutionClient` method to mark a chat/session as `closed` and unit test the request shape.
  [x]
- **Phase 2 [M]: Facade logout orchestration** — implement contextual `0` handling at the authenticated entrypoint; clear Redis keys; call Evolution close; add tests.
  [x]
- **Phase 3 [M]: Sub-flow cancel + CRUD completion returns menu in same reply** — update console service replies/text; update/extend tests.
  [x]
- **Phase 4 [S]: Docs + full regression verification** — update documentation about `0` semantics; run full backend test suite.
  [x]

## Key File Targets

Backend:
- `backend/app/services/evolution_client.py` — add `close_chat_session()` (or similarly named) method.
- `backend/app/services/whatsapp_master_console_facade.py` — add logout orchestration and login reset cleanup.
- `backend/app/api/v1/endpoints/integrations.py` — pass `request.instance` into the facade.
- `backend/app/schemas/whatsapp.py` — keep/confirm `instance` field; add clarifying docstring if needed.
- `backend/app/services/whatsapp_console_service.py` — append menu on success; cancel message + menu on reset inside active flow; copy changes.

Tests:
- `backend/tests/test_whatsapp_logout_flow.py` (new) — focused tests for logout vs cancel behavior.
- `backend/tests/test_whatsapp_menu_flow.py` — update assertions for menu/help/fallback text.
- `backend/tests/test_whatsapp_create_flow.py` — ensure success replies now include menu.
- `backend/tests/test_whatsapp_lifecycle_flow.py` — ensure lifecycle success replies now include menu.
- `backend/tests/test_evolution_client.py` (new) — unit tests for close-session endpoint call (mock httpx).

Docs:
- `docs/architecture/n8n-workflow.md` (small note) or a dedicated console doc if one exists — document contextual meaning of `0`.

## Verification Strategy

Per-phase targeted tests + final full run.

- Phase 1:
  - `cd backend && uv run pytest tests/test_evolution_client.py -v`
- Phase 2:
  - `cd backend && uv run pytest tests/test_whatsapp_logout_flow.py -v`
  - `cd backend && uv run pytest tests/test_whatsapp_credential_auth_flow.py -v`
- Phase 3:
  - `cd backend && uv run pytest tests/test_whatsapp_menu_flow.py -v`
  - `cd backend && uv run pytest tests/test_whatsapp_create_flow.py -v`
  - `cd backend && uv run pytest tests/test_whatsapp_lifecycle_flow.py -v`
- Final:
  - `cd backend && uv run pytest -v`

## Risks & Mitigations

- **Ambiguous “main menu” detection**: since the console does not persist a “screen” state, we define “top-level” as `no active flow`. Mitigation: add tests for both session-present (active flow) and session-absent cases.
- **Evolution API endpoint mismatch**: the close-session endpoint and payload must match the existing validated Evolution integration. Mitigation: phase 1 includes confirming the correct endpoint/path/payload and codifying it in a unit test.
- **Accidental logout**: users accustomed to `0` as “menu” may log out. Mitigation: update menu/help/fallback copy to explain `0` closes session at top-level and `menu` returns to main menu.

## Open Questions (need product/ops confirmation)

1. **Exact Evolution API endpoint** for “set chat/session status to closed” (path + payload). The PRD says it exists and is already validated; we must confirm the exact contract.
2. Desired logout reply copy (Spanish): e.g. include “Escribe *menu* para iniciar sesión de nuevo.”
