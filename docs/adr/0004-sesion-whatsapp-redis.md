# Sesión de WhatsApp Master Console respaldada por Redis

Decidimos que el estado conversacional de la WhatsApp Master Console se
almacene en Redis, no en las data tables de n8n ni en PostgreSQL. Redis
es el almacén efímero de sesión para cada conversación del Master,
keyado por su número de teléfono normalizado.

## Contexto

La integración actual con n8n (ADR-0003) gestiona el estado de la
conversación en una data table de n8n (`wa_sessions` con `phone`,
`step`, `temp_data`). Eso acopla la lógica conversacional al
orquestador, dificulta las pruebas automatizadas, y hace frágiles los
flujos multi-paso porque n8n debe mantener el estado entre ejecuciones
del webhook.

La WhatsApp Master Console (PRD `260512-0143-whatsapp-master-console`)
requiere flujos multi-paso predecibles: crear tenant, editar campos,
seleccionar tenant de una lista numerada, y confirmar acciones
destructivas. El backend debe ser el único propietario de las
transiciones de estado, validaciones y decisiones CRUD.

## Decisión

- Redis almacena la sesión efímera de cada conversación del Master.
- La clave es el número de teléfono del Master normalizado (sin `+`,
  sin sufijos `@c.us` / `@s.whatsapp.net`).
- Cada sesión contiene:
  - `flow` — flujo activo (ej. `main_menu`, `create_tenant`,
    `list_select`, `edit_tenant`, `deactivate`, `delete`).
  - `step` — paso dentro del flujo (ej. `awaiting_full_name`,
    `awaiting_confirmation`).
  - `selected_tenant_id` — UUID del tenant seleccionado, si aplica.
  - `temp_data` — datos parciales del formulario en curso (ej. campos
    recolectados durante la creación).
  - `selection_map` — mapeo de número mostrado en lista a UUID de
    tenant, para que el Master pueda seleccionar escribiendo `1`, `2`,
    etc.
- La sesión expira automáticamente con un TTL de 30 minutos desde la
  última interacción.
- El TTL es configurable mediante la variable de entorno
  `WHATSAPP_SESSION_TTL_MINUTES`.
- El backend es el único que lee y escribe la sesión en Redis. n8n no
  tiene acceso directo a Redis.

## Flujo

```
WhatsApp → Evolution API → n8n (transport only)
                             ↓
                    normaliza phone + message
                             ↓
                    POST /api/v1/integrations/n8n/console
                    (X-API-Key, phone, message)
                             ↓
                    Backend:
                      1. Identifica al Master por phone
                      2. Lee sesión actual de Redis (o crea nueva)
                      3. Procesa mensaje según flow/step actual
                      4. Actualiza sesión en Redis con TTL renovado
                      5. Produce texto de respuesta
                             ↓
                    n8n envía respuesta via Evolution API
```

## Implicaciones

- n8n se simplifica a transporte: recibe, normaliza, llama al backend,
  envía la respuesta. Ya no gestiona menús, steps, ni data tables de
  sesión.
- El backend puede probar la lógica conversacional sin n8n ni Redis
  real (usando un Redis fake o test double).
- Redis no contiene datos de negocio permanentes. Es solo estado de
  conversación efímero.
- Si Redis no está disponible, el backend debe fallar de forma segura
  con un error claro y no procesar la solicitud.
- La sesión expirada se trata como sesión nueva: el Master vuelve al
  menú principal sin datos residuales.
- Los comandos de reseteo global (`0`, `menu`, `menú`, `cancelar`)
  eliminan la sesión actual en Redis y devuelven al menú principal.
- La configuración de Redis (URL, TTL, client lifecycle) se agrega al
  módulo `core/config.py` existente usando el patrón Pydantic Settings
  del proyecto.

## Estado

Aceptado.
