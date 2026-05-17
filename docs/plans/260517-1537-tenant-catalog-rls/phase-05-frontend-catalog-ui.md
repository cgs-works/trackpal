# Phase 05: Frontend Catalog UI

## Objective

Expose tenant catalog management in the Vue dashboard and provide a Master support flow that can switch into a tenant context before operating tenant-scoped catalog APIs.

## Scope

- Files/modules this phase may touch:
  - `frontend/src/stores/auth.js`
  - `frontend/src/services/api.js`
  - `frontend/src/views/TenantDashboardView.vue`
  - `frontend/src/views/MasterDashboardView.vue`
  - Optional new frontend component files if keeping `TenantDashboardView.vue` small is necessary
  - `frontend/src/style.css` if shared styles are needed
- Files/modules this phase must not touch:
  - Backend production files except if a small API response mismatch is discovered and documented before fixing.
  - n8n workflow.

## Preconditions

- Phase 2 token response includes any needed `active_tenant_id` field while preserving `user.role` and `user.username`.
- Phase 3 catalog API endpoints are available and tested.
- Phase 4 isolation is in place or at least app-level isolation exists.

## Tasks

1. Context: inspect frontend patterns.
   - `frontend/src/stores/auth.js` for token storage.
   - `frontend/src/services/api.js` for auth header handling.
   - `frontend/src/views/TenantDashboardView.vue` for current dashboard/profile layout.
   - `frontend/src/views/MasterDashboardView.vue` for existing tenant list/action patterns.
2. Implement: adapt auth store.
   - Store `active_tenant_id` if backend returns it.
   - Persist `active_tenant_id` in the same durable frontend auth state as token/refresh token/user, e.g. `localStorage`, so Master support context survives page reload.
   - Preserve existing `token`, `refreshToken`, `user`, `role`, `username` API used by router.
   - Add method for Master switch tenant if endpoint returns new token pair or access token.
   - Add method to exit/clear Master support tenant context and store the unswitched Master token/context returned by backend.
3. Implement: Master switch UI.
   - In `MasterDashboardView.vue`, add an action on tenant rows such as `Manage catalog`.
   - When clicked, call switch endpoint for that tenant.
   - Store returned token/context.
   - Route or display catalog management context.
   - Show clear UI state that Master is managing a specific tenant.
   - Add explicit `Salir de tenant` / exit-support action visible when `role == 'master'` and `active_tenant_id` exists. It clears support context, persists the cleared auth state, and returns to Master dashboard.
   - Keep tenant CRUD actions unchanged.
4. Implement: tenant catalog UI.
   - Extend `TenantDashboardView.vue` with catalog section:
     - list services;
     - create service;
     - edit service name;
     - delete service with confirmation mentioning plans cascade;
     - select service and list its plans;
     - create/edit/delete plan.
   - Use Spanish UI text consistent with tenant dashboard.
   - Show duplicate/validation API errors clearly.
5. Implement: API calls.
   - Use existing Axios singleton.
   - Add local functions or service module for catalog calls.
   - No direct Supabase client.
6. Verify: manual frontend flow and build.
7. Confirm: record UI route/flow in `SUMMARY.md`.

## Acceptance Criteria

- User-visible or system-observable result:
  - Tenant user sees catalog management in dashboard.
  - Tenant can create/edit/delete services and plans.
  - Master can select a tenant and manage that tenant's catalog through support context.
- Required changed files:
  - Auth store and tenant dashboard UI.
  - Master dashboard only if Master support UI is implemented in this phase.
- Required unchanged behavior:
  - Existing login/logout and role-based routing work.
  - Existing profile/password update forms remain functional.
  - Existing Master tenant CRUD remains functional.

## Verification

- Commands:
  - `cd frontend && npm run build`
- Manual checks:
  - Login as tenant, open dashboard, create service, create plan, edit both, delete service and see plans removed.
  - Login as Master, switch to tenant, manage catalog, return to Master dashboard or logout cleanly.
  - Login as Master, switch to tenant, refresh browser, confirm `active_tenant_id` persists and catalog still works.
  - Use `Salir de tenant`, confirm context clears and Master dashboard works.
  - Duplicate service/plan names show readable error.
  - Refresh/reload keeps auth state coherent or fails safely to login.
- Expected results:
  - Vite build succeeds.
  - UI operations match backend API responses.
- Evidence to record in `SUMMARY.md`:
  - Build output summary.
  - Manual check notes.

## Idempotence and Recovery

- Safe to re-run:
  - Frontend build is read-only output to `dist/`.
  - Catalog UI actions are normal CRUD; tests/manual data should use disposable tenants.
- Recovery if interrupted:
  - If UI becomes too large in one file, split catalog section into local components and document paths.
- Rollback notes:
  - Frontend changes can be reverted independently if backend API remains stable.

## Exit Criteria

- [ ] Auth store handles active tenant context.
- [ ] Auth store persists active tenant context across page reload.
- [ ] Tenant catalog UI exists.
- [ ] Master switch/support UI exists with visible support context and `Salir de tenant` action.
- [ ] `npm run build` passes.
- [ ] Phase progress noted in `SUMMARY.md`.
