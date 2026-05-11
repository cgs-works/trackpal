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

## Rutas del frontend (Vue Router)

| Ruta                | Acceso  | Descripción                              |
| ------------------- | ------- | ---------------------------------------- |
| `/login`            | Público | Login unificado                          |
| `/master/dashboard` | Master  | Dashboard del Master con CRUD de tenants |
| `/admin/dashboard`  | Tenant  | Dashboard del Tenant (placeholder)       |
