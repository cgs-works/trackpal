# Evolution Go Integration

The backend integrates with **Evolution API** (WhatsApp Business API proxy, versions 2.x Node/Express or Evolution Go) for instance management, webhook registration, and message sending.

> **Note**: The deployed server may run either Evolution API v2.x (Node/Express, `X-Powered-By: Express`) or Evolution Go (Go/Gin). Both expose the same REST contracts for `/instance/create`, `/webhook/*`, and `/send/text`. The `EvolutionClient` is version-agnostic — verify the deployed version via `GET $BASE_URL/` if debugging contract mismatches.

## Client (`app/services/evolution_client/`)`

`EvolutionClient` is a singleton instantiated at module level as `evolution_client`.

### Instance Management

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `create_instance(name)` | `POST /instance/create` | Creates WhatsApp instance with Baileys integration |
| `register_webhook(instance_id)` | `POST /webhook/create/{instanceId}` | Registers n8n webhook for inbound messages (upsert) |
| `delete_instance(name)` | `DELETE /instance/delete/{name}` | Removes instance; 404 is handled gracefully |

Instance names are prefixed with `tenant-` automatically (e.g., `tenant-acme`).

### Webhook Registration
`register_webhook` replaces the legacy `setup_n8n_integration`. It uses a defensive upsert pattern and chatbot payload now includes LID-aware sender identity fields for n8n:

- `remoteJid` (conversation target)
- `senderPn` (phone JID when resolvable)
- `senderLid` (`@lid` identifier when present)

Upsert flow:
1. Attempt `POST /webhook/create/{instanceId}` with:
   - `enabled=true`, `webhookUrl=https://rs-n8n.wilfredocamacho.dev/webhook/trackpalmastertenantclient`
   - `triggerType=keyword`, `triggerOperator=startsWith`, `triggerValue=/menu`
   - `isTrusted=true` (includes `apiKey` in payload)
2. If create fails (4xx), `GET /webhook/find/{instanceId}` to list existing webhooks
3. Find matching webhook by `webhookUrl`, fallback to first available
4. `PUT /webhook/update/{webhookId}` to reconcile contract

### Chat Session Control

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `close_chat_session(instance, remote_jid)` | `(no-op, deprecated)` | Session closing handled by n8n via `POST /webhook/change-status` |

`close_chat_session` is deprecated and logs a warning. Session closing is managed entirely from the n8n Bot workflow when the user sends a top-level `0` (logout/exit).

### Message Sending

Outbound messages use `POST /send/text` (Evolution Go endpoint), not the legacy `/message/sendText/{instance}`. Authentication uses the **instance token** (`apiKey` from the trusted webhook payload or stored encrypted token), not the global `EVOLUTION_API_KEY`.

- **Bot replies**: n8n sends with `apikey` from the webhook payload `body.apiKey` (Evolution Go provides this when `isTrusted=true`).
- **Subscription reminders**: Backend decrypts the stored `evolution_instance_token` and includes it in the pending reminders payload. n8n sends with `apikey={{$json.evolution_instance_token}}`.

### Instance Token Persistence

When a tenant is created, the Evolution instance token (`hash` from `create_instance` response) is encrypted with `DATA_ENCRYPTION_KEY` and stored in the `tenants.evolution_instance_token` column. Decryption happens only at runtime when needed:

- In `reminder_payloads.py`: decrypted per-reminder for n8n send auth.
- Never persisted in plain text or logged.

### Configuration

- `EVOLUTION_API_URL` — Base URL (e.g., `https://rs-evoapi.wilfredocamacho.dev`)
- `EVOLUTION_API_KEY` — Global API key for instance management endpoints (create, webhook CRUD, delete)
- `DATA_ENCRYPTION_KEY` — App-layer key for encrypting instance tokens at rest

When `EVOLUTION_API_KEY` or `EVOLUTION_API_URL` are empty, all management methods are no-ops with a warning log. This enables testing without Evolution Go.

### Tenant Lifecycle Integration

- **Create tenant**: `create_instance` + `register_webhook` + encrypt & store instance token are called inside `TenantService.create_tenant()`. If any Evolution Go call fails, the tenant creation is rolled back.
- **Delete tenant**: `delete_instance` is called inside `TenantService.delete_tenant()`. The tenant must be inactive before deletion.
- **Update tenant**: Changing `evolution_instance_name` only updates the database value; it does NOT recreate or rename the instance in Evolution Go.
