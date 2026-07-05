# Tasks: Tenant WhatsApp Self-Linking

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 2,100-2,300 additions/deletions |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 Backend Evolution client → PR 2 Backend service/API/i18n → PR 3 Frontend API/hook/UI primitive → PR 4 Frontend section/settings/i18n polish |
| Delivery strategy | ask-on-risk |
| Chain strategy | feature-branch-chain |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: feature-branch-chain
400-line budget risk: High

## Implementation Notes

- Strict TDD is enabled in `openspec/config.yaml`; use RED → GREEN → TRIANGULATE → REFACTOR for backend and frontend work.
- Backend verification commands: `cd backend && uv run pytest` for full suite; run targeted pytest files during focused sessions.
- Frontend verification commands: `cd frontend && npm test` and `cd frontend && npm run lint`.
- No database schema change or Alembic migration is expected for this feature.
- Keep backend deployable before frontend usage; each PR below has a rollback boundary.

## PR 1 — Backend Evolution client lifecycle methods

Rollback boundary: revert `backend/app/services/evolution_client/client.py`, `backend/app/services/evolution_client/__init__.py`, and `backend/tests/test_evolution_client_whatsapp_link.py`.

- [x] 1. RED: add Evolution lifecycle client tests in `backend/tests/test_evolution_client_whatsapp_link.py`.
  - Cover `get_instance_status`, `get_qr_code`, `pair_instance`, and `logout_instance` using instance-token `apikey` headers, not global API-key headers.
  - Assert routes for `/instance/status`, `/instance/qr`, `/instance/pair`, and `/instance/logout` and pairing payload `{ "phone": phone }`.
  - Assert response normalization for `code`/`pairingCode` and `qrcode`/`qr`/`base64`.
  - Assert 401/403 maps to `EvolutionClientError("invalid_instance_token")`, 5xx/request errors/missing base URL map to `EvolutionClientError("service_unavailable")`, and other 4xx maps to `EvolutionClientError("request_failed")`.
  - Verify: targeted pytest fails for missing methods/errors: `cd backend && uv run pytest tests/test_evolution_client_whatsapp_link.py`.

- [x] 2. GREEN: implement Evolution client support in `backend/app/services/evolution_client/client.py`.
  - Add `EvolutionClientError` with `code` and optional `status_code`.
  - Add `_instance_headers(instance_token: str)` and `_send_instance_request(...)` without logging tokens.
  - Add async methods `get_instance_status`, `get_qr_code`, `pair_instance`, and `logout_instance` with Pydantic-compatible type hints.
  - Reuse `_response_data()` where available and normalize QR/pairing response shapes.
  - Export `EvolutionClientError` from `backend/app/services/evolution_client/__init__.py` if imports require it.
  - Verify: `cd backend && uv run pytest tests/test_evolution_client_whatsapp_link.py` passes.

- [x] 3. TRIANGULATE/REFACTOR: harden client edge cases.
  - Add or adjust tests for empty Evolution responses, missing QR/code fields, and logout returning no content.
  - Refactor route constants/helpers so any production route-shape change is isolated to `client.py`.
  - Verify: targeted client tests pass and no token values appear in log messages.

## PR 2 — Backend tenant WhatsApp-link API, service, router, i18n

Rollback boundary: remove router include from `backend/app/api/v1/router.py`, delete new `whatsapp_link` service/schema/endpoint files, and revert i18n catalog additions.

- [x] 4. RED: add API/service contract tests in `backend/tests/test_whatsapp_link_api.py`.
  - Cover `GET /api/v1/tenant/whatsapp-link/status` returning `{ connected, phone, instance_name }`, where connected is true only when Evolution reports both `connected` and `loggedIn` true.
  - Cover `POST /pair` with empty `{}` body, reject client-supplied phone via schema, no-phone 400, already-connected 409, and success `{ code }`.
  - Cover `GET /qr` success `{ qrcode }`, no-phone 400, and already-connected 409.
  - Cover `POST /disconnect` calling logout and returning 200 `{ connected: false }` without deleting instance or clearing tenant fields.
  - Cover missing instance name/token 400, Evolution downtime 503, invalid instance token 502, missing JWT 401, inactive tenant 403, client role 403, starter tenant concealment 404, and master support context bypass.
  - Verify: targeted pytest fails for missing API: `cd backend && uv run pytest tests/test_whatsapp_link_api.py`.

- [x] 5. RED: add i18n catalog assertions for backend and frontend keys.
  - In `backend/tests/test_whatsapp_link_api.py` or a focused i18n test file, assert both English and Spanish catalogs contain `errors.whatsapp_link.instance_not_configured`, `phone_required`, `already_connected`, `service_unavailable`, `invalid_instance_token`, and `request_failed`.
  - Assert frontend catalog keys listed in `design.md` under `frontend.whatsapp_link.*` exist in both `catalogs_en_frontend.py` and `catalogs_es_frontend.py`.
  - Verify: targeted pytest fails until catalog keys are added.

