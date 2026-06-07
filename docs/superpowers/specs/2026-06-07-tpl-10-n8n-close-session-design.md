# TPL-10 Design: Close Evolution Session After Successful Code Lookup

## Status

Approved for design by user on 2026-06-07.

## Problem

Issue TPL-10 reports that the n8n WhatsApp Bot workflow sends the final access-code lookup result but does not close the Evolution Go chatbot session afterward. The workflow sends the result through `Send result`, then routes into `Check close session`. `Check close session` merges current node output with `Merge & lookup data`; because the fallback still contains `lookup_job_id`, the node treats the lookup flow as active and returns no items. `Close session` is therefore skipped and Evolution Go keeps the chat session open until its TTL expires.

This causes follow-up user messages within the Evolution session TTL to be interpreted as continuation of the previous lookup flow.

## Goals

- Close the Evolution Go chat session after a successful terminal lookup result is sent.
- Preserve the post-result options for unsuccessful/non-terminal results:
  - `1` retry lookup
  - `2` back to services
  - `0` cancel
- Make the workflow lifecycle decision explicit rather than inferred from the presence of `lookup_job_id`.
- Keep the change surgical and localized to the n8n workflow plus the minimum backend behavior needed for timeout retry semantics.

## Non-goals

- Redesign the unauthenticated code lookup flow.
- Remove `lookup_job_id` from the n8n data payload.
- Change Evolution Go session TTL.
- Change mailbox lookup worker processing semantics beyond what is required for retry UX.

## Current Flow

1. User starts unauthenticated code lookup with `code` / `codigo` / `código`.
2. Backend creates a lookup job and returns `lookup_job_id` plus `tenant_id`.
3. n8n sends the initial `buscando` reply, polls the job, builds a final result message, and sends it through `Send result`.
4. `Send result` connects to `Check close session`.
5. `Check close session` sees `lookup_job_id` and returns `[]`, so `Close session` never runs.

## Design

### 1. Add explicit `close_after_send` in `Build result message`

`Build result message` is the correct node to decide whether the final result message is terminal, because it already maps poll state into the user-facing message.

It should emit a boolean `close_after_send`:

| Poll outcome | User-facing message | `close_after_send` |
| --- | --- | --- |
| `result_type === "code"` | Code found | `true` |
| `result_type === "url"` | Link found | `true` |
| `result_type === "not_found"` | Not found + `1/2/0` options | `false` |
| `result_type === "duplicate_suppressed"` | Not found + `1/2/0` options | `false` |
| `status === "failed"` | Error + `1/2/0` options | `false` |
| `status === "timeout"` | Timeout + `1/2/0` options | `false` |
| fallback/unknown non-success | Not found-style recoverable message + `1/2/0` options | `false` |

Successful `code` and `url` results are terminal because the user has received the code or continuation link. Recoverable outcomes stay open so the user can retry, go back to service selection, or cancel.

### 2. Update failure and timeout messages to include retry options

Currently `not_found` includes retry/back/cancel options. The same option set should be shown for `failed` and `timeout` so the final client can retry when the search could not complete in the configured time.

Spanish copy should follow the existing style:

```text
❌ *No se pudo completar la búsqueda*

Ocurrió un error o se agotó el tiempo al buscar el código.

1️⃣ Reintentar
2️⃣ Volver a servicios
0️⃣ Cancelar
```

English copy should follow the existing style:

```text
❌ *Could not complete code search*

An error occurred or the search timed out.

1️⃣ Retry
2️⃣ Back to services
0️⃣ Cancel
```

The exact wording can be refined during implementation, but the options must be present for `failed` and `timeout`.

### 3. Update `Check close session` to honor `close_after_send`

`Check close session` should no longer treat `lookup_job_id` as an unconditional blocker. Instead:

- If `lookup_job_id` exists and `close_after_send !== true`, return `[]`.
- If `lookup_job_id` exists and `close_after_send === true`, proceed to close the session.
- Preserve existing logout/status behavior for non-lookup flows.
- Preserve existing close JID selection:
  - prefer `close_jids` when present
  - otherwise `close_jid || reply_to || remoteJid`

Conceptual logic:

```javascript
const hasLookupResult = Boolean(data.lookup_job_id);
const shouldCloseAfterSend = data.close_after_send === true;

if (hasLookupResult && !shouldCloseAfterSend) {
  return [];
}

const isLogout = shouldCloseAfterSend || isClosedStatus || (isLogoutCommand && isLogoutReply);
```

