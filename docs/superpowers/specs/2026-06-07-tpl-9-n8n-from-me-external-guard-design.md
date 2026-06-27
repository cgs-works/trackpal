# TPL-9 Design: n8n Guard for `fromMe` External Non-Menu Messages

## Purpose

Prevent the cross-tenant WhatsApp ping-pong loop reported in TPL-9 while reducing unnecessary load on the TrackPal backend. The fix should let a tenant admin request access codes from another tenant normally, but prevent the requesting tenant's own Evolution Go instance from keeping an accidental chatbot session open for the same external chat.

## Decisions captured

- The selected fix is the n8n guard approach, applied before `Console call`.
- Do not block tenant admins from acting as clients or unauthenticated code seekers of another tenant.
- Do not implement a cross-tenant identity block in the backend for this issue.
- Do not change Evolution Go for the first fix.
- Do not rely on TrackPal-generated reply text filtering as the primary loop prevention mechanism.
- For `fromMe=true` messages targeting an external chat, only `/menu` and `menu` should continue to the backend because those commands intentionally start the Client Context Shortcut.
- For `fromMe=true` external non-menu messages, n8n must skip the backend, send no reply, and close the Evolution Go session for `targetJid`.

## Problem

TrackPal's tenant webhook must keep `listeningFromMe` enabled because tenant admins need the Client Context Shortcut: they can send `/menu` from their own WhatsApp chat with a client or unregistered contact and manage that contact in context.

The same setting creates an accidental side effect for tenant-to-tenant code requests:

1. Tenant A sends `code` to Tenant B.
2. Tenant B should process that message as an unauthenticated code lookup request and send its code-service menu back to Tenant A.
3. Tenant A's own Evolution Go instance also observes the outgoing `code` as `fromMe=true`.
4. Because TrackPal's webhook trigger includes `code`, Tenant A's Evolution Go instance opens a chatbot session for the external Tenant B chat and dispatches the webhook.
5. If that session remains open, Tenant B's menu response can re-enter Tenant A's bot path as a session continuation even though the menu text does not match the initial trigger.
6. Tenant A then replies with an unrelated fallback such as “No tienes una cuenta registrada.”
7. Tenant B interprets that fallback as invalid input in its code menu and replies again.
8. The two bot instances can keep responding to each other until session expiry or manual intervention.

The desired behavior is that Tenant B remains free to serve the code request, while Tenant A does not keep a local bot session open for the outgoing `code` command.

## Verified current behavior

### TrackPal backend registration

TrackPal registers Evolution Go webhooks with a regex trigger that includes `/menu`, `codigo`, `código`, and `code`. This is required because inbound unauthenticated code lookups and Client Context Shortcut both use the same webhook bridge.

### Evolution Go listener

Evolution Go checks `ListeningFromMe` before processing `fromMe=true` messages. Since TrackPal needs this enabled, outgoing messages are eligible for webhook evaluation.

When there is no opened session, Evolution Go evaluates the webhook trigger. If the outgoing message is `code`, the trigger matches, so Evolution Go opens a session and dispatches to n8n. For non-matching outgoing messages such as ordinary text, Evolution Go already skips dispatch.

This means the problematic load is not every outgoing tenant message. The problematic load is outgoing `fromMe=true` messages that match the shared trigger but are not intended to start TrackPal's admin context flow.

### n8n workflow

The n8n `Parse input` node already normalizes the fields required for a pre-backend guard:

- `message`
- `fromMe`
- `adminJid`
- `targetJid`
- `targetPhone`
- `targetLid`
- `remoteJid`
- `apiKey`

The current workflow always proceeds from `Parse input` through `Config` and `Console call`, unless existing TrackPal-generated text filtering returns no items. That means the backend still receives the avoidable `fromMe=true code` dispatch.

The workflow already has the downstream concepts needed for this design:

- `no_reply=true` skips Evolution send branches.
- `status="closed"` plus `close_jid` can trigger `Check close session` and `Close session`.
- `close_jids` can carry one or more sessions to close.

## Goals

- Stop the TPL-9 ping-pong loop.
- Avoid calling TrackPal backend for `fromMe=true` external non-menu messages.
- Preserve normal tenant-to-tenant code requests: Tenant B must still receive and process Tenant A's `code` message.
- Preserve Client Context Shortcut: `fromMe=true` external `/menu` and `menu` must still reach the backend.
- Keep the change isolated to the n8n workflow for the first fix.
- Close the accidental Evolution Go session immediately so later bot replies from the other tenant do not enter Tenant A's already-open session.
- Avoid text-fragile loop prevention based on Spanish or English generated replies.

