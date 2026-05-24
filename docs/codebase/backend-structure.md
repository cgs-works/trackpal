# Backend Codebase Structure

```
backend/
├── app/                          # Application package
│   ├── __init__.py
│   ├── main.py                   # FastAPI app entrypoint
│   ├── api/
│   │   ├── __init__.py
│   │   ├── dependencies.py       # get_current_user, require_role, verify_n8n_api_key_header
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── router.py         # Aggregates all endpoint routers
│   │       └── endpoints/
│   │           ├── __init__.py
│   │           ├── auth.py
│   │           ├── catalog.py
│   │           ├── clients.py
│   │           ├── dashboard.py
│   │           ├── i18n.py       # GET /i18n/catalog
│   │           ├── me.py
│   │           ├── tenants.py
│   │           ├── integrations/ # Package: adapter, console, identify
│   │           │   ├── __init__.py
│   │           │   ├── adapter.py
│   │           │   ├── console.py
│   │           │   └── identify.py
│   │           └── subscriptions/ # Package: crud, lifecycle, jobs, settings, router
│   │               ├── __init__.py
│   │               ├── _common.py
│   │               ├── crud.py
│   │               ├── jobs.py
│   │               ├── lifecycle.py
│   │               ├── router.py
│   │               └── settings.py
│   ├── core/
│   │   ├── __init__.py            # VALID_LOCALES
│   │   ├── config.py              # Pydantic Settings
│   │   ├── database.py            # AsyncSession factory
│   │   ├── encryption.py          # Fernet encrypt/decrypt
│   │   ├── errors.py              # UserFacingError, translate_error
│   │   ├── phone.py               # normalize_phone
│   │   ├── security.py            # bcrypt, JWT, refresh tokens
│   │   ├── i18n/                  # Package: engine + 6 catalog files
│   │   │   ├── __init__.py
│   │   │   └── engine.py, catalogs_en_general.py, catalogs_en_frontend.py,
│   │   │       catalogs_en_wa.py, catalogs_es_general.py, catalogs_es_frontend.py,
│   │   │       catalogs_es_wa.py
│   │   ├── input_validation/      # Package: validators by domain
│   │   │   ├── __init__.py
│   │   │   ├── contact_validators.py
│   │   │   ├── errors.py
│   │   │   ├── general_validators.py
│   │   │   └── phone_utils.py
│   │   └── redis_client/          # Package: manager, lifespan, policy, types
│   │       ├── __init__.py
│   │       ├── lifespan.py
│   │       ├── manager.py
│   │       ├── policy.py
│   │       └── types.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── client.py
│   │   ├── master_profile.py
│   │   ├── plan.py
│   │   ├── refresh_session.py
│   │   ├── service.py
│   │   ├── subscription.py
│   │   ├── tenant.py
│   │   └── user.py
│   ├── repositories/              # Data access layer (migrated from crud/)
│   │   ├── __init__.py
│   │   ├── catalog_repository.py
│   │   ├── clients_repository.py
│   │   ├── profiles_repository.py
│   │   ├── sessions_repository.py
│   │   ├── tenants_repository.py
│   │   └── users_repository.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── catalog.py
│   │   ├── client.py
│   │   ├── dashboard.py
│   │   ├── me.py
│   │   ├── tenant.py
│   │   ├── whatsapp.py
│   │   └── subscription/          # Package: create_update, responses
│   │       ├── __init__.py
│   │       ├── create_update.py
│   │       └── responses.py
│   └── services/                  # All services organized as packages
│       ├── __init__.py            # Re-exports for stable public API
│       ├── auth_service/
│       ├── catalog_service/
│       ├── client_service/
│       ├── contingency_reply_policy/
│       ├── evolution_client/
│       ├── profile_service/
│       ├── subscription_job_service/
│       ├── subscription_service/
│       ├── tenant_console_protocols/
│       ├── tenant_service/
│       ├── whatsapp_auth_session_service/
│       ├── whatsapp_console_service/
│       ├── whatsapp_master_console_facade/
│       ├── whatsapp_session_service/
│       ├── whatsapp_tenant_console_facade/
│       └── whatsapp_tenant_console_service/
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       ├── cd1efe74cae4_initial_schema.py
│       ├── cd2efe74cae5_normalize_phone_values.py
│       ├── cd3efe74cae6_tenant_catalog_rls.py
│       ├── cd4efe74cae7_fix_tenants_master_rls.py
│       ├── cd5efe74cae8_drop_tenant_profiles.py
│       ├── cd6efe74cae9_add_client_prefix_and_clients.py
│       └── cd7efe74caa0_add_subscriptions.py
├── scripts/
│   └── seed.py
├── tests/
│   ├── conftest.py
│   ├── test_auth.py
│   ├── test_catalog.py
│   ├── test_clients.py
│   ├── test_contingency_reply_policy.py
│   ├── test_evolution_client.py
│   ├── test_i18n.py
│   ├── test_input_validation_policy.py
│   ├── test_phone_normalization_migration.py
│   ├── test_phone_normalizer.py
│   ├── test_profile.py
│   ├── test_redis_connection_manager.py
│   ├── test_redis_failover_policy.py
│   ├── test_rls_policy_sql.py
│   ├── test_subscriptions.py
│   ├── test_tenant_console_service.py
│   ├── test_tenants.py
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
├── pyproject.toml
├── uv.lock
├── .env.example
├── render.yaml
└── .python-version
```

## Entry Points

| Entry point | Command |
|-------------|---------|
| FastAPI application | `uv run uvicorn app.main:app` |
| Alembic migrations | `uv run alembic upgrade head` |
| Seed script | `uv run python -m scripts.seed` |
| Tests | `uv run pytest -v` |

## Key Modules

| Module | Responsibility |
|--------|---------------|
| `app/api/v1/endpoints/subscriptions/` | Subscription CRUD, lifecycle, reminder endpoints (package) |
| `app/core/encryption.py` | Fernet encryption for subscription secrets |
| `app/core/errors.py` | UserFacingError and translate_error |
| `app/services/whatsapp_tenant_console_service/` | Tenant WhatsApp menu routing (package) |
| `app/services/whatsapp_tenant_console_facade/` | Tenant console phone-based orchestration (package) |
| `app/services/subscription_service/` | Subscription CRUD and lifecycle operations (package) |
| `app/services/subscription_job_service/` | Cleanup job and reminder payloads (package) |
| `app/services/tenant_console_protocols/` | Protocols for tenant console DI (package) |
