# Phase 2: Redis Conversation Session

**Complexity:** M
**Dependencies:** Phase 1

## Objective

- Build the Redis Conversation Session abstraction that stores ephemeral WhatsApp Master Console state keyed by Master phone number.

## Preconditions

- Redis config and client lifecycle exist.
- Redis architectural decision is documented.
- Existing backend tests pass.

## Tasks

1. Context: inspect existing service patterns and test fixtures.
2. Implement: define the conversation session shape for flow, step, selected Tenant, temporary input, and Tenant index map.
3. Implement: create a session service that can get a session by phone.
4. Implement: add create/update behavior that writes session JSON to Redis.
5. Implement: ensure session writes apply a 30-minute TTL.
6. Implement: add merge/update behavior for temporary data and selection maps.
7. Implement: add clear behavior for `0`, `menu`, `menú`, and `cancelar` callers to use later.
8. Test: add tests for session creation and retrieval.
9. Test: add tests for update/merge behavior.
10. Test: add tests for clear behavior and TTL application.
11. Verify: run the new session service tests and full backend suite.

## Verification

- Commands:
  - `cd backend && uv run pytest backend/tests/test_whatsapp_session_service.py -v`
  - `cd backend && uv run pytest -v`
- Expected results:
  - Session creation stores retrievable state by phone.
  - Updates preserve expected existing state and change only intended fields.
  - Clear removes the session key.
  - TTL is set on session writes.
  - Full backend suite remains green.

## Exit Criteria

- Redis Conversation Session service exists behind a small testable interface.
- Phone-keyed session state supports all PRD fields needed by later phases.
- 30-minute TTL behavior is covered by tests.
- No PostgreSQL persistence is introduced for conversational state.
