# TPL-8 Copy Visible y Terminología de Producto Design

Date: 2026-06-06
Related: Linear TPL-8
Status: Draft consolidado para implementación

## Purpose

Eliminar la exposición user-facing del término interno `tenant` en las superficies visibles incluidas en este trabajo, normalizar la terminología de producto por contexto y corregir mojibake/acentos rotos en el mismo recorrido, sin renombrar artefactos internos ni cambiar comportamiento funcional.

Este trabajo es de **copy visible** y de **alineación documental user-facing**. No es un rename de dominio.

## Product decision

`tenant` puede seguir existiendo en:

- clases, modelos, servicios y repositorios
- rutas y payloads API
- nombres de archivos
- stores y variables
- claves i18n
- tests internos cuando el término sea técnico y no visible al usuario
- documentación técnica donde `tenant` sea correcto como término de arquitectura

Pero `tenant` **no debe aparecer en texto visible para usuarios o soporte operativo** dentro del alcance de este trabajo.

## Canonical terminology by context

### 1. Master / administración de negocios

Cuando el usuario administra entidades del catálogo principal:

| Locale | Singular | Plural |
|---|---|---|
| ES | `empresa` | `empresas` |
| EN | `Business` | `Businesses` |

Ejemplos obligatorios:
- `Ver Tenants` -> `Ver empresas`
- `Lista de Tenants` -> `Lista de empresas`
- `Detalle del Tenant` -> `Detalle de la empresa`
- `Create Tenant` -> `Create Business`
- `Exit tenant` -> `Exit business context` o equivalente visible natural

### 2. Cliente final / catálogo consumido

Cuando el copy se refiere a la entidad vista por el cliente final:

| Locale | Singular | Plural |
|---|---|---|
| ES | `proveedor` | `proveedores` |
| EN | `Provider` | `Providers` |

Ejemplos obligatorios:
- label visible `Tenant` -> `Proveedor`
- label visible `Tenant:` -> `Proveedor:` / `Provider:`

### 3. Recipient modes / destinatarios

No se usa `tenant` como etiqueta visible.

Valores aprobados:
- ES `Solo administración`
- ES `Administración y cliente`
- EN `Admin only`
- EN `Admin and client`

## In scope

### A. Frontend web visible copy

Archivo confirmado:
- `frontend/src/views/MasterDashboardView.vue`

Incluye:
- KPIs
- botones
- títulos
- modales
- confirmaciones
- toasts
- labels CRUD
- textos visibles del contexto soporte/master

### B. Frontend i18n catalogs

Archivos confirmados:
- `backend/app/core/i18n/catalogs_es_frontend.py`
- `backend/app/core/i18n/catalogs_en_frontend.py`

Claves/hotspots ya confirmados:
- `frontend.dashboard.master_support`
- `frontend.dashboard.tenant.exit_tenant`
- `frontend.subscriptions.recipient_mode_tenant_only`
- `frontend.subscriptions.recipient_mode_both`
- `frontend.dashboard.client.tenant`

Regla: se actualizan los **values visibles**, no las keys.

### C. Master Console WhatsApp visible copy

La superficie visible está repartida entre varios módulos hardcoded del Master Console. El alcance no debe limitarse solo a seis archivos si aparecen más literales del mismo flujo.

Hot files confirmados:
- `backend/app/services/whatsapp_console_service/messages.py`
- `backend/app/services/whatsapp_console_service/formatters.py`
- `backend/app/services/whatsapp_console_service/create_confirm.py`
- `backend/app/services/whatsapp_console_service/edit_messages.py`
- `backend/app/services/whatsapp_console_service/edit_handlers.py`
- `backend/app/services/whatsapp_console_service/lifecycle_messages.py`
- `backend/app/services/contingency_reply_policy/policy.py`

Incluye:
- menú principal
- ayuda
- lista
- detalle
- crear
- editar
- desactivar
- reactivar
- eliminar
- contingencia/fallback
- mensajes de éxito y error del flujo master

### D. WhatsApp i18n catalogs

Archivos confirmados:
- `backend/app/core/i18n/catalogs_es_wa.py`
- `backend/app/core/i18n/catalogs_en_wa.py`

Hotspots confirmados:
- `wa.client.profile.body`
- `wa.tenant.client_context.collision`
- cualquier string visible `wa.tenant.*` que siga mostrando `Tenant` al usuario

### E. Tests que validan copy visible

Además de los tests ya sospechados, este trabajo debe actualizar cualquier aserción exacta afectada por el nuevo copy.