## Non-goals

- Do not modify Evolution Go in this fix.
- Do not modify backend routing in this fix.
- Do not prevent tenants from being clients or unauthenticated code seekers of other tenants.
- Do not remove `code`, `codigo`, or `código` from the webhook trigger, because inbound code lookup depends on those commands.
- Do not disable `listeningFromMe`, because Client Context Shortcut depends on it.
- Do not redesign the code lookup dialog.
- Do not change Redis session semantics in TrackPal backend.
- Do not introduce tenant identity allowlists or blocklists.

## Design

### 1. Add an n8n guard after `Parse input`

Add a Code node immediately after `Parse input` and before the backend `Console call`. Suggested node name:

```text
Guard fromMe external non-menu
```

This node classifies whether the parsed item is an outgoing tenant message that should not start or continue TrackPal backend routing.

Classification:

```javascript
const input = $json;

const canonicalJid = (value) => {
  const raw = String(value || '').trim();
  if (!raw) return '';
  if (!raw.includes('@')) return raw;
  const [local, domain] = raw.split('@', 2);
  return `${local.split(':', 1)[0]}@${domain}`;
};

const message = String(input.message || '').trim().toLowerCase();
const fromMe = input.fromMe === true;
const targetJid = canonicalJid(input.targetJid);
const adminJid = canonicalJid(input.adminJid);
const remoteJid = canonicalJid(input.remoteJid);

const isMenuCommand = message === '/menu' || message === 'menu';
const isSelfTarget = Boolean(
  targetJid &&
  ((adminJid && targetJid === adminJid) || (remoteJid && targetJid === remoteJid && adminJid === remoteJid))
);

const shouldSkipBackend = Boolean(
  fromMe &&
  targetJid &&
  !isSelfTarget &&
  !isMenuCommand
);

if (shouldSkipBackend) {
  return [{
    json: {
      ...input,
      reply: '',
      no_reply: true,
      status: 'closed',
      close_jid: targetJid,
      close_jids: [targetJid],
      skip_console_call: true,
      guard_reason: 'from_me_external_non_menu',
    },
  }];
}

return [{ json: { ...input, skip_console_call: false } }];
```

The exact JavaScript can be refined during implementation, but the semantics are fixed: external `fromMe=true` non-menu messages must bypass backend and close the target chat session.

### 2. Route guarded items around `Console call`

Add an IF node after the guard:

```text
IF skip_console_call === true
```

Routing:

- `true` branch: skip `Console call` and skip `Evolution API Send`; go to `Check close session` using the guard output item.
- `false` branch: continue through the existing `Config` / `Console call` / `Merge & lookup data` path.

The true branch must preserve enough fields for `Check close session` and `Close session`:

- `apiKey`
- `remoteJid`
- `close_jid`
- `close_jids`
- `status`
- `no_reply`

### 3. Preserve `/menu` and `menu` for Client Context Shortcut

If `fromMe=true` and the target is external, `/menu` and `menu` are intentionally allowed to continue to the backend.

This preserves the existing Client Context Shortcut behavior:

- tenant admin selects or is in a chat with a target contact;
- tenant admin sends `/menu`;
- Evolution Go opens or continues the session;
- n8n calls TrackPal backend;
- backend renders the contextual management menu privately to the admin.

### 4. Preserve inbound code lookup

If `fromMe=false`, the guard must not skip backend.

This ensures Tenant B still receives Tenant A's `code` message as a normal inbound message and can start the unauthenticated code lookup flow.

### 5. Use session closure, not reply-text filtering, as the main control

The guard output uses:

```json
{
  "reply": "",
  "no_reply": true,
  "status": "closed",
  "close_jid": "<targetJid>",
  "close_jids": ["<targetJid>"]
}
```

`no_reply=true` prevents any user-facing bot reply from Tenant A. `status="closed"` plus `close_jid` tells the existing close-session path to close the accidental Evolution Go session for the external target chat.

Generated-reply filters may still exist as defensive noise reduction, but they are not the fix for TPL-9.

## Data flow after change

### Tenant A sends `code` to Tenant B

