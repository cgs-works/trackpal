# System Overview

Trackpal is a multi-tenant platform for managing WhatsApp-based service delivery. The backend provides REST API and WhatsApp consoles (Master and Tenant) for tenant lifecycle management and daily operations.

## High-Level Architecture

```
[Cloudflare Pages] ---> [Trackpal API (Render)] ---> [PostgreSQL]
      |                      |                        |
      |                 [Redis HA]             [Alembic Migrations]
      |                      |
      |                 [Evolution API] ---> [n8n Webhook]
                                         |
                                     [WhatsApp]
```

- **Frontend**: Vue 3 + Vite SPA hosted on Cloudflare Pages
- **Backend**: Python FastAPI hosted on Render (free tier)
- **Database**: PostgreSQL with asyncpg driver, managed via Alembic
- **Redis**: Active-passive HA with circuit-breaker failover for ephemeral WhatsApp session state (Master + Tenant consoles)
- **Evolution API**: External WhatsApp Business API proxy for instance management and message relay
- **n8n**: Dual workflow automation - WhatsApp bot webhook bridge + subscription reminder scheduler
- **WhatsApp Tenant Console**: Phone-based conversational interface for tenant admins (clients, catalog, profile, subscriptions)
- **I18n System**: Python-centered localization with in-memory catalogs (`en`/`es`), English default and fallback, tenant locale persisted in DB, frontend catalog served via REST API
- **Deployment**: `render.yaml` defines the web service with build/start commands

## Key Design Decisions

- **Async everywhere**: FastAPI + asyncpg + async Redis for non-blocking I/O
- **Multi-role auth**: Role-based JWT with access/refresh token rotation
- **Ephemeral state**: WhatsApp conversational state (Master + Tenant) lives in Redis, not the database
- **Subscription secrets**: Streaming credentials encrypted at rest via Fernet symmetric key
- **Failover resilience**: Circuit-breaker pattern for Redis primary/backup; degraded replies never return HTTP 5xx to n8n
- **Input validation**: Centralized policy module used by REST API schemas and WhatsApp console flows
- **Canonical phone format**: All phone numbers stored as digits-only (no `+` prefix, no JID suffixes)
- **I18n architecture**: Python backend is source-of-truth for all translations; backend i18n engine at `app/core/i18n.py` with `t(locale, key)`; `UserFacingError` with `translate_error()` for API error localization; WhatsApp console uses `ContextVar`-based per-message locale; frontend fetches merged catalog via `/i18n/catalog`; n8n is pure transport (no translation logic)
