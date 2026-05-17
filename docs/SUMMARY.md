# Trackpal Documentation

## Project Overview

Trackpal is a multi-tenant platform for managing WhatsApp-based service delivery. The Master operator manages tenant lifecycle through a WhatsApp chatbot console and a web dashboard. The backend is Python/FastAPI with PostgreSQL and Redis HA. The frontend is a Vue 3 SPA hosted on Cloudflare Pages.

## Architecture

| File | Description |
|------|-------------|
| [System Overview](architecture/system-overview.md) | High-level architecture, key decisions, and component relationships |
| [API Layer](architecture/api-layer.md) | REST API endpoints, routing, authentication, and dependencies |
| [Database Schema](architecture/database-schema.md) | SQLAlchemy models, relationships, constraints, and migrations |
| [Redis HA](architecture/redis-ha.md) | Active-passive Redis failover with circuit-breaker, session services |
| [WhatsApp Console Flow](architecture/whatsapp-console-flow.md) | Conversational flow for Master Console auth and CRUD operations |
| [Input Validation Policy](architecture/input-validation-policy.md) | Centralized field validation and normalization rules |
| [Evolution Integration](architecture/evolution-integration.md) | Evolution API client for instance management and chat control |
| [Frontend Architecture](architecture/frontend-architecture.md) | Vue 3 SPA structure, routing, auth flow, state management, API integration |
| [n8n Workflow](architecture/n8n-workflow.md) | n8n automation: webhook, parsing, backend call, Evolution relay |

## Codebase

| File | Description |
|------|-------------|
| [Backend Structure](codebase/backend-structure.md) | Full directory tree, entry points, and module responsibilities |
| [Frontend Structure](codebase/frontend-structure.md) | Frontend directory tree, file responsibilities, entry points, dependencies |

## Code Standard

| File | Description |
|------|-------------|
| [Backend Conventions](code-standard/backend-conventions.md) | Python conventions, naming, testing, DI, security, and Redis key schema |
| [Frontend Conventions](code-standard/frontend-conventions.md) | Vue 3 patterns, naming rules, component conventions, API patterns, styling |

## Project PDR

| File | Description |
|------|-------------|
| [Product Goals](project-pdr/product-goals.md) | Core use cases, user roles, and non-goals |
| [Business Rules](project-pdr/business-rules.md) | Tenant lifecycle, auth constraints, phone handling, validation rules, deployment constraints |

## Other

| File | Description |
|------|-------------|
| [Plans](plans/260517-1537-tenant-catalog-rls/SUMMARY.md) | Recent execution plans and reports |
| [Brainstorms](brainstorms/260517-1543-tenant-catalog-rls/SUMMARY.md) | Design brainstorms and research |
