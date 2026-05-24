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

## Anti-patterns avoided

- Fat single-file services in `app/services/` root.
- SQL directly inside API endpoint handlers.
- Cross-layer shortcuts (`api` importing `repositories` directly for business rules).