# Quality Guidelines

> Frontend quality gates used in Trackpal.

## Required Patterns

- Vue 3 `<script setup>` in views/components.
- Pinia for cross-route state.
- Router guards for role/auth access checks.
- API calls through `services/api.js` (except deliberate login direct-call case).
- User-visible API errors surfaced from backend detail fields.

## Forbidden Patterns

- Hardcoding auth tokens/credentials.
- Skipping error handling on async actions.
- Copy-paste route guard logic into multiple views.

## Scenario: Tenant mailbox panel and WhatsApp code lookup handoff

### 1. Scope / Trigger

- Trigger: tenant dashboard mailbox configuration UI + WhatsApp/n8n code lookup flow integration.

### 2. Signatures

- Frontend API calls:
  - `GET /api/v1/tenant/mailbox/`
  - `PUT /api/v1/tenant/mailbox/`
  - `POST /api/v1/tenant/mailbox/test`
  - `POST /api/v1/tenant/mailbox/oauth/{provider}/start`
  - `POST /api/v1/tenant/mailbox/disconnect`
- n8n poll contract consumed indirectly:
  - `GET /api/v1/integrations/n8n/mail/lookups/{job_id}?tenant_id=<uuid>`

### 3. Contracts

- Mailbox panel must render status/method/provider from backend response (`disconnected|connected|error|revoked`).
- IMAP submit path must send `provider=imap_custom` and required IMAP fields.
- OAuth connect buttons must call provider-specific start endpoint and open returned `auth_url`.
- UI must not expose tokens/passwords in state snapshots, error toasts, or logs.
- WhatsApp lookup flow requires n8n to poll with both `lookup_job_id` and `tenant_id` when present.

### 4. Validation & Error Matrix

- `GET mailbox` 404 -> render "not configured" state (not global error screen).
- `PUT mailbox` invalid IMAP fields -> show inline/form error and keep form state.
- `POST mailbox/test` failure -> show user-facing failure status; keep credentials unchanged.
- OAuth start unsupported provider -> show safe backend error detail.
- n8n poll without `tenant_id` -> backend 422 (workflow misconfiguration; treat as integration bug).

### 5. Good/Base/Bad Cases

- Good: user clicks "Connect Google" -> OAuth starts -> dashboard reflects `connected` on return.
- Base: mailbox disconnected -> panel still allows IMAP configure + OAuth connect actions.
- Bad: UI sending poll calls without `tenant_id` or hiding backend error while loop continues.

### 6. Tests Required

- Frontend build: `cd frontend && npm run build`.
- Manual UI checks:
  - mailbox disconnected/connected/error/revoked states
  - IMAP save/test/disconnect flow
  - OAuth button launches provider URL
- Backend-coupled checks:
  - `cd backend && uv run pytest -q` (or focused mailbox suites)
  - verify n8n workflow JSON poll URL includes `tenant_id` query binding.

### 7. Wrong vs Correct

#### Wrong

```js
const pollUrl = `/api/v1/integrations/n8n/mail/lookups/${jobId}`;
```

#### Correct

```js
const pollUrl = `/api/v1/integrations/n8n/mail/lookups/${jobId}?tenant_id=${tenantId}`;
```

## Scenario: Code-services panels must reflect backend governance state deterministically

### 1. Scope / Trigger
- Trigger: Bug 05 introduced master global toggles + tenant per-tenant selection. UI drift caused stale success alerts and missing empty states.

### 2. Signatures
- Components:
  - `frontend/src/components/CodeServicesGlobalPanel.vue`
  - `frontend/src/components/CodeServicesTenantPanel.vue`
- i18n keys:
  - `frontend.code_services.none`

### 3. Contracts
- Global panel must render explicit empty-state message when catalog list is empty.
- Tenant panel must reload latest state before showing success confirmation.
- Reload helpers must not clear success message after a successful save.
- Disabled global services selected by tenant must be shown disabled, not silently removed.

### 4. Validation & Error Matrix
- Save success + reload failure -> show error, no stale success.
- Empty global catalog -> show `frontend.code_services.none`.
- API 400 invalid service keys -> show backend detail, keep selection form visible.

### 5. Good/Base/Bad Cases
- Good: save tenant selection -> reload -> then success toast/message.
- Base: load with existing disabled service -> visible with disabled affordance.
- Bad: set success message before reload and lose it on later load reset.

### 6. Tests Required
- Build check: `cd frontend && npm run build`.
- Manual checks:
  - global empty-state text visible when no services.
  - tenant save shows success only after refreshed data.
  - disabled items visible and not selectable.
- Backend-coupled regression: `cd backend && uv run pytest -q tests/test_code_services.py`.

### 7. Wrong vs Correct
#### Wrong
```js
successMessage.value = t('saved')
await loadServices() // load clears successMessage
```
#### Correct
```js
await loadServices()
successMessage.value = t('saved')
```

## Testing Requirements

- No automated frontend test suite currently.
- Minimum verification: run app and manually test login + role dashboards + subscriptions + i18n language switch.
- For backend-coupled changes validate impacted backend tests too.

## Review Checklist

- Route guards still enforce role boundaries.
- Auth store/login/logout behavior unchanged.
- i18n store loads catalogs and persists locale behavior.
- API error states visible in UI, not swallowed.

## Examples

- Guard logic: `frontend/src/router/index.js`.
- Token/interceptor behavior: `frontend/src/services/api.js`.
- i18n reactive usage: `frontend/src/views/*.vue` with `useI18nStore()`.