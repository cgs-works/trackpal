# Design — services modularization

## Scope

Non-WhatsApp oversized services:
- `subscription_service.py`
- `subscription_job_service.py`
- `client_service.py`
- `tenant_service.py`
- `whatsapp_auth_session_service.py`

## Approach

- Convert each service into package:
  - orchestration/service API
  - validators
  - command handlers
  - query adapters (repo calls)
  - mapping/format helpers
- Keep class/method public contract stable.

## Constraints

- Preserve business rules and side effects.
- Repository access centralized via `app/repositories`.
- LoC target <=200, max 240 with debt note.

## Risks

- Hidden shared state/helpers split incorrectly.
- Transaction boundary drift.

## Mitigations

- Keep commit/rollback points in orchestration module.
- Test each service split before next.
