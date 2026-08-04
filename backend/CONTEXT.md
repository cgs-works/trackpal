# Backend Context

## Stack

- Python 3.12+ con `from __future__ import annotations`
- FastAPI (async) con lifespan, middleware CORS, routes bajo `/api/v1`
- SQLAlchemy 2.0 async + asyncpg driver
- PostgreSQL con RLS (Row-Level Security)
- Redis HA (primary + backup) con circuit-breaker failover
- Alembic para migraciones
- Pydantic v2 para schemas

## Vocabulario de dominio

| Término | Definición |
|---------|------------|
| **Tenant** | Entidad que presta servicios. Tiene su propia instancia de Evolution WhatsApp, catálogo, clientes y suscripciones. Un tenant es un "empresa" en el sistema. Cada tenant tiene un **plan** (starter o pro) que determina qué módulos puede usar. |
| **Tenant Admin** | The person who operates a Tenant through TrackPal's administrative interfaces. Use **Tenant** for the business entity, never for the person. |
| **Demo Tenant** | A disposable Tenant created by the Master for one prospect's non-extendable 48-hour evaluation, beginning with the first successful Demo Credentials login. It exposes the immutable Master-selected Starter or Pro capability set but only authentication and lifecycle state in the backend, cannot enter Master Support Context, and never converts into a production Tenant. |
| **Pending Demo Tenant** | A Demo Tenant whose prospect has not logged in, so its evaluation clock has not started. It remains pending until activation or manual deletion by the Master. |
| **Expired Demo Tenant** | A Demo Tenant whose evaluation has ended and can no longer be used. It awaits removal by the next request or by the Master. |
| **Demo Credentials** | System-generated username and one-time-revealed password shared with the prospect. Password replacement revokes sessions without changing the evaluation clock. |
| **Demo Guardrail** | The boundary that prevents a Demo Tenant from reaching real business persistence, external integrations, Public API Catalog access, Tenant Data Export, or self-deletion. Demo business operations remain browser-local. |
| **Tenant Deletion** | The irreversible removal of a Tenant as a business entity, including its sole Tenant Admin identity and tenant-owned domain data. It is distinct from deactivation. Avoid the ambiguous term “account deletion.” |
| **Tenant Data Export** | A portable snapshot of a Tenant's selected business records, expressed through a stable business-facing schema independent of TrackPal's persistence model. It excludes authentication, integration, mailbox, and subscription secrets. |
| **Tenant Onboarding Status** | The tenant-wide record of orientation-tour releases that were completed or skipped. It belongs to the Tenant rather than to an individual Tenant Admin. |
| **Master** | Operador principal. Gestiona el ciclo de vida de tenants via WhatsApp Console y web dashboard. Solo hay una instancia. Puede **switchear** a un tenant específico para soporte; en ese contexto ve la UI completa sin restricciones de plan. |
| **TrackPal Broadcast Channel** | Canal editorial oficial de Telegram de TrackPal, que puede ser público o privado. Es el único destino de las Broadcasts creadas por el Master. _Avoid_: support chat, tenant channel. |
| **Broadcast** | Publicación editorial confirmada manualmente por el Master para el TrackPal Broadcast Channel. Puede contener texto con formato y una secuencia ordenada de adjuntos. _Avoid_: notification, automated post. |
| **Client** | End customer of a Tenant. Uses the canonical login `{client_prefix}_{local_username}` and has read-only access to profile and active subscription information, Web password changes, and WhatsApp access-code lookup. Client access is unavailable while the Tenant is on Starter, although its data is preserved. |
| **Evolution Instance** | Instancia de WhatsApp Business API (Evolution API/Go). Cada tenant tiene una, identificada por `evolution_instance_name`. |
| **WhatsApp Console** | Interfaz conversacional basada en menús numéricos (0=cancelar, 8=siguiente, 9=regresar). Existe para Master, Tenant Admin y Client. |
| **Client Context Shortcut** | A private WhatsApp session in which a Tenant Admin manages a remote contact from the admin's own chat. The remote contact cannot see or operate the administrative menu. |
| **Catalog** | Servicios y planes que un Tenant ofrece. Cada Service se identifica por nombre y puede tener un Service Icon opcional; cada Plan puede tener un Catalog Price opcional expresado en la Currency del Tenant. La disponibilidad no forma parte del catálogo. |
| **Service Icon** | Marca visual opcional elegida por el Tenant Admin para un Service del Catalog. Su ausencia o indisponibilidad usa una representación genérica y nunca cambia la identidad ni el comportamiento del Service. |
| **Icon Reference** | Identidad externa y transferible de un Service Icon. Es distinta del recurso SVG y puede exponerse junto con el Catalog sin convertir a TrackPal en propietario del icono. |
| **Catalog Price** | Precio opcional de un Plan, siempre interpretado en la Currency del Tenant. `NULL` significa "Precio a consultar" (sin precio publicado). No existe conversión ni precio por moneda. Se muestra en las superficies web y en las consolas WhatsApp (catálogo, selección de plan al crear suscripciones y suscripciones del cliente); crear/editar precio es posible también desde la consola WhatsApp del tenant. |
| **Currency Catalog** | Fuente centralizada y versionada de países y monedas válidas (Unicode CLDR + overrides curados), generada en dev-time y commiteada. Única fuente de verdad para validar códigos de Country y Currency en el backend. |
| **Country** | Territorio ISO 3166-1 alpha-2 donde opera el negocio del Tenant. Se persiste el código; los nombres se localizan en el frontend. Disponible para Starter y Pro. |
| **Currency** | Moneda ISO 4217 en la que el Tenant expresa los precios de su catálogo. Pro-only. `NULL` = no configurada (la UI no muestra símbolo). |
| **Official Currency** | Moneda nacional vigente de un Country según el Currency Catalog. Se muestra primero (grupo separado) en el selector de moneda cuando el Tenant ha elegido ese país, sin sobreescribir la Currency guardada. |
| **Regional Settings** | Conjunto {Country, idioma, zona horaria, moneda} del Tenant con gating mixto: Country e idioma libres para Starter; zona horaria y Currency Pro-only. |
| **Public API Catalog** | Exposición pública read-only del Catalog de un tenant Pro para frontends externos. Publica servicios con planes anidados (incluyendo Catalog Price) más la Currency del Tenant en el response top-level, y no permite mutaciones. |
| **Public API Key** | Credencial tenant-scoped que habilita el Public API Catalog. Es visible para el tenant, revocable y regenerable; una key activa representa una integración pública de catálogo. Implementation table: `tenant_api_keys`. One row per tenant, plain-text `api_key`, JSON `allowed_origins`. |
| **Allowed Origin** | Origin web exacto registrado por el tenant para usar su Public API Key desde navegador. Incluye scheme, host y puerto opcional; no representa un dominio wildcard ni acceso server-to-server. |
| **Subscription** | Vincula un cliente, servicio y plan. Tiene credenciales encriptadas (Fernet), fechas de inicio/fin y estados (active/expired/cancelled). |
| **Mailbox** | The Tenant's single connected Gmail account used to retrieve access-code messages. It is connected exclusively through an App Password Connection. |
| **App Password Connection** | The sole Mailbox connection method. It uses a Google-generated, revocable app password instead of the account's primary password. Avoid the user-facing term **IMAP**. |
| **Mail Lookup Job** | Trabajo asíncrono de extracción de código: pending ↔ processing → completed/failed/timeout. Puede volver a pending cuando un Execution Lease recuperable vence antes del TTL global. |
| **Lookup Executor** | Runtime externo confiable, registrado por el Master, que ejecuta Mail Lookup Jobs fuera del backend web. Es independiente del proveedor de hosting. _Avoid_: Cloudflare Worker, Render Worker. |
| **Executor Hosting Account** | Referencia opcional, visible solo para el Master, a la cuenta externa donde está alojado un Lookup Executor. No es una credencial del propio executor ni de un Mailbox. _Avoid_: Worker account, Mailbox account. |
| **Execution Lease** | Asignación exclusiva y temporal de un Mail Lookup Job a un Lookup Executor. Al vencer sin resultado, el job vuelve a estar disponible para otro executor. _Avoid_: lock, reservation. |
| **Code Service** | Servicio de extracción de código (netflix, hbo, spotify, etc.). Tiene activación global (Master) y selección por tenant. |
| **Codigo** | Flujo de búsqueda de código de acceso via WhatsApp. El cliente selecciona servicio → ingresa email → el sistema busca en el mailbox. |
| **RLS** | Row-Level Security en PostgreSQL. Contexto de transacción: `app.current_user_id`, `app.current_role`, `app.active_tenant_id`. |
| **Contingency Reply** | Respuesta determinística cuando Redis está caído. Resetea al menú principal sin estado. |

