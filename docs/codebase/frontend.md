# Frontend

Stack: **Vue 3 (Composition API) + Vue Router + Pinia + Vite**

## Directory structure

```
frontend/src/
├── main.js                      # App bootstrap (Pinia, Router, mount)
├── App.vue                      # Root component (<router-view />)
├── style.css                    # Global styles
├── router/
│   └── index.js                 # Route config with auth guards
├── stores/
│   └── auth.js                  # Pinia store (token, user, login/logout)
├── services/
│   └── api.js                   # Axios instance with JWT interceptor
└── views/
    ├── LoginView.vue            # Unified login form
    ├── MasterDashboardView.vue  # Tenant management dashboard
    └── TenantDashboardView.vue  # Placeholder + profile management
```

## Routes

| Path | Guard | Component |
|---|---|---|
| `/login` | Public (redirects if logged in) | `LoginView` |
| `/master/dashboard` | Master only | `MasterDashboardView` |
| `/admin/dashboard` | Tenant only | `TenantDashboardView` |
| `*` | — | Redirects to `/login` |

## Auth store

- `login(username, password)` — calls `POST /auth/login`, stores `access_token`, `refreshToken`, `user`.
- `logout()` — calls `POST /auth/logout`, clears stored state, redirects to `/login`.
- `initialize()` — called on app mount; restores token from `localStorage`, validates with `/me`.
- Actions guarded by `isMaster` / `isTenant` getters based on `user.role`.

## API service

Axios instance with:
- Base URL from Vite proxy (`/api` → `localhost:8000`)
- `Authorization: Bearer` interceptor injecting `access_token`
- 401 response interceptor clearing auth and redirecting to `/login`
- On 401, token is cleared but no auto-refresh is implemented (planned improvement)

## Build

```bash
npm run build     # Production build
npm run dev       # Dev server with proxy
```
