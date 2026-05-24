# Design — Backend modular refactor to FastAPI templates style

## Objective architecture

Apply modular package structure across `backend/app` with small modules.

Target layers:
- `api/` thin endpoints
- `services/` orchestration/business rules
- `repositories/` data access (SQLAlchemy queries)
- `schemas/` DTO contracts
- `core/` cross-cutting infra/utilities

## Size contract

- Target per module: `<=200` LoC
- Temporary hard cap: `<=240` LoC with explicit debt entry

## Structural conventions

For oversized modules, convert to package:
- `x.py` -> `x/`
  - `__init__.py` stable public surface
  - focused submodules (`commands.py`, `queries.py`, `flows.py`, `validators.py`, `types.py`, `constants.py`, etc.)

Keep public imports stable where possible using package `__init__` re-exports.

## CRUD migration decision

- Migrate `app/crud/` to `app/repositories/` now.
- Extract direct DB queries from `services/` and `api/dependencies.py` into repositories by domain.
- Add temporary compatibility shim in `app/crud/__init__.py` for phased migration.

## Execution model

Parent task coordinates. Child tasks implement independently verifiable blocks:
1. `core + schemas`
2. `repositories` migration
3. `services` modularization
4. `api` modularization
5. WhatsApp-heavy flows hard split (`whatsapp_*` services/facades)

## Compatibility and risk control

- No business-rule changes.
- No endpoint contract changes.
- Preserve response payloads and status codes.
- Preserve i18n keys and WhatsApp flow semantics.

## Validation strategy

Per child:
- targeted tests by domain
- full backend test pass at integration checkpoints
- smoke critical flows: auth, tenant/client/catalog/subscription, WhatsApp console entry paths

## Rollback

Per child task on dedicated commit boundary. If regression:
- revert child commit set
- keep previous children intact
- re-open child with narrower split