1. Tenant A sends `code` to Tenant B.
2. Tenant A's Evolution Go instance sees the outgoing message as `fromMe=true` and dispatches to n8n because `code` matches the shared trigger.
3. n8n `Parse input` emits `fromMe=true`, `targetJid=TenantB`, and `message=code`.
4. `Guard fromMe external non-menu` sets `skip_console_call=true`, `no_reply=true`, `status="closed"`, and `close_jid=TenantB`.
5. n8n skips `Console call`, so TrackPal backend is not called for Tenant A's outgoing `code`.
6. n8n skips Evolution send and closes the Tenant A ↔ Tenant B Evolution Go session for Tenant A's instance.
7. Tenant B still receives the real inbound `code` message and processes the code lookup normally.
8. Tenant B's menu response arrives at Tenant A, but Tenant A no longer has the accidental open session, and the menu text does not match the initial trigger.
9. The loop stops.

### Tenant A sends `/menu` in an external chat

1. Tenant A sends `/menu` while targeting an external chat.
2. n8n guard sees `fromMe=true`, external target, and a menu command.
3. `skip_console_call=false`.
4. Existing backend Client Context Shortcut flow runs unchanged.

### Tenant B receives inbound `code`

1. Tenant B's Evolution Go instance receives Tenant A's message as inbound `fromMe=false`.
2. n8n guard does not skip backend.
3. Backend processes unauthenticated code lookup as before.

## Error handling and observability

- The guard should include `guard_reason: 'from_me_external_non_menu'` on skipped items for n8n execution inspection.
- The guard should not throw for missing optional fields. Missing `targetJid` means the guard should let the item continue to backend rather than risk dropping legitimate messages.
- The guard should canonicalize JIDs by removing device suffixes such as `:81` before comparing admin and target JIDs.
- If `apiKey` is missing, the close-session HTTP request may fail in the existing workflow. The guard should still avoid the backend call, because preventing backend load and bot reply remains safer than forwarding an accidental `fromMe` dispatch.
- `no_reply=true` must prevent any Evolution send on the guard branch.

## Testing strategy

### n8n workflow checks

Validate with representative parsed items:

1. `fromMe=true`, `message="code"`, external `targetJid` → `skip_console_call=true`, backend not called, close item emitted for `targetJid`.
2. `fromMe=true`, `message="codigo"`, external `targetJid` → same as above.
3. `fromMe=true`, `message="código"`, external `targetJid` → same as above.
4. `fromMe=true`, `message="hello"`, external `targetJid` and an already-open session → same as above.
5. `fromMe=true`, `message="/menu"`, external `targetJid` → `skip_console_call=false`, backend called.
6. `fromMe=true`, `message="menu"`, external `targetJid` → `skip_console_call=false`, backend called.
7. `fromMe=false`, `message="code"` → `skip_console_call=false`, backend called.
8. Missing `targetJid` → `skip_console_call=false`, backend called.
9. Admin self-target with `fromMe=true` → `skip_console_call=false`, backend called.
10. Target JID with device suffix and admin JID without suffix should compare correctly after canonicalization.

### Manual end-to-end check

1. Tenant A sends `code` to Tenant B.
2. Confirm Tenant A's n8n execution skips `Console call` and closes `targetJid`.
3. Confirm Tenant B's n8n execution calls backend and sends the code-service menu.
4. Confirm Tenant A does not respond to Tenant B's menu.
5. Confirm Tenant A can still send `/menu` in a client chat and get the Client Context Shortcut.
6. Confirm a normal external user can still send `code` to a tenant and receive the code-service menu.

## Rollout notes

- This is an n8n workflow-only change for the initial fix.
- No database migration is required.
- No backend deploy is required for the selected fix.
- No Evolution Go deploy is required for the selected fix.
- Import or update `n8n/TrackPal WhatsApp Bot.json` after editing the workflow.
- Keep the previous workflow export available for rollback.
- If the guard accidentally blocks `/menu`, rollback immediately because that would break Client Context Shortcut.

## Deferred improvement

A cleaner long-term Evolution Go enhancement would add a separate configurable trigger for `fromMe` session starts. TrackPal could then configure normal inbound triggers as `/menu|codigo|código|code`, while allowing `fromMe` session starts only for `/menu|menu`.

That improvement would prevent even the n8n execution for outgoing `code`, but it requires Evolution Go model/API changes and is intentionally out of scope for this first TPL-9 fix.

## Spec self-review

- Placeholder scan: no placeholders, `TBD`, or incomplete sections remain.
- Internal consistency: the design consistently treats n8n as the first fix and avoids backend/Evolution Go changes.
- Scope check: the scope is a single n8n workflow change with explicit non-goals; it is appropriate for one implementation plan.
- Ambiguity check: external non-menu `fromMe` behavior is explicit, and `/menu`/`menu`, inbound `code`, missing `targetJid`, and self-target cases are all specified.
