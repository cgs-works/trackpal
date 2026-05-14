# Trackpal Domain Context

> **Trackpal** — Plataforma B2B multi-tenant para gestión de suscripciones de streaming.
> Permite a empresas (tenants) gestionar sus clientes y las suscripciones a servicios
> de streaming (Netflix, Disney+, etc.) que ofrecen a sus clientes finales.

---

## Domain Language (Ubiquitous Language)

### Roles

| Term | Definition | Avoid |
|---|---|---|
| **Master** | Dueño y operador único de la plataforma Trackpal. Crea y gestiona tenants via dashboard web o WhatsApp Console. Es ingresado en la base de datos mediante semilla (seed). | Superadmin, root, owner, admin |
| **Tenant** | Cada empresa cliente de Trackpal que utiliza la plataforma para gestionar sus propios clientes y suscripciones de streaming. Tiene un perfil (`tenant_profiles`) con full_name, email, phone, evolution_instance_name, is_active. | Admin, account, organization, cliente business |
| **Customer** | Usuario final de cada **Tenant** que recibe acceso a servicios de streaming a través de la plataforma. *(No implementado aún — futuro)* | Client, end-user, subscriber |
| **User** | Entidad de autenticación unificada. Todo **Master** y **Tenant** tiene un registro en la tabla `users` con UUID, username y password_hash. El campo `role` diferencia el tipo ('master' \| 'tenant'). | Login, account, credential |

### Business Entities

| Term | Definition | Avoid |
|---|---|---|
| **Subscription** | Registro de un **Customer** a un servicio de streaming específico (Netflix, Disney+, etc.) gestionado a través de Trackpal. *(No implementado aún — futuro)* | Plan, membership |
| **Service** | Plataforma de streaming que se ofrece como producto (Netflix, Disney+, HBO Max, etc.). *(No implementado aún — futuro)* | Provider, streamer |

### Infrastructure & Platform

| Term | Definition | Avoid |
|---|---|---|
| **Evolution Instance** | Conexión entre un número de WhatsApp y Trackpal via Evolution API. Cada **Tenant** tiene una instancia identificada por un nombre único con prefijo `tenant-`. El **Master** crea la instancia manualmente desde el dashboard; el **Tenant** escanea el QR para vincular su número. | WA connection, instance |
| **WhatsApp Console** | Interfaz conversacional del **Master** para gestionar **Tenants** a través de WhatsApp. Usa flujos multi-paso (menú → selección → confirmación) con estado efímero en Redis. | Master Console, WhatsApp bot, chatbot |
| **Console Session** | Estado efímero de conversación (flow, step, temp_data, selection_map) almacenado en Redis con TTL de 15 minutos, claveado por teléfono del **Master** bajo `session:{phone}`. | Session, conversation |
| **Auth Session** | Sesión autenticada del **Master** en el **WhatsApp Console**, creada tras verificar username+password y mantenida con TTL deslizante de 15 minutos bajo clave `wa:auth:{phone}`. | Login session, wa session |
| **Lockout** | Bloqueo temporal de 5 minutos tras 5 intentos fallidos consecutivos de autenticación en el **WhatsApp Console**, contados en una ventana de 15 minutos. Se almacena bajo `wa:auth:lock:{phone}`. | Rate limit, ban |
| **Contingency Reply** | Mensaje de respuesta predefinido que retorna el backend cuando Redis no está disponible o el circuit breaker ha abierto y la sesión no se encuentra en la instancia de respaldo. | Fallback, error message |
| **Phone Normalizer** | Transformación que convierte cualquier formato de teléfono (con `+`, sufijos JID `@c.us`, sufijos de dispositivo `:number`) a una representación canónica de solo dígitos para almacenamiento y búsqueda. | Phone format, canonical phone |

### Validation Policy (Input Validation Policy)

| Term | Definition | Avoid |
|---|---|---|
| **Input Validation Policy** | Política centralizada en el backend que define reglas de validación y normalización para username, email, phone y full_name. Es reutilizada por schemas Pydantic, servicios y flujos WhatsApp. | Validación por canal, reglas duplicadas |
| **Username** | Solo letras minúsculas, números y `_`, máximo 20 caracteres, debe iniciar con letra. | username libre, comandos tipo `/menu` |
| **Email** | Validación de sintaxis con `email-validator` + normalización; no se exige deliverability/DNS. | regex casero mínima, validación dependiente de red |
| **Phone** | Entrada obligatoriamente interpretable como E.164, pero puede recibirse sin `+`; se canonicaliza a dígitos para almacenamiento y lookup. | Heurística de país, formatos ambiguos por canal |
| **Full Name** | Permite letras Unicode, números y espacios; no permite espacio inicial/final; espacios internos múltiples se colapsan a uno antes de guardar. | Conservar whitespace sucio, comandos o payloads crudos |

