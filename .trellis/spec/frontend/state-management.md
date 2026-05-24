# State Management

> State conventions in Trackpal frontend.

## Overview

- Global state library: Pinia.
- Router handles URL/navigation state.
- Server state fetched on demand via Axios; no React Query/Vue Query layer currently.

## State Categories

- Global auth/session/role: `stores/auth.js`.
- Global locale/catalog/translations: `stores/i18n.js`.
- View-local UI state: refs inside each `.vue` view.

## When to Use Global State

Promote to store when state is:
- used across multiple routes/views,
- required by router guards,
- needed for app-wide rendering (auth user, locale, catalog).

## Server State

- Fetch via `services/api.js` in views/stores.
- Keep server data normalized enough for current small app scope.
- Handle API errors consistently through detail extraction helper pattern.

## Common Mistakes

- Storing transient form-only state globally.
- Duplicating auth/locale resolution logic in each view.
- Bypassing interceptor-managed API client for authenticated calls.

## Examples

- `frontend/src/stores/auth.js`
- `frontend/src/stores/i18n.js`
- `frontend/src/router/index.js` (depends on auth store)

## Scenario: Public pre-auth locale state (login + future public routes)

### 1. Scope / Trigger
- Trigger: unauthenticated login/public pages need i18n before auth catalog endpoint is available.

### 2. Signatures
- `usePublicI18n()` composable:
  - `locale: Ref<string>`
  - `setLocale(next: string): void`
  - `t(key: string): string`
- Storage key: `publicLocale`
- Source catalog: `frontend/src/i18n/public.json`

### 3. Contracts
- Supported locales: `en`, `es`.
- First visit contract: default locale is `en` when `localStorage.publicLocale` missing/invalid.
- Persistence contract: selected locale stored in `localStorage` and restored on reload.
- Key namespace contract: pre-auth strings use `login.*` keys.

### 4. Validation & Error Matrix
- Unsupported locale in storage -> fallback to `en`.
- Missing translation key -> return key string (render-safe fallback, no crash).
- `localStorage` unavailable/error -> keep in-memory locale `en`, no throw to UI.

### 5. Good/Base/Bad Cases
- Good: login selector change immediately updates labels and persists locale.
- Base: user keeps default `en`; no extra storage writes required.
- Bad: login depends on authenticated `/i18n/catalog` fetch before rendering labels.

### 6. Tests Required
- Frontend build: `cd frontend && npm run build`.
- Manual assertions:
  - Fresh browser session shows EN login text.
  - Switch to ES updates text instantly.
  - Reload keeps ES via `localStorage`.

### 7. Wrong vs Correct
#### Wrong
```js
// Login view waiting authenticated catalog
await i18nStore.fetchCatalog()
```
#### Correct
```js
const { locale, setLocale, t } = usePublicI18n()
```