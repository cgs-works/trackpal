# Phase 4: Session Lifecycle Policy and Cleanup

**Complexity:** M  
**Dependencies:** Phase 3

## Objective

Align WhatsApp session lifecycle behavior with the PRD: 15-minute TTL, refresh only on valid flow progress, explicit deletion on success/cancel/terminal close, and minimal Redis payload.

## Preconditions

- Session service operations route through the Redis HA manager.
- Both-store failures can be surfaced to endpoint/console handling.
- Existing WhatsApp console flow tests are green.

## Tasks

1. Confirm `settings.whatsapp_session_ttl_minutes` default is `15` in `backend/app/core/config.py`.
2. Update `backend/app/services/whatsapp_session_service.py` docstrings/tests from old 30-minute TTL assumptions to 15 minutes.
3. Add or formalize a `SessionLifecyclePolicy` in `backend/app/services/whatsapp_session_service.py` or a separate service module if it keeps the console service clearer.
4. Ensure `ConversationSession` contains only PRD-approved fields: `flow`, `step`, `selected_tenant_id`, `temp_data`, and `selection_map`, plus any unavoidable phone/key field needed internally.
5. Add a serialization guard/test that session JSON does not include raw WhatsApp payloads, inbound messages, tenant lists, or large non-minimal objects.
6. Review `backend/app/services/whatsapp_console_service.py` for every `save_session()`, `update_session()`, `create_session()`, and `clear_session()` call.
7. Change flow handling so TTL is refreshed only when a valid session is created, a valid step advances, or valid flow data changes.
8. Ensure invalid menu selections, malformed replies, access denied replies, and generic fallback/noise do not refresh TTL unless the flow explicitly requires preserving a just-created valid prompt.
9. Ensure global reset commands `0`, `menu`, `menú`, and `cancelar` call explicit delete before returning the menu.
10. Ensure successful create/edit/deactivate/reactivate/delete terminal outcomes explicitly delete session state.
11. Ensure terminal close paths after irrecoverable tenant-not-found or invalid stale selection clear session state when continuing would be unsafe.
12. Add tests in `backend/tests/test_whatsapp_session_service.py` for 900-second TTL writes, no extra fields in serialized payload, and explicit delete behavior.
13. Extend flow tests in `backend/tests/test_whatsapp_create_flow.py`, `backend/tests/test_whatsapp_edit_flow.py`, `backend/tests/test_whatsapp_lifecycle_flow.py`, and `backend/tests/test_whatsapp_menu_flow.py` to assert terminal cleanup.
14. Add tests that invalid/noise messages do not call Redis `set`/TTL refresh when no valid progress occurred.
15. Keep tenant CRUD behavior unchanged except for phone normalization from Phase 1.

## Verification

- Commands:
  - `cd backend && uv run pytest tests/test_whatsapp_session_service.py -v`
  - `cd backend && uv run pytest tests/test_whatsapp_menu_flow.py tests/test_whatsapp_create_flow.py tests/test_whatsapp_edit_flow.py tests/test_whatsapp_lifecycle_flow.py -v`
  - `cd backend && uv run pytest -v`
- Expected results:
  - Session TTL is 15 minutes (`900` seconds) by default.
  - Valid progress refreshes TTL.
  - Invalid/noise input does not keep abandoned sessions alive.
  - Cancel, completion, and unsafe terminal states delete session keys explicitly.
  - Redis payload contains only minimal approved session state.

## Exit Criteria

- Session lifecycle matches PRD TTL and cleanup rules.
- All terminal WhatsApp flows explicitly clear session state.
- Redis contains no raw WhatsApp payloads or unnecessary large data.
- Existing Tenant CRUD console behavior remains functionally unchanged.
