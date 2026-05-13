# Phase 2 — Conversational login flow + endpoint gating

**Complexity:** L

## Objective

Make the WhatsApp Master Console start **unauthenticated**, prompt for **username** and **password**, and only then allow access to the existing menu/CRUD flows.

This phase wires Phase 1 primitives into:

- `POST /api/v1/integrations/n8n/console`
- A backend-owned conversational login state machine

## Tasks (2–10 min each)

1. **Add a facade/orchestrator for the console**
   - New file: `backend/app/services/whatsapp_master_console_facade.py`
   - Responsibilities:
     - Check lock state (Phase 1) and return lockout reply.
     - Check auth session; if present and role is `master`, delegate to `WhatsAppConsoleService.process_message(is_master=True, ...)`.
     - If absent, run login flow and on success create auth session.

2. **Define login prompts + messages (Spanish) in a single place**
   - Prefer: constants in `whatsapp_master_console_facade.py` (or a small `reply_templates` section)
   - Required replies:
     - Username prompt
     - Password prompt (includes explicit warning about sending password via WhatsApp)
     - Unknown username message
     - Wrong password message
     - Role not allowed (valid creds but role != master)
     - Lockout message (includes remaining minutes or a clear “espera X minutos”)

3. **Represent login progress using the existing conversation session**
   - Use `WhatsAppSessionService` + `ConversationSession` fields:
     - `flow="auth"`
     - `step` values: `"username"` and `"password"`
     - `temp_data["username"]` stores the entered username.
   - Ensure global reset commands clear only the conversation session (`session_service.clear_session(phone)`) but do **not** clear `wa:auth:{phone}`.

4. **Implement global commands during unauthenticated state**
   - Reset commands: return to username prompt (not the main menu).
   - Help commands (`ayuda` / `5`): either show existing help + a login note or a dedicated login-help reply.

5. **Integrate credential verification via existing AuthService**
   - Update facade to accept `AuthService` + DB session and call:
     - `user = await auth_service.authenticate(db, username, password)`
   - Enforce: `user is not None and user.role == "master"`
   - On success:
     - Create `WhatsAppAuthSession` in Redis (Phase 1), TTL = `settings.whatsapp_session_ttl_minutes * 60`.
     - Clear the auth flow conversation session.
     - Reply with `WhatsAppConsoleService.MAIN_MENU`.

6. **Update the console endpoint to remove phone-based identity**
   - Edit: `backend/app/api/v1/endpoints/integrations.py`
   - In `POST /n8n/console`:
     - Remove `identify_by_phone()` usage and the early `ACCESS_DENIED` return.
     - Always create `WhatsAppSessionService` when Redis manager is present.
     - Create `WhatsAppAuthSessionService` using the same Redis manager.
     - Call facade and return its reply.

7. **Update endpoint contract tests for the new behavior**
   - Edit: `backend/tests/test_whatsapp_endpoint.py`
   - Update cases:
     - “unknown phone” should now return a **login prompt** (when Redis is available) instead of access denied.
     - “tenant phone” should also return a login prompt (because identity is no longer inferred by phone).
   - Keep existing 401 API key tests unchanged.

8. **Add new focused tests for conversational login (happy path)**
   - New file: `backend/tests/test_whatsapp_credential_auth_flow.py`
   - Use patched `get_redis_manager` with the fake manager pattern.
   - Cover:
     - First message → username prompt
     - Provide username → password prompt
     - Provide correct password → main menu

## Verification

- Endpoint + auth flow tests:
  - `cd backend && uv run pytest tests/test_whatsapp_endpoint.py -v`
  - `cd backend && uv run pytest tests/test_whatsapp_credential_auth_flow.py -v`
- Ensure existing menu flow tests still pass (they exercise the post-auth console engine directly):
  - `cd backend && uv run pytest tests/test_whatsapp_menu_flow.py -v`

## Exit Criteria

- Sending `/menu` (or any first message routed by Evolution/n8n) produces a login prompt on a fresh phone.
- Valid master credentials create a Redis auth session and unlock the menu.
- No code path in the endpoint returns the main menu or performs tenant actions without an auth session.
- Endpoint remains relayable (always returns `{reply: str}`) and still fails safely when Redis is unavailable.
