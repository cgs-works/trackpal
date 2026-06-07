# Uniform WhatsApp Console Navigation Design

Date: 2026-06-03
Status: approved for planning

## Goal

Create a uniform, fully interactive navigation model for every WhatsApp console flow in Trackpal.

Global option semantics:

- `8` = Siguiente / Next
- `9` = Regresar / Back
- `0` = Cancelar / Cancel

This applies strictly across all consoles, menus, lists, pagination, prompts, confirmation steps, and multi-step wizards.

## Scope

In scope:

- Master Console
- Tenant Admin Console
  - Clients
  - Catalog
  - Profile
  - Subscriptions
  - Access-code lookup
  - Message blocks
- Client Console
- Client Context Shortcut
- Ambiguity mode between tenant/client identities
- Unauthenticated access-code lookup
- Spanish and English WhatsApp i18n catalogs
- Backend tests for navigation behavior

Out of scope:

- Web dashboard UI navigation
- Evolution Go session-key behavior
- n8n workflow routing, unless backend response contract changes require small follow-up updates

## Current Problems

The current implementation uses mixed navigation semantics:

- Some flows use `9` to go back.
- Some flows use `9` to cancel.
- Some flows use `0` to go back.
- Subscription pagination currently shows `8` as previous and `9` as next, which conflicts with the new convention.
- Help and fallback messages describe mixed behavior.
- Client Context Shortcut was partially aligned but still has duplicated legacy strings and local handler rules.
- Master Console and Tenant Admin Console use separate services with separate reset/back logic, causing drift.

## Navigation Contract

### Option `0`: Cancelar

`0` always cancels the active interaction.

Behavior by context:

- In a main menu: close the console/session.
- In a wizard: abort the wizard, clear flow-specific temp data, and return to the appropriate idle/main-menu state or close if the flow is private context.
- In a confirmation step: cancel the pending action.
- In Client Context Shortcut: close the full context session and return backend closure metadata (`close_jid` / `close_jids`) as already supported.

Text aliases such as `cancelar`, `salir`, and `cerrar` may map to cancel, but numeric behavior must remain canonical.

### Option `9`: Regresar

`9` always navigates one level back without cancelling the whole console session.

Behavior by context:

- In a detail screen: return to the list or parent menu that opened it.
- In a submenu: return to parent menu.
- In page 2+ lists: return to previous page.
- In the first page of a list: return to parent menu.
- In wizard field-selection screens: return to previous menu/step where meaningful.
- If no previous screen exists: return to main menu.

`9` must no longer mean cancel.

### Option `8`: Siguiente

`8` advances to the next page or next interactive screen.

Behavior by context:

- In paginated lists: go to next page when available.
- In multi-step screens that explicitly offer a non-data-input next action: advance to next step.
- If no next page/step exists: show an invalid-option response with the available navigation options.

`8` must no longer mean previous.

## Architecture

Introduce a shared WhatsApp navigation layer used by console services.

Suggested module:

`backend/app/services/whatsapp_navigation.py`

Core constants:

```python
NAV_NEXT = "8"
NAV_BACK = "9"
NAV_CANCEL = "0"
```

Core helpers:

```python
def is_next(message: str) -> bool: ...
def is_back(message: str) -> bool: ...
def is_cancel(message: str) -> bool: ...
def normalize_nav_input(message: str) -> str | None: ...
```

Navigation state model:

```python
@dataclass
class ConsoleScreen:
    id: str
    params: dict[str, str]

@dataclass
class ConsoleNavigationState:
    current: ConsoleScreen | None
    stack: list[ConsoleScreen]
```

Session integration:

- Store navigation state inside existing session `temp_data` to avoid a new persistence mechanism.
- Keep existing `ConversationSession.step` for compatibility during migration.
- Add small adapter helpers that update both `step` and navigation state while flows are migrated.

Example helpers:

