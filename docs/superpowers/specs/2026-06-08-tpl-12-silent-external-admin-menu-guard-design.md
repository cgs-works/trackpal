# TPL-12 Design: Silent External Admin `/menu` Guard

## Purpose

Prevent cross-tenant WhatsApp bot loops when a TrackPal tenant admin sends `/menu` in another tenant's chat, while preserving the Client Context Shortcut, normal client access, and unauthenticated code lookup.

The fix should make the receiving tenant stay silent when `/menu` is clearly an external TrackPal admin shortcut, instead of replying with "No tienes una cuenta registrada" / "You do not have a registered account" and starting a bot-to-bot loop.

## Decisions captured

- The urgent fix belongs in TrackPal backend + n8n workflow, not as a first-pass Evolution Go redesign.
- The backend should be the authority for deciding whether an inbound `/menu` came from another TrackPal tenant/admin because it can query TrackPal identities.
- The receiving tenant should only silence the exact command `/menu`; plain `menu`, `code`, `codigo`, and `código` remain normal user/client inputs.
- If the sender is already an active Client of the receiving tenant, do not silence them under this guard.
- When the guard silences a message, it must still close the Evolution Go chatbot session for the sender JID.
- n8n must not let `no_reply=true` prevent the close-session path when the backend also returns `status="closed"` and `close_jid`.
- Add generated-reply text filtering only as defensive loop reduction, not as the primary fix.
- Verify the deployed Evolution Go build because current `main` already emits `adminJid=instance.Jid` for `fromMe=true`; production may be on an older build or have missing `instance.Jid` data.

## Problem

TrackPal enables Evolution Go `listeningFromMe` so tenant admins can send `/menu` from a WhatsApp chat with a client or unregistered contact and receive a private Client Context Shortcut menu.

That same outbound `/menu` is also a real WhatsApp message delivered to the target chat. If the target is another TrackPal tenant, the receiving tenant's Evolution Go instance sees the message as inbound (`fromMe=false`). The backend does not recognize the sender as a client of the receiving tenant, so it may reply with `wa.client.not_registered`.

That reply can bounce back into the sender tenant's bot session and produce a ping-pong loop:

1. Tenant A admin sends `/menu` to Tenant B.
2. Tenant A's instance handles the outbound `fromMe=true` shortcut.
3. Tenant B's instance receives the same message as inbound `fromMe=false`.
4. Tenant B treats the sender as unregistered and replies with `wa.client.not_registered`.
5. Tenant A receives that generated reply. If an Evolution Go session is open for Tenant B, the message continues the session without trigger reevaluation.
6. Tenant A sends its own fallback/generated reply.
7. The two bot instances can continue replying until session expiry or manual closure.

The desired behavior is not to block the outgoing WhatsApp message. The target tenant will receive it. The desired behavior is for TrackPal to recognize external admin `/menu` as a technical shortcut and make the receiving tenant's bot stay silent and close the sender session.

## Verified current behavior

### TrackPal backend

- `_route_by_instance()` resolves the receiving tenant from the Evolution instance and then routes inbound identities by tenant admin, client, or unregistered sender.
- Unregistered senders are allowed to start unauthenticated code lookup with `codigo`, `código`, or `code`.
- Non-code unregistered messages fall through to user-facing replies such as `wa.client.not_registered` or access-denied style messages.
- Tenant admins can also be clients, so broad cross-tenant blocking is not acceptable.

### TrackPal n8n workflow

- `Parse input` extracts `message`, `fromMe`, `remoteJid`, `senderPn`, `senderLid`, `adminJid`, `targetJid`, `targetPhone`, and `targetLid` where available.
- `Evolution API Send` sends to `reply_to || phone || remoteJid`, so an absent or incorrect `reply_to` can route a private admin menu to the wrong chat.
- `Close session` calls Evolution Go `/webhook/change-status` with `remoteJid` from `close_jid || reply_to || remoteJid`.
- Existing generated-reply filtering does not include `wa.client.not_registered` in Spanish or English.

### Evolution Go

