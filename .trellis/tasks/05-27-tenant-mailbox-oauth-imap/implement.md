# Implementation plan — tenant mailbox ingestion

## Execution status

- [x] Phase 0 — Prep
- [x] Phase 1 — Domain + persistence
- [x] Phase 2 — OAuth + IMAP config
- [x] Phase 3 — Extractor + catálogo regex
- [x] Phase 4 — Lookup jobs async
- [x] Phase 5 — Frontend tenant dashboard
- [x] Phase 6 — n8n workflow update
- [x] Phase 7 — Hardening

Final verification:
- `cd backend && uv run pytest -q` -> `1043 passed, 1 skipped`
- Frontend build validado en fase de implementación (`npm run build` OK)

## Phase 0 — Prep

1. Crear migraciones Alembic para tablas nuevas:
   - `tenant_mailboxes`
   - `mail_lookup_jobs`
   - `mail_code_delivery_log`
2. Agregar enums/constraints/índices.
3. Agregar variables env nuevas en `app/core/config.py`:
   - Google OAuth client/secret/redirect
   - Microsoft OAuth client/secret/tenant/redirect
   - Lookup timeout defaults

## Phase 1 — Domain + persistence

1. Modelos SQLAlchemy nuevos.
2. Repositorios:
   - mailbox config CRUD
   - lookup jobs CRUD/state transitions
   - dedupe log insert/check
3. Schemas Pydantic v2 para endpoints tenant + n8n.

Deliverable verificable:
- migraciones aplican y rollback limpio.
- tests repositorios pasan.

## Phase 2 — OAuth + IMAP config

1. Servicio OAuth Google (auth URL, exchange code, refresh, reconsent handling).
2. Servicio OAuth Microsoft (auth URL, exchange code, refresh).
3. Endpoint callbacks con validación `state` y tenant context.
4. Manejo explícito `invalid_grant`/refresh failures => mailbox `revoked` + reconexión requerida.
5. Servicio configuración IMAP + test de conexión.
6. Regla de exclusividad método activo.

Deliverable verificable:
- tests unitarios OAuth (mock HTTP) y IMAP test.
- endpoint tenant mailbox funcional en local.

## Phase 3 — Extractor + catálogo regex

1. Migrar `subjects.py` a catálogo backend `catalog_v1`.
2. Implementar extractor puro:
   - normalización subject/body
   - selección candidato más reciente
   - soporte `code` y `url`
3. Tests parametrizados por servicio.

Deliverable verificable:
- cobertura de regex claves (Netflix/Disney/HBO/Spotify/Universal/Prime).

## Phase 4 — Lookup jobs async

1. Endpoint n8n `POST /integrations/mail/lookups` (create job).
2. Endpoint `GET /integrations/mail/lookups/{id}` (status/result).
3. Worker central:
   - consume cola Redis
   - ejecuta fetch provider-specific
   - aplica extractor + dedupe (`Message-ID + fingerprint` con fallback sin Message-ID)
   - aplica retries transitorios con backoff dentro SLA
   - actualiza estado
4. Timeout SLA 20s en capa polling n8n.

Deliverable verificable:
- test integración API+worker con fake providers.
- dedupe `Message-ID + fingerprint` validado.

## Phase 5 — Frontend tenant dashboard

1. Nueva sección "Buzón de códigos" en Tenant dashboard.
2. Estados: disconnected/connected/error/revoked.
3. Acciones:
   - Conectar Google
   - Conectar Microsoft
   - Configurar IMAP app password
   - Test conexión
   - Desconectar

Deliverable verificable:
- flujo UI completo contra backend local.

## Phase 6 — n8n workflow update

1. Añadir trigger exacto en bot WhatsApp para `codigo|código|code`.
2. Backend consola gestiona diálogo de 2 pasos (servicio + email objetivo), n8n solo transporte.
3. Crear lookup job (`service_key` + `target_email`) y enviar mensaje inmediato "buscando...".
4. Polling status cada 4s con max wait 20s.
5. Branches:
   - found code/url
   - not_found
   - duplicate_suppressed (mensaje equivalente a no encontrado + esperar 15s)
   - timeout/error
6. Mantener aislamiento tenant (instance/token actual) y reply obligatorio en todos los caminos.
7. Validar contrato versionado de estados: `pending|processing|completed|failed|timeout`.

Deliverable verificable:
- ejecución n8n exitosa en casos found/not_found/timeout.

## Phase 7 — Hardening

1. Seguridad/log redaction.
2. Métricas y trazas operativas.
3. Job de cleanup y política retención para `mail_lookup_jobs` + `mail_code_delivery_log`.
4. Documentación arquitectura + runbook soporte.

Deliverable verificable:
- `trellis-check` completo + tests objetivo verdes.

---

## Test strategy

- Unit tests:
  - oauth services
  - token refresh (`invalid_grant` => `revoked`)
  - extractor regex
  - dedupe logic (con/sin Message-ID)
- Integration tests:
  - tenant mailbox endpoints
  - lookup create/status
  - worker state transitions
  - aislamiento: acceso cruzado por `job_id` entre tenants debe fallar
- Contract tests:
  - payload n8n↔backend
  - estados/result_type permitidos y mapping de errores seguros

## Rollout strategy

1. Feature flag por provider (`google_enabled`, `microsoft_enabled`).
2. Activar primero en staging con tenants piloto.
3. Monitorear dedupe hit rate, timeouts, errores OAuth.
4. Migrar tenants gradualmente desde bots legacy.

## Decisions closed

- `result_value` no se persiste en DB (`mail_lookup_jobs.result_value_encrypted` se mantiene null en v1).
- Rotación de secretos OAuth automática (client secrets y material de cifrado/tokens) con runbook, rollout gradual y validaciones de reconexión.
- Polling n8n aislado por tenant: `tenant_id` obligatorio en `GET /integrations/n8n/mail/lookups/{job_id}`.
- `target_email` obligatorio en create lookup y filtro por contenido (`subject/body`) aplicado en pipeline de extracción.
- Flujo WhatsApp de códigos usa 2 mensajes obligatorios: acuse inmediato + resultado final.