```python
def push_screen(session, screen_id: str, **params) -> None: ...
def replace_screen(session, screen_id: str, **params) -> None: ...
def pop_screen(session) -> ConsoleScreen | None: ...
def clear_navigation(session) -> None: ...
```

## Migration Strategy

Use incremental migration, not a full rewrite in one pass.

### Phase 1: Shared Navigation Primitives

- Add `whatsapp_navigation.py`.
- Add unit tests for numeric and text alias behavior.
- Add i18n keys for shared labels:
  - `wa.nav.next`
  - `wa.nav.back`
  - `wa.nav.cancel`
  - `wa.nav.invalid_option`

### Phase 2: Tenant Admin Console

Normalize the largest console first:

- Clients
- Catalog
- Profile
- Subscriptions
- Code lookup
- Message blocks

Specific known fixes:

- Change message-block unblock prompt from `0 Volver` to `9 Regresar` and reserve `0 Cancelar`.
- Change subscription pagination so `8` is next and `9` is back/previous.
- Replace all `9 para cancelar` prompts with `0 para cancelar`.
- Update fallback/help text to match the strict contract.

### Phase 3: Client Context Shortcut

Complete alignment after current partial work:

- Remove duplicate legacy catalog entries if present.
- Ensure detail/edit screens use `9 Regresar` and `0 Cancelar`.
- Ensure context close still emits `close_jid` and `close_jids`.
- Ensure post-create menu follows the global contract.

### Phase 4: Master Console

Normalize:

- Main menu close behavior.
- Tenant list/detail/edit/create flows.
- Login/auth reset commands.
- Confirmation prompts currently saying `9` cancels.

### Phase 5: Client Console and Ambiguity/Unauthenticated Flows

Normalize:

- Client main menu.
- Client profile/subscription/code redirect flows.
- Tenant/client ambiguity mode.
- Unauthenticated code lookup.

## i18n Requirements

All user-facing labels and instructions must use i18n catalogs.

Spanish canonical labels:

- `8️⃣ Siguiente`
- `9️⃣ Regresar`
- `0️⃣ Cancelar`

English canonical labels:

- `8️⃣ Next`
- `9️⃣ Back`
- `0️⃣ Cancel`

Avoid these old meanings:

- `9` as cancel
- `0` as back/return
- `8` as previous

## Testing Strategy

Use TDD for implementation.

Test layers:

1. Unit tests for `whatsapp_navigation.py`.
2. Tenant Admin Console regression tests for:
   - `0` cancels active flows.
   - `9` returns to previous screen/menu.
   - `8` advances pages where applicable.
3. Client Context Shortcut tests for:
   - `0` closes full context and includes close metadata.
   - `9` returns to parent menu/detail without clearing context.
4. Master Console tests for:
   - `0` cancels or closes session.
   - `9` returns to previous menu instead of cancelling.
5. Client Console and ambiguity tests for consistent menu labels and behavior.
6. i18n catalog tests to detect forbidden phrases/patterns:
   - `0 Volver`, `0 Back`
   - `9 cancelar`, `9 cancel`
   - `8 Anterior`, `8 Previous`
   - `9 Siguiente`, `9 Next`

## Risks

- Existing tests may encode old navigation semantics and require careful updates.
- Some flow-specific uses of `9` currently clear sessions; changing them may expose hidden assumptions.
- Subscriptions pagination change is user-visible and must be verified end-to-end.
- Master Console has separate hardcoded messages, so drift risk is high unless tests cover it.

## Acceptance Criteria

- Every WhatsApp console uses the same numeric contract:
  - `8` = next
  - `9` = back
  - `0` = cancel
- No i18n catalog entry or hardcoded console string presents conflicting semantics.
- All relevant backend WhatsApp tests pass.
- New regression tests cover navigation semantics in each console family.
- Client Context Shortcut still closes all required Evolution sessions through existing `close_jids` contract.
- Documentation mentions the global navigation rule.
