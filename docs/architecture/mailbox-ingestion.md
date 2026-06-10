# Mailbox Ingestion (Multi-OAuth + IMAP Fallback)

## Overview

Tenant mailbox ingestion lets each tenant configure a tech mailbox for
extracting streaming-service access codes without deploying Python bots
per tenant.  Execution is centralised in the Trackpal backend and runs
on-demand when n8n requests a code lookup.

## Components

| Component | Responsibility |
|-----------|---------------|
| **Tenant Dashboard (frontend)** | Mailbox config, OAuth connect/disconnect, connection tests |
| **Backend API (FastAPI)** | Mailbox config CRUD, OAuth start/callback, lookup job create/poll |
| **Mailbox Lookup Worker** | Background asyncio task — processes pending jobs, polls the mailbox for up to 60s, extracts codes, dedupes |
| **Mailbox Cleanup** | Periodic background task — expires stale jobs, hard-deletes expired data |
| **PostgreSQL** | `tenant_mailboxes`, `mail_lookup_jobs`, `mail_code_delivery_log` |
| **Redis** | Queue (`mailbox:lookup:queue`) for job dispatch + ephemeral result cache |

## Data Model

### `tenant_mailboxes`

- One mailbox per tenant (v1; `tenant_id` unique).
- Stores OAuth tokens and IMAP passwords **encrypted** at rest via `app.core.encryption` (Fernet).
- Exclusivity: `auth_method` is either `oauth` or `imap_app_password` — the other's secrets are null.
- Status: `disconnected` | `connected` | `error` | `revoked`.

### `mail_lookup_jobs`

- Created by n8n API endpoint `POST /api/v1/integrations/n8n/mail/lookups`.
- Status machine: `pending -> processing -> completed/failed | pending -> timeout`.
- `result_value` is **not persisted** in DB (ephemeral in-memory cache, 60s TTL).
- Stores required `target_email` for content-bound filtering.
- TTL default 5 minutes via `settings.mailbox_lookup_job_ttl_minutes`.

### `mail_code_delivery_log`

- Dedupe tracking with partial uniqueness:
  - `message_id IS NOT NULL`: unique `(tenant_id, mailbox_id, service_key, message_id, fingerprint)`
  - `message_id IS NULL`: unique `(tenant_id, mailbox_id, service_key, fingerprint)`
- Fingerprint: SHA-256 of `service_key + message_id + payload` (primary) or fallback `service_key + sender + received_at + subject + payload`.
- Retention default 7 days via `settings.mailbox_delivery_log_retention_days`.

## Worker Design

### Trigger

1. n8n calls `POST /api/v1/integrations/n8n/mail/lookups` with `{service_key, target_email, tenant_instance}`.
2. API resolves tenant, validates mailbox, creates `pending` job, pushes job ID to Redis list.
3. Background `worker_loop` polls Redis via `BRPOP`, pops job ID, loads and processes job.

### Processing

1. Status `pending -> processing`.
2. Load mailbox config (scoped to tenant).
3. Fetch recent emails (window: `now-5min..now`, configurable via `settings.mailbox_lookup_window_minutes`).
4. If no valid code is found yet, repeat the mailbox fetch/extract cycle until a code arrives or `settings.mailbox_lookup_timeout_seconds` elapses (default 60s).
5. Run extractor against catalog of per-service regex patterns (`app/services/mail_code_extractor/catalog_v1.py`).
6. Pick newest valid candidate.
7. Compute fingerprint. Check dedupe log.
   - New → record delivery, store ephemeral result, complete `code`/`url`.
   - Duplicate → complete `duplicate_suppressed`.
   - Timeout with no extraction → complete `not_found`.

### Retries

Transient errors (network, rate-limit) retry up to 3 times with
exponential backoff (1s, 2s, 4s).  Non-transient errors (revoked,
permissions) fail immediately.

## OAuth Flows

### Google (Gmail Read-Only)

- Scopes: `gmail.readonly openid email profile`.
- `access_type=offline` + `prompt=consent` ensures refresh token on first auth.
- Token refresh on expiry; `invalid_grant` marks mailbox as `revoked`.

### Microsoft (Mail.Read)

- Scopes: `Mail.Read offline_access openid profile email`.
- Delegated permissions via Microsoft identity platform.
- Same refresh cycle + revocation handling.

