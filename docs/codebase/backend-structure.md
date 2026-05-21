# Backend Codebase Structure

```
backend/
├── app/                          # Application package
│   ├── main.py                   # FastAPI app entrypoint
│   ├── api/
│   │   ├── dependencies.py       # get_current_user, require_role, verify_n8n_api_key_header
│   │   └── v1/
│   │       ├── router.py         # Aggregates all endpoint routers
│   │       └── endpoints/
│   │           ├── auth.py
│   │           ├── catalog.py
│   │           ├── clients.py
│   │           ├── dashboard.py
│   │           ├── integrations.py
│   │           ├── me.py
│   │           ├── subscriptions.py
│   │           └── tenants.py
│   ├── core/
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── encryption.py
│   │   ├── input_validation.py
│   │   ├── phone.py
│   │   ├── redis_client.py
│   │   └── security.py
│   ├── crud/
│   │   └── users.py
│   ├── models/
│   │   ├── base.py
│   │   ├── client.py
│   │   ├── master_profile.py
│   │   ├── plan.py
│   │   ├── refresh_session.py
│   │   ├── service.py
│   │   ├── subscription.py
│   │   ├── tenant.py
│   │   └── user.py
│   ├── schemas/
│   │   ├── auth.py
│   │   ├── catalog.py
│   │   ├── client.py
│   │   ├── dashboard.py
│   │   ├── me.py
│   │   ├── subscription.py
│   │   ├── tenant.py
│   │   └── whatsapp.py
│   └── services/
│       ├── auth_service.py
│       ├── catalog_service.py
│       ├── client_service.py
│       ├── contingency_reply_policy.py
│       ├── evolution_client.py
│       ├── profile_service.py
│       ├── subscription_job_service.py
│       ├── subscription_service.py
│       ├── tenant_console_protocols.py
│       ├── tenant_service.py
│       ├── whatsapp_auth_session_service.py
│       ├── whatsapp_console_service.py
│       ├── whatsapp_master_console_facade.py
│       ├── whatsapp_session_service.py
│       ├── whatsapp_tenant_console_facade.py
│       └── whatsapp_tenant_console_service.py
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
| `app/api/v1/endpoints/subscriptions.py` | Subscription CRUD, lifecycle, reminder endpoints |
| `app/core/encryption.py` | Fernet encryption for subscription secrets |
| `app/services/whatsapp_tenant_console_service.py` | Tenant WhatsApp menu routing |
| `app/services/whatsapp_tenant_console_facade.py` | Tenant console phone-based orchestration |
| `app/services/subscription_service.py` | Subscription CRUD and lifecycle operations |
| `app/services/subscription_job_service.py` | Cleanup job and reminder payloads |
| `app/services/tenant_console_protocols.py` | Protocols for tenant console DI |
