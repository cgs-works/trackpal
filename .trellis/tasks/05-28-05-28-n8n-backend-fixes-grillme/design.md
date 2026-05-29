# Design — Fixes workflow n8n y backend (grill-me)

## Strategy

- Diseño incremental por bug.
- Cada bug tendrá mini-sección: causa raíz, contrato deseado, superficie de cambio, riesgos.
- Prioridad inicial: aislamiento de instancia (seguridad/ruteo).

## Bug 01 — Instance isolation

### Root-cause hypothesis

- En `backend/app/api/v1/endpoints/integrations/console.py` existe rama con fallback por phone/LID cuando `instance` no matchea tenant conocido.
- Ese fallback permite ruteo cruzado no deseado (tenant/client fuera de su instancia).

### Desired contract

- `instance` presente => routing estricto por instancia.
- Master:
  - solo permitido en `MASTER_WHATSAPP_INSTANCE`.
- Tenant/Client:
  - solo permitido dentro de tenant resuelto por `instance`.
- `instance` desconocida/no autorizada:
  - deny (`wa.client.access_denied` o reply equivalente), sin fallback tenant/client.

### Affected components (expected)

- `backend/app/api/v1/endpoints/integrations/console.py` (`_route_by_instance`).
- Tests de integración de consola (`backend/tests/test_client_console_service.py` y/o tests dedicados de routing).
- n8n: verificar que siempre envía `instance` correcta (sin lógica de bypass).

### Risks

- Romper compatibilidad de flujos legacy que dependían de fallback por phone sin instancia válida.
- Falsos denies si instance config en Evolution/n8n está mal escrita.

### Mitigation

- Agregar tests de ruta permitida y denegada.
- Mensaje de deny claro para facilitar troubleshooting operativo.

## Bug 02 — Contrato global de navegación (`9` back, `0` exit) roto

### Root-cause hypothesis

- Diseño actual usa `0` con doble semántica (back en varios subflujos + exit global en otras capas).
- En ambigüedad, handler evalúa salida global temprano; en otros flows, prompts también anuncian `0` como back.
- Resultado: UX inconsistente y cierres de sesión no deseados.

### Desired contract

- Contrato único cross-console:
  - `9` = back local (paso anterior/menú del flow).
  - `0` = exit global (cerrar consola/sesión).
- Aplicar en Master, Tenant, Client y modo ambigüedad.
- Prompts, validadores y tests deben reflejar misma semántica.

### Affected components (expected)

- `backend/app/api/v1/endpoints/integrations/console_modes.py` (orden y semántica en ambigüedad).
- Servicios de consola:
  - `backend/app/services/whatsapp_tenant_console_service/*`
  - `backend/app/services/whatsapp_master_console_facade/*`
  - `backend/app/services/whatsapp_client_console_facade/*`
- Catálogos i18n `catalogs_*_wa.py` (textos de prompts).
- Tests de flujos interactivos para master/tenant/client.

### Risks

- Cambio amplio: puede romper hábitos existentes (`0` como back) en usuarios actuales.
- Alto impacto en tests por contrato transversal.

### Mitigation

- Inventario de pasos interactivos antes de tocar código.
- Migración consistente por consola + update completo de prompts/tests en mismo bloque.
- Validación manual con secuencias reales de chat por rol.

## Bug 03 — Session close parity Evolution Go + prompt post-acción

### Root-cause hypothesis

- Cierre de sesión está fragmentado: parte en backend, parte en n8n; no todos los caminos terminales invocan close session en Evolution Go.
- Flujos CRUD retornan éxito y/o menú directo sin etapa de decisión posterior uniforme.

### Desired contract

- Cualquier salida global de consola (master/tenant/client) debe ejecutar cierre en Evolution Go (best-effort con tolerancia a error, sin romper respuesta al usuario).
- Al finalizar acción CRUD/derivada, respuesta debe incluir menú corto de continuidad:
  - continuar en flujo actual,
  - ir a menú principal,
  - cerrar sesión global.
- El menú post-acción aplica en éxito y también en error/validación fallida.
- Contrato igual para backend y n8n (si n8n participa en cierre).

### Affected components (expected)

- Backend:
  - `backend/app/api/v1/endpoints/integrations/console_handlers.py`
  - facades/services master/tenant/client (puntos terminales de acción)
  - posibles helpers de cierre Evolution.
- n8n workflow `Trackpal WhatsApp Bot`:
  - nodos `Check close session` / `Close session` y ramas de resultado final.
- i18n `catalogs_*_wa.py` para prompts post-acción.
- tests backend de consola + validación funcional n8n.

