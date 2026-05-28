# Fix n8n mail lookup 404 despite email present

## Goal

Eliminar 404 en polling de `GET /api/v1/integrations/n8n/mail/lookups/{job_id}?tenant_id=...` cuando flujo `codigo` ya devolvió `lookup_job_id` y `tenant_id`.

## Requirements

1. Confirmar causa raíz con evidencia n8n + DB.
   - En ejecución n8n `35284`, backend devolvió `lookup_job_id=3448efe0-997d-468f-9ed6-84ccaa11f278` y `tenant_id=e1a3dc2f-c055-470a-9cf5-fcaeb876bfc2`.
   - Poll inmediato devolvió `{"detail":"Job not found"}`.
   - Query Supabase a `mail_lookup_jobs` por ese `job_id` devolvió `[]`.
2. Corregir persistencia de job en flujo tenant WhatsApp `codigo`.
   - Job no debe salir en respuesta si transacción no está confirmada.
   - Poll debe encontrar fila siempre que se devuelva `lookup_job_id`.
3. Mantener aislamiento multi-tenant.
   - `tenant_id` sigue obligatorio en poll.
   - No relajar filtro por tenant.
4. Agregar pruebas de regresión.
   - Caso: mensaje final de flujo `codigo` retorna `lookup_job_id`; poll posterior encuentra job (no 404).

## Acceptance Criteria

- [ ] Si backend responde `lookup_job_id` en consola tenant, existe fila correspondiente en `mail_lookup_jobs` antes de responder.
- [ ] Poll con `job_id+tenant_id` correcto no devuelve 404 por ausencia de fila recién creada.
- [ ] Poll con `tenant_id` incorrecto sigue devolviendo 404.
- [ ] Tests backend de flujo `codigo` y poll pasan.
