# External Mail Lookup Executors Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the complete Mail Lookup Job pipeline into independently deployable trusted Lookup Executors while TrackPal retains durable job state, Redis coordination, Master enrollment, dedupe, and result delivery.

**Architecture:** A standalone Python application under `worker/` implements the signed, application-encrypted executor protocol and owns Gmail IMAP, MIME parsing, extraction, Netflix resolution, and fingerprinting. The backend adds a deep `LookupExecutionCoordinator` module with a three-entry interface—`schedule`, `complete`, and `get_result`—plus a Master-only registry; PostgreSQL remains durable and Redis stores recoverable Execution Leases, capacity, replay nonces, queue acceleration, and encrypted results. The frontend adds a provider-agnostic Master page and enrollment/security flows.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, cryptography (HKDF/HMAC/AES-GCM/Fernet), httpx, SQLAlchemy 2 async, PostgreSQL RLS, Redis HA, Alembic, React 19, TypeScript strict, TanStack Router, Tailwind CSS v4, shadcn/ui, Vitest, pytest.

## Global Constraints

- `worker/` must deploy without importing or deploying `backend/`.
- Lookup Executors never receive PostgreSQL or Redis credentials.
- The backend never performs Gmail IMAP, MIME parsing, Code Service extraction, Netflix resolution, or automatic local fallback after migration.
- PostgreSQL is the durable source of jobs; Redis loss may delay dispatch but must not lose a Mail Lookup Job.
- Default timing: 90-second handoff timeout, 180-second Execution Lease, 60-second signature skew, 120-second encrypted result TTL capped by the job TTL, and existing five-minute Mail Lookup Job TTL.
- HTTPS is default; `http_encrypted` is allowed only for a public IP after Master step-up and explicit risk confirmation.
- Sensitive protocol bodies use AES-GCM; messages use HMAC-SHA256; signing and encryption keys are independently derived with HKDF-SHA256.
- No Mailbox App Password, extracted code, executor secret, hosting password, raw email body, or signed payload may appear in logs.
- Executor configuration is stored in PostgreSQL; adding an executor adds no backend environment variable.
- The optional Executor Hosting Account password is encrypted with `DATA_ENCRYPTION_KEY`, omitted from ordinary serializers and exports, and revealed only after fail-closed Master step-up.
- No periodic executor health polling; health evidence comes from manual challenges and real dispatch/callback traffic.
- Frontend text must come from the backend i18n catalog; do not hardcode translated strings.
- Follow TDD for every behavior change: write one behavioral test, run it and confirm the expected failure, add minimal production code, run green, then refactor.
- Task execution is sequential. Complete and review one entire Task before starting the next.

---

## File Map

### Standalone executor

- `worker/pyproject.toml`, `worker/uv.lock` — independent Python project and locked dependencies.
- `worker/app/config.py` — executor ID, secret, concurrency, callback timeout, and optional R2 diagnostic configuration.
- `worker/app/protocol/models.py` — protocol v1 headers, encrypted body, command, challenge, and callback models.
- `worker/app/protocol/crypto.py` — HKDF key derivation, AES-GCM payloads, canonical HMAC signing, and verification.
- `worker/app/protocol/replay.py` — bounded in-memory nonce cache.
- `worker/app/extractors/` — moved Code Service extraction catalog and pure extractor.
- `worker/app/providers/` — Gmail IMAP adapter and normalized email type, without backend models or Fernet.
- `worker/app/pipeline/runner.py` — `execute_lookup(command) -> LookupOutcome`.
- `worker/app/netflix/resolver.py`, `worker/app/netflix/r2_diagnostics.py` — Netflix URL resolution and optional diagnostics.
- `worker/app/callback_client.py` — signed encrypted callback delivery.
- `worker/app/runtime.py` — local concurrency and active-lease tracking.
- `worker/app/main.py` — `/v1/health/challenge` and `/v1/jobs/execute`.
- `worker/CONTEXT.md` — executor-context glossary and non-negotiable runtime rules.
- `worker/tests/` — protocol, extractor, provider, pipeline, callback, and HTTP behavior.

### Backend

- `backend/app/models/lookup_executor.py` — persisted registry.
- `backend/app/models/mail_lookup_job.py` — executor assignment and attempt metadata; remove unused persisted result column.
- `backend/alembic/versions/e023fe74cac3_add_lookup_executors.py` — table, columns, indexes, FK, RLS, and removal of `result_value_encrypted`.
- `backend/app/schemas/lookup_executors.py` — Master request/response contracts.
- `backend/app/schemas/lookup_executor_protocol.py` — backend callback/command protocol types.
- `backend/app/repositories/lookup_executors_repository.py` — registry persistence and dispatchable selection inputs.
- `backend/app/repositories/mailbox_lookup_repository.py` — processing-to-pending recovery, executor assignment, row lock, and durable reconciliation queries.
- `backend/app/core/lookup_executor_protocol.py` — independent backend protocol implementation.
- `backend/app/services/lookup_executor_transport/` — transport port, HTTP adapter, and in-memory adapter.
- `backend/app/services/lookup_executor_registry.py` — enrollment, verification, lifecycle, rotation, password storage/reveal.
- `backend/app/services/master_step_up.py` — shared Master password step-up interface.
- `backend/app/services/lookup_execution_coordinator/` — coordination store, Redis adapter, types, selector, runtime wiring, and coordinator.
- `backend/app/api/v1/endpoints/lookup_executors.py` — Master CRUD/action routes.
- `backend/app/api/v1/endpoints/integrations/executor_callbacks.py` — signed callback route.
- Existing lookup endpoints, console handlers, cleanup, main lifespan, config, metrics, and tests — rewired to the coordinator.

### Frontend

- `frontend/src/routes/master/executors.tsx` — file route.
- `frontend/src/features/master/services/executor-api.ts` — typed registry calls.
- `frontend/src/features/master/components/lookup-executors-page.tsx` — page state and orchestration.
- `frontend/src/features/master/components/executor-table.tsx` — desktop/mobile operational list.
- `frontend/src/features/master/components/executor-enrollment-dialog.tsx` — four-step wizard.
- `frontend/src/features/master/components/executor-credentials-dialog.tsx` — one-time ID/secret display.
- `frontend/src/features/master/components/executor-password-dialog.tsx` — step-up reveal.
- `frontend/src/features/master/components/executor-action-dialogs.tsx` — HTTP confirmation, rotation, disable, and delete dialogs.
- `frontend/src/features/master/layout/master-layout.tsx` — route navigation.
- Backend i18n catalogs — English and Spanish executor strings.

---

### Task 1: Create the standalone worker project and protocol crypto

**Files:**
- Create: `worker/pyproject.toml`
- Create: `worker/app/__init__.py`
- Create: `worker/app/config.py`
- Create: `worker/app/protocol/__init__.py`
- Create: `worker/app/protocol/models.py`
- Create: `worker/app/protocol/crypto.py`
- Create: `worker/app/protocol/replay.py`
- Create: `worker/tests/test_protocol.py`
- Create: `worker/tests/test_config.py`

**Interfaces:**
- Consumes: no earlier task.
- Produces:
  - `ProtocolKeys(signing: bytes, encryption: bytes)`
  - `EncryptedBody(nonce: str, ciphertext: str)`
  - `derive_protocol_keys(secret: str) -> ProtocolKeys`
  - `encrypt_payload(payload: BaseModel | dict[str, object], key: bytes) -> EncryptedBody`
  - `decrypt_payload(body: EncryptedBody, key: bytes) -> dict[str, object]`
  - `sign_request(method, path, executor_id, key_version, timestamp, nonce, body_bytes, signing_key) -> str`
  - `verify_request_signature(method: str, path: str, executor_id: UUID, key_version: int, timestamp: int, nonce: str, body_bytes: bytes, signature: str, signing_key: bytes, now: int, max_skew_seconds: int) -> None`
  - `NonceCache.consume(nonce: str, now: int) -> bool`

