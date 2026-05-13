# Trackpal Context Map

> This file maps every source file and document to the domain concepts it implements or describes.
> Use it to navigate the codebase from a domain perspective.

---

## Domain-to-File Mapping

### Master (Platform Owner)

| File | Role |
|---|---|
| `backend/app/models/master_profile.py` | SQLAlchemy model for Master-specific data (name, phone) |
| `backend/scripts/seed.py` | Creates the initial Master user (idempotent, env-based) |
| `frontend/src/views/MasterDashboardView.vue` | Master dashboard UI: tenant CRUD table, metrics, modals |
| `docs/adr/0002-modelo-de-autenticacion.md` | Documents Master auth model decision |

### Tenant (Client Business)

| File | Role |
|---|---|
| `backend/app/models/tenant_profile.py` | SQLAlchemy model: full_name, email, phone, evolution_instance, is_active |
| `backend/app/services/tenant_service.py` | Full CRUD, activate/deactivate/delete, Evolution API orchestration |
| `backend/app/api/v1/endpoints/tenants.py` | HTTP endpoints: POST/GET/PUT/PATCH/DELETE /tenants |
| `backend/app/schemas/tenant.py` | Pydantic schemas: TenantCreate, TenantUpdate, TenantResponse, TenantListResponse |
| `frontend/src/views/TenantDashboardView.vue` | Tenant placeholder dashboard with profile management |
| `backend/tests/test_tenants.py` | 12 tests covering Tenant CRUD, deactivation, role enforcement |

### User (Unified Auth)

| File | Role |
|---|---|
| `backend/app/models/user.py` | SQLAlchemy User model: id, username, password_hash, role |
| `backend/app/models/refresh_session.py` | Refresh token session tracking |
| `backend/app/schemas/auth.py` | LoginRequest, TokenResponse, RefreshRequest, IdentifyResponse |
| `backend/app/services/auth_service.py` | Authentication, token creation/refresh/revocation, phone identification |
| `backend/app/api/v1/endpoints/auth.py` | HTTP endpoints: /auth/login, /auth/refresh, /auth/logout |
| `backend/app/core/security.py` | JWT create/decode, bcrypt hash/verify, API key verification |
| `backend/tests/test_auth.py` | 12 tests covering login, refresh, logout, identify, deactivation |

### Profile (Self-management)

| File | Role |
|---|---|
| `backend/app/services/profile_service.py` | Get/update profile, change password |
| `backend/app/api/v1/endpoints/me.py` | HTTP endpoints: GET/PUT /me, PUT /me/password |
| `backend/app/schemas/me.py` | ProfileResponse, ProfileUpdate, PasswordChange |
| `backend/tests/test_profile.py` | 8 tests covering profile CRUD, password change, dashboard |

### Dashboard

| File | Role |
|---|---|
| `backend/app/api/v1/endpoints/dashboard.py` | Role-aware dashboard: Master gets tenant counts, Tenant gets placeholder |
| `backend/app/schemas/dashboard.py` | MasterDashboardResponse, TenantDashboardResponse |

### WhatsApp / n8n Integration

| File | Role |
|---|---|
| `backend/app/services/evolution_client.py` | Async HTTP client for Evolution API (create/setup/delete instances) |
| `backend/app/api/v1/endpoints/integrations.py` | GET /integrations/n8n/identify, POST /integrations/n8n/console |
| `backend/app/core/phone.py` | PhoneNormalizer — canonical digits-only phone for identity, session key, storage |
| `backend/app/core/redis_client.py` | RedisConnectionManager + FailoverPolicy — active-passive HA, circuit breaker |
| `backend/app/services/whatsapp_session_service.py` | WhatsAppSessionService — ephemeral session CRUD over Redis with TTL |
| `backend/app/services/whatsapp_console_service.py` | WhatsAppConsoleService — conversation routing, menus, multi-step CRUD flows |
| `backend/app/services/contingency_reply_policy.py` | ContingencyReplyPolicy — relayable texts for degraded Redis states |
| `n8n/Trackpal WhatsApp Bot.json` | n8n workflow export: webhook → parse → console call → merge → send |
| `docs/architecture/n8n-workflow.md` | Full workflow documentation with node descriptions |
| `backend/tests/conftest.py` | Evolution API disabled in tests (clears api_key) |

