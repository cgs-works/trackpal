# Investigación completa — entidad `clients` (tenant) en Trackpal

Fecha: 2026-05-25  
Tarea: `.trellis/tasks/05-25-investigar-clients-tenant`

## 1) Cómo inician sesión clientes (estado actual real)

## Entry points

- API login: `POST /api/v1/auth/login`
  - Archivo: `backend/app/api/v1/endpoints/auth.py`
  - Llama `AuthService.authenticate(...)` y luego `AuthService.create_tokens(...)`.
- Frontend login:
  - Vista: `frontend/src/views/LoginView.vue`
  - Store: `frontend/src/stores/auth.js`
  - Router: `frontend/src/router/index.js` (redirige `role=client` a `/client/dashboard`).

## Flujo backend auth para cliente

Archivo: `backend/app/services/auth_service/service.py`

1. `authenticate(db, username, password)`:
   - Busca usuario por username exacto: `users_repository.get_by_username`.
   - Si `role in {"tenant","client"}` exige tenant activo con `_active_tenant_id_for_user`.
   - Verifica contraseña con `verify_password(...)`.

2. `_active_tenant_id_for_user(db, user)` para `role == "client"`:
   - Activa contexto interno RLS: `set_internal_rls_context(db)`.
   - Consulta `clients_repository.get_active_client_tenant_join(db, user.id)`.
   - Solo pasa si:
     - existe fila `Client` para ese `owner_user_id`
     - `Client.is_active = true`
     - `Tenant.is_active = true`
   - Devuelve `tenant_id` para claim JWT.

3. `create_tokens(...)`:
   - Crea access token con claims: `sub`, `role`, `active_tenant_id`.
   - Crea refresh token.
   - Guarda hash SHA-256 del refresh token en `refresh_sessions`.

## Casos cubiertos por tests

Archivo: `backend/tests/test_auth.py`

- `test_login_client_success`: login client OK, incluye `active_tenant_id`.
- `test_login_inactive_client_rejected`: cliente inactivo -> 401.
- `test_login_client_under_inactive_tenant_rejected`: tenant inactivo -> 401.
- `test_malformed_client_token_without_active_tenant_returns_401`: token client sin `active_tenant_id` -> 401 al consumir API.
- `test_refresh_token_client`: refresh client devuelve `active_tenant_id`.
- `test_refresh_token_client_under_inactive_tenant_rejected`: refresh rechazado si tenant fue desactivado.

## Conclusión login dashboard cliente

Login cliente **sí existe** y funciona con `username` canónico + contraseña; bloquea cliente/tenant inactivo; emite JWT con `active_tenant_id`.

---

## 2) Cómo se guardan clientes

## Modelo y relaciones

Archivo: `backend/app/models/client.py`

Tabla `clients`:
- `id` UUID PK
- `tenant_id` FK -> `tenants.id` (CASCADE)
- `owner_user_id` FK -> `users.id` (CASCADE)
- `full_name`
- `username` (canónico)
- `phone` nullable
- `is_active`

Constraints/índices:
- `uq_clients_owner_user_id` (1:1 client <-> user)
- `ix_clients_tenant_lower_username` unique (`tenant_id`, `lower(username)`)
- `ix_clients_tenant_phone` unique (`tenant_id`, `phone`)

Archivo: `backend/app/models/user.py`
- `users.username` global unique.
- relación `client_profile` con `cascade="all, delete-orphan"`.

## Creación/actualización

Archivo: `backend/app/services/client_service/service.py`

- Username canónico: `build_client_username(prefix, local_username)` -> `<prefix>_<local>`.
- `create_client(...)`:
  - valida `full_name/local_username/phone/password`
  - valida duplicados por tenant (`local_username_exists`, `phone_exists`)
  - valida username global (`users_repository.username_exists`)
  - crea `User(role="client", password_hash=get_password_hash(...))`
  - crea `Client(..., username=canonical_username, is_active=True)`
- `update_client(...)`:
  - recalcula username canónico si cambia local username
  - sincroniza `client.user.username` y `client.username`
- `deactivate_client(...)`:
  - `client.is_active=False`
  - revoca sesiones de usuario: `sessions_repository.revoke_all_for_user`
- `delete_client(...)`:
  - exige inactivo, si activo lanza `client_delete_active`
  - borra `User`; cascada elimina `Client` + refresh sessions

## Evidencia de reglas en tests

Archivo: `backend/tests/test_clients.py`

- `test_create_client`: username canónico generado (`tna01_client1`).
- `test_create_client_duplicate_local_username`: conflicto local username por tenant.
- `test_create_client_duplicate_phone`: phone duplicado mismo tenant -> 409.
- `test_local_username_update_syncs_login_username`: login viejo falla, login nuevo funciona.
- `test_prefix_update_syncs_client_usernames`: cambio `client_prefix` sincroniza logins.
- `test_deactivate_delete_client_removes_user`: flujo desactivar->eliminar.
- `test_delete_active_client_forbidden`: no elimina cliente activo.

---

## 3) Qué funciones tiene hoy entidad `clients`

## API REST de administración de clientes (rol tenant)

Archivo: `backend/app/api/v1/endpoints/clients.py`

