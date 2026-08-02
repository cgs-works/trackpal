# TrackPal Lookup Executor

The `worker/` project is the reference, provider-agnostic Lookup Executor. It
runs Gmail lookup and code extraction outside the FastAPI deployment and talks
to TrackPal only through the signed, encrypted HTTP protocol.

The executor does not need PostgreSQL, Redis, or the backend source tree. It
keeps mailbox credentials, email content, and extracted values in memory only;
it does not provide durable job storage.

## Configuration

| Variable | Required | Purpose |
|---|---:|---|
| `TRACKPAL_EXECUTOR_ID` | yes | UUID issued by the Master enrollment flow |
| `TRACKPAL_EXECUTOR_SECRET` | yes | One-time protocol secret issued by enrollment or rotation |
| `TRACKPAL_MAX_CONCURRENCY` | no | Local execution limit; Render Free uses `1` |

Start locally with Python 3.12 and uv:

```bash
cp .env.example .env
uv sync
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

The service listens on port `8000`. It exposes the protocol challenge and job
handoff routes; it does not expose a public unauthenticated health endpoint.
Use the Master **Test** action to perform a signed challenge.

## Enrollment and activation

1. Deploy this project using [Render](../docs/how-to/deploy-lookup-executor-render.md)
   or [Docker/VPS](../docs/how-to/deploy-lookup-executor-vps.md).
2. In TrackPal, open **Lookup Executors**, create a draft, and copy the
   executor ID and secret immediately. The secret is not returned again.
3. Set the two values in the deployment environment and restart the service.
4. Set the public base URL in the draft and run **Test** or **Verify**.
5. Activate only after the challenge reports the expected protocol and
   advertised capacity.

The same executor can be disabled, tested, rotated, and deleted from the
Master registry. Rotation creates a pending key; deploy the new value, verify
it, and only then promote it. Keep the old value until promotion succeeds. If
rolling back the code after promotion, keep the current active secret; restore
the old secret only after explicitly confirming that TrackPal still accepts
it.

## Protocol and operational boundaries

- Requests and callbacks use protocol version 1, HMAC signatures, AES-GCM
  envelopes, timestamps, and one-use nonces.
- The executor accepts a handoff with `202`, performs the bounded pipeline in a
  background task, and sends the encrypted result to the callback URL.
- A local restart can lose an in-flight task. TrackPal's Execution Lease makes
  that job eligible for recovery; do not add a local database or queue.
- Do not log environment variables, protocol bodies, mailbox credentials,
  email content, codes, or callback payloads.
- HTTPS is the normal deployment mode. Public-IP `http_encrypted` is an
  explicitly controlled exception configured by the Master with step-up
  confirmation; application encryption and signing remain mandatory.

## Verification

```bash
uv run pytest
uv run ruff check app tests
uv run ruff format --check app tests
```

See the repository [mailbox ingestion architecture](../docs/architecture/mailbox-ingestion.md)
for the lease, callback, Redis, and PostgreSQL recovery contract.
