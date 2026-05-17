# System Overview

Trackpal is a multi-tenant platform for managing WhatsApp-based service delivery. The backend provides REST API and WhatsApp Master Console for tenant lifecycle management.

## High-Level Architecture

```
[Cloudflare Pages] ─── [Trackpal API (Render)] ─── [PostgreSQL]
       │                        │                        │
       │                   [Redis HA]               [Alembic Migrations]
       │                        │
       │                   [Evolution API] ─── [n8n Webhook]
                                                │
                                           [WhatsApp]
```

- **Frontend**: Vue 3 + Vite SPA hosted on Cloudflare Pages
- **Backend**: Python FastAPI hosted on Render (free tier)
- **Database**: PostgreSQL with asyncpg driver, managed via Alembic
- **Redis**: Active-passive HA with circuit-breaker failover for ephemeral WhatsApp session state
- **Evolution API**: External WhatsApp Business API proxy for instance management and message relay
- **n8n**: Workflow automation connecting Evolution API webhooks to backend endpoints
- **Deployment**: `render.yaml` defines the web service with build/start commands

## Key Design Decisions

- **Async everywhere**: FastAPI + asyncpg + async Redis for non-blocking I/O
- **Multi-role auth**: Role-based JWT with access/refresh token rotation
- **Ephemeral state**: WhatsApp conversational state lives in Redis, not the database
- **Failover resilience**: Circuit-breaker pattern for Redis primary/backup; degraded replies never return HTTP 5xx to n8n
- **Input validation**: Centralized policy module used by both REST API schemas and WhatsApp console flows
- **Canonical phone format**: All phone numbers stored as digits-only (no `+` prefix, no JID suffixes)
