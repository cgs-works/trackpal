# Mailbox Ingestion (Gmail App-Password Only)

## Overview

Tenant mailbox ingestion lets each tenant configure a Gmail account for
extracting streaming-service access codes. Lookup jobs are durable in
PostgreSQL and are dispatched to a trusted external Lookup Executor. The
backend never runs Gmail IMAP or extraction work locally.

## Components

| Component | Responsibility |
|-----------|---------------|
| **Tenant Dashboard (frontend)** | Mailbox config, Gmail Setup Assistant, connection tests |
| **Backend API (FastAPI)** | Mailbox config CRUD, job creation, dispatch coordination, callback completion, and status polling |
| **Lookup Executor** | External runtime that fetches emails, extracts codes, and sends signed results back |
| **Mailbox Cleanup** | Periodic task that expires stale jobs and removes expired data |
| **PostgreSQL** | `tenant_mailboxes`, `mail_lookup_jobs`, `mail_code_delivery_log`, and executor registry |
| **Redis** | Durable-work queue coordination, dispatch locks, leases, capacity, cooldowns, and encrypted ephemeral results |

## Data Model

### `tenant_mailboxes`

- One mailbox per tenant (`tenant_id` unique).
- Stores credentials encrypted at rest via `app.core.encryption` (Fernet).
- Gmail is the only supported mailbox provider.
- Status: `disconnected` | `connected` | `error`.

### `mail_lookup_jobs`

- Created by n8n API endpoint `POST /api/v1/integrations/n8n/mail/lookups`.
- Status machine: `pending -> processing -> completed/failed`; dispatch and
  lease failures can recover `processing -> pending`; expired jobs become
  `timeout`.
- Extracted result values are not persisted in PostgreSQL.
- `executor_id`, `execution_attempts`, and `last_dispatch_error_safe` retain
  safe assignment metadata.
- Default TTL is five minutes via `settings.mailbox_lookup_job_ttl_minutes`.
- The executor keeps polling Gmail after an empty result instead of returning
  `not_found` immediately. Its default search budget is 55 seconds via
  `settings.mailbox_lookup_timeout_seconds`; n8n polls the job every 4 seconds
  for up to 60 seconds, leaving margin for callback and message delivery.

### `mail_code_delivery_log`

Dedupe tracking uses partial uniqueness for message IDs when available and a
fallback fingerprint otherwise. Entries are retained for
`settings.mailbox_delivery_log_retention_days`.

## External Execution

After a job is committed, `LookupExecutionCoordinator.schedule(job_id)` adds
it to the Redis queue and starts at most one short-lived pump. Each bounded
pump starts a follow-on pump when its queue still contains work, including work
remaining after a requeued dispatch; a pump does not immediately retry a sole
requeued job. The pump:

1. Acquires the per-job dispatch lock.
2. Selects an active, verified executor with capacity and no failure cooldown,
   using the smallest `active_leases / max_concurrency` ratio.
3. Creates a Redis execution lease and capacity marker.
4. Decrypts the mailbox app password only while constructing the encrypted
   execution envelope.
5. Sends the signed handoff and returns immediately; the executor performs the
   lookup and calls the backend asynchronously.

No permanent lookup worker loop runs inside FastAPI. If Redis, capacity, or an
executor is unavailable, the durable job remains `pending` and is requeued for
later scheduling. If other queued jobs remain, the coordinator starts a
follow-on pump; a sole requeued job waits for a later scheduling trigger. A
`429` requeues without changing executor health. Transport failures mark the
executor `degraded`, then `unreachable` after three consecutive failures and
open the configured five-minute cooldown. Security or protocol failures set
`requires_reverification=true` immediately. There is no local pipeline fallback.

Accepted `202` handoffs and same-lease `409` duplicates move a job to
`processing`, assign its executor, increment `execution_attempts`, and mark the
executor healthy. The lease remains until callback completion or expiry.

Executor callbacks use `POST /api/v1/integrations/executors/{executor_id}/jobs/{job_id}/complete` (with the compact `/executor-callback` compatibility route). The endpoint establishes internal RLS context before loading the executor, verifies the signed AES-GCM envelope, and consumes a one-use Redis nonce retained for three times the signature-skew window so future-dated signatures cannot outlive replay protection. It then delegates to a row-locked coordinator transaction. Found values are atomically deduplicated in PostgreSQL and cached only as Fernet-encrypted Redis results; duplicate-suppressed and `not_found` outcomes never create a result cache entry. Retryable outcomes clear the assignment, release the lease, and requeue only before the job deadline.

## Redis Coordination

The coordinator uses these keys:

