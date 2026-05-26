# Design — Login + Dashboard + WhatsApp Console Cliente Multi-tenant

## Arquitectura y límites

- Mantener modelo actual: `User` + `Client` 1:1 por tenant (`uq_clients_owner_user_id`).
- No identidad global cross-tenant en esta entrega.
- Tenant contextual en web por `active_tenant_id` claim JWT; en WhatsApp por instancia/tenant de webhook.

## Flujo web cliente

1. Login en `/api/v1/auth/login` con `username` canónico + password.
2. `AuthService` valida usuario, password, y tenant activo para rol `client`.
3. JWT incluye `role=client` y `active_tenant_id`.
4. Frontend redirige a `/client/dashboard`.
5. `GET /dashboard` para cliente retorna perfil + suscripciones activas tenant actual.

## Flujo WhatsApp cliente

1. Mensaje entra por instancia de tenant (contexto tenant resuelto por integración).
2. Normalizar teléfono remitente.
3. Buscar cliente por `(tenant_id, phone)` únicamente dentro tenant actual.
4. Validar `client.is_active` y `tenant.is_active`.
5. Si válido: iniciar contexto sesión consola cliente (read-only).
6. Si no válido/no existe: responder no autorizado/registro requerido.

## Contratos de datos

- `ClientDashboardResponse` se extiende con colección de suscripciones activas.
- Nuevo contrato de salida para menú WhatsApp cliente read-only:
  - Perfil cliente (nombre, username/local, teléfono, tenant).
  - Suscripciones activas (plan/servicio, estado, fechas relevantes).

## Trade-offs

- Elegido: cuentas separadas por tenant.
  - Pro: aislamiento fuerte, cambios acotados, menor riesgo.
  - Contra: mismo humano maneja múltiples credenciales.
- Elegido: WhatsApp solo precreado.
  - Pro: seguridad y control operativo.
  - Contra: más fricción onboarding inicial.

## Compatibilidad y migraciones

- Sin cambio de unicidad teléfono global; mantener único por tenant.
- Puede requerir ajustes de consultas por teléfono para forzar filtro por `tenant_id` en flujo WhatsApp cliente.
- Sin migración estructural mayor esperada salvo schema dashboard/API si hoy no incluye suscripciones.

## Operación / rollback

- Feature set incremental en endpoints/servicios existentes.
- Rollback: revertir cambios de dashboard cliente y flujo WhatsApp cliente; auth base ya estable.
- Verificación clave: no fuga cross-tenant en queries por teléfono ni suscripciones cliente.
