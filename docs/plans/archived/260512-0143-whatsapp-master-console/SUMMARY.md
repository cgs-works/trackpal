# Implementation Plan: WhatsApp Master Console

## Objective

- Build a WhatsApp Master Console that lets the Master manage Tenants from WhatsApp with backend-owned conversation logic and Redis-backed ephemeral session state.
- Replace n8n-owned menu/session behavior with a stateless transport workflow that receives WhatsApp messages, calls the backend, and sends the returned reply.
- Link to PRD: `docs/prds/260512-0143-whatsapp-master-console/PRD.md`

## Scope

### In scope

- Redis configuration for backend conversational state.
- Redis Conversation Session service with 30-minute TTL and reset semantics.
- Backend n8n console endpoint protected by `X-API-Key`.
- Backend-owned WhatsApp Master Console flow logic.
- n8n workflow simplification to transport-only behavior.
- Main menu, help, cancellation, and fallback messages.
- Tenant list/select/detail flow with numbered selection maps in Redis.
- Create Tenant flow with optional fields, password mode, confirmation, and regression coverage for the full-name bug.
- Edit Tenant flow for full name, email, phone, and Evolution Instance.
- Tenant lifecycle flows: deactivate, reactivate, delete inactive only.
- Automated tests for Redis session behavior, CRUD flows, n8n/backend contract, and regression cases.
- Documentation/ADR updates for the Redis-backed backend-owned architecture.

### Out of scope

- Customer CRUD from WhatsApp.
- Subscription CRUD from WhatsApp.
- Service catalog management from WhatsApp.
- Tenant self-service WhatsApp flows.
- Persisting conversational state in PostgreSQL.
- Reworking the Vue Master dashboard.
- Tenant QR self-service generation.
- Multi-language WhatsApp support.
- Sending real WhatsApp messages in automated tests.
- Building a generalized chatbot or AI assistant.

## Architecture & Approach

- The backend owns conversation state transitions, validation, Tenant selection, and CRUD decisions.
- Redis stores ephemeral WhatsApp conversation state keyed by Master phone number.
- n8n becomes transport only: parse inbound Evolution API payload, call the backend console endpoint, send returned reply through Evolution API.
- Tenant lifecycle behavior must reuse existing backend rules and services so WhatsApp behavior matches the dashboard.
- Destructive operations require explicit textual confirmation, e.g. `CONFIRMAR`.
- Global reset commands are `0`, `menu`, `menú`, and `cancelar`.
- Plan phases are ordered so infrastructure and contract work precede individual flows.

## Phases

- [ ] **Phase 1 [M]: Foundation and architecture alignment** — Document the Redis-backed backend-owned direction and add Redis configuration without changing product behavior.
- [ ] **Phase 2 [M]: Redis Conversation Session** — Build and test the Redis session abstraction for ephemeral WhatsApp state.
- [ ] **Phase 3 [M]: n8n/backend contract and transport endpoint** — Add the backend console endpoint and simplify n8n to stateless transport.
- [X] **Phase 4 [M]: Core navigation and menu flow** — Implement main menu, help, fallback, and global reset behavior.
- [ ] **Phase 5 [M]: List and select Tenant flow** — Implement numbered Tenant listing, Redis selection map, and Tenant detail screen.
- [ ] **Phase 6 [L]: Create Tenant flow and regression fix** — Implement guided Tenant creation and prove the full-name step no longer resets to menu.
- [ ] **Phase 7 [M]: Edit Tenant flow** — Implement contextual editing for Tenant fields from the detail screen.
- [ ] **Phase 8 [M]: Lifecycle flows** — Implement deactivate, reactivate, and delete flows with lifecycle safeguards and confirmation.

## Key Changes

- Backend settings/configuration for Redis URL and client lifecycle.
- Backend service for Redis Conversation Session state.
- Backend service for WhatsApp Master Console flow routing.
- Backend integration endpoint for n8n WhatsApp messages.
- n8n workflow export simplified to transport-only behavior.
- Tests for session service, endpoint contract, menu, CRUD flows, lifecycle flows, and regression behavior.
- ADR/docs updated to reflect backend-owned conversation logic and Redis state.

## Verification Strategy

- Backend unit/integration tests per phase using pytest.
- Full backend test suite after each phase that touches shared auth, Tenant lifecycle, or integrations.
- n8n workflow validation after transport workflow changes.
- No automated test should send real WhatsApp messages through Evolution API.

Core commands:

- `cd backend && uv run pytest -v`
- `cd backend && uv run pytest backend/tests/test_whatsapp_session_service.py -v`
- `cd backend && uv run pytest backend/tests/test_whatsapp_endpoint.py -v`
- `cd backend && uv run pytest backend/tests/test_whatsapp_menu_flow.py -v`
- `cd backend && uv run pytest backend/tests/test_whatsapp_list_select_flow.py -v`
- `cd backend && uv run pytest backend/tests/test_whatsapp_create_flow.py -v`
- `cd backend && uv run pytest backend/tests/test_whatsapp_edit_flow.py -v`
- `cd backend && uv run pytest backend/tests/test_whatsapp_lifecycle_flow.py -v`

## Dependencies

- Redis Python client for backend async Redis access.
- Redis service available in development/test/deploy environments.
- Existing TenantService and auth/identify behavior remain the source of truth for Tenant lifecycle and Master identity.
- n8n MCP/workflow validation access for updating and validating the transport workflow.

## Risks & Mitigations

- Redis unavailable → fail safely with a clear backend error; add health/config checks and keep tests isolated with a fake Redis or test double.
- Conversation state drift → centralize all transitions in the backend console service and cover every transition with tests.
- Accidental destructive action → require textual `CONFIRMAR` and show Tenant identity/status before action.
- n8n still contains stale menu logic → simplify workflow to transport-only and validate/export the workflow.
- Duplicate behavior with dashboard → reuse existing Tenant lifecycle service rules instead of creating parallel CRUD logic.
- Session key collision or phone formatting mismatch → normalize phone consistently at the n8n/backend contract boundary and test request handling.

## Open Questions

- Exact Redis deployment target for local/deployed environments.
- Exact wording for WhatsApp messages can be refined during implementation, but behavior and menu categories are fixed by the PRD.
- Whether to use a fake Redis test double or a real Redis test service in CI/development verification.
