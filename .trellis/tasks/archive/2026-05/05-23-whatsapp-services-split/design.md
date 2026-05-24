# Design — WhatsApp services split

## Scope

- `services/whatsapp_tenant_console_service.py`
- `services/whatsapp_console_service.py`
- `services/whatsapp_master_console_facade.py`

## Approach

- Convert each huge file into package.
- Partition by flow/state-machine concerns:
  - constants/keys
  - session/context helpers
  - menu routing
  - active-flow handlers
  - CRUD action handlers
  - formatter/translation helpers
- Keep facade entrypoints and service public methods stable.

## Constraints

- No conversation-flow behavior changes.
- Keep reset/help/fallback semantics.
- Keep i18n keys and output behavior.
- LoC target <=200, max 240 with debt note.

## Risks

- State transition regressions.
- Subtle locale/phone/session regressions.

## Mitigations

- Golden-path tests for flow transitions.
- Stepwise split with immediate regression checks.