- [ ] **Step 1: Add worker project metadata and lockable dependencies**

Create `worker/pyproject.toml` with Python `>=3.12` and these runtime dependencies: `fastapi`, `uvicorn[standard]`, `pydantic`, `pydantic-settings`, `cryptography`, `httpx`, and `boto3`. Add a dev group containing `pytest`, `pytest-asyncio`, and `respx`.

```toml
[project]
name = "trackpal-lookup-executor"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "boto3>=1.35.0",
  "cryptography>=42.0.0",
  "fastapi>=0.136.1",
  "httpx>=0.28.1",
  "pydantic>=2.13.4",
  "pydantic-settings>=2.14.1",
  "uvicorn[standard]>=0.46.0",
]

[dependency-groups]
dev = [
  "pytest>=9.0.3",
  "pytest-asyncio>=1.3.0",
  "respx>=0.23.1",
  "ruff>=0.15.0",
]
```

Run: `cd worker && uv lock`
Expected: `worker/uv.lock` is created without resolving `backend` as a package.

- [ ] **Step 2: Write failing protocol tests with hand-derived fixtures**

Test deterministic key separation, round-trip encryption, tamper rejection, exact canonical signature verification, clock-skew rejection, and duplicate nonce rejection. Use a literal secret and literal request fields; do not derive expected signatures with the production signer.

```python
def test_tampered_ciphertext_is_rejected() -> None:
    keys = derive_protocol_keys("executor-secret")
    body = encrypt_payload({"job_id": "job-1"}, keys.encryption)
    tampered = EncryptedBody(
        nonce=body.nonce,
        ciphertext=body.ciphertext[:-2] + "AA",
    )
    with pytest.raises(InvalidTag):
        decrypt_payload(tampered, keys.encryption)


def test_nonce_cache_rejects_second_use() -> None:
    cache = NonceCache(ttl_seconds=60, max_entries=100)
    assert cache.consume("nonce-1", now=1000) is True
    assert cache.consume("nonce-1", now=1001) is False
```

- [ ] **Step 3: Run the protocol tests and verify RED**

Run: `cd worker && uv run pytest tests/test_protocol.py tests/test_config.py -v`
Expected: collection fails because `app.protocol` and `ExecutorSettings` do not exist.

- [ ] **Step 4: Implement protocol models, crypto, replay cache, and settings**

Use separate HKDF `info` values and a fixed v1 salt. AES-GCM uses a random 12-byte nonce. Canonical request signing joins these values with newline separators:

```python
canonical = "\n".join(
    [
        method.upper(),
        path,
        "1",
        str(executor_id),
        str(key_version),
        str(timestamp),
        nonce,
        hashlib.sha256(body_bytes).hexdigest(),
    ]
).encode("utf-8")
```

`ExecutorSettings` requires `TRACKPAL_EXECUTOR_ID` and `TRACKPAL_EXECUTOR_SECRET`, defaults `TRACKPAL_MAX_CONCURRENCY=1`, and validates positive concurrency.

- [ ] **Step 5: Run protocol tests and Ruff**

Run: `cd worker && uv run pytest tests/test_protocol.py tests/test_config.py -v && uv run ruff check app tests`
Expected: all tests pass and Ruff reports no errors.

- [ ] **Step 6: Commit**

```bash
git add worker/pyproject.toml worker/uv.lock worker/app worker/tests/test_protocol.py worker/tests/test_config.py
git commit -m "feat(worker): add signed executor protocol"
```

---

### Task 2: Move pure extraction and fingerprint behavior into `worker/`

**Files:**
- Create: `worker/app/extractors/__init__.py`
- Create: `worker/app/extractors/types.py`
- Create: `worker/app/extractors/extractor.py`
- Create: `worker/app/extractors/catalog/__init__.py`
- Create: `worker/app/extractors/catalog/{netflix,disney,hbo_max,prime_video,spotify,universal_plus}.py`
- Create: `worker/app/pipeline/email_message.py`
- Create: `worker/app/pipeline/fingerprint.py`
- Create: `worker/tests/test_extractors.py`
- Create: `worker/tests/test_fingerprint.py`
- Source to move later: `backend/app/services/mail_code_extractor/`
- Source to move later: `backend/app/services/mail_lookup_worker/fingerprint.py`
- Source tests: `backend/tests/test_mail_code_extractor.py`
- Source tests: fingerprint cases in `backend/tests/test_mailbox_lookup_worker.py`

**Interfaces:**
- Consumes: Task 1 project.
- Produces:
  - `extract_newest_from_emails(emails, service_key, max_age_minutes) -> ExtractedCode | None`
  - `EmailMessage(subject, body, received_at, message_id, sender, to_recipients)`
  - `compute_fingerprint(service_key: str, message_id: str | None, sender: str | None, received_at_iso: str, subject: str, payload_normalized: str) -> str`

- [ ] **Step 1: Copy characterization tests into worker imports**

Move the extractor test cases to `worker/tests/test_extractors.py`, preserving literal email fixtures and expected codes/URLs for every supported Code Service. Add a separate fingerprint test that asserts the known SHA-256 hex output for one literal input.

```python
def test_spotify_extracts_newest_six_digit_code() -> None:
    result = extract_newest_from_emails(
        [
            ParsedEmail(
                subject="Your Spotify login code",
                body="Enter this code 654321",
                received_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
            )
        ],
        "spotify",
        max_age_minutes=5,
        now=datetime(2026, 8, 1, 0, 1, tzinfo=timezone.utc),
    )
    assert result is not None
    assert result.value == "654321"
```

- [ ] **Step 2: Run the moved tests and verify RED**

Run: `cd worker && uv run pytest tests/test_extractors.py tests/test_fingerprint.py -v`
Expected: imports fail because `app.extractors` and `app.pipeline.fingerprint` do not exist.

- [ ] **Step 3: Move the pure implementation and rewrite imports**

Move the catalog and extractor implementation into `worker/app/extractors/`. Move fingerprint logic into `worker/app/pipeline/fingerprint.py`. Replace every `app.services.mail_code_extractor` import with `app.extractors` and keep the implementation free of FastAPI, SQLAlchemy, Redis, and backend settings.

- [ ] **Step 4: Add the normalized email type**

Create `EmailMessage` as a frozen dataclass so later pipeline code can use one stable representation:

```python
@dataclass(frozen=True, slots=True)
class EmailMessage:
    subject: str
    body: str
    received_at: datetime
    message_id: str | None = None
    sender: str | None = None
    to_recipients: tuple[str, ...] = ()
```

- [ ] **Step 5: Run worker extraction tests**

Run: `cd worker && uv run pytest tests/test_extractors.py tests/test_fingerprint.py -v`
Expected: all extractor and fingerprint behaviors pass unchanged.

- [ ] **Step 6: Commit**

```bash
git add worker/app/extractors worker/app/pipeline worker/tests/test_extractors.py worker/tests/test_fingerprint.py
git commit -m "feat(worker): move mail code extractors"
```

---

### Task 3: Build the standalone Gmail lookup pipeline

