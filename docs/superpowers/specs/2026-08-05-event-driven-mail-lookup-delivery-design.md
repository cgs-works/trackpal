# Event-Driven Mail Lookup Delivery Design

**Date:** 2026-08-05
**Status:** Approved

## Purpose

Replace repeated n8n status polling with event-driven execution resumption while fixing the lookup timing defects observed in executions 2103–2108. The design keeps Gmail retrieval and Netflix resolution outside the backend, delivers results as soon as they are found, and reduces normal backend traffic to approximately three inbound requests per lookup.

## Confirmed Problems

1. Candidate messages are selected relative to each worker fetch time. The five-minute rolling cutoff excluded a still-valid Netflix travel email that was seven minutes old when the job was created.
2. n8n polls the backend every four seconds for up to 60 seconds. Extending that loop to 130 seconds would increase worst-case backend traffic from approximately 17 to 35 requests per lookup.
3. A recovered job can complete as `not_found` while retaining `error_code=fetch_timeout` from an earlier attempt.
4. Retry flows can create overlapping work unless the prior session-linked job is explicitly superseded.

## Goals

- Use a global 15-minute candidate window anchored to job creation time.
- Deliver a found result immediately rather than waiting for the maximum timeout.
- Tolerate a simulated 60-second executor startup delay within a 130-second WhatsApp wait limit.
- Remove repeated status polling from the n8n workflow.
- Keep PostgreSQL as the durable job-state source and Redis as the encrypted ephemeral coordination store.
- Preserve multi-tenant and multi-job isolation.
- Keep active terminal errors consistent with terminal job outcomes.

## Non-Goals

- Moving Gmail retrieval, extraction, Netflix resolution, or a permanent worker loop into the backend.
- Persisting extracted codes, Netflix URLs, or n8n resume URLs in PostgreSQL.
- Redesigning WhatsApp transport outside the existing n8n workflow.
- Adding per-service configurable windows in this change.

## Architecture

### Normal flow

```text
WhatsApp → n8n → Backend creates job
                    ↓
n8n registers $execution.resumeUrl
                    ↓
n8n Wait: On Webhook Call, limit 130 seconds
                    ↓
Lookup Executor searches Gmail
                    ↓
Signed executor callback → Backend reconciles job
                    ↓
Backend POSTs terminal payload to the registered resume URL
                    ↓
n8n resumes and sends the WhatsApp result immediately
```

### Module seams

- **Lookup Executor module interface:** receives a fixed `search_after` timestamp and a remaining `timeout_seconds` budget. It knows nothing about n8n or WhatsApp.
- **Lookup coordination module interface:** owns durable transitions, leases, retry eligibility, encrypted ephemeral results, and one-time n8n resume notification.
- **n8n workflow interface:** registers its unique resume URL, suspends execution, and transports the terminal result to WhatsApp.

The backend does not retain an in-process waiter, sleep task, or permanent lookup loop.

## Temporal Policy

### Candidate cutoff

The backend computes one immutable cutoff per job:

```text
search_after = job.requested_at - 15 minutes
```

Every handoff and retry for that job uses the same cutoff. The worker Gmail query and extractor use this timestamp rather than recalculating `now - window_minutes` on every attempt. Messages arriving during the lookup remain eligible because they are newer than the fixed cutoff.

### End-to-end response deadline

- n8n Wait limit: 130 seconds from workflow lookup start.
- Backend interactive deadline: 120 seconds from `job.requested_at`.
- Reserved delivery margin: 10 seconds for callback reconciliation, n8n resume, and WhatsApp send.

For every dispatch attempt, the backend computes:

```text
timeout_seconds = floor(interactive_deadline - handoff_time)
```

The backend does not dispatch when no positive budget remains. Retryable callbacks requeue only while the interactive deadline has not expired. Once expired, the job transitions to `timeout` and n8n is notified.

The existing five-minute job TTL remains a retention and cleanup boundary, not permission to continue interactive work after the 120-second deadline.

## n8n Workflow

The current `Wait 4s → Poll status → Check retry` loop is replaced with:

1. Send the existing searching message.
2. Register `$execution.resumeUrl` against `job_id` and `tenant_id` through an X-API-Key-authenticated backend endpoint.
3. If registration reports a terminal job, skip waiting and build the result immediately.
4. Otherwise enter a Wait node configured as:
   - Resume: `On Webhook Call`
   - HTTP method: `POST`
   - Header authentication
   - Limit wait time: enabled
   - Limit: 130 seconds
5. If resumed by callback, build and send the terminal result immediately.
6. If resumed by the time limit, perform one final status GET. Deliver a terminal result if present; otherwise send the safe timeout message.

User-facing not-found copy refers to “recent emails” rather than hardcoding the configured minute count.

## Resume Registration and Notification

### Registration endpoint

The backend exposes a tenant-scoped n8n integration endpoint that accepts:

- `job_id`
- `tenant_id`
- `resume_url`

The endpoint:

- requires the existing n8n API key;
- verifies job ownership;
- validates that the URL is HTTPS and belongs to the configured n8n host;
- stores the URL encrypted in Redis under a job-scoped key with bounded TTL;
- is idempotent for the same job;
- returns the current terminal payload when the job has already completed.

