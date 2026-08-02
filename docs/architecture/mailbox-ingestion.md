# Mailbox Ingestion (Gmail App-Password Only)

## Overview

Tenant mailbox ingestion lets each tenant configure a Gmail account for
extracting streaming-service access codes without deploying Python bots
per tenant.  Execution is coordinated by the TrackPal backend and runs in a trusted
external Lookup Executor when n8n requests a code lookup.

## Components

| Component | Responsibility |
|-----------|---------------|
| **Tenant Dashboard (frontend)** | Mailbox config, Gmail Setup Assistant, connection tests |
| **Backend API (FastAPI)** | Mailbox config CRUD, app-password validation, lookup job create/poll |
| **Lookup Executor** | External runtime — fetches emails, extracts codes, and sends signed results back to TrackPal |
| **Mailbox Cleanup** | Periodic background task — expires stale jobs, hard-deletes expired data |
| **PostgreSQL** | `tenant_mailboxes`, `mail_lookup_jobs`, `mail_code_delivery_log` |
| **Redis** | Queue (`mailbox:lookup:queue`) for job dispatch + ephemeral result cache |

## Data Model

### `tenant_mailboxes`

- One mailbox per tenant (`tenant_id` unique).
- Stores credentials **encrypted** at rest via `app.core.encryption` (Fernet).
- Gmail is the only supported mailbox provider; `provider` is a legacy column retained for backward compatibility.
- Status: `disconnected` | `connected` | `error`.
- Server details (host, port, SSL) are fixed Gmail IMAP values; they are not configurable by the user.

### `mail_lookup_jobs`

- Created by n8n API endpoint `POST /api/v1/integrations/n8n/mail/lookups`.
- Status machine: `pending -> processing -> completed/failed | pending -> timeout`; external lease failures may recover `processing -> pending`.
- Extracted result values are **not persisted** in DB.
- `executor_id`, `execution_attempts`, and `last_dispatch_error_safe` retain safe assignment metadata.
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
2. API resolves tenant, validates mailbox, creates and commits a `pending` job.
3. The external execution coordinator selects a dispatchable executor and hands off the job; durable pending rows remain recoverable if Redis or an executor is unavailable.

### Processing

1. Status `pending -> processing`.
2. Load mailbox config (scoped to tenant).
3. Fetch recent emails (window: `now-5min..now`, configurable via `settings.mailbox_lookup_window_minutes`). Gmail app-password lookups use the Gmail IMAP `X-GM-RAW after:<unix_timestamp>` extension so the window is based on an exact UTC instant rather than IMAP calendar-date semantics.
4. Run extractor against catalog of per-service regex patterns (`app/services/mail_code_extractor/catalog_v1.py`).
5. Pick newest valid candidate.
6. Compute fingerprint. Check dedupe log.
   - New → record delivery, store ephemeral result, complete `code`/`url`.
   - Duplicate → complete `duplicate_suppressed`.
   - No extraction → complete `not_found`.

### Retries

Transient errors (network, rate-limit) retry up to 3 times with
exponential backoff (1s, 2s, 4s).  Non-transient errors (revoked,
permissions) fail immediately.

## Gmail App-Password Connection

The primary connection method uses a Google-generated app password:

1. The Tenant Admin creates an app password at [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords).
2. The Gmail Setup Assistant collects the Gmail address and app password.
3. Backend validates the credential by testing an IMAP connection to `imap.gmail.com:993` with SSL before persisting.
4. The normalized credential is encrypted and stored as `app_password_encrypted`.
5. Gmail server details (`imap.gmail.com`, port 993, SSL=true) are fixed implementation details; the user never sees or configures them.

## API Contracts

### Tenant Dashboard (auth: Bearer JWT)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/tenant/mailbox/` | Get config |
| PUT | `/tenant/mailbox/` | Validate app password and connect |
| POST | `/tenant/mailbox/test` | Test connection |
| POST | `/tenant/mailbox/disconnect` | Disconnect + clear secrets |

### n8n Integration (auth: X-API-Key)

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/v1/integrations/n8n/mail/lookups` | Create lookup job (`target_email` required) → `{job_id, status=pending}` |
| GET | `/api/v1/integrations/n8n/mail/lookups/{job_id}?tenant_id=<uuid>` | Poll status scoped by tenant → `{status, result_type?, result_value?}` |

### Lookup Job States

`pending` → `processing` → `completed` | `failed`
`processing` → `pending` (recoverable lease or dispatch failure)
`pending` → `timeout` (when job TTL expires)

Result types: `code`, `url`, `not_found`, `duplicate_suppressed`.

Polling scope contract: n8n must send both `lookup_job_id` and `tenant_id`.

Durability contract for WhatsApp `codigo` handoff:
- `lookup_job_id` must be emitted only after `mail_lookup_jobs` row is committed.
- If enqueue fails after commit, backend compensates (delete job; fallback mark `failed` with `queue_unavailable`).
- On compensation/failure branch, `lookup_job_id` is omitted from console response.

## Observability

### Metrics (`GET /metrics`)

- `lookup_job_total{status,service}` — job results by outcome.
- `lookup_job_latency{quantile}` — p50/avg/count of job processing time.
- `lookup_api_create{status}` — job creation outcomes.
- `lookup_api_poll{status}` — poll status distribution.
- `mailbox_test_total{status}` — connection test outcomes.
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
- No `result_value` persisted in the database; result delivery remains ephemeral.
- Tenant isolation at repository layer: all queries scoped by `tenant_id`.
- Rate-limit sensitive endpoints at proxy/reverse-proxy level.

## Runbook

### Mailbox shows `error`

1. Tenant must reconnect via the Gmail Setup Assistant (app password).
2. If the app password was revoked (e.g. main Google password changed), generate a new app password and reconnect.

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