---

## Entity-Relationship Summary

```
User (unified auth)
 ├── role = 'master' → MasterProfile  (name, phone)
 │                           └── WhatsApp Console access
 │                               ├── Auth Session (Redis, wa:auth:{phone})
 │                               ├── Console Session (Redis, session:{phone})
 │                               └── Lockout state (Redis, wa:auth:lock:{phone})
 └── role = 'tenant' → TenantProfile  (full_name, email, phone,
                                        evolution_instance_name, is_active)
                           └── (futuro) → manages Customers
                               └── (futuro) → has Subscriptions
                                   └── (futuro) → to Services
```

- Un **Master** puede crear y gestionar múltiples **Tenants**
- Un **Tenant** tiene exactamente un registro en **Users** (para login)
- Un **Tenant** tiene exactamente una **Evolution Instance** vinculada (prefijo `tenant-`)
- Un **Tenant** gestionará múltiples **Customers** (a futuro)
- Un **Customer** puede tener una o más **Subscriptions** a distintos **Services**
- El **Master** tiene exactamente un número de teléfono único que usa para acceder al **WhatsApp Console**
- El **WhatsApp Console** usa tres claves Redis por teléfono: auth session, console session, lockout state

---

## Architecture Overview

```
┌───────────────────────────────────────────────────────────────────────┐
│                        Frontend (Vue 3 + Vite)                       │
│    LoginView ─── MasterDashboardView ─── TenantDashboardView         │
└──────────────────────┬───────────────────────────────────────────────┘
                       │ HTTP/JSON (JWT Bearer)
                       ▼
┌───────────────────────────────────────────────────────────────────────┐
│                      Backend API (FastAPI + SQLAlchemy)               │
│  /api/v1/auth/*           → AuthService                              │
│  /api/v1/tenants/*        → TenantService (Master only)              │
│  /api/v1/me/*             → ProfileService                           │
│  /api/v1/dashboard        → role-aware response                      │
│  /api/v1/integrations/n8n/identify  → n8n identification             │
│  /api/v1/integrations/n8n/console   → WhatsApp Console endpoint      │
└───────────┬───────────────────────────────────────┬───────────────────┘
            │ async SQLAlchemy                      │ Redis (HA)
            ▼                                       ▼
     ┌──────────────┐                    ┌──────────────────────┐
     │  Supabase     │                    │  Redis Primary       │
     │  PostgreSQL   │                    │  (active-passive     │
     └──────────────┘                    │   circuit breaker)   │
            ▲                            │  wa:auth:{phone}     │
            │ webhook                    │  session:{phone}     │
            │ ("/menu" keyword)          │  wa:auth:fail:{phone}│
     ┌──────────────┐                    │  wa:auth:lock:{phone}│
     │  n8n Workflow │──→ Evolution API └──────────────────────┘
     │  (transport)   │──→ WhatsApp
     └──────────────┘
```

### WhatsApp Console Flow (detallado)

```
WhatsApp → Evolution API → n8n webhook → POST /integrations/n8n/console
  → Backend:
    1. Verify X-API-Key header
    2. Normalize phone (digits-only)
    3. Get Redis manager → fail if unavailable → return ContingencyReply
    4. WhatsAppMasterConsoleFacade.process_message()
       a. Check Lockout → si locked → return LOCKOUT_TEMPLATE
       b. Check Auth Session → si existe + role=master → refresh TTL
          → delegate to WhatsAppConsoleService
            → Console Session (flow/step/temp_data en Redis)
            → TenantService via TenantAdapter
       c. Si no hay Auth Session → run login flow
          → username step → password step → verify credentials
          → success → create Auth Session → show MAIN_MENU
          → failure → record fail counter → lockout si threshold alcanzado
    5. Return reply text → n8n → Evolution API → WhatsApp
```

---

## Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12+ / FastAPI / SQLAlchemy async / Pydantic V2 / UV |
| Database | Supabase PostgreSQL / Alembic (async migrations) |
| Frontend | Vue 3 (Composition API) / Pinia / Vue Router / Vite |
| Messaging | n8n (orchestrator, transport-only) / Evolution API (WhatsApp gateway) |
| Auth | JWT (HS256, python-jose) / bcrypt / refresh token rotation |
| Session State | Redis (active-passive HA with circuit breaker) |
| Infra | Render (backend) / Cloudflare Pages (frontend) |
| Testing | pytest + httpx + aiosqlite (backend, in-memory) |

---

## Project Structure

