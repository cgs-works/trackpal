# Phase 05: Audit + n8n cleanup + final verification

## Objective

- Ensure no tenant/client-visible hardcoded strings remain outside i18n catalogs.
- Ensure n8n acts only as transport for localized text.
- Final test/build + manual QA across channels.

## Scope

- Files/modules this phase may touch:
  - Backend: any tenant/client-facing services/endpoints still containing hardcoded user-facing strings.
  - Frontend: any remaining tenant/client-facing hardcoded strings.
  - n8n workflow JSON: `n8n/Trackpal WhatsApp Bot.json`, `n8n/Trackpal Subscription Reminders.json`.
  - Docs: optional small note in architecture docs (only if behavior changed materially).

## Preconditions

- Phases 01-04 complete.

## Tasks

1. Systematic hardcoded-string audit (backend)
   - Run `rg` sweeps scoped to tenant/client-visible areas:
     - WhatsApp tenant console + facade.
     - Reminder generation.
     - Tenant/client API endpoints/services.
   - Example commands (adjust patterns as needed):
     - `rg -n "No se pudo|No hay|Contraseña|Perfil|Servicio temporalmente" backend/app`
     - `rg -n "Unable to|not found|Incorrect|required" backend/app/api/v1/endpoints`
   - For each match, decide:
     - master-only (OK to remain Spanish), or
     - tenant/client-visible (must become i18n key).

1a. Master-to-tenant outbound text audit (PRD FR-8)
   - Search for any backend-generated outbound WhatsApp/Evolution messages besides n8n transport:
     - `rg -n "sendText|message/send|Evolution" backend/app/services`
   - If any tenant-targeted text exists, ensure it renders via i18n using `tenants.locale`.

2. Systematic hardcoded-string audit (frontend)
   - `rg -n "Bienvenido|Cargando|No se pudo|Guardar|Eliminar|Logout|Password" frontend/src/views`
   - Replace remaining with `t()` keys.

3. n8n transport alignment
   - WhatsApp bot workflow:
     - Ensure backend always returns non-empty `reply` (so Merge Reply fallback rarely used).
     - Keep Merge Reply fallback Spanish (Spain market) since locale unknown when backend unreachable.
   - Subscription reminders workflow:
     - Confirm it sends `message` field from backend payload unchanged.

4. Performance sanity check
   - Confirm i18n adds negligible overhead:
     - Ensure `t()` is dict lookup + `str.format` only.
     - Ensure no file I/O in request path.
   - If needed, add small micro-benchmark script under `backend/scripts/` (optional) and record numbers.

5. Final verification
   - Backend:
     - `cd backend && uv run pytest -v`
   - Frontend:
     - `cd frontend && npm run build`

6. Manual QA checklist (must record results)
   - Tenant web:
     - New tenant default English.
     - Switch locale to Spanish, UI updates immediately.
   - Tenant WhatsApp console:
     - Main menu + help in correct locale.
     - Change locale inside profile flow; next reply updates immediately.
   - Reminders:
     - Set tenant locale `en` and hit `/api/v1/subscriptions/reminders/pending` (with API key); verify message English.
     - Set tenant locale `es`; verify Spanish.

## Acceptance Criteria

- No tenant/client-visible hardcoded strings remain outside i18n catalogs.
- n8n workflows do not own translation catalogs for tenant/client-visible text.
- All tests pass; frontend build passes.

## Verification

- Commands:
  - `cd backend && uv run pytest -v`
  - `cd frontend && npm run build`
- Expected results:
  - Both succeed.
- Evidence to record in `SUMMARY.md`:
  - Test/build outputs (summary lines).
  - Manual QA notes.

## Idempotence and Recovery

- Safe to re-run: audits, tests, build.
- Rollback notes: avoid reverting migration in prod.

## Exit Criteria

- [ ] Audit complete; remaining matches triaged.
- [ ] Tests green; build green.
- [ ] Manual QA recorded.

