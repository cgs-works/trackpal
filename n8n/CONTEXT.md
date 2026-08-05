# n8n Context

## Stack

- n8n workflow automation (self-hosted o cloud)
- 2 workflows exportados como JSON
- Comunicación con backend via HTTP requests
- Integración con Evolution API para WhatsApp

## Workflows

| Workflow | Archivo | Propósito |
|----------|---------|-----------|
| WhatsApp Bot | `TrackPal WhatsApp Bot.json` | Bridge webhook: recibe mensajes de Evolution → envía a backend → procesa respuesta → envía via Evolution |
| Subscription Reminders | `TrackPal Subscription Reminders.json` | Scheduler diario: genera recordatorios de suscripciones próximas a vencer |

## Vocabulario de dominio

| Término | Definición |
|---------|------------|
| **Parse Input** | Code node que extrae `phone` de `senderPn`. Si el inbound id es `@lid` y no hay PN, envía `phone` vacío + `sender_lid`. |
| **Console Call** | HTTP Request node que llama al backend `POST /api/v1/integrations/n8n/console` con el mensaje parseado. |
| **Evolution Send** | HTTP Request node que envía respuesta via `POST /send/text` de Evolution API. |
| **Config Set** | Node que contiene todos los valores de entorno (backend URL, API key, Evolution base URL). Referenciados via `$('Config').first().json.<field>`. |
| **Merge Reply** | Code node que proporciona fallback en español y fija `wait_deadline_at` 130 segundos después de iniciar un lookup. |
| **Register lookup resume** | HTTP node que registra `$execution.resumeUrl` en el backend para reanudar el workflow sin polling. |
| **Wait for lookup callback** | Wait node en modo webhook; reanuda inmediatamente con el callback terminal o al alcanzar el deadline absoluto. |
| **Final lookup status** | Único GET de fallback, ejecutado solo si el Wait vence sin callback. |
| **IF suppress lookup result** | Finaliza en silencio una ejecución anterior cuando su job fue cancelado por un retry de la misma sesión. |
| **reply_to** | Campo del backend que indica JID alternativo para envío (respuestas contextuales privadas al admin). |
| **no_reply** | Campo del backend que indica silencio — se salta el envío por Evolution. |
| **client_notification_target** | JID original del contacto remoto que debe recibir notificaciones terminales de bloqueo/desbloqueo. |
| **outbound_messages** | Lista backend-driven de mensajes extra que n8n debe transportar además de la respuesta privada primaria. |
| **close_jid** | JID canónico del teléfono para cierre de sesión. Fallback chain: `close_jid → reply_to → remoteJid`. |
| **senderPn** | Phone number del remitente en el payload de Evolution. |
| **sender_lid** | LID del remitente cuando no hay phone number disponible. |

## Convenciones n8n

### Config Set node pattern

Todos los valores de entorno viven en un solo node `Config`:
```js
$('Config').first().json.BACKEND_URL
$('Config').first().json.N8N_API_KEY
$('Config').first().json.EVOLUTION_BASE_URL
```

### Event-driven lookup delivery

Los lookups no hacen polling periódico. Después de enviar “buscando...”, n8n registra `$execution.resumeUrl`, suspende la ejecución hasta `wait_deadline_at` y procesa el callback terminal inmediatamente. El Wait usa la credencial Header Auth nativa `TrackPal Backend Resume Auth` (`X-API-Key` = `N8N_API_KEY`). Si el webhook no llega, hace exactamente un `Final lookup status` GET.

### neverError

Los HTTP Request nodes de Console Call, registro de resume y Evolution Send usan `neverError: true`. Esto previene que el workflow falle cuando backend o Evolution retornan non-2xx.

### Input normalization (Parse Input)

```js
// Priorizar senderPn sobre sender_lid
const phone = item.json.senderPn || "";
const sender_lid = !item.json.senderPn ? item.json.senderLid || "" : "";
```

### Reply fallback (Merge Reply)

Cuando el backend no retorna reply, usar mensaje estático en español. Si `no_reply=true`, saltar el envío.

### reply_to routing

Cuando el backend retorna `reply_to`, usar ese JID como destino en Evolution Send en vez del phone del remitente.

### no_reply silence

Cuando `no_reply=true`, el IF node rutea directamente a Check Close Session, saltándose todos los nodes de envío Evolution.

### close_jid propagation

Siempre setear `close_jid` al JID canónico del teléfono (ej. `584243106642@s.whatsapp.net`) para evitar fallback a LID que Evolution Go no puede matchear.

## Secrets

Ambos archivos JSON contienen valores de configuración en texto plano. El resume URL también es secreto transitorio y solo debe enviarse al backend HTTPS configurado. Tratar como secrets-bearing:
- `n8n/TrackPal WhatsApp Bot.json`
- `n8n/TrackPal Subscription Reminders.json`
