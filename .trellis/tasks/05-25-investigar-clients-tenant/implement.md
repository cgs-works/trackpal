# Implement Plan — Acceso cliente multi-tenant (web + WhatsApp)

## Objetivo ejecución

Entregar dashboard cliente con suscripciones activas + consola WhatsApp cliente read-only por tenant, sin romper integración Evolution Go/n8n migrada.

---

## Fase 0 — Precheck compatibilidad

- [ ] Revisar contratos vigentes de migración archivada (`05-25-migrar-evolution-go-n8n`):
  - [ ] webhook path/trigger esperado
  - [ ] payload entrante disponible en `console`
  - [ ] envío saliente `/send/text`
- [ ] Confirmar que cambios cliente no alteran esos contratos.

---

## Fase 1 — Dashboard cliente (backend)

- [ ] Extender schema `ClientDashboardResponse` con lista suscripciones activas.
- [ ] Definir sub-schema `ClientActiveSubscription` (id, service_name, plan_name, status, starts_at, expires_at).
- [ ] Actualizar `GET /api/v1/dashboard` rama client para incluir colección.
- [ ] Reusar servicio/repos de subscriptions con filtro estricto:
  - [ ] `tenant_id = active_tenant_id`
  - [ ] `client_id = client_profile.id`
  - [ ] estado activo.

Archivos probables:
- `backend/app/schemas/dashboard.py`
- `backend/app/api/v1/endpoints/dashboard.py`
- `backend/app/services/subscription_service/*` o repos asociados

---

## Fase 2 — Dashboard cliente (frontend)

- [ ] Actualizar `ClientDashboardView.vue` para pintar sección suscripciones activas.
- [ ] Mostrar estado vacío: “Sin suscripciones activas”.
- [ ] Mantener diseño mínimo sin nuevas rutas ni acciones mutables.

Archivo probable:
- `frontend/src/views/ClientDashboardView.vue`

---

## Fase 3 — Identidad WhatsApp cliente por tenant

- [ ] Ajustar resolución en endpoint consola con `instance-first routing`:
  - [ ] leer variable `MASTER_WHATSAPP_INSTANCE`
  - [ ] si `instance == MASTER_WHATSAPP_INSTANCE` enrutar solo master
  - [ ] si instancia tenant, resolver tenant por instancia
  - [ ] phone normalizado
  - [ ] lookup cliente por `(tenant_id, phone)`
- [ ] Validar `tenant.is_active` + `client.is_active`.
- [ ] Si no cumple: responder exacto
  - [ ] `"Acceso denegado, no tienes una cuenta activa."`

Archivos probables:
- `backend/app/api/v1/endpoints/integrations/console.py`
- repos/servicios auth/tenant/client involucrados en resolve

---

## Fase 4 — Consola WhatsApp cliente read-only

- [ ] Implementar facade/servicio cliente (nuevo o extensión limpia):
  - [ ] menú principal read-only
  - [ ] ver perfil
  - [ ] ver suscripciones activas
  - [ ] salir/cancelar sesión (retornar flag `status="closed"` para cumplir contrato n8n)
- [ ] Implementar manejo de ambigüedad tenant+client en misma instancia:
  - [ ] prompt "¿Cómo quieres proceder? 1) Tenant 2) Cliente"
  - [ ] guardar elección en sesión Redis actual
  - [ ] si elige client, enviar aviso de modo persistente hasta `0` o `/menu`
  - [ ] limpiar elección al salir (`0`/`/menu`/timeout)
- [ ] No exponer operaciones create/update/delete.
- [ ] Preservar intactas ramas master/tenant actuales.

Archivos probables:
- `backend/app/services/whatsapp_client_console_facade/*` (nuevo)
- `backend/app/services/whatsapp_client_console_service/*` (nuevo)
- o integración mínima en estructura existente de tenant console

---

## Fase 5 — Aislamiento y seguridad

- [ ] Auditar todas queries nuevas cliente/suscripciones WhatsApp para evitar lookup global por phone.
- [ ] Añadir hard-fail controlado si aparece ambigüedad de phone en mismo tenant (legacy inconsistente). Responder WhatsApp: "Error de cuenta. Múltiples registros encontrados. Contacta a soporte." (prevenir HTTP 500).
- [ ] Revisar logs: no exponer datos sensibles ni pistas de existencia cross-tenant.

---

## Fase 6 — Tests backend

- [ ] Auth cliente:
  - [ ] login éxito
  - [ ] cliente inactivo bloqueado
  - [ ] tenant inactivo bloqueado
- [ ] Dashboard cliente:
  - [ ] retorna solo suscripciones de tenant activo + cliente actual
  - [ ] no fuga cross-tenant
- [ ] WhatsApp cliente:
  - [ ] cliente precreado tenant A accede datos A
  - [ ] mismo phone en tenant B no mezcla datos
  - [ ] no precreado/inactivo devuelve mensaje genérico exacto
  - [ ] instancia `MASTER_WHATSAPP_INSTANCE` solo enruta master
  - [ ] ramas master/tenant sin regresión
  - [ ] ambigüedad tenant+client muestra prompt de modo
  - [ ] elección de modo persiste en sesión hasta `0` o `/menu`
  - [ ] al elegir client, muestra aviso de modo activo
  - [ ] "0. Salir" retorna payload `status="closed"` y limpia modo
  - [ ] duplicado legacy mismo tenant retorna mensaje de soporte (sin 500)

Suites objetivo:
- `backend/tests/test_auth.py`
- `backend/tests/test_clients.py`
- `backend/tests/test_tenant_console_service.py` (o nueva suite client console)
- tests dashboard/subscriptions relacionados

---

## Validación comandos

```bash
cd backend
uv run pytest -v tests/test_auth.py tests/test_clients.py
uv run pytest -v -k "dashboard and client"
uv run pytest -v -k "console and (tenant or client)"
uv run pytest -v -k "subscription and client"
```

Frontend smoke:

```bash
cd frontend
npm run build
```

---

## Gate anti-conflicto con tarea archivada

Antes de cerrar:
- [ ] Confirmar que no se tocó contrato webhook Evolution Go (path/trigger esperados).
- [ ] Confirmar que no se revirtió flujo `/send/text` ni close-status.
- [ ] Confirmar que endpoint `/integrations/n8n/console` sigue compatible con payload actual n8n.

---

## Rollback points

- Commit A: dashboard backend+frontend.
- Commit B: resolución/ruteo WhatsApp cliente.
- Commit C: tests.

Si falla aislamiento o compatibilidad integración:
- revertir Commit B primero,
- mantener Commit A si estable y validado.

---

## Ready-to-start criteria

- [ ] PRD cerrado con criterios testeables.
- [ ] Design aprobado.
- [ ] Implement checklist aprobado.
- [ ] Sin open questions bloqueantes.