# Task 6 Report: Backend Protocol Crypto and Executor Transport

## Implementation

- Added an independent backend protocol v1 implementation with HKDF-SHA256 key separation, AES-GCM payload encryption/decryption, canonical request signing, timestamp validation, and constant-time HMAC verification.
- Added protocol value objects for encrypted bodies, challenge results, handoff results, and explicit handoff statuses.
- Added the `LookupExecutorTransport` protocol port and an in-memory fake adapter.
- Added the HTTP adapter using `httpx.AsyncClient(follow_redirects=False)`, signed/encrypted challenge and handoff requests, response validation, safe status mapping, and lease identity handling.
- Added URL validation that rejects unsafe schemes, HTTP hostnames, credentials, fragments, invalid ports, private/loopback/link-local/multicast/reserved/metadata addresses, and DNS results containing any non-public address. DNS is revalidated for every transport request.

## Tests and Results

- TDD RED run:
  - `cd backend && uv run pytest tests/test_lookup_executor_protocol.py tests/test_lookup_executor_transport.py -v`
  - Failed during collection with the expected missing-module errors for the new protocol and transport modules.
- Focused GREEN run:
  - `cd backend && uv run pytest tests/test_lookup_executor_protocol.py tests/test_lookup_executor_transport.py -q`
  - Result: **21 passed** before the review-fix cycle and **29 passed** after the review-fix cycle.
- Static validation:
  - Ruff check passed for all changed backend and worker application and test files.
  - Ruff format check passed for all changed backend and worker application and test files.
- Full backend suite after the review fixes:
  - `cd backend && uv run pytest`
  - Result: **1833 passed, 2 skipped, 1 failed**.
  - The failure is the unrelated existing `tests/test_profile.py::test_client_dashboard_subscription_includes_service_icon`; it fails while constructing `CurrencyMeta` from an unconfigured `AsyncMock` currency query. No files involved in this task are referenced in the failure.
- Full worker suite after the review fixes:
  - `cd worker && uv run pytest -q`
  - Result: **145 passed**.

## Files Changed

- `backend/app/core/lookup_executor_protocol.py`
- `backend/app/services/lookup_executor_transport/http.py`
- `backend/app/services/lookup_executor_transport/url_safety.py`
- `backend/tests/test_lookup_executor_transport.py`
- `worker/app/main.py`
- `worker/app/protocol/crypto.py`
- `worker/tests/test_response_signing.py`
- `docs/adr/0006-external-mail-lookup-executors.md`
- This report

## Review Fixes

- Replaced the DNS TOCTOU window with a custom HTTPX/httpcore transport that connects to the first public address from the immediately preceding validation while retaining the configured hostname for HTTPS SNI and certificate verification.
- Added HMAC-signed executor response headers and backend verification for challenge and handoff responses, including identity, key version, timestamp, nonce, body, and canonical path checks. The worker now signs successful and protocol-error responses.
- Made `202` acceptance require an explicit lease ID matching the requested lease.
- Made `409` duplicate handling require explicit duplicate evidence plus a matching response lease; ambiguous or conflicting responses become `protocol_error`.
- Added tests covering all handoff statuses, response authentication, URL path/query rejection, and DNS rebinding.
- Updated the worker duplicate response to include explicit duplicate evidence and the active lease ID.
- Documented pinned connections, signed responses, and strict executor URL forms in ADR 0006.

## Self-Review

- The pinned transport keeps the URL hostname in the HTTP request, so TLS hostname verification and SNI are not replaced by the validated IP.
- Redirects remain disabled, and a new validation plus pinned connection is used for each request.
- Response signatures cover the exact response bytes and fixed endpoint path; malformed, stale, wrong-identity, and unsigned responses cannot produce accepted capabilities or leases.
- Handoff network failures remain `transport_error`; response-authentication failures are `security_error`.
- Existing protocol compatibility vectors remain unchanged.

## Concerns

