# Frontend Coding Conventions

## Language & Runtime

- JavaScript (ES modules) — no TypeScript currently
- Vue 3 Composition API with `<script setup>` syntax
- Node.js (managed via `package.json`, lockfile `package-lock.json`)

## Project Structure

- `src/router/` — route definitions and navigation guards
- `src/stores/` — Pinia stores (one file per store)
- `src/services/` — API client and other service modules
- `src/views/` — page-level components, one per route
- No `components/` directory yet — reusable UI components are co-located in views or extracted as needed

## Naming

| Artifact | Convention | Example |
|----------|-----------|---------|
| Files | camelCase | `auth.js`, `LoginView.vue` |
| Vue components (single-file) | PascalCase | `LoginView.vue`, `MasterDashboardView.vue` |
| Pinia stores | camelCase, `use<Name>Store` | `useAuthStore` |
| Route names | kebab-case | `master-dashboard`, `tenant-dashboard` |
| Axios instance | lowercase | `api` |
| Environment variables | `VITE_UPPER_SNAKE_CASE` | `VITE_API_URL` |

## Vue Component Patterns

### Script Setup

All components use `<script setup>` with explicit imports:

```vue
<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '../services/api'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const authStore = useAuthStore()
</script>
```

### Template

- Scoped styles via `<style scoped>`
- No Renderless components or slots currently
- Event handlers use `@submit.prevent` for forms
- Error messages use `v-if`, not `v-show`

### Styling

- CSS custom properties defined in `:global(:root)` inside scoped blocks
- CSS class naming: kebab-case
- Layout: flexbox and CSS Grid
- Responsive breakpoints via `@media (max-width: 760px)` or `720px`
- No CSS framework (Tailwind, Bootstrap) — raw CSS

## State Management (Pinia)

- Store created with `defineStore('name', () => { ... })` — composition API style
- State variables use `ref()`, getters use `computed()`
- Actions are async functions that directly mutate refs
- Auth state persisted to `localStorage` manually (no pinia-persistedstate plugin)

## API Patterns

- Axios interceptors handle token injection and 401 responses globally
- Login action uses a direct `axios.post()` call (not the `api` instance) to avoid interceptor recursion
- Error handling: try/catch in views, extract `error.response?.data?.detail` for user-facing messages
- API error helper pattern:

```js
function getApiError(error, fallback) {
  const detail = error.response?.data?.detail
  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg || item.message || String(item)).join(', ')
  }
  return detail || error.response?.data?.message || fallback
}
```

## Router Patterns

- Routes with `meta.requiresAuth` and `meta.role` for access control
- Lazy loading: `component: () => import('...')` for all views except LoginView
- Navigation guard in `router/index.js` handles:
  - Redirect to `/login` when unauthenticated
  - Role mismatch redirect to correct dashboard
  - Redirect to dashboard from `/login` when already authenticated
- Catch-all route `/:pathMatch(.*)*` redirects unknown paths to `/login`

## Environment Variables

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `VITE_API_URL` | No | `http://localhost:8000/api/v1` | Backend API base URL |

## No Tests

No test files exist in the frontend directory. Tests are not part of the current frontend setup.

## Dev Server

Vite dev server proxies `/api` requests to `http://localhost:8000` (configured in `vite.config.js`). This avoids CORS issues during development.
