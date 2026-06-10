# TPL-15 — Remote `codigo` Flow Cancellation

## Status

Approved design. Awaiting user review before implementation planning.

## Summary

Allow a tenant admin to manually cancel a user's active `codigo` / `code` lookup flow by sending exactly `0` in that user's WhatsApp chat.

The cancellation is remote from the user's perspective: the user does not need to send `0`, and the tenant admin does not need an active TrackPal admin console or Client Context Shortcut session.

This design relies on an already-open Evolution Go chatbot session for the target chat. It does not add `0` as a new webhook trigger.

## Problem

A user may start the code lookup flow by sending `code`, `codigo`, or `código` to a tenant's WhatsApp instance. TrackPal creates a backend Redis session for that user and may create a `MailLookupJob` while n8n polls for the result.

If the user gets stuck or does not know how to cancel, the tenant admin needs a way to stop that user's active code flow manually.

The complication is that Evolution Go only dispatches chatbot messages to n8n when either:

1. A chatbot session is already open for the target `remoteJid`; or
2. There is no open session, but the incoming content matches the webhook trigger.

Because this design must not add `0` to the trigger, tenant-side cancellation can only work while the user's Evolution Go chatbot session is still open.

## Goals

- Let a tenant admin cancel a target user's active `codigo` flow by sending exactly `0` in that target chat.
- Keep the operation silent: no TrackPal confirmation message is sent to the tenant or the user.
- Clear the target user's TrackPal Redis `codigo` session.
- Cancel the active `MailLookupJob` when the target session references one and the job is still active.
- Return `status="closed"` and `close_jid` so n8n closes the Evolution Go chatbot session for the target chat.
- Preserve the existing webhook trigger. Do not add `0` to it.

## Non-goals

- Do not use or modify Client Context Shortcut behavior for this feature.
- Do not create a tenant admin Redis session when a user starts `codigo`.
- Do not create a tenant admin Evolution Go chatbot session when a user starts `codigo`.
- Do not add aliases such as `cancelar`, `salir`, or `cerrar`; only exact `0` is accepted.
- Do not make cancellation work after the Evolution Go chatbot session for the target has expired, unless a future design adds a new trigger or Evolution Go bypass.
- Do not modify Evolution Go source code for this issue.

## Existing behavior and constraints

### TrackPal webhook registration

TrackPal currently registers the tenant webhook with this trigger:

```regex
(?i)^\s*(?:/menu|codigo|código|code)\b
```

That trigger is retained exactly. The design adds `listeningFromMe=true` to the webhook registration payload so Evolution Go will consider outgoing tenant messages when a chatbot session exists.

### Evolution Go session dispatch

Evolution Go filters `fromMe` messages before session lookup unless `ListeningFromMe` is enabled on the webhook. Therefore, `listeningFromMe=true` is required.

When a session is already `opened`, Evolution Go dispatches the message to the webhook without rechecking the trigger. This is what lets tenant-sent `0` reach TrackPal while the user's chat session is open.

When no session is open, Evolution Go evaluates the trigger. Since `0` is not part of the trigger, the message is discarded and does not reach TrackPal. This limitation is accepted.

### TrackPal backend sessions

The target user's code flow uses the unauthenticated code session namespace:

```text
session:unreg:{tenant_prefix}:{target_phone_or_lid}
```

where `tenant_prefix` is `str(tenant_id)[:8]`, matching `_unauth_session_key(...)`.

## Proposed architecture

### 1. Update TrackPal webhook registration

In `backend/app/services/evolution_client/client.py`, update `EvolutionClient.register_webhook()` to include:

```json
"listeningFromMe": true
```

Keep the current trigger unchanged:

```python
"triggerValue": r"(?i)^\s*(?:/menu|codigo|código|code)\b"
```

This allows outgoing tenant messages to be processed only when Evolution Go already has a chatbot session for the target `remoteJid`.

### 2. Add remote cancel branch in backend routing

In `_handle_from_me_routing(...)`, after self-target detection and before the existing non-`/menu` external-target gate, add a branch for:

```text
from_me=true
non-self target
message.strip() == "0"
```

When matched:

1. Resolve the target identity from `target_phone`, `target_lid`, and `target_jid`.
2. Cancel the target's active `codigo` state through a helper.
3. Return a silent close response:

```json
{
  "reply": "",
  "no_reply": true,
  "status": "closed",
  "close_jid": "<target canonical jid>"
}
```

