# ADR Candidates

> Architecture Decision Records que aún no se han escrito.
> Se listan aquí para planificar su redacción cuando se aborde el
> dominio correspondiente.

---

## Accepted / Documented

Los siguientes ADR ya existen y NO necesitan ser recreados:

| ID | Title | File |
|---|---|---|
| 0001 | Stack y arquitectura inicial | `docs/adr/0001-stack-y-arquitectura.md` |
| 0002 | Modelo de autenticación unificado con perfiles separados | `docs/adr/0002-modelo-de-autenticacion.md` |
| 0003 | Integración n8n y Evolution API para WhatsApp | `docs/adr/0003-integracion-n8n-y-evolution-api.md` |
| 0004 | Sesión de WhatsApp Master Console respaldada por Redis | `docs/adr/0004-sesion-whatsapp-redis.md` |

---

## ADR-0012 (Candidate): Multi-tenant Data Isolation Strategy

**When to write**: When implementing Customer / Subscription / Service entities.

**Decision needed**: How will data be isolated between tenants?

Options:
- **Row-level isolation** (current implicit approach): Every data table has a `tenant_id` FK column. Queries always filter by `tenant_id`. Simple, standard approach.
- **Schema-per-tenant**: Each tenant gets its own PostgreSQL schema. Stronger isolation but more complex migrations and connection management.
- **Database-per-tenant**: Each tenant gets its own database. Maximum isolation but highest operational overhead.

**Context**: Currently only `tenant_profiles` exists with a single row per tenant. When customers, subscriptions, and services are added, every query must be scoped to the correct tenant. The choice affects query patterns, migration complexity, and scalability.

**Related files**: `backend/app/models/tenant_profile.py`, `backend/app/services/tenant_service.py`

---

## ADR-0005 (Candidate): Customer & Subscription Data Model

**When to write**: When implementing Customer entity (next major feature).

**Decision needed**: How are customers and subscriptions modeled?

Key questions:
- Is a Customer shared across tenants or tenant-scoped?
- How are streaming credentials stored? Encrypted at rest?
- Can a customer have multiple subscriptions to the same service with different credentials?
- How are shared/group accounts handled (e.g., Netflix 4K plan shared among several customers of the same tenant)?
- What is the lifecycle of a subscription? (active, paused, cancelled, expired?)

**Related context files**: `CONTEXT.md`, `docs/prds/`, `README.md` (mentions Customers and Subscriptions as future scope)

---

## ADR-0006 (Candidate): Service Catalog Model

**When to write**: When implementing Service entity.

**Decision needed**: How are streaming services defined and managed?

Options:
- **Enum in code**: Services defined as a Python enum. Simple but requires code changes to add services.
- **Database table**: Services stored in a `services` table. Allows Master to add/configure services dynamically.
- **Hybrid**: Core services seeded in DB, with optional config overrides per tenant.

**Context**: The term "Service" appears in CONTEXT.md and README.md as "plataforma de streaming que se ofrece como producto (Netflix, Disney+, HBO Max, etc.)". The model needs to support service-specific fields like max profiles, pricing, supported regions, etc.

---

## ADR-0007 (Candidate): Frontend Token Storage Strategy

**When to write**: When addressing security improvements or implementing token refresh on frontend.

**Decision needed**: Where to store JWT tokens on the client side?

Current approach (implicit): `localStorage` for both `access_token` and `refresh_token`.

Options:
- **localStorage** (current): Simple, persists across tabs, but vulnerable to XSS.
- **httpOnly cookies**: More secure against XSS, but requires backend changes (set-cookie header) and CSRF protection.
- **In-memory only + refresh**: Access token in memory only, refresh token in httpOnly cookie. Most secure but requires more complex refresh logic.

**Context**: `frontend/src/stores/auth.js` stores tokens in localStorage. The 401 interceptor in `frontend/src/services/api.js` clears auth and redirects to login without attempting refresh.

---

## ADR-0008 (Candidate): Testing Strategy for Async FastAPI

**When to write**: When adding more tests or setting up CI.

**Decision needed**: What testing approach for the async backend?

Current approach: pytest + httpx (ASGITransport) + aiosqlite in-memory database. Evolution API calls disabled in tests by clearing `evolution_client.api_key`.

**Context**: `backend/tests/conftest.py` uses `sqlite+aiosqlite:///:memory:` with `StaticPool`. This approach provides fast, isolated tests but may not catch PostgreSQL-specific issues.

---

## ADR-0009 (Candidate): Deployment Model

**When to write**: When reviewing infrastructure decisions or adding new services.

**Decision needed**: Which hosting services for each component?

Current approach:
- **Backend**: Render Web Service (Python, Free plan, Oregon region)
- **Frontend**: Cloudflare Pages (static site)
- **Database**: Supabase PostgreSQL (external)
- **n8n**: Self-hosted at `https://rs-n8n.wilfredocamacho.dev`
- **Evolution API**: Self-hosted at `https://rs-evoapi.wilfredocamacho.dev`

**Context**: `render.yaml`, `docs/deployment.md`, `frontend/vite.config.js` (dev proxy)

---

## ADR-0010 (Candidate): API Versioning Strategy

**When to write**: Before introducing breaking changes to the API.

**Decision needed**: How to version the API.

Current approach: All endpoints under `/api/v1/` prefix.

Key questions:
- When to bump the version?
- How long to support old versions?
- How to communicate deprecation?

**Context**: `backend/app/api/v1/router.py`, `docs/architecture/api-routes.md`

---

## ADR-0011 (Candidate): Evolution Instance Lifecycle Management

**When to write**: When implementing tenant self-service QR generation or multi-instance support.

**Decision needed**: How are Evolution API instances managed throughout their lifecycle?

Current approach:
- **Create**: On tenant creation via `POST /tenants` → `EvolutionClient.create_instance()` + `setup_n8n_integration()`
- **Update**: Changing `evolution_instance_name` via `PUT /tenants/{id}` does NOT recreate/rename the instance (documented behavior).
- **Delete**: On tenant deletion via `DELETE /tenants/{id}` → `EvolutionClient.delete_instance()`
- **Transaction safety**: DB rollback if Evolution API call fails (both create and delete).

**Context**: `backend/app/services/evolution_client.py`, `backend/app/services/tenant_service.py`

---

## Summary Table

| Priority | ADR | Domain | Blocked By | Status |
|---|---|---|---|---|
| High | 0012 | Multi-tenant data isolation | Customer implementation | Draft (this doc) |
| High | 0005 | Customer & Subscription model | Domain clarification | Draft (this doc) |
| Medium | 0006 | Service catalog model | Service implementation | Draft (this doc) |
| Medium | 0007 | Token storage (security) | Security review | Draft (this doc) |
| Low | 0008 | Testing strategy | CI setup | Draft (this doc) |
| Low | 0009 | Deployment model | Infrastructure review | Draft (this doc) |
| Low | 0010 | API versioning | Breaking change | Draft (this doc) |
| Low | 0011 | Evolution instance lifecycle | Tenant QR feature | Draft (this doc) |