### Risks

- Duplicar cierre de sesión (backend + n8n) generando llamadas redundantes.
- Incremento de complejidad UX si prompt post-acción aparece en pasos no deseados.

### Mitigation

- Definir fuente de verdad de cierre (backend orquesta; n8n solo transporte/contingencia, o viceversa) antes de codificar.
- Aplicar prompt post-acción solo en terminales de operaciones (create/update/delete/complete), no en navegación intermedia.
- Tests de idempotencia en cierre de sesión.

## Bug 04 — Orden de servicios en lookup de código

### Root-cause hypothesis

- Orden de servicios se define en múltiples puntos (catálogo backend, render prompt, posible mapeo n8n) sin contrato explícito de orden único.
- Puede existir mezcla entre orden de inserción, orden por key interno y orden mostrado al usuario.

### Desired contract

- Flujo "Find Access Code" debe mostrar servicios con orden único y predecible.
- Índice mostrado (1..N) debe mapear exactamente al `service_key` esperado en backend/n8n.
- Misma lista/orden para ES/EN.

### Affected components (expected)

- Backend tenant code flow:
  - `backend/app/services/whatsapp_tenant_console_service/codigo_flow.py`
  - `backend/app/services/mail_code_extractor/catalog/*` (si fuente de listado viene de catálogo)
- n8n workflow `Trackpal WhatsApp Bot` (si arma o transforma lista de servicios).
- Tests del flujo código (`backend/tests/test_tenant_console_service.py` y/o tests dedicados).

### Risks

- Cambiar orden puede romper tests o automatizaciones que asumen índice viejo.
- Si backend y n8n no cambian juntos, puede desalinearse índice -> `service_key`.

### Mitigation

- Definir fuente única de orden (backend como source of truth).
- Alinear n8n solo como transporte; sin reordenar allí.
- Añadir tests de mapeo índice->servicio.

## Bug 05 — Catálogo de servicios de código separado + gobernanza global

### Root-cause hypothesis

- Arquitectura actual mezcla dos dominios distintos:
  - catálogo comercial tenant (servicios libres),
  - catálogo técnico de extracción de códigos (debe ser soportado).
- Falta entidad dedicada por tenant para servicios de código.
- Falta control global de activación/desactivación por master para servicios soportados.

### Desired contract

- Mantener catálogo general tenant sin cambios.
- Introducir catálogo técnico separado por tenant para code lookup.
- Fuente única de servicios soportados = catálogo global predefinido en código + estado activo/inactivo gestionado por master.
- Tenant selecciona múltiples servicios de código desde modal multiselect (no texto libre).
- Persistencia de selección tenant por reemplazo total en transacción única (last-write-wins).
- Lista final en WhatsApp `code`:
  - solo servicios seleccionados por tenant y activos globalmente,
  - orden alfabético,
  - sin fallback genérico cuando tenant no configuró servicios.
- Mensajería diferenciada por rol si no hay configuración (tenant detallado con CTA a dashboard, client genérico con retorno a menú), con i18n.
- Labels visibles centralizados en catálogo i18n por `service_key`.
- Validación estricta en API: `service_key` inválida => 400 y rechazo total.

### Affected components (expected)

- DB/migrations:
  - tabla global de estado de servicios de código (si no existe),
  - tabla mapping tenant↔service_key para code lookup.
- Backend API:
  - endpoints master para activar/desactivar servicios globales,
  - endpoints tenant/master para gestionar selección por tenant.
- Backend WhatsApp code flow:
  - `backend/app/services/whatsapp_tenant_console_service/codigo_flow.py`
  - validación de lista efectiva por tenant.
- Frontend:
  - master dashboard (toggles globales),
  - tenant dashboard modal multiselect "servicios disponibles para búsqueda de códigos de acceso".
- n8n:
  - sin construcción de lista (solo transporte).
- i18n + tests backend/frontend.

### Risks

- Desalineación temporal entre catálogo global activo y selecciones tenant existentes.
- Regresiones en flujo code para tenants no configurados (ahora error explícito).
- Complejidad de permisos master+tenant en misma configuración por tenant.

### Mitigation

- Implementar reglas de filtrado deterministas: `effective = tenant_selected ∩ global_active`.
- Mantener selecciones tenant aunque global quede inactivo (mostrar deshabilitado en UI tenant; no usable en WhatsApp).
- Sin auditoría en v1 (solo estado actual).
- Tests de matriz de casos: tenant vacío, tenant con seleccionados inactivos, client vs tenant messages, orden alfabético, 400 por service_key inválida.