```
trackpal/
├── backend/
│   ├── app/
│   │   ├── api/                    # FastAPI endpoints + dependencies
│   │   │   └── v1/endpoints/       # auth, tenants, me, dashboard, integrations
│   │   ├── core/                   # config, database, security, phone,
│   │   │                          # input_validation, redis_client
│   │   ├── models/                 # SQLAlchemy ORM models
│   │   ├── schemas/                # Pydantic V2 request/response
│   │   ├── services/               # Business logic layer
│   │   │   ├── auth_service.py
│   │   │   ├── tenant_service.py
│   │   │   ├── profile_service.py
│   │   │   ├── evolution_client.py
│   │   │   ├── whatsapp_console_service.py       # Conversation routing
│   │   │   ├── whatsapp_session_service.py       # Redis session CRUD
│   │   │   ├── whatsapp_auth_session_service.py  # Auth session + lockout
│   │   │   ├── whatsapp_master_console_facade.py # Auth-gated orchestrator
│   │   │   └── contingency_reply_policy.py       # Degraded Redis replies
│   │   ├── crud/                  # users.py (data access helpers)
│   │   └── main.py                # FastAPI app factory
│   ├── alembic/                   # Async Alembic migrations
│   ├── scripts/seed.py            # Master user seed (idempotent)
│   ├── tests/                     # 18 test files, 143+ test functions
│   └── pyproject.toml             # UV dependencies
├── frontend/
│   └── src/
│       ├── router/                # Vue Router config
│       ├── stores/                # Pinia auth store
│       ├── services/              # Axios API client
│       └── views/                 # LoginView, MasterDashboardView, TenantDashboardView
├── n8n/                           # WhatsApp Bot workflow JSON export
├── docs/                          # Architecture, ADRs, plans, PRDs
│   ├── adr/                       # 3 Architecture Decision Records
│   ├── architecture/              # API routes, data flow, n8n workflow
│   ├── codebase/                  # Backend & frontend structure
│   ├── plans/                     # Implementation plans (archived)
│   └── prds/                      # Product requirements (5 PRDs)
├── render.yaml                    # Render Blueprint deploy config
├── CONTEXT.md                     # This file
├── CONTEXT-MAP.md                 # Domain-to-file mapping
├── CLAUDE.md                      # GitNexus integration
├── AGENTS.md                      # Agent instructions
└── README.md                      # Project overview and quick start
```

---

## Key Design Decisions

### Auth Model
- Tabla `users` unificada con role (`master`|`tenant`).
- Perfiles separados en `master_profiles` y `tenant_profiles`.
- Login unificado: un solo endpoint, frontend redirige según role.
- Refresh token rotation: cada refresh emite nuevo par e invalida el anterior. Los refresh tokens se almacenan hasheados (SHA-256) en `refresh_sessions`.

### Tenant Lifecycle
1. **Create**: Crea User + TenantProfile. Si se provee `evolution_instance_name`,
   también crea instancia en Evolution API + configura integración n8n.
   Si no se provee password, se genera uno automáticamente (token_urlsafe(16)).
   El nombre de instancia se prefija con `tenant-` automáticamente.
2. **Active**: Puede iniciar sesión y ser identificado por n8n.
3. **Deactivate** (soft-delete): `is_active=false`, revoca todas las sesiones.
   No puede iniciar sesión ni ser identificado.
4. **Delete** (hard-delete): Solo permitido si está inactivo.
   Elimina el User (cascade a perfil y sesiones) y la instancia de Evolution API.

### WhatsApp Console Auth Model
- El **Master** debe iniciar sesión con username+password a través de WhatsApp antes de operar la consola.
- **Auth Session** con sliding TTL: 15 minutos desde la última actividad.
- **Lockout**: 5 intentos fallidos consecutivos en ventana de 15 minutos → bloqueo de 5 minutos.
- Las Console Sessions (flow state) son independientes de las Auth Sessions.
- La autenticación se verifica contra la tabla `users` usando el mismo `AuthService.authenticate()` que el login web.
- Los mensajes de ayuda y comandos globales (0, menu, cancelar) funcionan incluso durante el flujo de login.

### WhatsApp Console Conversation Model
- Flujos multi-paso gestionados enteramente por el backend (no hay lógica de flujo en n8n).
- n8n actúa solo como **transport**: recibe el mensaje, llama a `/integrations/n8n/console`, retorna la respuesta.
- Cada flujo tiene un identificador (`flow`) y un paso (`step`) almacenados en la Console Session.
- Los datos temporales se acumulan en `temp_data` dentro de la sesión.
- Comandos globales: `0`, `menu`, `menú`, `cancelar` resetean al menú principal; `5`, `ayuda` muestran ayuda contextual.
- Las respuestas de error de validación (InputValidationError) se traducen a mensajes en español con reprompt.

