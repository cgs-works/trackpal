# Implement Plan — Migración Evolution Go + n8n

## Fase 1 — Backend Evolution client

- [ ] Actualizar `backend/app/services/evolution_client/client.py`:
  - [ ] Reemplazar `setup_n8n_integration` legacy por flujo webhooks (`create/find/update`).
  - [ ] Soportar resolución de `instanceId` tras create.
  - [ ] Reemplazar `close_chat_session` legacy o marcar deprecado si cierre queda en n8n.
  - [ ] Ajustar envío saliente helper a `/send/text` cuando aplique.

## Fase 2 — Persistencia token cifrado

- [ ] Definir ubicación token instancia (tenant o tabla credenciales).
- [ ] Crear migración DB.
- [ ] Implementar util cifrado app-layer con `DATA_ENCRYPTION_KEY`.
- [ ] Guardar token cifrado en create tenant.
- [ ] Exponer token desencriptado solo en payload interno de reminders.

## Fase 3 — Tenant lifecycle

- [ ] Ajustar `backend/app/services/tenant_service/mutations.py`:
  - [ ] create_instance + register_webhook + persist_token.
  - [ ] rollback total en fallos.
  - [ ] mantener delete_instance coherente.

## Fase 4 — n8n workflows

- [ ] `n8n/Trackpal WhatsApp Bot.json`:
  - [ ] webhook path -> `trackpalmastertenantclient` (no `trackpal-whatsapp-bot`).
  - [ ] parser payload Evolution Go (`chatInput`, `remoteJid`, `apiKey`).
  - [ ] send node -> `POST /send/text` con `apikey={{$json.apiKey}}`.
  - [ ] agregar nodo cierre sesión -> `POST /webhook/change-status` con `apikey={{$json.apiKey}}` y body `{remoteJid,status:"closed"}`.
- [ ] `n8n/Trackpal Subscription Reminders.json`:
  - [ ] send node -> `POST /send/text`.
  - [ ] header `apikey` desde `{{$json.evolution_instance_token}}` (NO global api key).

## Gate obligatorio (advisor)

- [ ] Confirmar en diff JSON que:
  - [ ] Bot webhook path final = `trackpalmastertenantclient`.
  - [ ] Existe nodo `change-status` en Bot.
  - [ ] Reminders no usa `$('Config').first().json.evolution_api_key` para send.

## Fase 5 — Tests

- [ ] Actualizar `backend/tests/test_evolution_client.py` endpoints/payloads nuevos.
- [ ] Ajustar tests tenant creation rollback por fallos webhook.
- [ ] Ajustar tests reminders payload para token cifrado/desencriptado.
- [ ] Correr suites objetivo.

## Fase 6 — Documentación

- [ ] Actualizar `docs/architecture/evolution-integration.md`.
- [ ] Actualizar `docs/architecture/n8n-workflow.md`.
- [ ] Actualizar secciones operativas/deploy relacionadas con endpoints y secretos.

## Validación

```bash
cd backend
uv run pytest -v tests/test_evolution_client.py
uv run pytest -v tests/test_tenants.py -k "evolution or create"
uv run pytest -v tests/test_subscriptions.py -k "reminder"
uv run pytest -v tests/test_whatsapp_endpoint.py
```

Smoke manual:
1) Crear tenant nuevo.
2) Verificar webhook en Evolution Go (`/webhook/find/:instanceId`).
3) Enviar `/menu` por WhatsApp y validar respuesta.
4) Ejecutar reminder pendiente y validar `POST /send/text` exitoso.
5) Validar cierre sesión chatbot por `change-status`.

## Riesgo alto archivos

- `backend/app/services/evolution_client/client.py`
- `backend/app/services/tenant_service/mutations.py`
- `backend/app/services/subscription_job_service/reminder_payloads.py`
- `n8n/Trackpal WhatsApp Bot.json`
- `n8n/Trackpal Subscription Reminders.json`

## Pre-start

- [ ] PRD aprobado.
- [ ] Design aprobado.
- [ ] Implement checklist aprobado.
- [ ] `implement.jsonl` y `check.jsonl` curados.