- Current Evolution Go `main` builds dispatch payloads with `adminJid = instance.Jid` and `targetJid = remoteJid` for `fromMe=true` messages.
- Current Evolution Go opens a chatbot session for the target `remoteJid` when a `fromMe=true` trigger matches, and also opens an admin alias session using `instance.Jid`.
- When a session is already open, Evolution Go dispatches follow-up messages without reevaluating the trigger.
- `/webhook/change-status` with `status="closed"` deletes sessions by exact `remoteJid`.

## Goals

- Prevent Tenant B from sending `wa.client.not_registered` when it receives `/menu` from another TrackPal tenant/admin who is not a client of Tenant B.
- Close the receiving tenant's Evolution Go session for that sender so later generated bot replies do not continue an open session.
- Preserve Tenant A's Client Context Shortcut when the admin intentionally sends `/menu` from an external chat.
- Preserve tenant-to-tenant code lookup: `code`, `codigo`, and `código` must still reach the receiving tenant's unauthenticated code flow.
- Preserve normal client access for users who are active clients of the receiving tenant.
- Keep the urgent implementation small enough for one plan.

## Non-goals

- Do not redesign Evolution Go session strategies in this urgent fix.
- Do not disable `listeningFromMe`.
- Do not remove `/menu`, `menu`, `code`, `codigo`, or `código` from webhook triggers.
- Do not block all messages from tenants/admins to other tenants.
- Do not prevent a tenant/admin from also being a client of another tenant.
- Do not rely on generated-reply text filters as the primary loop prevention mechanism.
- Do not change the code lookup dialog behavior.

## Design

### 1. Add a narrow backend guard for inbound external admin `/menu`

Add a helper in the WhatsApp console routing layer, near the unregistered known-tenant branch:

```python
async def _should_silence_external_admin_menu(
    *,
    tenant: Tenant,
    phone_digits: str,
    sender_lid: str | None,
    message: str,
    db: AsyncSession,
) -> bool:
    ...
```

The helper returns `True` only when all of these are true:

1. `message.strip() == "/menu"` exactly after trimming.
2. The inbound sender is not the receiving tenant's own admin identity.
3. The inbound sender is not an active Client of the receiving tenant.
4. The inbound sender matches an active TrackPal tenant/admin identity belonging to a different tenant.

When the helper returns `True`, return a silent closed response:

```python
return WhatsAppConsoleResponse(
    reply="",
    no_reply=True,
    status="closed",
    close_jid=close_jid,
)
```

Do not include `reply_to` in this silent response. The workflow should route closure from `close_jid`, and omitting `reply_to` removes an unnecessary fallback path back to the external admin chat if workflow logic is changed later.

`close_jid` should be the sender's canonical phone JID when `phone_digits` is available, otherwise the sender LID if that is the only identity available.

### 2. Add tenant identity lookup support

Extend `tenants_repository` with a focused helper that can identify active tenant/admin WhatsApp identities:

```python
async def get_active_by_whatsapp_identity(
    db: AsyncSession,
    *,
    phone_digits: str | None = None,
    whatsapp_lid: str | None = None,
) -> Tenant | None:
    ...
```

Semantics:

- Compare phone identities using normalized digits, not raw string equality.
- Compare LID identities using exact `Tenant.whatsapp_lid`.
- Return only active tenants.
- Return `None` when neither phone nor LID is available.

This helper is intentionally tenant-focused. It should not alter client lookup behavior.

### 3. Insert the guard before unregistered fallback replies

The guard should run in the known-tenant, non-admin, non-client path before any user-facing unregistered/access-denied reply is emitted.

Recommended placement:

1. `_route_by_instance()` resolves `tenant` from `instance`.
2. Existing admin/client/block/session checks run as today.
3. Before starting or resuming unauthenticated code fallback for non-code messages, call `_should_silence_external_admin_menu()`.
4. If it returns true, return the silent closed response.
5. Otherwise continue existing code lookup and unregistered behavior.

This keeps the rule close to the exact fallback it prevents and avoids affecting identified tenant admins or identified clients.

### 4. Preserve supported user flows

The guard must not silence these cases:

