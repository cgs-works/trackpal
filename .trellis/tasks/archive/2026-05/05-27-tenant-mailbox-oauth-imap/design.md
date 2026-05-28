# Design — tenant mailbox ingestion (Google + Microsoft OAuth, IMAP fallback)

## 1. Architecture

### 1.1 Components

- **Tenant Dashboard (frontend)**
  - Configura buzón técnico.
  - Inicia OAuth connect/disconnect.
  - Inicia test de conexión.

- **Backend API (FastAPI)**
  - Endpoints de configuración mailbox.
  - Endpoints OAuth start/callback.
  - Endpoints de lookup job (create/status/result).

- **Mailbox Lookup Worker (backend central)**
  - Procesa jobs asíncronos bajo demanda.
  - Lee buzón por proveedor/método activo.
  - Ejecuta parser regex global.
  - Aplica dedupe y retorna resultado.

- **Data stores**
  - PostgreSQL: configuración, tokens cifrados, jobs, logs de entrega/dedupe.
  - Redis: cola liviana de jobs + locks/coord.

- **n8n workflow**
  - Crea lookup job.
  - Polling status hasta timeout 20s.
  - Usa resultado para respuesta WhatsApp.

### 1.2 Flow (high-level)

1. Tenant conecta mailbox (OAuth o IMAP).
2. n8n solicita código (`tenant/service/mailbox`).
3. API crea job `pending`.
4. Worker toma job, consulta correo, extrae candidato más reciente (5 min), valida dedupe.
5. Worker marca `completed` (`found` o `not_found`).
6. n8n consulta estado y consume resultado.

## 2. Data model

## 2.1 `tenant_mailboxes`

Campos clave:
- `id` UUID PK
- `tenant_id` UUID FK unique (v1: un buzón por tenant; extensible luego)
- `mailbox_email` varchar(255)
- `provider` enum: `google|microsoft|imap_custom`
- `auth_method` enum: `oauth|imap_app_password`
- `status` enum: `disconnected|connected|error|revoked`
- `imap_host`, `imap_port`, `imap_ssl` (nullable)
- `oauth_access_token_encrypted` (nullable)
- `oauth_refresh_token_encrypted` (nullable)
- `oauth_token_expires_at` (nullable)
- `oauth_scope` (nullable)
- `imap_password_encrypted` (nullable)
- `last_connection_test_at`, `last_connection_error`
- timestamps

Regla exclusividad:
- Si `auth_method=oauth` => secretos IMAP null.
- Si `auth_method=imap_app_password` => tokens OAuth null.

## 2.2 `mail_lookup_jobs`

- `id` UUID PK
- `tenant_id` UUID FK
- `mailbox_id` UUID FK
- `service_key` varchar(64) (netflix/disney/etc)
- `requested_at`
- `status` enum: `pending|processing|completed|failed|timeout`
- `result_type` enum nullable: `code|url|not_found|duplicate_suppressed`
- `result_value_encrypted` nullable (opcional corto TTL; si se evita persistir valor, mantener null)
- `error_code`, `error_detail_safe`
- `expires_at` (TTL de job/result)

## 2.3 `mail_code_delivery_log`

- `id` UUID PK
- `tenant_id` UUID FK
- `mailbox_id` UUID FK
- `service_key` varchar(64)
- `message_id` varchar(500) nullable
- `fingerprint` varchar(128) not null
- `delivered_at`
- Unique compuesto sugerido: `(tenant_id, mailbox_id, service_key, message_id, fingerprint)`

## 3. OAuth design

### 3.1 Google

- OAuth authorization code flow server-side.
- Scopes mínimos:
  - `https://www.googleapis.com/auth/gmail.readonly`
  - openid/email/profile opcional para identidad UX.
- `access_type=offline`, `prompt=consent` según necesidad para refresh.

### 3.2 Microsoft

- Microsoft identity platform + delegated permissions.
- Scope mínimo:
  - `Mail.Read`
  - `offline_access`
  - `openid profile email` para identidad UX.

### 3.3 Token lifecycle

- Guardar tokens cifrados con `encrypt_value`.
- Renovar access token usando refresh token al expirar.
- Si refresh falla con `invalid_grant`: marcar mailbox `revoked`, limpiar tokens activos y forzar reconexión desde dashboard.
- Para Google, contemplar flujo de reconsent (`prompt=consent`) cuando no se reciba refresh token en exchanges posteriores.

## 4. IMAP fallback design

- Config manual tenant: host, port, ssl, email, app password.
- Test de conexión obligatorio al guardar.
- App password cifrada.
- Método exclusivo: activar IMAP desactiva OAuth y viceversa.

## 5. Lookup worker design

### 5.1 Trigger

- API `POST /mailboxes/lookups` crea job + enqueue Redis.

### 5.2 Processing

- Cargar mailbox por tenant.
- Calcular rango tiempo: now-5min..now.
- Query proveedor:
  - Google: Gmail API list/get.
  - Microsoft: Graph messages filter/order.
  - IMAP: search por fecha/flags y fetch acotado.
- Parse subject/body con catálogo global regex.
- Elegir candidato más reciente válido.
- Generar fingerprint (`sha256(service_key + normalized_payload)`).
- Revisar `mail_code_delivery_log`:
  - existe => `duplicate_suppressed`.
  - no existe => registrar entrega y retornar resultado.
