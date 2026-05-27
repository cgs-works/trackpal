# Fix LID to JID resolution in WhatsApp flow

## Goal

Garantizar identificación correcta de remitente WhatsApp cuando Evolution entrega `remoteJid` con `@lid`, evitando tratar LID como número telefónico.

## Confirmed Facts

- Flujo actual: Evolution webhook -> `n8n/Trackpal WhatsApp Bot.json` -> `POST /api/v1/integrations/n8n/console`.
- En backend, `backend/app/api/v1/endpoints/integrations/console.py` usa `normalize_phone(request.phone)` antes de identificar usuario.
- `backend/app/core/phone.py` remueve sufijos JID con `_strip_phone_suffixes` y deja solo dígitos.
- Si entrada es `...@lid`, normalizador produce dígitos de LID (no phone real) y lookup falla.
- Test actual cubre JID phone (`@s.whatsapp.net`), no cubre caso `@lid`.
- En `evolution-go/pkg/webhook/service/listener.go`, payload chatbot envía `remoteJid` pero no envía campo alterno tipo `senderPn`/`remoteJidAlt`.
- En `evolution-api` (Express), existe swap cuando `remoteJid` es `@lid` y `remoteJidAlt` existe.

## Requirements

- Parse de n8n no debe convertir `@lid` en `phone`.
- Backend no debe tratar `@lid` como número telefónico válido para `identify_by_phone`.
- Extender `evolution-go` para enviar identificador alterno (`senderPn`/`remoteJidAlt`) cuando exista.
- Soportar resolución por LID persistido en base de datos cuando no exista PN resolvible.
- Agregar cobertura de tests para caso `@lid` en endpoint WhatsApp.

## Acceptance Criteria

- [ ] Con payload con `remoteJid` phone (`@s.whatsapp.net`), flujo actual sigue funcionando sin regresión.
- [ ] `evolution-go` incluye campo alterno de PN/JID en payload chatbot cuando mapping exista.
- [ ] Con payload `@lid` sin PN resolvible, Trackpal identifica por LID persistido en DB.
- [ ] Sistema nunca usa dígitos de LID como teléfono canónico.
- [ ] Tests backend de endpoint cubren casos `@s.whatsapp.net`, `@lid` con PN alterno, y `@lid` sin PN alterno.

## Decisions Locked

- Alcance: `Trackpal + evolution-go`.
- Sin PN resolvible: persistir LID en DB para matching.
- Entidades con `whatsapp_lid`: Master + Tenant + Client.
- Payload nuevo en webhook chatbot: `senderPn` + `senderLid`.
- Migración DB: columna nullable, llenado progresivo (sin backfill obligatorio inicial).

## User Intent Captured

- Usuario prefiere migrar/portar resolución LID→JID del Evolution API (Express) hacia `evolution-go`.
- Usuario aprobó alcance `Trackpal + evolution-go`.
- Usuario eligió persistir LID en DB cuando no exista PN resolvible.
