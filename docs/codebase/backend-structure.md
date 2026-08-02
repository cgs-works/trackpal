# Backend Codebase Structure

```
backend/
├── app/                          # Application package
│   ├── __init__.py
│   ├── main.py                   # FastAPI app entrypoint
│   │           ├── __init__.py
│   │           ├── auth.py
│   │           ├── catalog.py
│   │           ├── demos.py              # Master-only Demo Tenant lifecycle management
│   │           ├── clients.py
│   │           ├── code_services.py   # Code-services governance (global + tenant)
│   │           ├── access_control.py  # Tenant access-control blocks (list, create, delete)
│   │           ├── dashboard.py
│   │           ├── export.py          # Tenant Data Export self-service endpoints (/me/export/*)
│   │           ├── tenant_export.py   # Master-scoped Tenant Data Export (/tenants/{id}/export/*)
│   │           ├── help.py
│   │           ├── i18n.py       # GET /i18n/catalog
│   │           ├── me.py              # Includes /me/delete-account (Tenant Admin self-deletion)
│   │           ├── tenants.py         # Updated: /tenants/{id}/delete with step-up + destructive word
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
│   │           ├── mailbox.py               # Tenant mailbox CRUD/test/disconnect endpoints
│   │           ├── whatsapp_link.py         # Tenant WhatsApp self-linking endpoints
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
│   │   ├── demo_guardrail.py      # Demo allowlist and stable blocked-operation policy
│   │   ├── phone.py               # normalize_phone
│   │   ├── security.py            # bcrypt, JWT, refresh tokens
│   │   ├── tenant_plan.py          # TenantPlan type, valid plans, normalize helper
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
│   │   ├── blocked_client.py               # Tenant-scoped blocked clients for unregistered identities (renamed from client_messaging_block)
│   │   ├── export_job.py                   # Tenant-scoped export job/artifact metadata
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
│   │   ├── blocked_clients_repository.py   # Blocked client CRUD + block enforcement (renamed from client_messaging_block_repository)
│   │   ├── clients_repository.py
│   │   ├── code_services_repository.py      # Code-service global + tenant data
│   │   ├── export_jobs_repository.py         # Export job CRUD, cooldown checks, lifecycle transitions
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
│   │   ├── access_control.py           # Access-control block schemas
│   │   ├── code_services.py                # Code-service governance schemas
│   │   ├── dashboard.py
│   │   ├── mailbox.py
│   │   ├── me.py
│   │   ├── tenant.py
│   │   ├── demo.py
│   │   ├── whatsapp.py
│   │   └── subscription/          # Package: create_update, responses
│   │       ├── __init__.py
│   │       ├── create_update.py
│   │       └── responses.py
│   └── services/                  # All services organized as packages
│       ├── __init__.py            # Re-exports for stable public API
│       ├── access_control_service.py  # Block/unblock + codigo session cleanup
│       ├── auth_service/
│       ├── demo_lifecycle_service.py     # Activation, 48-hour expiry, heartbeat metadata, credential version checks
│       ├── demo_management_service.py    # Master Demo Tenant identity and credential lifecycle
│       ├── catalog_service/
│       ├── client_service/
│       ├── contingency_reply_policy/
│       ├── dashboard_service/     # Dashboard response assembly (package)
│       ├── evolution_client/
│       ├── imap_service.py        # Internal Gmail connection-test adapter (used by app_password flow)
│       ├── lookup_execution_coordinator/ # Queue acceleration, leases, dispatch, and reconciliation
│       ├── lookup_executor_transport/    # Signed/encrypted executor HTTP transport
│       ├── lookup_executor_registry.py   # Master registry lifecycle and hosting-password controls
│       ├── mailbox_cleanup.py     # Retention/cleanup loop
│       ├── mailbox_app_password.py  # Gmail app-password validation and connection
│       ├── profile_service/
│       ├── subscription_job_service/
│       ├── subscription_service/
│       ├── export_service.py           # Tenant Data Export orchestration: create, claim, cancel, finalise
│       ├── export_worker.py            # Background worker that builds ZIP and uploads to R2
│       ├── export_cleanup_worker.py    # Periodic cleanup of expired export objects
│       ├── export_storage/             # Storage adapter: R2 private upload, metadata, delete, presigned GET
│       │   ├── __init__.py
│       │   ├── _config.py
│       │   ├── _exceptions.py
│       │   ├── _fake.py
│       │   ├── _keys.py
│       │   ├── _protocol.py
│       │   └── _r2.py
│       ├── step_up_limiter.py          # Three-attempt/fifteen-minute rate limiter for export/deletion step-up
│       ├── tenant_console_protocols/
│       ├── tenant_service/
│       │   └── deletion.py             # Tenant self-deletion and Master deletion coordinator: export cancel, R2 purge, Evolution delete, DB cascade, session teardown
│       ├── whatsapp_auth_session_service/
│       ├── whatsapp_client_console_facade/  # Client WhatsApp console (read-only)
│       ├── whatsapp_console_service/
│       ├── whatsapp_master_console_facade/
│       ├── whatsapp_session_service/
│       ├── whatsapp_tenant_console_facade/
│       ├── whatsapp_link_service.py     # Tenant WhatsApp self-linking orchestration
│       ├── whatsapp_navigation.py       # Shared navigation helpers (is_cancel, is_back, is_next, screen stack)
│       └── whatsapp_tenant_console_service/ # Includes codigo_flow.py, access_control_flow.py for mailbox lookup + access control
│       ├── e014fe74cab4_add_tenant_help_acknowledgements.py  # Tour release acknowledgement storage
│       ├── e015fe74cab5_add_export_jobs.py                     # Tenant data export job/artifact table
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
│       ├── ce10fe74caa10_add_client_messaging_blocks_table.py  # Client Messaging Blocks table (renamed to blocked_clients in ce10fe74caa11)
│       ├── ce10fe74caa11_rename_client_messaging_blocks_to_blocked_clients.py  # Rename to blocked_clients
│       ├── e011fe74cab1_add_tenant_plan.py  # Add plan column to tenants
│       └── e017fe74cab7_add_demo_tenant_lifecycle.py # Demo identity/lifecycle columns, constraints, and index
├── scripts/
│   └── seed.py
├── tests/
│   ├── conftest.py
│   ├── test_auth.py
│   ├── test_demo_guardrails.py          # Direct route-family containment and explicit allowlist
│   ├── test_demo_integration_gate.py    # Creation/login/lifecycle/containment narrative
│   ├── test_demo_tenant_management.py   # Master create/list/credentials/delete lifecycle
│   ├── test_demo_tenant_persistence.py  # Model and migration constraints
│   ├── test_catalog.py
│   ├── test_client_console_service.py  # 26 tests
│   ├── test_whatsapp_navigation.py     # 7 tests — shared navigation primitives
│   ├── test_whatsapp_console_navigation_contract.py  # 3 tests — 8/9/0 convention enforcement
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
│   ├── test_access_control_api.py # Access-control API tests
│   ├── test_tenant_plan.py       # Tenant plan create/update/auth/gate tests
│   ├── test_mailbox_persistence.py
│   ├── test_mailbox_oauth_imap.py
│   ├── test_mailbox_lookup_api.py
│   ├── test_mailbox_cleanup.py
│   └── test_mailbox_metrics.py
├── pyproject.toml
├── uv.lock
├── .env.example
├── render.yaml
├── .python-version

worker/
├── app/                          # Independently deployable Lookup Executor
├── tests/                        # Worker protocol and pipeline tests
├── Dockerfile                    # Python 3.12 non-root image
├── render.yaml                   # Render Free Web Service Blueprint
├── README.md                     # Local operation and enrollment guide
└── CONTEXT.md                   # Worker domain boundary and secret rules
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
| `app/core/tenant_plan.py` | TenantPlan type, valid plans, normalize helper |
| `app/core/errors.py` | UserFacingError and translate_error |
| `app/core/demo_guardrail.py` | Rejects Demo JWT access outside the auth/password/Help/i18n/heartbeat allowlist |
| `app/services/demo_lifecycle_service.py` | Activates the single 48-hour window and resolves expiry/credential-version lifecycle outcomes |
| `app/services/demo_management_service.py` | Master-only Demo identity creation, credential replacement, listing, and deletion |
| `app/api/v1/endpoints/code_services.py` | Code-services global + tenant selection endpoints |
| `app/core/input_validation/` | Shared validation package: contact, phone, general validators |
| `app/services/whatsapp_tenant_console_service/` | Tenant WhatsApp menu routing (package, 18 modules) |
| `app/services/whatsapp_tenant_console_facade/` | Tenant console phone-based orchestration (package) |
| `app/services/whatsapp_client_console_facade/` | Client WhatsApp read-only console (package) |
| `app/services/whatsapp_link_service.py` | Tenant WhatsApp connection self-linking orchestration |
| `app/services/dashboard_service/` | Dashboard response assembly per role (package) |
| `app/services/subscription_service/` | Subscription CRUD and lifecycle operations (package) |
| `app/services/access_control_service.py` | Block/unblock identities + codigo session cleanup |
| `app/services/subscription_job_service/` | Cleanup job and reminder payloads (package) |
| `app/services/lookup_execution_coordinator/` | External executor selection, leases, dispatch, callback reconciliation, and Redis recovery |
| `app/services/lookup_executor_transport/` | Signed/encrypted challenge, handoff, and callback transport |
| `app/services/lookup_executor_registry.py` | Master-only enrollment, verification, activation, rotation, and deletion |
| `app/services/mailbox_app_password.py` | Gmail app-password validation and connection testing |
| `app/services/tenant_console_protocols/` | Protocols for tenant console DI (package) |
| `app/services/imap_service.py` | Internal Gmail IMAP connection-test adapter (used by app_password flow) |
| `app/services/mailbox_cleanup.py` | Periodic retention/cleanup loop for stale jobs and delivery logs |
