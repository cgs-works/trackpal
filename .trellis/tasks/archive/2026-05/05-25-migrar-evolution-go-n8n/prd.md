# Migrar integración Evolution Go + n8n

## Goal

Migrar integración actual de Trackpal con Evolution API y workflows n8n hacia sistema nuevo de Evolution Go (webhooks multi-trigger), manteniendo provisión por tenant, aislamiento multi-tenant, y continuidad de consola WhatsApp + recordatorios.

## Confirmed Facts

- Backend actual usa `EvolutionClient` con:
  - `POST /instance/create`
  - `POST /n8n/create/{instance}`
  - `POST /n8n/changeStatus/{instance}`
  (`backend/app/services/evolution_client/client.py`)
- Docs internas Trackpal describen flujo legado con webhook path `trackpal-whatsapp-bot` y trigger `/menu` (`docs/architecture/evolution-integration.md`, `docs/architecture/n8n-workflow.md`).
- Workflow WhatsApp Bot actual llama backend `/api/v1/integrations/n8n/console` y luego envía por Evolution.
- Evolution Go nuevo expone:
  - `POST /webhook/create/:instanceId` (GlobalApiKey)
  - `GET /webhook/find/:instanceId`
  - `GET /webhook/fetch/:webhookId`
  - `PUT /webhook/update/:webhookId`
  - `DELETE /webhook/delete/:webhookId`
  - `POST /webhook/change-status` (token instancia)
  (`E:/Documentos/GitHub/evolution-go/docs/wiki/guias-api/api-webhooks.md`)
- Payload webhook nuevo incluye `chatInput`, `remoteJid`, `instanceName`, `instanceId`, y `apiKey` cuando `isTrusted=true`.
- En docs Evolution Go, envío de texto documentado por `POST /send/text`.

## Requirements

- Reemplazar uso de endpoints legacy `/n8n/create` y `/n8n/changeStatus/{instance}` por endpoints de webhooks/sesiones en Evolution Go.
- Mantener creación de instancia por tenant en lifecycle backend.
- Registrar webhook por tenant con trigger compatible con consola actual.
- Adaptar workflows n8n (bot + recordatorios) a contrato Evolution Go.
- Preservar aislamiento multi-tenant en ruteo por instancia.
- Soportar cierre de sesión chatbot con endpoint compatible Evolution Go.
- Persistir token de instancia en DB con cifrado app-layer para flujos salientes sin webhook (recordatorios).
- Actualizar tests backend afectados.
- Actualizar documentación completa relacionada.

## Acceptance Criteria

- [ ] Alta de tenant crea instancia y registra webhook funcional en Evolution Go.
- [ ] Webhook usa path `trackpalmastertenantclient`, trigger `keyword+startsWith+/menu`, `isTrusted=true`.
- [ ] Mensaje entrante procesa consola vía n8n+backend y respuesta llega a WhatsApp.
- [ ] Cierre de sesión usa `POST /webhook/change-status` desde n8n con token de instancia.
- [ ] Workflows bot y recordatorios envían por `POST /send/text`.
- [ ] Token de instancia se guarda cifrado con `DATA_ENCRYPTION_KEY`.
- [ ] Si falla provisión Evolution/webhook en alta tenant, operación hace rollback total.
- [ ] No hay mezcla de contexto entre tenants.
- [ ] Tests backend afectados pasan + smoke manual n8n/Evolution pasa.
- [ ] Documentación completa actualizada y alineada.

## Out of Scope

- Rediseño funcional de menús WhatsApp.
- Features nuevas de chatbot fuera de compatibilidad migración.

## Decisions Taken

- Mantener comportamiento funcional actual; cambiar solo contratos/endpoints necesarios.
- Migración aplica a nuevos tenants; estado actual sin tenants registrados.
- Registro webhook con upsert defensivo (`create` + `find/update` en reintentos/duplicados).
- Trigger webhook: `keyword`, `startsWith`, valor `/menu`.
- Path webhook n8n: `trackpalmastertenantclient`.
- `isTrusted=true` para incluir `apiKey` en payload.
- Cierre sesión vía n8n a `POST /webhook/change-status`.
- Envío saliente por `POST /send/text`.
- Persistir token instancia en DB cifrado app-layer.
- Clave de cifrado: `DATA_ENCRYPTION_KEY`.
- Fallo de provisión en alta tenant: rollback total.
- Validación mínima: tests backend afectados + smoke manual n8n/Evolution.
- Documentación: actualización completa.

## Open Questions

- Ninguna bloqueante por ahora.
