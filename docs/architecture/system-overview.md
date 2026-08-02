# System Overview

TrackPal is a multi-tenant platform for managing WhatsApp-based service
delivery. The backend provides REST API and WhatsApp consoles (Master and
Tenant) for tenant lifecycle management and daily operations.

## High-Level Architecture

```text
[Cloudflare Pages] ---> [TrackPal API (Render)] <----> [Lookup Executor (worker/)]
                              |          |                    |
                         [PostgreSQL] [Redis HA]          Gmail
                              |          |                    |
                      [Alembic Migrations]              signed callback
                                         |
                              [Evolution] ---> [n8n Webhook]
                                  |                 |
                           [Cloudflare R2]       [WhatsApp]
                           (diagnostic +
                            export private)
```

- **Frontend**: React 19 + TypeScript SPA with Zustand, TanStack Router,
  and Tailwind CSS hosted on Cloudflare Pages.
- **Backend**: Python FastAPI hosted on Render. It owns authentication,
  tenant authorization, mailbox configuration, durable lookup jobs, dispatch,
  and callback reconciliation.
- **Lookup Executor**: The independently deployable Python project in
  `worker/`. It performs Gmail retrieval, MIME normalization, Code Service
  extraction, Netflix resolution, and fingerprint generation outside FastAPI.
  Render Free and Docker/VPS use the same signed HTTP protocol.
- **Database**: PostgreSQL with asyncpg driver, managed via Alembic. It is the
  durable source of truth for lookup jobs and the Master-managed executor
  registry.
- **Redis**: Active-passive HA with circuit-breaker failover. It coordinates
  dispatch acceleration, Execution Leases, executor capacity, replay nonces,
  cooldowns, and encrypted short-lived result cache entries. PostgreSQL
  reconciliation makes pending jobs recoverable after Redis state loss.
- **Evolution**: External WhatsApp Business API proxy for instance management,
  webhook registration, and message relay.
- **n8n**: WhatsApp bot bridge and subscription reminder scheduler.
- **Cloudflare R2**: Separate public diagnostic and private export buckets.

## Key Design Decisions

- **External lookup boundary**: FastAPI never opens Gmail, parses MIME,
  extracts codes, resolves Netflix URLs, or falls back to local execution. It
  sends a signed and application-encrypted command to a trusted executor and
  accepts a signed encrypted callback.
- **Master registry**: Executors are enrolled, verified, activated, disabled,
  rotated, and deleted through the Master API and UI. Adding an executor does
  not add backend environment variables. The optional hosting-account password
  is Master-only, encrypted at rest, step-up protected, and never sent to the
  executor.
- **Async everywhere**: FastAPI + asyncpg + async Redis for non-blocking I/O.
  The worker returns `202` after reserving local capacity and completes through
  the callback route.
- **Lease recovery**: Redis leases are exclusive and time-bounded. A lost
  worker task or Redis state does not create a local fallback; PostgreSQL
  durable state is reconciled and pending work can be dispatched again.
- **Multi-role auth**: Role-based JWT with access/refresh token rotation.
- **Contained Demo boundary**: Demo JWTs are restricted to authentication,
  password change, Help/i18n reads, and lifecycle heartbeat. Business data is
  browser-local. See [ADR-0004](../adr/0004-browser-local-demo-tenant-workspaces.md).
- **Ephemeral state**: WhatsApp conversational state and encrypted lookup
  results live in Redis, not PostgreSQL. Extracted lookup values are not
  persisted in the job row.
- **Subscription secrets**: Streaming credentials encrypted at rest via Fernet.
- **Failover resilience**: Circuit-breaker pattern for Redis primary/backup;
  degraded replies never return HTTP 5xx to n8n.
- **Input validation**: Centralized policy module used by REST API schemas and
  WhatsApp console flows.
- **Canonical phone format**: All phone numbers stored as digits-only.
- **I18n architecture**: Python backend is source-of-truth for translations;
  frontend fetches the merged catalog via `/i18n/catalog`.
- **Password step-up for sensitive operations**: Export, deletion, and hosting
  password reveal use the shared fail-closed limiter.
- **External-first deletion**: R2 purge and Evolution deletion run before a
  database commit; failure preserves the Tenant for safe retry.
