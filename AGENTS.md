# Trackpal

## Project Overview

Trackpal — multi-tenant SaaS. Master manages tenants via WhatsApp console + web dashboard. Spanish market.

**Stack:** Python ≥3.12 / FastAPI / SQLAlchemy async / PostgreSQL / Redis HA / JWT+bcrypt / Evolution API / n8n / Vue 3+Pinia / Vite

## Documentation

All project documentation is in [docs/SUMMARY.md](docs/SUMMARY.md). Before planning or implementing, read it to understand the full documentation map. Key docs:

| Area | Location |
|------|----------|
| System architecture | `docs/architecture/system-overview.md` |
| API layer | `docs/architecture/api-layer.md` |
| Database schema | `docs/architecture/database-schema.md` |
| Redis HA | `docs/architecture/redis-ha.md` |
| WhatsApp console flow | `docs/architecture/whatsapp-console-flow.md` |
| Evolution integration | `docs/architecture/evolution-integration.md` |
| n8n workflow | `docs/architecture/n8n-workflow.md` |
| Frontend architecture | `docs/architecture/frontend-architecture.md` |
| Input validation policy | `docs/architecture/input-validation-policy.md` |
| Backend conventions | `docs/code-standard/backend-conventions.md` |
| Frontend conventions | `docs/code-standard/frontend-conventions.md` |
| Product goals | `docs/project-pdr/product-goals.md` |
| Business rules | `docs/project-pdr/business-rules.md` |

## Setup Commands

```bash
# Backend
cd backend && pip install uv && uv sync --group dev
uv run alembic upgrade head && uv run python -m scripts.seed
uv run uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend && npm install && npm run dev    # proxies /api → :8000
npm run build                                 # → dist/

# n8n
# Import n8n/Trackpal\ WhatsApp\ Bot.json via n8n UI
```

**Key env vars** (22+ total, see `app/core/config.py` or `render.yaml`):
`DATABASE_URL`, `SECRET_KEY`, `MASTER_USERNAME/PASSWORD`, `MASTER_PHONE`, `N8N_API_KEY`, `EVOLUTION_API_URL/KEY`, `REDIS_PRIMARY_URL`, `REDIS_BACKUP_URL`

## Project Structure

```text
backend/
├── app/main.py                     # FastAPI entry, CORS, lifespan
├── app/api/dependencies.py         # get_current_user, require_role, verify_n8n
├── app/api/v1/endpoints/           # auth, me, dashboard, tenants, catalog, i18n, plus integrations/, subscriptions/ packages
├── app/core/                       # config, database, security, phone, errors, plus i18n/, input_validation/, redis_client/ packages
├── app/models/                     # user, tenant, service, plan, client, profiles, refresh_session, subscription
├── app/repositories/               # users, tenants, clients, catalog, profiles, sessions (migrated from crud/)
├── app/schemas/                    # auth, tenant, catalog, me, dashboard, whatsapp, plus subscription/ package
├── app/services/                   # All services as packages: auth_service/, tenant_service/, subscription_service/, etc.
├── tests/                          # 28 files, ~12k LOC
└── scripts/seed.py

frontend/
├── src/
│   ├── main.js / App.vue / style.css
│   ├── router/index.js             # 3 rutas + guards
│   ├── services/api.js             # Axios + interceptors
│   ├── stores/auth.js              # Pinia: token, user, login/logout
│   └── views/                      # LoginView, MasterDashboardView, TenantDashboardView,
│                                   # ClientDashboardView
└── vite.config.js
```

**n8n pipeline:** `Webhook POST → Parse → Config → POST /api/v1/integrations/n8n/console → Merge → Evolution API sendText`

## Testing

```bash
cd backend
uv run pytest -v                          # All tests
uv run pytest tests/test_auth.py -v       # Single file
uv run pytest -v -k "tenant"              # By keyword
```

**Patterns:** async (pytest-asyncio), SQLite in-memory (aiosqlite), httpx ASGITransport client. Evolution + Redis mocked. Fixtures: `async_client`, `db_session`, `master_headers`, `tenant_headers`.

## Code Style

- **Backend:** Python 3.12+ type hints, FastAPI endpoints thin (logic in services/), SQLAlchemy async, Pydantic v2 schemas, bcrypt + JWT short-lived + refresh rotation, phone digits-only canonical form, Spanish UI
- **Frontend:** Vue 3 `<script setup>`, Pinia stores, Axios interceptors, router guards, plain JS (no TypeScript), **no frontend tests**
- **n8n:** Config Set node for vars, `neverError` on webhook, input normalization (strip `@c.us`), reply fallback on timeout

