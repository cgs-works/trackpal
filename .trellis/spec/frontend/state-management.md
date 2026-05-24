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