# Lookup Executor activation requires verified destination state

## Context

Lookup Executor records are created as drafts with `requires_reverification` set
false for compatibility with the initial enrollment state. Dispatch selection
also requires an active lifecycle and a false reverification flag. Treating the
flag alone as proof of verification would therefore make a newly created draft
dispatchable when an operator enabled it without first completing a challenge.

An active executor can also be moved to a different base URL or transport mode.
That change replaces the destination that was previously challenged and must not
retain dispatch eligibility.

## Decision

The enable endpoint requires both a healthy verification result and
`requires_reverification == false`; otherwise it returns
`executor_requires_verification` and leaves the lifecycle unchanged.

When `base_url` or `transport_mode` changes on an active executor, the registry
sets `requires_reverification` to true, records an unknown health state, and
moves the executor to `disabled`. A subsequent successful challenge is required
before activation. Secret rotation follows the same challenge-before-promotion
rule: a failed challenge leaves the pending key unpromoted and quarantines the
executor.

## Consequences

- Drafts cannot become dispatchable through lifecycle mutation alone.
- Destination changes cause a deliberate dispatch interruption until verified.
- Operators receive stable error codes instead of transport exception details.
- Existing credentials remain encrypted and intact while the executor is
  disabled.