- [x] 6. GREEN: add schemas in `backend/app/schemas/whatsapp_link.py`.
  - Implement `WhatsAppLinkStatusResponse`, `WhatsAppPairRequest` with `ConfigDict(extra="forbid")`, `WhatsAppPairResponse`, `WhatsAppQrResponse`, and `WhatsAppDisconnectResponse`.
  - Verify: schema-related tests progress from validation failures to passing.

- [x] 7. GREEN: implement service orchestration in `backend/app/services/whatsapp_link_service.py`.
  - Load the active tenant by tenant id, validate `is_active`, `evolution_instance_name`, and encrypted `evolution_instance_token`.
  - Decrypt the token with the project encryption helper (`decrypt_value`) and treat decrypt/empty-token failures as `whatsapp_link.invalid_instance_token`.
  - Implement `get_status`, `request_pairing_code`, `get_qr_code`, and `disconnect` using the singleton `evolution_client`.
  - Enforce stored `tenant.whatsapp_phone` for pair/QR only; do not accept a client phone value.
  - Check status before pair/QR and raise already-connected before requesting a code/QR.
  - Map `EvolutionClientError` codes to `UserFacingError` codes.
  - Verify: service-focused API tests pass.

- [x] 8. GREEN: add FastAPI router in `backend/app/api/v1/endpoints/whatsapp_link.py` and register it in `backend/app/api/v1/router.py`.
  - Prefix router with `/tenant/whatsapp-link` and tag `tenant-whatsapp-link`.
  - Use existing dependencies from `backend/app/api/dependencies.py` for DB session, current user, active tenant id, and tenant plan.
  - Explicitly allow only tenant and master roles; reject client role.
  - Enforce Pro plan for tenant users and bypass plan gate for master support context.
  - Translate `UserFacingError` with request locale and return correct HTTP status from the design error map.
  - Verify: `cd backend && uv run pytest tests/test_whatsapp_link_api.py` passes.

- [x] 9. TRIANGULATE/REFACTOR: add catalog translations and run backend suite.
  - Add backend error translations to `backend/app/core/i18n/catalogs_en_general.py` and `backend/app/core/i18n/catalogs_es_general.py`.
  - Add frontend UI translations to `backend/app/core/i18n/catalogs_en_frontend.py` and `backend/app/core/i18n/catalogs_es_frontend.py`.
  - Confirm no Alembic migration files were created.
  - Verify: `cd backend && uv run pytest` passes.

## PR 3 — Frontend API service, polling hook, Tabs primitive

Rollback boundary: delete `whatsapp-link-api.ts`, `use-whatsapp-link-polling.ts`, associated tests, and `tabs.tsx` if newly added.

- [x] 10. RED: add frontend API service tests in `frontend/src/features/admin/services/__tests__/whatsapp-link-api.spec.ts`.
  - Mock `@/lib/api` and assert exact calls to `/tenant/whatsapp-link/status`, `/tenant/whatsapp-link/pair` with `{}`, `/tenant/whatsapp-link/qr`, and `/tenant/whatsapp-link/disconnect`.
  - Assert typed response values are returned unchanged.
  - Verify: targeted Vitest run fails for missing service, or run full frontend tests: `cd frontend && npm test`.

- [x] 11. GREEN: implement `frontend/src/features/admin/services/whatsapp-link-api.ts`.
  - Export `WhatsAppLinkStatus`, `PairingCodeResponse`, `QRCodeResponse`, `DisconnectResponse`, `getWhatsAppLinkStatus`, `requestPairingCode`, `getQRCode`, and `disconnectWhatsApp`.
  - Verify: API service tests pass.

- [x] 12. RED: add polling hook tests in `frontend/src/features/admin/hooks/__tests__/use-whatsapp-link-polling.spec.tsx`.
  - Use Vitest fake timers to assert immediate poll, 5-second interval, stop on connected, single `onConnected`, 60-second timeout, cleanup on unmount, and transient error surfacing through `onError`.
  - Verify: targeted/full frontend tests fail for missing hook.

- [x] 13. GREEN/REFACTOR: implement `frontend/src/features/admin/hooks/use-whatsapp-link-polling.ts`.
  - Encapsulate default `intervalMs = 5000`, `timeoutMs = 60000`, `isPolling`, `elapsedMs`, and `stop()`.
  - Clear all timers on unmount or disabled state changes.
  - Keep status polling logic UI-agnostic and call `getWhatsAppLinkStatus()` from the API service.
  - Verify: hook tests pass.

- [x] 14. GREEN: add or verify Tabs primitive at `frontend/src/components/ui/tabs.tsx`.
  - Discovery target: if `frontend/src/components/ui/tabs.tsx` exists, reuse and adjust imports only as needed; if absent, add the shadcn/base-compatible Tabs component.
  - Keep component API compatible with intended `Tabs`, `TabsList`, `TabsTrigger`, and `TabsContent` usage in the WhatsApp section.
  - Verify: `cd frontend && npm test` and `cd frontend && npm run lint` pass for PR 3 scope.

