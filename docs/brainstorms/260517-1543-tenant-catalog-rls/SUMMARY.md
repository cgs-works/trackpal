# Brainstorm: Tenant Catalog with Supabase/Postgres RLS

> Created: 2026-05-17 15:43:24

## Context

Trackpal currently models tenant accounts through `tenant_profiles`, where each tenant profile is directly coupled to a `users.id`. The requested feature adds tenant-managed catalog data: services and plans. During discussion, the domain was clarified:

- Trackpal Master creates tenant companies.
- A tenant is the company/admin account that buys Trackpal and logs into the current admin dashboard.
- Each tenant has one login `user`; the tenant owner can be transferred by Master.
- Tenants will later create their own clients, but clients are out of scope for this feature.
- Catalog data must be isolated per tenant at the database level using Supabase/Postgres RLS.

External research confirmed that custom FastAPI JWTs do not automatically map to Supabase `auth.uid()`. RLS must therefore use explicit Postgres session-local context settings or a future Supabase Auth migration. This brainstorm selected session-local context to preserve the current FastAPI auth architecture.

## Goals

- Replace `tenant_profiles` as the canonical tenant entity with a real `tenants` table.
- Keep existing `users` table as the login/identity table.
- Link each tenant to its login user with `tenants.owner_user_id`.
- Add tenant-owned services and plans.
- Enforce tenant isolation with app checks and real Postgres/Supabase RLS.
- Keep Master support ability through explicit tenant switching.
- Preserve current tenant login/dashboard behavior as much as possible.

## Non-Goals

- No customer/client entity in this phase.
- No subscriptions purchased by customers.
- No plan price, currency, billing cycle, payments, or invoices.
- No WhatsApp tenant self-service catalog management yet.
- No migration to Supabase Auth.
- No audit log for Master support operations yet.
- No direct frontend-to-Supabase data access.

## Chosen Approach

Use `users` for authentication and `tenants` for company/account data:

```text
users
  └── tenants.owner_user_id
          └── services
                └── plans
```

Chosen model:

- `tenants`
  - `id`
  - `owner_user_id`
  - `name`
  - `email`
  - `whatsapp_phone`
  - `evolution_instance_name`
  - `is_active`
- `services`
  - `id`
  - `tenant_id`
  - `name`
- `plans`
  - `id`
  - `tenant_id`
  - `service_id`
  - `name`

Rules:

- `owner_user_id` is unique and transferable by Master.
- A tenant user logs in with the existing `users` auth flow and resolves its tenant through `owner_user_id`.
- Master must switch into a tenant context before tenant-scoped catalog operations.
- WhatsApp tenant resolution requires both `whatsapp_phone` and `evolution_instance_name` to match.
- Service names are unique per tenant, case-insensitive.
- Plan names are unique per tenant + service, case-insensitive.
- Deletes are physical.
- Deleting a service cascades to its plans.
- Plans include no price in this phase.

RLS approach:

- Set Postgres session-local settings per request:
  - `app.current_user_id`
  - `app.current_role`
  - `app.active_tenant_id`
- RLS policies filter `tenants`, `services`, and `plans` by those settings.
- Tenant users can access only their owned tenant.
- Master can access only the switched tenant context for tenant-scoped operations.

## Alternatives Considered

- `tenant_memberships` table — rejected for now because the user clarified that each tenant has one admin/login owner. This can be revisited if multiple admins per tenant become required.
- Tenant as login identity without separate `users` row — rejected because current auth already uses `users`, and keeping it minimizes disruption.
- Full Supabase Auth migration — rejected for this phase because it is broader and riskier than needed.
- App-only isolation without RLS — rejected because the user explicitly wants Supabase/Postgres RLS isolation.
- Plan price in initial schema — removed after clarification; plans are name-only for this phase.
- Soft delete — rejected; user selected physical delete.

## Risks & Mitigations

- Current code assumes `tenant_profile.id == user.id` → introduce `tenants.owner_user_id` and add tests where tenant ID differs from user ID.
- RLS with custom JWT cannot use `auth.uid()` → use transaction-local Postgres context settings.
- App DB role may bypass RLS if it owns tables or uses service role → validate Supabase role behavior and consider `FORCE ROW LEVEL SECURITY` or a non-owner app role.
- SQLite tests cannot enforce RLS → add app-level isolation tests plus SQL policy checks, and document Postgres/Supabase manual validation.
- WhatsApp Master Console adapter expects `TenantProfile` fields → update adapter/wrapper to expose compatible attributes from `Tenant`.
- Case-insensitive uniqueness differs across DBs → enforce in service layer and with Postgres expression indexes/constraints.

## Open Questions

- No business/domain questions remain blocking.
- Execution must verify the actual Supabase/Postgres role used by the backend so RLS is not bypassed.
- Execution must decide whether to drop `tenant_profiles` immediately or keep it through a short transitional migration if code changes require a safer path.

## Next Step Recommendation

Proceed with the implementation plan:

`docs/plans/260517-1537-tenant-catalog-rls/SUMMARY.md`

Recommended workflow before execution:

1. Create GitHub issue from the plan: `/issue docs/plans/260517-1537-tenant-catalog-rls/SUMMARY.md`
2. Execute with worker after approval: `/worker docs/plans/260517-1537-tenant-catalog-rls/SUMMARY.md`
