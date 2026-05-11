# PRD: Scaffolding Inicial — Trackpal MVP

## Problem Statement

Trackpal es una plataforma B2B multi-tenant para gestión de suscripciones de streaming. Antes de implementar la lógica de negocio (clientes, suscripciones, servicios, flujos de WhatsApp con Evolution API), necesitamos establecer la base del sistema: el modelo de autenticación unificado, la gestión de tenants por parte del Master, los dashboards para cada rol, y la estructura del proyecto que permita integrar n8n como orquestador de mensajería.

Actualmente no existe código, configuración ni infraestructura. Este PRD define el MVP mínimo para tener un sistema funcional desde el login hasta los dashboards, con la API lista para que n8n pueda consumirla.

## Solution

Construir un monorepo con backend en Python (FastAPI + SQLAlchemy + UV) y frontend en Vue 3 + Vite, conectados a una base de datos Supabase PostgreSQL. Implementar:

- Autenticación unificada (Master y Tenant) con JWT + refresh tokens
- CRUD completo de tenants accesible solo por el Master, con soft-delete
- Dashboard del Master con lista de tenants y métricas resumen
- Dashboard del Tenant como placeholder post-login
- Endpoint de identificación para n8n protegido con API Key
- Workflow real de n8n con menú interactivo para CRUD via WhatsApp
- Semilla para crear el Master inicial con nombre, username, password y phone

## User Stories

1. Como **Master**, quiero iniciar sesión con mi username y contraseña, para acceder al dashboard de administración.

2. Como **Master**, quiero ver un dashboard con la lista de todos los tenants y métricas (totales, activos, inactivos), para tener visibilidad del estado del sistema.

3. Como **Master**, quiero crear un nuevo tenant proporcionando su nombre completo, email, username, y elegir entre generar contraseña automáticamente o ingresarla manualmente, para incorporar nuevas empresas a la plataforma.

4. Como **Master**, quiero ver el detalle de un tenant específico (full_name, email, phone, evolution_instance_name, estado activo/inactivo), para consultar su información.

5. Como **Master**, quiero editar los datos de un tenant (full_name, email, phone), para mantener la información actualizada.

6. Como **Master**, quiero desactivar un tenant sin eliminarlo, para suspender su acceso sin perder sus datos. Un tenant desactivado no puede iniciar sesión ni ser identificado por n8n.

7. Como **Master**, quiero reactivar un tenant previamente desactivado, para restaurar su acceso.

8. Como **Master**, quiero eliminar permanentemente un tenant solo si está previamente desactivado, para evitar borrados accidentales.

9. Como **Master**, quiero actualizar mi propio perfil (nombre, teléfono), para mantener mis datos correctos.

10. Como **Master**, quiero cambiar mi contraseña, por seguridad.

11. Como **Master**, quiero gestionar tenants desde WhatsApp mediante un menú interactivo en n8n, para operar la plataforma sin necesidad del dashboard.

12. Como **Tenant**, quiero iniciar sesión con mi username y contraseña en el mismo login que el Master, para acceder a mi dashboard.

13. Como **Tenant**, quiero ver una página de bienvenida al iniciar sesión que indique que el sistema está en construcción, para saber que el acceso funciona.

14. Como **Tenant**, quiero actualizar mi perfil (full_name, email, phone), para mantener mis datos actualizados.

15. Como **Tenant**, quiero cambiar mi contraseña, por seguridad.

16. Como **sistema**, quiero que el Master se cree mediante una semilla (seed) idempotente, con nombre, username, password y phone desde variables de entorno, para garantizar que siempre exista un super-administrador.

17. Como **sistema**, quiero que n8n pueda identificar a un usuario por su número de teléfono mediante un endpoint protegido con API Key, para asociar mensajes de WhatsApp con cuentas de Trackpal de forma segura.

18. Como **sistema**, quiero generar IDs UUID v4 para todos los registros, para evitar colisiones y no depender de secuencias auto-incrementales.

