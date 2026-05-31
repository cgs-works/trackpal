# Logging Guidelines

Logging rules observed in the backend.

## Overview

Uses Python `logging` module. Primary rule: **no secrets or PII in logs**.

## Log Levels

| Level | When |
|-------|------|
| `INFO` | Lifecycle events, startup/shutdown, normal operation summaries |
| `WARNING` | Fallback paths (missing i18n key, degraded dependency path) |
| `ERROR` | Failed external calls, unhandled failures with context |
| `DEBUG` | Temporary/local debugging only; remove before merge |

## Structured Context

When logging failures, include:
- Operation name
- Tenant/user identifiers when safe (IDs, not passwords/tokens)
- Exception type and message

Do **not** dump full payload bodies with personal data.

## What to Log

- Auth/session anomalies (without credentials).
- Redis/Evolution API availability failures.
- i18n missing keys (already done in i18n engine fallback path — logged at 1st, 10th, 100th, 1000th, and every 10000th occurrence).

## What NOT to Log

- Passwords, JWTs, refresh tokens, API keys.
- Full phone numbers if unnecessary.
- Raw request bodies containing sensitive data.
- Secret env vars from `app/core/config.py` values.

## Anti-Patterns

- `print()` debug calls left in production paths.
- Logging decrypted secrets before use (e.g., `evolution_instance_token`).
- Logging full exception tracebacks for expected `UserFacingError`.

## Related

- [Backend Conventions](backend-conventions.md)
- [Error Handling](error-handling.md)
