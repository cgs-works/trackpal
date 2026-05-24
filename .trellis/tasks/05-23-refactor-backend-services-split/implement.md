# Implementation plan — Backend modular refactor

## Phase 0 — Task tree setup

- [ ] Create child tasks under parent:
  - [ ] `core-schemas-modularization`
  - [ ] `repositories-migration`
  - [ ] `services-modularization`
  - [ ] `api-modularization`
  - [ ] `whatsapp-services-split`
- [ ] Write dependency notes inside each child artifact (not implicit by tree)

## Phase 1 — Core + Schemas (first, low-risk)

- [ ] Split oversized `core/*` and `schemas/*` files into packages/modules
- [ ] Keep public API stable through `__init__` re-exports
- [ ] Enforce LoC threshold (`<=200`, max `240` with debt note)
- [ ] Run targeted tests touching validation/i18n/redis/subscription schemas

## Phase 2 — Repositories migration

- [ ] Create `app/repositories/` domain repos
- [ ] Move `app/crud/users.py` logic into repositories
- [ ] Extract direct SQL queries from `services/` and `api/dependencies.py` into repositories
- [ ] Add temporary shim in `app/crud/__init__.py`
- [ ] Update imports incrementally
- [ ] Run auth/tenant/client tests

## Phase 3 — Services modularization

- [ ] Convert oversized service files to package-per-service layout
- [ ] Split by concern: orchestration, validators, query adapters, flow handlers
- [ ] Keep service public methods/behavior stable
- [ ] Run service-domain tests per module moved

## Phase 4 — API modularization

- [ ] Split oversized endpoint modules into domain submodules
- [ ] Keep routes, methods, response models, status codes stable
- [ ] Run API endpoint tests and smoke HTTP paths

## Phase 5 — WhatsApp heavy split

- [ ] Deep split `whatsapp_tenant_console_service.py`
- [ ] Deep split `whatsapp_console_service.py`
- [ ] Split related facade/session helpers as needed
- [ ] Preserve commands, transitions, fallback, i18n outputs
- [ ] Run WhatsApp flow tests + integration checks

## Global verification gates

Run at each phase end and final end:

```bash
cd backend
uv run pytest -v
```

Suggested focused checks during work:

```bash
cd backend
uv run pytest -v -k "auth or tenant or client"
uv run pytest -v -k "subscription"
uv run pytest -v -k "console or whatsapp"
```

LoC audit command:

```bash
python - << 'PY'
import os
for root,_,files in os.walk('backend/app'):
    for f in files:
        if f.endswith('.py'):
            p=os.path.join(root,f)
            n=sum(1 for _ in open(p,encoding='utf-8'))
            if n>200:
                print(n,p)
PY
```

## Debt policy

- 201-240 LoC allowed only with explicit debt note in child task artifact.
- >240 LoC blocks phase completion.

## Definition of done

- [ ] No backend module >240 LoC
- [ ] Target achieved: near-total <=200 LoC except documented temporary debt
- [ ] No functional regressions
- [ ] Backend test suite passes
- [ ] Parent task includes final integration summary
