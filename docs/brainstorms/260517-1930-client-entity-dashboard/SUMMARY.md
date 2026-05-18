# Brainstorm: Client Entity and Dashboard

> Created: 2026-05-17 19:30:04

## Context

- Trackpal currently supports `master` and `tenant` roles. Master manages tenants; tenants manage own profile and catalog.
- Existing auth uses `users.username` as a globally unique login identifier, JWT access/refresh tokens, and role-aware dashboard routing.
- Existing tenant-scoped data uses `active_tenant_id` plus PostgreSQL RLS policies on tenant-owned tables.
- New requirement: add end-customer (`client`) entity with its own login and dashboard.
- Scout findings:
  - Relevant backend patterns: `backend/app/models/user.py`, `backend/app/models/tenant.py`, `backend/app/api/v1/endpoints/dashboard.py`, `backend/app/services/profile_service.py`, `backend/app/core/database.py`.
  - RLS pattern should follow catalog tables in `backend/alembic/versions/cd3efe74cae6_tenant_catalog_rls.py`.
  - Frontend role-dashboard pattern lives in `frontend/src/router/index.js`, `frontend/src/stores/auth.js`, and `frontend/src/views/TenantDashboardView.vue`.

## Goals

- Add `client` as a first-class authenticated role.
- Tenant can create, list, edit, deactivate/reactivate, and delete inactive clients from tenant dashboard.
- Client has UUID, full name, username, password, and phone number.
- Client can log in and access a client dashboard.
- Client dashboard shows own profile as read-only and allows password change only.
- Client phone uniqueness is per tenant.
- Client username is unique within tenant from product perspective; tenant may auto-generate from full name or type manually.
- Preserve current one-field username login by storing a technical globally unique username in `users.username`.

## Non-Goals

- Client self-registration.
- Client profile self-editing.
- Client catalog management.
- WhatsApp console management for clients.
- Replacing current tenant/master auth architecture.
- External integrations or new third-party services.

## Chosen Approach

- Use existing `users` auth table plus new `clients` profile table.
- Add role `client` to auth and routing.
- Store client profile in `clients` with tenant ownership:
  - `id` UUID primary key.
  - `tenant_id` FK to `tenants`.
  - `owner_user_id` unique FK to `users`.
  - `full_name`.
  - `phone` canonical digits-only.
  - `display_username` or local username value unique per tenant.
  - `is_active`.
- Keep `users.username` globally unique as technical login identifier, generated from tenant context plus local username. UI can present tenant-local username.
- Client access tokens must include `active_tenant_id`; login must fail for inactive clients or clients whose tenant is inactive.
- Tenant dashboard owns client CRUD. Client dashboard remains readonly profile + password change.
- RLS should isolate client rows by tenant and allow client self-access only to own row.

Rationale:

- Reuses current JWT/session/password infrastructure.
- Avoids duplicating auth logic.
- Fits existing RLS and dashboard patterns.
- Satisfies tenant-local username requirement without changing login form yet.

## Alternatives Considered

- Separate client credential system — isolates customer auth from staff auth, but duplicates JWT, refresh sessions, dependencies, password handling, and frontend flows. Too much risk for current scope.
- CRM-only clients first — easiest and safest, but fails requirement for client login/dashboard now.
- Login with tenant + username — clean tenant-local username model, but changes login UX and auth contract. Better future option if technical usernames become confusing.

## Risks & Mitigations

- Tenant-local username conflicts with global `users.username` → store local username separately and generate deterministic technical username for auth.
- RLS gaps may expose clients across tenants → add policies for tenant role by owned tenant, master by active tenant context if needed, and client by own row; add SQL policy tests.
- Client token missing tenant context could cause 500s → mirror recent tenant-token hardening: fail token creation/login if active tenant cannot be resolved; dependency maps context errors to 401.
- Deleting clients may leave sessions or user rows inconsistent → use cascades carefully and revoke refresh sessions on deactivate/delete.
- Tenant dashboard may grow too large → keep client management section simple: list, create/edit modal, deactivate/reactivate/delete actions.

## Open Questions

- Should master in switched tenant context also manage clients for support, or tenant-only for first release?
- Should client see catalog services/plans later, or profile-only is strict long-term scope?
- Exact technical username format: e.g. `<tenant-id>:<local-username>`, `<tenant-slug>:<local-username>`, or generated opaque username.
- Should tenant be able to reset client passwords, or only create initial password and client changes later?

## Next Step Recommendation

- Proceed to `write-plan` for an implementation plan covering:
  1. Backend schema/model/migration/RLS.
  2. Auth and role/dashboard context changes.
  3. Client management API for tenants.
  4. Client dashboard API behavior.
  5. Frontend tenant client-management UI and client dashboard route/view.
  6. Regression tests and docs updates.
