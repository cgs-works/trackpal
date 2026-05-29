# Implement plan — Fixes workflow n8n y backend (grill-me)

## Execution model

- Ejecutar bug por bug.
- Para cada bug: Repro -> Fix -> Verify -> Document.
- No mezclar varios bugs en mismo commit salvo aprobación explícita.

## Bug 01 plan (pending approval to implement)

1. Reproducir caso con test o escenario controlado.
2. Endurecer `_route_by_instance` para eliminar fallback inseguro con `instance` inválida/no autorizada.
3. Asegurar contrato:
   - master only master instance.
   - tenant/client only own tenant instance.
4. Agregar/ajustar tests de aislamiento de instancia.
5. Ejecutar subset de tests de consola.
6. Actualizar docs/task artifacts con resultado.

## Verification commands (for execution phase)

```bash
cd backend
uv run pytest -q tests/test_client_console_service.py -k "instance or ambiguity"
uv run pytest -q tests/test_tenant_console_service.py -k "menu or codigo"
```

## Bug 02 plan (pending approval to implement)

1. Levantar inventario de todos los pasos interactivos con navegación en master/tenant/client.
2. Marcar dónde hoy se usa `0` como back y dónde como exit.
3. Definir refactor transversal al contrato único:
   - `9` back local.
   - `0` exit global.
4. Ajustar handlers de flows + ambigüedad + prompts i18n.
5. Actualizar tests de navegación por rol (master/tenant/client).
6. Verificar manualmente secuencias de chat críticas.
7. Documentar resultado en task artifacts.

## Bug 03 plan ✅ IMPLEMENTED

1. ✅ Mapped all global exit paths in master/tenant/client.
2. ✅ Verified Evolution Go close is handled by n8n `Check close session` node (backend `close_chat_session()` was deprecated no-op).
3. ✅ Strategy: n8n owns Evolution close; backend owns Redis session clear + goodbye reply.
4. ✅ Removed deprecated `close_chat_session()` calls from all 3 facades (master/tenant/client).
5. ✅ Added post-action decision prompt (`wa.tenant.post_action_prompt`) to all 12 terminal CRUD handlers (client create/edit/deactivate/delete, subscription create/edit/cancel/renew/reactivate, profile edit/password/locale, master create/edit/deactivate/delete).
6. ✅ Updated i18n catalogs (ES/EN) with post-action prompt + added 'goodbye' keyword to all goodbye messages for reliable n8n detection.
7. ✅ n8n workflow unchanged — `Check close session` node already works correctly.
8. ✅ Updated 3 existing tests (removed deprecated Evolution close assertions), added 2 new tests (goodbye keyword detection + post-action prompt presence).
9. ✅ Full suite: 1058 passed, 1 skipped.

## Bug 04 plan (pending approval to implement)

1. Localizar fuente real de orden de servicios (backend y n8n).
2. Definir orden final y congelarlo en contrato explícito.
3. Ajustar render de menú + parser de selección para mantener índice->service_key.
4. Revisar n8n para evitar reordenamiento o transformación inconsistente.
5. Actualizar tests de flujo código (orden visible + mapeo correcto).
6. Validar manualmente prompt final con lista esperada.

## Bug 05 plan (pending approval to implement)

1. Diseñar esquema DB para catálogo técnico de código:
   - global service states (toggle master),
   - tenant code-service selections (many-to-many por service_key).
2. Crear migraciones y repositorios/queries.
3. Exponer APIs:
   - master: activar/desactivar servicios globales predefinidos,
   - tenant+master: configurar selección multiselect por tenant (reemplazo total, last-write-wins).
   - validación estricta: `service_key` inválida => 400 rechazo total.
4. Actualizar dashboards:
   - master: panel toggles globales,
   - tenant: modal "servicios disponibles para búsqueda de códigos de acceso".
   - servicios globalmente inactivos pero seleccionados: mostrar deshabilitados en UI tenant.
5. Ajustar flujo WhatsApp `code` para usar `effective = tenant_selected ∩ global_active`, orden A-Z.
6. Quitar fallback genérico para tenant no configurado; aplicar mensajes diferenciados tenant/client con i18n.
   - tenant/admin: mensaje + CTA a configuración en dashboard.
   - client: mensaje genérico + retorno a menú principal.
7. Verificar n8n como transporte (sin lógica de listado).
8. Agregar tests backend/frontend para permisos, filtros, orden, mensajes y validación 400 en `service_key` inválida.
9. Confirmar explícitamente que n8n no construye lista; solo transporta respuesta backend.
10. Validar manualmente con tenants configurados/no configurados y servicio global inactivo.

## Commit policy

- Un commit por bug aprobado.
- Mensaje debe incluir bug id interno de esta tarea (Bug 01, Bug 02, Bug 03, Bug 04, Bug 05...).
