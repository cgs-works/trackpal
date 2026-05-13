# Trackpal Domain Context

> **Trackpal** — Plataforma B2B multi-tenant para gestión de suscripciones de streaming.
> Permite a empresas (tenants) gestionar sus clientes y las suscripciones a servicios
> de streaming (Netflix, Disney+, etc.) que ofrecen a sus clientes finales.

---

## Domain Language (Ubiquitous Language)

### Roles

| Term | Definition | Avoid |
|---|---|---|
| **Master** | Dueño y operador único de la plataforma Trackpal. Crea y gestiona tenants via dashboard o WhatsApp. Es ingresado en la base de datos mediante semilla (seed). | Superadmin, root, owner, admin |
| **Tenant** | Cada empresa cliente de Trackpal que utiliza la plataforma para gestionar sus propios clientes y suscripciones de streaming. | Admin, account, organization, cliente business |
| **Customer** | Usuario final de cada **Tenant** que recibe acceso a servicios de streaming a través de la plataforma. *(No implementado aún — futuro)* | Client, end-user, subscriber |
| **User** | Entidad de autenticación unificada. Todo **Master** y **Tenant** tiene un registro en la tabla `users` con UUID, username y password_hash. El campo `role` diferencia el tipo ('master' \| 'tenant'). | Login, account, credential |

### Business Entities

| Term | Definition | Avoid |
|---|---|---|
| **Subscription** | Registro de un **Customer** a un servicio de streaming específico (Netflix, Disney+, etc.) gestionado a través de Trackpal. *(No implementado aún — futuro)* | Plan, membership |
| **Service** | Plataforma de streaming que se ofrece como producto (Netflix, Disney+, HBO Max, etc.). *(No implementado aún — futuro)* | Provider, streamer |

### Infrastructure

| Term | Definition | Avoid |
|---|---|---|
| **Evolution Instance** | Conexión entre un número de WhatsApp y Trackpal via Evolution API. Cada **Tenant** tiene una instancia identificada por un nombre único. El **Master** crea la instancia manualmente desde el dashboard; el **Tenant** escanea el QR para vincular su número. | WA connection, instance |

---

## Entity-Relationship Summary

```
User (unified auth)
 ├── role = 'master' → MasterProfile  (name, phone)
 └── role = 'tenant' → TenantProfile  (full_name, email, phone,
                                        evolution_instance_name, is_active)
                           └── (futuro) → manages Customers
                               └── (futuro) → has Subscriptions
                                   └── (futuro) → to Services
```

- Un **Master** puede crear y gestionar múltiples **Tenants**
- Un **Tenant** tiene exactamente un registro en **Users** (para login)
- Un **Tenant** gestionará múltiples **Customers** (a futuro)
- Un **Customer** puede tener una o más **Subscriptions** a distintos **Services**
- Un **Tenant** tiene exactamente una **Evolution Instance** vinculada

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                   Frontend (Vue 3 + Vite)           │
│    LoginView ─── MasterDashboardView                │
│                   TenantDashboardView                │
└─────────────────┬───────────────────────────────────┘
                  │ HTTP/JSON (JWT Bearer)
                  ▼
