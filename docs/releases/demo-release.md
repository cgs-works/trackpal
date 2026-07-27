# Demo Tenant release evidence

This is the release gate and evidence record for the plan-aware Demo Tenant initiative in issue #136. It is a how-to and release reference for maintainers, not prospect-facing documentation.

## Recommendation

**Blocked pending credential rotation.** The final source diff restores both n8n workflow exports to `main`, but branch history previously contained a real n8n credential. Treat that credential as compromised: rotate it before release and remove or invalidate the exposed historical value according to the repository's security process.

No remaining functional Demo defect was found after the final QA fixes described below.

## Release contract

- Master manages Demo lifecycle separately from production Tenants.
- First successful Demo Credentials login starts one non-extendable 48-hour period.
- Backend stores authentication and lifecycle only; business state remains in an isolated browser-local Demo Workspace.
- Demo network traffic is limited to auth/logout/refresh, password change, Help, i18n catalog, and lifecycle heartbeat.
- Direct business, integration, Public API, export, and self-deletion requests fail closed with `demo_operation_blocked`.
- Starter exposes the Request simulator only. Pro adds browser-local CRUD and Request/Operation simulator modes.
- Demo locale, tour acknowledgement, and business changes persist in the workspace; credentials, tokens, provider secrets, and chat transcripts do not.

## Automated evidence

Executed on 2026-07-27 from branch `feat-demo-system`.

| Gate | Result | Evidence |
|------|--------|----------|
| Backend Ruff lint | Pass | `uv run ruff check .` |
| Changed Python formatting | Pass | `uv run ruff format --check app/api/v1/endpoints/i18n.py tests/test_i18n.py` |
| Backend pytest | Pass | 1720 passed, 1 skipped, 20 existing warnings |
| Frontend Vitest | Pass | 47 files, 285 tests |
| Frontend ESLint | Pass | `npm run lint` |
| Frontend strict TypeScript + build | Pass | `npm run build`; existing >500 kB bundle warning only |
| Impeccable mechanical detector | Pass | One final run against Demo, Master Demo, login, and navigation targets returned `[]` |

Repository-wide `ruff format --check .` still reports 40 pre-existing files that would be reformatted. This ticket formatted only its two changed Python files to avoid unrelated churn.

## Manual browser QA

Environment: local FastAPI + SQLite QA database and Vite, Chromium automation, desktop and 375 × 812 mobile viewport, dark and light themes.

| Matrix | Result | Observation |
|--------|--------|-------------|
| Master | Pass | Production and Demos tabs remained separate; Starter default, explicit Pro selection, one-time credentials, lifecycle rows, replace/delete actions, and no workspace telemetry were visible. |
| Starter | Pass | Banner showed Starter and browser-local scope; Pro routes returned the normal 404; Request simulator completed `code → service → email → fictitious code`. |
| Pro | Pass | Pro navigation, baseline dashboard, Clients CRUD, Request/Operation tabs, and production-style Tenant Admin menu were available. Client create/update remained local. |
| Lifecycle/browser | Pass for exercised states | Pending became Active on first login; logout/login preserved workspace; an intentionally corrupt workspace restored the safe baseline and showed the recovery notice. Exact expiry and two-heartbeat-failure timing remain covered by automated tests. |
| Localization | Pass after fix | Demo locale changed to Spanish without server-side Tenant Settings and remained Spanish after authenticated reload. Public login and Demo Ended stayed independently localized. |
| Theme | Pass | Mobile login rendered correctly in dark and light modes. |
| Accessibility | Pass for exercised paths | Keyboard-operable login, tabs, dialogs, tour skip confirmation, simulator input, menu Sheet, and contact links exposed programmatic names. Countdown remained non-noisy. |
| Responsive | Pass after fix | Login, banner, dashboard, Settings, mobile navigation, and the orientation tour fit 375 × 812 without document overflow. The tour is portaled to `document.body` so Floating UI transforms cannot collapse the mobile sheet. |
| Storage recovery | Pass | Unsupported/corrupt workspace data reset to the plan baseline with a clear notice and preserved lifecycle. Unavailable/quota states remain covered by component and workspace tests. |
| Network/security | Pass | Normal Demo interaction produced only i18n, Help, heartbeat, auth, and logout traffic. An intentional direct `GET /api/v1/clients` with a Demo JWT returned 403 and `demo_operation_blocked`. Simulator interactions produced no Evolution, n8n, mailbox, Public API, export, or business request. |

## QA defects fixed during this gate

1. Client create/update success toasts rendered the literal `{login}` placeholder. The page now uses the returned canonical username, with component coverage.
2. The mobile orientation tooltip was fixed-positioned inside a transformed Floating UI wrapper, collapsing it to a narrow off-screen sheet. Mobile tooltips now render through a body portal, with regression coverage.
3. Demo locale changes persisted locally but did not replace the active catalog or survive reload. Demo users can now request an `en` or `es` catalog without server persistence, and auth/reload restore the workspace locale.

## Final diff inspection

Before commit:

- Both `n8n/Trackpal WhatsApp Bot.json` and `n8n/Trackpal Subscription Reminders.json` were restored to `main`; no Demo feature requires n8n changes.
- No generated Demo password, QA database, browser screenshot, network capture, server log, or temporary detector artifact is included.
- QA names, phones, and emails were fictional local fixtures.
- No new provider credential, plaintext production password, or real PII was introduced.
- Documentation changes are limited to Demo behavior, the QA-discovered fixes, and this release gate.

## Required release-owner action

1. Rotate the exposed n8n credential and verify the old value is rejected.
2. Decide whether the branch history must be rewritten before publication; a clean final diff does not unexpose an already-pushed secret.
3. Re-run the automated gates from the final release commit after any history rewrite.
4. Record the credential-rotation evidence on issue #136, then change the recommendation from **Blocked** to **Ready**.

## Related documentation

- [ADR-0004: Browser-local Demo Tenant Workspaces](../adr/0004-browser-local-demo-tenant-workspaces.md)
- [Frontend Architecture](../architecture/frontend-architecture.md)
- [API Layer](../architecture/api-layer.md)
- [Database Schema](../architecture/database-schema.md)
- [I18n System](../architecture/i18n-system.md)
- [WhatsApp Console Flow](../architecture/whatsapp-console-flow.md)
- [Business Rules](../project-pdr/business-rules.md)