19. Como **sistema**, quiero que todas las contraseñas se almacenen hasheadas con bcrypt, por seguridad.

20. Como **sistema**, quiero implementar refresh tokens con rotación y tabla de sesiones, para mantener la seguridad de las sesiones.

21. Como **sistema**, quiero que el número de teléfono sea único entre todos los usuarios (Master y Tenants), para evitar conflictos en la identificación de WhatsApp.

22. Como **sistema**, quiero proteger que solo exista un único Master, para evitar duplicación del super-administrador.

23. Como **sistema**, quiero devolver mensajes de error claros y códigos HTTP apropiados (201, 400, 401, 403, 404, 409), para que el frontend y n8n puedan manejarlos correctamente.

## Modules

### Backend

- **Auth** — Login unificado JWT + refresh tokens con tabla `refresh_sessions`. Endpoints: `POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout`. Dependencias: `get_current_user` (JWT), `require_role` (middleware).
- **Tenants** — CRUD completo de tenants con soft-delete. Solo accesible por Master. Endpoints: `GET /tenants` (con metadata de totales), `POST /tenants`, `GET/PUT/DELETE /tenants/{id}`, `PATCH /tenants/{id}/deactivate|activate`. DELETE solo si `is_active = false`. La creación soporta auto-generación de contraseña o ingreso manual.
- **Profile** — Perfil del usuario autenticado según role. Endpoints: `GET/PUT /me`, `PUT /me/password`. Resuelve `master_profiles` o `tenant_profiles` según el role del JWT.
- **Integrations** — Endpoints para integraciones externas. Endpoint: `GET /integrations/n8n/identify?phone=`. Protegido con header `X-API-Key`. Busca en `master_profiles.phone` y `tenant_profiles.phone`. Retorna 404 si el tenant está desactivado o el teléfono no existe.
- **Dashboard** — Placeholder para Tenant. Endpoint: `GET /dashboard`. Retorna un mensaje de construcción y datos básicos del tenant.
- **Seed** — Script ejecutable con `uv run seed`. Crea el Master si no existe. Lee `MASTER_USERNAME`, `MASTER_PASSWORD`, `MASTER_NAME`, `MASTER_PHONE` de variables de entorno. Idempotente.

### Frontend

- **Login** — Página única con formulario username + password. Manejo de JWT + refresh token. Tras login exitoso, redirige según role: `/master/dashboard` o `/admin/dashboard`.
- **MasterDashboard** — Tabla paginada de tenants con búsqueda. Modal/formulario para crear/editar. Opción de auto-generar contraseña o ingresarla manualmente. Botones de activar/desactivar/eliminar por fila. Métricas resumen (total, activos, inactivos) en la parte superior.
- **TenantDashboard** — Página informativa: "Has iniciado sesión como [full_name]. El dashboard está en construcción." Acceso a perfil y cambio de contraseña.

### n8n

- **WhatsAppBot** — Workflow único implementado que recibe webhooks de Evolution API, se autentica con API Key contra Trackpal, identifica al usuario por teléfono, mantiene sesión en data table, muestra menú interactivo y ejecuta CRUD de tenants via HTTP a la API de Trackpal.

## Implementation Decisions