**Files:**
- Create: `worker/app/providers/__init__.py`
- Create: `worker/app/providers/errors.py`
- Create: `worker/app/providers/gmail_imap.py`
- Create: `worker/app/netflix/__init__.py`
- Create: `worker/app/netflix/resolver.py`
- Create: `worker/app/netflix/r2_diagnostics.py`
- Create: `worker/app/pipeline/models.py`
- Create: `worker/app/pipeline/runner.py`
- Create: `worker/tests/test_gmail_provider.py`
- Create: `worker/tests/test_pipeline.py`
- Source: `backend/app/services/mail_lookup_worker/providers/`
- Source: execution-only portions of `backend/app/services/mail_lookup_worker/_helpers.py`
- Source: Netflix and R2 portions of `backend/app/services/mail_lookup_worker/worker.py` and `r2_upload.py`

**Interfaces:**
- Consumes: Task 2 `EmailMessage`, extractors, and fingerprint.
- Produces:
  - `LookupCommand`
  - `LookupOutcome`
  - `async execute_lookup(command: LookupCommand, provider: MailProvider, netflix: NetflixResolver) -> LookupOutcome`
  - `async fetch_gmail_messages(mailbox_email, app_password, window_minutes) -> list[EmailMessage]`

- [ ] **Step 1: Write failing provider tests without backend models**

Adapt `backend/tests/test_gmail_app_password_provider.py` so the provider accepts plaintext credentials supplied only for the call. Assert exact Gmail `X-GM-RAW after:<timestamp>` search, bounded newest-message fetch, MIME decoding, and safe error taxonomy.

```python
messages = await fetch_gmail_messages(
    mailbox_email="codes@example.com",
    app_password="app-password",
    window_minutes=5,
    imap_factory=fake_imap_factory,
    now=datetime(2026, 8, 1, tzinfo=timezone.utc),
)
assert messages[0].to_recipients == ("client@example.com",)
```

- [ ] **Step 2: Write failing pipeline outcome tests**

Cover `found`, `not_found`, `retryable_failure`, and `terminal_failure`. Assert that a found outcome contains only normalized result and dedupe metadata, never raw email bodies or the App Password.

```python
assert outcome.kind == "found"
assert outcome.result_type == "code"
assert outcome.result_value == "654321"
assert outcome.message_id == "msg-1"
assert outcome.fingerprint == expected_fingerprint
assert "app-password" not in outcome.model_dump_json()
```

- [ ] **Step 3: Run provider and pipeline tests and verify RED**

Run: `cd worker && uv run pytest tests/test_gmail_provider.py tests/test_pipeline.py -v`
Expected: failures identify missing provider and pipeline modules.

- [ ] **Step 4: Implement provider and pipeline types**

Define literal outcome kinds and result types in Pydantic models. The runner performs target-email filtering before extraction, resolves Netflix URLs, and maps exceptions exactly:

```python
try:
    emails = await provider.fetch(command)
except NonTransientProviderError as exc:
    return LookupOutcome.terminal(exc.error_code, safe_provider_detail(exc.error_code))
except ProviderFetchError:
    return LookupOutcome.retryable("fetch_failed", "Email fetch failed after retries")
```

Port the existing three-attempt exponential backoff and keep raw exception messages out of returned details.

- [ ] **Step 5: Move Netflix resolution and optional R2 diagnostics**

The resolver accepts an injected `httpx.AsyncClient`; diagnostics accept an injected storage adapter or a disabled adapter. A failed diagnostic upload must not change the lookup outcome.

- [ ] **Step 6: Run the worker pipeline suite**

Run: `cd worker && uv run pytest tests/test_gmail_provider.py tests/test_pipeline.py tests/test_extractors.py -v`
Expected: all tests pass with no backend import on the worker import graph.

- [ ] **Step 7: Commit**

```bash
git add worker/app/providers worker/app/netflix worker/app/pipeline worker/tests/test_gmail_provider.py worker/tests/test_pipeline.py
git commit -m "feat(worker): add standalone lookup pipeline"
```

---

### Task 4: Expose the executor HTTP runtime and signed callback

**Files:**
- Create: `worker/app/callback_client.py`
- Create: `worker/app/runtime.py`
- Create: `worker/app/main.py`
- Create: `worker/tests/test_callback_client.py`
- Create: `worker/tests/test_api.py`

**Interfaces:**
- Consumes: Tasks 1–3 protocol and `execute_lookup`.
- Produces:
  - `POST /v1/health/challenge`
  - `POST /v1/jobs/execute`
  - `create_app(settings: ExecutorSettings, runtime: ExecutorRuntime) -> FastAPI`
  - `ExecutorRuntime.accept(command, callback_context) -> Acceptance`
  - signed encrypted callback to the command-provided URL.

- [ ] **Step 1: Write failing HTTP behavior tests**

Use `httpx.ASGITransport` against the real worker app. Cover valid challenge, invalid signature, accepted execution, same-lease duplicate `409`, different-lease conflict `409`, and local capacity `429`.

```python
response = await client.post(
    "/v1/jobs/execute",
    content=body_bytes,
    headers=signed_headers,
)
assert response.status_code == 202
assert response.json() == {"accepted": True, "lease_id": str(lease_id)}
```

- [ ] **Step 2: Run API tests and verify RED**

Run: `cd worker && uv run pytest tests/test_api.py tests/test_callback_client.py -v`
Expected: imports fail because `app.main`, `ExecutorRuntime`, and callback delivery do not exist.

- [ ] **Step 3: Implement bounded runtime state**

Use one `asyncio.Lock`, an active map keyed by job ID, and the configured capacity. Validate and reserve before returning `202`; start execution using FastAPI `BackgroundTasks`. Always release the local slot in `finally` after callback delivery attempts finish.

- [ ] **Step 4: Implement the app factory, challenge, and execute routes**

`create_app(settings, runtime)` registers both routes and lets tests supply a fake pipeline without production test switches. The module-level `app` constructs production settings/runtime. Both routes verify protocol headers, timestamp, nonce, signature, executor ID, and key version before decryption. Challenge responses echo the random challenge and advertise protocol `1`, runtime version `0.1.0`, and configured capacity.

- [ ] **Step 5: Implement callback delivery**

`CallbackClient.send()` encrypts and signs the `LookupOutcome`, uses `follow_redirects=False`, and retries only connection errors and HTTP `5xx`. Treat backend `2xx` with `accepted=false` as final acknowledgement.

- [ ] **Step 6: Run worker suite and verify no backend imports**

Run:

```bash
cd worker
uv run pytest -v
uv run python -c "import app.main; print('worker import ok')"
uv run ruff check app tests
```

Expected: all commands pass; importing `app.main` does not require `backend/` or its environment.

- [ ] **Step 7: Commit**

```bash
git add worker/app/callback_client.py worker/app/runtime.py worker/app/main.py worker/tests
git commit -m "feat(worker): expose lookup executor runtime"
```

---

### Task 5: Add executor persistence, job metadata, and RLS

**Files:**
- Create: `backend/app/models/lookup_executor.py`
- Create: `backend/app/schemas/lookup_executors.py`
- Create: `backend/app/repositories/lookup_executors_repository.py`
- Create: `backend/alembic/versions/e023fe74cac3_add_lookup_executors.py`
- Create: `backend/tests/test_lookup_executor_persistence.py`
- Create: `backend/tests/test_lookup_executor_migration.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/models/mail_lookup_job.py`
- Modify: `backend/app/repositories/mailbox_lookup_repository.py`
- Modify: `backend/tests/test_rls_policy_sql.py`
- Modify: `backend/tests/test_mailbox_persistence.py`

