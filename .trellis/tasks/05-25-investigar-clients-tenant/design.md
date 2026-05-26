# Design — Acceso cliente multi-tenant (web + WhatsApp)

## Objetivo técnico

Extender experiencia cliente sin cambiar modelo identidad actual, garantizando aislamiento por tenant y compatibilidad total con migración Evolution Go + n8n ya archivada.

## Arquitectura y límites

## Se mantiene

- Modelo 1:1 `User(role=client)` ↔ `Client(owner_user_id)` por tenant.
- Login web por `username` canónico + password.
- Claim JWT `active_tenant_id` como contexto obligatorio para rol client.
- Contrato Evolution Go/n8n vigente (`/menu`, webhook path, `/send/text`, close-status).

## Se agrega

- Agregación de suscripciones activas en dashboard cliente.
- Resolución de identidad cliente por WhatsApp en contexto tenant (no global).
- Menú WhatsApp cliente read-only.

## No se agrega

- Identidad global cliente cross-tenant.
- Mutaciones en consola WhatsApp cliente.

---

## Diseño flujo web cliente

1. `POST /api/v1/auth/login` (ya existente).
2. `AuthService` valida:
   - usuario existe,
   - password válida,
   - `client.is_active` y `tenant.is_active` vía join activo.
3. `create_tokens` emite JWT con `role=client` + `active_tenant_id`.
4. Frontend enruta a `/client/dashboard`.
5. `GET /api/v1/dashboard` rama client retorna:
   - perfil cliente,
   - `active_subscriptions[]` tenant actual.

### Contrato respuesta dashboard cliente (MVP)

Extender `ClientDashboardResponse` con colección:
- `subscriptions: list[ClientActiveSubscription]`

`ClientActiveSubscription` mínimo:
- `id`
- `service_name`
- `plan_name`
- `status`
- `starts_at`
- `expires_at`

Filtrado obligatorio:
- `tenant_id == active_tenant_id`
- `client_id == perfil_cliente.id`
- estado activo (regla vigente de dominio)

---

## Diseño flujo WhatsApp cliente

## Entrada

`POST /api/v1/integrations/n8n/console` (existente)

## Resolución identidad (nuevo comportamiento)

1. Normalizar `instance` y `phone` remitente.
2. Si `instance == MASTER_WHATSAPP_INSTANCE`:
   - habilitar solo flujo master.
   - no evaluar rutas tenant/client.
3. Si `instance != MASTER_WHATSAPP_INSTANCE`:
   - resolver tenant dueño de esa instancia,
   - evaluar identidad dentro de ese tenant.
4. Identidad tenant/client dentro de instancia tenant:
   - match tenant admin por `tenant.whatsapp_phone`.
   - match client por **(tenant_id, phone)**.
5. Si solo hay match tenant -> flujo tenant.
6. Si solo hay match client -> flujo client.
7. Si hay ambos matches (ambigüedad): preguntar modo (`tenant`|`client`) y guardar elección en sesión Redis actual.
8. Si elige `client`, responder confirmación: opera en modo cliente hasta salir con `0` o `/menu`.
9. Si no hay match válido activo: responder
   - **"Acceso denegado, no tienes una cuenta activa."**

## Ruteo

Ruteo `instance-first`:
1. `instance == MASTER_WHATSAPP_INSTANCE` -> flujo master.
2. `instance tenant` -> resolver tenant por instancia.
3. Dentro instancia tenant:
   - match único tenant -> flujo tenant.
   - match único client -> flujo client.
   - match tenant+client -> prompt de selección de modo.

## Menú cliente MVP (read-only)

Opciones:
1. Ver perfil
2. Ver suscripciones activas
0. Salir (debe retornar `status: "closed"` a n8n para gatillar nodo `change-status` de Evolution Go y limpiar modo seleccionado en sesión)

Sin pasos de create/update/delete.

## Aislamiento

Toda query cliente/suscripciones en WhatsApp debe incluir:
- `tenant_id` resuelto por instancia,
- `client_id` del match en ese tenant.

Nunca resolver cliente WhatsApp con búsqueda global por phone únicamente.

---

## Contratos y componentes a tocar

## Backend

- `backend/app/api/v1/endpoints/dashboard.py`
- `backend/app/schemas/dashboard.py`
- servicio/repos subscriptions usados por dashboard client
- `backend/app/api/v1/endpoints/integrations/console.py`
- `backend/app/repositories/users_repository.py` (evitar lookup global inseguro para client whatsapp)
- nuevo servicio/fachada de consola cliente (paquete `whatsapp_client_console_*` o extensión controlada del tenant facade)

## Frontend

- `frontend/src/views/ClientDashboardView.vue` para renderizar suscripciones activas.

---

## Seguridad y privacidad

- Mensaje denegado genérico evita enumeración de existencia en otros tenants.
- No revelar tenant alterno ni estado detallado de cuenta por WhatsApp.
- Mantener validaciones de `active_tenant_id` en endpoints protegidos.

---

## Compatibilidad con tarea archivada Evolution Go

Invariante:
- No cambiar path/trigger ni payload base webhook ya migrado.
- No revertir `/send/text` ni close-status establecidos.
- Cambios cliente se montan encima del contrato ya vigente.

---

## Riesgos y mitigaciones

1. **Riesgo:** fuga cross-tenant por lookup phone global.
   - Mitigación: lookup cliente forzado por `(tenant_id, phone)`.

2. **Riesgo:** regressión consola master/tenant.
   - Mitigación: ruteo por rol preserva ramas existentes; tests regresión.

3. **Riesgo:** inconsistencia datos legacy (phone duplicado inesperado mismo tenant).
   - Mitigación: hard-fail controlado + log de seguridad + mensaje genérico.

4. **Riesgo:** dashboard cliente filtra mal suscripciones.
   - Mitigación: filtro dual `tenant_id` + `client_id`, tests explícitos.

---

## Rollback

- Rollback por bloques:
  1) dashboard cliente (schema + endpoint + view),
  2) ruteo WhatsApp cliente.
- Mantener base auth/login intacta para minimizar impacto.