## Build & Deployment

| Target | Command |
|---|---|
| Render | `pip install uv && uv sync` → `uv run alembic upgrade head && uv run python -m scripts.seed && uv run uvicorn app.main:app` |
| Cloudflare Pages | `VITE_API_URL=<url> npm run build` → upload `dist/` |
| n8n | Import workflow JSON; set webhook URL in Evolution API instance (trigger: `/menu`) |

---

# Contexto ampliado de la codebase (fusionado desde `CONTEXT.md`)

Trackpal es una plataforma SaaS multi-inquilino (multi-tenant) orientada al mercado español que permite gestionar el ciclo de vida de inquilinos y sus suscripciones mediante una consola conversacional de WhatsApp (soportada por Evolution API y n8n) y un panel web de administración reactivo.

## Glosario y Vocabulario Técnico

**Reminder Settings**:
Ajustes del inquilino (tenant) que determinan si se generan recordatorios de vencimiento de suscripciones, cuándo son elegibles y quién los recibe.
_Evitar_: Reminder Preferences, Reminder Configuration.

**Tenant Context**:
El ámbito del inquilino activo en un momento dado para acciones bajo su dominio, ya sea que el actor sea un usuario del inquilino o el usuario Master operando temporalmente en modo soporte.
_Evitar_: Account Context, Support Tenant.

## Arquitectura General de la Solución

La solución se compone de tres piezas principales conectadas de forma asíncrona:
1. **Frontend (Vue 3 SPA)**: Alojado en Cloudflare Pages, desarrollado con Vite, Pinia para la gestión del estado, Axios para peticiones HTTP y Vue Router para navegación y guardas de seguridad.
2. **Backend (FastAPI)**: Alojado en Render con Python ≥3.12, base de datos PostgreSQL (SQLAlchemy Async, Alembic para migraciones) y Redis HA (para estado efímero y resiliencia de las sesiones conversacionales de WhatsApp).
3. **Automatización de Bots (n8n + Evolution API)**: n8n actúa como pasarela para orquestar los webhooks de WhatsApp entrantes desde la Evolution API, enrutándolos a las API de consola del backend de Trackpal y enviando respuestas formateadas de vuelta.

## Resumen del Backend (`backend/app/`)

El backend está estructurado siguiendo un diseño modular y limpio, desacoplando la capa de transporte (API), la validación de esquemas, la lógica de negocio (servicios) y la persistencia (repositorios).

### 1. Modelos de Base de Datos (`app/models/`)
Todos los modelos heredan de `Base` (SQLAlchemy Declarative) y la mayoría incluye `TimestampMixin` para auditoría automática de creación y actualización:
- **`User`**: Representa a los usuarios del sistema (inquilinos o administradores maestros) con contraseñas seguras (bcrypt) y roles de acceso.
- **`Tenant`**: Entidad inquilina principal con configuración de idioma local (`locale`), teléfono e información comercial.
- **`Client`**: Clientes finales de cada inquilino, asociados a suscripciones de servicios.
- **`Service` & `Plan`**: Catálogo de productos/servicios e intervalos de pago definidos por los inquilinos.
- **`Subscription`**: Instancia de servicio contratada por un cliente final. Almacena de forma encriptada (con Fernet) las credenciales de streaming/acceso del servicio.
- **`SubscriptionEvent`, `SubscriptionReminderLog`, `SubscriptionReminderSettings`**: Gestión de eventos de suscripción, registros históricos de recordatorios enviados y ajustes individuales de notificaciones.
- **`TenantMailbox`**: Buzones de correo configurados por los inquilinos para la ingesta y extracción automática de códigos de verificación.
- **`MailLookupJob` & `MailCodeDeliveryLog`**: Tareas de consulta y logs de envío de códigos de verificación extraídos.
- **`CodeServiceGlobalStatus` & `TenantCodeServiceSelection`**: Control de activación global y por inquilino de servicios de extracción de códigos automáticos (Netflix, HBO Max, Disney, Prime Video, Spotify, Universal Plus).

### 2. Repositorios (`app/repositories/`)
Abstraen las operaciones de consulta y mutación con la base de datos usando sesiones asíncronas de SQLAlchemy (`AsyncSession`):
- `users_repository`, `tenants_repository`, `clients_repository`, `catalog_repository`, `profiles_repository`, `sessions_repository`, `mailbox_config_repository`, `mailbox_dedupe_repository`, `mailbox_lookup_repository`, `code_services_repository`.

### 3. Esquemas de Datos (`app/schemas/`)
Modelos de validación Pydantic V2 que garantizan la integridad de las entradas y salidas de la API REST:
- `auth`, `tenant`, `catalog`, `client`, `me`, `dashboard`, `whatsapp`, `mailbox`, `code_services`, `subscription`.

