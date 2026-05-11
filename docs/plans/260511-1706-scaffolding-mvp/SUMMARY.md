# Implementation Plan: Trackpal MVP Scaffolding

## Objective

Build the MVP scaffolding for Trackpal, establishing the unified authentication model, Master and Tenant roles, backend CRUD logic for tenants, Vue 3 frontend dashboards, the n8n integration endpoint, and the real WhatsApp bot workflow. This prepares the system for future streaming subscription management.

Link to PRD: `docs/prds/260511-1706-scaffolding-mvp/PRD.md`

## Scope

### In scope

- Monorepo setup (backend with UV, frontend with Vite)
- SQLAlchemy async models + Alembic migrations for Supabase PostgreSQL
- Master seed script with env-based config (name, username, password, phone)
- Unified JWT auth with refresh token rotation (table refresh_sessions)
- Master Tenant CRUD with soft-delete (deactivated tenant blocks login + n8n identify)
- Dashboard metrics in GET /tenants metadata (total, active, inactive)
- Frontend login, Master dashboard (with password auto/manual options), Tenant placeholder
- n8n identify endpoint protected with API Key
- Real n8n WhatsApp bot workflow implementation
- Phone uniqueness cross-table validation
- Master unique protection (seed idempotent + service layer guard)

### Out of scope

- Evolution API streaming QR generation (manual for now)
- Multi-language support
- Real Tenant Dashboard features (placeholder only)
- End customers management and streaming subscriptions
- CI/CD pipeline and production deployment

## Architecture & Approach

- Backend: FastAPI, SQLAlchemy (async via asyncpg), Alembic, Pydantic V2. UV for dependency management.
- Frontend: Vue 3 (Composition API), Vite, Vue Router, Pinia, Axios.
- Database: Supabase PostgreSQL (direct SQLAlchemy connection). All IDs are UUID v4.
- Migrations: Alembic with async support.
- Endpoints prefixed with `/api/v1/`.
- Architecture layers: models (SQLAlchemy) → schemas (Pydantic V2) → services (logic + validation) → api (endpoints).

## Phases

- [x] **Phase 1 [M]: Project scaffolding** — UV, FastAPI app structure, Vue + Vite, monorepo layout, configs.
- [x] **Phase 2 [M]: Database models + seed** — SQLAlchemy models (User, MasterProfile, TenantProfile, RefreshSession), Alembic migrations, Master seed script with env vars, phone uniqueness, Master unique constraint.
- [x] **Phase 3 [M]: Auth module** — Login endpoint, JWT creation/validation, refresh token rotation, logout, bcrypt hashing, role-based dependency, integrations/n8n/identify endpoint with API Key.
- [x] **Phase 4 [M]: Tenants CRUD** — Master endpoints for tenant management with soft-delete, metadata metrics, password auto/manual options on create.
- [ ] **Phase 5 [S]: Profile + Dashboard** — Authenticated profile endpoints and tenant dashboard placeholder API.
- [ ] **Phase 6 [M]: Frontend: Login** — Vue auth components, Pinia store with JWT + refresh, router guards, role-based redirect.
- [ ] **Phase 7 [M]: Frontend: Master Dashboard** — Tenant table with metrics, creation/editing forms with password options, activate/deactivate/delete actions.
- [ ] **Phase 8 [S]: Frontend: Tenant Dashboard** — Placeholder UI with profile access and password change.
- [ ] **Phase 9 [M]: n8n workflow** — Implement real WhatsApp bot workflow: webhook from Evolution API, identify via API Key, data table session management, interactive menu, CRUD tenants via HTTP.

## Key Changes

- New monorepo layout at root: `backend/` and `frontend/`.
- Database schema: `users`, `master_profiles`, `tenant_profiles`, `refresh_sessions`.
- Unified authentication logic with two distinct roles and conditional routing.
- n8n API Key auth for integrations endpoint.

## Verification Strategy

- Backend: `pytest` with `httpx` and `aiosqlite`. Run after each phase.
- Frontend: `vitest` for components. Manual dev server verification.
- n8n: `validate_workflow` + manual test with Evolution API.

## Dependencies

- Backend: `fastapi`, `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `pydantic[email]`, `python-jose`, `passlib[bcrypt]`, `python-dotenv`, `pytest`, `httpx`, `pytest-asyncio`, `aiosqlite`.
- Frontend: `vue`, `vue-router`, `pinia`, `axios`, `vite`.

## Risks & Mitigations

- Async DB concurrency issues → Use properly scoped async sessions via dependency injection.
- n8n integration issues → Dedicated identify endpoint with API Key, testable in isolation.
- WhatsApp password in chat → Support both auto-generate (recommended) and manual entry (risk accepted).
- Refresh token security → Rotation on each refresh, revoke on logout, stored as hash.

## Open Questions

- Evolution API instance URL and credentials for n8n workflow testing.
