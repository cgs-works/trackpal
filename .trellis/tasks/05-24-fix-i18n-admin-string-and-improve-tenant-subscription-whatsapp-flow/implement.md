# Implementation Plan — i18n + WhatsApp subscriptions flow

## Phase 1 — Frontend i18n label

1. Add/adjust frontend i18n keys:
   - ES: `frontend.clients.password` => `Contraseña`
   - EN: `frontend.clients.password` => `Password`
2. Replace hardcoded `Contraseña inicial` in `TenantDashboardView.vue` with i18n lookup.
3. Verify template renders key in create-client mode.

## Phase 2 — WA i18n hardcodes removal

1. Add WA catalog keys for subscriptions header and statuses in ES/EN.
2. Refactor formatter to resolve header/status via i18n translator.
3. Ensure no Spanish literals remain in formatter output for these fields.

## Phase 3 — Interactive pagination/navigation

1. Locate filtered subscriptions list step handler.
2. Add page state to session (`page`, `status`).
3. Implement pagination slicing: 7 items/page.
4. Render commands conditionally:
   - `8` previous page (if page > 1)
   - `9` next page (if page < total_pages)
   - `0` cancel/exit always
5. Build per-page `selection_map` with keys `1..7` only.
6. Route command inputs (`8`,`9`,`0`) before detail selection lookup.

## Phase 4 — Verification

1. Run focused backend tests for tenant subscriptions flow.
2. Run frontend build (`npm run build`) to validate template changes.
3. If risk signals appear, run broader backend suite subset.

## Done Criteria

- PRD acceptance criteria all checked.
- No hardcoded target strings remain.
- WA list flow supports consistent cancel/back-next semantics.
- Pagination stable with large subscription lists.