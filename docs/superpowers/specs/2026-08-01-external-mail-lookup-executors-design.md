# External Mail Lookup Executors — Design

**Date:** 2026-08-01
**Status:** Approved
**Scope:** Backend coordination, Master UI, independently deployable Python executor, Redis, documentation, and removal of the local lookup pipeline

## Summary

TrackPal will execute Mail Lookup Jobs outside the FastAPI web backend through trusted, provider-agnostic **Lookup Executors**. The first reference executor will be a standalone Python application under the repository root `worker/`, deployable independently to a Render Free Web Service or a Docker VPS. Future runtimes can participate by implementing the same signed HTTP protocol.

FastAPI will continue to create and expose Mail Lookup Jobs, but it will no longer open Gmail IMAP connections, parse email messages, run code extractors, resolve Netflix verification URLs, or retain lookup results in process memory. PostgreSQL remains the durable source of job and executor state. Redis remains the ephemeral coordination layer for dispatch locks, Execution Leases, capacity, replay protection, queue acceleration, and encrypted short-lived results.

The Master can enroll, verify, activate, disable, monitor, rotate, and delete executors from the Web panel. Executor configuration is stored dynamically in PostgreSQL, so adding an executor never adds an environment variable to the existing backend deployment.

## Goals

1. Remove mailbox lookup I/O and extraction work from the Render-hosted FastAPI process.
2. Allow the Master to add multiple trusted executor instances without redeploying the backend.
3. Keep the runtime independent of Render, VPS, Cloudflare, or any other hosting provider.
4. Preserve Redis-based asynchronous job coordination and PostgreSQL durability.
5. Prevent automatic fallback to local backend execution.
6. Make `worker/` independently deployable without importing or deploying `backend/`.
7. Preserve the current Mail Lookup Job behavior, code-service extraction rules, dedupe guarantees, and no-persisted-code policy.
8. Remove all backend code made obsolete by the external executor architecture.
9. Provide deployment tutorials for Render Free and Docker/VPS.

## Non-goals

- Deploying Render, VPS, or Cloudflare resources from the TrackPal panel.
- Giving executors direct PostgreSQL or Redis access.
- Advanced executor analytics, charts, or historical run inspection in v1.
- Periodic health polling that keeps free hosting instances awake.
- Automatic execution by the backend when the external pool is unavailable.
- Supporting untrusted third-party executors.
- Guaranteeing Cloudflare Workers Free compatibility for the full Python pipeline.

## Domain Language

### Lookup Executor

A trusted external runtime registered by the Master that executes Mail Lookup Jobs outside the backend web process. It is independent of the hosting provider. Avoid provider-specific canonical names such as “Render Worker” or “Cloudflare Worker.”

### Execution Lease

The exclusive, time-bounded assignment of a Mail Lookup Job to a Lookup Executor. If the lease expires without an accepted result, the job becomes eligible for another executor while its overall job TTL remains valid.

### Executor Hosting Account

An optional Master-only reference to the external account used to host a Lookup Executor. It is separate from both the executor protocol secret and Tenant Mailbox credentials.

## Considered Approaches

### 1. TrackPal-coordinated HTTP push — selected

TrackPal selects an executor, creates an Execution Lease, sends a signed encrypted job envelope, and receives a signed callback.

**Advantages**

- Executors need no Redis or database credentials.
- Real n8n traffic wakes Render Free services naturally.
- FastAPI performs only bounded asynchronous HTTP coordination.
- The hosting provider is hidden behind one stable protocol.
- Redis HA and replay logic remain local to the backend.

**Trade-offs**

- FastAPI owns a lightweight dispatch pump.
- The distributed protocol, leases, callbacks, and retries require careful idempotency.

### 2. Executors consume Redis directly — rejected

This would distribute Redis HA credentials and failover behavior to every runtime, couple executors to TrackPal infrastructure, and allow a defective executor to affect unrelated Redis state. It places the seam below the behavior that should remain local to TrackPal.

### 3. Executors poll TrackPal — rejected

Polling is incompatible with sleeping Render Free Web Services unless an external cron or keep-alive wakes them. It adds latency, consumes free hours without useful work, and introduces another operational dependency.

### 4. Full pipeline on Cloudflare Workers Free — rejected as the reference runtime

Cloudflare Workers Free currently limits each HTTP invocation to 10 ms of CPU. Multiple accounts increase daily request quota but do not increase per-invocation CPU. IMAP protocol handling, MIME parsing, extraction, and Netflix HTML parsing cannot be guaranteed within that budget. The protocol remains generic enough for a future Cloudflare Paid or restricted adapter.

