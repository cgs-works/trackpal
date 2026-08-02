# Task 1 Implementation Report

## What I implemented

Created the standalone `worker/` Python project without any imports from `backend/`.

- Added lockable project metadata and the requested runtime and development dependencies in `worker/pyproject.toml`.
- Generated `worker/uv.lock`; the lock contains the worker project and its dependencies only, with no `backend` package.
- Added protocol models:
  - Frozen `ProtocolKeys` dataclass with separate signing and encryption keys.
  - Strict `EncryptedBody` Pydantic model.
- Added protocol cryptography:
  - Deterministic HKDF-SHA256 derivation using separate v1 salt/info values for signing and encryption.
  - AES-GCM encryption with fresh 12-byte nonces and base64 transport fields.
  - JSON object decryption with authentication/tamper rejection.
  - Canonical newline-delimited HMAC-SHA256 request signing and constant-time verification.
  - Timestamp skew validation.
- Added bounded TTL-based `NonceCache` replay protection.
- Added `ExecutorSettings` with required `TRACKPAL_EXECUTOR_ID` and `TRACKPAL_EXECUTOR_SECRET`, default concurrency of 1, and positive-concurrency validation.
- Added protocol and configuration tests with literal signature and body-hash fixtures.

## Testing and results

Final verification:

```text
cd worker && uv run pytest -v
10 passed in 0.12s

cd worker && uv run ruff check app tests
All checks passed!

cd worker && uv run ruff format --check app tests
8 files already formatted

cd worker && uv run --with mypy mypy --strict app
Success: no issues found in 6 source files
```

Dependency verification:

```text
cd worker && uv lock --check
Resolved 43 packages in 1ms
```

## TDD Evidence

### RED

Command:

```text
cd worker && uv lock && uv run pytest tests/test_protocol.py tests/test_config.py -v
```

Relevant failure before implementation:

```text
collected 0 items / 2 errors
ModuleNotFoundError: No module named 'app'
```

This was the expected pre-implementation collection failure because the standalone `app` package and its protocol/config modules did not yet exist. The worker project was then given a local pytest `pythonpath` configuration so the requested `app.*` imports resolve when running from `worker/`.

### GREEN

After implementing the modules, the focused suite passed:

```text
cd worker && uv run pytest tests/test_protocol.py tests/test_config.py -v
10 passed in 0.11s
```

The final full suite and lint/format checks are recorded above.

## Files changed

- `worker/pyproject.toml`
- `worker/uv.lock`
- `worker/app/__init__.py`
- `worker/app/config.py`
- `worker/app/protocol/__init__.py`
- `worker/app/protocol/models.py`
- `worker/app/protocol/crypto.py`
- `worker/app/protocol/replay.py`
- `worker/tests/test_protocol.py`
- `worker/tests/test_config.py`

## Self-review findings

- Verified the worker imports only its own `app` package and does not import `backend`.
- Verified deterministic key derivation and signing/encryption key separation.
- Verified AES-GCM tamper rejection, canonical signature compatibility, timestamp rejection, nonce replay rejection, TTL expiry, and bounded cache behavior.
- Verified required settings, default concurrency, and invalid concurrency rejection.
- An initial implementation attempted to generate a nonce through `AESGCM.generate_key(bit_length=96)`; the focused test exposed that AES-GCM key generation only accepts AES key sizes. It was corrected to use `os.urandom(12)` before final verification.
- No remaining issues or concerns identified.

## Commit

`ee5ff16 feat(worker): add signed executor protocol`

## Fix Report: Replay Cache Capacity Review

### What I changed

- Updated `NonceCache.consume` to reject a new nonce when the cache is at capacity after purging expired entries, instead of evicting a still-valid nonce.
- Updated `worker/tests/test_protocol.py` to verify that a full cache rejects the new nonce, preserves both valid existing nonces against replay, and accepts a nonce after its TTL expires.

### Covering tests

Command:

```text
cd worker && uv run pytest tests/test_protocol.py tests/test_config.py -v && uv run ruff check app tests
```

Output:

```text
============================= test session starts =============================
collected 10 items

10 passed in 0.12s

All checks passed!
```