- Dedupe key:
  - primary: `Message-ID + fingerprint`.
  - fallback (sin Message-ID): fingerprint derivado de `service + sender + received_at + subject + payload_normalized`.

### 5.3 Timeouts/retries

- Worker per-job timeout interno < 20s.
- Retries limitados solo para fallas transitorias red/API (Gmail/Graph/IMAP), con backoff corto y presupuesto total dentro del SLA.
- Errores no transitorios (credenciales inválidas/revoked/permisos) no reintentan; marcan estado seguro.

## 6. API contracts (draft)

### Tenant dashboard

- `GET /api/v1/tenant/mailbox`
- `PUT /api/v1/tenant/mailbox`
- `POST /api/v1/tenant/mailbox/test`
- `POST /api/v1/tenant/mailbox/oauth/{provider}/start`
- `GET  /api/v1/tenant/mailbox/oauth/{provider}/callback`
- `POST /api/v1/tenant/mailbox/disconnect`

### n8n lookup

- `POST /api/v1/integrations/n8n/mail/lookups`
  - input: `tenant_instance|tenant_id`, `service_key`, `target_email`, optional `mailbox_email`
  - output: `job_id`, `status=pending`
- `GET /api/v1/integrations/n8n/mail/lookups/{job_id}?tenant_id=<uuid>`
  - `tenant_id` requerido para aislamiento estricto en polling
  - output: `status` in `pending|processing|completed|failed|timeout`
  - on `completed`: `result_type` in `code|url|not_found|duplicate_suppressed`
  - `result_value` solo efímero en respuesta (no persistido)
  - errores con `error_code` seguro (sin secretos)

### WhatsApp workflow decisions (Phase 6)

- Trigger exacto para flujo de códigos: mensaje `codigo|código|code`.
- Orquestación conversacional en backend (no en n8n):
  1) seleccionar servicio,
  2) ingresar email objetivo.
- `service_key` cerrados v1: `disney`, `hbo_max`, `netflix`, `prime_video`, `spotify`, `universal`.
- Si tenant tiene catálogo propio de servicios registrados, backend muestra esos primero; si no, usa lista global compatible.
- Lookup filtra candidatos por `service_key` + `target_email` en contenido (subject/body).
- n8n responde siempre con 2 mensajes: acuse inmediato (`buscando...`) + resultado final.
- Polling n8n cada 4s hasta SLA 20s.
- `duplicate_suppressed` se comunica como "no se encontraron códigos recientes" + instrucción de esperar 15s y reintentar.

## 7. Regex catalog migration

- Mover `pending-migration/subjects.py` a módulo backend versionado:
  - `app/services/mail_code_extractor/catalog_v1.py`
- Crear parser puro + tests parametrizados por servicio.

## 8. Security

- No logs con código plano ni tokens.
- Cifrado en reposo para secretos.
- `result_value` no persistido en DB (respuesta efímera al poller).
- Sanitizar errores externos.
- RLS/tenant checks estrictos en endpoints tenant.
- Validación de ownership en jobs: `job_id` siempre filtrado por `tenant_id` resuelto del caller.
- Rotación automática de secretos OAuth (client secrets y material asociado) con política operativa documentada.
- Rotación con transición segura: estado mailbox `error|revoked` + acción de reconexión cuando falle refresh post-rotación.

## 9. Retention / cleanup

- `mail_lookup_jobs`: TTL corto (ej. 24-72h) y cleanup programado.
- `mail_code_delivery_log`: retención definida (ej. 30-90 días) según operación/dedupe.
- Limpieza automática con job backend programado y métricas de filas purgadas.

## 10. Observability

- Métricas:
  - `lookup_job_total{status,provider,service}`
  - latencia p50/p95
  - dedupe hit rate
- Auditoría:
  - connection changes
  - oauth connect/disconnect
  - lookup result summary (sin dato sensible)

## 11. Implemented architecture mapping

- API tenant mailbox: `backend/app/api/v1/endpoints/mailbox.py`
- API n8n lookup: `backend/app/api/v1/endpoints/integrations/mail_lookups.py`
- OAuth services: `backend/app/services/oauth_service/{google,microsoft,service}.py`
- IMAP connection/test: `backend/app/services/imap_service.py`
- Worker + queue + providers: `backend/app/services/mail_lookup_worker/*`
- Cleanup/retention: `backend/app/services/mailbox_cleanup.py`
- Metrics endpoint/registry: `backend/app/core/metrics.py`, `backend/app/main.py` (`/metrics`)
- WhatsApp codigo flow: `backend/app/services/whatsapp_tenant_console_service/codigo_flow.py`
- n8n workflow implementation: `n8n/Trackpal WhatsApp Bot.json`

## 12. Risks

- Consent/OAuth misconfig en clouds tenants.
- Variabilidad formatos email por servicio.
- Rate limits APIs Google/Microsoft.
- IMAP providers heterogéneos en fallback.

Mitigaciones:
- Feature flag por provider.
- Catálogo regex testeado y versionado.
- Retry/backoff + circuit breakers.
- Health endpoint worker + dashboards.
- Contrato n8n versionado y tests de contrato para estados/resultados.
