# Design — Migración Evolution Go + n8n

## Scope

Migrar contratos de integración Evolution en backend + workflows n8n, manteniendo flujo funcional actual de consola y recordatorios.

## Arquitectura objetivo

### 1) Provisión tenant (backend)

Flujo `TenantService.create_tenant`:
1. Crear User/Tenant en transacción.
2. `EvolutionClient.create_instance(instance_name)`.
3. Resolver `instanceId` desde Evolution Go (`GET /instance/all` o `GET /instance/info/:instanceId`, según respuesta real de create).
4. Registrar webhook de consola por `instanceId`:
   - `POST /webhook/create/:instanceId`
   - payload: `enabled=true`, `webhookUrl=https://.../webhook/trackpalmastertenantclient`, `triggerType=keyword`, `triggerOperator=startsWith`, `triggerValue=/menu`, `isTrusted=true`.
5. Guardar token de instancia cifrado (app-layer, `DATA_ENCRYPTION_KEY`) para uso en reminders (`/send/text`).
6. Commit.

Si falla cualquier paso Evolution/webhook/token: rollback total.

### 2) Upsert webhook defensivo

Si `create` falla por duplicado/estado parcial:
1. `GET /webhook/find/:instanceId`
2. Buscar webhook objetivo por URL/path/description.
3. `PUT /webhook/update/:webhookId` para reconciliar contrato.

### 3) Consola WhatsApp (n8n + backend)

Se mantiene patrón:
- n8n recibe webhook Evolution Go.
- Parsea `chatInput`, `remoteJid`, `instanceName`, `instanceId`, `apiKey`.
- Llama backend `/api/v1/integrations/n8n/console`.
- Envía respuesta por `POST /send/text` con token de instancia (`apiKey` del payload).

Cierre de sesión:
- n8n llama `POST /webhook/change-status` con `apikey=<instance token>` y body `{remoteJid, status:"closed"}`.

### 4) Reminders

Workflow de recordatorios no recibe webhook entrante, por tanto obtiene token desde backend:
- endpoint pending retorna `evolution_instance_token` (desencriptado en runtime de backend; no en DB plano).
- n8n usa ese token en header `apikey` para `POST /send/text`.
- prohibido usar `evolution_api_key` global en node de envío reminders; rompería aislamiento multi-tenant.

## Cambios de datos

- DB: agregar campo token cifrado de instancia (en `tenants` o tabla dedicada de credenciales; preferible columna dedicada en tenant para alcance actual).
- Seguridad:
  - nunca persistir token plano.
  - cifrar al guardar, descifrar solo en uso.
  - clave: `DATA_ENCRYPTION_KEY`.

## Compatibilidad

- Solo nuevos tenants.
- Sin tenants existentes actualmente, sin backfill requerido.

## Riesgos y mitigaciones

- **Riesgo:** mismatch endpoint/docs Evolution create/info.
  - Mitigar: test integración con stub y validación manual en ambiente real.
- **Riesgo:** fuga token en logs n8n/backend.
  - Mitigar: sanitizar logs y evitar imprimir headers.
- **Riesgo:** estado parcial webhook.
  - Mitigar: upsert defensivo + rollback transaccional.

## Rollback

Revertir cambios de cliente Evolution + workflows n8n + migración DB token.
Dado inicio desde cero, rollback bajo impacto de datos productivos.