- The full backend suite retains one unrelated pre-existing `test_profile.py` failure described above.
- The pinned transport uses the stable httpcore transport interfaces exposed through the installed httpx dependency; an httpx major-version upgrade should rerun the focused transport and TLS integration tests.

## Prior Commit

- `ef59469 feat(backend): add executor protocol transport`

## Review Round 2 Fix Report

### Implemented

- Moved challenge response signature verification before `raise_for_status()`. Unsigned or malformed error responses now fail as invalid authenticated challenges instead of being trusted as HTTP errors.
- Changed `409` duplicate handling to require `duplicate: true` explicitly and retain matching lease-ID validation. Text in `detail` is no longer accepted as duplicate evidence.
- Updated transport tests so the DNS-rebinding test uses the default pinned transport path, and added coverage proving each validated request constructs the pinned transport with the validated address. The redirect fixture is signed so the test reaches the no-follow status assertion without bypassing response authentication.

### Tests

- RED verification after adding the review tests:
  - `cd backend && uv run pytest tests/test_lookup_executor_transport.py -q`
  - Expected failures: challenge error authentication ordering and ambiguous duplicate text acceptance.
- Focused suite:
  - `cd backend && uv run pytest tests/test_lookup_executor_protocol.py tests/test_lookup_executor_transport.py -v`
  - Result: **32 passed**.
- Static validation:
  - `cd backend && uv run ruff check app/services/lookup_executor_transport/http.py tests/test_lookup_executor_transport.py` — passed.
  - `cd backend && uv run ruff format --check app/services/lookup_executor_transport/http.py tests/test_lookup_executor_transport.py` — passed.
- Full backend suite:
  - `cd backend && uv run pytest`
  - Result: **1836 passed, 2 skipped, 1 failed**. The sole failure is the unrelated existing `tests/test_profile.py::test_client_dashboard_subscription_includes_service_icon` AsyncMock currency-query setup failure.

### Files changed in this round

- `backend/app/services/lookup_executor_transport/http.py`
- `backend/tests/test_lookup_executor_transport.py`
- This report

### Self-review and concerns

- All three re-review findings are addressed: error responses are authenticated before status handling, duplicate text is insufficient without `duplicate: true`, and the DNS test no longer injects a transport into the code path under test.
- The existing unrelated full-suite profile failure remains the only concern.

## Review Round 3 Fix Report

### Implemented

- Replaced the DNS pinning test's `_PinnedAsyncHTTPTransport` factory with a test of the real `_PinnedAsyncHTTPTransport` class.
- The test stubs only the underlying httpcore connection pool and network backend, then verifies that the real pinned transport connects to the validated IP.
- The test verifies that the httpcore request retains `executor.example.test` as its hostname for TLS SNI and certificate verification.
- The test configures a different pinned address and verifies that connection attempts raise `httpx.ConnectError` rather than silently connecting to the allowed address.

### Tests

- Focused transport suite:
  - `cd backend && uv run pytest tests/test_lookup_executor_transport.py -q`
  - Result: **28 passed**.
- Focused protocol and transport suite:
  - `cd backend && uv run pytest tests/test_lookup_executor_protocol.py tests/test_lookup_executor_transport.py -q`
  - Result: **32 passed**.
- Static validation:
  - `cd backend && uv run ruff check tests/test_lookup_executor_transport.py` — passed.
  - `cd backend && uv run ruff format --check tests/test_lookup_executor_transport.py` — passed.
  - `git diff --check` — passed.

### Files changed in this round

- `backend/tests/test_lookup_executor_transport.py`
- This report

### Self-review and concerns

- The reworked test no longer replaces `_PinnedAsyncHTTPTransport` with `httpx.MockTransport`; it exercises the production transport constructor and request path directly.
- The hostname assertion is made on the generated httpcore request, which is the hostname consumed by the HTTPS connection layer for SNI and certificate validation, while the backend assertion independently checks the TCP destination.
- No production code changes were necessary because the existing implementation already pins the validated address and retains the request hostname.
- The pre-existing unrelated full-backend profile test failure recorded above remains the only known suite-level concern.
