# Phase 04: Frontend Dashboards

## Objective

- Expose tenant prefix management, tenant client CRUD, and client readonly dashboard in Vue UI.

## Scope

- Files/modules this phase may touch:
  - `frontend/src/router/index.js`
  - `frontend/src/stores/auth.js`
  - `frontend/src/views/LoginView.vue`
  - `frontend/src/views/MasterDashboardView.vue`
  - `frontend/src/views/TenantDashboardView.vue`
  - `frontend/src/views/ClientDashboardView.vue`
  - `frontend/src/services/api.js` only if needed
- Files/modules this phase must not touch:
  - Backend production code except if a frontend-discovered API mismatch requires returning to prior phases.

## Preconditions

- Phases 1-3 completed and backend client APIs work.
- API response shapes are known from backend schemas/tests.

## Tasks

1. Context: inspect current route guards and dashboard UI patterns.
2. Update auth routing:
   - Add `/client/dashboard` route requiring role `client`.
   - Redirect logged-in client users from `/login` to `/client/dashboard`.
   - Redirect role mismatch for `client` to correct dashboard.
3. Update `LoginView.vue`:
   - Add client redirect after login.
   - Keep Spanish UI text.
4. Update `MasterDashboardView.vue`:
   - Show `client_prefix` in tenant table.
   - Add prefix field in create/edit modal.
   - Allow empty prefix on create so backend auto-generates.
   - Validate/display API errors for duplicate/invalid prefix.
   - Display prefix collision/update failure from backend 409 as a clear Spanish message.
   - Show a clear Spanish warning when editing prefix: existing client login usernames for that tenant will change.
5. Update `TenantDashboardView.vue`:
   - Add client management section below or beside catalog section.
   - Load clients from `GET /clients`.
   - Add create/edit modal or inline form with full name, local username, password on create, phone.
   - Show technical login username returned by API so tenant can share it with client.
   - Add activate/deactivate/delete inactive actions.
   - Prevent delete active client in UI and show Spanish message.
6. Add `ClientDashboardView.vue`:
   - Load `/dashboard` and `/me` as needed.
   - Show UUID, full name, username/login username, phone, tenant/provider name if backend returns it.
   - Include password change form only.
   - No profile edit form.
   - Logout button.
7. Reuse existing CSS classes where practical; avoid new design system.
8. Verify build and manually inspect route strings for correct redirects.

## Acceptance Criteria

- User-visible or system-observable result:
  - Master can see/edit tenant prefix.
  - Tenant can manage clients from dashboard.
  - Client can log in and sees readonly dashboard with password change.
- Required changed files:
  - Router, auth store/Login if needed, master/tenant dashboards, new client dashboard view.
- Required unchanged behavior:
  - Master and tenant dashboard flows still work.
  - Catalog UI still works.

## Verification

- Commands:
  - `cd frontend && npm run build`
- Expected results:
  - Vite build succeeds.
- Evidence to record in `SUMMARY.md`:
  - Build result line.

## Idempotence and Recovery

- Safe to re-run:
  - Frontend build.
- Recovery if interrupted:
  - Keep `ClientDashboardView.vue` isolated until router import is complete.
- Rollback notes:
  - Remove client route and dashboard sections if backend contract changes.

## Exit Criteria

- [ ] Client route exists and redirects work.
- [ ] Master prefix UI exists.
- [ ] Master prefix edit warning exists.
- [ ] Master sees clean Spanish conflict message when prefix edit collides.
- [ ] Tenant client management UI exists.
- [ ] Client dashboard has no profile edit capability.
- [ ] `npm run build` passes.