### API Layer

| File | Role |
|---|---|
| `backend/app/main.py` | FastAPI app, CORS, lifespan, health endpoint |
| `backend/app/api/v1/router.py` | Aggregates all v1 routers |
| `backend/app/api/dependencies.py` | get_current_user, require_role, verify_n8n_api_key_header |
| `docs/architecture/api-routes.md` | Complete route table with methods, paths, auth requirements |

### Database

| File | Role |
|---|---|
| `backend/app/core/database.py` | AsyncSession factory (engine + sessionmaker) |
| `backend/app/core/config.py` | Pydantic Settings from environment variables |
| `backend/alembic/versions/cd1efe74cae4_initial_schema.py` | Initial migration: users, master_profiles, tenant_profiles, refresh_sessions |
| `backend/alembic/env.py` | Async Alembic configuration (reads DATABASE_URL from env) |

### Frontend Core

| File | Role |
|---|---|
| `frontend/src/router/index.js` | Route definitions with auth guards and role-based redirect |
| `frontend/src/stores/auth.js` | Pinia store: login, logout, token/localStorage management |
| `frontend/src/services/api.js` | Axios instance with JWT interceptor and 401 redirect |
| `frontend/src/views/LoginView.vue` | Unified login form, role-based redirect |
| `frontend/src/App.vue` | Root component (<router-view />) |
| `frontend/src/style.css` | Global base styles |

### Deployment & Operations

| File | Role |
|---|---|
| `render.yaml` | Render Blueprint: web service config, build/start commands, env vars |
| `frontend/public/_redirects` | Cloudflare Pages SPA routing |
| `frontend/vite.config.js` | Vite config with API proxy to backend |
| `docs/deployment.md` | Deploy guide for Render + Cloudflare Pages + n8n |

### Documentation

| File | Role |
|---|---|
| `docs/SUMMARY.md` | Documentation index |
| `docs/architecture/api-routes.md` | All API endpoints documented |
| `docs/architecture/data-flow.md` | Auth, refresh, n8n, deactivation, deletion flow diagrams |
| `docs/architecture/n8n-workflow.md` | n8n WhatsApp workflow detailed documentation |
| `docs/codebase/backend.md` | Backend structure, key modules, services, tests |
| `docs/codebase/frontend.md` | Frontend structure, routes, auth store, API service |
| `docs/prds/260511-1706-scaffolding-mvp/PRD.md` | Product Requirements Document (MVP) |
| `docs/plans/260511-1706-scaffolding-mvp/SUMMARY.md` | Implementation plan (10 phases, all complete) |
| `docs/adr/0001-stack-y-arquitectura.md` | Stack and architecture decision |
| `docs/adr/0002-modelo-de-autenticacion.md` | Unified auth model with profiles |
| `docs/adr/0003-integracion-n8n-y-evolution-api.md` | n8n and Evolution API integration |
| `README.md` | Project overview, quick start, stack |

---

## Architecture Layers

