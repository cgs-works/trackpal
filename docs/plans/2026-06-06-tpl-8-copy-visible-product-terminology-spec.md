# TPL-8 Copy Visible y Terminología de Producto Spec

> Migrated to GentlePI / OpenSpec artifacts:
> - `openspec/changes/tpl-8-copy-visible-product-terminology/proposal.md`
> - `openspec/changes/tpl-8-copy-visible-product-terminology/specs/visible-product-copy/spec.md`
>
> This document remains as the original consolidated source brief.

Date: 2026-06-06
Related: Linear TPL-8, `spec-product-copy-terminology.md`
Status: Approved formal spec

## 1. Contexto

Hoy existen tres problemas simultáneos en superficies visibles del producto:

1. El término interno `tenant` aparece expuesto al usuario en web y WhatsApp.
2. Hay mezcla inconsistente de idiomas (`Tenant` dentro de copy en español).
3. El catálogo español del frontend y algunos mensajes de WhatsApp contienen mojibake / texto roto por encoding.

Este PR **no cambia el modelo de dominio** ni renombra artefactos internos. Solo corrige **copy visible**.

## 2. Decisión de producto

`tenant` puede seguir existiendo en código, modelos, rutas, payloads, stores, servicios, keys i18n y tests internos, pero **no debe aparecer en texto visible para usuarios**.

### 2.1 Terminología canónica por contexto

#### A. Master / administración de negocios

Usar cuando el usuario esté administrando entidades del catálogo principal.

| Contexto | Singular | Plural |
|---|---|---|
| ES | `empresa` | `empresas` |
| EN | `Business` | `Businesses` |

Ejemplos:
- `Total Tenants` → `Total Businesses`
- `Create Tenant` → `Create Business`
- `Lista de Tenants` → `Lista de empresas`
- `Detalle del Tenant` → `Detalle de la empresa`

#### B. Cliente final / catálogo consumido

Usar cuando el copy se refiera a la entidad vista por el cliente final.

| Contexto | Singular | Plural |
|---|---|---|
| ES | `proveedor` | `proveedores` |
| EN | `provider` | `providers` |

Ejemplos:
- label cliente `Tenant` → `Proveedor`
- label cliente `Tenant` → `Provider`

#### C. Modos de destinatario

No usar `tenant` como etiqueta visible.

Aprobado:
- ES:
  - `Solo administración`
  - `Administración y cliente`
- EN:
  - `Admin only`
  - `Admin and client`

## 3. Alcance

### 3.1 Frontend web

Archivo confirmado:
- `frontend/src/views/MasterDashboardView.vue`

Incluye:
- KPIs
- botones
- títulos de modal
- confirmaciones
- toasts
- mensajes de éxito/error
- labels CRUD

### 3.2 Catálogos i18n frontend

Archivos:
- `backend/app/core/i18n/catalogs_es_frontend.py`
- `backend/app/core/i18n/catalogs_en_frontend.py`

Incluye:
- `frontend.dashboard.tenant.*`
- contexto de soporte
- salida de contexto
- recipient modes
- labels visibles del dashboard cliente
- valores visibles con mojibake dentro del alcance

### 3.3 Master Console de WhatsApp

Archivos confirmados:
- `backend/app/services/whatsapp_console_service/messages.py`
- `backend/app/services/whatsapp_console_service/formatters.py`
- `backend/app/services/whatsapp_console_service/edit_messages.py`
- `backend/app/services/whatsapp_console_service/lifecycle_messages.py`
- `backend/app/services/whatsapp_console_service/create_confirm.py`
- `backend/app/services/contingency_reply_policy/policy.py`

Incluye:
- menú principal
- ayuda
- lista
- detalle
- crear
- editar
- desactivar / reactivar / eliminar
- mensajes de contingencia / fallback

### 3.4 Catálogos i18n WhatsApp

Archivos:
- `backend/app/core/i18n/catalogs_es_wa.py`
- `backend/app/core/i18n/catalogs_en_wa.py`

Incluye:
- perfil cliente
- contexto cliente
- cualquier string visible con `Tenant` o mojibake en el alcance

### 3.5 Tests

Actualizar cualquier test que aserte copy exacto viejo, especialmente en:
- `backend/tests/test_whatsapp_list_select_flow.py`
- `backend/tests/test_whatsapp_endpoint.py`
- `backend/tests/test_whatsapp_create_flow.py`
- `backend/tests/test_tenant_console_service.py`