- `GET /api/v1/clients`
- `POST /api/v1/clients`
- `GET /api/v1/clients/{client_id}`
- `PUT /api/v1/clients/{client_id}`
- `PATCH /api/v1/clients/{client_id}/deactivate`
- `PATCH /api/v1/clients/{client_id}/activate`
- `DELETE /api/v1/clients/{client_id}`

Permiso:
- `_require_tenant_user` bloquea no-tenant con 403.

## Repositorio

Archivo: `backend/app/repositories/clients_repository.py`

Funciones clave:
- `get(...)` cliente por tenant+id
- `get_active_client_tenant_join(...)` (auth client)
- `get_active_client_in_tenant(...)`
- `list_clients(...)`
- `local_username_exists(...)`
- `phone_exists(...)`
- `get_clients_with_user(...)` (sync masiva prefijo)

## Dashboard/perfil de cliente

- Endpoint dashboard: `backend/app/api/v1/endpoints/dashboard.py`
  - rama client retorna `ClientDashboardResponse`.
- Schema: `backend/app/schemas/dashboard.py`
  - hoy incluye datos de perfil/tenant, **no incluye suscripciones activas aún**.
- Perfil: `backend/app/api/v1/endpoints/me.py` + `backend/app/services/profile_service/service.py`
  - cliente puede consultar perfil y cambiar contraseña
  - update de perfil bloqueado para client (`PermissionError("Client profile is read-only")`).

---

## 4) WhatsApp y clientes — estado real vs objetivo

## Estado real hoy

Entry: `backend/app/api/v1/endpoints/integrations/console.py`

- Flujo identifica por phone con `auth_service.identify_by_phone(...)`.
- Ruteo actual:
  - `role == "master"` -> consola master
  - `role == "tenant"` -> consola tenant admin
  - otro rol -> `UNKNOWN_PHONE_REPLY`

`AuthService.identify_by_phone` depende de `users_repository.get_by_phone`.

Archivo: `backend/app/repositories/users_repository.py`
- `get_by_phone` busca solo en:
  - `master_profiles.phone`
  - `tenants.whatsapp_phone`
- **No busca en `clients.phone`**.

Resultado:
- Cliente por WhatsApp **no se identifica** hoy.
- Consola WhatsApp cliente por tenant **no implementada** aún.

## Implicación directa para tarea

Para cumplir objetivo cliente WhatsApp multi-tenant:
- ampliar identificación por teléfono para contexto tenant+client,
- rutar `role=client` a nuevo flujo cliente,
- resolver cliente por `(tenant_id, phone)` aislado por instancia tenant,
- bloquear no-precreados/no-activos.

---

## 5) Reglas de negocio explícitas e implícitas

1. Identidad cliente separada por tenant (1 user por client profile).
2. Username login de cliente canónico con prefijo tenant: `<prefix>_<local>`.
3. Teléfono único dentro de tenant (`tenant_id + phone`), no global.
4. Login client requiere cliente activo + tenant activo.
5. Client token debe llevar `active_tenant_id` para pasar dependencias RLS.
6. Cliente activo no se elimina; primero desactivar.
7. Cambio de `client_prefix` debe sincronizar usernames de `users` y `clients`.
8. Hoy WhatsApp soporta master/tenant; client aún fuera de flujo.

---

## 6) Aislamiento multi-tenant observado

Evidencia:
- Queries de cliente usan `tenant_id` en repos/servicios.
- Auth client obtiene tenant activo por join client+tenant activo.
- Test `test_cross_tenant_client_access_blocked` (`backend/tests/test_clients.py`) valida no acceso cross-tenant.

Riesgo pendiente para nueva implementación WhatsApp client:
- si identificación por phone no usa `tenant_id` de instancia, fuga posible.

---

## 7) Archivos fuente relevantes

## Backend núcleo clients/auth
- `backend/app/models/client.py`
- `backend/app/models/user.py`
- `backend/app/services/auth_service/service.py`
- `backend/app/services/client_service/service.py`
- `backend/app/repositories/clients_repository.py`
- `backend/app/repositories/users_repository.py`
- `backend/app/api/v1/endpoints/auth.py`
- `backend/app/api/v1/endpoints/clients.py`
- `backend/app/api/v1/endpoints/dashboard.py`
- `backend/app/schemas/dashboard.py`
- `backend/app/api/v1/endpoints/me.py`
- `backend/app/services/profile_service/service.py`

## WhatsApp/integraciones
- `backend/app/api/v1/endpoints/integrations/console.py`
- `backend/app/services/whatsapp_tenant_console_facade/facade.py`
- `backend/app/services/whatsapp_tenant_console_service/service.py`
- `backend/app/api/v1/endpoints/integrations/adapter.py`

## Documentación
- `docs/architecture/database-schema.md`

## Tests
- `backend/tests/test_auth.py`
- `backend/tests/test_clients.py`
- `backend/tests/test_tenant_console_service.py` (infra tenant console; no flujo client final)

---

## 8) Resumen ejecutivo

- Dashboard login cliente ya existe técnicamente en backend/frontend.
- Entidad `clients` ya soporta persistencia y aislamiento por tenant con username canónico y phone único por tenant.
- Gap real está en 2 frentes:
  1) dashboard cliente aún no expone suscripciones activas,
  2) consola WhatsApp cliente no existe: identificación por phone no contempla `clients` ni ruteo `role=client`.
- Base actual permite extensión segura si toda resolución por phone en WhatsApp se fuerza por `tenant_id` de instancia.