Suites confirmadas con dependencia visible al copy actual:
- `backend/tests/test_contingency_reply_policy.py`
- `backend/tests/test_whatsapp_menu_flow.py`
- `backend/tests/test_whatsapp_lifecycle_flow.py`
- `backend/tests/test_whatsapp_list_select_flow.py`
- `backend/tests/test_whatsapp_create_flow.py`
- `backend/tests/test_whatsapp_endpoint.py`
- `backend/tests/test_whatsapp_credential_auth_flow.py`
- `backend/tests/test_tenant_console_service.py` si tiene asserts de copy exacto

### F. Documentación existente con copy literal user-facing

Este fue uno de los huecos del spec previo: la actualización documental no puede quedar abierta ni solo ejemplificada.

Revisión mínima obligatoria:
- `docs/architecture/whatsapp-console-flow.md`
- `docs/architecture/n8n-workflow.md`
- `docs/project-pdr/business-rules.md`

Además:
- cualquier otra doc existente en `docs/` que cite literalmente menús, labels, mensajes o payload examples con el copy viejo dentro del alcance
- cualquier screenshot o material operativo incluido en el PR

Regla documental:
- se corrige el copy user-facing citado literalmente
- no se hace barrido cosmético global de la palabra `tenant` en documentación técnica sana

## Out of scope

No forma parte de este trabajo:

- renombrar clases/modelos/servicios como `Tenant`, `TenantService`, etc.
- renombrar rutas o endpoints `/tenants/...`
- renombrar keys i18n
- renombrar variables, stores, fixtures o nombres de helpers
- cambiar contratos API o payloads técnicos
- introducir refactor global del sistema i18n
- cambiar flujos funcionales del Master Console o Client Context Shortcut
- limpiar toda la documentación técnica del repo por ocurrencias internas de `tenant`
- tocar copy fuera del alcance solo por consistencia estética

`frontend/src/i18n/public.json` queda fuera de alcance salvo hallazgo puntual durante implementación.

## Implementation rules

1. Cambiar **values/literales visibles**, no nombres internos.
2. Corregir mojibake y acentos en cualquier string visible tocado.
3. No dejar mezcla ES/EN como `Lista de Tenants`, `Salir de tenant`, `Tenant y cliente`.
4. Mantener el cambio quirúrgico: sin renames internos ni refactors especulativos.
5. Si aparecen más strings visibles del mismo flujo con copy viejo, alinearlos en el mismo PR.
6. Si una key legacy visible no tiene referencias reales, puede eliminarse; si sí tiene referencias, se conserva y se limpia su value.
7. La documentación existente afectada debe quedar sincronizada en el mismo PR.

## Required visible outcomes

### Frontend

Valores mínimos obligatorios:
- `frontend.dashboard.master_support`
  - ES: `Estás gestionando el catálogo de esta empresa en modo soporte`
  - EN: copy equivalente natural sin `tenant`
- `frontend.dashboard.tenant.exit_tenant`
  - ES: `Salir de la empresa`
  - EN: equivalente natural sin `tenant`
- `frontend.subscriptions.recipient_mode_tenant_only`
  - ES: `Solo administración`
  - EN: `Admin only`
- `frontend.subscriptions.recipient_mode_both`
  - ES: `Administración y cliente`
  - EN: `Admin and client`
- `frontend.dashboard.client.tenant`
  - ES: `Proveedor`
  - EN: `Provider`

### WhatsApp Master Console

Deben desaparecer textos como:
- `Ver Tenants`
- `Crear Tenant`
- `Desactivar Tenant`
- `Eliminar Tenant`
- `Lista de Tenants`
- `Detalle del Tenant`
- `Editar Tenant`
- `Tenant creado exitosamente`
- `tenant actualizado exitosamente`

En español visible se usa terminología de `empresa` y se corrige legibilidad:
- `Opción inválida`
- `sesión`
- `Teléfono`
- `catálogo`
- `gestión`
- `Envía`

### WhatsApp Client / Context

Valores mínimos obligatorios:
- `wa.client.profile.body`
  - `Tenant:` visible debe pasar a `Proveedor:` / `Provider:`
- `wa.tenant.client_context.collision`
  - debe dejar de decir `chat privado de Tenant`
- cualquier string visible de contexto cliente debe evitar `Tenant` como etiqueta mostrada al usuario

## Legacy key cleanup

Candidatas claras en ambos catálogos WhatsApp:
- `wa.tenant.client_context.active.menu_text`
- `wa.tenant.client_context.active.invalid_option`
- `wa.tenant.client_context.inactive.menu_text`
- `wa.tenant.client_context.inactive.invalid_option`