**Interfaces:**
- Consumes: existing SQLAlchemy/Alembic/encryption conventions.
- Produces:
  - `LookupExecutor` model.
  - repository `create`, `get`, `list_all`, `list_dispatchable`, `delete`, and state-update functions.
  - Mail Lookup Job fields `executor_id`, `execution_attempts`, and `last_dispatch_error_safe`.
  - repository recovery transition `processing -> pending`.

- [ ] **Step 1: Write failing model and repository tests**

Assert encrypted fields differ from plaintext, ordinary model serialization has only `has_hosting_password`, dispatchable queries exclude disabled/reverification rows, and a job can recover from processing to pending while clearing assignment timestamps.

- [ ] **Step 2: Write failing migration behavior tests**

Execute `upgrade()` through an Alembic offline `MigrationContext` that captures emitted SQL. Assert the generated operations create `lookup_executors`, add the nullable FK with `SET NULL`, enable/force Master-only RLS, and drop `result_value_encrypted`. Update persistence tests so attempting to use the removed field fails at model construction.

- [ ] **Step 3: Run persistence tests and verify RED**

Run: `cd backend && uv run pytest tests/test_lookup_executor_persistence.py tests/test_lookup_executor_migration.py tests/test_rls_policy_sql.py tests/test_mailbox_persistence.py -v`
Expected: failures reference the missing model, migration, and job columns.

- [ ] **Step 4: Implement the model and migration**

Use string-backed statuses, Boolean defaults, UUID PK, encrypted text columns, and indexes on lifecycle/health. Add this policy:

```sql
CREATE POLICY lookup_executors_master_only ON lookup_executors
FOR ALL
USING (current_setting('app.current_role', true) = 'master')
WITH CHECK (current_setting('app.current_role', true) = 'master')
```

Enable and force RLS. The downgrade restores `result_value_encrypted` before removing the new table and job columns.

- [ ] **Step 5: Implement schemas and repositories**

`LookupExecutorResponse` never contains encrypted values. It contains `has_hosting_password`, current statuses, timing fields, and `active_jobs`. Add `with_for_update=True` support to `mailbox_lookup_repository.get_job()` and allow `processing -> pending` with processing fields cleared.

- [ ] **Step 6: Run persistence and migration tests**

Run: `cd backend && uv run pytest tests/test_lookup_executor_persistence.py tests/test_lookup_executor_migration.py tests/test_rls_policy_sql.py tests/test_mailbox_persistence.py -v`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add backend/app/models backend/app/schemas/lookup_executors.py backend/app/repositories backend/alembic/versions/e023fe74cac3_add_lookup_executors.py backend/tests
git commit -m "feat(backend): persist lookup executor registry"
```

---

### Task 6: Add backend protocol crypto, SSRF validation, and HTTP transport

**Files:**
- Create: `backend/app/schemas/lookup_executor_protocol.py`
- Create: `backend/app/core/lookup_executor_protocol.py`
- Create: `backend/app/services/lookup_executor_transport/__init__.py`
- Create: `backend/app/services/lookup_executor_transport/protocol.py`
- Create: `backend/app/services/lookup_executor_transport/http.py`
- Create: `backend/app/services/lookup_executor_transport/fake.py`
- Create: `backend/app/services/lookup_executor_transport/url_safety.py`
- Create: `backend/tests/test_lookup_executor_protocol.py`
- Create: `backend/tests/test_lookup_executor_transport.py`

**Interfaces:**
- Consumes: Task 5 executor model.
- Produces:
  - backend-independent copy of protocol v1.
  - `ChallengeResult(executor_id, protocol_version, runtime_version, max_concurrency)`.
  - `HandoffResult(status, lease_id, safe_error)`.
  - `LookupExecutorTransport.challenge(executor, challenge) -> ChallengeResult`.
  - `LookupExecutorTransport.handoff(executor, envelope) -> HandoffResult`.
  - `validate_executor_url(base_url, transport_mode, resolver) -> ValidatedExecutorUrl`.

- [ ] **Step 1: Write failing protocol compatibility fixtures**

Use the same literal secret/request vector as worker Task 1, but store the expected signature and ciphertext fixture as literals in the backend test. Assert backend output decrypts to the expected command and rejects a changed path.

- [ ] **Step 2: Write failing URL safety tests**

Cover HTTPS hostname, HTTPS public IP, explicit HTTP public IP, HTTP hostname rejection, URL credentials, fragments, redirects, loopback, RFC1918, link-local, multicast, reserved ranges, metadata IPs, and DNS answers that change to private addresses.

- [ ] **Step 3: Run tests and verify RED**

Run: `cd backend && uv run pytest tests/test_lookup_executor_protocol.py tests/test_lookup_executor_transport.py -v`
Expected: missing protocol and transport modules.

- [ ] **Step 4: Implement protocol crypto independently**

Match the worker canonical string, HKDF salt/info values, URL-safe Base64 encoding, AES-GCM nonce size, and signature comparison with `hmac.compare_digest`. Do not import from `worker/`.

- [ ] **Step 5: Implement the transport port and HTTP adapter**

Use an `httpx.AsyncClient(follow_redirects=False)` and validate DNS immediately before each request. Map statuses to explicit `HandoffStatus` values: `accepted`, `duplicate_same_lease`, `busy`, `security_error`, `protocol_error`, and `transport_error`.

- [ ] **Step 6: Run focused transport tests**

Run: `cd backend && uv run pytest tests/test_lookup_executor_protocol.py tests/test_lookup_executor_transport.py -v`
Expected: all pass, including no-follow redirect and DNS rebinding cases.

- [ ] **Step 7: Commit**

```bash
git add backend/app/core/lookup_executor_protocol.py backend/app/schemas/lookup_executor_protocol.py backend/app/services/lookup_executor_transport backend/tests/test_lookup_executor_protocol.py backend/tests/test_lookup_executor_transport.py
git commit -m "feat(backend): add executor protocol transport"
```

---

### Task 7: Implement Master enrollment, lifecycle, rotation, and hosting-password controls

**Files:**
- Create: `backend/app/services/master_step_up.py`
- Create: `backend/app/services/lookup_executor_registry.py`
- Create: `backend/app/api/v1/endpoints/lookup_executors.py`
- Create: `backend/tests/test_lookup_executor_api.py`
- Modify: `backend/app/api/v1/router.py`
- Modify: `backend/app/api/v1/endpoints/tenant_export.py` to use shared Master step-up.
- Modify: `backend/app/core/i18n/catalogs_en_frontend.py`
- Modify: `backend/app/core/i18n/catalogs_es_frontend.py`

**Interfaces:**
- Consumes: Tasks 5–6 persistence and transport.
- Produces `ActiveLeaseReader.active_count(executor_id: UUID) -> int`, supplied by a fake in tests and by the Redis coordination store in Task 8. Until Task 8 wiring exists, the production `UnavailableActiveLeaseReader` fails deletion closed with `executor_coordination_unavailable`.
- Produces Master routes under `/api/v1/lookup-executors`:
  - `POST /`
  - `GET /`
  - `GET /{executor_id}`
  - `PUT /{executor_id}`
  - `POST /{executor_id}/verify`
  - `POST /{executor_id}/test`
  - `POST /{executor_id}/enable`
  - `POST /{executor_id}/disable`
  - `POST /{executor_id}/rotate-secret`
  - `POST /{executor_id}/reveal-hosting-password`
  - `DELETE /{executor_id}`.

- [ ] **Step 1: Write failing Master API tests**

Cover Master-only access, draft creation with one-time `plain_secret`, ordinary responses without secret/password, HTTP verification requiring password plus exact confirmation `ALLOW HTTP`, challenge activation, rotation pending-secret promotion, disable semantics, delete blocked by active jobs/leases, deletion failing closed when lease coordination is unavailable, and step-up password reveal.

```python
response = await client.post(
    "/api/v1/lookup-executors/",
    headers=auth_headers,
    json={"name": "Render 1", "provider_label": "render", "max_concurrency": 1},
)
assert response.status_code == 201
assert response.json()["plain_secret"]
assert "hosting_account_password" not in response.json()["executor"]
```

- [ ] **Step 2: Run endpoint tests and verify RED**

Run: `cd backend && uv run pytest tests/test_lookup_executor_api.py -v`
Expected: route returns `404` because the endpoint module is not registered.

- [ ] **Step 3: Extract shared Master step-up**

Move the password-check behavior from `tenant_export._verify_master_password` into:

```python
async def verify_master_step_up(
    db: AsyncSession,
    master_user: User,
    password: str,
    limiter: StepUpRateLimiter | None,
) -> None:
```

It requires a configured limiter, checks it first, verifies bcrypt, records failure, resets on success, and raises stable service errors. A missing limiter is `step_up_unavailable`, not permission to proceed. Reuse it from tenant export to prove behavior did not fork.

- [ ] **Step 4: Implement registry lifecycle rules**

Generate secrets with `secrets.token_urlsafe(32)`, encrypt both protocol and hosting credentials with Fernet, verify current or pending secret through the transport, promote pending rotation only after a matching challenge, set `requires_reverification` after protocol security failures, and prohibit deletion while either processing jobs or Redis Execution Leases remain active.

- [ ] **Step 5: Implement API schemas and route mappings**

Return stable detail codes such as `executor_not_found`, `executor_has_active_jobs`, `invalid_master_password`, `insecure_http_confirmation_required`, and `executor_verification_failed`. Do not return raw transport exceptions. Log hosting-password reveal as safe audit context containing only Master ID, executor ID, operation, and outcome.

- [ ] **Step 6: Add bilingual frontend catalog keys**

Add navigation, list, wizard, actions, status, transport warning, one-time secret, reveal, and error keys under `frontend.master.executors.*` in both catalogs.

- [ ] **Step 7: Run API and existing step-up/export tests**

Run: `cd backend && uv run pytest tests/test_lookup_executor_api.py tests/test_step_up_limiter.py tests/test_tenant_export_api.py -v`
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/master_step_up.py backend/app/services/lookup_executor_registry.py backend/app/api/v1/endpoints/lookup_executors.py backend/app/api/v1/router.py backend/app/api/v1/endpoints/tenant_export.py backend/app/core/i18n backend/tests
git commit -m "feat(backend): add executor registry API"
```