```
┌─────────────────────────────────────────────────────────────────────┐
│                        PRESENTATION LAYER                           │
│  frontend/src/views/LoginView.vue                                   │
│  frontend/src/views/MasterDashboardView.vue                         │
│  frontend/src/views/TenantDashboardView.vue                         │
├─────────────────────────────────────────────────────────────────────┤
│                        API / ROUTER LAYER                           │
│  backend/app/api/v1/endpoints/*.py          (HTTP handlers)         │
│  backend/app/api/dependencies.py            (auth guards)           │
│  frontend/src/router/index.js              (Vue Router)            │
├─────────────────────────────────────────────────────────────────────┤
│                        SERVICE LAYER                                │
│  backend/app/services/auth_service.py       (auth logic)            │
│  backend/app/services/tenant_service.py     (tenant CRUD)           │
│  backend/app/services/profile_service.py    (profile management)    │
│  backend/app/services/evolution_client.py   (Evolution API client)  │
├─────────────────────────────────────────────────────────────────────┤
│                        DATA LAYER                                   │
│  backend/app/models/*.py                    (SQLAlchemy ORM)        │
│  backend/app/schemas/*.py                   (Pydantic V2)           │
│  backend/app/crud/users.py                  (data access helpers)   │
│  backend/alembic/versions/*.py              (migrations)            │
├─────────────────────────────────────────────────────────────────────┤
│                        INTEGRATION LAYER                            │
│  n8n/Trackpal WhatsApp Bot.json            (workflow export)        │
│  backend/app/api/v1/endpoints/integrations.py (n8n hook)            │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Test Coverage Map

| Test File | Lines | Coverage |
|---|---|---|
| `backend/tests/test_auth.py` | ~150 | Login, refresh, logout, rotation, identify, deactivated tenant |
| `backend/tests/test_tenants.py` | ~160 | CRUD, soft-delete, activation, delete only inactive, role enforcement |
| `backend/tests/test_profile.py` | ~110 | Profile get/update, password change, dashboard, phone conflict |
| `backend/tests/test_phone_normalizer.py` | ~80 | Phone canonicalization: +, JID, device suffix, None, blank |
| `backend/tests/test_redis_failover_policy.py` | ~120 | Circuit breaker: CLOSED, OPEN, HALF_OPEN, threshold, window |
| `backend/tests/test_redis_connection_manager.py` | ~150 | Primary/backup pools, execute routing, failover, no-redis |
| `backend/tests/test_whatsapp_session_service.py` | ~200 | Session CRUD, TTL, explicit delete, used_backup, serialization |
| `backend/tests/test_whatsapp_menu_flow.py` | ~200 | Menu, reset, help, fallback, TTL not refreshed, no-session-service |
| `backend/tests/test_whatsapp_create_flow.py` | ~150 | Multi-step create tenant flow |
| `backend/tests/test_whatsapp_edit_flow.py` | ~100 | Multi-step edit tenant flow |
| `backend/tests/test_whatsapp_list_select_flow.py` | ~150 | Tenant list + detail selection, detail actions |
| `backend/tests/test_whatsapp_lifecycle_flow.py` | ~100 | Deactivate/delete confirmation flows |
| `backend/tests/test_whatsapp_endpoint.py` | ~100 | /integrations/n8n/console endpoint: contingency, HA, total failure |
| `backend/tests/test_contingency_reply_policy.py` | ~30 | SESSION_RESET, TEMPORARY_UNAVAILABLE constants |
| `backend/tests/conftest.py` | ~90 | Fixtures: in-memory DB, master/tenant/deactivated users, auth headers |

**Total: 340 tests** — all passing async with aiosqlite in-memory database. Redis operations use fake/test doubles.

---

## Data Flow Paths

### Login
```
Frontend → POST /auth/login → AuthService.authenticate()
  → verify password → check is_active → create tokens → store refresh session
  → return {access_token, refresh_token, user}
```

### Tenant Deactivation
```
Master → PATCH /tenants/{id}/deactivate → TenantService.deactivate_tenant()
  → profile.is_active = False → revoke all refresh sessions → commit
```

### WhatsApp Message (Console / Transport-only)
```
WhatsApp → Evolution API → n8n webhook → parse → POST /integrations/n8n/console
  → Backend: normalize phone → identify Master → Redis session (HA, circuit breaker)
  → WhatsAppConsoleService routing → Redis session write (TTL 15 min)
  → reply text → n8n → Evolution API → WhatsApp
```

### Token Refresh
```
Client → POST /auth/refresh → AuthService.refresh_access_token()
  → decode JWT → find non-revoked session → verify hash match
  → revoke old → check is_active (if tenant) → create new token pair
```

---

## Future Domain Entities (Not Yet Implemented)

| Entity | Expected Location | Status |
|---|---|---|
| Customer | `backend/app/models/customer.py`, `backend/app/services/customer_service.py` | Planned |
| Subscription | `backend/app/models/subscription.py`, `backend/app/services/subscription_service.py` | Planned |
| Service | `backend/app/models/service.py` (streaming platform catalog) | Planned |

*See `docs/prds/` and `docs/plans/` for roadmap details.*
