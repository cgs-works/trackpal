# Design — core/schemas modularization

## Scope

- `backend/app/core/*`
- `backend/app/schemas/*`

## Approach

- Convert oversized files to package layout:
  - `module.py` -> `module/` + submodules (`constants`, `types`, `builders`, `validators`, etc.)
- Keep public imports stable via `__init__.py` re-exports.
- No behavior change; only structural decomposition.

## Constraints

- Preserve exception types/messages.
- Preserve validation and i18n contract surfaces.
- LoC target <=200, max 240 with debt note.

## Risks

- Circular imports after split.
- Hidden import path coupling in services/tests.

## Mitigations

- Incremental split per file.
- Run targeted tests per moved module.
- Add temporary compatibility exports if needed.
