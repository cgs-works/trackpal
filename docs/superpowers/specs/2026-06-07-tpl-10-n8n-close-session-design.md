# TPL-10 Design: Close Evolution Session After Successful Code Lookup

## Purpose

Fix the WhatsApp Bot workflow so Evolution Go closes the chat session after a terminal successful code lookup result is sent, while keeping recoverable lookup outcomes open for retry/back/cancel.

## Decisions captured

- Successful terminal lookup results close the Evolution Go session after the result is sent.
- Recoverable lookup outcomes stay open and must include `1 / 2 / 0` options:
  - `not_found`
  - `duplicate_suppressed`
  - `failed`
  - `timeout`
  - unknown/fallback non-success outcomes
- If the user chooses `0 Cancelar` from any post-result recoverable lookup state, the Redis session and Evolution Go session must close.
- The workflow will use an explicit `close_after_send` flag set in `Build result message`.
- `Check close session` must read `close_after_send` from upstream lookup-result data, not assume `Send result` preserves custom fields.
- Local n8n polling timeout retry semantics are closed for **both** code flows:
  - tenant self-target flow (`_handle_codigo_awaiting_result`)
  - unauthenticated/client-sent flow (`_handle_unauth_codigo_result`)
- No database migration is required.

## Problem

Issue TPL-10 reports that the n8n WhatsApp Bot workflow sends the final access-code lookup result but does not close the Evolution Go chatbot session afterward.

The verified current root cause is in `n8n/Trackpal WhatsApp Bot.json`:

- `Merge & lookup data` preserves `lookup_job_id` on the item.
- `Build result message` currently returns `{ ...base, ...poll, reply: finalMessage }` and does **not** emit any explicit close/terminal flag.
- `Send result` is an HTTP Request node.
- `Check close session` currently does:

```javascript
const fallback = $('Merge & lookup data').first().json;
const data = { ...fallback, ...$json };

const hasLookupResult = Boolean(data.lookup_job_id);
if (hasLookupResult) {
  return [];
}
```

Because `lookup_job_id` is still present in the merged lookup context, `Check close session` unconditionally returns `[]` for lookup-result flows, so `Close session` is skipped even after successful `code`/`url` results.

This leaves the Evolution Go session open until TTL expiry, so follow-up user messages can be interpreted as continuation of the previous lookup flow.

## Goals

- Close the Evolution Go chat session after a successful terminal lookup result is sent.
- Preserve post-result options for recoverable outcomes:
  - `1` retry lookup
  - `2` back to services
  - `0` cancel
- Make `0` a terminal action in post-result recoverable states: it must clear the backend session and close the Evolution Go session.
- Make the workflow lifecycle decision explicit rather than inferred from `lookup_job_id`.
- Keep the change surgical and localized to the n8n workflow plus the minimum backend behavior needed for coherent retry semantics after local n8n timeout.
- Make timeout/retry behavior consistent across both tenant and unauth lookup flows.

## Non-goals

- Redesign the access-code lookup flow.
- Remove `lookup_job_id` from the n8n payload.
- Change Evolution Go session TTL.
- Introduce a persisted mailbox-job `timeout` state beyond the current workflow-local timeout handling.
- Refactor unrelated WhatsApp console or n8n behavior.

## Verified current behavior

### Workflow

1. User starts a code lookup flow.
2. Backend returns `lookup_job_id` plus `tenant_id`.
3. n8n sends the initial `buscando` reply and polls the lookup job.
4. `Build result message` maps poll output into the final user-facing message.
5. `Send result` sends the final message.
6. `Check close session` still sees `lookup_job_id` and returns `[]` immediately.
7. `Close session` never runs for lookup-result flows.

Additional verified details:

- `Build result message` currently appends `1/2/0` options only for `not_found` / `duplicate_suppressed`.
- `failed` and `timeout` currently use an error message without retry/back/cancel options.
- Because `Send result` is an HTTP Request node, the spec must not rely on its output to carry custom workflow fields like `close_after_send`.

### Backend

The backend currently behaves differently between the two awaiting-result handlers when the previous job is still `pending` or `processing`:

- `backend/app/services/whatsapp_tenant_console_service/codigo_flow.py::_handle_codigo_awaiting_result`
  - `1` or `2` while the previous job is not terminal returns `wa.tenant.codigo.still_checking`.