This branch must not create `wa:client_ctx:{admin_phone}` and must not route to the tenant admin console.

### 3. Add helper to cancel target `codigo` flow

Add a small helper near the existing console handler utilities, for example in `console_handlers.py`:

```python
async def _cancel_target_codigo_flow(
    *,
    manager: RedisConnectionManager,
    db: AsyncSession,
    tenant_id: UUID,
    target_phone: str | None,
    target_lid: str | None,
) -> bool:
    ...
```

Behavior:

1. Build candidate logical session keys using `_unauth_session_key(...)`:
   - `unreg:{tenant_prefix}:{target_phone}` when `target_phone` exists.
   - `unreg:{tenant_prefix}:{target_lid}` when `target_lid` exists.
2. For each unique candidate:
   - Load the session via `WhatsAppSessionService.get_session(logical_key)`.
   - If the session exists and `session.flow == "codigo"`, inspect `session.temp_data["lookup_job_id"]`.
   - If a `lookup_job_id` exists, call `mailbox_lookup_repository.cancel_active_job_if_present(...)` with the current `tenant_id`.
   - Delete the session via `clear_session(logical_key)`.
3. Commit successful job cancellation changes.
4. Roll back and log if job cancellation fails, but still attempt to clear the Redis session.
5. Return `True` if at least one `codigo` session was found or cleared; otherwise return `False`.

The helper should be idempotent. Missing sessions, missing job ids, invalid job ids, and already-terminal jobs must not fail the webhook response.

### 4. n8n behavior

n8n must preserve the existing response contract:

- If `no_reply=true`, do not send a WhatsApp text message.
- If `status="closed"` and `close_jid` is present, call Evolution Go `POST /webhook/change-status` with that `remoteJid`.

For this feature, both must happen together: no message is sent, but the target Evolution Go chatbot session is closed.

### 5. Evolution Go behavior

No Evolution Go code changes are part of this design.

The feature relies on existing Evolution Go behavior:

- `ListeningFromMe=true` allows outgoing messages to be evaluated by the webhook listener.
- An open chatbot session dispatches messages without rechecking trigger content.
- Without an open chatbot session, `0` is discarded because it does not match the trigger.

## Data flow

### Successful remote cancellation

1. User sends `code`, `codigo`, or `código`.
2. Evolution Go trigger matches and opens a chatbot session for `remoteJid=<user_jid>`.
3. n8n calls TrackPal.
4. TrackPal creates or continues `session:unreg:{tenant_prefix}:{user}`.
5. Tenant sends `0` in the user's chat.
6. Evolution Go sees `fromMe=true` and allows the message because the webhook has `ListeningFromMe=true`.
7. The existing Evolution Go session for the user's `remoteJid` is `opened`, so Evolution Go dispatches `0` to n8n/TrackPal.
8. TrackPal detects `from_me=true`, non-self target, and exact `0`.
9. TrackPal cancels the target user's Redis `codigo` session and active lookup job.
10. TrackPal returns `reply=""`, `no_reply=true`, `status="closed"`, and `close_jid=<target_jid>`.
11. n8n sends no text and calls Evolution Go `change-status` for `close_jid`.
12. Evolution Go removes the chatbot session for the target `remoteJid`.

### Expired Evolution Go session

1. User previously started `codigo`, but the Evolution Go chatbot session expires or is closed before the tenant sends `0`.
2. Tenant sends `0` in the user's chat.
3. Evolution Go has no open session for the target `remoteJid`.
4. Evolution Go evaluates the trigger.
5. `0` does not match the trigger, so no webhook dispatch occurs.
6. TrackPal cannot cancel because it never receives the event.

This is an accepted limitation of the design.

## Edge cases

### No Redis session found

If Evolution Go dispatches the tenant's `0` but TrackPal finds no target Redis `codigo` session, TrackPal still returns silent close:

```json
{
  "reply": "",
  "no_reply": true,
  "status": "closed",
  "close_jid": "<target jid>"
}
```

This closes the Evolution Go session if it exists.

### Session exists without `lookup_job_id`

Delete the Redis session and close Evolution Go. Do not attempt job cancellation.

### Session has invalid `lookup_job_id`

Log a warning, clear the Redis session, and return silent close.

### Job already terminal

`cancel_active_job_if_present(...)` should be treated as idempotent. Terminal jobs do not block Redis cleanup or the close response.

