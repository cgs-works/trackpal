# Phase 8: Frontend: Tenant Dashboard

**Complexity:** S
**Dependencies:** Phase 5, Phase 6

## Objective
Provide the placeholder dashboard for Tenants.

## Preconditions
- Login redirects to `/admin/dashboard` for tenants.

## Tasks
1. Context: `frontend/src/views/tenant/TenantDashboard.vue`.
2. Implement basic layout:
   - Fetch data from `GET /api/v1/dashboard/`.
   - Display welcome message: "Has iniciado sesión como [full_name]. El dashboard está en construcción."
3. Implement Profile modal/page:
   - Provide form for Tenant to update their data (`full_name`, `email`, `phone`) and password via `/api/v1/me/`.

## Verification
- Commands:
  - Local testing via browser at `/admin/dashboard`.
- Expected results:
  - Interface displays the placeholder message and user info.
  - Profile updates save successfully.

## Exit Criteria
- Tenants have a functional landing page post-login and can update credentials.