## Starter/Pro Product Split

| Término | Definición |
|---------|------------|
| **TenantPlan** | Nivel de servicio del tenant: `starter` o `pro`. Source of truth: `tenants.plan` en la BD. El frontend lo usa solo como UI hint; la autorización real es backend. |
| **Pro Gate** | Dependency injection (`ProTenantId`) que bloquea endpoints Pro-only para tenants Starter retornando 404. Master en contexto de soporte bypass el gate. |
| **Access Control** | Módulo para bloquear/desbloquear identidades de WhatsApp. Afecta interacciones del bot y búsqueda de códigos, no cuentas de portal de clientes. |
| **BlockedClient** | Identidad de WhatsApp bloqueada. Una fila en `blocked_clients` representa un bloqueo activo; desbloquear elimina la fila. Bloquear y desbloquear son acciones terminales del Client Context Shortcut: el admin recibe confirmación privada y el contacto recibe una notificación genérica i18n en su `targetJid` original. |
| **Downgrade Effects** | Efectos secundarios al cambiar plan de Pro a Starter: revocar refresh sessions de clients, limpiar sesión admin Redis, intentar cerrar Evolution session (best-effort). |
| **Master Support Context** | Master con `active_tenant_id` seteado. Ve UI completa incluyendo datos Pro preservados, con banner de soporte visible. |
| **Public API Access** | Derecho Pro-only que permite usar y configurar el Public API Catalog. En downgrade a Starter se pausa el acceso público, pero se conserva la configuración para una futura reactivación. |