## PR 4 — Frontend WhatsApp section, settings integration, UI flows

Rollback boundary: revert `settings-page.tsx`, delete `whatsapp-link-section.tsx`, and remove related frontend tests/i18n keys from catalogs if desired.

- [x] 15. RED: add component tests in `frontend/src/features/admin/components/__tests__/whatsapp-link-section.spec.tsx`.
  - Mock `whatsapp-link-api`, `use-whatsapp-link-polling` where useful, Sonner toast, and translations.
  - Cover initial skeleton/load, connected state with Disconnect button, disconnected state with pairing tabs, no-phone alert with no pairing UI, backend detail error display, and fallback translated errors.
  - Cover pairing code request displaying the 8-digit code and starting polling.
  - Cover QR tab loading an image with `data:image/png;base64,...` and refreshing near expiry while disconnected.
  - Cover polling success transitioning to connected and calling `toast.success` with `frontend.whatsapp_link.success_linked`.
  - Cover timeout alert and retry action.
  - Cover disconnect confirmation calling API and returning to disconnected UI.
  - Verify: tests fail until component exists.

- [x] 16. RED: update settings page tests in `frontend/src/features/admin/components/__tests__/settings-page.spec.tsx` or the existing settings-page test file.
  - Mock `WhatsappLinkSection`.
  - Assert Pro tenant sees `frontend.whatsapp_link.section_title`.
  - Assert starter/non-Pro tenant admin does not see the WhatsApp section.
  - Assert master support context sees the WhatsApp section regardless of tenant plan.
  - Verify: tests fail until settings integration exists.

- [x] 17. GREEN: implement `frontend/src/features/admin/components/whatsapp-link-section.tsx`.
  - Use existing shadcn/ui components (`Card`, `Button`, `Alert`, `Badge`, `Skeleton`, `AlertDialog`) and the Tabs primitive.
  - Display phone, instance name, and status badge states `Connected`, `Disconnected`, and `Connecting` via `t("frontend.whatsapp_link.*")` keys only.
  - Implement pairing-code flow with generated code display, translated instructions, loading state, error state, and polling start.
  - Implement QR flow with base64 normalization, translated instructions, manual refresh, automatic refresh around 35 seconds, and cleanup on unmount/connection.
  - Implement disconnect confirmation, API call, optimistic cleanup of pairing/QR state, success feedback, and status refresh.
  - Do not hardcode user-visible strings; all labels, alerts, buttons, and toast text must use `t()` keys.
  - Verify: component tests pass.

- [x] 18. GREEN: integrate section into `frontend/src/features/admin/components/settings-page.tsx`.
  - Import `WhatsappLinkSection` and a lucide WhatsApp-related icon such as `MessageCircle`.
  - Extend the settings section id union with `"whatsapp-link"`.
  - Add the menu section under the existing Pro/master-support gate (`showProSettings` behavior).
  - Add the render switch case returning `<WhatsappLinkSection />`.
  - Verify: settings-page tests pass.

- [x] 19. TRIANGULATE: polish accessibility, responsive layout, and error details.
  - Ensure buttons have translated accessible names, QR image has translated alt text, alerts announce meaningful titles/descriptions, and keyboard navigation works for tabs/dialog.
  - Ensure mobile layout uses flex/grid with `gap-*` utilities and avoids `space-x-*`/`space-y-*` patterns per project style.
  - Ensure API error extraction handles string `detail` and validation arrays.
  - Verify: add/adjust tests for accessibility names and error extraction where gaps are found.

- [x] 20. REFACTOR/VERIFY: run full frontend quality gates.
  - Verify: `cd frontend && npm test` passes.
  - Verify: `cd frontend && npm run lint` passes.
  - Confirm no user-visible hardcoded Spanish/English strings remain in `frontend/src/features/admin/components/whatsapp-link-section.tsx` except stable non-visible constants.

## Final Cross-PR Verification

- [x] 21. Run full backend suite: `cd backend && uv run pytest`.
- [x] 22. Run full frontend suite: `cd frontend && npm test`.
- [x] 23. Run frontend lint: `cd frontend && npm run lint`.
- [x] 24. Manual smoke test with a configured Pro tenant in a safe environment:
  - Open Settings and confirm WhatsApp section visibility.
  - Check status display for phone and instance name.
  - Request pairing code and verify polling/timeout behavior.
  - Request QR code and verify image rendering/auto-refresh.
  - Connect successfully and verify success toast.
  - Disconnect and verify status returns to disconnected.
- [x] 25. Rollout check: backend can deploy before frontend; rollback is removing `api_router.include_router(whatsapp_link.router)` and reverting the Settings section integration. No database rollback is required.