### Target has both phone and LID

Try both candidate session keys. Prefer canonical phone JID for `close_jid` when available. Fall back to `target_jid` only when a canonical phone JID cannot be built.

### Message aliases

Only `message.strip() == "0"` triggers remote cancellation. `cancelar`, `salir`, `cerrar`, `menu`, and `/menu` must not use this remote cancel path.

### Self-target

If the target is the tenant's own chat, keep existing self-target routing. Do not treat that as remote target cancellation.

## Tests

### Backend tests

1. **Webhook registration payload**
   - Update `backend/tests/test_evolution_client.py`.
   - Assert `listeningFromMe=True` is present.
   - Assert the trigger remains exactly `(?i)^\s*(?:/menu|codigo|código|code)\b`.
   - Assert `0` is not added to the trigger.

2. **Remote cancel by target phone**
   - Seed `session:unreg:{tenant_prefix}:{target_phone}` with `flow="codigo"`.
   - Send console request with `from_me=true`, non-self target, and `message="0"`.
   - Assert response has `reply=""`, `no_reply=true`, `status="closed"`, and phone-based `close_jid`.
   - Assert the Redis session is deleted.

3. **Remote cancel by target LID**
   - Seed `session:unreg:{tenant_prefix}:{target_lid}`.
   - Send `from_me=true`, `message="0"`, and `target_lid`.
   - Assert session deletion and silent close.

4. **Active job cancellation**
   - Seed a `MailLookupJob` in an active state and a target `codigo` session with `lookup_job_id`.
   - Send remote `0`.
   - Assert job cancellation is attempted/applied and Redis session is deleted.

5. **No aliases**
   - Send `from_me=true`, non-self target, `message="cancelar"`.
   - Assert target Redis `codigo` session remains.
   - Assert no remote cancel path is used.

6. **No Client Context Shortcut created**
   - Send `from_me=true`, non-self target, `message="0"`.
   - Assert no `wa:client_ctx:{admin_phone}` key is created.

7. **No Redis session still closes Evolution**
   - Send valid remote `0` with no target Redis session.
   - Assert silent close response still includes `status="closed"` and `close_jid`.

8. **Admin session is not cleared**
   - Seed `session:admin:{tenant_phone}`.
   - Send remote `0`.
   - Assert admin session remains untouched.

### n8n validation

Manual or workflow-level validation should confirm:

- `no_reply=true` prevents any outgoing text message.
- `status="closed"` plus `close_jid` still invokes `POST /webhook/change-status`.
- `close_jid` uses the target chat, not the tenant admin chat.

### Evolution Go validation

No Evolution Go code tests are required for this issue. Manual validation should confirm that, with `listeningFromMe=true`, tenant-sent `0` is dispatched while the target chatbot session is open.

## Acceptance criteria

- TrackPal registers tenant webhooks with `listeningFromMe=true`.
- The webhook trigger remains unchanged and does not include `0`.
- A tenant-sent exact `0` in a target user's chat is handled only when Evolution Go dispatches it from an already-open target session.
- TrackPal deletes the target user's `codigo` Redis session.
- TrackPal cancels the active `MailLookupJob` when the session references one.
- TrackPal responds with `reply=""`, `no_reply=true`, `status="closed"`, and target `close_jid`.
- n8n sends no text but closes the target Evolution Go chatbot session.
- Client Context Shortcut behavior remains unchanged.
- Tenant admin sessions remain untouched.
- The limitation that cancellation does not work after Evolution Go session expiry is documented.

## Rollout notes

Existing tenant webhooks must be reconciled through the existing `register_webhook()` upsert path so `listeningFromMe=true` reaches deployed Evolution Go configs. New tenants receive the setting during normal tenant creation.

If a tenant's webhook config is not reconciled, remote cancellation will not work because Evolution Go will discard `fromMe` messages before session lookup.

## Spec self-review

- Placeholder scan: no TODO/TBD placeholders remain.
- Consistency check: design keeps the current trigger unchanged and relies on `listeningFromMe=true` plus open Evolution Go sessions.
- Scope check: focused on TrackPal webhook registration, TrackPal backend routing, Redis/job cleanup, and n8n close behavior. No Evolution Go code changes included.
- Ambiguity check: exact command is `0`; aliases are excluded; expired Evolution Go sessions are explicitly unsupported.