- `message == "menu"`: plain menu remains a normal client/user input.
- `message in ("code", "codigo", "código")`: unauthenticated code lookup remains available.
- sender is an active Client of the receiving tenant: route existing client behavior.
- sender is the receiving tenant's own admin: route existing tenant admin behavior.
- sender is unknown and not a TrackPal tenant/admin: existing unregistered behavior remains unchanged.

### 5. Harden `from_me` admin identity resolution in backend

Keep the separate but related TPL-12 fix for `fromMe=true` routing:

- In `_handle_from_me_routing()`, derive `resolved_admin_phone` authoritatively from the tenant resolved by `instance` when `tenant.whatsapp_phone` is present.
- Only fall back to n8n's `admin_phone` when the tenant record does not yet provide a usable phone.
- Build `resolved_admin_jid` from `_canonical_jid(admin_jid) or admin_jid or f"{resolved_admin_phone}@s.whatsapp.net"`.
- Use `resolved_admin_jid` for `reply_to`, `temp_data["admin_jid"]`, and close-session targets that refer to the admin's private chat.
- If no authoritative admin phone can be resolved, prefer a safe no-reply fallback plus logging over routing a private admin response to an ambiguous target chat.

This protects Client Context Shortcut when the deployed Evolution Go payload omits `adminJid`, or when n8n parsed `phone` as the target instead of the admin.

### 6. Ensure n8n closes sessions even for no-reply backend responses

The current workflow graph already supports this contract; no structural n8n routing change is required.

- `no_reply=true` must prevent `Evolution API Send`.
- `status="closed"` plus `close_jid` or `close_jids` must still reach `Check close session` and `Close session`.
- The existing `IF no reply -> Check close session -> Close session` path is compatible with the silent guard response.

This is mandatory for the silent guard. A silent response that does not close the Evolution Go session only hides one message and leaves the loop risk in memory.

### 7. Add defensive generated-reply filtering

Extend `Parse input` generated-reply filtering to drop TrackPal's not-registered messages when they arrive inbound:

- `no tienes una cuenta registrada`
- `you do not have a registered account`

This is a defensive belt-and-suspenders measure. The primary fix is the backend guard that prevents Tenant B from sending those messages for external admin `/menu` in the first place.

### 8. Verify Evolution Go deployment state

Before rollout, verify the deployed Evolution Go build and instance data:

- The deployed build includes `buildDispatchPayload()` behavior that emits `adminJid=instance.Jid` for `fromMe=true`.
- The affected instances have non-empty `instance.Jid` values.
- `/webhook/change-status` closes sessions for the expected canonical phone JID.

If production lacks any of these, deploy or patch Evolution Go separately before relying on the admin alias behavior.

## Data flows after change

### Tenant A admin sends `/menu` to Tenant B

1. Tenant A admin sends `/menu` in Tenant B's WhatsApp chat.
2. Tenant A instance receives `fromMe=true`; Client Context Shortcut starts or resumes.
3. Tenant B instance receives inbound `fromMe=false` from Tenant A admin.
4. Tenant B backend sees exact `/menu`, checks sender identity, and detects an active external TrackPal tenant/admin.
5. Tenant B backend returns `reply=""`, `no_reply=true`, `status="closed"`, and `close_jid=<Tenant A admin JID>`.
6. n8n skips any text send and calls Evolution Go `change-status` for that close JID.
7. Tenant B sends no not-registered message and keeps no open chatbot session for Tenant A.
8. Tenant A's private admin context can continue through the admin alias/private chat path.

### Tenant A admin sends `code` to Tenant B

1. Tenant A admin sends `code` in Tenant B's chat.
2. Tenant B receives inbound `fromMe=false` with `message="code"`.
3. The external admin `/menu` guard does not apply.
4. Tenant B continues existing unauthenticated code lookup behavior.

### Tenant A is also a client of Tenant B

1. Tenant A admin's phone is registered as an active Client of Tenant B.
2. Tenant B receives a message from that phone.
3. Existing client detection wins before the external admin guard silences anything.
4. The client flow continues normally.

## Error handling and observability