### 4. Capa de Servicios y Lógica de Negocio (`app/services/`)
La lógica principal se divide en paquetes modulares autocontenidos:
- **`auth_service`**: Gestión de tokens de acceso (JWT de corta duración) y rotación de tokens de refresco en base de datos.
- **`tenant_service`**: Reglas de negocio para la creación, desactivación y actualización de inquilinos.
- **`whatsapp_session_service`**: Administra los estados efímeros de conversación en Redis para evitar colisiones de sesión.
- **`whatsapp_console_service`**: Máquina de estados conversacionales y flujos de interacción de WhatsApp para consolas Master, Tenant (creación/edición de suscripciones, catálogo y clientes) y Client.
- **`evolution_client`**: Cliente REST para interactuar con Evolution API (crear instancias de WhatsApp, enviar mensajes, registrar webhooks).
- **`mail_lookup_worker`**: Worker en background encargado del procesamiento de cuentas de correo (OAuth Google/Microsoft e IMAP estándar) para consultar correos, extraer códigos mediante scrapers especializados de streaming (`mail_code_extractor`), y registrar logs de envío.

### 5. API Layer y Rutas (`app/api/`)
FastAPI expone endpoints REST en la ruta `/api/v1/`:
- `/auth`: Login, refresco de sesión y logout.
- `/me`: Perfil del usuario autenticado.
- `/dashboard`: Métricas agregadas y datos rápidos de uso.
- `/tenants`: Operaciones CRUD sobre inquilinos (solo Master).
- `/catalog`: CRUD sobre planes y servicios del inquilino.
- `/clients`: CRUD de clientes finales de cada inquilino.
- `/mailbox`: Configuración de buzones, ingesta de correos y webhooks de OAuth.
- `/code_services`: Gestión de activación global y por inquilino de los bots de extracción de códigos de streaming.
- `/subscriptions`: Endpoints para el ciclo de vida de suscripciones, configuración de recordatorios (`ReminderSettings`) e historiales.
- `/integrations/n8n/console`: Punto de entrada para el flujo n8n que procesa los mensajes interactivos de WhatsApp.

## Resumen del Frontend (`frontend/src/`)

El frontend es una aplicación de página única (SPA) desarrollada sobre Vue 3 que ofrece una interfaz intuitiva para administradores de Trackpal (Master) e inquilinos (Tenants).

### 1. Gestión de Estado (`stores/`)
- **`auth.js`**: Estado reactivo del usuario logueado, roles de acceso, tokens JWT y flujos de login/logout.
- **`i18n.js`**: Carga de forma dinámica los diccionarios de idiomas localizados desde el endpoint `/api/v1/i18n/catalog` para aplicar traducción interactiva en español/inglés en toda la aplicación web.

### 2. Capa de Red e Interceptores (`services/api.js`)
Cliente Axios unificado que inyecta automáticamente el token JWT en las cabeceras HTTP (`Authorization: Bearer <token>`) y gestiona de forma transparente el flujo de refresco de tokens mediante interceptores en caso de respuestas 401.

### 3. Enrutador (`router/index.js`)
Configura las rutas principales de la SPA con guardas de navegación (`beforeEach`) basadas en el rol y el estado de autenticación:
- `/login`: Vista de login público.
- `/master-dashboard`: Panel administrativo exclusivo para el rol Master.
- `/tenant-dashboard`: Panel principal del inquilino para gestionar clientes, catálogos y métricas.
- `/client-dashboard`: Panel adaptativo y responsive exclusivo para clientes de inquilinos.
- `/subscriptions`: Panel dedicado a la creación, edición, y envío de recordatorios de suscripciones.

### 4. Vistas y Componentes Reactivos (`views/` & `components/`)
Los componentes modulares encapsulan lógica compleja de interfaz para mantener las vistas limpias:
- **`CatalogPanel.vue`**: Gestión interactiva del catálogo de servicios y planes.
- **`ClientManagementPanel.vue`**: ABM completo de clientes finales, integrando búsquedas rápidas.
- **`MailboxConfigPanel.vue`**: Configuración de buzones IMAP/OAuth para el inquilino.
- **`CodeServicesTenantPanel.vue` & `CodeServicesGlobalPanel.vue`**: Interruptores para activar o desactivar la extracción automática de códigos de streaming por inquilino o globalmente.
- **`ReminderSettingsModal.vue`**: Modal de configuración para los ajustes de recordatorios de suscripciones del inquilino (Reminder Settings).
