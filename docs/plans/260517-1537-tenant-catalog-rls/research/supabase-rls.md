# Research: Supabase/Postgres RLS for Tenant Catalog

> Created: 2026-05-17 15:37:42

## Sources used

- Supabase Row Level Security: https://supabase.com/docs/guides/database/postgres/row-level-security
- Supabase RLS performance/best practices: https://supabase.com/docs/guides/troubleshooting/rls-performance-and-best-practices-Z5Jjwv
- Supabase Securing your API: https://supabase.com/docs/guides/api/securing-your-api
- Supabase service role bypass RLS note: https://supabase.com/docs/guides/troubleshooting/why-is-my-service-role-key-client-getting-rls-errors-or-not-returning-data-7_1K9z
- PostgreSQL constraints: https://www.postgresql.org/docs/current/ddl-constraints.html
- PostgreSQL numeric types: https://www.postgresql.org/docs/16/datatype-numeric.html

## Findings for this plan

- Put `tenant_id` on both `services` and `plans`; do not rely on joining `plans -> services` inside every RLS policy.
- Add composite FK from `plans(tenant_id, service_id)` to `services(tenant_id, id)` to prevent cross-tenant plan/service links.
- Use `WITH CHECK` policies for inserts/updates, not only `USING` policies.
- Index RLS columns: `tenant_id`, `(tenant_id, service_id)`, and case-insensitive unique keys.
- Do not depend on Supabase `auth.uid()` because the current app uses custom FastAPI JWTs, not Supabase Auth.
- For custom JWTs, set Postgres session-local settings per request, e.g. `app.current_user_id`, `app.current_role`, `app.active_tenant_id`, then reference them from RLS policies.
- PostgreSQL custom GUC names must include a dot. Use `app.current_user_id`, `app.current_role`, and `app.active_tenant_id`; do not use undotted names such as `tenant_id`.
- Because `set_config(..., true)` is transaction-local, it must be applied inside the same real PostgreSQL transaction that executes tenant-scoped queries. A dependency that sets context and then allows later SQL in a new transaction is unsafe.
- Non-PostgreSQL test dialects such as SQLite must skip `set_config` explicitly by dialect check.
- Composite FK from `plans(tenant_id, service_id)` to `services(tenant_id, id)` requires explicit `UNIQUE (tenant_id, id)` on `services`, even though `services.id` is already a primary key.
- Avoid service-role or owner bypass for tenant-facing operations. If app connects as table owner, consider `FORCE ROW LEVEL SECURITY` or a non-owner application role.
- Views may bypass RLS unless `security_invoker = true` in supported Postgres versions; avoid views for this phase.

## Decisions already made in brainstorm

- Tenant is a company/customer account that buys Trackpal.
- Tenant has a separate `users` row for login.
- `tenants.owner_user_id` points to that login user.
- One tenant has one owner user; owner is transferable by Master.
- Services and plans have no price in this phase.
- Service name is unique per tenant, case-insensitive.
- Plan name is unique per tenant + service, case-insensitive.
- Deletes are physical; deleting a service cascades to plans.
- WhatsApp resolves a tenant only when both `whatsapp_phone` and `evolution_instance_name` match.
- Master must switch into a tenant context before tenant-scoped catalog operations.
