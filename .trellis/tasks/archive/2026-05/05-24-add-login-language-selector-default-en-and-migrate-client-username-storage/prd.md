# Add login language selector default EN and migrate client username storage

## Goal

Add login language selector with default English and migrate clients.local_username to username storing tenant prefix + client username for future client panel and WhatsApp client console auth.

## Requirements

- Frontend-only for pre-auth i18n on login/public views. No backend i18n endpoint changes.
- Add language selector in first view (`/login`).
- Default selected language on first visit: English (`en`).
- If user selects non-English language, persist selection in `localStorage`.
- Use one frontend JSON file as source for unauthenticated-page translations.
- JSON i18n must support at least `en` and `es` for login labels/messages.
- Architecture must be reusable for future unauthenticated views (not only login).
- Keep authenticated i18n flow untouched for now.
- In same task, migrate client username storage contract:
  - rename clients column `local_username` -> `username`
  - `clients.username` must store full prefixed username (`<tenant_prefix>_<client_username_local>`)
  - use this value as canonical future client login identifier.

## Acceptance Criteria

- [ ] Login shows language selector with default `en`.
- [ ] Login strings render from frontend JSON i18n file (no backend fetch for pre-auth).
- [ ] Changing language updates login texts immediately.
- [ ] Selected language persists via `localStorage` and reloads on revisit.
- [ ] Pre-auth i18n foundation reusable for future public routes.
- [ ] Backend schema migrated: `clients.local_username` no longer exists; `clients.username` exists.
- [ ] Existing client rows migrated to full prefixed username values.
- [ ] Client create/update flows keep username uniqueness and prefix sync behavior.
- [ ] Relevant backend/frontend tests for touched flows pass.

## Notes

- Keep `prd.md` focused on requirements, constraints, and acceptance criteria.
- Lightweight tasks can remain PRD-only.
- For complex tasks, add `design.md` for technical design and `implement.md` for execution planning before `task.py start`.