---

### Task 8: Add Redis queue, locks, leases, capacity, nonces, and encrypted results

**Files:**
- Create: `backend/app/services/lookup_execution_coordinator/types.py`
- Create: `backend/app/services/lookup_execution_coordinator/store.py`
- Create: `backend/app/services/lookup_execution_coordinator/redis_store.py`
- Create: `backend/app/services/lookup_execution_coordinator/fake_store.py`
- Create: `backend/tests/test_lookup_coordination_store.py`
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/services/lookup_executor_registry.py`
- Modify: `backend/.env.example`
- Modify: `docs/code-standard/backend-conventions.md` Redis key table.

**Interfaces:**
- Consumes: existing `RedisConnectionManager`.
- Produces `LookupCoordinationStore` methods:
  - `enqueue(job_id)` / `pop()`
  - `acquire_dispatch_lock(job_id)` / `release_dispatch_lock(job_id)`
  - `reserve_lease(job_id, executor_id, lease_id, expires_at)`
  - `get_lease(job_id)` / `release_lease(job_id)`
  - `active_count(executor_id)`
  - `consume_callback_nonce(executor_id, nonce, ttl_seconds)`
  - `put_result(job_id, result_type, result_value, ttl_seconds)` / `get_result(job_id)`
  - failure cooldown helpers.

- [ ] **Step 1: Write failing store contract tests**

Run the same behavioral test suite against `FakeLookupCoordinationStore` and a Redis adapter backed by the existing fake manager. Assert duplicate enqueue is harmless, one dispatch lock wins, expired leases stop counting, nonce second use fails, and result storage never contains plaintext.

- [ ] **Step 2: Run store tests and verify RED**

Run: `cd backend && uv run pytest tests/test_lookup_coordination_store.py -v`
Expected: missing coordinator store modules.

- [ ] **Step 3: Add explicit backend timing settings**

Add:

```python
lookup_executor_handoff_timeout_seconds: int = 90
lookup_execution_lease_seconds: int = 180
lookup_signature_skew_seconds: int = 60
lookup_result_ttl_seconds: int = 120
lookup_executor_failure_cooldown_seconds: int = 300
lookup_dispatch_batch_size: int = 10
```

Correct the stale `.env.example` mailbox TTL name to `MAILBOX_LOOKUP_JOB_TTL_MINUTES=5`.

- [ ] **Step 4: Implement Redis keys and atomic semantics**

Use namespaced keys:

```text
mailbox:lookup:queue
lookup:dispatch-lock:{job_id}
lookup:lease:{job_id}
lookup:executor-leases:{executor_id}
lookup:callback-nonce:{executor_id}:{nonce}
lookup:result:{job_id}
lookup:executor-cooldown:{executor_id}
```

Use `SET NX EX` for locks/nonces, sorted sets scored by lease expiry for capacity, and Fernet-encrypted JSON for results. Make `RedisLookupCoordinationStore.active_count()` satisfy Task 7's `ActiveLeaseReader`, replace the fail-closed unavailable reader in runtime wiring, and avoid adding a second lease-count interface.

- [ ] **Step 5: Run store tests and Redis manager regressions**

Run: `cd backend && uv run pytest tests/test_lookup_coordination_store.py tests/test_redis_connection_manager.py tests/test_redis_failover_policy.py -v`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/lookup_execution_coordinator backend/app/services/lookup_executor_registry.py backend/app/core/config.py backend/.env.example docs/code-standard/backend-conventions.md backend/tests/test_lookup_coordination_store.py
git commit -m "feat(backend): add Redis execution coordination"
```

---

### Task 9: Implement external scheduling, selection, and handoff

**Files:**
- Create: `backend/app/services/lookup_execution_coordinator/selector.py`
- Create: `backend/app/services/lookup_execution_coordinator/coordinator.py`
- Create: `backend/app/services/lookup_execution_coordinator/runtime.py`
- Create: `backend/app/services/lookup_execution_coordinator/__init__.py`
- Create: `backend/tests/test_lookup_execution_coordinator.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/core/metrics.py` only if a reset helper is required by existing metric-test style.

**Interfaces:**
- Consumes: Tasks 5–8 persistence, transport, and coordination store.
- Produces `LookupExecutionCoordinator.schedule(job_id: UUID) -> None`. Task 10 adds the final `complete` and `get_result` entry points after their tests exist.

- [ ] **Step 1: Write failing selection and scheduling tests**

Assert least-loaded ratio, stable tie-breaking, exclusion of disabled/reverification/cooldown/full executors, one active pump despite duplicate `schedule`, accepted handoff transition, `429` requeue without health penalty, transport failure requeue, security failure quarantine, and no executor leaving the durable job pending.

- [ ] **Step 2: Run coordinator tests and verify RED**

