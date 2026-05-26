# Extender login y consola para clientes multi-tenant

## Goal

Permitir que clientes de tenants inicien sesión en dashboard cliente y usen consola WhatsApp cliente por tenant, aislando datos entre tenants.

## Confirmed Facts

- Ya existe `POST /api/v1/auth/login` y soporta rol `client` (`backend/app/api/v1/endpoints/auth.py`).
- Frontend ya tiene ruta protegida `/client/dashboard` rol `client` (`frontend/src/router/index.js`).
- Modelo actual `clients` fuerza 1:1 con `users` por `uq_clients_owner_user_id` (`backend/app/models/client.py`).
- `phone` no es global único; índice actual es único por tenant (`tenant_id`, `phone`) (`backend/app/models/client.py`).
- Login cliente actual depende de relación activa `client + tenant activo` (`AuthService` + tests auth/clientes investigados).

## Requirements

- Cliente debe poder autenticarse al dashboard cliente con credenciales de cuenta cliente por tenant.
- Mismo número telefónico permitido en tenants distintos sin colisión.
- Aislamiento estricto por tenant: acciones/datos en tenant A no afectan tenant B.
- Dashboard web cliente MVP debe mostrar perfil + suscripciones activas del tenant actual.
- Consola WhatsApp cliente: al escribir al número WhatsApp de tenant X, resolver cliente dentro de tenant X por teléfono y abrir sesión contextual de ese tenant.
- Acceso a menú WhatsApp cliente solo para clientes precreados en ese tenant.
- Menú WhatsApp cliente MVP: solo lectura (perfil + suscripciones activas), sin mutaciones.
- Mantener prefijo tenant en username canónico para evitar colisiones globales.

## Acceptance Criteria

- [ ] Cliente de tenant puede login y acceder `/client/dashboard` con JWT rol `client` y `active_tenant_id` correcto.
- [ ] Dashboard web cliente retorna perfil y suscripciones activas del tenant actual.
- [ ] Mismo teléfono puede existir en clientes de tenant A y tenant B sin error.
- [ ] Mensajes WhatsApp de cliente en instancia tenant A solo operan sobre datos de tenant A.
- [ ] Mensajes WhatsApp de cliente en instancia tenant B solo operan sobre datos de tenant B.
- [ ] Si teléfono no pertenece a cliente precreado en tenant de instancia WhatsApp, menú cliente se bloquea con respuesta de no autorizado/registro requerido.
- [ ] Menú WhatsApp cliente expone solo lectura de perfil + suscripciones activas.
- [ ] No hay fuga de datos cross-tenant en consultas clientes/suscripciones/dashboard cliente.
- [ ] Tests backend cubren login cliente, aislamiento multi-tenant por teléfono y flujo WhatsApp cliente.

## Out of Scope (propuesto)

- SSO global cliente entre tenants.
- Unificación de perfil global cliente entre tenants.

## Decisions Taken

- Modelo identidad: cuenta cliente separada por tenant.
- Teléfono: único dentro de cada tenant; reutilizable en tenants distintos.
- Login web cliente: `username` canónico (`prefijo_usuario`) + contraseña.
- WhatsApp auto-login: permitir solo con cliente activo y tenant activo.

## Open Questions

- Ninguna crítica por ahora.
