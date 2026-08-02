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
- Added tests covering all handoff statuses, inconsistent acceptance leases, ambiguous duplicates, response authentication, URL path/query rejection, and DNS rebinding.
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