- `mailbox:lookup:queue` and `mailbox:lookup:queue:seen` — queued job IDs and dedupe.
- `lookup:dispatch-lock:{job_id}` — short-lived per-job pump lock.
- `lookup:lease:{job_id}` — execution lease metadata.
- `lookup:executor-leases:{executor_id}` — expiring capacity markers.
- `lookup:callback-nonce:{executor_id}:{nonce}` — callback replay protection.
- `lookup:result:{job_id}` — Fernet-encrypted result cache.
- `lookup:executor-cooldown:{executor_id}` — failure cooldown marker.

PostgreSQL remains the durable source of truth. Duplicate scheduling is safe,
and polling or another job creation can re-schedule a pending durable row after
Redis recovery. A reconciliation pass treats PostgreSQL `pending` rows as the
recovery input, removes stale assignment metadata when an Execution Lease has
expired, and never invokes a local Gmail or extraction pipeline. Redis result
entries are encrypted and short-lived; the database stores only safe result
metadata, not extracted values.

## Gmail App-Password Connection

1. The Tenant Admin creates a Google app password.
2. The Gmail Setup Assistant collects the address and app password.
3. The backend validates the credential against Gmail IMAP over TLS.
4. The normalized credential is encrypted and stored as
   `app_password_encrypted`.

Gmail server details are fixed implementation details and are not user
configurable.

## API Contracts

### Tenant Dashboard (auth: Bearer JWT)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/tenant/mailbox/` | Get config |
| PUT | `/tenant/mailbox/` | Validate app password and connect |
| POST | `/tenant/mailbox/test` | Test connection |
| POST | `/tenant/mailbox/disconnect` | Disconnect and clear secrets |

### n8n Integration (auth: X-API-Key)

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/v1/integrations/n8n/mail/lookups` | Create a lookup job |
| GET | `/api/v1/integrations/n8n/mail/lookups/{job_id}?tenant_id=<uuid>` | Poll a tenant-scoped job |

### Master Lookup Executor Registry

Master users manage external executors through `/api/v1/lookup-executors/`.
Creation returns a generated protocol secret once. `/verify` establishes trust;
`/test` checks connectivity without establishing activation trust. Rotation
keeps the current secret active until a pending secret passes its challenge.

Changing `base_url` or `transport_mode` clears verification and requires a new
challenge. The Master capacity indicator reports current unexpired Redis leases,
not the number of PostgreSQL jobs still marked `processing`; the separate active
job count remains the deletion safety check. Deletion fails closed while
PostgreSQL jobs or Redis leases are active, or when lease coordination is
unavailable. Optional hosting passwords
are encrypted and require Master step-up authentication for reveal; they are
never sent to executors.

### Lookup Job States

`pending` → `processing` → `completed` | `failed`

`processing` → `pending` (recoverable lease or dispatch failure)

`pending` → `timeout` (when the job TTL expires)

Result types are `code`, `url`, `not_found`, and `duplicate_suppressed`.

## Observability

`GET /metrics` exposes lookup creation/poll outcomes, job latency, mailbox
connection tests, and cleanup status. Logs contain IDs and safe operational
errors only; credentials, tokens, raw email, and extracted values are not
logged.

## Retention and Cleanup

`mailbox_cleanup.cleanup_loop` runs periodically to expire pending or
processing jobs past their TTL, hard-delete expired jobs, and remove old
 dedupe records. Configure retention with
`settings.mailbox_lookup_job_ttl_minutes` and
`settings.mailbox_delivery_log_retention_days`.

## Security

- Credentials are encrypted at rest with Fernet.
- Sensitive executor bodies use application encryption and signed transport.
- Executor URL validation rejects unsafe destinations and redirects.
- Result values are ephemeral and encrypted in Redis.
- Tenant ownership is enforced at the repository/API boundary.

## Runbook

### Lookup jobs stuck in `pending`

1. Check Redis availability and failover logs.
2. Check active executor lifecycle, verification, health, capacity, and cooldown.
3. Confirm the job has not reached its five-minute TTL.
4. Do not start a local lookup worker; the external executor boundary is
   intentional. Pending jobs can be re-scheduled after Redis recovery.

### Cleanup not running

Check startup logs for `Mailbox cleanup loop starting` and verify periodic
`Mailbox cleanup complete` entries, then restart the application if needed.

## Related Documentation

- [System Overview](system-overview.md)
- [Database Schema](database-schema.md)
- [Input Validation Policy](input-validation-policy.md)
- [Code-Services Governance](code-services.md)
- [Backend Conventions](../code-standard/backend-conventions.md)
- [Error Handling](../code-standard/error-handling.md)