- **Stack backend**: Python + FastAPI + SQLAlchemy async + UV.
- **Stack frontend**: Vue 3 + Composition API + Vite.
- **Base de datos**: Supabase PostgreSQL con UUID v4 como primary keys. Migraciones con Alembic.
- **Estructura**: Monorepo con `backend/` y `frontend/`.
- **Autenticación**: Tabla `users` unificada con role (`master` | `tenant`). Perfiles separados en `master_profiles` y `tenant_profiles`.
- **Refresh tokens**: Tabla `refresh_sessions` con hash del token, expiración, flag de revocación. Rotación: cada refresh emite nuevo par access+refresh e invalida el anterior.
- **Login unificado**: Un solo endpoint de login. El frontend redirige según el role del JWT.
- **JWT**: Token con claims: `sub` (user UUID), `role`, `exp`. Access token: 15-30 min. Refresh token: 7 días.
- **Hash de contraseñas**: bcrypt via passlib.
- **Control de acceso por rol**: Dependencia `require_role('master')` en FastAPI, aplicada a nivel de router.
- **Eliminación de tenants**: Dos fases — desactivar (is_active = false) impide login e identificación n8n; luego eliminar permanentemente solo si ya está desactivado.
- **API versionada**: Prefijo `/api/v1/` en todas las rutas.
- **Endpoint n8n**: Ruta `/api/v1/integrations/n8n/identify`. Requiere header `X-API-Key` validado contra variable de entorno `N8N_API_KEY`.
- **Arquitectura backend**: Capas: models (SQLAlchemy) → schemas (Pydantic V2) → services (lógica + validaciones) → api (endpoints).
- **Phone único**: Validación cross-table en service layer. No puede existir el mismo phone en master_profiles y tenant_profiles.
- **Master único**: Seed idempotente + validación en service layer que bloquea creación de segundo Master.
- **Métricas dashboard**: `GET /tenants` devuelve `{ data: [...], meta: { total, active, inactive } }`.
- **n8n**: Workflow único implementado con Switch router. Sesiones gestionadas con data table de n8n. Comunicación vía HTTP Request a la API de Trackpal con API Key.
- **Contraseña en creación de tenant**: Dos opciones — auto-generada (back-end genera con mejores prácticas de seguridad) o manual (el usuario la escribe). Aplica tanto en dashboard como en WhatsApp.
- **Vinculación WhatsApp**: El número de teléfono es el identificador. n8n consulta `GET /integrations/n8n/identify?phone=X` con `X-API-Key` para reconocer al usuario.

## Testing Decisions

- **Backend**: Tests asíncronos con pytest + httpx. Base de datos en memoria (aiosqlite) para tests. Probar cada endpoint: status code, validación de schemas, control de acceso por rol, refresh token rotación, soft-delete (tenant desactivado no puede loguearse), phone único, imposibilidad de crear segundo Master.
- **Frontend**: Tests de componentes con Vitest + Vue Test Utils. Probar: renderizado de login, redirección por role, listado de tenants, formularios de crear/editar con opciones de contraseña, confirmación de eliminación.
- **n8n**: Validación con validate_workflow + pruebas manuales con el bot de WhatsApp conectado a instancia de desarrollo de Evolution API.
- **Prioridad**: Backend primero (API funcional y testeada), luego frontend (consume API), luego n8n (consume API con API Key).

## Out of Scope

- Gestión de customers (clientes finales de cada tenant)
- Gestión de suscripciones a servicios de streaming
- Servicios de streaming (Netflix, Disney+, etc.)
- Flujo de n8n para obtención de códigos de streaming vía email Gmail
- Multi-idioma (inglés/español)
- Generación de QR de Evolution API desde el dashboard (se hará manualmente)
- Dashboard funcional del Tenant (solo placeholder)
- Notificaciones, reminders o alertas
- Pipeline CI/CD
- Despliegue a producción

## Further Notes

- El orden de implementación sugerido: (1) estructura del proyecto, (2) modelos SQLAlchemy + migraciones Alembic, (3) seed del Master, (4) auth (login, refresh, logout, JWT, middleware), (5) CRUD de tenants con soft-delete, (6) perfil y dashboard, (7) integración n8n endpoint, (8) frontend login, (9) frontend dashboards, (10) workflow n8n real.
- El endpoint `GET /integrations/n8n/identify?phone=` es crítico para n8n. Debe estar protegido con API Key, buscar en ambas tablas de perfiles, y no retornar tenants desactivados.
- `master_profiles.phone` es obligatorio para que el Master pueda usar el bot de WhatsApp.
- La tabla `tenant_profiles.evolution_instance_name` se usará a futuro para vincular la instancia de Evolution API con el tenant.
- Los ADRs con las decisiones arquitectónicas están en `docs/adr/`.
- Las migraciones se gestionan con Alembic contra Supabase PostgreSQL.