- `backend/app/api/v1/endpoints/integrations/console_handlers.py::_handle_unauth_codigo_result`
  - `1` or `2` while the previous job is not terminal clears the session and reopens the service list.

This means the current UX is not consistent across flows, and current unauth `1` behavior does not actually mean “retry same search with saved inputs”.

## Design

### 1. Add explicit `close_after_send` in `Build result message`

`Build result message` is the correct node to decide whether the final lookup message is terminal, because it already maps poll result semantics into the final user-facing text.

It should emit a boolean `close_after_send`:

| Poll outcome | User-facing message | `close_after_send` |
| --- | --- | --- |
| `result_type === "code"` | Code found | `true` |
| `result_type === "url"` | Link found | `true` |
| `result_type === "not_found"` | Not found + `1/2/0` options | `false` |
| `result_type === "duplicate_suppressed"` | Not found + `1/2/0` options | `false` |
| `status === "failed"` | Error + `1/2/0` options | `false` |
| `status === "timeout"` | Timeout + `1/2/0` options | `false` |
| fallback/unknown non-success | Recoverable not-found-style message + `1/2/0` options | `false` |

Successful `code` and `url` results are terminal because the user already received the code or continuation link. Recoverable outcomes stay open so the user can retry, go back to service selection, or cancel.

### 2. Update failure and timeout messages to include retry options

Currently `not_found` includes retry/back/cancel options. The same option set must be shown for `failed`, `timeout`, and unknown fallback non-success outcomes.

Spanish copy should stay consistent with current style:

```text
❌ *No se pudo completar la búsqueda*

Ocurrió un error o se agotó el tiempo al buscar el código.

1️⃣ Reintentar
2️⃣ Volver a servicios
0️⃣ Cancelar
```

English copy should stay consistent with current style:

```text
❌ *Could not complete code search*

An error occurred or the search timed out.

1️⃣ Retry
2️⃣ Back to services
0️⃣ Cancel
```

Exact wording can be refined during implementation, but the options must be present.

### 3. Update `Check close session` to honor `close_after_send`

`Check close session` must no longer treat `lookup_job_id` as an unconditional blocker.

It must read lookup-result data from upstream result-building context rather than assuming the current `$json` from `Send result` still contains custom fields.

Recommended shape:

```javascript
const fallback = $('Merge & lookup data').first().json;
const resultData = $('Build result message').first().json;
const data = { ...fallback, ...resultData, ...$json };

const hasLookupResult = Boolean(data.lookup_job_id);
const shouldCloseAfterSend = data.close_after_send === true;

if (hasLookupResult && !shouldCloseAfterSend) {
  return [];
}

const isLogout = shouldCloseAfterSend || isClosedStatus || (isLogoutCommand && isLogoutReply);
```

Required behavior:

- If `lookup_job_id` exists and `close_after_send !== true`, return `[]`.
- If `lookup_job_id` exists and `close_after_send === true`, emit the close item.
- Preserve existing non-lookup logout/status behavior.
- Preserve existing close target selection:
  - prefer `close_jids` when present
  - otherwise `close_jid || reply_to || remoteJid`

This keeps the active/recoverable lookup guard while allowing terminal lookup success to close the Evolution session.

### 4. Close timeout-retry semantics for both backend awaiting-result handlers

n8n can produce a **workflow-local timeout** when polling exhausts attempts and sets `status: "timeout"`, even if the backend mailbox job is still `pending` or `processing`.

The spec closes retry semantics for **both** flows so the `1 / 2 / 0` options shown by n8n stay coherent.

#### 4a. Tenant self-target flow

In `backend/app/services/whatsapp_tenant_console_service/codigo_flow.py::_handle_codigo_awaiting_result`:

- `0` still cancels immediately and must close the Evolution Go session.
- `2` should return to service selection even if the previous job is still non-terminal.
- `1` should allow a fresh retry with the saved `service_key` and `target_email` even if the previous job is still non-terminal.
- Preserve the existing tenant orchestration pattern: when retrying from the tenant flow, reuse `pending_lookup_intent` so the integration handler creates/enqueues the new job on the next pass.
- If saved inputs are missing, fall back to the existing service-list restart behavior.