## 4. Fuera de alcance

No forma parte de este PR:

- renombrar clases/modelos/servicios como `Tenant`, `TenantService`, etc.
- renombrar rutas o endpoints como `/tenants/...`
- renombrar keys i18n
- renombrar variables, archivos o stores
- cambios funcionales de flujo
- refactors de arquitectura i18n
- errores técnicos/API como `Tenant not found`
- barrido global de documentación técnica no afectada

`frontend/src/i18n/public.json` queda fuera de alcance salvo hallazgo puntual; actualmente se considera limpio.

## 5. Reglas de implementación

1. **Cambiar values/literales visibles, no nombres internos.**
2. **Corregir mojibake** en cualquier string visible tocado.
3. **No dejar mezclas ES/EN** como `Lista de Tenants` o `Salir de tenant`.
4. **Eliminar keys legacy visibles sin uso**, pero solo después de comprobar referencias.
5. Si una key legacy sí tiene uso indirecto real, **no se borra**: se actualiza su value.
6. Si durante la implementación aparecen más strings visibles del mismo flujo con copy viejo, también deben alinearse en el mismo PR.
7. Si hay docs o screenshots user-facing afectados por este cambio, se actualizan en el mismo PR.

## 6. Criterios de aceptación por superficie

### 6.1 Master Dashboard web

En `frontend/src/views/MasterDashboardView.vue`:
- no queda `Tenant` / `Tenants` visible
- el contexto Master usa `Business` / `Businesses`
- no se renombra lógica interna con `tenant`

### 6.2 Frontend i18n

Ejemplos obligatorios:
- `frontend.dashboard.tenant.exit_tenant`
  - ES: `Salir de la empresa`
- `frontend.dashboard.master_support`
  - ES: `Estás gestionando el catálogo de esta empresa en modo soporte`
- `frontend.subscriptions.recipient_mode_tenant_only`
  - ES: `Solo administración`
  - EN: `Admin only`
- `frontend.subscriptions.recipient_mode_both`
  - ES: `Administración y cliente`
  - EN: `Admin and client`
- `frontend.dashboard.client.tenant`
  - ES: `Proveedor`
  - EN: `Provider`

Además:
- no queda ningún value visible con `tenant`
- no queda mojibake en los values tocados

### 6.3 Master Console WhatsApp

Desaparecen textos como:
- `Ver Tenants`
- `Lista de Tenants`
- `Detalle del Tenant`
- `Crear Tenant`
- `Editar Tenant`
- `Tenant creado exitosamente`

En español visible se usa `empresa` y se corrigen acentos/legibilidad:
- `Opción inválida`
- `Teléfono`
- etc.

### 6.4 Catálogos WhatsApp

Ejemplos concretos:
- `wa.client.profile.body`
  - reemplazar label visible `Tenant:` por `Proveedor:` / `Provider:`
- `wa.tenant.client_context.collision`
  - eliminar `chat privado de Tenant`
- cualquier `wa.tenant.*` visible debe dejar de exponer `Tenant` al usuario

### 6.5 Keys legacy candidatas a eliminación

Hay candidatas claras en ambos catálogos WhatsApp:
- `wa.tenant.client_context.active.menu_text`
- `wa.tenant.client_context.active.invalid_option`
- `wa.tenant.client_context.inactive.menu_text`
- `wa.tenant.client_context.inactive.invalid_option`

Regla:
- si no tienen uso comprobado en `backend/`, `frontend/` y `backend/tests/`, se eliminan en ES y EN
- si aparece uso indirecto real, se mantienen pero se limpian sus values

## 7. Normalización lingüística obligatoria

Además del cambio terminológico, se debe corregir texto dañado por encoding en strings visibles.

Ejemplos:
- `sesiÃ³n` → `sesión`
- `ContraseÃ±a` → `Contraseña`
- `TelÃ©fono` → `Teléfono`
- `catÃ¡logo` → `catálogo`
- `Opcion invalida` → `Opción inválida`

Orden de prioridad si una cadena tiene varios problemas:
1. término de producto
2. idioma correcto por contexto
3. acentos / encoding / legibilidad

## 8. Actualización de documentación existente

