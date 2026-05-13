# Phase 3: n8n/backend Contract and Transport Endpoint

**Complexity:** M
**Dependencies:** Phase 2

## Objective

- Create the backend WhatsApp Master Console entrypoint for n8n and simplify n8n so it transports messages without owning CRUD or conversation state.

## Preconditions

- Redis Conversation Session service exists.
- Existing n8n workflow export is available.
- Existing n8n identify/API-key patterns are understood.

## Tasks

1. Context: inspect current integration endpoint and auth dependency patterns.
2. Context: inspect current n8n workflow parse/send behavior.
3. Implement: define request schema for normalized phone, message text, and optional Evolution Instance context.
4. Implement: define response schema with the reply text n8n must send.
5. Implement: add backend console endpoint protected by the n8n API key.
6. Implement: identify the caller by phone and allow only Master actions.
7. Implement: return an access-denied reply for non-Master or unknown users that n8n can relay safely.
8. Implement: call a skeleton backend console service that returns a placeholder/main-menu reply for Master messages.
9. n8n: simplify workflow to Webhook → Parse → backend console call → Evolution API Send.
10. n8n: remove direct Tenant CRUD/menu state behavior from the workflow.
11. Test: add endpoint contract tests for auth, Master, non-Master, and response shape.
12. Verify: validate the n8n workflow and run endpoint tests.

## Verification

- Commands:
  - `cd backend && uv run pytest backend/tests/test_whatsapp_endpoint.py -v`
  - `cd backend && uv run pytest -v`
  - Validate the updated n8n workflow with the available n8n validation tool.
- Expected results:
  - Missing or wrong API key returns unauthorized.
  - Master phone receives a valid reply payload.
  - Non-Master phone receives a relayable access-denied reply and no CRUD action occurs.
  - n8n workflow has no persistent conversation state or direct Tenant CRUD branches.

## Exit Criteria

- Backend exposes a stable n8n WhatsApp console contract.
- n8n transport workflow can send backend replies through Evolution API.
- n8n no longer owns Master Console menu state or direct Tenant CRUD logic.
- Contract tests pass.