Run: `cd backend && uv run pytest tests/test_lookup_execution_coordinator.py -v`
Expected: missing coordinator and selector modules.

- [ ] **Step 3: Implement selector as a pure function**

```python
def select_executor(candidates: list[ExecutorCapacity]) -> ExecutorCapacity | None:
    eligible = [item for item in candidates if item.active_leases < item.max_concurrency]
    return min(
        eligible,
        key=lambda item: (
            item.active_leases / item.max_concurrency,
            item.last_selected_at or datetime.min.replace(tzinfo=timezone.utc),
            str(item.executor_id),
        ),
        default=None,
    )
```

- [ ] **Step 4: Implement idempotent scheduling and short-lived pump**

Inject a task spawner into the coordinator. Production uses `asyncio.create_task`; tests use a collecting spawner and await the captured task. `schedule` enqueues, starts at most one pump, and returns before handoff completion.

- [ ] **Step 5: Implement handoff outcomes and health transitions**

Create the Redis reservation and lease, decrypt Mailbox and executor secret only for envelope construction, call transport, and map outcomes exactly. On `202` or same-lease `409`, set job `processing`, `executor_id`, increment attempts, mark the executor healthy, reset consecutive failures, and commit. On transport failure, release reservation and leave/recover `pending`; one or two consecutive failures mark degraded, the third marks unreachable and opens the five-minute cooldown. Security errors set `requires_reverification=true` immediately. `429` changes neither health nor failure count.

- [ ] **Step 6: Wire runtime construction in FastAPI lifespan**

After Redis initialization, configure one coordinator with the HTTP transport and Redis store. Do not start a permanent lookup worker loop. Keep mailbox cleanup running.

- [ ] **Step 7: Run coordinator and main tests**

Run: `cd backend && uv run pytest tests/test_lookup_execution_coordinator.py tests/test_main.py -v`
Expected: all pass; startup contains no local lookup execution loop.

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/lookup_execution_coordinator backend/app/main.py backend/tests/test_lookup_execution_coordinator.py backend/tests/test_main.py
git commit -m "feat(backend): dispatch lookup jobs externally"
```

---

### Task 10: Complete signed callbacks, dedupe, retry, and Redis result delivery

**Files:**
- Create: `backend/app/api/v1/endpoints/integrations/executor_callbacks.py`
- Create: `backend/tests/test_lookup_executor_callbacks.py`
- Modify: `backend/app/api/v1/endpoints/integrations/__init__.py`
- Modify: `backend/app/services/lookup_execution_coordinator/coordinator.py`
- Modify: `backend/app/repositories/mailbox_dedupe_repository.py` only if the callback needs a focused result type.
- Modify: `backend/app/repositories/mailbox_lookup_repository.py`

**Interfaces:**
- Consumes: Task 9 coordinator and Task 6 protocol verifier.
- Produces:
  - `VerifiedCallback(executor_id, lease_id, key_version, nonce, outcome)`.
  - `CompletionAck(accepted: bool)`.
  - `LookupExecutionCoordinator.complete(job_id: UUID, callback: VerifiedCallback) -> CompletionAck`.
  - `LookupExecutionCoordinator.get_result(job_id: UUID) -> tuple[str, str] | None`.
  - callback endpoint and transactional completion behavior.

- [ ] **Step 1: Write failing callback tests**

Cover found result, duplicate suppression, not found, retryable failure returning processing to pending, terminal auth failure, pending/callback race, expired lease, wrong executor, wrong lease, duplicate callback, nonce replay, and Redis result ciphertext.

```python
assert response.status_code == 200
assert response.json() == {"accepted": True}
job = await mailbox_lookup_repository.get_job(db_session, job_id)
assert job.status == "completed"
assert job.result_type == "code"
assert await store.get_result(job_id) == ("code", "654321")
```

- [ ] **Step 2: Run callback tests and verify RED**

Run: `cd backend && uv run pytest tests/test_lookup_executor_callbacks.py -v`
Expected: callback route is absent.

- [ ] **Step 3: Implement callback authentication at the integration seam**

Set internal RLS context, load the executor, verify HMAC/timestamp/key version, atomically consume the Redis nonce, decrypt the callback, and pass a `VerifiedCallback` to `coordinator.complete`.

- [ ] **Step 4: Implement transactional completion**

Lock the job row, validate current lease, and apply dedupe before terminal status. A retryable callback uses `processing -> pending`, clears assignment fields, releases lease, and re-enqueues only while `expires_at > now`.

- [ ] **Step 5: Implement encrypted result retrieval**

`get_result` delegates to the coordination store. Result TTL is `min(120, remaining_job_ttl_seconds)` and no result is stored for `not_found` or `duplicate_suppressed`.

- [ ] **Step 6: Run callback, dedupe, and cleanup tests**

Run: `cd backend && uv run pytest tests/test_lookup_executor_callbacks.py tests/test_mailbox_cleanup.py tests/test_mailbox_persistence.py -v`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add backend/app/api/v1/endpoints/integrations backend/app/services/lookup_execution_coordinator backend/app/repositories backend/tests/test_lookup_executor_callbacks.py
git commit -m "feat(backend): complete executor callbacks"
```

---

### Task 11: Rewire all Mail Lookup Job creation and polling callers

**Files:**
- Modify: `backend/app/api/v1/endpoints/integrations/mail_lookups.py`
- Modify: `backend/app/api/v1/endpoints/integrations/console_handlers.py`
- Modify: `backend/tests/test_mailbox_lookup_api.py`
- Modify: `backend/tests/test_tenant_console_service.py`
- Modify: `backend/tests/test_whatsapp_endpoint.py`
- Modify: `backend/tests/test_demo_guardrails.py`
- Modify: `backend/tests/test_demo_integration_gate.py`
- Modify: `docs/architecture/whatsapp-console-flow.md`

**Interfaces:**
- Consumes: working coordinator from Tasks 9–10.
- Produces: every job creation path calls `schedule`; every pending poll opportunistically calls `schedule`; result polling reads Redis through `get_result`.

- [ ] **Step 1: Change endpoint tests first**

Replace enqueue mocks with an injected/fake coordinator. Add a test proving a committed job ID is returned even when immediate scheduling cannot reach Redis or an executor, because PostgreSQL reconciliation is now authoritative. Add a poll test proving `pending` triggers another idempotent `schedule` call.

- [ ] **Step 2: Run changed lookup and console tests and verify RED**

Run: `cd backend && uv run pytest tests/test_mailbox_lookup_api.py tests/test_tenant_console_service.py tests/test_whatsapp_endpoint.py -v`
Expected: failures show old `enqueue_job` calls and process-local result reads.

- [ ] **Step 3: Rewire n8n create and poll endpoints**

After durable commit, call `await coordinator.schedule(job.id)`. Do not compensate by deleting the durable job when scheduling is unavailable. Polling calls `schedule` only for non-expired pending jobs and obtains found values through `coordinator.get_result(job.id)`.

- [ ] **Step 4: Rewire all console-handler creation/retry branches**

Replace the three `enqueue_job` sites with the same durable-commit-plus-schedule contract. Preserve `lookup_job_id` and `tenant_id` after commit even when immediate dispatch is delayed; update localized fallback behavior only when job creation itself fails.

- [ ] **Step 5: Update guardrail mocks and documentation contract**

Demo guardrail tests must assert the coordinator is not called. Update WhatsApp flow docs to state that successful durable creation is enough to return the ID and dispatch may be recovered by polling.

- [ ] **Step 6: Run the affected integration suites**

Run:

