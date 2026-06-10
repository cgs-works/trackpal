# TPL-13 — Codigo restart from awaiting_result

## Status

Approved design. This spec records the agreed behavior before implementation.

## Problem

After a codigo lookup result is sent to the user, Evolution Go may close its chat session, but TrackPal's Redis conversation session can remain alive in `awaiting_result`. If the user later sends `code`, `codigo`, or `código`, the backend currently routes that message through the active `awaiting_result` handler and replies with `wa.tenant.codigo.still_checking` instead of starting a fresh codigo flow.

This affects both:

- Tenant admin codigo sessions stored as `session:admin:{phone}`.
- Unauthenticated codigo sessions stored as `session:unreg:{tenant-prefix}:{phone|lid}`.

## Goals

- Treat `code|codigo|código` inside `awaiting_result` as an explicit request to restart codigo lookup from the service list.
- Best-effort cancel the active lookup job associated with the current Redis session before restarting.
- Preserve existing post-result menu behavior:
  - `1` retry
  - `2` back to services
  - `0` cancel
- Avoid schema changes and avoid introducing a new job status.
- Add regression coverage for tenant and unauthenticated codigo flows.

## Non-goals

- Do not add a `cancelled` job status.
- Do not add phone/user metadata to `mail_lookup_jobs`.
- Do not cancel jobs by querying all jobs for a phone number; `MailLookupJob` does not currently store requester phone.
- Do not change Evolution Go behavior for this issue.
- Do not change n8n polling behavior.

## Approved decisions

- Use approach A: keep the existing job status model and mark active restarted jobs as `failed` with a cancellation error code.
- Scope cancellation to the job linked from the user's current Redis session via `temp_data.lookup_job_id`.
- Interpret “for this user/phone” as “the active job referenced by that phone's Redis conversation session,” because jobs do not persist phone identity.

## Current behavior summary

### Tenant admin flow

`WhatsAppTenantConsoleService.process_message()` routes active flows before checking top-level codigo triggers. When a tenant admin session has `flow="codigo"` and `step="awaiting_result"`, a fresh `code` message is sent to `_handle_codigo_awaiting_result()` rather than `_start_codigo_flow()`.

`_handle_codigo_awaiting_result()` handles `1`, `2`, and `0`. Any other input currently returns `wa.tenant.codigo.still_checking`, which causes the observed regression.

### Unauthenticated flow

`_handle_unauthenticated_codigo()` resumes an existing `session:unreg:*` codigo session and dispatches `awaiting_result` to `_handle_unauth_codigo_result()`.

`_handle_unauth_codigo_result()` handles `1`, `2`, and `0`. Any other input currently returns `wa.tenant.codigo.still_checking`, so a fresh `code` message is also swallowed there.

## Proposed design

### Shared trigger rule

Define the restart trigger as:

```python
msg.strip().lower() in ("codigo", "código", "code")
```

Apply this rule inside both `awaiting_result` handlers before the fallback `still_checking` response.

### Job cancellation policy

Add a small repository helper in `backend/app/repositories/mailbox_lookup_repository.py`:

```python
async def cancel_active_job_if_present(
    db: AsyncSession,
    job_id: UUID,
    tenant_id: UUID | None = None,
) -> bool:
    ...
```

Behavior:

1. Fetch the job with existing `get_job(db, job_id, tenant_id=tenant_id)`.
2. If the job does not exist, return `False`.
3. If `job.status` is not `pending` or `processing`, return `False` without mutating it.
4. If active, set:
   - `status = "failed"`
   - `completed_at = now`
   - `error_code = "user_cancelled"`
   - `error_detail_safe = "User restarted codigo flow"`
5. Flush and return `True`.

The helper should not commit. Callers keep transaction control, matching repository patterns.

This intentionally avoids `transition_status()` because the desired behavior is an idempotent cancellation helper that safely no-ops for terminal jobs instead of raising on invalid transitions.

### Tenant admin restart

In `_handle_codigo_awaiting_result()`:

1. Detect the restart trigger before returning `still_checking`.
2. Read `lookup_job_id` from `session.temp_data`.
3. If present and valid UUID, call `cancel_active_job_if_present(db, UUID(lookup_job_id), tenant_id=tenant_id)`.
4. Commit the cancellation if it succeeds or no-op if the job is terminal/missing.
5. If cancellation raises, log with `logger.exception`, attempt rollback if needed, and continue with Redis reset.
6. Clear `session:admin:{phone}`.
7. Call `_start_codigo_flow(phone, session_service, tenant_id, db, started_from_menu=False, role="tenant")`.
8. Return the fresh service prompt.

`1`, `2`, and `0` behavior remains unchanged.

### Unauthenticated restart

