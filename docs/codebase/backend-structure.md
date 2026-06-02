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
│   │           ├── code_services.py   # Code-services governance (global + tenant)
│   │           ├── dashboard.py
│   │           ├── i18n.py       # GET /i18n/catalog
│   │           ├── me.py
│   │           ├── tenants.py
│   │           ├── integrations/ # Package: adapter, console (split), identify, mail lookups
│   │           │   ├── __init__.py
│   │           │   ├── adapter.py
│   │           │   ├── console.py               # Entrypoint + routing + from_me routing
│   │           │   ├── console_handlers.py      # Flow handlers + unauthenticated codigo + context shortcut orchestration
│   │           │   ├── console_context_shortcut.py # Client Context Shortcut: creating, active, inactive, subscription flows
│   │           │   ├── console_modes.py         # Ambiguity mode selection
│   │           │   ├── identify.py
│   │           │   └── mail_lookups.py          # n8n create/poll mailbox lookup jobs
│   │           ├── _mailbox_helpers.py      # Shared mailbox response helpers
│   │           ├── mailbox.py               # Tenant mailbox CRUD/test/OAuth endpoints
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
│   │   ├── metrics.py             # lightweight registry + /metrics output
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
│   │   ├── client_messaging_block.py        # Tenant-scoped Client Messaging Blocks for unregistered identities
│   │   ├── code_service_global_status.py    # Global code-service activation
│   │   ├── tenant_mailbox.py
│   │   ├── tenant_code_service_selection.py # Per-tenant code-service selection
│   │   ├── mail_lookup_job.py
│   │   ├── mail_code_delivery_log.py
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
│   │   ├── client_messaging_block_repository.py  # Client Messaging Block CRUD + block enforcement
│   │   ├── clients_repository.py
│   │   ├── code_services_repository.py      # Code-service global + tenant data
│   │   ├── mailbox_config_repository.py
│   │   ├── mailbox_dedupe_repository.py
│   │   ├── mailbox_lookup_repository.py
│   │   ├── profiles_repository.py
│   │   ├── sessions_repository.py
│   │   ├── tenants_repository.py
│   │   └── users_repository.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── catalog.py
│   │   ├── client.py
│   │   ├── code_services.py                # Code-service governance schemas
│   │   ├── dashboard.py
│   │   ├── mailbox.py
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
│       ├── dashboard_service/     # Dashboard response assembly (package)
│       ├── evolution_client/
│       ├── imap_service.py        # IMAP connection test helper
│       ├── mail_code_extractor/   # Regex catalog v1 + pure extractor + per-service catalogs
│       ├── mail_lookup_worker/    # Queue, providers (google/microsoft/imap), worker pipeline
│       ├── mailbox_cleanup.py     # Retention/cleanup loop
│       ├── oauth_service/         # Google/Microsoft OAuth start/callback/refresh + revocation
│       ├── profile_service/
│       ├── subscription_job_service/
│       ├── subscription_service/
│       ├── tenant_console_protocols/
│       ├── tenant_service/
│       ├── whatsapp_auth_session_service/
│       ├── whatsapp_client_console_facade/  # Client WhatsApp console (read-only)
│       ├── whatsapp_console_service/
│       ├── whatsapp_master_console_facade/
│       ├── whatsapp_session_service/
│       ├── whatsapp_tenant_console_facade/
│       └── whatsapp_tenant_console_service/ # Includes codigo_flow.py for mailbox lookup dialog
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
│       ├── cd7efe74caa0_add_subscriptions.py
│       ├── cd8efe74caa1_add_tenant_locale.py  # Add locale column to tenants
│       ├── cd9efe74caa2_rename_clients_local_username_to_username.py  # Canonical client username
│       ├── cdaefe74caa3_add_tenant_evolution_instance_token.py
│       ├── cdaefe74caa4_add_whatsapp_lid_columns.py
│       ├── cdbfefe74caa5_add_tenant_mailbox_tables.py
│       ├── cdbfefe74caa6_add_target_email_and_fix_dedupe_unique.py
│       ├── cdbfefe74caa7_add_rls_to_core_and_mail_tables.py  # RLS on core + mailbox tables
│       ├── cdc0fe74caa8_add_code_service_tables.py  # Code-service governance tables
│       └── ce10fe74caa10_add_client_messaging_blocks_table.py  # Client Messaging Blocks table
├── scripts/
│   └── seed.py
├── tests/
│   ├── conftest.py
│   ├── test_auth.py
│   ├── test_catalog.py
│   ├── test_client_console_service.py  # 22 tests
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
│   ├── test_whatsapp_instance_alias.py
│   ├── test_whatsapp_session_service.py
│   ├── test_code_services.py    # Code-services governance tests
│   ├── test_mailbox_persistence.py
│   ├── test_mailbox_oauth_imap.py
│   ├── test_mail_code_extractor.py
│   ├── test_mailbox_lookup_worker.py
│   ├── test_mailbox_lookup_api.py
│   ├── test_mailbox_cleanup.py
│   └── test_mailbox_metrics.py
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
| `app/api/v1/endpoints/code_services.py` | Code-services global + tenant selection endpoints |
| `app/core/input_validation/` | Shared validation package: contact, phone, general validators |
| `app/services/whatsapp_tenant_console_service/` | Tenant WhatsApp menu routing (package, 18 modules) |
| `app/services/whatsapp_tenant_console_facade/` | Tenant console phone-based orchestration (package) |
| `app/services/whatsapp_client_console_facade/` | Client WhatsApp read-only console (package) |
| `app/services/dashboard_service/` | Dashboard response assembly per role (package) |
| `app/services/subscription_service/` | Subscription CRUD and lifecycle operations (package) |
| `app/services/subscription_job_service/` | Cleanup job and reminder payloads (package) |
| `app/services/mail_lookup_worker/` | Async mailbox lookup worker, provider fetchers (google/microsoft/imap), retries, dedupe pipeline, Redis queue |
| `app/services/oauth_service/` | Google/Microsoft OAuth start/callback/refresh and revocation handling |
| `app/services/mail_code_extractor/` | Regex-based code extraction: catalog_v1 (multi-service) + per-service catalog files (netflix, disney, spotify, etc.) + pure extractor |
| `app/services/tenant_console_protocols/` | Protocols for tenant console DI (package) |
| `app/services/imap_service.py` | IMAP connection test helper |
| `app/services/mailbox_cleanup.py` | Periodic retention/cleanup loop for stale jobs and delivery logs |
