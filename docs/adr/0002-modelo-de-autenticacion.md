# Modelo de autenticación unificado con perfiles separados

Tabla `users` unificada para login de Master y Tenant, con el campo
`role` ('master' | 'tenant') y tablas separadas `master_profiles` y
`tenant_profiles` para datos específicos de cada rol.

## Campos iniciales

**users**: id (UUID PK), username (UNIQUE), password_hash,
role ('master'|'tenant'), created_at, updated_at

**master_profiles**: id (UUID PK, FK -> users.id), name, phone,
created_at, updated_at

**tenant_profiles**: id (UUID PK, FK -> users.id), full_name, email,
phone, evolution_instance_name, is_active (default true),
created_at, updated_at

## Refresh tokens

Se implementa refresh token completo con tabla `refresh_sessions`:
id (UUID PK), user_id (FK -> users.id), refresh_token (hash),
expires_at, revoked (bool default false), created_at.

El access token expira en 15-30 min. El refresh token en 7 días.
Rotación: cada refresh emite un nuevo refresh token e invalida el
anterior.

## Control de acceso

- Tenant desactivado (is_active = false) no puede iniciar sesión.
- Tenant desactivado no aparece en el endpoint de identificación de n8n.
- Solo el Master puede reactivar un tenant.
- El endpoint de identificación para n8n requiere API Key via header.

## Restricciones

- El phone debe ser único entre todos los usuarios (validación cross-table
  en service layer).
- El Master es único: el seed es idempotente y el service layer bloquea
  la creación de un segundo Master.
- Todos los IDs son UUID v4 — no hay auto-incrementales.
- Migraciones gestionadas con Alembic.
