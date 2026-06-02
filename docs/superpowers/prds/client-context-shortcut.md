# Client Context Shortcut PRD

## Problem Statement

Tenant administrators manage clients and subscriptions from their main WhatsApp Tenant console. When an administrator is already in a WhatsApp conversation with a client and needs to perform an administrative action for that specific identity, they must leave that chat, open the bot chat, navigate the Tenant console, find the client, and then act. This context switch slows down operations.

Tenant instances also need to support unauthenticated client-side code lookup for WhatsApp identities that are not registered as Clients, while allowing Tenant administrators to block that code-lookup access for specific unregistered identities.

## Goals

1. Let a Tenant administrator trigger a private administrative shortcut for the current client chat by sending `/menu` in that chat.
2. Ensure all administrative shortcut messages are sent only to the administrator's private bot chat, never to the client chat.
3. Preserve the administrator's existing Tenant console session while a temporary contextual session is active.
4. Support unregistered WhatsApp identities that can request access codes, unless blocked by a Tenant administrator.
5. Add persistent, reversible Client Messaging Blocks for unregistered WhatsApp identities.

## Non-Goals

- Displaying administrative menu content inside a client chat.
- Applying Client Messaging Blocks to registered Clients. Registered Clients continue to use the existing activation/deactivation model.
- Implementing Evolution Go changes inside this repository; those changes are an external subtask.

## Domain Terms

- **Client Context Shortcut**: Temporary administrative access initiated from a conversation with a client identity, with all administrative interaction moved to the Tenant administrator's private bot chat.
- **Client Messaging Block**: Persistent tenant-scoped block for an unregistered WhatsApp identity that prevents client-side console/code-lookup interaction.

## User Stories

1. As a Tenant administrator, I want to send `/menu` in a client's chat so I can manage that specific identity without navigating the full Tenant console.
2. As a Tenant administrator, I want the contextual menu to appear in my private bot chat so the client never sees administrative options.
3. As a Tenant administrator, I want an unregistered target identity to offer `Create client`, `Block client messaging`, and `0 Cancel`.
4. As a Tenant administrator, I want `Create client` to skip phone entry when the target phone is available, while preserving the existing required fields: full name, local username, password, and confirmation.
5. As a Tenant administrator, I want a target with only `@lid` and no phone to ask for phone during Client creation instead of deriving a phone from LID.
6. As a Tenant administrator, I want inactive Clients to count as existing Clients, not as unregistered identities, so Trackpal prevents duplicate client records.
7. As a Tenant administrator, I want inactive Clients to expose reactivation before subscription creation.
8. As a Tenant administrator, I want the contextual menu for an existing Client to expose the Tenant console's client detail actions, except phone editing.
9. As a Tenant administrator, I want active existing Clients to support `Create subscription` while skipping client selection.
10. As a Tenant administrator, I want Client Messaging Blocks to be reversible from both the shortcut for that identity and the Clients section of the Tenant console.
11. As a Tenant administrator, I want `0` to close any active contextual session from any depth.
12. As a Tenant administrator, I want a new contextual `/menu` trigger to be rejected while another Client Context Shortcut is active.
13. As a Tenant administrator, I want contextual sessions to expire after 5 minutes of inactivity.
14. As a user of an unregistered WhatsApp identity, I can use only the client-side code lookup flow, not profile or subscription views, unless my identity is blocked.

## WhatsApp and n8n Contract

### Incoming n8n payload to backend

For contextual triggers, n8n sends an explicit actor/target contract instead of overloading `phone`:

- `from_me: true`
- `instance`: Evolution instance name
- `message`: normalized message text
- `admin_phone`: phone from `senderPn` when available
- `admin_jid`: full Evolution-compatible private-chat JID for the admin
- `target_jid`: full JID from `remoteJid`
- `target_phone`: normalized phone when the target is a phone JID
- `target_lid`: LID when the target is an `@lid` identity
- `sender_lid`: existing sender LID field for inbound compatibility

If `admin_phone` is unavailable on a `from_me=true` event, backend routing falls back to the tenant owner resolved by `instance` as the acting admin.

### Backend response to n8n

The backend response adds:

- `reply_to: str | null`: full Evolution-compatible JID where n8n must send the reply. Contextual administrative replies use `reply_to=<admin_jid>`.
- `no_reply: bool`: when `true`, n8n sends nothing to Evolution and bypasses the current empty-reply fallback.

Existing fields remain:

- `reply`
- `status`
- `lookup_job_id`
- `tenant_id`

## Routing Rules

1. Routing remains instance-first.
2. `from_me=true` and target equals admin chat routes to the standard Tenant console.
3. `from_me=true` and target differs from admin chat routes to the Client Context Shortcut.
4. Contextual responses always include `reply_to=<admin_jid>`.
5. If a contextual session is already active and the admin sends `/menu` in another client chat, backend rejects the new context privately via `reply_to=<admin_jid>`.
6. If a contextual session is already active and the admin sends `/menu` in the private bot chat, backend returns a blocking message explaining that `0` must be sent before opening the regular Tenant console.
7. Registered inactive Clients do not fall back to unauthenticated code lookup.
8. Deleted Clients become unregistered identities and may use unauthenticated code lookup unless a Client Messaging Block exists.

