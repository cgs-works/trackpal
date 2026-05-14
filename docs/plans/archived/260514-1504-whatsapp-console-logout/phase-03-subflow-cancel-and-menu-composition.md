# Phase 3 — Sub-flow cancel + CRUD completion returns menu in same reply

**Complexity:** M

## Objective

Make sub-flow endings (success or cancellation) always return a single WhatsApp reply containing:

- A final message (success or cancellation)
- Followed by the `MAIN_MENU`

…and keep `0` as contextual cancel inside active flows.

Also update top-level copy so `0` is described as **logout** at the main menu.

## Tasks (2–10 min each)

1. **Add a reusable reply composer helper (optional but keeps diff small)**
   - Edit: `backend/app/services/whatsapp_console_service.py`
   - Add private helper:
     - `_with_main_menu(message: str) -> str` returning `message.rstrip() + "\n\n" + MAIN_MENU`

2. **Contextual reset behavior inside active flows**
   - In `WhatsAppConsoleService.process_message()`:
     - Move reset handling to be aware of session state:
       - If `msg in RESET_COMMANDS` and there is an active flow (`session.flow` truthy):
         - clear session
         - return `"🚫 Operación cancelada." + "\n\n" + MAIN_MENU`
       - If `msg in RESET_COMMANDS` and there is **no** active flow:
         - return `MAIN_MENU`
         - Note: in production the facade intercepts top-level `0` to perform logout, so the console service’s top-level reset reply is primarily for direct/unit-test usage.

3. **Append menu on CRUD success completion paths**
   - In `whatsapp_console_service.py`, update success returns where the session is cleared:
     - Create tenant confirm success (`_handle_create_confirm`)
     - Reactivate success (`_handle_detail_deactivate_reactivate` when inactive)
     - Deactivate confirm success (`_handle_deactivate_confirm`)
     - Delete confirm success (`_handle_delete_confirm`)
   - Replace `return msg` / `return SUCCESS_MESSAGE` with `_with_main_menu(msg)`.

4. **Update top-level copy to reflect new `0` semantics**
   - Edit: `backend/app/services/whatsapp_console_service.py`
   - Update these templates:
     - `MAIN_MENU`: change `0️⃣ Cancelar / Menú` to `0️⃣ Cerrar sesión` and add “Escribe *menu* para ver el menú” if needed.
     - `HELP_TEXT`: explain `0` closes session at top-level; within flows it cancels.
     - `FALLBACK_NO_FLOW`: replace guidance “0 para volver al menú” with `menu` to show menu and `0` to logout.
   - Keep active-flow prompts that say “0 para cancelar” unchanged.

5. **Update tests to match new replies**
   - `backend/tests/test_whatsapp_menu_flow.py`:
     - Update assertions that expect `Cancelar / Menú`.
     - Add/adjust assertions for the new help/fallback wording.
   - `backend/tests/test_whatsapp_create_flow.py`:
     - Ensure create success reply contains `Trackpal Master Console` (menu appended).
   - `backend/tests/test_whatsapp_lifecycle_flow.py`:
     - Ensure deactivate/reactivate/delete success replies contain menu.
     - Ensure cancel/reset inside active flows returns cancellation + menu (still contains menu).

## Verification

- `cd backend && uv run pytest tests/test_whatsapp_menu_flow.py -v`
- `cd backend && uv run pytest tests/test_whatsapp_create_flow.py -v`
- `cd backend && uv run pytest tests/test_whatsapp_lifecycle_flow.py -v`

## Exit Criteria

- Any CRUD flow success that clears session returns `final message + MAIN_MENU` in one reply.
- Reset/cancel inside an active flow returns a clear cancellation message + menu in one reply.
- Menu/help/fallback text no longer misleads users into thinking `0` is “menu” at top-level.
- All affected tests updated and passing.
