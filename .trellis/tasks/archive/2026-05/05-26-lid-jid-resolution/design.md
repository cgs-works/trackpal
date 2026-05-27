# Design — LID/JID resolution end-to-end

## Scope

Repos:
- `trackpal` (`backend` + `n8n/Trackpal WhatsApp Bot.json`)
- `evolution-go` (chatbot webhook payload and LID resolution)

## Architecture Changes

1. Evolution-go webhook payload enrichment
- Source: incoming message event (`events.Message`).
- Compute:
  - `senderPn`: phone JID when available (`@s.whatsapp.net`)
  - `senderLid`: LID JID when available (`@lid`)
- Emit both in chatbot payload sent by `pkg/webhook/service/listener.go`.

2. n8n Parse Input contract
- Prefer `senderPn` to derive canonical phone.
- If no `senderPn` and `remoteJid` is `@lid`:
  - do not derive phone from LID digits.
  - pass `senderLid` (or `remoteJid` LID) explicitly to backend.
- Keep original `remoteJid` unchanged for outbound reply target (Evolution sendText path).
3. Backend identity resolution
- Extend request schema for optional `sender_lid` (or equivalent field name aligned with payload).
- In `integrations/console.py` flow:
  - phone path unchanged for canonical phone values.
  - when phone unavailable but LID present: resolve identity by `whatsapp_lid`.
  - update `_route_by_instance` to support LID lookup for tenant-admin/client paths and ambiguity handling.
- Add `whatsapp_lid` nullable columns for:
  - `master_profiles`
  - `tenants`
  - `clients`
4. Repository/service lookup
- Add lookup by LID in user resolution path (`AuthService` + repositories).
- Add persistence path: when payload carries both `senderPn` and `senderLid`, save/update `whatsapp_lid` for matched entity (progressive fill).
- Ensure precedence:
  - phone match first when valid phone exists
  - fallback to LID lookup
## Data Model

- New nullable string columns:
  - `master_profiles.whatsapp_lid`
  - `tenants.whatsapp_lid`
  - `clients.whatsapp_lid`
- Add indexes for lookup performance.
- No mandatory backfill; progressive fill from live traffic.

## Compatibility

- Existing phone/JID flow stays backward compatible.
- No conversion of `@lid` to phone digits anywhere.
- Phone normalizer must explicitly reject `@lid` as canonical phone input.
- Unknown LID without mapping returns deterministic unknown-access reply.
## Risks

- Whatsmeow LID->PN mapping may be empty for first contact.
- Dual-repo rollout sequencing required:
  1) evolution-go payload fields
  2) n8n/backend consumer
