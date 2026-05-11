# Trackpal

Plataforma B2B multi-tenant para gestión de suscripciones de streaming.
Trackpal permite a empresas (tenants) gestionar sus clientes y las
suscripciones a servicios de streaming (Netflix, Disney+, etc.) que
ofrecen a sus clientes finales.

## Language

**Master**:
El dueño y operador único de la plataforma Trackpal. Crea y gestiona
tenants via dashboard o WhatsApp. Es ingresado en la base de datos
mediante semilla (seed).
_Avoid_: Superadmin, root, owner

**Tenant**:
Cada empresa cliente de Trackpal que utiliza la plataforma para
gestionar sus propios clientes y suscripciones de streaming.
_Avoid_: Admin, account, organization, cliente business

**Customer**:
Usuario final de cada **Tenant** que recibe acceso a servicios de
streaming a través de la plataforma.
_Avoid_: Client, end-user, subscriber

**Subscription**:
Registro de un **Customer** a un servicio de streaming específico
(Netflix, Disney+, etc.) gestionado a través de Trackpal.
_Avoid_: Plan, membership

**Service**:
Plataforma de streaming que se ofrece como producto (Netflix, Disney+,
HBO Max, etc.).
_Avoid_: Provider, streamer

**User**:
Entidad de autenticación unificada. Todo **Master** y **Tenant** tiene
un registro en la tabla `users` con UUID, username y password*hash.
El campo `role` diferencia el tipo ('master' | 'tenant').
\_Avoid*: Login, account, credential

**Evolution Instance**:
Conexión entre un número de WhatsApp y Trackpal via Evolution API.
Cada **Tenant** tiene una instancia identificada por un nombre único.
El **Master** crea la instancia manualmente desde el dashboard; el
**Tenant** escanea el QR para vincular su número.
_Avoid_: WA connection, instance

## Relationships

- Un **Master** puede crear y gestionar múltiples **Tenants**
- Un **Tenant** tiene exactamente un registro en **Users** (para login)
- Un **Tenant** gestionará múltiples **Customers** (a futuro)
- Un **Customer** puede tener una o más **Subscriptions** a distintos **Services**
- Un **Tenant** tiene exactamente una **Evolution Instance** vinculada

## Example dialogue

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

## Flagged ambiguities

| Ambiguity            | Resolución                                                      |
| -------------------- | --------------------------------------------------------------- |
| ¿Qué se trackea?     | Suscripciones a servicios de streaming (Netflix, Disney+, etc.) |
| ¿Quién es el Pal?    | El **Master** (dueño de la plataforma)                          |
| ¿Admin o Tenant?     | Se usará **Tenant** — cada cliente business de Trackpal         |
| Scope de "track"     | Gestión B2B de suscripciones                                    |
| Persistencia         | Supabase PostgreSQL                                             |
| Stack backend        | Python FastAPI + SQLAlchemy + UV                                |
| Stack frontend       | Vue 3 + Vite                                                    |
| Estructura repo      | Monorepo: backend/ y frontend/                                  |
| n8n + WhatsApp       | Evolution API + workflow único con router por acción            |
| Vinculación WhatsApp | QR de Evolution API, gestionado manualmente por ahora           |
| Multi-idioma         | Postergado — fuera del scope inicial                            |
