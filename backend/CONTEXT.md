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
| **Tenant** | Entidad que presta servicios. Tiene su propia instancia de Evolution WhatsApp, catálogo, clientes y suscripciones. Un tenant es un "empresa" en el sistema. |
| **Master** | Operador principal. Gestiona el ciclo de vida de tenants via WhatsApp Console y web dashboard. Solo hay una instancia. |
| **Client** | Cliente final de un tenant. Login compuesto: `{client_prefix}_{local_username}`. Solo puede ver perfil y cambiar contraseña. |
| **Evolution Instance** | Instancia de WhatsApp Business API (Evolution API/Go). Cada tenant tiene una, identificada por `evolution_instance_name`. |
| **WhatsApp Console** | Interfaz conversacional basada en menús numéricos (0=cancelar, 8=siguiente, 9=regresar). Existe para Master, Tenant y Client. |
| **Client Context Shortcut** | Sesión de WhatsApp que permite al Tenant gestionar clientes remotos desde su propia consola. |
| **Catalog** | Servicios y planes que un tenant ofrece. Cada servicio tiene planes con duración y precio. |
| **Subscription** | Vincula un cliente, servicio y plan. Tiene credenciales encriptadas (Fernet), fechas de inicio/fin y estados (active/expired/cancelled). |
| **Mailbox** | Conexión IMAP/OAuth (Google/Microsoft) de un tenant para extracción automática de códigos de acceso a streaming. |
| **Mail Lookup Job** | Trabajo asíncrono de extracción de código: pending → processing → completed/failed/timeout. |
| **Code Service** | Servicio de extracción de código (netflix, hbo, spotify, etc.). Tiene activación global (Master) y selección por tenant. |
| **Codigo** | Flujo de búsqueda de código de acceso via WhatsApp. El cliente selecciona servicio → ingresa email → el sistema busca en el mailbox. |
| **RLS** | Row-Level Security en PostgreSQL. Contexto de transacción: `app.current_user_id`, `app.current_role`, `app.active_tenant_id`. |
| **Contingency Reply** | Respuesta determinística cuando Redis está caído. Resetea al menú principal sin estado. |

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

## Convenciones clave

- Todos los teléfonos se almacenan como dígitos sin prefijo `+`
- Navegación WhatsApp: `0`=cancelar, `8`=siguiente, `9`=regresar
- Estado de WhatsApp en Redis, nunca en DB
- Suscripciones con secretos encriptados via Fernet
- i18n: backend es source-of-truth, frontend consume via `/i18n/catalog`
- Tests: pytest + aiosqlite (in-memory), Redis fake, Evolution deshabilitado
