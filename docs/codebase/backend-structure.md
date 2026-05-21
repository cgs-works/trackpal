# Backend Codebase Structure

```
backend/
├── app/                          # Application package
│   ├── __init__.py
│   ├── main.py                   # FastAPI app entrypoint
│   ├── api/                      # REST API layer
│   │   ├── __init__.py
│   │   ├── dependencies.py       # Deps: get_current_user, require_role, etc.
│   │   └── v1/
│   │       ├── router.py         # Aggregates all endpoint routers
│   │       └── endpoints/
│   │           ├── auth.py       # Login, refresh, logout
│   │           ├── catalog.py    # Tenant-scoped services/plans CRUD
│   │           ├── clients.py    # Tenant-scoped client lifecycle CRUD
│   │           ├── dashboard.py  # Role-aware dashboard data
│   │           ├── integrations.py # n8n identify, WhatsApp console
│   │           ├── me.py         # Self-profile CRUD
├── subscriptions.py # Tenant subscription CRUD + lifecycle job + reminders
│   │           └── tenants.py    # Master-only tenant CRUD
│   ├── core/                     # Core infrastructure
│   │   ├── __init__.py
│   │   ├── config.py            # Pydantic Settings (all env vars)
│   │   ├── database.py          # SQLAlchemy async engine + session
├── encryption.py        # Fernet symmetric encryption for subscription secrets
│   │   ├── input_validation.py  # Centralized field validators
│   │   ├── phone.py             # Phone normalizer utility
│   │   ├── redis_client.py      # Redis connection manager + failover
│   │   └── security.py          # JWT, bcrypt, API key helpers
│   ├── crud/                     # Data access layer
│   │   ├── __init__.py
│   │   └── users.py             # User queries (by username, id, phone)
│   ├── models/                   # SQLAlchemy ORM models
│   │   ├── __init__.py          # Exports all models
│   │   ├── base.py              # DeclarativeBase + TimestampMixin
│   │   ├── user.py              # User (polymorphic role)
│   │   ├── master_profile.py    # MasterProfile (1:1 with User)
│   │   ├── tenant.py            # Canonical Tenant (owner_user_id → User, client_prefix)
│   │   ├── client.py            # Tenant-owned Client profile
│   │   ├── service.py           # Tenant catalog service
│   │   ├── plan.py              # Service catalog plan
├── subscription.py       # Subscription, SubscriptionEvent, SubscriptionReminderLog, SubscriptionReminderSettings
│   │   └── refresh_session.py   # RefreshSession (1:N with User)
│   ├── schemas/                  # Pydantic schemas (request/response)
│   │   ├── __init__.py
│   │   ├── auth.py              # LoginRequest, TokenResponse, IdentifyResponse
│   │   ├── catalog.py           # Service/plan request and response schemas
│   │   ├── dashboard.py         # MasterDashboardResponse, TenantDashboardResponse, ClientDashboardResponse
│   │   ├── client.py            # ClientCreate, ClientUpdate, ClientResponse
│   │   ├── me.py                # ProfileResponse, ProfileUpdate, PasswordChange
├── subscription.py      # Subscription request/response schemas + reminder payloads
│   │   ├── tenant.py            # TenantCreate, TenantUpdate, TenantResponse, etc.
│   │   └── whatsapp.py          # WhatsAppConsoleRequest, WhatsAppConsoleResponse
│   └── services/                 # Business logic layer
│       ├── __init__.py
│       ├── auth_service.py      # Authenticate, token creation, refresh, revoke
│       ├── catalog_service.py   # Tenant-scoped catalog CRUD/validation
│       ├── contingency_reply_policy.py  # Degraded state reply text constants
│       ├── evolution_client.py  # Evolution API HTTP client
│       ├── client_service.py    # Client CRUD + technical username sync
│       ├── profile_service.py   # Profile get/update, password change
├── subscription_service.py    # Subscription CRUD + lifecycle operations
├── subscription_job_service.py  # Lifecycle job + reminder payloads
│       ├── tenant_service.py    # Tenant CRUD + client prefix sync + Evolution lifecycle
│       ├── whatsapp_auth_session_service.py  # Auth session + lockout Redis primitives
│       ├── whatsapp_console_service.py       # Console flow routing + templates
│       ├── whatsapp_master_console_facade.py # Auth-orchestrator facade
│       └── whatsapp_session_service.py       # Ephemeral conversation session state
├── alembic/                      # Database migrations
│   ├── env.py
│   ├── versions/
│   │   ├── cd1efe74cae4_initial_schema.py
│   │   ├── cd2efe74cae5_normalize_phone_values.py
│   │   ├── cd3efe74cae6_tenant_catalog_rls.py
│   │   └── cd6efe74cae9_add_client_prefix_and_clients.py
│   └── script.py.mako
├── scripts/                      # Utility scripts
│   └── seed.py                   # Master user seeder
├── tests/                        # Pytest test suite
│   ├── conftest.py              # Fixtures: DB, client, users
│   ├── test_auth.py
│   ├── test_catalog.py
│   ├── test_contingency_reply_policy.py
│   ├── test_evolution_client.py
│   ├── test_input_validation_policy.py
│   ├── test_phone_normalization_migration.py
│   ├── test_phone_normalizer.py
│   ├── test_profile.py
│   ├── test_redis_connection_manager.py
│   ├── test_redis_failover_policy.py
│   ├── test_rls_policy_sql.py
│   ├── test_tenants.py
├── test_subscriptions.py
│   ├── test_whatsapp_auth_session_service.py
│   ├── test_whatsapp_create_flow.py
│   ├── test_whatsapp_credential_auth_flow.py
│   ├── test_whatsapp_edit_flow.py
│   ├── test_whatsapp_endpoint.py
│   ├── test_whatsapp_lifecycle_flow.py
│   ├── test_whatsapp_list_select_flow.py
│   ├── test_whatsapp_logout_flow.py
│   ├── test_whatsapp_menu_flow.py
│   └── test_whatsapp_session_service.py
├── pyproject.toml               # Python project config (deps, tool config)
├── uv.lock                      # Lock file (uv package manager)
├── .env.example                 # Environment variable template
└── .python-version              # Python 3.12
```

## Entry Points

- **FastAPI application**: `app/main.py` — `uv run uvicorn app.main:app`
- **Alembic migrations**: `uv run alembic upgrade head`
- **Seed script**: `uv run python -m scripts.seed`
- **Tests**: `uv run pytest -v`
