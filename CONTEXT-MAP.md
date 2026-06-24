# Context Map

Trackpal es un multi-context project. Cada contexto tiene su propio `CONTEXT.md` con vocabulario de dominio, decisiones arquitectónicas y convenciones específicas.

## Contexts

| Contexto | Path | Stack | Descripción |
|----------|------|-------|-------------|
| **Backend** | `backend/CONTEXT.md` | Python 3.12, FastAPI, SQLAlchemy async, PostgreSQL, Redis HA | API REST, WhatsApp consoles, mailbox ingestion, subscription jobs |
| **Frontend** | `frontend/CONTEXT.md` | React 19, TypeScript, Zustand, TanStack Router, Tailwind v4, shadcn/ui | SPA multi-role (Master, Tenant, Client) |
| **n8n** | `n8n/CONTEXT.md` | n8n workflows (JSON exports) | WhatsApp bot bridge + subscription reminder scheduler |

## Reglas de consumo

1. Lee `CONTEXT-MAP.md` primero para entender la estructura.
2. Lee el `CONTEXT.md` del contexto relevante para tu tarea.
3. Si la tarea toca múltiples contextos, lee todos los relevantes.
4. La documentación transversal vive en `docs/` (architecture, code-standard, project-pdr).
