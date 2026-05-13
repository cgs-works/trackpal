# Phase 3 — Security + regression coverage

**Complexity:** M

## Objective

Harden the credential-authenticated WhatsApp console by:

- Enforcing lockout after repeated failures.
- Ensuring session expiry returns the console to the login prompt.
- Proving there is no bypass to menu/CRUD without a valid auth session.
- Ensuring instance name changes do not affect authorization.

## Tasks (2–10 min each)

1. **Add lockout behavior to the auth flow**
   - In `backend/app/services/whatsapp_master_console_facade.py`
   - When in login flow:
     - On unknown username or wrong password: call `record_failed_attempt(phone)`.
     - If locked: return lockout reply and clear any in-progress auth conversation session.
   - On successful login: clear fail counter keys (if implemented) to avoid accidental lock later.

2. **Add lockout test cases**
   - In `backend/tests/test_whatsapp_credential_auth_flow.py`
   - Cover:
     - Wrong password repeated `threshold` times → lock message.
     - While locked → any message returns lock message.
     - After lock (simulate by removing lock key in fake redis) → login prompts again.

3. **Add role enforcement test**
   - Ensure tenant credentials do not unlock menu.
   - Expected behavior:
     - Return `ACCESS_DENIED`-style message (master-only) OR keep prompting login (choose one behavior and assert it).
   - Test should verify **no auth session** is created.

4. **Add expiry behavior tests**
   - Simulate auth session expiry by deleting `wa:auth:{phone}` key in fake redis.
   - Verify:
     - With no auth session, sending `menu` or `1` returns username prompt.
     - Any existing conversation CRUD session is cleared when auth is missing (safe reset).

5. **Add bypass regression tests (menu/CRUD before auth)**
   - Cases:
     - Unauthenticated message `"1"` (list tenants) does **not** list tenants; it prompts login.
     - Unauthenticated message `"2"` (create tenant) does **not** start create flow; it prompts login.

6. **Add multi-instance invariance tests**
   - In endpoint-level tests, send requests with different `instance` values but same phone:
     - Instance does not influence auth session lookup or lockout keys.

7. **Ensure password is not persisted or logged**
   - Confirm by inspection + test:
     - In fake redis store, assert no stored JSON values contain the raw password string.
   - If the repo uses structured logging in auth flow, ensure password is never interpolated.

## Verification

- Run auth flow tests:
  - `cd backend && uv run pytest tests/test_whatsapp_credential_auth_flow.py -v`
- Run endpoint contract tests:
  - `cd backend && uv run pytest tests/test_whatsapp_endpoint.py -v`
- Run the WhatsApp regression suite:
  - `cd backend && uv run pytest tests/test_whatsapp_menu_flow.py tests/test_whatsapp_list_select_flow.py tests/test_whatsapp_create_flow.py tests/test_whatsapp_edit_flow.py tests/test_whatsapp_lifecycle_flow.py -v`

## Exit Criteria

- Lockout triggers deterministically after the configured threshold.
- Auth session expiry returns the user to the login prompt and prevents continuing an in-progress CRUD flow.
- Tenant credentials never unlock the Master Console.
- Tests prove no bypass to menu/CRUD without a valid Redis auth session.
