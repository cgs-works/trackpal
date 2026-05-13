# Project Documentation

## Architecture

| File | Description |
|---|---|
| [api-routes.md](architecture/api-routes.md) | All API endpoints with methods, paths, and auth |
| [data-flow.md](architecture/data-flow.md) | System interaction diagrams (auth, n8n, deactivation, Redis HA) |
| [n8n-workflow.md](architecture/n8n-workflow.md) | WhatsApp bot workflow configuration (transport-only) |

## Codebase

| File | Description |
|---|---|
| [backend.md](codebase/backend.md) | Backend structure, key modules, services, tests, Redis HA |
| [frontend.md](codebase/frontend.md) | Frontend structure, routes, auth store, API service |

## PRDs (Product Requirements Documents)

| File | Description |
|---|---|
| [Scaffolding MVP](prds/260511-1706-scaffolding-mvp/PRD.md) | Initial project scaffolding and MVP definition |
| [WhatsApp Master Console](prds/260512-0143-whatsapp-master-console/PRD.md) | Backend-driven Master Console via WhatsApp |
| [Redis Session HA](prds/260512-2005-redis-session-ha/PRD.md) | Redis high-availability for WhatsApp Master Console |
| [Input Validation Policy](prds/260513-1049-input-validation-policy/PRD.md) | Centralized backend-owned validation for identity/contact fields |

## Plans (Archived)

| File | Description |
|---|---|
| [Scaffolding MVP — Plan](plans/archived/260511-1706-scaffolding-mvp/SUMMARY.md) | 9-phase implementation plan |
| [WhatsApp Master Console — Plan](plans/archived/260512-0143-whatsapp-master-console/SUMMARY.md) | 8-phase execution plan and EXECUTION-REPORT |
| [Redis Session HA — Plan](plans/archived/260512-2005-redis-session-ha/SUMMARY.md) | 6-phase execution plan and EXECUTION-REPORT |
| [Input Validation Policy — Plan](plans/archived/260513-1049-input-validation-policy/SUMMARY.md) | 6-phase execution plan and EXECUTION-REPORT |

## ADRs (Architecture Decision Records)

See [docs/adr/](/docs/adr/) directory. Managed separately.

## Operations

| File | Description |
|---|---|
| [deployment.md](deployment.md) | Deployment guide for Render and Cloudflare Pages |