```bash
cd backend
uv run pytest tests/test_mailbox_lookup_api.py tests/test_tenant_console_service.py tests/test_whatsapp_endpoint.py tests/test_demo_guardrails.py tests/test_demo_integration_gate.py -v
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add backend/app/api/v1/endpoints/integrations backend/tests docs/architecture/whatsapp-console-flow.md
git commit -m "refactor(backend): wire external lookup execution"
```

---

### Task 12: Add the Master executor route, typed API, and operational list

**Files:**
- Create: `frontend/src/routes/master/executors.tsx`
- Create: `frontend/src/features/master/services/executor-api.ts`
- Create: `frontend/src/features/master/components/lookup-executors-page.tsx`
- Create: `frontend/src/features/master/components/executor-table.tsx`
- Create: `frontend/src/features/master/components/__tests__/lookup-executors-page.spec.tsx`
- Modify: `frontend/src/features/master/layout/master-layout.tsx`

**Interfaces:**
- Consumes: Task 7 Master HTTP contracts and i18n keys.
- Produces: `/master/executors`, typed API functions, responsive list, and navigation.

- [ ] **Step 1: Write failing page behavior tests**

Mock only `executor-api.ts`; render the real page and table. Assert loading, retry, empty state, desktop table, mobile cards, transport badges, lifecycle/health, active/capacity, last safe error, and absence of passwords/secrets.

- [ ] **Step 2: Run page tests and verify RED**

Run: `cd frontend && npm test -- src/features/master/components/__tests__/lookup-executors-page.spec.tsx`
Expected: module imports fail.

- [ ] **Step 3: Add exact typed API contracts**

Define `LookupExecutor`, status unions, `LookupExecutorEnrollment`, create/update/verify/reveal requests, and functions matching all Task 7 endpoints. Add `mapExecutorError(error, fallbackKey)` to translate stable backend codes through `t()`.

- [ ] **Step 4: Implement page and responsive list**

Follow `DemosTab` loading/error/refresh structure. Desktop uses a table; mobile uses cards under `md:hidden`. Do not poll. Display `HTTP encrypted` as a warning badge and `requires_reverification` as an action-required state.

- [ ] **Step 5: Wire route and sidebar**

Use `to` values instead of hardcoded `active: true`:

```tsx
{
  label: t("frontend.master.executors.navigation"),
  icon: <ServerCog className="size-4 shrink-0" />,
  to: "/master/executors",
}
```

Do not edit `routeTree.gen.ts`; Vite/TanStack generates it.

- [ ] **Step 6: Run focused tests and build**

Run: `cd frontend && npm test -- src/features/master/components/__tests__/lookup-executors-page.spec.tsx && npm run build`
Expected: test and strict TypeScript build pass.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/routes/master/executors.tsx frontend/src/features/master frontend/src/routeTree.gen.ts
git commit -m "feat(frontend): add lookup executor management"
```

---

### Task 13: Add enrollment wizard and one-time executor credentials

**Files:**
- Create: `frontend/src/features/master/components/executor-enrollment-dialog.tsx`
- Create: `frontend/src/features/master/components/executor-credentials-dialog.tsx`
- Create: `frontend/src/features/master/components/__tests__/executor-enrollment-dialog.spec.tsx`
- Modify: `frontend/src/features/master/components/lookup-executors-page.tsx`

**Interfaces:**
- Consumes: Task 12 API types/functions.
- Produces: four-step draft/credentials/connection/activation flow.

- [ ] **Step 1: Write failing wizard tests**

Assert required name/provider/capacity, optional hosting account fields without workspace, one-time ID/secret display and copy actions, closing clears plaintext, URL and transport step, challenge verification, and final activation.

- [ ] **Step 2: Run wizard tests and verify RED**

Run: `cd frontend && npm test -- src/features/master/components/__tests__/executor-enrollment-dialog.spec.tsx`
Expected: missing wizard modules.

- [ ] **Step 3: Implement controlled wizard state**

Use a discriminated step union:

```ts
type EnrollmentStep = "identity" | "credentials" | "connection" | "activation";
```

Create the draft before entering credentials. Keep `plain_secret` only in dialog state; clear it on dismiss and never add it to list state.

- [ ] **Step 4: Implement accessible credentials dialog**

Reuse the copy/announcement behavior from `DemoCredentialsDialog`, but show `executor_id` and `plain_secret`. The dismiss action explicitly warns that the secret cannot be retrieved again.

- [ ] **Step 5: Implement connection verification and activation**

Save URL/transport/capacity, call verify, show advertised protocol/runtime/capacity, prevent configured capacity above advertised capacity, then enable.

- [ ] **Step 6: Run wizard and page tests**

Run: `cd frontend && npm test -- src/features/master/components/__tests__/executor-enrollment-dialog.spec.tsx src/features/master/components/__tests__/lookup-executors-page.spec.tsx`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/features/master/components/executor-enrollment-dialog.tsx frontend/src/features/master/components/executor-credentials-dialog.tsx frontend/src/features/master/components/lookup-executors-page.tsx frontend/src/features/master/components/__tests__
git commit -m "feat(frontend): add executor enrollment wizard"
```

---

### Task 14: Add HTTP-risk confirmation, hosting-password reveal, rotation, and lifecycle actions

**Files:**
- Create: `frontend/src/features/master/components/executor-password-dialog.tsx`
- Create: `frontend/src/features/master/components/executor-action-dialogs.tsx`
- Create: `frontend/src/features/master/components/__tests__/executor-security-actions.spec.tsx`
- Modify: `frontend/src/features/master/components/executor-table.tsx`
- Modify: `frontend/src/features/master/components/lookup-executors-page.tsx`

**Interfaces:**
- Consumes: Task 12 API actions and Task 13 dialogs.
- Produces: complete v1 operational actions.

- [ ] **Step 1: Write failing security-action tests**

Assert HTTP verification requires Master password plus exact confirmation, reveal does not occur before step-up, plaintext disappears on close, rotate shows a new secret once, disable keeps active-job display, and delete is disabled while active jobs are nonzero.

- [ ] **Step 2: Run tests and verify RED**

Run: `cd frontend && npm test -- src/features/master/components/__tests__/executor-security-actions.spec.tsx`
Expected: missing dialogs and actions.

- [ ] **Step 3: Implement HTTP-risk dialog**

Require the user to type `ALLOW HTTP` and enter the Master password. Show permanent transport metadata warning; never treat HTTP as equivalent visual status to HTTPS.

- [ ] **Step 4: Implement hosting-password reveal**

Keep the response only in dialog state, use `type="password"` until explicit reveal, provide copy, and clear both entered Master password and revealed hosting password when closed.

- [ ] **Step 5: Implement rotation, disable, enable, test, and delete actions**

Rotation uses the one-time credentials dialog with the new secret version. Disable/enable refresh the list. Manual test warns that Render Free may cold-start. Delete uses confirmation and is unavailable while `active_jobs > 0`.

- [ ] **Step 6: Run all Master executor frontend tests and build**

Run:

```bash
cd frontend
npm test -- src/features/master/components/__tests__/lookup-executors-page.spec.tsx src/features/master/components/__tests__/executor-enrollment-dialog.spec.tsx src/features/master/components/__tests__/executor-security-actions.spec.tsx
npm run build
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/features/master/components frontend/src/features/master/services/executor-api.ts
git commit -m "feat(frontend): add executor security actions"
```

---

### Task 15: Add cross-project contract coverage and remove the local pipeline

