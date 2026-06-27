# Client Context Shortcut Repair Design

## Purpose

Repair the Client Context Shortcut so `/menu` behaves predictably for Tenant admins, sends an intuitive private client-management menu, closes the correct Evolution session, reduces unnecessary Redis reads, and aligns all backend-rendered messages with TrackPal i18n.

## Approved Behaviour

### Self chat

When a Tenant admin sends `/menu` in their own private Tenant chat, TrackPal must route to the normal Tenant console menu. It must not create a Client Context Shortcut and must not treat the Tenant admin as a client.

### Client or external chat

When a Tenant admin sends `/menu` in a chat that is not their own private Tenant chat, TrackPal must open a temporary Client Context Shortcut for that target identity and immediately send the relevant contextual menu to the Tenant admin's private chat.

Administrative shortcut messages must never be sent to the target/client chat.

### Private contextual menu copy

The first private response must be action-oriented and intuitive. It must not only say “context started”. The approved title is `Gestión del cliente` / `Client management`.

Rules:

- Label phone as `Número de teléfono` / `Phone number`.
- Show phone digits without `+`.
- If only WhatsApp LID is available, do not show the LID and do not mention that only an identifier was received.
- Use `0 Cancelar` / `0 Cancel`, not “Cerrar gestión rápida”.

Unregistered, unblocked Spanish example:

```text
📌 *Gestión del cliente*

Este contacto todavía no existe como cliente.
El cliente no ve este menú.

Número de teléfono: 34600111222

Elige una opción:
1️⃣ Crear cliente para este número
2️⃣ Bloquear acceso
0️⃣ Cancelar
```

Unregistered, blocked Spanish example:

```text
📌 *Gestión del cliente*

Este contacto tiene bloqueado el acceso al sistema.
No puede pedir códigos, ver perfil ni consultar suscripciones.

Número de teléfono: 34600111222

Elige una opción:
1️⃣ Desbloquear acceso
0️⃣ Cancelar
```

Existing active Client Spanish example:

```text
📌 *Gestión del cliente*

Estás administrando este cliente desde tu panel privado.
El cliente no ve este menú.

Cliente: Ana Pérez
Número de teléfono: 34600111222
Estado: ✅ Activo

Elige una opción:
1️⃣ Ver detalle
2️⃣ Editar cliente
3️⃣ Crear suscripción
4️⃣ Desactivar cliente
5️⃣ Eliminar cliente
0️⃣ Cancelar
```

Existing inactive Client Spanish example:

```text
📌 *Gestión del cliente*

Estás administrando este cliente desde tu panel privado.
El cliente no ve este menú.

Cliente: Ana Pérez
Número de teléfono: 34600111222
Estado: ❌ Inactivo

Elige una opción:
1️⃣ Ver detalle
2️⃣ Editar cliente
3️⃣ Reactivar cliente
4️⃣ Eliminar cliente
0️⃣ Cancelar
```

English equivalents must exist in the backend i18n catalog.

## Contextual Menu Variants

The backend renders the initial menu according to target state:

1. **Unregistered, unblocked**
   - `1 Crear cliente para este número` when target phone exists.
   - `1 Crear cliente` when only LID exists.
   - `2 Bloquear acceso`.
   - `0 Cancelar`.

2. **Unregistered, blocked**
   - `1 Desbloquear acceso`.
   - `0 Cancelar`.

3. **Existing active Client**
   - Full contextual Client CRUD using this target client as implicit context.
   - View detail.
   - Edit allowed fields except phone.
   - Create subscription with client preselected.
   - Deactivate Client.
   - Delete only when the same eligibility rules as the Tenant console allow it.
   - `0 Cancelar`.

4. **Existing inactive Client**
   - Full contextual Client CRUD using this target client as implicit context.
   - View detail.
   - Edit allowed fields except phone.
   - Reactivate Client.
   - Delete Client when eligible.
   - Create subscription remains unavailable until reactivation.
   - `0 Cancelar`.

Contextual flows must never ask the admin to select the client again. If the target phone is known, client creation must not ask for phone; it creates the client associated with that phone. If only LID is known, creation asks for phone without exposing the LID in the menu.

## Blocked Clients Table

Rename `client_messaging_blocks` to `blocked_clients`.

Meaning:

- Stores tenant-scoped WhatsApp identities that are not registered Clients.
- If an identity is present and active in `blocked_clients`, that person cannot use any WhatsApp console surface for that tenant.
- Blocked access includes code lookup, `/menu`, profile, subscriptions, and any client-side console attempt.
- This is not “message blocking”; it is system access blocking for unregistered identities.

Rules:

- Table has tenant id, phone nullable, WhatsApp LID nullable, active state, timestamps.
- At least one of phone or LID is required.
- Blocks apply only to identities with no Client row in that tenant.
- Registered Clients use normal Client activation/deactivation, not `blocked_clients`.
- If an admin creates a Client for a blocked identity, the block is automatically cleared as part of successful Client creation.
- Blocks are persistent until explicitly unblocked.
- Blocks can be unblocked from the shortcut and from the Tenant console Clients section.

## Closing Semantics

When the Tenant admin sends `0` inside the Client Context Shortcut, TrackPal must perform a total Tenant-side close:

1. Delete `wa:client_ctx:{admin_phone}`.
2. Delete the normal Tenant console session `session:admin:{admin_phone}`.
3. Return a localized close reply to the Tenant admin private chat.
4. Return `status="closed"`.
5. Return `close_jid=<admin_jid>` so n8n closes the Tenant admin private Evolution session, not the target/client chat.

## Backend/n8n Response Contract

`WhatsAppConsoleResponse` must support:

- `reply_to`: exact JID where n8n sends the reply. Contextual admin responses use `admin_jid`.
- `no_reply`: when true, n8n sends nothing.
- `status="closed"`: close requested.
- `close_jid`: exact JID n8n must close in Evolution.

Rules:

- Context started: `reply_to=admin_jid`, `status=null`, `close_jid=null`.
- Context closed: `reply_to=admin_jid`, `status="closed"`, `close_jid=admin_jid`.
- n8n Close Session node must use `close_jid || reply_to || remoteJid`.

## i18n Requirements

Backend owns all user-facing strings. n8n remains pure transport.

All Client Context Shortcut replies must use backend i18n keys under:

```text
wa.tenant.client_context.*
```

Required key groups:

- `menu.unregistered_with_phone`
- `menu.unregistered_lid_only`
- `menu.blocked_with_phone`
- `menu.blocked_lid_only`
- `menu.active`
- `menu.inactive`
- `closed`
- `collision`
- `invalid_option`
- `create.*`
- `block_access.*`
- `unblock_access.*`

No user-facing hardcoded literals should remain in `console.py` or `console_context_shortcut.py` for this flow.

## Redis Optimization

Implementation should reduce redundant Redis access without strict numeric budgets:

- Read active client context at most once per relevant request path.
- Do not read the normal Tenant session when an active Client Context Shortcut consumes the message.
- Cache stable context metadata in the context payload: `tenant_id`, `locale`, `target_identity`, `target_phone`, `target_state`, `menu_variant`, `client_id`, and `admin_jid`.
- Use atomic delete or pipeline-style operations where practical for closing context plus Tenant session.
- Avoid recalculating target state unless an action changes it, such as client creation, block/unblock, reactivation, deletion, or subscription creation.

## Testing Scope

Backend tests must cover:

- `/menu` from Tenant private chat routes to normal Tenant console.
- `/menu` from external/client chat starts context and immediately returns target-specific menu.
- Initial contextual response uses `reply_to=admin_jid`.
- `0` inside context deletes contextual and Tenant sessions and returns `status="closed"` plus `close_jid=admin_jid`.
- Existing active, existing inactive, unregistered unblocked, and unregistered blocked variants render correct menus.
- Registered active client menu includes deactivate.
- Registered client flows do not ask for phone or client selection.
- Unregistered phone target creation starts with target phone prefilled.
- LID-only menus hide the LID.
- Locale `es` and `en` render from i18n catalogs.
- No reply is sent to target/client chat.
- `blocked_clients` prevents unregistered identities from code lookup, `/menu`, profile, subscriptions, and any client-side console attempt.

n8n validation/manual tests must cover:

- Parser preserves admin/target fields for `fromMe=true`.
- Send node uses `reply_to` for private contextual replies.
- Close node uses `close_jid || reply_to || remoteJid`.
- `no_reply=true` skips all sends.

## Non-goals

- Evolution Go code changes inside TrackPal repository.
- Client-specific locale override.
- Redesigning all Tenant console menus outside the Client Context Shortcut work.
