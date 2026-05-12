# Phase 4: Core Navigation and Menu Flow

**Complexity:** M
**Dependencies:** Phase 3

## Objective

- Implement backend-owned main menu, help text, fallback behavior, and global reset commands for the WhatsApp Master Console.

## Preconditions

- Backend console endpoint exists.
- Skeleton console service exists.
- Redis Conversation Session service is available to clear/update state.

## Tasks

1. Context: inspect PRD menu requirements and existing Tenant dashboard terminology.
2. Implement: add exact main menu categories: Ver tenants, Crear tenant, Desactivar tenant, Eliminar tenant, Ayuda, Cancelar / menú.
3. Implement: route numeric option `5` and text `ayuda` to help text.
4. Implement: add global reset command handling for `0`, `menu`, `menú`, and `cancelar`.
5. Implement: ensure reset clears Redis session before returning the main menu.
6. Implement: add fallback response for unrecognized commands when no active flow exists.
7. Implement: add fallback response for invalid input while a flow is active.
8. Test: verify main menu is returned for empty/menu/reset cases.
9. Test: verify help text is returned.
10. Test: verify reset clears active session state.
11. Verify: run menu flow tests and full backend suite.

## Verification

- Commands:
  - `cd backend && uv run pytest backend/tests/test_whatsapp_menu_flow.py -v`
  - `cd backend && uv run pytest -v`
- Expected results:
  - Master sees the categorized menu.
  - Global reset commands clear Redis and return the main menu.
  - Help text is reachable.
  - Unknown input guides the Master toward valid commands.

## Exit Criteria

- Backend console service owns main navigation.
- Reset behavior works from any active flow state.
- Redis session is cleared on reset.
- Menu tests pass.
