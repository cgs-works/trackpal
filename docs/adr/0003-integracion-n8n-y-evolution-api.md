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
- Trackpal API configurada para el workflow: `https://c502-146-70-183-190.ngrok-free.app/api/v1`
- Data table: `wa_sessions` (`phone`, `step`, `temp_data`, `created_at`, `updated_at`)

Notas operativas:

- El URL de ngrok puede cambiar al reiniciar el túnel; si cambia, se debe
  actualizar `TRACKPAL_API_URL` en el entorno de n8n.
- La licencia actual de n8n no permite gestionar variables desde la API
  pública (`/api/v1/variables`). Las variables requeridas por el workflow
  deben estar disponibles como variables de entorno del proceso n8n:
  `TRACKPAL_API_URL`, `N8N_API_KEY` y `EVOLUTION_API_URL`.

## Rutas del frontend (Vue Router)

| Ruta                | Acceso  | Descripción                              |
| ------------------- | ------- | ---------------------------------------- |
| `/login`            | Público | Login unificado                          |
| `/master/dashboard` | Master  | Dashboard del Master con CRUD de tenants |
| `/admin/dashboard`  | Tenant  | Dashboard del Tenant (placeholder)       |
