# Domain Docs

Cómo las skills de ingeniería consumen la documentación de dominio de este repo.

## Antes de explorar, lee esto

- **`CONTEXT-MAP.md`** en la raíz — apunta a un `CONTEXT.md` por contexto (backend, frontend, n8n). Lee cada uno relevante para el tema.
- **`docs/adr/`** — lee ADRs que toquen el área en la que vas a trabajar. En contextos específicos, también verifica `src/<context>/docs/adr/` si existe.

Si alguno de estos archivos no existe, **procede sin avisar**. No reportes su ausencia; no sugieras crearlos de entrada. La skill `/domain-modeling` los crea lazy cuando se resuelven términos o decisiones.

## Estructura multi-context

```
/
├── CONTEXT-MAP.md           ← mapa de contexts (entry point)
├── docs/adr/                ← decisiones del sistema completo
├── docs/
│   ├── architecture/        ← documentación arquitectónica existente
│   ├── codebase/            ← estructura de código
│   ├── code-standard/       ← convenciones de código
│   └── project-pdr/         ← reglas de negocio y goals
└── src/ o dirs equivalentes
    ├── backend/             ← Python FastAPI
    │   ├── CONTEXT.md
    │   └── docs/adr/
    ├── frontend/            ← React 19 + TypeScript
    │   ├── CONTEXT.md
    │   └── docs/adr/
    └── n8n/                 ← Workflows de automatización
        ├── CONTEXT.md
        └── docs/adr/
```

## Contextos del proyecto

| Contexto | Stack | Directorio |
|----------|-------|------------|
| **Backend** | Python 3.12, FastAPI, SQLAlchemy async, PostgreSQL, Redis HA, Alembic | `backend/` |
| **Frontend** | React 19, TypeScript, Zustand, TanStack Router, Tailwind v4, shadcn/ui | `frontend/` |
| **n8n** | Workflows JSON (WhatsApp bot + subscription reminders) | `n8n/` |

## Documentación existente

El repo ya tiene documentación sustancial en `docs/`:

- `docs/architecture/` — 13 archivos: system-overview, api-layer, database-schema, redis-ha, whatsapp-console-flow, evolution-integration, frontend-architecture, n8n-workflow, mailbox-ingestion, subscriptions, code-services, i18n-system, input-validation-policy
- `docs/codebase/` — 3 archivos: backend-structure, frontend-structure, frontend-components
- `docs/code-standard/` — 4 archivos: backend-conventions, frontend-conventions, error-handling, logging-guidelines
- `docs/project-pdr/` — 2 archivos: product-goals, business-rules

Lee `docs/SUMMARY.md` como entry point antes de asumir arquitectura.

## Usa el vocabulario del glossario

Cuando tu output nombre un concepto de dominio (título de issue, propuesta de refactor, hipótesis, nombre de test), usa el término tal como está definido en la documentación del proyecto. No cambies a sinónimos que el glossario evita explícitamente.

Si el concepto que necesitas no está en el glossario aún, es una señal — o estás inventando lenguaje que el proyecto no usa (reconsidera), o hay un gap real (anótalo para `/domain-modeling`).

## Flaggea conflictos con decisiones existentes

Si tu output contradice un ADR o una decisión documentada en `docs/architecture/`, levántalo explícitamente en vez de silenciarlo:

> _Contradice system-overview.md (async everywhere) — pero worth reopening porque…_
