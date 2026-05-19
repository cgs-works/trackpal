# Phase 04: WhatsAppTenantConsoleService

## Objective

- Implement the full tenant-admin WhatsApp conversational service for clients, catalog, profile, help, and contextual cancellation while reusing established Master Console flow patterns where they fit.

## Complexity / Risk

- Complexity: XL
- Risk: High

## Scope

- Files/modules this phase may touch:
  - `backend/app/services/whatsapp_tenant_console_service.py`
  - `backend/app/services/client_service.py` (reference only, no schema changes)
  - `backend/app/services/catalog_service.py` (reference only, no schema changes)
  - `backend/app/services/profile_service.py` (only if a tiny helper is needed)
  - `backend/tests/test_tenant_console_service.py`
- Files/modules this phase must not touch:
  - Master Console flow files except as read-only references
  - frontend code
  - n8n/Evolution transport setup
  - models, schemas, or Alembic migrations (no schema changes needed)

## Preconditions

- Phase 01 through Phase 03 are complete enough that the tenant path can call into this service.
- Current `ClientService`, `CatalogService`, `ProfileService`, and validation helpers have been reviewed.
- **No schema changes are required.** Client has no email field. Service/Plan have name only. These are by design. The conversational flows are trimmed to match the current data model.

## Tasks

1. **No schema changes needed.** Client has no email, Service/Plan have name only — by design.
   - Client flow omits email create/view/edit.
   - Catalog editing is limited to name changes only. No description, no price.
   - The conversational flows in the brainstorm artifacts are trimmed to match the current data model.
2. Create `WhatsAppTenantConsoleService` with injected dependencies.
   - Constructor should accept `client_service`, `catalog_service`, and `profile_service`.
   - Keep dependency types aligned with the Phase 02 protocols.
3. Define service-level reply constants and flow ids.
   - Main menu: `Clientes`, `Catalogo`, `Mi Perfil`, `Ayuda`, `Salir`.
   - Flow/state names for clients, client create/edit/lifecycle, catalog, profile, password, and help.
   - Keep all user-facing text in Spanish.
4. Implement the service entrypoint and session loading.
   - Route from `session.flow` plus current message.
   - Use `admin:{phone}` as the logical key passed to `WhatsAppSessionService`.
   - Reuse `temp_data` and `selection_map` instead of overloading `selected_tenant_id`.
5. Implement the main menu handler.
   - `1` → clients submenu.
   - `2` → catalog submenu.
   - `3` → profile submenu.
   - `4` → help.
   - `0` handling remains contextual: main-menu exit belongs to the facade; in-flow cancel belongs to the service.
6. Implement the clients sub-flow.
    - List clients with active/inactive labeling and `selection_map`. Client detail omits email (not in schema).
    - Show client detail with actions.
    - Support create wizard, edit, deactivate/reactivate, and delete.
    - Follow existing Master Console patterns for `CONFIRMAR`, selection maps, validation-reprompt replies, and session-step persistence.
7. Implement the client create wizard.
    - Steps: nombre completo → teléfono (opcional) → usuario local → contraseña (opcional, auto-generada si se omite). No incluye email.
    - Allow optional phone and generated password behavior according to the brainstorm.
    - If concrete services still require a password string, let the console generate one and pass it explicitly rather than weakening service-layer validation.
8. Implement the catalog sub-flow.
   - List services.
   - Show service detail plus plan list.
   - Show plan detail.
   - Allow edit of service/plan names only. No description, no price, no creation.
   - Keep catalog create/delete and any price editing out of scope.
9. Implement the profile sub-flow.
    - Display tenant profile using `ProfileService.get_profile()`. No email field in client profile (only tenant admin's own profile).
    - Allow update of name/email/phone via `ProfileUpdate`.
    - Allow password change via a multi-step flow that calls `ProfileService.change_password()`.
    - Keep username read-only.
10. Implement help and fallback behavior.
   - Reuse centralized `validate_*()` helpers where they exist.
   - For field types without a dedicated validator yet, add the smallest shared validation helper needed rather than inlining inconsistent checks in multiple handlers.
11. Handle edge cases explicitly.
   - Empty client/service/plan lists.
   - Invalid menu selection.
   - Validation errors with Spanish reprompt.
   - Delete-active-client rejection.
   - Missing session state after failover/reset.
   - `0` cancellation from nested steps returning to the correct parent view.
12. Keep the implementation testable.
   - Prefer many small private handlers over one giant `process_message()` body.
   - Avoid direct DB work in the service; use the injected service dependencies and session service.

## Acceptance Criteria

- User-visible or system-observable result:
  - Tenant admins can navigate the main menu and complete the supported flows in Spanish.
  - `0` cancels in-progress operations without logging out, and top-level exit still works via the facade.
  - Client lifecycle rules are enforced.
  - Catalog editing is limited to approved fields only.
  - Profile view/update/password-change work for tenant admins.
  - Missing data or invalid input yields deterministic reprompts instead of tracebacks.
- Required changed files:
  - `backend/app/services/whatsapp_tenant_console_service.py`
  - `backend/tests/test_tenant_console_service.py`
- Required unchanged behavior:
  - Master Console flow logic remains untouched.
  - No catalog creation/deletion is introduced through WhatsApp.
  - No plan price support is added by this phase.

## Verification

- Commands:
  - `cd backend && uv run pytest tests/test_tenant_console_service.py -q`
  - `cd backend && uv run pytest tests/test_clients.py tests/test_catalog.py tests/test_profile.py -q`
  - `cd backend && uv run alembic upgrade head` (not needed — no schema changes in this feature)
- Expected results:
  - Tenant console service tests pass for clients, catalog, profile, help, invalid input, and zero handling.
  - Existing client/catalog/profile regressions remain green.
- Evidence to record in `SUMMARY.md`:
  - pytest summary lines.
  - Confirmation that no schema changes were needed.

## Idempotence and Recovery

- Safe to re-run:
  - Service-level tests with fakes/mocks are safe to rerun.
- Recovery if interrupted:
  - Land the service in vertical slices by flow group, keeping non-wired handlers private until tests pass.
  - Delay endpoint wiring until the service imports cleanly and has baseline tests.
- Rollback notes:
  - Remove tenant service wiring first, then back out the new service file.

## Exit Criteria

- [ ] Main menu exists with the approved Spanish options.
- [ ] Clients flow supports list/detail/create/edit/deactivate/reactivate/delete.
- [ ] Catalog flow supports list/detail and approved edit operations only.
- [ ] Profile flow supports view, edit, and password change.
- [ ] Invalid input and empty-list cases are handled explicitly.
- [ ] Contextual `0` behavior works from nested flows.
- [ ] Catalog editing is confirmed as name-only (no description, no price).
- [ ] Tenant console service tests cover the major branches.
