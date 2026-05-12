# Integración n8n y Evolution API para WhatsApp

n8n es el orquestador de mensajería. Recibe mensajes de WhatsApp via
Evolution API, interpreta la acción y llama al backend FastAPI de
Trackpal para ejecutarla. Usa un solo workflow con router (Switch node)
que bifurca según la acción detectada.

## Endpoint de identificación

n8n identifica al usuario por número de teléfono mediante un endpoint
protegido con API Key:

`GET /api/v1/integrations/n8n/identify?phone=XXXX`

Header requerido: `X-API-Key` (valor configurado en variable de entorno
`N8N_API_KEY`).

Busca en `master_profiles.phone` y `tenant_profiles.phone`. Retorna
`user_id`, `role`, `username`. Si el tenant está desactivado o el
teléfono no existe, retorna 404.

## Flujo

```
WhatsApp → Evolution API → Webhook (n8n)
                             ↓
                          Code node (parsear + identificar usuario)
                             ↓
                          HTTP Request (FastAPI: /identify con X-API-Key)
                             ↓
                          Switch (router por acción)
                          ├─ "crear tenant"    → HTTP → FastAPI
                          ├─ "listar tenants"  → HTTP → FastAPI
                          ├─ "editar tenant"   → HTTP → FastAPI
                          └─ "ayuda"           → respuesta fija
                             ↓
                          Code node (formatear respuesta)
                             ↓
                          HTTP Request (Evolution API → enviar WhatsApp)
```

## Acciones por rol

- **Master** — CRUD completo de tenants desde WhatsApp.
- **Tenant** — placeholder (en construcción) por ahora.
- **Customer** — se definirá en futuras iteraciones.

## Creación de tenants desde WhatsApp

Cuando el Master crea un tenant, el menú pregunta:

1. "Generar contraseña automáticamente o ingresarla manualmente?"
2. Si auto-generada: backend genera contraseña segura, n8n la muestra
   UNA SOLA vez.
3. Si manual: el Master escribe la contraseña en el chat (se advierte
   el riesgo de seguridad).
4. En el dashboard del Master también aplican las mismas dos opciones.

## Sesiones

El estado de la conversación se gestiona con data table de n8n
(`phone`, `step`, `temp_data`).

## Workflow MVP creado en n8n

- Instancia n8n: `https://rs-n8n.wilfredocamacho.dev`
- Workflow: `Trackpal WhatsApp Bot`
- Workflow ID: `vtqUvdkNnTNcKnwj`
- Webhook path: `trackpal-whatsapp-bot`
- Webhook URL: `https://rs-n8n.wilfredocamacho.dev/webhook/trackpal-whatsapp-bot`
- Data table: `wa_sessions` (ID: `tOsSN3fuGDtB0Svf`, columnas: `phone`, `step`, `temp_data`, `created_at`, `updated_at`)
- 8 nodos: Webhook → Parse input → Identify user → Merge identity → Route by role → (Menu router | Access denied) → Evolution API Send

### Valores hardcodeados en el workflow

Dado que la licencia de n8n no permite gestionar variables desde la API pública, todos los valores están hardcodeados directamente en los nodos:

| Variable | Valor hardcodeado |
|---|---|
| Trackpal API URL | `https://c502-146-70-183-190.ngrok-free.app/api/v1` |
| Trackpal X-API-Key | `fXzqZpBtpAKC9ipa7St83cAYJadAK72P` |
| Evolution API URL | `https://rs-evoapi.wilfredocamacho.dev` |
| Evolution API Key | `B68769E2D248462C8F38DAF3CB7AE194` |

### Nodos del workflow

1. **Webhook** — POST en `/webhook/trackpal-whatsapp-bot`. Recibe payload de Evolution API.
2. **Parse input** (Code) — Extrae `phone`, `message` (cuerpo del texto), e `instance` del payload de Evolution API. Limpia sufijos `@c.us` / `@s.whatsapp.net` del número.
3. **Identify user** (HTTP Request) — `GET` a Trackpal API `/integrations/n8n/identify?phone={{phone}}` con header `X-API-Key: fXzqZpBtpAKC9ipa7St83cAYJadAK72P`.
4. **Merge identity** (Code) — Combina datos de entrada con la respuesta de identidad. Maneja 404 (usuario no encontrado).
5. **Route by role** (IF) — Si `role === "master"` continúa; si no, envía mensaje de acceso denegado.
6. **Menu router** (Code) — Analiza el mensaje numérico (1-8):
   - Menú principal con 8 opciones (Crear, Listar, Ver, Editar, Desactivar, Reactivar, Eliminar, Ayuda)
   - Si es opción 1 (Crear): establece step `awaiting_full_name`, guarda sesión
   - Si es opción 2 (Listar): step `list_tenants`
   - Si es opciones 3-7: step `awaiting_tenant_id`
   - Si es opción 8: muestra ayuda
   - Si no es válido: muestra menú nuevamente
7. **Access denied text** (Code) — Mensaje de error para no-Master.
8. **Evolution API Send** (HTTP Request) — `POST` a Evolution API `/message/sendText/{instance}` con header `apikey: B68769E2D248462C8F38DAF3CB7AE194`. Envía el texto manteniendo sesión.

### Notas operativas

- El URL de ngrok (`https://c502-146-70-183-190.ngrok-free.app`) cambia al reiniciar el túnel. Si cambia, se debe actualizar manualmente en el nodo "Identify user".
- El formato de número de teléfono en Evolution API no usa signo `+`. El workflow remueve `+` automáticamente antes de enviar.
- La funcionalidad completa de multi-paso (crear tenant con varios campos, CRUD completo) requiere nodos adicionales para manejar cada step de la sesión. Actualmente el workflow soporta el menú principal y enruta por opción.

## Rutas del frontend (Vue Router)

| Ruta                | Acceso  | Descripción                              |
| ------------------- | ------- | ---------------------------------------- |
| `/login`            | Público | Login unificado                          |
| `/master/dashboard` | Master  | Dashboard del Master con CRUD de tenants |
| `/admin/dashboard`  | Tenant  | Dashboard del Tenant (placeholder)       |