Regla:
- si no tienen uso comprobado en `backend/`, `frontend/` y `backend/tests/`, se eliminan en ES y EN
- si tienen uso indirecto real, se mantienen pero con value limpio

## Linguistic normalization

Además del cambio terminológico, corregir texto dañado por encoding en strings visibles tocados.

Ejemplos concretos ya detectados:
- `EstÃ¡s gestionando el catÃ¡logo de este tenant en modo soporte.`
- `Salir de tenant`
- `Solo el tenant`
- `Tenant y cliente`
- `Telefono`
- `gestion`
- `Envia`
- `sesion`
- `catalogo`

Orden de prioridad cuando una cadena tenga varios problemas:
1. término de producto correcto por contexto
2. idioma correcto por contexto
3. encoding / acentos / legibilidad

## Documentation acceptance rules

La documentación afectada debe quedar alineada con el nuevo copy visible, pero sin confundir dominio técnico con terminología de UI.

### Debe actualizarse
- tablas de menús visibles del Master Console
- ejemplos literales de replies en WhatsApp
- payload examples o capturas donde el campo `reply` contenga el copy viejo
- instrucciones operativas dirigidas a usuarios o soporte

### No debe forzarse
- descripciones técnicas como `Tenant locale`, `Tenant scope`, `Tenant service`, `session:admin:{phone}`
- nombres de entidades de arquitectura
- referencias de dominio interno que no sean copy visible

## Verification

### 1. Static search

Confirmar que no queda `Tenant`/`Tenants`/`tenant` visible dentro del alcance en:
- `frontend/src/views/MasterDashboardView.vue`
- `backend/app/core/i18n/catalogs_*_frontend.py`
- `backend/app/core/i18n/catalogs_*_wa.py`
- `backend/app/services/whatsapp_console_service/*.py` para strings visibles del Master Console
- `backend/app/services/contingency_reply_policy/policy.py`
- `docs/architecture/whatsapp-console-flow.md`
- `docs/architecture/n8n-workflow.md`
- `docs/project-pdr/business-rules.md`

Confirmar también:
- no queda mojibake en strings visibles tocados
- toda key eliminada fue validada contra referencias reales

### 2. Automated tests

Backend mínimo:
```bash
cd backend && uv run pytest tests/test_contingency_reply_policy.py tests/test_whatsapp_menu_flow.py tests/test_whatsapp_lifecycle_flow.py tests/test_whatsapp_list_select_flow.py tests/test_whatsapp_create_flow.py tests/test_whatsapp_endpoint.py
```

Si se actualizan asserts adicionales, incluir también:
```bash
cd backend && uv run pytest tests/test_whatsapp_credential_auth_flow.py tests/test_tenant_console_service.py
```

Frontend:
```bash
cd frontend && npm test
```

Si aparecen dudas de regresión colateral:
```bash
cd backend && uv run pytest
```

### 3. Manual smoke checks

#### Web Master Dashboard
- no aparece `Tenant` / `Tenants`
- se usa `Business` / `Businesses`
- el contexto soporte usa `empresa` / `business` correctamente

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
- no hay acentos rotos ni mezcla ES/EN

#### WhatsApp cliente
- perfil muestra `Proveedor` / `Provider`
- mensajes contextuales no dicen `Tenant`

#### Docs
- `whatsapp-console-flow`, `n8n-workflow` y `business-rules` no muestran el copy user-facing viejo dentro del alcance
- se mantienen intactas las referencias técnicas donde `tenant` sigue siendo correcto

## Definition of done

El trabajo queda terminado solo si:

- no queda `tenant` visible en ninguna superficie user-facing dentro del alcance
- la terminología canónica quedó aplicada por contexto
- el mojibake fue corregido en los strings tocados
- las keys legacy visibles sin uso comprobado fueron eliminadas o saneadas correctamente
- los tests afectados fueron actualizados y pasan
- no se renombraron artefactos internos fuera de alcance
- no se cambiaron flujos funcionales para acomodar el copy
- la documentación existente afectada quedó sincronizada con el nuevo copy visible
- no se dañó documentación técnica correcta por un reemplazo global indiscriminado

## Delegation clause

Cualquier subagente o worker que implemente una tarea derivada de este diseño debe leer su tarea completa antes de actuar.

Mínimos obligatorios:
- leer alcance, exclusiones, archivos afectados y verificación
- no actuar sobre resúmenes truncados
- pedir contexto completo si la tarea llega incompleta
- no inferir cambios globales a partir de snippets parciales