### Redis HA Model
- Active-passive primary/backup con circuit breaker gestionado por `RedisConnectionManager` + `FailoverPolicy`.
- **Estados del breaker**: CLOSED (primary activo), OPEN (backup activo), HALF_OPEN (probando primary).
- **Threshold**: 3 fallos consecutivos en primary para abrir el breaker.
- **Ventana de recuperación**: 30 segundos en OPEN antes de pasar a HALF_OPEN.
- **ContingencyReplyPolicy**: respuestas relayables cuando Redis no está disponible (`TEMPORARY_UNAVAILABLE`) o cuando el failover causa pérdida de sesión (`SESSION_RESET`).
- La señal `used_backup` permite al servicio de sesiones decidir si una sesión ausente es normal (primer mensaje) o por failover (sesión perdida en backup).

### Input Validation Policy
- **Centralización total**: la validación vive en `app/core/input_validation.py` y es el único lugar donde se definen las reglas.
- **Reutilización forzada**: schemas Pydantic y servicios llaman a las mismas funciones validadoras.
- **Errores estructurados**: `InputValidationError` con field, message y code para manejo programático.
- **Sin excepciones**: incluso los flujos WhatsApp usan las mismas funciones y traducen los errores a español.
- **Normalización**: los validadores devuelven valores normalizados (email minúsculas, espacios colapsados, phone digits-only).
- **Phone sin heurística**: usa `phonenumbers` para parseo E.164; requiere código de país explícito.

### WhatsApp Integration
- n8n recibe mensajes via Evolution API (keyword trigger: "/menu").
- Workflow filtra por instancia "Sublify" (solo Master por ahora).
- El endpoint `/integrations/n8n/console` es el único entrypoint para mensajes WhatsApp entrantes.
- Identificación vía endpoint protegido con API Key (`X-API-Key` header).
- No hay lógica de flujo en n8n — todo el routing y estado vive en el backend.

### Constraints
- Phone único cross-table (master_profiles + tenant_profiles).
- Un solo Master (seed idempotente + validación en service layer).
- Todos los IDs son UUID v4.
- Contraseñas hasheadas con bcrypt (sin passlib).
- Las migraciones Alembic son asíncronas.
- En tests, la integración con Evolution API se deshabilita (api_key vacía).
- Redis no es obligatorio: si no hay Redis configurado, el endpoint WhatsApp retorna `TEMPORARY_UNAVAILABLE`.

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
| Redis HA | Active-passive con circuit breaker (3 fallos → 30s half-open) |
| WhatsApp Auth | Conversacional username+password con sliding TTL de 15min y lockout 5min tras 5 fallos |
| Input Validation | Centralizada en backend, reutilizada por schemas, servicios y WhatsApp |
| Test count | 143 test functions en 18 archivos, más expansión parametrizada; ejecutados con aiosqlite in-memory |
| Phone canonicalization | Digits-only sin `+` para storage/lookup; `+`-prefixed buscado por compatibilidad retro |
| Prefijo Evolution | `tenant-` antepuesto automáticamente al `evolution_instance_name` al crear instancia |

---

## Example Dialogue

> **Dev:** "Cuando un **Tenant** inicia sesión, ¿validamos contra la tabla
> **Users** igual que el **Master**, solo que con role='tenant'?"
> **Domain expert:** "Exacto. El login es unificado. La tabla **Users**
> tiene el role y el UUID que conecta con `tenant_profiles` para los
> datos específicos del tenant."
>
> **Dev:** "¿El **Master** puede gestionar tenants desde WhatsApp?"
> **Domain expert:** "Sí. El **WhatsApp Console** permite al Master crear,
> editar, desactivar, reactivar y eliminar tenants mediante flujos
> conversacionales multi-paso. n8n es solo transporte."
>
> **Dev:** "¿El QR de vinculación se muestra en el dashboard?"
> **Domain expert:** "A futuro, sí, en el dashboard del tenant. Por ahora
> el master lo genera manualmente."
>
> **Dev:** "¿Qué pasa si el Master escribe cualquier cosa durante un flujo?"
> **Domain expert:** "El **WhatsApp Console Service** maneja cada paso del
> flujo. Si la entrada no es válida, muestra un mensaje de error en español
> y repite el prompt del paso actual sin perder los datos ya recolectados."
>
> **Dev:** "¿Y si Redis se cae?"
> **Domain expert:** "El backend tiene un **ContingencyReplyPolicy** que
> devuelve mensajes relayables ('Consola temporalmente no disponible' o
> 'Sesión reiniciada por contingencia'). n8n los reenvía sin cambios."

---

*See also: [CONTEXT-MAP.md](CONTEXT-MAP.md) for domain-to-file mapping, and [docs/SUMMARY.md](docs/SUMMARY.md) for full technical documentation index.*