**Files:**
- Create: `backend/tests/test_lookup_executor_contract.py`
- Create: `backend/tests/contract_callback_server.py`
- Create: `worker/tests/contract_app.py`
- Delete after moved behavior is green:
  - `backend/app/services/mail_code_extractor/`
  - `backend/app/services/mail_lookup_worker/providers/`
  - `backend/app/services/mail_lookup_worker/worker.py`
  - `backend/app/services/mail_lookup_worker/_helpers.py`
  - `backend/app/services/mail_lookup_worker/ephemeral_cache.py`
  - `backend/app/services/mail_lookup_worker/fingerprint.py`
  - `backend/app/services/mail_lookup_worker/r2_upload.py`
  - dequeue-only portions of `backend/app/services/mail_lookup_worker/redis_queue.py`
  - `backend/tests/test_mail_code_extractor.py`
  - `backend/tests/test_gmail_app_password_provider.py`
  - local-pipeline portions of `backend/tests/test_mailbox_lookup_worker.py`
- Modify: `backend/app/services/mail_lookup_worker/__init__.py` or delete package if no caller remains.
- Modify: `backend/app/main.py`
- Modify: affected imports/tests discovered by reference search.

**Interfaces:**
- Consumes: complete backend and worker runtimes.
- Produces: verified protocol compatibility and a backend with no local pipeline.

- [ ] **Step 1: Write the real cross-process contract test**

Create `worker/tests/contract_app.py` with `create_app()` and a deterministic fake pipeline that returns code `654321` while using the real worker protocol, runtime, routes, and callback client. Start it with `subprocess.Popen(["uv", "run", "--project", "../worker", "uvicorn", "tests.contract_app:app", "--port", str(port)])` on a free local port. Start `contract_callback_server.py` on a second port to capture and verify the worker callback with the backend protocol module. Configure the backend HTTP adapter with the test-only URL resolver that permits loopback. Verify challenge, encrypted handoff, signed callback, and normalized outcome through the real network seam. Do not import worker implementation modules into backend production code.

- [ ] **Step 2: Run the contract test and verify RED**

Run: `cd backend && uv run pytest tests/test_lookup_executor_contract.py -v`
Expected: the first run fails because the subprocess worker and callback harness are not yet wired to the backend transport; the failure must occur at the real HTTP/protocol seam, not during test collection.

- [ ] **Step 3: Make the minimal compatibility fixes**

Align only mismatched field names, canonical paths, key versions, and status mappings. Do not create a shared runtime package between backend and worker.

- [ ] **Step 4: Prove old modules have no remaining production callers**

Run:

```bash
rg "mail_code_extractor|process_job\(|worker_loop\(|get_ephemeral_result|StubProvider|dequeue_job" backend/app backend/tests
```

Expected: matches exist only in files scheduled for deletion or tests being migrated. Any other match must be rewired before deletion.

- [ ] **Step 5: Delete obsolete code and move remaining behavior tests**

Remove the verified dead modules. Keep only an enqueue compatibility helper if a live caller still needs the queue key; otherwise the coordinator store owns it. Replace implementation-detail tests with worker behavior tests and backend coordinator/callback tests.

- [ ] **Step 6: Run worker and backend suites**

Run:

```bash
cd worker && uv run pytest && uv run ruff check app tests
cd ../backend && uv run pytest && uv run ruff check .
```

Expected: all tests pass and no backend import references the removed pipeline.

- [ ] **Step 7: Commit**

```bash
git add -A worker backend
git commit -m "refactor(mail): remove local lookup pipeline"
```

---

### Task 16: Add deployment guides, update architecture docs, and run final verification

**Files:**
- Create: `worker/Dockerfile`
- Create: `worker/render.yaml`
- Create: `worker/.env.example`
- Create: `worker/README.md`
- Create: `worker/CONTEXT.md`
- Create: `docs/how-to/deploy-lookup-executor-render.md`
- Create: `docs/how-to/deploy-lookup-executor-vps.md`
- Modify: `CONTEXT-MAP.md`
- Modify: `docs/SUMMARY.md`
- Modify: `docs/architecture/system-overview.md`
- Modify: `docs/architecture/mailbox-ingestion.md`
- Modify: `docs/architecture/api-layer.md`
- Modify: `docs/architecture/database-schema.md`
- Modify: `docs/architecture/redis-ha.md`
- Modify: `docs/architecture/frontend-architecture.md`
- Modify: `docs/codebase/backend-structure.md`
- Modify: `docs/codebase/frontend-structure.md`
- Modify: `backend/CONTEXT.md`
- Modify: `frontend/CONTEXT.md`
- Modify: `render.yaml` only if backend timing env defaults need Blueprint entries.

**Interfaces:**
- Consumes: finished implementation.
- Produces: independently deployable artifacts, operational runbooks, and release evidence.

- [ ] **Step 1: Add worker deployment artifacts**

`worker/Dockerfile` uses a Python 3.12 slim image, installs `uv`, syncs the locked project, runs as a non-root user, exposes `8000`, and starts `uvicorn app.main:app`. `worker/render.yaml` defines one Free Web Service with `rootDir: worker`, ID/secret as `sync: false`, and concurrency `1`.

- [ ] **Step 2: Write the Render tutorial**

Document: create draft in TrackPal, copy one-time credentials, create Render Free Web Service from `worker/`, set env values, copy URL, verify, activate, expected one-minute cold start, shared 750 workspace hours, manual health test, rotation, and rollback.

- [ ] **Step 3: Write the Docker/VPS tutorial**

Include exact Docker commands, public-IP firewall ports, HTTPS with Caddy/domain, `sslip.io` Caddy example, direct-IP certificate note, and explicit `http_encrypted` setup requiring Master step-up and `ALLOW HTTP`.

```caddyfile
203-0-113-10.sslip.io {
    reverse_proxy 127.0.0.1:8000
}
```

- [ ] **Step 4: Update architecture and codebase documentation**

Remove statements that FastAPI processes lookup jobs. Document PostgreSQL reconciliation after Redis loss, no local fallback, Master registry routes, callback route, encrypted result cache, and the `worker/` project. Add Worker to `CONTEXT-MAP.md` and create `worker/CONTEXT.md` with Lookup Executor, Execution Lease, protocol secret, and no-durable-secret rules.

- [ ] **Step 5: Run the full verification matrix**

Run:

```bash
cd backend && uv run pytest && uv run ruff check . && uv run ruff format --check .
cd ../worker && uv run pytest && uv run ruff check app tests && uv run ruff format --check app tests
cd ../frontend && npm test && npm run lint && npm run build
```

Expected: every command exits `0`; output contains no unexpected warnings or secret values.

- [ ] **Step 6: Run secret/dead-reference checks**

Run:

```bash
rg "mail_code_extractor|process_job\(|worker_loop\(|get_ephemeral_result|result_value_encrypted" backend/app docs
rg "TRACKPAL_EXECUTOR_SECRET|hosting_account_password|app_password" worker backend/app frontend/src
```

Expected: the first command finds only intentional historical migration/spec references; the second finds declarations and safe handling paths, never literal credentials or logging statements.

- [ ] **Step 7: Inspect the final diff against the spec acceptance criteria**

Confirm all 13 acceptance criteria in `docs/superpowers/specs/2026-08-01-external-mail-lookup-executors-design.md` have code, tests, or documentation evidence. Record any external deployment that cannot be executed locally as a manual release step rather than claiming it was verified.

- [ ] **Step 8: Commit**

```bash
git add worker docs CONTEXT-MAP.md backend/CONTEXT.md frontend/CONTEXT.md render.yaml
git commit -m "docs(mail): document external lookup executors"
```
