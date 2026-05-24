# Design — API modularization

## Scope

- `api/v1/endpoints/subscriptions.py`
- `api/v1/endpoints/integrations.py`

## Approach

- Split by resource/use-case into endpoint submodules.
- Keep router aggregation entrypoint stable.
- Move non-HTTP logic into services/repositories.

## Constraints

- Keep route paths/methods/status codes/response schemas.
- Keep auth/dependency behavior intact.
- LoC target <=200, max 240 with debt note.

## Risks

- Route registration drift.
- Hidden dependency side effects.

## Mitigations

- Snapshot route table before/after.
- Run endpoint-focused tests and smoke checks.
