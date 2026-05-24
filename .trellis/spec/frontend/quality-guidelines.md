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