- Add a backend log line when the silent guard triggers, including receiving tenant id, sender phone/LID presence, and reason `external_admin_menu_silenced`.
- Do not include sensitive message bodies beyond the exact command classification.
- If tenant identity lookup fails due to a database exception, fail safe for the guard decision by returning `False`, log the error, and continue existing behavior. Do not accidentally silence legitimate users because identity lookup errored.
- If `close_jid` cannot be computed, return `no_reply=true` without `status="closed"` only as a last resort; log the missing close target. The expected path must compute a canonical close target.
- If n8n close-session call fails, the workflow should still send no reply. Operational logs should surface the failed close call.

## Testing strategy

### Backend tests

1. Inbound `/menu` from another active tenant/admin who is not a client of receiving tenant returns `reply=""`, `no_reply=true`, `status="closed"`, and a non-empty `close_jid`.
2. Inbound `menu` from another active tenant/admin does not trigger the silent guard.
3. Inbound `code`, `codigo`, and `código` from another active tenant/admin do not trigger the silent guard and continue code lookup behavior.
4. Inbound `/menu` from an active Client of the receiving tenant does not trigger the silent guard.
5. Inbound `/menu` from the receiving tenant's own admin does not trigger the silent guard.
6. Inbound `/menu` from an unknown, non-tenant sender keeps existing unregistered behavior.
7. LID-only sender matching another active tenant's `whatsapp_lid` triggers the silent guard when no active receiving-tenant client matches.
8. Duplicate active client lookup errors preserve existing multiple-match behavior instead of being swallowed by the guard.

### n8n workflow tests

1. Backend response with `no_reply=true`, `status="closed"`, and `close_jid` must not call `Evolution API Send`.
2. The same response must reach `Check close session` and `Close session`.
3. `Parse input` generated-reply filter includes both Spanish and English `wa.client.not_registered` fragments.
4. Existing guard behavior for `fromMe=true` external non-menu code commands remains covered.

### Manual end-to-end checks

1. Tenant A sends `/menu` to Tenant B. Tenant A receives the private Client Context Shortcut menu. Tenant B sends no not-registered message.
2. Tenant A answers `1` in the private admin chat. The contextual flow continues and the admin session is not closed prematurely.
3. Tenant A sends `code` to Tenant B. Tenant B serves code lookup normally.
4. Tenant A is registered as a Client of Tenant B and sends normal client commands. Client behavior remains available.
5. Inspect Evolution Go sessions before and after the silent guard to confirm the receiving tenant's sender session is closed.

## Rollout notes

- Backend deploy is required.
- n8n workflow import/update is required if the no-reply close path or generated-reply filter needs changes.
- Evolution Go code change is not required for the urgent fix, but deployed version and `instance.Jid` must be verified.
- Roll out backend first, then n8n. The backend can return the silent closed contract before n8n is updated, but full loop prevention depends on n8n executing `Close session` for no-reply closed responses.
- Keep the TPL-9 behavior for outgoing `code` intact.
- If legitimate clients lose access to `/menu`, rollback the backend guard and re-check the active-client exclusion.

## Deferred Evolution Go improvement

A later Evolution Go enhancement can add a per-webhook `fromMeSessionStrategy` setting:

- `target_and_admin_alias` for current behavior.
- `admin_alias_only` for TrackPal's Client Context Shortcut.
- `target_only` for integrations that want only the external chat session.

TrackPal would use `admin_alias_only` so outbound `/menu` opens only the private admin alias while still passing `targetJid` to n8n/backend. This would remove the need to close the target session after admin shortcuts, but it is larger than the urgent TPL-12 fix.

## Spec self-review

- Placeholder scan: no placeholders, `TBD`, `TODO`, or incomplete sections remain.
- Internal consistency: the design consistently treats the backend guard as the primary fix, n8n close-session handling as required plumbing, and generated-reply filtering as defensive only.
- Scope check: the urgent scope fits one implementation plan across backend tests, backend routing/repository helper, and n8n workflow contract tests/JSON edits. The Evolution Go strategy change is explicitly deferred.
- Ambiguity check: `/menu` is the only silenced command; `menu`, `code`, `codigo`, and `código` are explicitly preserved. Active clients and the receiving tenant's own admin are explicitly excluded from silencing.
