# Phase 04: Frontend i18n + locale switch UI

## Objective

- Frontend renders tenant/client-facing system text according to tenant locale using backend-provided catalogs.
- Frontend fetches locale catalog at login and refetches immediately after locale change.
- Tenant can change locale from dashboard profile/settings.

## Scope

- Files/modules this phase may touch:
  - `frontend/src/stores/i18n.js` (new)
  - `frontend/src/stores/auth.js` (hook catalog fetch)
  - `frontend/src/views/LoginView.vue`
  - `frontend/src/views/TenantDashboardView.vue`
  - `frontend/src/views/ClientDashboardView.vue`
  - `frontend/src/views/SubscriptionsView.vue`
  - `frontend/src/router/index.js` (optional: load catalog on route guard)
- Files/modules this phase must not touch:
  - Master dashboard i18n (master fixed Spanish; out of scope)

## Preconditions

- Phase 01 complete: `/api/v1/i18n/catalog` exists.
- `/api/v1/me` exposes locale; `PUT /api/v1/me` supports locale update for tenant role.

## Tasks

1. Add i18n store
   - Create `frontend/src/stores/i18n.js` with:
     - state: `locale`, `strings`, `isLoaded`.
     - action: `loadCatalog()` -> `GET /i18n/catalog` using `api` client.
     - helper: `t(key, params)`:
       - Lookup in `strings`.
       - If missing: return key (and optionally console.warn in dev).
       - Apply `{name}` placeholder interpolation.

2. Fetch catalog at login + on refresh
   - In `LoginView.vue` after successful `authStore.login()`, call `i18nStore.loadCatalog()` before routing.
   - On app reload with token already present:
     - Option A: call `loadCatalog()` in `App.vue`/`main.js` on mount when token exists.
     - Option B: call in router guard for `requiresAuth` routes.

3. Tenant locale change UI (web)
   - In `TenantDashboardView.vue` profile/settings section:
     - Add language selector bound to `profile.locale` (or separate ref).
     - Options: `en`, `es`.
     - On save: `PUT /me` includes `locale`.
     - After save success: `await i18nStore.loadCatalog()`; update displayed strings immediately.
   - Ensure master support mode does not display or modify tenant locale (unless explicitly desired).

4. Replace hardcoded tenant/client-facing strings with `t()` keys
   - Tenant dashboard:
     - Page titles, labels, button text, empty states, error/success messages.
   - Client dashboard:
     - Titles, labels, button text, status labels.
   - Subscriptions view:
     - All labels/buttons/status text.
   - Keep master dashboard unchanged (fixed Spanish/out-of-scope).

5. Date formatting
   - Use backend-provided formatted display fields added in Phase 02 (PRD FR-15).
   - If any screen still needs formatting and backend lacks display field, add backend field instead of using frontend `Intl`.

## Acceptance Criteria

- Frontend loads backend i18n catalog at login.
- Tenant can switch locale in web UI; strings update immediately without logout.
- Client UI uses tenant locale.
- No frontend-owned translation strings as source-of-truth (keys only; strings delivered by backend).

## Verification

- Commands:
  - `cd frontend && npm run build`
- Expected results:
  - Build succeeds.
- Manual checks:
  - Login as tenant; verify UI shows English for new tenant default `en`.
  - Switch to Spanish; verify immediate UI update + persists on refresh.
  - Login as client; verify UI language matches tenant.

## Idempotence and Recovery

- Safe to re-run: `npm run build`.
- Rollback: revert i18n store usage; UI falls back to hardcoded Spanish.

## Exit Criteria

- [ ] i18n store exists + used by tenant/client views.
- [ ] Login triggers catalog fetch; refresh triggers catalog fetch.
- [ ] Tenant locale switch implemented + refetches catalog.
- [ ] `npm run build` passes.

