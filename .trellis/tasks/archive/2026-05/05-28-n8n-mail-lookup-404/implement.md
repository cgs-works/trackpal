# Implementation Plan — Fix n8n mail lookup 404

## Scope

Implement broad fix with central transaction boundary and full `codigo_flow` decoupling.

## Phase 1 — Refactor flow contract

1. Update `codigo_flow` to stop direct lookup persistence/enqueue.
2. Keep dialog responsibilities only:
   - service selection
   - target email validation
   - intent payload emission
3. Preserve current localized responses.

## Phase 2 — Centralize orchestration in handler

1. In tenant integration handler, add orchestration path for lookup intent:
   - create job (`mailbox_lookup_repository.create_job`)
   - `db.commit()` durability boundary
   - enqueue Redis
   - resolve `tenant_id`
   - clear session `pending_job_id` after full success path
2. Return `WhatsAppConsoleResponse` with `lookup_job_id` + `tenant_id` only on success.

## Phase 3 — Failure/compensation semantics

1. If enqueue fails after commit:
   - attempt compensating delete of created job
2. If compensating delete fails:
   - mark job `failed`
   - set `error_code=queue_unavailable`
   - log critical with job_id + tenant context
3. In any failure branch above:
   - do not return `lookup_job_id`
   - return existing user-safe error reply

## Phase 4 — Tests (required)

### Unit

1. `codigo_flow` no longer persists/enqueues directly.
2. Handler emits `lookup_job_id` only after successful commit+enqueue path.
3. Session cleanup occurs only after success path.

### Integration

1. End-to-end backend test:
   - trigger `codigo` final step
   - response contains `lookup_job_id`
   - same transaction window confirms row exists in `mail_lookup_jobs`
2. Poll with correct `tenant_id` finds job (not 404).
3. Poll with wrong `tenant_id` still returns 404.

## Phase 5 — Runtime verification (required)

1. Execute real n8n flow in production.
2. Capture execution IDs proving:
   - console response returns `lookup_job_id` + `tenant_id`
   - poll returns status payload, not `{"detail":"Job not found"}`
3. Attach evidence to task notes/journal.

## Commands

```bash
cd backend
uv run pytest -v tests/test_client_console_service.py
uv run pytest -v tests/test_mailbox_lookup_worker.py tests/test_mailbox_persistence.py
# plus any new/updated integration tests for n8n lookup poll path
```

## Exit Criteria

- All acceptance criteria in `prd.md` checked.
- Backend tests green for changed areas.
- n8n production evidence captured with execution IDs.
