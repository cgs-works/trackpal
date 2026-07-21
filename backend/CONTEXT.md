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
| **Tenant Onboarding Status** | The tenant-wide record of orientation-tour releases that were completed or skipped. It belongs to the Tenant rather than to an individual Tenant Admin. |
| **Master** | Operador principal. Gestiona el ciclo de vida de tenants via WhatsApp Console y web dashboard. Solo hay una instancia. Puede **switchear** a un tenant específico para soporte; en ese contexto ve la UI completa sin restricciones de plan. |
| **Client** | End customer of a Tenant. Uses the canonical login `{client_prefix}_{local_username}` and has read-only access to profile and active subscription information, Web password changes, and WhatsApp access-code lookup. Client access is unavailable while the Tenant is on Starter, although its data is preserved. |
| **Evolution Instance** | Instancia de WhatsApp Business API (Evolution API/Go). Cada tenant tiene una, identificada por `evolution_instance_name`. |
| **WhatsApp Console** | Interfaz conversacional basada en menús numéricos (0=cancelar, 8=siguiente, 9=regresar). Existe para Master, Tenant Admin y Client. |
| **Client Context Shortcut** | A private WhatsApp session in which a Tenant Admin manages a remote contact from the admin's own chat. The remote contact cannot see or operate the administrative menu. |
| **Catalog** | Servicios y planes que un tenant ofrece. Cada servicio tiene planes identificables por nombre; precios, disponibilidad y metadata no forman parte del catálogo v1. |
| **Public API Catalog** | Exposición pública read-only del Catalog de un tenant Pro para frontends externos. Publica servicios con planes anidados y no permite mutaciones. |
| **Public API Key** | Credencial tenant-scoped que habilita el Public API Catalog. Es visible para el tenant, revocable y regenerable; una key activa representa una integración pública de catálogo. Implementation table: `tenant_api_keys`. One row per tenant, plain-text `api_key`, JSON `allowed_origins`. |
| **Allowed Origin** | Origin web exacto registrado por el tenant para usar su Public API Key desde navegador. Incluye scheme, host y puerto opcional; no representa un dominio wildcard ni acceso server-to-server. |
| **Subscription** | Vincula un cliente, servicio y plan. Tiene credenciales encriptadas (Fernet), fechas de inicio/fin y estados (active/expired/cancelled). |
| **Mailbox** | Conexión IMAP/OAuth (Google/Microsoft) de un tenant para extracción automática de códigos de acceso a streaming. |
| **Mail Lookup Job** | Trabajo asíncrono de extracción de código: pending → processing → completed/failed/timeout. |
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
| Timezone (Settings) | Oculto y bloqueado para tenant admin | Visible y editable |
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
| `app/services/mail_lookup_worker/` | Worker asíncrono de extracción de códigos |
| `app/services/mail_code_extractor/` | Extracción regex por servicio (netflix, disney, spotify, etc.) |
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
