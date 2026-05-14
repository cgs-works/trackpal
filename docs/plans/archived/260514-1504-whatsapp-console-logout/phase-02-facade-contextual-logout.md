# Phase 2 — Facade contextual logout (`0` from top-level)

**Complexity:** M

## Objective

Implement full logout when the Master is authenticated and sends `0` while not in an active CRUD flow:

- Clear Auth Session + Conversation Session in Redis
- Mark Evolution chat/session as `closed` for the active instance + contact
- Return a clear confirmation reply

Also ensure `0` (and other reset commands) during login clears both auth + conversation state.

## Tasks (2–10 min each)

1. **Thread `instance` through the endpoint → facade**
   - Edit: `backend/app/api/v1/endpoints/integrations.py`
   - Pass `request.instance` into `facade.process_message(...)`.

2. **Update facade API to accept instance**
   - Edit: `backend/app/services/whatsapp_master_console_facade.py`
   - Update `process_message()` signature to accept `instance: str | None`.
   - Propagate to internal helpers as needed.

3. **Add a dedicated logout handler in the facade**
   - In `WhatsAppMasterConsoleFacade.process_message()` authenticated branch:
     - If `message.strip() == "0"`:
       - Load conversation session via `self._session_service.get_session(phone)`
       - If session exists and `session.flow` is truthy → do **not** logout (delegate to console service)
       - Else → perform logout:
         1) `await self._auth_session_service.clear_auth_session(phone)`
         2) `await self._session_service.clear_session(phone)`
         3) If `instance` is not None: call `await evolution_client.close_chat_session(instance=instance, remote_jid=...)`
         4) Return logout confirmation text (Spanish)
   - Ensure logout does **not** `touch_auth_session()`.

4. **Build a `remote_jid` safely**
   - Use canonical digits-only phone when building remoteJid:
     - `digits = normalize_phone(phone) or phone_digits_fallback`
     - `remote_jid = f"{digits}@s.whatsapp.net"`
   - Keep key clearing (`wa:auth:*`, `session:*`) using the same `phone` value used to set them (caller responsibility).

5. **Login reset clears lingering auth + conversation sessions**
   - In `_run_login_flow()`, `_handle_username_step()`, `_handle_password_step()` reset-command branches:
     - Call both:
       - `await self._auth_session_service.clear_auth_session(phone)`
       - `await self._session_service.clear_session(phone)`
     - Return `USERNAME_PROMPT`

6. **Add focused tests for logout vs cancel**
   - New file: `backend/tests/test_whatsapp_logout_flow.py`
   - Use fake Redis + manager pattern from existing tests.
   - Mock Evolution close call:
     - Patch `app.services.whatsapp_master_console_facade.evolution_client.close_chat_session`.
   - Cover:
     - Auth session exists + no active conversation flow + message `0` →
       - auth session cleared
       - conversation session cleared
       - evolution close called with `(instance, remote_jid)`
       - reply contains logout confirmation
     - Auth session exists + active flow session (e.g. `flow="create_tenant"`) + message `0` →
       - evolution close NOT called
       - auth session NOT cleared
       - reply is produced by console service (cancel path will be refined in phase 3)
     - During login flow, `0` clears both keys and returns username prompt.

## Verification

- `cd backend && uv run pytest tests/test_whatsapp_logout_flow.py -v`
- Regression: ensure credential auth still passes:
  - `cd backend && uv run pytest tests/test_whatsapp_credential_auth_flow.py -v`

## Exit Criteria

- `0` from authenticated top-level triggers full logout (Redis cleanup + Evolution close invocation + confirmation reply).
- `0` inside an active flow does not logout.
- Login reset (`0`) clears both Auth Session and Conversation Session.
- Tests prove Evolution close is called only for real logout.
