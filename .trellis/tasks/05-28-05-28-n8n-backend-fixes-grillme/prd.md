# Fixes workflow n8n y backend (grill-me)

## Goal

Corregir bugs funcionales y de aislamiento entre instancias WhatsApp (master/tenant/client) en backend + workflow n8n, revisando uno por uno en dinámica grill-me antes de implementar.

## Requirements

- Registrar cada bug confirmado en este task antes de implementación.
- Discutir cada bug de forma secuencial (uno por turno), con síntoma, impacto, regla esperada, propuesta de fix y riesgo.
- No iniciar implementación hasta aprobación explícita por bug.

### Bug 01 — Aislamiento de instancia roto

**Síntoma reportado**
- Número tenant puede escribir a instancia master.
- En algunos casos, flujo termina abriendo consola tenant/admin fuera de instancia esperada.

**Regla de negocio confirmada por usuario**
- Tenant no puede iniciar consola tenant en instancia distinta a su propio tenant.
- Master solo opera en `MASTER_WHATSAPP_INSTANCE`.
- No mezclar identidades por fallback cuando `instance` viene en request.

**Comportamiento requerido**
- Si request trae `instance`, backend debe enrutar estrictamente por instancia autorizada.
- `instance` desconocida o no autorizada para identidad => `access denied` (sin fallback por phone/LID para tenant/client).

### Bug 02 — Contrato de navegación inconsistente (`0`/`9`) en flujos interactivos

**Síntoma reportado**
- En flujo tenant (Clientes → Detalle), interfaz muestra `0️⃣ Back`, pero al enviar `0` sistema cierra sesión global (`✅ You have exited. Goodbye!`).
- Comportamiento mezcla semánticas de navegación local y salida global.

**Regla de negocio confirmada por usuario**
- En todos los flujos interactivos (Master/Tenant/Client):
  - `9` => regresar (back) al paso anterior.
  - `0` => salir de consola (cierre global de sesión).
- Nunca usar `0` como “back” dentro de flujo interactivo.

**Comportamiento requerido**
- Unificar prompts y handlers para que `9` sea back consistente en todos los pasos interactivos.
- Reservar `0` exclusivamente para exit global.
- Corregir ramas de ambigüedad para no romper contrato de navegación.

### Bug 03 — Cierre de sesión Evolution ausente + post-acción sin decisión guiada

**Síntoma reportado**
- Tras migración a Evolution Go, cerrar sesión de consola no siempre cierra sesión/chat en Evolution.
- Al completar acciones de consola (CRUD y derivados), no existe paso consistente para decidir: continuar en flujo actual, volver a menú principal, o cerrar sesión.

**Regla de negocio confirmada por usuario**
- Cerrar sesión de consola debe cerrar también sesión en Evolution Go.
- Al terminar una acción interactiva, sistema debe preguntar siguiente paso con opciones explícitas:
  1) continuar operación del flujo actual,
  2) ir al menú principal,
  3) cerrar sesión global.
- Este prompt post-acción aplica tanto en resultados exitosos como en errores/validaciones fallidas.

**Comportamiento requerido**
- Garantizar close-session end-to-end (backend + n8n) en master/tenant/client cuando usuario sale.
- Definir prompt post-acción estandarizado y reusable en flujos CRUD/derivados.
- Evitar quedarse en estado ambiguo luego de operaciones exitosas.

### Bug 04 — Orden de servicios en "Find Access Code" desorganizado

**Síntoma reportado**
- Menú de servicios del flujo "Find Access Code" en n8n/backend no respeta orden esperado.
- UX percibida como desordenada al seleccionar servicio.

**Regla de negocio confirmada por usuario**
- Servicios deben mostrarse en orden alfabético en el flujo interactivo.
- Orden final confirmado por usuario (A-Z real):
  1) Disney+
  2) HBO Max
  3) Netflix
  4) Prime Video
  5) Spotify
  6) Universal+

**Comportamiento requerido**
- Unificar orden de servicios en prompts/backend y mensajes n8n para "Find Access Code".
- Mantener consistencia entre índice mostrado y `service_key` enviado al backend.

### Bug 05 — Catálogo de servicios de código separado + gobernanza master/tenant

**Síntoma reportado**
- Flujo `code` no está alineado con configuración real por tenant y mezcla catálogo general con catálogo soportado para extracción.
- Tenant hoy puede crear servicios libres; eso no garantiza soporte de extractor.
- Falta gobernanza global: master requiere controlar qué servicios de código están habilitados en TrackPal.

**Regla de negocio confirmada por usuario (grill-me)**
- No cambiar flujo actual de catálogo general tenant (servicios propios libres se mantienen).
- Crear configuración separada: "servicios disponibles para búsqueda de códigos de acceso" por tenant.
- Persistencia en tabla DB dedicada (no JSON).
- Tenant solo puede seleccionar `service_key` soportadas globalmente (fuente única global).
- Master dashboard solo activa/desactiva servicios predefinidos en código (sin crear/editar nombres desde UI).
- Tenant + master pueden gestionar selección de servicios de código por tenant.
- Guardado de selección tenant por reemplazo total (sync completo), con política last-write-wins.
- Si tenant no tiene servicios de código configurados:
  - Tenant/admin: mensaje de configuración faltante + instrucción para configurar en dashboard.
  - Client: mensaje genérico de servicio no operativo y retorno a menú principal.
- n8n no arma lista; backend responde lista final.
- Si master desactiva servicio global ya seleccionado por tenant: mostrarlo deshabilitado en UI tenant (selección persiste inactiva).
- Orden en WhatsApp: siempre alfabético por label visible.
- Labels de servicios provienen de catálogo i18n central por `service_key`.
- API de selección tenant rechaza `service_key` inválidas con 400 estricto.
- Migración inicial: tenants existentes quedan vacíos por defecto.
- Bug 05 reemplaza fallback genérico para tenant sin configuración (confirmado por usuario).

**Comportamiento requerido**
- End-to-end backend + DB + dashboards (tenant/master) + i18n + contrato n8n.
- Flujo `Find Access Code` usa exclusivamente lista de servicios de código configurados por tenant y activos globalmente.

## Acceptance Criteria

- [x] Bug 01 documentado en PRD con síntoma, regla y resultado esperado.
- [x] Bug 02 documentado en PRD con síntoma, regla y resultado esperado.
- [x] Bug 03 documentado en PRD con síntoma, regla y resultado esperado.
- [x] Bug 04 documentado en PRD con síntoma, regla y resultado esperado.
- [x] Bug 05 documentado en PRD con síntoma, regla y resultado esperado.
- [ ] Se mantiene bitácora de bugs siguientes en este mismo task (PRD + design + implement).
- [ ] Cada bug solo pasa a implementación tras aprobación explícita del usuario en grill-me.

## Notes

- Task intencionalmente incremental: bug-by-bug.
- Si alcance crece, dividir en child tasks verificables.