┌─────────────────────────────────────────────────────┐
│            Backend API (FastAPI + SQLAlchemy)       │
│  /api/v1/auth/*     → AuthService                   │
│  /api/v1/tenants/*  → TenantService (Master only)   │
│  /api/v1/me/*       → ProfileService                │
│  /api/v1/dashboard  → role-aware response           │
│  /api/v1/integrations/n8n/identify → n8n hook      │
└─────────────────┬───────────────────────────────────┘
                  │ async SQLAlchemy
                  ▼
         ┌────────────────┐
         │  Supabase       │
         │  PostgreSQL     │
         └────────────────┘
                  ▲
                  │ webhook (keyword trigger: "/menu")
         ┌────────────────┐
         │  n8n Workflow   │──→ Evolution API → WhatsApp
         └────────────────┘
```

---

## Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12+ / FastAPI / SQLAlchemy async / Pydantic V2 / UV |
| Database | Supabase PostgreSQL / Alembic (async migrations) |
| Frontend | Vue 3 (Composition API) / Pinia / Vue Router / Vite |
| Messaging | n8n (orchestrator) / Evolution API (WhatsApp gateway) |
| Auth | JWT (HS256, python-jose) / bcrypt / refresh token rotation |
| Infra | Render (backend) / Cloudflare Pages (frontend) |
| Testing | pytest + httpx + aiosqlite (backend) |

---

## Project Structure

```
trackpal/
├── backend/
│   ├── app/
│   │   ├── api/            # FastAPI endpoints + dependencies
│   │   │   └── v1/endpoints/   # auth, tenants, me, dashboard, integrations
│   │   ├── core/           # config, database, security
│   │   ├── models/         # SQLAlchemy ORM models
│   │   ├── schemas/        # Pydantic V2 request/response
│   │   ├── services/       # Business logic layer
│   │   ├── crud/           # Data access helpers
│   │   └── main.py         # FastAPI app factory
│   ├── alembic/            # Async Alembic migrations
│   ├── scripts/seed.py     # Master user seed (idempotent)
│   ├── tests/              # 34 pytest tests
│   └── pyproject.toml      # UV dependencies
├── frontend/
│   └── src/
│       ├── router/         # Vue Router config
│       ├── stores/         # Pinia auth store
│       ├── services/       # Axios API client
│       └── views/          # LoginView, MasterDashboardView, TenantDashboardView
├── n8n/                    # WhatsApp Bot workflow JSON export
├── docs/                   # Architecture, ADRs, plans, PRDs
│   ├── adr/                # Architecture Decision Records (3 existing)
│   ├── architecture/       # API routes, data flow, n8n workflow
│   ├── codebase/           # Backend & frontend structure
│   ├── plans/              # Implementation plan
│   └── prds/               # Product requirements
├── render.yaml             # Render Blueprint deploy config
└── CONTEXT.md              # This file
```

---

## Key Design Decisions

### Auth Model
- Tabla `users` unificada con role (`master`|`tenant`).
- Perfiles separados en `master_profiles` y `tenant_profiles`.
- Login unificado: un solo endpoint, frontend redirige según role.
- Refresh token rotation: cada refresh emite nuevo par e invalida el anterior.

### Tenant Lifecycle
1. **Create**: Crea User + TenantProfile. Si se provee `evolution_instance_name`,
   también crea instancia en Evolution API + configura integración n8n.
2. **Active**: Puede iniciar sesión y ser identificado por n8n.
3. **Deactivate** (soft-delete): `is_active=false`, revoca todas las sesiones.
   No puede iniciar sesión ni ser identificado.
4. **Delete** (hard-delete): Solo permitido si está inactivo.
   Elimina el User (cascade a perfil y sesiones) y la instancia de Evolution API.

### WhatsApp Integration
- n8n recibe mensajes via Evolution API (keyword trigger: "/menu").
- Workflow filtra por instancia "Sublify" (solo Master por ahora).
- Identifica usuario por teléfono via endpoint protegido con API Key.
- Gestiona sesiones multi-paso (crear tenant, editar) mediante data table.

### Constraints
- Phone único cross-table (master_profiles + tenant_profiles).
- Un solo Master (seed idempotente + validación en service layer).
- Todos los IDs son UUID v4.
- Contraseñas hasheadas con bcrypt (sin passlib).
- **Input Validation Policy** — validación centralizada en backend, reutilizable por dashboard, API y WhatsApp. _Avoid_: validación por canal, reglas duplicadas en n8n/frontend.
- **Username** — solo letras minúsculas, números y `_`, máximo 20 caracteres, debe iniciar con letra. _Avoid_: username libre, comandos tipo `/menu`, espacios, mayúsculas.
- **Email** — validación de sintaxis + normalización; no se exige deliverability/DNS por request. _Avoid_: regex casero mínima, validación dependiente de red.
- **Phone** — entrada obligatoriamente interpretable como E.164, pero puede recibirse sin `+`; se canonicaliza a dígitos para almacenamiento y lookup. _Avoid_: heurística de país, formatos ambiguos por canal.
- **Full Name** — permite letras, números y espacios; no permite espacio inicial/final; espacios internos múltiples se colapsan a uno antes de guardar. _Avoid_: conservar whitespace sucio, comandos o payloads crudos como nombre.

### Current Gaps (Out of Scope MVP)
- Customer entity and CRUD
- Subscription entity and CRUD
- Service catalog (Netflix, Disney+, etc.)
- Tenant self-service QR generation
- Multi-language support
- CI/CD pipeline

---

## Flagged Ambiguities

| Ambiguity | Resolution |
|---|---|
| ¿Qué se trackea? | Suscripciones a servicios de streaming (Netflix, Disney+, etc.) |
| ¿Quién es el Pal? | El **Master** (dueño de la plataforma) |
| ¿Admin o Tenant? | Se usará **Tenant** — cada cliente business de Trackpal |
| Scope de "track" | Gestión B2B de suscripciones |
| Persistencia | Supabase PostgreSQL |
| Stack backend | Python FastAPI + SQLAlchemy + UV |
| Stack frontend | Vue 3 + Vite |
| Estructura repo | Monorepo: backend/ y frontend/ |
| n8n + WhatsApp | Evolution API + workflow único con router por acción |
| Vinculación WhatsApp | QR de Evolution API, gestionado manualmente por ahora |
| Multi-idioma | Postergado — fuera del scope inicial |
| Versionado API | `/api/v1/` en todas las rutas |

---

## Example Dialogue

> **Dev:** "Cuando un **Tenant** inicia sesión, ¿validamos contra la tabla
> **Users** igual que el **Master**, solo que con role='tenant'?"
> **Domain expert:** "Exacto. El login es unificado. La tabla **Users**
> tiene el role y el UUID que conecta con `tenant_profiles` para los
> datos específicos del tenant."
>
> **Dev:** "¿El **Master** puede gestionar tenants desde WhatsApp?"
> **Domain expert:** "Sí. n8n recibe el mensaje via Evolution API,
> interpreta la acción y llama al backend. Todo el CRUD de tenants
> funciona desde WhatsApp."
>
> **Dev:** "¿El QR de vinculación se muestra en el dashboard?"
> **Domain expert:** "A futuro, sí, en el dashboard del tenant. Por ahora
> el master lo genera manualmente."

---

*See also: [docs/SUMMARY.md](docs/SUMMARY.md) for full technical documentation index.*