## Contextual Session Rules

- Redis namespace: `wa:client_ctx:{admin_phone}`.
- Regular Tenant console session remains in `session:admin:{phone}` and is not overwritten.
- While `wa:client_ctx:{admin_phone}` exists, private bot-chat messages route to the contextual facade before the regular Tenant console.
- TTL: 5 minutes.
- Only valid contextual messages refresh TTL; invalid inputs do not.
- `0` is the only manual close command.
- At any depth, `0` aborts the active contextual flow, clears the contextual Redis key, and resumes normal Tenant console routing.
- Completing any contextual action also clears the contextual Redis key.

## Contextual Menus and Flows

### Unregistered, unblocked target

Menu:

1. Crear cliente
2. Bloquear mensajes
0. Cancelar

Behavior:

- `Crear cliente` starts the current client creation flow, skipping phone only if `target_phone` exists.
- If only `target_lid` exists, creation asks for phone.
- `Bloquear mensajes` creates a Client Messaging Block immediately, without confirmation and without asking for a reason.
- Any completed action closes the context.

### Unregistered, blocked target

Menu:

1. Desbloquear mensajes
0. Cancelar

Behavior:

- `Desbloquear mensajes` clears the Client Messaging Block and closes the context.

### Existing active Client

Menu includes:

- Client detail actions from the Tenant console.
- Create subscription shortcut with client selection skipped.
- Deactivate Client.
- Delete only when the same eligibility rules as the Tenant console allow it.

Constraint:

- Contextual edit must not allow editing the Client phone, because the phone/JID is the target identity that opened the context.

### Existing inactive Client

Menu includes:

- Reactivate Client.
- Delete Client when eligible.
- Edit allowed fields except phone.

Constraint:

- Create subscription is not available until the Client is reactivated.

## Client Messaging Blocks

Create a dedicated tenant-scoped database table for unregistered WhatsApp identity blocks.

Required properties:

- tenant id
- phone, nullable
- LID, nullable
- active state
- timestamps

Rules:

- At least one of phone or LID is required.
- Blocks apply only to identities with no Client row in that tenant.
- If an admin creates a Client for a blocked identity, the block is automatically cleared as part of successful Client creation.
- Blocks are persistent until explicitly unblocked.
- Blocks can be unblocked from the shortcut and from the Tenant console Clients section.

## Tenant Console Changes

The regular Tenant console Clients menu becomes:

1. Ver clientes
2. Crear cliente
3. Bloqueos de mensajes
9. Volver al menú principal

Implementation must align handlers with the displayed `9` back command. Current Clients flow code paths that treat `0` as the Clients-menu back command should be corrected as part of this work.

## Unauthenticated Client Code Lookup

Unregistered WhatsApp identities in a tenant instance may use only code lookup:

1. They trigger with `codigo`, `código`, or `code`.
2. Backend checks Client Messaging Block first.
3. If blocked, backend returns `no_reply=true`.
4. If unblocked, backend starts the existing code lookup flow: service selection, then target email.
5. Replies and final lookup results are sent to the requesting WhatsApp identity's chat, not to the tenant admin.
6. They cannot view profile or subscriptions unless they are registered Clients.

Blocked unregistered identities also receive `no_reply=true` for `/menu` or any other client-side console attempt.

## External Evolution Go Subtask

Evolution Go must expose enough data for n8n to build the actor/target contract:

- inject `fromMe` into webhook payloads;
- dispatch outgoing `fromMe=true` `/menu` events instead of skipping them when normal inbound sender fields are empty;
- provide or allow reconstruction of `admin_jid`, `target_jid`, target phone/LID, and `senderPn` when available.

Evolution Go tests live in the Evolution Go repository, not in Trackpal.

## Testing Decisions

### Backend API layer

Expand `test_console.py` to cover:

- `from_me=true` target equals admin chat routes to Tenant console;
- `from_me=true` target differs from admin chat routes to Client Context Shortcut;
- missing `admin_phone` uses instance-owner fallback;
- contextual responses include `reply_to=<admin_jid>`;
- active-context collision rejects privately via `reply_to=<admin_jid>`;
- blocked unregistered client-side attempts return `no_reply=true`.

### Backend service layer

Create `test_whatsapp_client_context.py` using existing async fixtures to cover:

- unregistered target menu;
- create client with target phone skipped;
- create client with LID-only target asking for phone;
- immediate Client Messaging Block creation;
- unblock flow;
- active and inactive Client menus;
- inactive Client cannot create subscription;
- active Client subscription shortcut skips client selection;
- `0` aborts at any depth and clears context;
- completed action clears context;
- invalid input does not refresh TTL;
- concurrent context collision is rejected.

### n8n workflow

Update workflow tests/manual validation to cover:

- parser extracts `fromMe`, `admin_jid`, `target_jid`, `target_phone`, and `target_lid`;
- Console Call sends the new fields;
- Merge node preserves `reply_to` and `no_reply`;
- send node uses `reply_to` when present;
- workflow sends nothing when `no_reply=true`.

## Open Risks

- The external Evolution Go payload must reliably distinguish admin actor and target chat for `fromMe=true` events.
- Instance-owner fallback is acceptable for the current single-admin tenant model, but would need revisiting if multiple tenant admins are introduced.