## High-level Architecture

```text
[n8n]
  |
  v
[FastAPI lookup API]
  |
  +--> [PostgreSQL: Mail Lookup Job + Lookup Executor registry]
  |
  +--> [Redis: queue, locks, leases, capacity, nonces, encrypted result]
  |
  v
[LookupExecutionCoordinator]
  |
  +---- signed + encrypted HTTP ----> [worker/ Lookup Executor]
                                         |
                                         +--> Gmail IMAP
                                         +--> MIME parsing
                                         +--> Code extractors
                                         +--> Netflix resolution
                                         +--> Fingerprint
                                         |
  <------------ signed callback --------+
```

## Repository Shape

```text
trackpal/
├── backend/                 # Job lifecycle, executor registry, Redis coordination
├── frontend/                # Master executor management
├── worker/                  # Independently deployable Lookup Executor
│   ├── app/
│   │   ├── api/             # Health challenge and execute endpoints
│   │   ├── pipeline/        # Pipeline orchestration
│   │   ├── providers/       # Gmail IMAP adapter
│   │   ├── extractors/      # Code Service catalog and extraction
│   │   ├── netflix/         # Verification URL resolution and diagnostics
│   │   └── protocol/        # Envelopes, signatures, encryption, callbacks
│   ├── tests/
│   ├── pyproject.toml
│   ├── Dockerfile
│   ├── render.yaml
│   └── README.md
└── docs/
```

`worker/` must not import modules from `backend/`. Render can use `worker/` as its Root Directory, and a Docker build can use `worker/` as its build context.

## Deep Modules and Interfaces

### `LookupExecutionCoordinator`

The external interface used by lookup endpoints remains deliberately small:

```python
await coordinator.schedule(job_id)
```

The operation is idempotent and may be called after job creation or during a poll of a pending job. The implementation hides:

- Redis enqueue and reconciliation;
- executor eligibility and least-loaded selection;
- dispatch locks;
- capacity reservations;
- Execution Lease creation and expiration;
- Mailbox credential loading and temporary decryption;
- envelope encryption and signing;
- HTTP handoff;
- callback validation;
- dedupe persistence;
- result caching;
- job transitions and retry decisions.

Deleting this module would spread distributed coordination across the n8n endpoint, console handlers, polling endpoint, Redis helpers, and callback endpoint. Its depth therefore provides leverage and locality.

A short-lived dispatch pump may run in the web process only while useful work exists. It performs no Mailbox or extraction work. Job creation and polling return without waiting for executor cold start or pipeline completion.

### Executor transport seam

The coordinator depends on an internal port:

```python
class LookupExecutorTransport(Protocol):
    async def challenge(self, executor, challenge) -> ChallengeResult: ...
    async def handoff(self, executor, envelope) -> HandoffResult: ...
```

- Production uses an HTTP adapter.
- Backend tests use an in-memory adapter.

This is a real seam because the owned remote dependency and test adapter both exist.

### `LookupExecutorRegistry`

The Master-facing module owns enrollment and lifecycle rules:

```python
create_draft(...)
set_connection(executor_id, ...)
verify(executor_id)
enable(executor_id)
disable(executor_id)
rotate_secret(executor_id)
delete(executor_id)
```

It hides secret generation, encryption, safe serialization, challenge verification, lifecycle transitions, hosting-credential controls, and active-lease deletion guards.

### `worker/` pipeline

The executor exposes a small HTTP interface and hides the complete lookup implementation. Its pipeline accepts a decrypted execution command and returns one normalized outcome. Internally it owns provider retries, MIME normalization, target-email filtering, extraction, Netflix resolution, and fingerprint generation.

## Executor Registry Data Model

Create `lookup_executors` with:

| Field | Meaning |
|---|---|
| `id` | Stable executor UUID |
| `name` | Master-defined display name |
| `provider_label` | Informational `render`, `vps`, or `custom` label |
| `base_url` | Public executor URL |
| `transport_mode` | `https` or `http_encrypted` |
| `lifecycle_status` | `draft`, `active`, or `disabled` |
| `health_status` | `unknown`, `healthy`, `degraded`, or `unreachable` |
| `max_concurrency` | TrackPal-side capacity limit |
| `secret_encrypted` | Current executor protocol secret |
| `secret_version` | Current signing/encryption key version |
| `pending_secret_encrypted` | Secret awaiting verification during rotation |
| `pending_secret_version` | Candidate version during rotation |
| `hosting_account_email` | Optional external account email |
| `hosting_account_password_encrypted` | Optional external account password |
| `dashboard_url` | Optional provider dashboard URL |
| `last_health_check_at` | Last explicit or operational health evidence |
| `last_success_at` | Last successful handoff or callback |
| `last_error_safe` | Latest non-secret operational error |
| timestamps | Creation and update timestamps |

