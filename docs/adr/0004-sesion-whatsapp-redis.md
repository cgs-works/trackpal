# Sesión de WhatsApp Master Console respaldada por Redis (HA)

Decidimos que el estado conversacional de la WhatsApp Master Console se
almacene en Redis con una arquitectura activa-pasiva, no en las data
tables de n8n ni en PostgreSQL. Redis es el almacén efímero de sesión
para cada conversación del Master, keyado por su número de teléfono
canonicalizado (solo dígitos, sin `+`).

## Contexto

La integración actual con n8n (ADR-0003) gestionaba originalmente el
estado de la conversación en una data table de n8n (`wa_sessions` con
`phone`, `step`, `temp_data`). Eso acoplaba la lógica conversacional al
orquestador, dificultaba las pruebas automatizadas, y hacía frágiles los
flujos multi-paso porque n8n debía mantener el estado entre ejecuciones
del webhook.

La ADR-0004 original adoptó Redis como almacén de sesión con un solo
cliente Redis, TTL de 30 minutos y sin estrategia de alta disponibilidad.
Para soportar carga alta y evitar puntos únicos de fallo, se requiere
una arquitectura HA con failover automático, circuit breaker, pools de
conexiones por proceso y limpieza explícita de sesiones.

## Decisión

- Redis almacena la sesión efímera de cada conversación del Master.
- La clave es el número de teléfono del Master canonicalizado
  (`PhoneNormalizer.normalize_phone()` → solo dígitos, sin `+`,
  sin sufijos `@c.us` / `@s.whatsapp.net`, sin sufijos `:device`).
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
- La sesión expira automáticamente con un TTL de **15 minutos** desde
  la última interacción válida (no se renueva por ruido o mensajes
  inválidos).
- El TTL es configurable mediante la variable de entorno
  `WHATSAPP_SESSION_TTL_MINUTES`.
- La sesión se **elimina explícitamente** al completar, cancelar o
  cerrar un flujo, además del TTL por expiración.
- El backend es el único que lee y escribe la sesión en Redis. n8n no
  tiene acceso directo a Redis.

### Arquitectura de alta disponibilidad

- **Redis activo-pasivo**: Redis principal atiende operación normal;
  Redis backup entra solo por contingencia.
- **No hay doble escritura** entre principal y backup.
- **Connection pooling por proceso**: cada worker del backend mantiene
  un pool de conexiones para Redis principal y otro para Redis backup
  durante todo su ciclo de vida (no se crean clientes por request).
- **Circuit breaker**: tras 3 fallos consecutivos del principal
  (configurable via `REDIS_FAILOVER_FAILURE_THRESHOLD`), el breaker
  abre y las operaciones se redirigen al backup.
- **Ventana de breaker abierto**: 30 segundos (configurable via
  `REDIS_BREAKER_OPEN_SECONDS`) antes de reintentar el principal en
  estado half-open.
- **Recuperación por tráfico real**: no hay health checks activos en
  segundo plano; la recuperación del principal se prueba solo cuando
  llega tráfico real.
- **Soporte TLS para backup**: la URL del backup acepta tanto
  `redis://` como `rediss://` según configuración, sin cambios
  arquitectónicos.
- **Timeouts cortos**: socket timeout y connect timeout de 5 segundos
  para detectar fallos de red rápidamente.

### Comportamiento en contingencia

- **Backup sin sesión activa**: si durante failover el backup no
  contiene la sesión activa, la conversación se reinicia y el Master
  recibe un mensaje claro de contingencia indicando que la sesión
  anterior no pudo recuperarse y debe seleccionar una opción del menú.
- **Ambos Redis no disponibles**: la consola responde con un mensaje de
  indisponibilidad temporal. No se permite degradar a flujo stateless.

## Flujo

```
WhatsApp → Evolution API → n8n (transport only)
                             ↓
                    canonicaliza phone + message
                             ↓
                    POST /api/v1/integrations/n8n/console
                    (X-API-Key, phone, message)
                             ↓
                    Backend:
                      1. Normaliza phone (PhoneNormalizer)
                      2. Identifica al Master por phone canonicalizado
                      3. Lee sesión actual de Redis (o crea nueva)
                      4. Procesa mensaje según flow/step actual
                      5. Actualiza sesión en Redis con TTL renovado
                         (solo en pasos válidos del flujo)
                      6. Produce texto de respuesta
                             ↓
                    n8n envía respuesta via Evolution API
```

## Implicaciones

- n8n se simplifica a transporte: recibe, canonicaliza, llama al
  backend, envía la respuesta. Ya no gestiona menús, steps, ni data
  tables de sesión.
- El backend puede probar la lógica conversacional sin n8n ni Redis
  real (usando un Redis fake o test double).
- Redis no contiene datos de negocio permanentes. Es solo estado de
  conversación efímero.
- Si Redis no está disponible, el backend debe fallar de forma segura
  con `ContingencyReplyPolicy.TEMPORARY_UNAVAILABLE` y no procesar la
  solicitud.
- La sesión expirada o en backup sin estado se trata como sesión nueva
  con mensaje explícito de contingencia.
- Los comandos de reseteo global (`0`, `menu`, `menú`, `cancelar`)
  eliminan la sesión actual en Redis y devuelven al menú principal.
- La canonicalización de phone se aplica consistentemente en:
  identificación del Master, persistencia en base de datos, keyado de
  sesión en Redis y búsqueda de tenants.
- La configuración de Redis HA (URLs, pool size, timeouts, breaker,
  TTL) se agrega al módulo `core/config.py` usando el patrón Pydantic
  Settings del proyecto.

## Módulos nuevos

| Módulo | Propósito |
|---|---|
| `app/core/phone.py` | `PhoneNormalizer.normalize_phone()` — canonicaliza phone a solo dígitos |
| `app/core/redis_client.py` | `RedisConnectionManager` — pools primario/backup, `FailoverPolicy`, circuit breaker |
| `app/services/whatsapp_session_service.py` | `WhatsAppSessionService` — CRUD de sesión efímera sobre Redis |
| `app/services/whatsapp_console_service.py` | `WhatsAppConsoleService` — ruteo conversacional, menús, flujos CRUD |
| `app/services/contingency_reply_policy.py` | `ContingencyReplyPolicy` — respuestas relayables para contingencia |

## Configuraciones

| Variable | Default | Descripción |
|---|---|---|
| `REDIS_URL` | `""` | URL de Redis (legacy, fallback si `REDIS_PRIMARY_URL` no está) |
| `REDIS_PRIMARY_URL` | `""` | URL de Redis principal (`redis://` o `rediss://`) |
| `REDIS_BACKUP_URL` | `""` | URL de Redis backup (`redis://` o `rediss://`) |
| `REDIS_POOL_SIZE` | `20` | Conexiones máximas por pool |
| `REDIS_SOCKET_TIMEOUT_SECONDS` | `5.0` | Timeout de socket |
| `REDIS_CONNECT_TIMEOUT_SECONDS` | `5.0` | Timeout de conexión |
| `REDIS_HEALTH_CHECK_INTERVAL_SECONDS` | `30.0` | Intervalo de health check |
| `REDIS_FAILOVER_FAILURE_THRESHOLD` | `3` | Fallos consecutivos antes de abrir breaker |
| `REDIS_BREAKER_OPEN_SECONDS` | `30` | Ventana de breaker abierto |
| `WHATSAPP_SESSION_TTL_MINUTES` | `15` | TTL de sesión conversacional |

## Estado

Aceptado.
