# Directory Structure

> Frontend layout used in Trackpal.

## Overview

Vue 3 SPA, JS-only, route-driven views. No TypeScript.
Small shared layers: router, stores, services.

## Directory Layout

```text
frontend/src/
├── App.vue
├── main.js
├── style.css
├── router/
│   └── index.js
├── services/
│   └── api.js
├── stores/
│   ├── auth.js
│   └── i18n.js
└── views/
    ├── LoginView.vue
    ├── MasterDashboardView.vue
    ├── TenantDashboardView.vue
    ├── ClientDashboardView.vue
    └── SubscriptionsView.vue
```

## Module Organization

- `views/`: route pages, page-level UI + API calls.
- `stores/`: cross-page state (auth, i18n catalogs/locale).
- `services/api.js`: Axios instance + interceptors.
- `router/index.js`: routes + auth/role guards.

## Naming Conventions

- View components: `PascalCaseView.vue`.
- Store files: concise domain names (`auth.js`, `i18n.js`).
- JS modules: `snake_or_short-lower` by existing style.

## Examples

- Routing/guards: `frontend/src/router/index.js`.
- Auth flow state: `frontend/src/stores/auth.js`.
- i18n store + catalog loading: `frontend/src/stores/i18n.js`.

## Anti-patterns avoided

- Random shared utils in root.
- Business logic duplicated across multiple views without store/service extraction.