### Comportamiento por plan

| Aspecto | Starter | Pro |
|---------|---------|-----|
| Client login | 401 genérico (datos preservados) | Login normal |
| Clientes, Catálogo, Suscripciones | 404 (bloqueado por Pro Gate) | Accesible |
| Public API Catalog | 403 pausado si existe configuración preservada | Accesible con Public API Key + Allowed Origin |
| WhatsApp self-linking | Accesible si la instancia Evolution está configurada | Accesible si la instancia Evolution está configurada |
| Public API Key (Settings) | Oculto y bloqueado para tenant admin | Visible y gestionable |
| Regional Settings (país, idioma, zona horaria, moneda) | País e idioma visibles y editables; zona horaria y moneda ocultas y bloqueadas | Los 4 visibles y editables |
| Reminder settings | Oculto | Visible |
| Subscription jobs/reminders/cleanup | Ignorados completamente | Procesados |
| Search code flow | Requiere mailbox `connected` | Requiere mailbox `connected` |

## Arquitectura por capas

```
api → services → repositories → models
  ↓        ↓           ↓
schemas  core       models
```

- `api/` depende de `services` y `schemas`
- `services/` depende de `repositories`, `core` y `models`
- `repositories/` depende de `models` y `core`
- `core/` no tiene dependencias internas (excepto `config`)

## Módulos clave

| Módulo | Responsabilidad |
|--------|----------------|
| `app/api/v1/endpoints/integrations/` | Webhook de n8n, routing de WhatsApp, identidad, console handlers |
| `app/services/whatsapp_tenant_console_service/` | Menús y flujos del tenant (18 módulos) |
| `app/services/whatsapp_master_console_facade/` | Consola Master de WhatsApp |
| `app/services/whatsapp_client_console_facade/` | Consola Client (read-only) |
| `app/services/lookup_execution_coordinator/` | Queue acceleration, executor selection, Execution Leases, dispatch, and PostgreSQL reconciliation |
| `app/services/lookup_executor_transport/` | Signed/encrypted challenge, handoff, and callback transport |
| `app/services/lookup_executor_registry.py` | Master registry lifecycle, verification, rotation, and hosting-password controls |
| `worker/` (separate context) | External Gmail retrieval, MIME normalization, extraction, Netflix resolution, and callback delivery |
| `app/services/subscription_job_service/` | Limpieza y recordatorios de suscripciones |
| `app/core/i18n/` | Motor de localización (en/es) con catálogos en memoria |
| `app/core/input_validation/` | Validación centralizada de campos |
| `app/core/redis_client/` | Gestión HA de Redis con failover |
| `app/help/` | Compiled private Help artifact and strict bilingual Markdown contract |
| `app/api/v1/endpoints/help.py` | Authenticated, role/plan/locale-aware Help index, topic, and search API |


## Convenciones clave

- Todos los teléfonos se almacenan como dígitos sin prefijo `+`
- Navegación WhatsApp: `0`=cancelar, `8`=siguiente, `9`=regresar
- Estado de WhatsApp en Redis, nunca en DB
- Suscripciones con secretos encriptados via Fernet
- i18n: backend es source-of-truth, frontend consume via `/i18n/catalog`
- Tests: pytest + aiosqlite (in-memory), Redis fake, Evolution deshabilitado


## External lookup boundary

FastAPI creates durable Mail Lookup Jobs and coordinates them through Redis and
PostgreSQL. It does not execute Gmail retrieval, MIME parsing, Code Service
extraction, Netflix resolution, or a local result-cache fallback. The separate
`worker/` context receives a signed, AES-GCM encrypted handoff and returns a
signed encrypted callback. Redis result entries are ephemeral and encrypted;
PostgreSQL reconciliation makes pending jobs recoverable after Redis loss.
