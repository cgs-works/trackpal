# Lookup Executor activation requires verified destination state

## Context

Lookup Executor records are created as drafts with `requires_reverification` set
false for compatibility with the initial enrollment state. Treating the flag
alone as proof of verification would therefore make a newly created draft
dispatchable when an operator enabled it without first completing a challenge.

A connectivity check also performs a protocol exchange, but it is diagnostic
only. It must not establish the explicit trust state required for activation.

An executor can be moved to a different base URL or transport mode while active
or disabled. That change replaces the destination that was previously
challenged and must not retain dispatch eligibility.

## Decision

The enable endpoint requires all of the following:

- a healthy health result;
- `requires_reverification == false`; and
- a non-null `last_verified_at` written only after a successful `/verify`
  challenge.

The `/test` endpoint records connectivity health but never writes
`last_verified_at` and therefore cannot authorize activation.

When `base_url` or `transport_mode` changes, the registry always sets
`requires_reverification` to true, clears `last_verified_at`, and records an
unknown health state. An active executor is also moved to `disabled`. A
subsequent successful challenge is required before activation. Secret rotation
follows the same challenge-before-promotion rule: a failed challenge leaves the
pending key unpromoted and quarantines the executor.

## Consequences

- Drafts cannot become dispatchable through lifecycle mutation alone.
- Connectivity checks cannot substitute for trust-establishing verification.
- Destination changes cause a deliberate dispatch interruption until verified,
  including changes made while an executor is disabled.
- Operators receive stable error codes instead of transport exception details.
- Existing credentials remain encrypted and intact while the executor is
disabled.
