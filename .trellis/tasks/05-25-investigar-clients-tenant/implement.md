# Implement Plan — Cliente multi-tenant (web + WhatsApp)

## Checklist ordenado

1. **Backend auth/contexto**
   - Verificar `AuthService` para cliente con `active_tenant_id` consistente.
   - Confirmar dependencias que consumen `active_tenant_id` para rol client.

2. **Dashboard cliente (API)**
   - Extender schema `ClientDashboardResponse` con suscripciones activas.
   - Actualizar endpoint `GET /api/v1/dashboard` rama `role=client`.
   - Reusar servicio/repos existentes de subscriptions con filtro tenant+cliente.

3. **Frontend dashboard cliente**
   - Ajustar `ClientDashboardView.vue` para renderizar suscripciones activas.
   - Manejar vacío (`sin suscripciones activas`).

4. **WhatsApp consola cliente (read-only)**
   - Implementar/ajustar resolución de cliente por `(tenant_id, phone)` en contexto de instancia tenant.
   - Validar cliente/tenant activos antes de sesión.
   - Implementar menú lectura: perfil + suscripciones activas.
   - Bloquear no precreado con mensaje explícito.

5. **Aislamiento multi-tenant**
   - Auditar queries de teléfono/suscripciones para garantizar filtro tenant.
   - Revisar posibles rutas sin filtro tenant en flujo cliente.

6. **Tests backend**
   - Login cliente éxito/fallo (cliente inactivo, tenant inactivo).
   - Mismo teléfono en tenants distintos permitido.
   - Dashboard cliente devuelve solo datos tenant activo + suscripciones activas.
   - WhatsApp cliente: misma persona en tenant A/B no cruza datos.
   - WhatsApp cliente: no precreado => bloqueado.

## Validación (comandos)

```bash
cd backend
uv run pytest -v tests/test_auth.py tests/test_clients.py
uv run pytest -v -k "dashboard and client"
uv run pytest -v -k "whatsapp and client"
```

Si existe suite específica integraciones consola:

```bash
cd backend
uv run pytest -v -k "integrations and console"
```

## Archivos de riesgo

- `backend/app/services/auth_service/service.py`
- `backend/app/api/v1/endpoints/dashboard.py`
- `backend/app/schemas/dashboard.py`
- servicios/repos de subscriptions usados por dashboard cliente
- flujo consola WhatsApp tenant/client

## Puntos rollback

- Commit separado para dashboard web cliente.
- Commit separado para consola WhatsApp cliente.
- Si falla aislamiento: revertir bloque WhatsApp y mantener mejoras web.

## Pre-start checks

- PRD cerrado sin preguntas críticas.
- `design.md` y `implement.md` revisados por usuario.
- Si hace falta sub-agent manifests: curar `implement.jsonl` y `check.jsonl` con rutas de specs/tests clave.
