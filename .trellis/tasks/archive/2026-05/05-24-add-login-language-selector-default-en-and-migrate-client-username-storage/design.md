# Design — Login pre-auth i18n (frontend JSON) + client username storage migration

## Scope

1) **Pre-auth i18n (frontend-only)**
- Login/public views use local JSON translations.
- No backend i18n endpoint change.

2) **Backend username storage migration**
- `clients.local_username` renamed to `clients.username`.
- Stored value is full prefixed username: `<tenant_prefix>_<client_username_local>`.

---

## Part A — Frontend pre-auth i18n

### Current behavior
- `LoginView.vue` contains hardcoded Spanish labels/messages.
- Existing i18n store fetches `/i18n/catalog` (authenticated), not usable before login.

### Target behavior
- Login first render defaults to English.
- Selector (`en`/`es`) shown in login.
- Language saved to `localStorage` and reused on next visit.
- Strings loaded from one frontend JSON file.

### Proposed design

#### A1. JSON catalog
- New file: `frontend/src/i18n/public.json`
- Shape:
```json
{
  "en": {"login.title": "...", "login.username": "..."},
  "es": {"login.title": "...", "login.username": "..."}
}
```

#### A2. Minimal pre-auth resolver
- Add tiny helper/composable for public i18n:
  - reads selected locale from `localStorage` key (e.g. `publicLocale`)
  - default fallback `en`
  - returns `t(key)` from JSON map
  - setter persists selected locale.

#### A3. Login integration
- `LoginView.vue`:
  - add locale selector bound to helper state
  - replace hardcoded labels/buttons/errors with `t('login.*')`
  - initialize using stored locale or `en`.

#### A4. Reusability
- Helper/composable and JSON key namespace `login.*` can extend to future unauthenticated views (`public.*`).

### Risks / constraints
- Avoid coupling pre-auth JSON helper with authenticated i18n store.
- Keep authenticated pages unchanged to prevent regressions.

---

## Part B — Client username storage migration

### Current behavior
- `clients.local_username` stores tenant-local part.
- Canonical login is actually `users.username` built as `<prefix>_<local_username>`.
- Many services/tests still reference `local_username`.

### Target behavior
- `clients.username` stores canonical full prefixed value.
- `users.username` remains same canonical value.
- Prefix update must sync both `users.username` and `clients.username`.

### Proposed design

#### B1. DB migration
- Alembic migration steps:
  1. rename column `clients.local_username` -> `username`
  2. rename index `ix_clients_tenant_lower_local_username` -> `ix_clients_tenant_lower_username`
  3. backfill safety update from `users.username` join (`clients.owner_user_id = users.id`) to ensure canonical values.

#### B2. Model/repository updates
- `Client` model field renamed to `username`.
- repository uniqueness check renamed (tenant-scoped lower compare on `Client.username`).

#### B3. Service updates
- Client create:
  - validate local input
  - compute full prefixed username
  - persist computed value into `clients.username` and `users.username`.
- Client update:
  - when local part changes, recompute canonical and sync both tables.
- Tenant prefix update:
  - recompute and sync both `clients.username` and `users.username` for all tenant clients.

#### B4. API/schema contract
- Replace `local_username` fields in client-facing schemas/endpoints with `username` (canonical).
- Preserve validation semantics for local-part input where needed (internal field names in request handling can differ, but persisted column is canonical username).

#### B5. WhatsApp tenant console flow
- Update create/edit prompts and temp_data mapping to new contract where applicable.

### Risks / constraints
- Broad reference surface (schemas, services, WA flow, tests).
- Must preserve uniqueness and avoid duplicate usernames during migration.
- Keep tenant isolation rules intact.

---

## Validation strategy

### Frontend
- manual: login default EN, switch ES, reload keeps ES.
- build: `cd frontend && npm run build`.

### Backend
- focused:
  - `cd backend && uv run pytest tests/test_clients.py -v`
  - `cd backend && uv run pytest tests/test_i18n.py -v`
  - tenant console subset if touched.
- optional full suite if risk remains.