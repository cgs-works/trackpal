# Tenant mailbox ingestion with multi-OAuth and IMAP fallback

## Goal

Permitir que cada tenant configure un buzón técnico para extracción de códigos de acceso de servicios streaming sin desplegar bots Python por tenant, usando OAuth (Google/Microsoft) o IMAP app-password como alternativa exclusiva.

## Context

Sistema legacy (`pending-migration/imap_bot.py` + `subjects.py`) hace polling continuo por tenant y consume recursos altos. Nuevo diseño debe centralizar ejecución en backend Trackpal, mantener aislamiento por tenant y operar bajo demanda cuando n8n solicita código.

## Requirements

1. **Mailbox separada de contacto**
   - Mantener `tenants.email` como email de contacto.
   - Crear entidad/configuración separada para buzón técnico de códigos.

2. **Métodos de conexión**
   - Soportar OAuth2 delegado para:
     - Google (Gmail read-only + offline refresh).
     - Microsoft (Mail.Read delegado + refresh).
   - Soportar IMAP con app password como fallback alternativo.
   - Política: un solo método activo por buzón (OAuth o IMAP).

3. **Flujo de consulta bajo demanda**
   - No escaneo periódico continuo.
   - Solo buscar correos cuando n8n solicite código (`tenant + mailbox + servicio`).
   - Modelo asíncrono job/polling con timeout de 20s para n8n.

4. **Extracción de códigos**
   - Migrar reglas de `pending-migration/subjects.py` a catálogo global versionado backend.
   - Buscar en ventana reciente (5 min) y devolver código más reciente válido para servicio solicitado.

5. **Prevención de reenvío duplicado**
   - Persistir huella por entrega usando `Message-ID + fingerprint`.
   - Si falta `Message-ID`, usar fingerprint fallback (service + sender + fecha + subject + payload normalizado).
   - No reenviar mismo código/artefacto en ventana de consulta.

6. **Seguridad**
   - Cifrar secretos/tokens en reposo (aprovechar `app.core.encryption`).
   - Mínimo privilegio en scopes.
   - Manejo explícito de refresh OAuth inválido (`invalid_grant`): marcar mailbox `revoked` y requerir reconexión tenant.
   - Auditoría sin persistir código en texto plano.

7. **UI/UX tenant dashboard**
   - Configurar buzón técnico en Dashboard Tenant.
   - Botones de conexión OAuth Google/Microsoft.
   - Estado de conexión, método activo, pruebas de conexión, opción de desconectar.

8. **Flujo WhatsApp/n8n para solicitud de código**
   - Trigger exacto por mensaje: `codigo|código|code`.
   - Diálogo de selección (servicio y email objetivo) se maneja en backend de consola.
   - Lookup usa mailbox técnico centralizado del tenant; email objetivo del usuario se usa para filtrar contenido de correos.
   - Consolas habilitadas: Tenant + Client + Master (en práctica operativa, lookup ocurre en instancias tenant).
   - Respuesta siempre obligatoria al usuario; UX en 2 mensajes (`buscando...` + resultado final).

9. **Aislamiento multi-tenant**
   - Toda lectura, dedupe y entrega estrictamente acotada a tenant solicitante.

## Non-Goals

- No incluir Yahoo/Apple en v1.
- No mantener bots Python legacy como ruta principal.
- No polling continuo background de bandeja.

## Acceptance Criteria

- [x] Tenant puede conectar Gmail por OAuth y completar callback con estado `connected`.
- [x] Tenant puede conectar Outlook por OAuth y completar callback con estado `connected`.
- [x] Tenant puede configurar IMAP app-password como método alterno exclusivo.
- [x] n8n puede crear job de lookup y consultar estado hasta 20s con contrato explícito: `pending|processing|completed|failed|timeout`.
- [x] Lookup encuentra y devuelve código/URL más reciente dentro de 5 min cuando existe.
- [x] Lookup devuelve `not_found` sin error cuando no existe código válido.
- [x] Contrato de resultado polling define `result_type` permitido (`code|url|not_found|duplicate_suppressed`) y `result_value` solo en respuesta efímera.
- [x] Sistema no reenvía códigos ya entregados (dedupe por Message-ID + fingerprint, con fallback cuando falta Message-ID).
- [x] Si refresh OAuth falla con `invalid_grant`, mailbox pasa a `revoked` y dashboard exige reconexión.
- [x] Worker aplica retries transitorios con backoff dentro SLA 20s antes de marcar `failed`.
- [x] Existe política de retención/cleanup para `mail_lookup_jobs` y `mail_code_delivery_log`.
- [x] Tokens/credenciales quedan cifrados en DB; sin exposición en logs/responses.
- [x] Aislamiento multi-tenant validado: no se puede leer mailbox/job/log de otro tenant aunque se manipule `job_id` o `tenant_id` en request.
- [x] Rotación automática de secretos OAuth no rompe tenants conectados sin registrar estado (`connected|error|revoked`) y acción requerida.
- [x] Pruebas cubren Google/Microsoft token flow (mock), IMAP fallback, dedupe y aislamiento tenant.

## Implementation Status

Implementado en backend, frontend y n8n.

Principales artefactos:
- Migraciones: `backend/alembic/versions/cdbfefe74caa5_add_tenant_mailbox_tables.py`, `backend/alembic/versions/cdbfefe74caa6_add_target_email_and_fix_dedupe_unique.py`
- Modelos/repos/schemas: `backend/app/models/{tenant_mailbox,mail_lookup_job,mail_code_delivery_log}.py`, `backend/app/repositories/mailbox_*_repository.py`, `backend/app/schemas/mailbox.py`
- OAuth/IMAP: `backend/app/services/oauth_service/*`, `backend/app/services/imap_service.py`
- Worker/lookup: `backend/app/services/mail_lookup_worker/*`, `backend/app/api/v1/endpoints/integrations/mail_lookups.py`
- Extractor: `backend/app/services/mail_code_extractor/*`
- Tenant UI: `frontend/src/components/MailboxConfigPanel.vue` + integración en `frontend/src/views/TenantDashboardView.vue`
- Workflow n8n: `n8n/Trackpal WhatsApp Bot.json` (trigger `codigo|código|code`, mensaje inmediato + polling 4s/20s + resultado final)

Validación final ejecutada:
- `cd backend && uv run pytest -q` -> `1043 passed, 1 skipped`

## Constraints

- Backend FastAPI async + PostgreSQL + Redis HA.
- Integración n8n actual debe mantenerse compatible mediante contrato explícito nuevo.
- Cumplir convenciones backend y validación existente del proyecto.
