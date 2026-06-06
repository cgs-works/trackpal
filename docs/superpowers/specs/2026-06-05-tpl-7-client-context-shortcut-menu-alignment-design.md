# TPL-7 Client Context Shortcut Menu Alignment Design

Date: 2026-06-05
Related: Linear TPL-7, `spec-tpl-7-client-context-shortcut.md`
Status: Approved design

## Purpose

Align the Client Context Shortcut so the contextual root menus for active and inactive clients match the options actually handled by the backend, preserve coherent contextual navigation, and keep the current-screen re-render behavior consistent on errors and successful actions.

## Scope

In scope:

- Active client contextual root menu behavior under `active_menu`.
- Inactive client contextual root menu behavior under `inactive_menu`.
- Immediate child screens needed to keep contextual navigation coherent: detail, edit field, edit value, deactivate confirmation, inactive delete confirmation, and subscription handoff.
- Rendering helpers local to the Client Context Shortcut flow.
- Canonical i18n key usage for active and inactive contextual root menus.
- Optional phone display rules for normal phone targets and LID-only targets.
- Backend regression tests for the corrected routing and rendering contract.
- Technical documentation updates limited to the affected Client Context Shortcut flow section.

Out of scope:

- Global mojibake cleanup in backend or frontend catalogs.
- Global terminology cleanup such as removing “Tenant/tenant” everywhere.
- Renaming models, routes, variables, or i18n namespaces.
- Broad navigation-system refactors or introduction of a new navigation stack.
- n8n changes.
- Copy cleanup outside the Client Context Shortcut flow.

## Current problem

The backend currently renders full contextual menus for active and inactive clients, but the handlers do not honor the rendered option order.

For active clients, the menu shown to the admin offers:

- `1` Ver detalle
- `2` Editar cliente
- `3` Crear suscripción
- `4` Desactivar cliente
- `5` Eliminar cliente
- `0` Cancelar

But the current handler only supports:

- `1` -> Ver detalle
- `2` -> Crear suscripción

This means `2` performs the wrong action and `3`, `4`, and `5` fall into invalid-option handling. The invalid path also re-renders an outdated short menu instead of the full current screen.

The inactive flow has the same class of problem: the visible root menu and the handler option mapping are also misaligned.

## Chosen approach

Use a surgical alignment patch over the current flow.

- Keep the existing dispatcher and state-machine shape.
- Correct the root menu handlers so they match the visible menus.
- Add local render helpers for current-screen re-rendering.
- Use canonical contextual menu keys as the source of truth.
- Keep the change focused on this contextual flow and its direct transitions.

Rejected alternatives:

1. i18n-heavy patch with more duplicated keys for mini-menus and invalid-option variants. Rejected because it preserves the root cause and increases drift risk between visible menu and backend behavior.
2. Broad contextual-navigation refactor. Rejected because it exceeds the issue scope and conflicts with the explicit non-goal of avoiding a wide navigation rewrite.

## Approved behavior

### Active root menu: `active_menu`

Visible options:

- `1` -> View detail -> `active_detail`
- `2` -> Edit client -> `active_edit_field`
- `3` -> Create subscription -> `_start_context_subscription()`
- `4` -> Deactivate client -> `active_deactivate_confirm`
- `5` -> Block deletion for active client, explain that deactivation is required first, stay in `active_menu`
- `0` -> Cancel/close context using the existing universal cancel behavior

Root-menu rules:

- Do not show `9` in the root menu.
- If the admin sends `9` at the root menu, treat it as an invalid option.
- Any invalid input at `active_menu` returns generic invalid-option text plus the full active contextual menu.
- Invalid input at `active_menu` refreshes contextual TTL because the system is recovering the user with the full current screen.
- Option `5` does not transition to any delete-confirmation step.

### Inactive root menu: `inactive_menu`

Visible options:

- `1` -> View detail -> `inactive_detail`
- `2` -> Edit client -> `inactive_edit_field`
- `3` -> Reactivate client
- `4` -> Delete client -> `inactive_delete_confirm`
- `0` -> Cancel/close context using the existing universal cancel behavior

Root-menu rules:

- Do not show `9` in the root menu.
- If the admin sends `9` at the root menu, treat it as an invalid option.
- Any invalid input at `inactive_menu` returns generic invalid-option text plus the full inactive contextual menu.
- Invalid input at `inactive_menu` refreshes contextual TTL for the same reason as `active_menu`.

### Current-screen error rule

On any contextual screen, selection errors must re-render the current screen, not a generic tenant menu and not an outdated shortcut mini-menu.

Required behavior by screen:

- `active_menu` -> invalid-option text + full active menu
- `active_detail` -> invalid-option text + full active detail screen and its options
- `active_edit_field` -> invalid-option text + full editable-fields menu
- `active_edit_value` -> field validation or generic error + same expected-value prompt
- `active_deactivate_confirm` -> confirmation error + same confirmation prompt
- `inactive_menu` -> invalid-option text + full inactive menu
- `inactive_detail` -> invalid-option text + full inactive detail screen and its options
- `inactive_edit_field` -> invalid-option text + full editable-fields menu
- `inactive_edit_value` -> field validation or generic error + same expected-value prompt
- `inactive_delete_confirm` -> confirmation error + same confirmation prompt

### Successful actions

After a successful action, the system must reply with:

`result message + updated contextual screen`

Required cases:

- Successful edit -> success text + updated detail screen + detail options
- Successful deactivation -> success text + updated inactive root menu
- Successful reactivation -> success text + updated active root menu
- Successful inactive deletion -> success text + unregistered-target contextual menu
- Active option `5` -> logical block text + active root menu