The provider label is descriptive only. Dispatch behavior cannot branch on it.

The executor protocol secret and hosting account password are distinct credentials:

- The protocol secret is needed by TrackPal for HMAC and application-level encryption. It is shown once during enrollment or rotation and is never revealed later.
- The hosting account password exists only as an optional Master reference. It is never sent to an executor or returned in ordinary executor responses.

Deleting an executor is allowed only when it has no active Execution Leases. Historical Mail Lookup Jobs retain no required dependency on the deleted row; `executor_id` uses nullable `SET NULL` semantics.

## Mail Lookup Job Changes

Add to `mail_lookup_jobs`:

| Field | Meaning |
|---|---|
| `executor_id` | Executor currently or most recently assigned |
| `execution_attempts` | Number of accepted external attempts |
| `last_dispatch_error_safe` | Latest safe coordination failure |

Do not persist the extracted code or URL. The existing unused `result_value_encrypted` column should be evaluated during implementation: remove it if no supported behavior still depends on it, rather than preserving a misleading field.

## Job State Machine

```text
pending
  ├─ no executor/capacity                    -> pending
  ├─ handoff rejected or connection failed  -> pending
  └─ handoff accepted                       -> processing
       ├─ successful outcome                -> completed
       ├─ terminal provider failure         -> failed
       ├─ retryable execution failure       -> pending, if TTL remains
       └─ Execution Lease expires           -> pending, if TTL remains

pending or processing past job TTL          -> timeout
```

A callback may complete a job only when:

- its executor matches the lease;
- its `lease_id` matches the current lease;
- the lease has not been superseded;
- the job is not already terminal.

Duplicate, late, or superseded callbacks return a successful acknowledgement with `accepted=false` so executors do not retry them, but they do not mutate state.

A callback can race with the backend transition after a `202` handoff. If the lease is valid and the job is still pending, the callback handler may perform the processing transition and terminal transition in one transaction.

## Redis Responsibilities

Redis stores only ephemeral coordination data:

- `mailbox:lookup:queue` — job IDs available for scheduling;
- dispatch lock per job;
- Execution Lease per job;
- expiring active-lease set per executor;
- consumed request and callback nonces;
- encrypted result value with a short TTL;
- per-executor failure cooldown/circuit state where appropriate.

PostgreSQL remains the durable source of truth. The current Redis active-passive manager does not guarantee queue replication. Therefore:

- `schedule(job_id)` always tolerates duplicate enqueue;
- job creation and n8n polling can re-schedule a durable pending job;
- opportunistic reconciliation queries durable pending jobs when a dispatch pump starts;
- Redis loss can delay dispatch but cannot erase a Mail Lookup Job.

The encrypted result cache replaces the current process-local dictionary. Polling can retrieve a result regardless of which FastAPI process receives the request.

## Executor Selection and Capacity

Eligible executors are:

- lifecycle `active`;
- not in security quarantine;
- not inside a failure cooldown;
- below `max_concurrency` according to unexpired Redis leases.

Selection uses the smallest ratio:

```text
active_leases / max_concurrency
```

Ties use stable round-robin or oldest-last-selected ordering to avoid repeatedly favoring the first row.

Render Free defaults to capacity `1`. A VPS can advertise or configure a larger runtime capacity. Verification must ensure the panel value does not exceed the capacity advertised by the executor. The executor also enforces its own local limit and returns `429` when full; this response requeues the job without degrading health.

## Enrollment Flow

1. Master chooses **Add Lookup Executor**.
2. TrackPal creates a `draft` row and generates:
   - `executor_id`;
   - a cryptographically random protocol secret.
3. The UI shows the ID and secret once with copy actions.
4. The executor deployment receives at minimum:
   - `TRACKPAL_EXECUTOR_ID`;
   - `TRACKPAL_EXECUTOR_SECRET`.
5. Optional executor-side configuration may include maximum concurrency and diagnostic R2 settings. These are executor settings, not backend settings.
6. Master enters base URL, transport mode, and TrackPal capacity.
7. TrackPal sends a signed challenge.
8. The executor returns its identity, protocol version, runtime version, and advertised capabilities.
9. A valid challenge marks health `healthy`; the Master can activate the executor.

