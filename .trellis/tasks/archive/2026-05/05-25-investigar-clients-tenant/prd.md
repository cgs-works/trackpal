# PRD — Extender acceso cliente multi-tenant (dashboard + WhatsApp)

## Goal

Permitir acceso cliente por tenant en web y WhatsApp, con aislamiento estricto entre tenants, sin romper contrato Evolution Go + n8n ya migrado.

## User Value

- Cliente entra a su panel con cuenta propia por tenant.
- Cliente consulta estado de sus suscripciones activas.
- Cliente usa consola WhatsApp del tenant donde está registrado.
- Operación segura: mismo teléfono puede existir en tenants distintos sin fuga de datos.

## Confirmed Facts (evidencia repo)

- Login cliente ya existe en backend: `POST /api/v1/auth/login` + `AuthService`.
- JWT cliente ya incluye `active_tenant_id` cuando cliente/tenant activos.
- Frontend ya redirige `role=client` a `/client/dashboard`.
- Tabla `clients` ya permite mismo teléfono en tenants distintos (`UNIQUE tenant_id + phone`).
- Dashboard cliente actual devuelve perfil básico; no incluye lista de suscripciones activas en schema actual.
- Integración WhatsApp actual identifica por teléfono solo master/tenant (`users_repository.get_by_phone` no consulta `clients`).
- Endpoint consola (`/api/v1/integrations/n8n/console`) hoy enruta master/tenant; client cae en no acceso.
- Tarea archivada `05-25-migrar-evolution-go-n8n` ya definió contrato Evolution Go (path, triggers, send, close-status). Esta tarea debe ser compatible.

## Requirements

1. Cliente login web por username canónico de tenant + password.
2. Mantener modelo cuenta cliente separada por tenant (sin identidad global).
3. Dashboard cliente MVP debe mostrar:
   - perfil cliente tenant actual,
   - suscripciones activas tenant actual.
4. WhatsApp cliente:
   - resolver contexto de instancia primero,
   - si instancia == `MASTER_WHATSAPP_INSTANCE`: solo flujo master,
   - si instancia tenant: resolver tenant por instancia y luego identidad dentro de ese tenant,
   - resolver cliente por `(tenant_id, phone)`,
   - permitir solo cliente activo + tenant activo,
   - menú read-only (perfil + suscripciones activas).
5. Ambigüedad misma instancia (phone coincide como tenant y client): preguntar modo (`tenant` o `client`) y guardar elección en sesión actual hasta `0` o `/menu`.
6. Al entrar en modo client, avisar explícitamente que seguirá en modo cliente hasta salir con `0` o `/menu`.
7. Bloquear acceso WhatsApp cuando teléfono no pertenece a cliente precreado de ese tenant.
8. No alterar contrato Evolution Go/n8n migrado (payload/rutas/headers críticos).
9. Cobertura de tests para aislamiento cross-tenant y flujos cliente.

## Acceptance Criteria

- [ ] Login cliente válido retorna token usable y acceso a `/client/dashboard`.
- [ ] Login cliente falla si cliente inactivo o tenant inactivo.
- [ ] Dashboard cliente responde solo datos de tenant activo + suscripciones activas de ese tenant.
- [ ] Mismo teléfono en tenants distintos no causa colisión.
- [ ] WhatsApp cliente en tenant A nunca lee/escribe datos tenant B.
- [ ] Instancia `MASTER_WHATSAPP_INSTANCE` nunca enruta a tenant/client.
- [ ] Ambigüedad tenant+client en misma instancia pregunta modo y persiste en sesión actual hasta `0` o `/menu`.
- [ ] Al seleccionar modo cliente, sistema avisa persistencia de modo hasta salir (`0` o `/menu`).
- [ ] WhatsApp cliente no precreado recibe respuesta de acceso denegado/registro requerido.
- [ ] Menú WhatsApp cliente no expone mutaciones (solo lectura).
- [ ] Contratos Evolution Go/n8n existentes siguen pasando (sin regresión de integración).
- [ ] Tests backend nuevos/ajustados cubren casos anteriores.

## Out of Scope

- SSO global cliente entre tenants.
- Cuenta única cliente compartida entre tenants.
- Mutaciones por WhatsApp cliente (crear/editar/cancelar recursos).

## Constraints

- Compatibilidad obligatoria con migración archivada `05-25-migrar-evolution-go-n8n`.
- Cambios mínimos, enfocados en flujo cliente.

## Decisions Taken

- Mensaje para cliente no precreado/inactivo en WhatsApp: **"Acceso denegado, no tienes una cuenta activa."** (genérico, sin filtrar existencia en otros tenants).
- Verificación de ruteo primero por contexto de instancia.
- Instancia master definida por variable `MASTER_WHATSAPP_INSTANCE`.
- En colisión tenant+client en misma instancia, preguntar modo y guardar en sesión actual (no persistente en BD).
- Si elige modo cliente, notificar que seguirá en ese modo hasta salir con `0` o `/menu`.

## Open Questions

- Definir política exacta para colisión de teléfono dentro mismo tenant en flujo WhatsApp cliente cuando existan datos legacy inconsistentes (si apareciera más de un match).