### Create subscription handoff

Option `3` from `active_menu` must preserve the current architectural behavior of `_start_context_subscription()`:

1. Create the normal admin subscription-flow session.
2. Preselect `client_id` and `client_name`.
3. Render the subscription service list.
4. Clear `wa:client_ctx:{admin_phone}`.
5. Continue in the standard subscription flow.

This is required to avoid two competing conversational states.

## Navigation contract for this spec

This spec does not introduce a new back-stack. Navigation remains explicit per screen.

### Root contextual menus

For both `active_menu` and `inactive_menu`:

- `0` cancels/closes the contextual flow.
- `9` is not shown and is treated as invalid input.
- `8` is not shown and is treated as invalid input unless a future screen explicitly supports pagination or forward movement.

### Child contextual screens

Required `9` behavior:

- active detail -> back to `active_menu`
- active edit field -> back to full active detail screen
- active edit value -> back to active edit field screen
- active deactivate confirm -> back to `active_menu`
- inactive detail -> back to `inactive_menu`
- inactive edit field -> back to full `inactive_detail`
- inactive edit value -> back to `inactive_edit_field`
- inactive delete confirm -> back to `inactive_menu`

Required `8` behavior:

- If a child screen does not explicitly support forward/paginated navigation, `8` is invalid and re-renders the current screen.

## Rendering and i18n design

The flow must use one canonical root-menu key per contextual state:

- `wa.tenant.client_context.menu.active`
- `wa.tenant.client_context.menu.inactive`

Legacy parallel keys such as `wa.tenant.client_context.active.menu_text` and `wa.tenant.client_context.inactive.menu_text` may remain temporarily if removal is risky, but they must not remain the source of truth for this flow.

### Generic invalid option key

Use `wa.tenant.client_context.invalid_option` as the generic error line. The full reply is composed as:

`invalid option text + current rendered screen`

Avoid storing old mini-menus inside `active.invalid_option` or `inactive.invalid_option`.

### Local render helpers

Implementation should add small helpers local to the Client Context Shortcut module, for example:

- active root menu renderer
- inactive root menu renderer
- detail renderer
- optional phone-line renderer
- helper that composes `error + current screen`

These helpers are specific to this flow and must not render the global tenant main menu.

## Identity and phone-display rules

Show the phone line only when a real phone number exists, using either target context data or client data.

Rules:

- If a real phone exists, show `Teléfono: {phone}` or the locale-equivalent label.
- If the contextual target is LID-only or no real phone exists, omit the entire phone line.
- Never render placeholders such as `Teléfono: --`.

This rule applies to root menus, detail screens, and any contextual block/success screen that repeats client identity.

## Testing scope

Backend tests must validate contract and state, not long copy blocks.

Minimum required cases:

1. `2` from `active_menu` enters edit flow and does not start subscription.
2. `3` from `active_menu` starts subscription, clears shortcut context, and leaves the admin session in the normal subscription flow.
3. `4` from `active_menu` opens deactivate confirmation.
4. `5` from `active_menu` does not delete, shows the logical block message, re-renders the active root menu, and keeps `step = active_menu`.
5. Invalid input from `active_menu` re-renders the full active menu and refreshes TTL.
6. `9` from `active_menu` is invalid and re-renders the full active menu.
7. `9` from `active_detail` returns to the active root menu.
8. `9` from `active_edit_field` returns to the full detail screen, not only a header.
9. Successful deactivation shows the inactive root menu.
10. `1` from `inactive_menu` shows inactive detail.
11. `3` from `inactive_menu` reactivates and shows the active root menu.
12. `4` from `inactive_menu` enters inactive delete confirmation and successful confirmation shows the unregistered-target menu.
13. Invalid input from `inactive_menu` re-renders the full inactive menu and refreshes TTL.
14. `9` from `inactive_menu` is invalid and re-renders the full inactive menu.
15. LID-only contextual targets hide the phone line in root menu and detail rendering.

If fake Redis or equivalent test doubles can expose TTL refresh behavior directly, assert it. If not, assert the persisted context remains active and consistent after recognized recovery paths.

## Documentation updates

Update only the affected Client Context Shortcut section in `docs/architecture/whatsapp-console-flow.md`.

The documentation must reflect:

- active root menu: detail, edit, create subscription, deactivate, blocked delete, cancel
- inactive root menu: detail, edit, reactivate, delete, cancel
- root menus do not show `9`
- `9` at root is invalid
- errors re-render the current contextual screen
- successful actions return result text plus the updated contextual screen

This spec does not require broader documentation cleanup outside that section.

## Acceptance criteria

- Active and inactive contextual root handlers match their visible menus.
- `2` from the active root menu edits instead of creating a subscription.
- `3` from the active root menu creates a subscription instead of failing as invalid.
- `4` from the active root menu opens deactivate confirmation.
- `5` from the active root menu does not delete the client and keeps the admin in `active_menu`.
- Invalid input at either contextual root menu re-renders the full current root menu and refreshes TTL.
- Root contextual menus do not show `9`, and `9` at root is invalid.
- Child screens honor contextual back-navigation with `9`.
- Phone display is shown only when a real phone exists and is hidden for LID-only targets.
- Successful actions render both the result message and the updated contextual screen.
- Backend regression tests pass.

## Non-goals

- Global copy cleanup in WhatsApp catalogs.
- Broader cleanup of old i18n keys outside what is necessary for this flow to stop using them as its source of truth.
- Navigation-contract refactors outside the Client Context Shortcut flow.
- Changes to unrelated tenant-console flows.
- n8n workflow changes.
