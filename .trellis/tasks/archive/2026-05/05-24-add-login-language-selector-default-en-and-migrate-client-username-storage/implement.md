# Implementation Plan

## Phase 1 — Frontend pre-auth i18n (login/public)

1. Create `frontend/src/i18n/public.json` with `en` + `es` login keys.
2. Add lightweight public i18n helper/composable/store:
   - default locale `en`
   - `localStorage` persistence key
   - `t(key)` resolver from JSON.
3. Update `LoginView.vue`:
   - add language selector
   - replace hardcoded login strings with helper `t()` keys
   - immediate update on selector change.
4. Keep authenticated i18n store flow unchanged.

Validation:
- manual login view checks (default EN, switch ES, reload persistence)
- `cd frontend && npm run build`

---

## Phase 2 — DB migration clients.local_username -> clients.username

1. Create Alembic migration:
   - rename column
   - rename/recreate lower-username tenant index
   - backfill `clients.username = users.username` via join for consistency.
2. Update SQLAlchemy `Client` model field and index name.

Validation:
- migration upgrade/downgrade locally
- quick DB sanity query (non-null, expected format)

---

## Phase 3 — Backend repository/service/schema contract updates

1. Repositories:
   - rename `local_username_exists` logic to username-based check.
2. Services (`client_service`, tenant prefix sync):
   - persist canonical full username in `clients.username`
   - sync `users.username` + `clients.username` together.
3. Schemas/endpoints:
   - replace API contract fields from `local_username` to `username` where required by new contract.
4. Update `me/dashboard/clients` response mappings and dependent flows.

Validation:
- `cd backend && uv run pytest tests/test_clients.py -v`
- `cd backend && uv run pytest tests/test_i18n.py -v`

---

## Phase 4 — WhatsApp tenant console alignment

1. Update client create/edit flow fields/prompts/constants from `local_username` mapping to new canonical contract.
2. Ensure confirmations and success messages show correct username.

Validation:
- focused tenant console tests if impacted

---

## Phase 5 — Final verification and report

1. Run targeted test set for touched domains.
2. If any fragile area remains, run broader backend suite.
3. Summarize changed files + migration behavior + verification evidence.