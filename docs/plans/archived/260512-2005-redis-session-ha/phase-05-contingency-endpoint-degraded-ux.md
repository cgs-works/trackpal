# Phase 5: Contingency Endpoint Behavior and Degraded UX

**Complexity:** M  
**Dependencies:** Phase 4

## Objective

Make WhatsApp console endpoint behavior explicit and safe during Redis failover: reset with a clear contingency reply when backup lacks the active session, and return a relayable unavailable reply when both Redis stores fail.

## Preconditions

- Redis manager/failover policy surfaces whether an operation used primary or backup and whether both stores failed.
- Session lifecycle cleanup is deterministic.
- n8n remains transport-only and relays backend `reply` text.

## Tasks

1. Add a `ContingencyReplyPolicy` in `backend/app/services/whatsapp_session_service.py`, `backend/app/services/whatsapp_console_service.py`, or a small dedicated module.
2. Define Spanish reply text for backup-missing-session reset. It must clearly say the session was restarted due to temporary failover/contingency and ask the Master to choose an option again.
3. Define Spanish reply text for total Redis outage. It must clearly say the console is temporarily unavailable and the Master should retry later.
4. Ensure both reply texts are relayable through existing `WhatsAppConsoleResponse.reply` without requiring n8n workflow changes.
5. Add a manager/session result signal such as `store_name`, `used_backup`, or an exception type so the endpoint/console can distinguish “no session found on backup during failover” from a normal new session on primary.
6. In `backend/app/api/v1/endpoints/integrations.py`, when both Redis stores are unavailable, return the total-unavailable reply and do not call `WhatsAppConsoleService.process_message()`.
7. In the console/session flow, when failover is active and `get_session()` returns missing for an in-progress-looking request, return the contingency reset reply plus menu, and create/delete state only as needed to start clean on the active backup.
8. Ensure backup-missing-session behavior does not pretend to continue a multi-step flow from missing state.
9. Ensure both-store failure during `save_session()` or `clear_session()` after processing is handled safely: do not return success for a business mutation if session cleanup/persistence failure would leave the conversation inconsistent, unless the mutation already committed and the reply clearly resets/unavailable according to policy.
10. Add endpoint tests in `backend/tests/test_whatsapp_endpoint.py` for primary success, failover to backup with missing session, and both Redis unavailable.
11. Add session/console tests proving failover with missing backup state returns reset text rather than falling back to stateless menu continuation.
12. Add tests proving access denied/non-Master behavior still does not expose Redis errors or attempt console state transitions unnecessarily.
13. Confirm HTTP status remains `200` for relayable degraded replies, while invalid API key remains `401` as today.

## Verification

- Commands:
  - `cd backend && uv run pytest tests/test_whatsapp_endpoint.py -v`
  - `cd backend && uv run pytest tests/test_whatsapp_session_service.py tests/test_redis_connection_manager.py tests/test_redis_failover_policy.py -v`
  - `cd backend && uv run pytest -v`
- Expected results:
  - Primary-normal requests behave as before.
  - Failover to backup with no session returns an explicit session-reset contingency reply.
  - Both Redis stores unavailable returns an explicit temporary-unavailable reply.
  - Endpoint does not process WhatsApp console flows statelessly when Redis is unavailable.
  - Invalid API key still returns `401`.

## Exit Criteria

- Degraded behavior is deterministic, user-visible, and covered by tests.
- Backup-missing-session and total-outage cases have different replies.
- n8n can relay all degraded replies with the existing response schema.
- No stateless fallback path exists for the WhatsApp Master Console.