Secret rotation generates a pending secret. The old secret remains active until the new one passes a challenge, then the new version is promoted atomically. This prevents rotation downtime.

## Protocol v1

### Executor endpoints

```text
POST /v1/health/challenge
POST /v1/jobs/execute
```

### TrackPal callback

```text
POST /api/v1/integrations/executors/{executor_id}/jobs/{job_id}/complete
```

### Signing

Derive independent signing and encryption keys from the executor secret with HKDF-SHA256. Never reuse one raw key for both purposes.

Each message includes:

- protocol version;
- key version;
- executor ID;
- timestamp;
- random nonce;
- body digest;
- HMAC-SHA256 signature.

The signature covers HTTP method, canonical path, timestamp, nonce, key version, and ciphertext digest. TrackPal stores consumed callback nonces in Redis. Executors maintain an in-memory TTL cache for inbound nonces. Timestamp tolerance is short and bounded.

### Payload encryption

Sensitive job and callback bodies use authenticated AES-GCM encryption. The encrypted execution payload contains:

- job ID and lease ID;
- lease expiry;
- callback URL;
- Mailbox email;
- decrypted App Password;
- Code Service key;
- target email;
- lookup window and safe retry settings.

The result callback contains:

- job and lease identity;
- terminal or retryable classification;
- result type and value when found;
- fingerprint and minimum dedupe metadata;
- safe error code/detail;
- bounded timing metadata.

Raw email messages, complete message bodies, protocol secrets, and hosting credentials are never included in callbacks.

### Handoff behavior

The executor validates the envelope before accepting it. On acceptance it returns `202` and runs the pipeline in a bounded background task. A crash or restart can lose the local task; the Execution Lease makes this recoverable without local persistence.

The executor returns:

- `202` — accepted;
- `409` — duplicate active execution already known locally;
- `429` — local capacity reached;
- `401/403` — invalid identity, signature, or key version;
- `422` — unsupported protocol or malformed encrypted command.

The coordinator never waits for pipeline completion in the original n8n request.

## Transport Modes

### `https`

Default and recommended. Accept a valid public certificate for either a hostname or IP address. Redirects are disabled.

The VPS guide documents:

- domain + Caddy;
- `sslip.io` hostname + Caddy without purchasing a domain;
- direct IP certificates as an advanced alternative.

### `http_encrypted`

Allowed only by explicit Master choice for a public IP endpoint. It requires:

- application-level AES-GCM for every sensitive body;
- HMAC authentication;
- nonce and timestamp replay controls;
- no redirects;
- Master password step-up;
- an explicit high-risk confirmation;
- a permanent degraded-transport badge in the UI.

HTTP can expose destination, timing, frequency, and message size and remains vulnerable to traffic blocking. It must never send a plaintext Mailbox credential or result.

### SSRF controls

For both modes:

- resolve and validate the destination before use;
- reject loopback, private, link-local, multicast, reserved, and cloud metadata addresses;
- reject URL credentials and fragments;
- allow only expected HTTP/HTTPS schemes and bounded ports;
- disable redirects;
- revalidate DNS results to reduce rebinding risk;
- set bounded connect and response timeouts.

A direct `http://IP` executor must still use a public address reachable from the backend.

## Worker Pipeline

Move the full execution implementation from `backend/` into `worker/`:

1. Decrypt the execution command in memory.
2. Connect to Gmail IMAP using TLS and the App Password.
3. Search the exact recent UTC window.
4. Fetch a bounded set of newest messages.
5. Parse MIME and normalize subject, body, date, message ID, sender, and recipients.
6. Filter by target email.
7. Run the Code Service extractor catalog.
8. Resolve Netflix verification URLs to a code when required.
9. Compute the delivery fingerprint and minimum dedupe metadata.
10. Clear secret-bearing values from references as soon as practical.
11. Send the signed encrypted callback.

Provider retry taxonomy remains:

- transient network, timeout, or rate limit — bounded exponential retry;
- authentication or configuration failure — terminal;
- unexpected internal failure — safe generic error.

The executor never stores Mailbox credentials or extracted codes durably.

## Callback Completion and Dedupe

TrackPal remains authoritative for cross-job dedupe because the delivery log lives in PostgreSQL.

On a valid callback:

1. Load and lock the job.
2. Validate executor and current lease.
3. For a found value, atomically insert the fingerprint into the delivery log.
4. If duplicate, complete with `duplicate_suppressed`.
5. Otherwise encrypt and store the result in Redis with a short TTL, then complete with `code` or `url`.
6. For `not_found`, complete without a result value.
7. For retryable infrastructure/provider outcomes, return the job to pending while TTL remains.
8. For terminal outcomes, mark failed with safe error fields.
9. Release capacity and delete the lease.

Database mutation and dedupe remain transactionally local to TrackPal.

## Health and Failure Policy

TrackPal does not periodically ping executors. Health evidence comes from:

- enrollment or manual verification;
- real handoff responses;
- valid callbacks;
- connection failures;
- lease expiration.

This avoids keeping Render Free instances awake.

Behavior by failure:

| Failure | Behavior |
|---|---|
| No active executor or no capacity | Keep pending until capacity or job TTL |
| Render cold start / connect timeout | Release reservation, record safe error, requeue |
| `429` busy | Requeue without health penalty |
| Executor dies after `202` | Lease expires; requeue if TTL remains |
| Retryable Gmail failure | Executor retries locally, then callback requests requeue |
| Revoked App Password | Terminal job failure; do not try another executor |
| Signature/protocol failure | Security quarantine; require verification |
| Duplicate/late callback | Acknowledge with `accepted=false`; no mutation |
| Redis unavailable | Durable job remains; reconciliation retries later |
| All external execution unavailable | Never run locally; job eventually times out |

Consecutive transport failures open an executor cooldown. A later successful challenge, handoff, or callback resets failure state.

## Master UI

Add `/master/executors` and a **Lookup Executors** sidebar destination.

### List/card content

- name and provider label;
- base URL;
- HTTPS or HTTP-encrypted badge;
- lifecycle and health;
- active jobs / maximum capacity;
- last success and safe error;
- actions for verify, test, edit, activate, disable, rotate, reveal hosting account, and delete.

### Wizard

1. **Identity** — name, provider, TrackPal capacity, optional hosting account email/password, optional dashboard URL.
2. **Credentials** — one-time executor ID and secret with copy actions.
3. **Connection** — URL, transport mode, challenge.
4. **Activation** — verified summary and confirmation.

### Hosting account password

The user explicitly accepts the risk of allowing TrackPal to retain this external administrative password. Controls are mandatory:

- optional field;
- encrypted with `DATA_ENCRYPTION_KEY`;
- absent from list/detail serializers by default;
- excluded from exports;
- never logged;
- never sent to executors;
- reveal only after Master password step-up;
- existing Redis-backed step-up limiter fails closed;
- reveal is temporary and cleared when the dialog closes;
- reveal action emits safe audit context without the secret;
- updates replace the encrypted value without returning the previous plaintext.

### Lifecycle actions

- **Disable:** stop new assignments; allow valid active leases to finish.
- **Delete:** only when no active leases remain.
- **Rotate:** verify a pending secret before promoting it.
- **Test:** manual challenge that may wake a sleeping Render service.

## Render Free Deployment

The reference Render deployment is a Free Web Service, not a Render Background Worker because background workers do not have a free instance type.

Expected behavior and documentation:

- Root Directory: `worker/`;
- Python build/install from `worker/pyproject.toml`;
- start the executor HTTP application;
- configure executor ID and secret;
- Free instances spin down after inactivity and can take approximately one minute to wake;
- default TrackPal capacity is one;
- TrackPal allows a bounded cold-start handoff timeout;
- Render free instance hours are workspace-scoped and should be monitored;
- local filesystem cannot be treated as durable state.

The executor's `202` plus callback model prevents the n8n create request from waiting for the full pipeline. Lease expiry handles restarts or lost background work.

## Docker/VPS Deployment

Provide:

- `worker/Dockerfile`;
- environment example;
- Docker run/Compose instructions;
- firewall guidance;
- Caddy examples for domain and `sslip.io`;
- advanced direct-IP certificate guidance;
- explicit HTTP-encrypted setup and warning;
- health verification and secret rotation procedure;
- upgrade and rollback procedure.

A VPS deployment still uses the same executor ID, secret, endpoints, and callback protocol as Render.

## Removal of Obsolete Backend Code

After the external path is connected and tested, remove code made obsolete by this change:

- local `mail_lookup_worker.worker_loop`;
- lookup-worker startup task from FastAPI lifespan;
- backend Gmail IMAP provider implementation;
- backend extraction pipeline and Netflix resolution when no other backend caller remains;
- process-local ephemeral result cache;
- local queue-dequeue helpers no longer used by the coordinator;
- settings and imports used only by the old local executor;
- tests that assert local execution implementation details;
- documentation claiming FastAPI processes Mail Lookup Jobs.

