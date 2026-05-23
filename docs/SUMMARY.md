# Trackpal Documentation

## Project Overview

Trackpal is a multi-tenant platform for WhatsApp-based service delivery. Master manages tenant lifecycle; Tenant admins manage clients, catalog, profile, and subscriptions. Backend is Python/FastAPI with PostgreSQL and Redis HA. Frontend is Vue 3 SPA.

## Agent Context Guide

1. Read `docs/SUMMARY.md` first when it exists
2. Load only task-relevant detail docs
3. Prioritize `Code Standard` docs for implementation conventions
4. Use the available input/question before broad changes when docs conflict with code or user intent

## Architecture

| File | Description |
|------|-------------|
| [System Overview](architecture/system-overview.md) | High-level architecture, component relationships, and key decisions |
| [API Layer](architecture/api-layer.md) | REST routes, auth, dependencies, and integrations |
| [Database Schema](architecture/database-schema.md) | ORM models, relationships, constraints, and migrations |
| [Redis HA](architecture/redis-ha.md) | Redis failover, session state, and contingency replies |
| [WhatsApp Console Flow](architecture/whatsapp-console-flow.md) | Master and Tenant WhatsApp console orchestration and menus |
| [Input Validation Policy](architecture/input-validation-policy.md) | Validation and normalization rules |
| [Evolution Integration](architecture/evolution-integration.md) | Evolution API client, instance lifecycle, and chat control |
| [Frontend Architecture](architecture/frontend-architecture.md) | Vue routing, state, API integration, and views |
| [n8n Workflow](architecture/n8n-workflow.md) | WhatsApp bot bridge and subscription reminders workflows |
| [Subscriptions](architecture/subscriptions.md) | Subscription data model, API, jobs, reminders, and frontend |
| [I18n System](architecture/i18n-system.md) | Backend i18n engine, catalogs, locale resolution, frontend store, WhatsApp ContextVar |

## Codebase

| File | Description |
|------|-------------|
| [Backend Structure](codebase/backend-structure.md) | Backend directory tree, entry points, and key modules |
| [Frontend Structure](codebase/frontend-structure.md) | Frontend directory tree, entry points, and key modules |

## Code Standard

| File | Description |
|------|-------------|
| [Backend Conventions](code-standard/backend-conventions.md) | Python conventions, testing, security, Redis, and n8n patterns |
| [Frontend Conventions](code-standard/frontend-conventions.md) | Vue 3, Pinia, routing, API, i18n store, and styling conventions |

## Project PDR

| File | Description |
|------|-------------|
| [Product Goals](project-pdr/product-goals.md) | Core use cases, user roles, and non-goals |
| [Business Rules](project-pdr/business-rules.md) | Lifecycle, auth, phone handling, validation, and deployment constraints |

## Other

| File | Description |
|------|-------------|
| [Tenant Catalog Plan](plans/260517-1537-tenant-catalog-rls/SUMMARY.md) | Tenant catalog and RLS plan |
| [Client Entity Plan](plans/260517-1938-client-entity-dashboard/SUMMARY.md) | Client entity and dashboard plan |
| [Tenant Admin WhatsApp Console Plan](plans/260518-2146-tenant-admin-whatsapp-console/SUMMARY.md) | Tenant WhatsApp console implementation plan |
| [Tenant Catalog Brainstorm](brainstorms/260517-1543-tenant-catalog-rls/SUMMARY.md) | Catalog RLS brainstorm summary |
| [Client Entity Brainstorm](brainstorms/260517-1930-client-entity-dashboard/SUMMARY.md) | Client entity brainstorm summary |
| [Tenant Admin WhatsApp Console Brainstorm](brainstorms/260518-2146-tenant-admin-whatsapp-console/SUMMARY.md) | Tenant WhatsApp console brainstorm summary |
