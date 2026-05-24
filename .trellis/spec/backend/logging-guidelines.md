# Logging Guidelines

> Logging rules observed in backend.

## Overview

Project uses Python `logging` (backend runtime) and structured helper logging in Trellis scripts (`.trellis/scripts/common/log.py`).
Primary rule: no secrets/PII in logs.

## Levels

- `INFO`: lifecycle events, startup/shutdown, normal ops summaries.
- `WARNING`: fallback paths (missing i18n key, degraded dependency path).
- `ERROR`: failed external calls, unhandled failures with context.
- `DEBUG`: temporary/local debugging only; remove before merge.

## Structured Context

When logging failures include:
- operation name
- tenant/user identifiers when safe (ids, not passwords/tokens)
- exception type/message

Avoid dumping full payload bodies with personal data.

## What to Log

- Auth/session anomalies (without credentials).
- Redis/Evolution API availability failures.
- i18n missing keys (already done in i18n engine fallback path).

## What NOT to Log

- Passwords, JWTs, refresh tokens, API keys.
- Full phone numbers if unnecessary.
- Raw request bodies containing sensitive data.

## Examples

- i18n fallback warning behavior documented in `docs/code-standard/backend-conventions.md` and implemented in `backend/app/core/i18n/engine.py`.
- Trellis script severity helper patterns in `.trellis/scripts/common/log.py`.

## Anti-patterns avoided

- `print()` debug left in production paths.
- Logging secret env vars from `app/core/config.py` values.