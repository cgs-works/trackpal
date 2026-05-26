# Directory Structure

> Backend layout used in Trackpal.

## Overview

FastAPI layered layout with package-per-domain splits.
Current direction: `api -> services -> repositories -> models`.
`core` shared infra/helpers. `schemas` request/response contracts.

## Directory Layout

```text
backend/app/
├── api/
│   ├── dependencies.py
│   └── v1/
│       ├── router.py
│       └── endpoints/
│           ├── auth.py
│           ├── clients.py
│           ├── tenants.py
│           ├── catalog.py
│           ├── dashboard.py
│           ├── me.py
│           ├── i18n.py
│           ├── subscriptions/
│           └── integrations/
├── core/
│   ├── config.py
│   ├── database.py
│   ├── errors.py
│   ├── i18n/
│   ├── input_validation/
│   └── redis_client/
├── models/
├── repositories/
├── schemas/
│   └── subscription/
└── services/
    ├── __init__.py
    └── <service_package>/
```

## Module Organization

- Endpoints thin: HTTP mapping, auth deps, status codes.
- Business rules in `services/*`.
- SQLAlchemy query/data access in `repositories/*`.
- Shared validators in `core/input_validation/*`.
- Large domains split into focused modules (`service.py`, `queries.py`, `mutations.py`, `flow` modules).

## Naming Conventions

- Python files: `snake_case.py`.
- Service packages end with `_service` or domain/facade name.
- Main exported entry usually `service.py` or `facade.py`.
- Package `__init__.py` re-exports public API for stable imports.

## Examples

- Endpoint package split: `backend/app/api/v1/endpoints/subscriptions/router.py`, `crud.py`, `jobs.py`.
- Service package split: `backend/app/services/tenant_service/{queries.py,mutations.py,lifecycle.py}`.
- WhatsApp domain split: `backend/app/services/whatsapp_tenant_console_service/*`.
- Core infra split: `backend/app/core/redis_client/{manager.py,lifespan.py,policy.py}`.

## Convention: Service single-file → package when >240 LoC

Services that start as a single file (`dashboard_service.py`) must be converted to a package (`dashboard_service/__init__.py`) when:
- LoC exceeds 240, or
- They gain multiple responsibilities that should be split into focused modules (`queries.py`, `mutations.py`, `facade.py`, etc.).

**Why**: Python resolves `app.services.dashboard_service` identically whether it is a module or a package `__init__.py`. Converting is transparent to all importers — no import paths change.

**Pattern**:
- Create directory `app/services/{name}/`.
- Move class into `__init__.py`.
- Delete `{name}.py`.
- Add splitting modules as needed later.

**Example** (dashboard):
```
# Before
app/services/dashboard_service.py  # ~250 LoC

# After (imports unchanged)
app/services/dashboard_service/
├── __init__.py  # DashboardService class, ~198 LoC
# Future: queries.py, helpers.py, etc.
```

## Anti-patterns avoided

- Fat single-file services in `app/services/` root.
- SQL directly inside API endpoint handlers.
- Cross-layer shortcuts (`api` importing `repositories` directly for business rules).