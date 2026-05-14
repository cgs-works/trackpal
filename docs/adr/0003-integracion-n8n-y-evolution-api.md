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

> **Nota para Master Console:** El flujo transport-only (Phase 3+) **no
> llama a `/identify`** para autorización. La consola usa autenticación
> por credenciales (username + password) con sesión efímera en Redis
> (`wa:auth:{phone}`). El endpoint `/identify` se mantiene para otros
> usos (ej. identificación general de contacto) pero no interviene en
> el flujo de la consola Master.

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

El estado de la conversación se gestiona **exclusivamente en Redis**
por el backend FastAPI (ver ADR-0004). n8n ya no mantiene data tables
de sesión. La canonicalización del phone (solo dígitos, sin `+`) la
realiza el backend vía `PhoneNormalizer.normalize_phone()`.

## Workflow actual — Transport-only

El workflow transporta mensajes entre Evolution API y el backend sin
interpretar lógica de negocio. El backend (vía `WhatsAppConsoleService`)
posee toda la lógica conversacional, menús, estado de sesión en Redis
y decisiones CRUD.

- **Sin filtro de instancias:** n8n no discrimina por instancia de
  Evolution API. Todas las instancias llegan al mismo webhook y el
  backend maneja cualquier distinción necesaria.
- **Sin `/identify` para consola:** El workflow no llama a
  `GET /identify` para autorizar al Master. La autenticación se realiza
  mediante credenciales (username + password) directamente en el backend
  a través del endpoint `/console`.
- **Sin estado de sesión en n8n:** El workflow no mantiene data tables
  de sesión. Todo el estado conversacional y de autenticación reside en
  Redis, gestionado por el backend.

- Instancia n8n: `https://rs-n8n.wilfredocamacho.dev`
- Workflow: `Trackpal WhatsApp Bot`
- Workflow export: `n8n/Trackpal WhatsApp Bot.json`
- Webhook path: `trackpal-whatsapp-bot`
- 5 nodos: Webhook → Parse input → Console call → Merge reply → Evolution API Send

### Nodos del workflow transport-only

1. **Webhook** — POST en `/webhook/trackpal-whatsapp-bot`. Recibe payload de Evolution API.
2. **Parse input** (Code) — Extrae `phone`, `message` (cuerpo del texto), e `instance` del payload de Evolution API. Limpia sufijos `@c.us` / `@s.whatsapp.net` del número.
3. **Console call** (HTTP POST) — `POST /api/v1/integrations/n8n/console` con body `{phone, message, instance}` y header `X-API-Key`. El backend maneja toda la sesión y lógica.
4. **Merge reply** (Code) — Combina `phone`/`instance` originales con `reply` del backend.
5. **Evolution API Send** (HTTP Request) — `POST /message/sendText/{instance}` con el texto de respuesta.

### Notas operativas

- El placeholder `YOUR_TRACKPAL_API_URL` debe apuntar al backend FastAPI público.
- La canonicalización completa del phone (dígitos, sin `+`, sin sufijos JID) la realiza el backend vía `PhoneNormalizer.normalize_phone()`.
- La sesión conversacional se almacena en Redis con TTL de 15 minutos (ver ADR-0004 para la estrategia HA completa).
- Detalles completos del workflow en `docs/architecture/n8n-workflow.md`.

## Rutas del frontend (Vue Router)

| Ruta                | Acceso  | Descripción                              |
| ------------------- | ------- | ---------------------------------------- |
| `/login`            | Público | Login unificado                          |
| `/master/dashboard` | Master  | Dashboard del Master con CRUD de tenants |
| `/admin/dashboard`  | Tenant  | Dashboard del Tenant (placeholder)       |
