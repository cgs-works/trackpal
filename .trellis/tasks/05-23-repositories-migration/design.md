# Design — repositories migration

## Scope

- Create `backend/app/repositories/`
- Migrate `app/crud/users.py`
- Extract direct queries from services/api dependencies

## Architecture

- Repository per domain (`users`, `tenants`, `clients`, `catalog`, `subscriptions`, `sessions`).
- Services call repositories; endpoints stay thin.
- Temporary shim: `app/crud` re-exporting repository adapters until imports fully moved.

## Constraints

- No behavior or auth/tenant scoping change.
- Keep transaction boundaries in services.
- LoC target <=200, max 240 with debt note.

## Risks

- Query semantics drift during extraction.
- Over-fragmentation with poor ownership.

## Mitigations

- Move query blocks with tests green each domain.
- Keep repository methods explicit and domain-named.