In `_handle_unauth_codigo_result()`:

1. Detect the restart trigger before returning `still_checking`.
2. Read `lookup_job_id` from `session.temp_data`.
3. If present and valid UUID, call `cancel_active_job_if_present(db, UUID(lookup_job_id), tenant_id=tenant.id)`.
4. Commit the cancellation if it succeeds or no-op if terminal/missing.
5. If cancellation raises, log with `logger.exception`, attempt rollback if needed, and continue with Redis reset.
6. Clear the current `session_key`.
7. Rebuild effective services with `code_services_repository.get_effective_service_keys(db, tenant.id)`.
8. If no services remain, return `wa.tenant.codigo.no_code_services_client`.
9. Create a new session at the same `session_key` with:
   - `flow = _UNAUTH_CODIGO_FLOW`
   - `step = _UNAUTH_CODIGO_STEP_SERVICE`
   - `temp_data.codigo_effective_keys = effective_keys`
   - `temp_data.codigo_current_page = 0`
10. Return `wa.tenant.codigo.service_prompt` with page 0.

`1`, `2`, and `0` behavior remains unchanged.

## Data flow

### Tenant admin

```text
User sends code
  -> active session:admin:{phone} flow=codigo step=awaiting_result
  -> detect restart trigger
  -> best-effort fail lookup_job_id from session temp_data
  -> clear Redis session
  -> _start_codigo_flow(... started_from_menu=False)
  -> service list prompt
```

### Unauthenticated

```text
User sends code
  -> active session:unreg:{tenant-prefix}:{phone|lid} flow=codigo step=awaiting_result
  -> detect restart trigger
  -> best-effort fail lookup_job_id from session temp_data
  -> clear Redis session
  -> create new unauth codigo service session
  -> service list prompt
```

## Error handling

- Missing `lookup_job_id`: continue restart.
- Invalid UUID in `lookup_job_id`: log at warning/debug level if useful, then continue restart.
- Missing job: continue restart.
- Terminal job (`completed`, `failed`, `timeout`): leave unchanged and continue restart.
- DB cancellation exception: log exception, rollback if needed, continue with Redis reset and restart.
- Redis clear/create errors: existing Redis unavailable handling should continue to govern the request.
- No mailbox or no effective services: preserve existing user-facing responses from the existing flow-start logic.

## Testing plan

### Tenant service tests

Add coverage in `backend/tests/test_tenant_console_service.py` or the most local existing tenant codigo test area:

1. Existing tenant codigo session in `awaiting_result` with active `lookup_job_id` + message `code`:
   - reply contains the service prompt/list
   - reply does not contain `still_checking`
   - session step becomes `service`
   - active job becomes `failed` with `error_code="user_cancelled"`

2. Existing tenant codigo session in `awaiting_result` with terminal `completed` job + message `code`:
   - flow restarts from service list
   - job remains `completed`
   - no invalid transition is raised

3. Existing tenant codigo session in `awaiting_result` + unknown message `hola`:
   - reply remains `wa.tenant.codigo.still_checking`

### Endpoint / unauth tests

Add coverage in `backend/tests/test_whatsapp_endpoint.py` or an equivalent focused unauthenticated codigo test module:

1. Existing unauth session in `awaiting_result` with active `lookup_job_id` + message `code`:
   - reply contains the service prompt/list
   - reply does not contain `still_checking`
   - session step becomes `service`
   - active job becomes `failed` with `error_code="user_cancelled"`

2. Existing unauth session in `awaiting_result` with terminal `completed` job + message `codigo`:
   - flow restarts from service list
   - job remains `completed`

3. Existing unauth session in `awaiting_result` + unknown message `hola`:
   - reply remains `wa.tenant.codigo.still_checking`

## Verification commands

```bash
cd backend && uv run pytest backend/tests/test_tenant_console_service.py backend/tests/test_whatsapp_endpoint.py
cd backend && uv run pytest
```

## Documentation update

Update `docs/architecture/whatsapp-console-flow.md` to describe the new restart behavior:

- `code|codigo|código` during `awaiting_result` restarts codigo from service selection.
- The backend best-effort cancels the active job referenced by the current Redis session.
- Cancellation is limited to the session-linked `lookup_job_id` because `MailLookupJob` does not store requester phone.

## Self-review

- Placeholder scan: no TODO, TBD, or open placeholder sections remain.
- Consistency check: the design consistently uses approach A, marks active jobs as `failed/user_cancelled`, and avoids introducing a new status.
- Scope check: the work is bounded to one repository helper, two codigo awaiting-result handlers, documentation, and tests.
- Ambiguity check: “for this user/phone” is explicitly defined as the job referenced by the Redis session for that phone because the DB job model has no phone column.