La implementación debe actualizar la documentación existente que describa copy visible, labels, menús, ejemplos o screenshots afectados por este PR.

Reglas:
- actualizar la documentación **existente** antes de crear documentación nueva redundante
- corregir ejemplos visibles que todavía muestren `Tenant` / `tenant` cuando estén dirigidos a usuarios o soporte operativo
- actualizar screenshots, capturas, tablas o ejemplos de flujo si muestran copy anterior
- mantener `tenant` en documentación técnica cuando el término sea interno y correcto desde arquitectura o dominio

Revisión mínima obligatoria:
- `docs/architecture/whatsapp-console-flow.md`
- cualquier doc existente en `docs/` que cite literalmente menús, labels o mensajes visibles cambiados por este spec
- cualquier material de soporte operativo incluido en el PR

Criterio de aceptación documental:
- no queda documentación existente desalineada con el nuevo copy visible dentro del alcance
- no se reescribe documentación técnica sana solo por reemplazo cosmético del término interno `tenant`

## 9. Cláusula obligatoria para agentes de menor inteligencia

Cualquier agente de menor inteligencia, menor capacidad de razonamiento o contexto reducido que ejecute una tarea derivada de este spec debe **leer su tarea asignada en su totalidad antes de actuar**.

Obligaciones mínimas:
- leer el encargo completo, no solo el título, resumen, primeras líneas o snippets parciales
- identificar alcance, exclusiones, archivos afectados, criterios de aceptación y pasos de verificación antes de editar
- detenerse y pedir la tarea completa si el encargo recibido está truncado, resumido de forma ambigua o incompleto
- no ejecutar cambios basados en inferencias hechas desde instrucciones parciales

Esta cláusula es obligatoria para cualquier delegación, worker o subagente usado para implementar partes de este trabajo.

## 10. Verificación

### 10.1 Búsquedas estáticas

Confirmar que no queda `tenant` visible en:
- `frontend/src/views/MasterDashboardView.vue`
- `backend/app/core/i18n/catalogs_*_frontend.py`
- `backend/app/core/i18n/catalogs_*_wa.py`
- `backend/app/services/whatsapp_console_service/*`
- `backend/app/services/contingency_reply_policy/policy.py`

Confirmar también:
- no queda mojibake en strings visibles
- toda key eliminada fue validada contra referencias reales

### 10.2 Pruebas automatizadas mínimas

Backend:
```bash
cd backend && uv run pytest tests/test_whatsapp_list_select_flow.py tests/test_whatsapp_create_flow.py tests/test_whatsapp_endpoint.py tests/test_tenant_console_service.py
```

Frontend:
```bash
cd frontend && npm test
```

Si la implementación toca más aserciones o genera dudas, correr suite completa de backend:
```bash
cd backend && uv run pytest
```

### 10.3 Smoke tests manuales

#### Web Master Dashboard
- no aparece `Tenant` / `Tenants`
- se usa `Business` / `Businesses`

#### Frontend ES
- aparece `Salir de la empresa`
- aparece `Estás gestionando el catálogo de esta empresa en modo soporte`
- recipient modes usan el copy nuevo
- no hay acentos rotos

#### WhatsApp Master Console
Validar:
- menú principal
- ayuda
- lista
- detalle
- crear
- editar
- desactivar
- reactivar
- eliminar
- fallback/contingencia

Resultado esperado:
- se usa `empresa`
- no aparece `Tenant`
- no hay placeholders ni acentos rotos

#### WhatsApp cliente
- perfil muestra `Proveedor` / `Provider`
- los mensajes de contexto no dicen `Tenant`

## 11. Definition of Done

El PR queda terminado solo si:

- no queda `tenant` visible en ninguna superficie user-facing dentro del alcance
- la terminología canónica quedó aplicada por contexto
- el mojibake fue corregido en los strings tocados
- las keys legacy visibles sin uso comprobado fueron eliminadas en ES y EN
- los tests afectados fueron actualizados y pasan
- no se renombraron artefactos internos fuera de alcance
- no se debilitaron tests innecesariamente para acomodar el cambio de copy
- cualquier doc/screenshot user-facing afectado quedó actualizado
- la documentación existente afectada quedó sincronizada con el nuevo copy visible
- cualquier agente delegado leyó su tarea completa antes de ejecutar cambios
