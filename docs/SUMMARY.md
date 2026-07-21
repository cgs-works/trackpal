# TrackPal Documentation

## Project Overview

TrackPal is a multi-tenant platform for WhatsApp-based service delivery. Master manages tenant lifecycle; Tenant admins manage clients, catalog, profile, and subscriptions. Backend is Python/FastAPI with PostgreSQL and Redis HA. Frontend is React 19 + TypeScript SPA with Zustand, TanStack Router, and Tailwind CSS.

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
| [WhatsApp Console Flow](architecture/whatsapp-console-flow.md) | Master/Tenant/Client WhatsApp console orchestration, instance-first routing, LID fallback, from_me contextual routing, Client Context Shortcut, and Blocked Clients |
| [Input Validation Policy](architecture/input-validation-policy.md) | Validation and normalization rules |
| [Evolution Integration](architecture/evolution-integration.md) | Evolution client, webhook registration, senderPn/senderLid payload contract, token encryption, and n8n relay |
| [Frontend Architecture](architecture/frontend-architecture.md) | React 19 routing, state, API integration, and views |
| [n8n Workflow](architecture/n8n-workflow.md) | WhatsApp bot bridge (LID-aware parse contract), contextual payload routing, reply_to / no_reply handling, and subscription reminders workflows |
| [Mailbox Ingestion](architecture/mailbox-ingestion.md) | Multi-OAuth + IMAP mailbox ingestion, lookup worker, metrics, cleanup |
| [Subscriptions](architecture/subscriptions.md) | Subscription data model, API, jobs, reminders, and frontend |
| [Code-Services](architecture/code-services.md) | Global activation + tenant selection governance for code-extraction services |
| [I18n System](architecture/i18n-system.md) | Backend i18n engine, catalogs, locale resolution, frontend store, WhatsApp ContextVar |
| [User Help System](architecture/user-help-system.md) | Private Markdown compiler, authenticated Help API, plan-aware manuals, contextual help, and Tenant Admin orientation tours |

## Architecture Decisions

| File | Description |
|------|-------------|
| [Markdown Capability Registry for User Help](adr/0001-markdown-capability-registry-for-user-help.md) | Canonical Markdown topic source for in-app manuals, orientation tours, and CI capability contracts |

## Codebase

| File | Description |
|------|-------------|
| [Backend Structure](codebase/backend-structure.md) | Backend directory tree, entry points, and key modules |
| [Frontend Structure](codebase/frontend-structure.md) | Frontend directory tree, entry points, and key modules |
| [Frontend Components](codebase/frontend-components.md) | Reusable panels, including Catalog CRUD with delete preview confirmation, and their responsibilities |

## Code Standard

| File | Description |
|------|-------------|
| [Backend Conventions](code-standard/backend-conventions.md) | Python conventions, testing, security, Redis, and n8n patterns |
| [Error Handling](code-standard/error-handling.md) | Error types, propagation, i18n-aware exception mapping |
| [Logging Guidelines](code-standard/logging-guidelines.md) | Log levels, structured context, secrets policy |
| [Frontend Conventions](code-standard/frontend-conventions.md) | React 19, Zustand, TanStack Router, Tailwind CSS, and i18n conventions |

## Project PDR

| File | Description |
|------|-------------|
| [Product Goals](project-pdr/product-goals.md) | Core use cases, user roles, and non-goals |
| [Business Rules](project-pdr/business-rules.md) | Lifecycle, auth, phone/LID handling, validation, and deployment constraints |
| [Public API Catalog](project-pdr/public-api-catalog.md) | Implemented Pro-only public catalog API rules, UI scope, and Cloudflare rate-limit requirement |
| [User Help Requirements](project-pdr/user-help-requirements.md) | Approved audiences, manual information architecture, tour sequences, privacy, fidelity, and release gates |