Use reference searches and the deletion test before removing each module. Move behavior tests to `worker/tests/`; do not keep duplicate copies solely for comfort. Preserve only code with a verified remaining caller.

The final backend must not import the worker pipeline.

## Testing Strategy

### Worker tests

- protocol challenge and key-version handling;
- HMAC verification and canonicalization;
- AES-GCM encryption/decryption and tamper rejection;
- timestamp and nonce replay protection;
- local concurrency and `429` behavior;
- Gmail IMAP behavior through fakes;
- MIME normalization and target-email filtering;
- all Code Service extractors;
- Netflix URL resolution;
- fingerprint output;
- transient and terminal retry taxonomy;
- callback serialization;
- secret-safe logs and errors.

### Backend tests

- executor draft creation and one-time secret response;
- encrypted secret and hosting password persistence;
- lifecycle transitions and rotation promotion;
- step-up reveal and fail-closed limiter behavior;
- HTTPS and HTTP-encrypted URL validation;
- SSRF, redirects, and DNS rebinding defenses;
- least-loaded selection and capacity bounds;
- dispatch lock and duplicate scheduling;
- handoff outcome handling;
- lease expiry, requeue, and timeout;
- callback signature, decryption, and idempotency;
- atomic dedupe and encrypted Redis result;
- PostgreSQL reconciliation after Redis loss/failover;
- disabled/deleted executor behavior;
- proof that no local pipeline fallback runs.

### Frontend tests

- enrollment wizard steps;
- one-time secret presentation;
- transport warnings and step-up for HTTP;
- lifecycle and health badges;
- active/capacity display;
- disable/delete guards;
- rotation flow;
- hosting password absent from ordinary responses;
- step-up reveal dialog and clearing behavior;
- responsive table/card behavior.

### Contract test

A repository-level contract test launches the `worker` ASGI application and exercises it through the backend HTTP transport adapter. It verifies protocol v1 challenge, handoff, callback, error mapping, and key rotation without sharing runtime implementation modules.

### Verification commands

- Backend: `cd backend && uv run pytest`
- Worker: `cd worker && uv run pytest`
- Frontend: `cd frontend && npm test`
- Frontend build: `cd frontend && npm run build`
- Python style for affected projects: Ruff check and format verification

## Documentation Impact

Implementation must update:

- `docs/SUMMARY.md`;
- `docs/architecture/system-overview.md`;
- `docs/architecture/mailbox-ingestion.md`;
- `docs/architecture/api-layer.md`;
- `docs/architecture/database-schema.md`;
- `docs/architecture/redis-ha.md`;
- `docs/architecture/frontend-architecture.md`;
- backend and frontend structure references;
- backend and frontend `CONTEXT.md` files;
- deployment and security runbooks;
- `worker/README.md`;
- Render Free tutorial;
- Docker/VPS tutorial.

## Architectural Decisions

Two ADRs accompany this design:

1. TrackPal coordinates provider-agnostic external Lookup Executors through signed encrypted HTTP and Redis-backed Execution Leases.
2. TrackPal accepts the explicit risk of storing optional external hosting account passwords under Master-only encrypted step-up controls.

## Acceptance Criteria

1. The Master can enroll, verify, activate, disable, rotate, and delete multiple Lookup Executors without modifying backend environment variables.
2. The reference executor deploys from `worker/` without importing or deploying `backend/`.
3. FastAPI performs no Gmail IMAP, MIME parsing, Code Service extraction, Netflix resolution, or local result caching.
4. Redis coordinates queue acceleration, leases, capacity, nonces, and encrypted ephemeral results; PostgreSQL can recover pending jobs after Redis state loss.
5. No job automatically falls back to backend execution.
6. Render Free and Docker/VPS deployments implement the same protocol.
7. HTTPS is recommended, while explicitly enabled public-IP HTTP uses mandatory application encryption, signing, replay protection, warning, and step-up.
8. Executor and Mailbox secrets, extracted codes, and hosting passwords never appear in logs or ordinary API responses.
9. Hosting password reveal is Master-only, rate-limited, step-up protected, and temporary.
10. Late or duplicate callbacks cannot corrupt a terminal or reassigned job.
11. Executor capacity is enforced by both TrackPal leases and the executor runtime.
12. Code made obsolete by the migration is removed after verified reference searches.
13. Backend, worker, frontend, contract, and build verification pass.
