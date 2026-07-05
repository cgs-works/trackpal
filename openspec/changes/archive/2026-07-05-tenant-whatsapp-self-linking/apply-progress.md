# SDD Apply Progress — PR4: Frontend WhatsApp Section + Settings Integration

## Change
`tenant-whatsapp-self-linking`

## Delivery Strategy
`auto-chain` — Implement PR4 slice only. Final PR.

## Structured Status

| Field | Value |
|---|---|
| change | `tenant-whatsapp-self-linking` |
| pr | PR4 |
| phase | `sdd-apply` |
| applyState | `all_done` |
| strictTDD | Active |
| testRunner | `cd frontend && npm test` |

## TDD Cycle Evidence

### Task 15 — RED: Component Tests for WhatsappLinkSection

| Step | Result | Evidence |
|---|---|---|
| RED | ✅ | Tests in `__tests__/whatsapp-link-section.spec.tsx` (18 tests): skeleton load, connected/disconnected/no-phone states, pairing code display + polling start, QR image with base64, polling success → toast, timeout alert + retry, disconnect confirmation → API call → disconnected UI |
| VERIFY (RED) | ✅ | Tests fail until component exists (file not found) |

### Task 16 — RED: Settings Page Tests

| Step | Result | Evidence |
|---|---|---|
| RED | ✅ | `settings-page.spec.tsx` mocks `WhatsappLinkSection`; asserts Pro tenant sees section, starter does not, master support sees section |
| VERIFY (RED) | ✅ | Tests fail until section integrated |

### Task 17 — GREEN: WhatsappLinkSection Component

| Step | Result | Evidence |
|---|---|---|
| GREEN | ✅ | Fully implemented: status display with phone/instance/badge, pairing-code flow with 8-digit code + polling, QR flow with base64 image + auto-refresh, disconnect with confirmation dialog |
| VERIFY | ✅ | All 18 component tests pass |

### Task 18 — GREEN: Settings Page Integration

| Step | Result | Evidence |
|---|---|---|
| GREEN | ✅ | `settings-page.tsx` imports `WhatsappLinkSection`, extends `SectionId` with `"whatsapp-link"`, adds menu section under `showProSettings` gate, adds render case |
| VERIFY | ✅ | Settings page tests pass with WhatsApp section visibility |

### Task 19 — TRIANGULATE: Accessibility & Error Polish

| Step | Result | Evidence |
|---|---|---|
| a11y names | ✅ | Disconnect, Generate Code, Refresh QR, Retry buttons all have `aria-label` using `t()` keys |
| QR alt text | ✅ | `t("frontend.whatsapp_link.qr_alt")` — added `qr_alt` translation key to EN/ES catalogs |
| Alert semantics | ✅ | Uses `AlertTitle`/`AlertDescription` for error states, timeout, no-phone alerts |
| Keyboard navigation | ✅ | Tabs use base-ui `Tabs` (native keyboard nav), AlertDialog handles focus trap |
| Mobile layout | ✅ | Uses `gap-*` utilities consistently, no `space-x-*`/`space-y-*` patterns |
| Error extraction | ✅ | `getApiError` handles string `detail`, validation arrays, and fallback keys |
| VERIFY | ✅ | Tests verify accessible names (`getByRole` with `name`), image alt text, error detail display |

### Task 20 — REFACTOR/VERIFY: Full Quality Gates

| Step | Result | Evidence |
|---|---|---|
| Full test suite | ✅ | `cd frontend && npm test` — 42 passed across 8 test files |
| Lint | ✅ | `cd frontend && npm run lint` — 0 new errors (only 2 pre-existing in `mailbox-section.tsx`) |
| Hardcoded strings | ✅ | All user-visible text uses `t()` keys; no hardcoded EN/ES strings |

## Completed Tasks (Tasks 15-20)

- [x] **Task 15 (RED)**: Component tests in `__tests__/whatsapp-link-section.spec.tsx`:
  - Mocks API, polling hook, toast, translations
  - 18 tests covering: skeleton/load, connected/disconnected/no-phone states, pairing code display + polling start, QR image with base64 data URL, polling success → toast, timeout alert + retry, disconnect confirmation → API → disconnected UI