This keeps the tenant flow consistent with the workflow-local timeout message the user already saw.

#### 4b. Unauthenticated/client-sent flow

In `backend/app/api/v1/endpoints/integrations/console_handlers.py::_handle_unauth_codigo_result`:

- `0` still cancels immediately and closes the Evolution Go session.
- `2` still clears the old flow and returns to service selection.
- `1` should create/enqueue a fresh lookup job using saved `service_key` and `target_email` whenever those values exist, even if the previous job is still `pending` or `processing`.
- If the retry cannot be created, fall back to the existing service-selection restart behavior.

This is narrower than introducing a persisted timeout state and only changes post-result retry semantics.

## Data flow after change

### Successful code/url

1. `Build result message` returns final message with `close_after_send: true`.
2. `Send result` sends the code/link to the user.
3. `Check close session` reads merged lookup context plus upstream `Build result message` output.
4. `Check close session` sees `lookup_job_id` and `close_after_send: true`.
5. `Check close session` emits the close item.
6. `Close session` posts `status: "closed"` to Evolution Go.

### Not found / duplicate / failed / timeout / unknown recoverable non-success

1. `Build result message` returns recoverable message with `1/2/0` options and `close_after_send: false`.
2. `Send result` sends the options to the user.
3. `Check close session` sees `lookup_job_id` and `close_after_send !== true`.
4. `Check close session` returns `[]`.
5. User can send `1`, `2`, or `0`.
6. If the user sends `0`, backend clears the session and n8n closes the Evolution Go session.

## Testing strategy

### n8n workflow checks

Validate that:

- `Build result message` emits `close_after_send: true` for `code` and `url`.
- `Build result message` emits `close_after_send: false` for `not_found`, `duplicate_suppressed`, `failed`, `timeout`, and unknown fallback non-success outcomes.
- `failed` and `timeout` messages include `1/2/0` options.
- `Check close session` does not return early solely because `lookup_job_id` exists when `close_after_send === true`.
- `Check close session` still returns `[]` for recoverable lookup outcomes.
- `Check close session` reads `close_after_send` from upstream lookup-result context rather than depending only on `Send result` output.

### Backend tests

Add focused tests for both awaiting-result handlers:

- Tenant flow: previous job still `pending` + user sends `1` after local n8n timeout UX → backend restarts the lookup with saved `service_key`/`target_email`.
- Tenant flow: previous job still `pending` + user sends `2` → backend returns the service list instead of `still_checking`.
- Unauth flow: previous job still `pending` + user sends `1` after local n8n timeout UX → backend creates/enqueues a fresh lookup job and returns a fresh `lookup_job_id`.
- Unauth flow: previous job still `pending` + user sends `2` → backend returns service selection.
- Both flows: user sends `0` → backend clears session and returns the close contract needed for n8n to close the Evolution Go session.
- Existing terminal failed job + user sends `1` → retry still works.

## Rollout notes

- This is a workflow + backend behavior change; deploy backend first, then import/update the n8n workflow.
- If only the n8n workflow is changed first, successful results will close correctly, but timeout retry semantics will remain inconsistent until backend changes land.
- No database migration is required.

## Risks and mitigations

- **Risk:** Closing successful lookup sessions could close the wrong JID if `remoteJid` is not canonical.
  - **Mitigation:** Preserve the existing close target fallback and prefer canonical close fields already provided by the backend.
- **Risk:** Timeout retry can create duplicate lookup jobs while the previous job may still finish later.
  - **Mitigation:** This is acceptable for explicit user-driven retry. Existing duplicate/result suppression behavior remains responsible for duplicate user-visible handling.
- **Risk:** Future workflow edits may accidentally read `close_after_send` from the wrong node output.
  - **Mitigation:** Keep the `Check close session` implementation explicit about sourcing the flag from `Build result message` / merged lookup context.

## Spec self-review

- Placeholder scan: no unresolved TBD/TODO placeholders remain.
- Internal consistency: terminal success closes after send; recoverable outcomes stay open with explicit options.
- Scope check: focused on TPL-10 plus the minimum backend retry semantics needed to keep workflow timeout UX coherent.
- Ambiguity check: retry semantics are now explicitly closed for both tenant and unauth flows, and the flag-source detail for `Check close session` is specified.