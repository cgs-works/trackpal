# System Overview

TrackPal is a multi-tenant platform for managing WhatsApp-based service delivery. The backend provides REST API and WhatsApp consoles (Master and Tenant) for tenant lifecycle management and daily operations.

## High-Level Architecture

```
[Cloudflare Pages] ---> [TrackPal API (Render)] ---> [PostgreSQL]
      |                      |                        |
      |                 [Redis HA]             [Alembic Migrations]
      |                      |
      |                 [Evolution] ---> [n8n Webhook]
      |                      |            |
      |                 [Cloudflare R2]  [WhatsApp]
      |                 (diagnostic +
      |                  export private)
```

- **Frontend**: React 19 + TypeScript SPA with Zustand, TanStack Router, Tailwind CSS hosted on Cloudflare Pages
- **Backend**: Python FastAPI hosted on Render (free tier)
- **Database**: PostgreSQL with asyncpg driver, managed via Alembic
- **Redis**: Active-passive HA with circuit-breaker failover for ephemeral WhatsApp session state (Master + Tenant consoles)
- **Evolution**: External WhatsApp Business API proxy for instance management, webhook registration, and message relay. The deployed server may run Evolution API v2.x (Node/Express) or Evolution Go (Go/Gin); both expose compatible REST contracts.
- **n8n**: Dual workflow automation - WhatsApp bot webhook bridge + subscription reminder scheduler
- **WhatsApp Tenant Console**: Phone-based conversational interface for tenant admins (clients, catalog, profile, subscriptions, Client Context Shortcut for remote management)
- **WhatsApp Self-Linking**: Web-based self-service pairing (via 8-digit code or QR code scanning) for tenant admins (both Starter and Pro) to link WhatsApp to their Evolution instance without Master intervention
- **Client Messaging Blocks**: Tenant-scoped blocks preventing unregistered WhatsApp identities from using the console or code lookup
- **Demo Tenant evaluations**: Master-managed, non-extendable 48-hour Starter or Pro evaluations. The backend persists only identity and lifecycle state; each browser stores an isolated, versioned Demo Workspace for business data and simulator state.
- **I18n System**: Python-centered localization with in-memory catalogs (`en`/`es`), English default and fallback, tenant locale persisted in DB, frontend catalog served via REST API
- **Deployment**: `render.yaml` defines the web service with build/start commands

## Key Design Decisions

- **Async everywhere**: FastAPI + asyncpg + async Redis for non-blocking I/O
- **Multi-role auth**: Role-based JWT with access/refresh token rotation
- **Contained Demo boundary**: Demo JWTs are restricted to authentication, password change, Help/i18n reads, and lifecycle heartbeat. All Demo business operations use browser-local adapters, while backend guardrails reject direct persistence or provider access. See [ADR-0004](../adr/0004-browser-local-demo-tenant-workspaces.md).
- **Ephemeral state**: WhatsApp conversational state (Master + Tenant) lives in Redis, not the database
- **Subscription secrets**: Streaming credentials encrypted at rest via Fernet symmetric key
- **Failover resilience**: Circuit-breaker pattern for Redis primary/backup; degraded replies never return HTTP 5xx to n8n
- **Input validation**: Centralized policy module used by REST API schemas and WhatsApp console flows
- **Canonical phone format**: All phone numbers stored as digits-only (no `+` prefix, no JID suffixes)
- **I18n architecture**: Python backend is source-of-truth for all translations; backend i18n engine at `app/core/i18n/` with `t(locale, key)`; `UserFacingError` with `translate_error()` for API error localization; WhatsApp console uses `ContextVar`-based per-message locale; frontend fetches merged catalog via `/i18n/catalog`; n8n is pure transport (no translation logic)
- **Isolated storage boundaries**: Cloudflare R2 split into public diagnostic bucket (`trackpal-debug`) and private export bucket (`trackpal-exports-private`) — never sharing credentials or public URLs
- **Password step-up for sensitive operations**: Export generation and Tenant Deletion require current password re-entry with a shared three-attempt/fifteen-minute rate limiter; fails closed when Redis HA is unavailable
- **External-first deletion**: R2 purge and Evolution deletion run before database commit; failure preserves the Tenant for safe retry
- **Fail-closed cleanup**: Export and deletion operations fail closed when external resources cannot be confirmed as cleaned up; no partial deletion without explanation