### Notification

After a terminal callback is committed, the coordinator reads the registered URL and sends one terminal payload to n8n. The Wait webhook uses a dedicated shared Header Auth secret. Redirects are disabled.

The notifier makes bounded short retries to cover the small race between resume registration and the Wait node becoming active. The resume URL is removed only after a successful notification and otherwise expires through Redis TTL.

Notification failure never rolls back durable callback completion. The n8n final GET is the recovery path.

## Terminal Payload

The backend-to-n8n payload contains only the fields required to render and route the result:

- `job_id`
- `status`
- `result_type`
- `result_value` when applicable
- `error_code`
- `error_detail`
- `completed_at`

Codes, URLs, resume URLs, credentials, and raw email content must not be logged.

## State and Error Semantics

| Outcome | Durable state | Notification |
|---|---|---|
| Found | `completed` with `code` or `url` | Immediate |
| No candidate found | `completed/not_found` | Immediate |
| Duplicate | `completed/duplicate_suppressed` | Immediate |
| Retryable with remaining budget | `pending` | None yet |
| Retryable without remaining budget | `timeout` | Immediate |
| Terminal provider/protocol failure | `failed` | Immediate |

`error_code` and `error_detail_safe` describe only the current state. A successful terminal transition clears stale active errors. `last_dispatch_error_safe` retains the latest recoverable operational failure for diagnostics.

## Concurrency and Idempotency

Every lookup is isolated by `tenant_id`, `job_id`, execution lease, and unique n8n resume URL. Redis resume keys are job-scoped.

The WhatsApp session permits only one active lookup job:

1. Starting or retrying a lookup cancels the previous session-linked job when it is still `pending` or `processing`.
2. Its resume URL is removed.
3. A new job and n8n execution receive new identities.
4. A late callback for the superseded job cannot resume the new execution.

Concurrent jobs from different clients, tenants, or services remain independent. Existing atomic delivery deduplication continues to suppress duplicate delivery of the same mailbox result.

## Backend Load

Normal inbound backend requests per lookup:

1. Console call and job creation.
2. Resume URL registration.
3. Executor callback.

A fourth status request occurs only when the Wait node reaches its 130-second limit or notification delivery fails. The design removes the previous per-job polling rate of one request every four seconds.

## Security

- Resume URLs are capability secrets and are encrypted in Redis.
- PostgreSQL does not store resume URLs or extracted values.
- Registration is n8n API-key authenticated and tenant-scoped.
- Resume webhook calls use a dedicated Header Auth secret.
- Resume URL validation enforces the configured HTTPS n8n origin.
- Redirects are disabled for resume notification HTTP calls.
- Safe logs contain identifiers and stable operational errors only.

## Testing

### Worker

- A message aged 14 minutes 59 seconds is eligible.
- A message older than 15 minutes is rejected.
- Retries preserve the same fixed cutoff.
- A realistic Netflix travel body extracts and resolves correctly.
- Found results return immediately.
- The worker honors the remaining timeout budget.

### Backend

- Registration is authenticated, tenant-scoped, URL-validated, encrypted, and idempotent.
- A terminal job returned during registration skips n8n waiting.
- Callback completion resumes only the matching job.
- Retryable outcomes requeue only before the interactive deadline.
- Deadline exhaustion transitions to `timeout`.
- Terminal success and not-found clear stale active errors.
- Notification failure leaves durable completion intact.
- Same-session retry supersedes the previous active job.
- Concurrent tenant jobs do not share resume state.

### n8n

- Callback before 130 seconds resumes immediately.
- Time limit causes exactly one final status GET.
- A terminal result found by the final GET is still delivered.
- Missing callback and nonterminal final status produce the safe timeout message.
- The repeated polling loop is absent.

### Acceptance matrix

- The incident email, seven minutes old at job creation, is eligible.
- Warm executor completion is delivered as soon as found.
- A simulated 60-second executor startup delay completes within 130 seconds.
- Normal backend traffic is three inbound requests per lookup.
- Fallback backend traffic is no more than four inbound requests per lookup.

## Observability

Add safe metrics for:

- resume registrations;
- resume notification success and failure;
- job creation-to-callback latency;
- final-GET recovery;
- interactive deadline expiration;
- same-session job supersession.

## Deployment and Rollback

Deployment order preserves compatibility with the worker's strict command validation:

1. Deploy worker support for optional `search_after`, retaining the legacy window fallback.
2. Deploy backend deadline calculation, resume registration, notifier, state cleanup, and supersession behavior.
3. Deploy the n8n Wait-based workflow.
4. Verify warm and simulated cold-start scenarios and monitor initial executions.

Rollback restores the prior n8n polling workflow. Backend resume endpoints and worker fallback support can remain unused without affecting legacy operation.

## Documentation Updates During Implementation

Update behavior documentation and context maps in:

- `docs/architecture/mailbox-ingestion.md`
- `docs/architecture/n8n-workflow.md`
- `backend/CONTEXT.md`
- `worker/CONTEXT.md`
- `n8n/CONTEXT.md`

The documentation must describe event-driven n8n resumption, fixed candidate cutoff, end-to-end deadline, concurrency semantics, and fallback behavior.