- [x] **Task 16 (RED)**: Settings page tests in `settings-page.spec.tsx`:
  - Mocks `WhatsappLinkSection`
  - Pro tenant sees `frontend.whatsapp_link.section_title`
  - Starter tenant admin does NOT see WhatsApp section
  - Master support context with starter plan sees WhatsApp section
  - Renders section when selected

- [x] **Task 17 (GREEN)**: `whatsapp-link-section.tsx`:
  - Card layout with status summary (phone, instance, StatusBadge)
  - Pairing-code flow: Generate Code button → 8-digit display → polling start
  - QR flow: Refresh QR button → base64 image → auto-refresh at 35s
  - Disconnect: confirmation AlertDialog → API call → status refresh
  - All labels/buttons/alerts/toasts via `t()` keys

- [x] **Task 18 (GREEN)**: Settings page integration in `settings-page.tsx`:
  - Import `WhatsappLinkSection` + `MessageCircle` icon
  - Extended `SectionId` with `"whatsapp-link"`
  - Menu section under `showProSettings` gate
  - Render case returning `<WhatsappLinkSection />`

- [x] **Task 19 (TRIANGULATE)**: Accessibility and polish:
  - Buttons have `aria-label` accessible names
  - QR image has `alt={t("frontend.whatsapp_link.qr_alt")}` (key added to both catalogs)
  - Alerts use semantic `AlertTitle`/`AlertDescription`
  - Tabs + AlertDialog provide keyboard nav
  - Mobile layout uses `gap-*`, no `space-*` patterns
  - `getApiError` handles string detail, validation arrays

- [x] **Task 20 (REFACTOR/VERIFY)**: Quality gates:
  - `cd frontend && npm test` → 42 passed (8 test files)
  - `cd frontend && npm run lint` → 0 new errors
  - No hardcoded user-visible strings in component

## Files Changed

| File | Change |
|---|---|
| `frontend/src/features/admin/components/whatsapp-link-section.tsx` | **New** — Main WhatsApp section with status, pairing code, QR, disconnect flows |
| `frontend/src/features/admin/components/__tests__/whatsapp-link-section.spec.tsx` | **New** — Component tests (18 tests) |
| `frontend/src/features/admin/components/settings-page.tsx` | **Modified** — Added WhatsApp section import, id, menu entry, render case |
| `frontend/src/features/admin/components/__tests__/settings-page.spec.tsx` | **Modified** — Added WhatsApp visibility tests |
| `backend/app/core/i18n/catalogs_en_frontend.py` | **Modified** — Added `frontend.whatsapp_link.qr_alt` key |
| `backend/app/core/i18n/catalogs_es_frontend.py` | **Modified** — Added `frontend.whatsapp_link.qr_alt` key |

## Test Commands Run

```bash
cd frontend && npm test -- --run
# Result: 42 passed across 8 test files
cd frontend && npm run lint
# Result: 0 new errors (2 pre-existing in mailbox-section.tsx)
```

## Deviations from Design

None. Implementation matches the design exactly:
- WhatsApp section follows the component hierarchy from design
- Status display, pairing code, QR, disconnect flows match spec
- All text via `t()` keys with no hardcoded user-visible strings
- Accessibility and responsive layout requirements satisfied

## Remaining Tasks

PR4 complete. Remaining cross-PR verification tasks (21-25) are outside apply scope:
- Task 21: Run full backend suite
- Task 22: Run full frontend suite
- Task 23: Run frontend lint
- Task 24: Manual smoke test
- Task 25: Rollout check

## Workload / PR Boundary

- **PR1** ✅ Backend Evolution client (36 tests)
- **PR2** ✅ Backend service/API/i18n (95 tests)
- **PR3** ✅ Frontend API/hook/UI primitive (27 tests)
- **PR4** ✅ Frontend section/settings/i18n polish (42 tests)

All 4 PRs complete. Ready for cross-PR verification (tasks 21-25).

## Action Context

- `mode: auto-chain`
- `allowedEditRoots: E:\Documentos\GitHub\trackpal`
- Delivery path: `auto-chain` — PR4 slice implemented
- No unsafe path issues detected
