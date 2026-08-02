# Worker Context

## Scope

The `worker/` project is the standalone **Lookup Executor** runtime. It is
independently deployable and must not import, install, or deploy `backend/`.
The backend remains responsible for job creation, tenant authorization,
durable PostgreSQL state, Redis coordination, and callback reconciliation.

## Domain vocabulary

| Term | Definition |
|---|---|
| **Lookup Executor** | A trusted external runtime registered by the Master that performs one Mail Lookup Job outside FastAPI. |
| **Execution Lease** | The exclusive, time-bounded assignment of a job to an executor. The worker does not create or persist leases; it receives the lease ID and returns it in the callback. |
| **Protocol secret** | The executor-specific shared secret used to derive separate signing and encryption keys. It is issued once by enrollment or rotation and configured as `TRACKPAL_EXECUTOR_SECRET`. |
| **Mail Lookup Job** | A bounded request containing mailbox access details, service and target-email filters, and callback identity. |
| **Callback** | The signed and encrypted result sent to TrackPal after the in-memory pipeline finishes. |

Avoid provider-specific names for the runtime. Render and Docker/VPS are
deployment choices, not domain types.

## Runtime contract

- `POST /v1/health/challenge` authenticates a challenge and returns protocol
  version, runtime version, executor identity, and advertised capacity.
- `POST /v1/jobs/execute` authenticates and decrypts a command, reserves a
  local slot, returns `202`, and schedules bounded background execution.
- Capacity is enforced locally; a full executor returns signed `429`.
- The worker sends callbacks with the job ID and Execution Lease ID. Duplicate
  handoffs for the same lease are acknowledged without starting a second task.
- HTTP redirects are disabled for callbacks. Errors are safe, stable messages;
  secrets, raw email, and extracted values are never logged.

The protocol uses HMAC-SHA256 signatures, AES-GCM payload encryption,
HKDF-derived independent signing/encryption keys, timestamp skew checks, and
single-use nonce replay protection. The callback URL is supplied by TrackPal
inside the authenticated command and is not a worker routing configuration.

## Secret boundary

Mailbox app passwords and protocol secrets exist only in process memory while
a command is handled. The worker has no PostgreSQL or Redis credentials and
must not persist a mailbox secret, extracted code, raw message, callback body,
or lease state. Container logs and exception details must remain secret-safe.

The optional hosting-account password belongs to the Master registry. It is
never sent to this project and must never be added to worker environment
variables, images, or logs.

## Deployment and tests

- Render Free is a request-driven Web Service with capacity `1` and an
  expected cold start of approximately one minute.
- Docker/VPS uses the same environment variables and protocol. Prefer HTTPS;
  public-IP HTTP requires the explicitly enabled `http_encrypted` transport,
  Master step-up, and `ALLOW HTTP` confirmation.
- Run `uv run pytest`, `uv run ruff check app tests`, and
  `uv run ruff format --check app tests` from this directory.

Read `README.md` for local operation and the repository deployment runbooks
for release procedures.