## API Contracts

### Tenant Dashboard (auth: Bearer JWT)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/tenant/mailbox/` | Get config |
| PUT | `/tenant/mailbox/` | Create/update |
| POST | `/tenant/mailbox/test` | Test connection |
| POST | `/tenant/mailbox/oauth/{provider}/start` | Start OAuth |
| GET | `/tenant/mailbox/oauth/{provider}/callback` | OAuth callback |
| POST | `/tenant/mailbox/disconnect` | Disconnect + clear secrets |

### n8n Integration (auth: X-API-Key)

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/v1/integrations/n8n/mail/lookups` | Create lookup job (`target_email` required) → `{job_id, status=pending}` |
| GET | `/api/v1/integrations/n8n/mail/lookups/{job_id}?tenant_id=<uuid>` | Poll status scoped by tenant → `{status, result_type?, result_value?}` |

### Lookup Job States

`pending` → `processing` → `completed` | `failed`
`pending` → `timeout` (when job TTL expires)

Result types: `code`, `url`, `not_found`, `duplicate_suppressed`.

Polling scope contract: n8n must send both `lookup_job_id` and `tenant_id`.

Durability contract for WhatsApp `codigo` handoff:
- `lookup_job_id` must be emitted only after `mail_lookup_jobs` row is committed.
- If enqueue fails after commit, backend compensates (delete job; fallback mark `failed` with `queue_unavailable`).
- On compensation/failure branch, `lookup_job_id` is omitted from console response.

## Observability

### Metrics (`GET /metrics`)

- `lookup_job_total{status,provider,service}` — job results by outcome.
- `lookup_job_latency{quantile}` — p50/avg/count of job processing time.
- `lookup_api_create{status}` — job creation outcomes.
- `lookup_api_poll{status}` — poll status distribution.
- `oauth_*_total{provider,status}` — OAuth flow counts.
- `mailbox_test_total{method,status}` — connection test outcomes.
- `mailbox_cleanup_total{step,status}` — cleanup runs.

### Logging

- No secrets/tokens in logs (IDs only).
- Safe error codes returned to n8n via `error_code` / `error_detail_safe`.
- `last_connection_error` stored safely in DB (no tokens).

## Retention and Cleanup

A periodic background task (`mailbox_cleanup.cleanup_loop`) runs hourly:

1. **Expire stale jobs** → moves `pending`/`processing` jobs past TTL to `timeout`.
2. **Hard-delete expired jobs** → removes completed/failed/timeout jobs past TTL.
3. **Hard-delete delivery log** → removes entries older than retention window.

Configurable via:
- `settings.mailbox_lookup_job_ttl_minutes` (default 5m)
- `settings.mailbox_delivery_log_retention_days` (default 7d)

## Security

- All secrets encrypted at rest via `cryptography.fernet.Fernet`.
- No `result_value` persisted in database (ephemeral in-memory only).
- State token signed with HMAC-SHA256; expires after 10 minutes.
- Refresh token `invalid_grant` → mailbox `revoked`, tokens cleared.
- Tenant isolation at repository layer: all queries scoped by `tenant_id`.
- Rate-limit sensitive OAuth endpoints at proxy/reverse-proxy level.

## Runbook

### Mailbox shows `revoked`

1. Tenant must reconnect OAuth via dashboard.
2. If refresh token was permanently revoked (Google/Microsoft deauthorised),
   tenant must complete a fresh OAuth flow.

### Lookup jobs stuck in `pending`

1. Check Redis availability: `GET /health` shows status.
2. Check background worker running: logs show `Worker picked up job <id>`.
3. If Redis unavailable, jobs remain `pending` indefinitely until Redis resumes.
4. Manual intervention: run `expire_stale_jobs()` via admin hook to transition
   stale jobs to `timeout`.

### Cleanup not running

1. Check app startup logs for `Mailbox cleanup loop starting`.
2. Verify `cleanup_loop` task is running: look for `Mailbox cleanup complete`
   log entries.
3. If missing, restart the application.

## Related Documentation

- [System Overview](system-overview.md)
- [Database Schema](database-schema.md)
- [Input Validation Policy](input-validation-policy.md)
- [Code-Services Governance](code-services.md)
- [Backend Conventions](../code-standard/backend-conventions.md)
- [Error Handling](../code-standard/error-handling.md)