This keeps the existing guard for active/recoverable lookup flows while allowing terminal lookup success to close the Evolution session.

### 4. Backend retry behavior for local n8n timeout

`timeout` can be local to n8n: `Check retry` may set `status: "timeout"` after polling attempts are exhausted even if the backend job is still `pending` or `processing`.

To make the retry UX coherent, `_handle_unauth_codigo_result` should allow `1` to start a new lookup with the same service/email even when the previous job is not yet terminal. This avoids a confusing state where n8n showed retry options but the backend treats the old job as still pending.

Required behavior:

- `0` still cancels immediately and closes the session.
- `2` still clears the old flow and returns to service selection.
- `1` should create/enqueue a fresh lookup job using `service_key` and `target_email` from session temp data whenever those values exist, regardless of whether the previous job is terminal.
- If the retry cannot be created, fall back to the existing service-selection restart behavior.

This is intentionally narrow and does not require adding a persisted `timeout` state to lookup jobs.

## Data Flow After Change

### Successful code/url

1. `Build result message` returns final message with `close_after_send: true`.
2. `Send result` sends the code/link to the user.
3. `Check close session` sees `lookup_job_id` and `close_after_send: true`.
4. `Check close session` emits the close item.
5. `Close session` posts `status: "closed"` to Evolution Go.

### Not found / duplicate / failed / timeout

1. `Build result message` returns recoverable message with `1/2/0` options and `close_after_send: false`.
2. `Send result` sends the options to the user.
3. `Check close session` sees `lookup_job_id` and `close_after_send !== true`.
4. `Check close session` returns `[]`; Evolution session stays open.
5. User can send `1`, `2`, or `0`.

## Testing Strategy

### n8n workflow JSON checks

Because the n8n workflow is stored as JSON, test coverage can be a lightweight unit/script test or targeted assertions if the project already has a pattern for workflow validation.

Validate that:

- `Build result message` emits `close_after_send: true` for `code` and `url`.
- `Build result message` emits `close_after_send: false` for `not_found`, `duplicate_suppressed`, `failed`, and `timeout`.
- `Check close session` does not return early solely because `lookup_job_id` exists when `close_after_send === true`.
- `Check close session` still returns `[]` for recoverable lookup outcomes.

### Backend tests

Add focused tests for `_handle_unauth_codigo_result` or the n8n console endpoint flow:

- Existing awaiting-result session + previous job still `pending` + user sends `1` → backend creates/enqueues a new lookup job and returns a fresh `lookup_job_id`.
- Existing awaiting-result session + user sends `2` → backend returns service selection.
- Existing awaiting-result session + user sends `0` → backend clears session and returns `status: "closed"` with close JID.
- Existing terminal failed job + user sends `1` → retry still works.

## Rollout Notes

- This is a workflow and backend behavior change; deploy backend first if backend retry behavior is implemented, then import/update the n8n workflow.
- If only the n8n workflow is changed first, `failed` retry likely works for terminal failed jobs, but local n8n `timeout` retry may still fall into the previous pending-job behavior.
- No database migration is required.

## Risks and Mitigations

- **Risk:** Closing successful lookup sessions could close the wrong JID if `remoteJid` is not canonical.
  - **Mitigation:** Preserve the existing close target fallback and prefer existing canonical `close_jid` fields when available.
- **Risk:** Timeout retry creates duplicate lookup jobs while the previous job may still finish later.
  - **Mitigation:** This is acceptable for user-driven retry. Existing dedupe/result suppression behavior remains responsible for duplicate result handling.
- **Risk:** n8n `Send result` output may not preserve custom fields.
  - **Mitigation:** `Check close session` already merges the current node output with `Merge & lookup data`. Ensure `Build result message` output remains available after `Send result`; if not, introduce a small post-send merge or route the flag through a field that survives the HTTP node output.

## Spec Self-review

- Placeholder scan: no unresolved TBD/TODO placeholders remain.
- Internal consistency: `close_after_send` is set by result semantics and consumed only by session-close logic.
- Scope check: focused on TPL-10; no unrelated workflow or backend refactor included.
- Ambiguity check: timeout is explicitly treated as recoverable UX without adding a persisted timeout state.
