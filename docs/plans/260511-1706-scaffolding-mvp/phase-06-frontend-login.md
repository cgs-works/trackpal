# Phase 6: Frontend: Login

**Complexity:** M
**Dependencies:** Phase 1, Phase 3

## Objective
Build the Vue 3 login page and establish global auth state using Pinia.

## Preconditions
- Vue Vite project exists.
- Backend `/api/v1/auth/login` functioning.

## Tasks
1. Context: `frontend/src/views/LoginView.vue`, `frontend/src/stores/auth.ts`, `frontend/src/router/index.ts`.
2. Implement Pinia store (`auth.ts`):
   - Manage JWT token, `login(username, password)`, `logout()`, `role` state.
3. Implement LoginView.vue:
   - Form with username and password.
   - Display error messages on 401/400.
4. Implement Vue Router:
   - Navigation Guard to check for auth state.
   - Redirect to `/master/dashboard` or `/admin/dashboard` based on role after successful login.
5. Setup Axios instance:
   - Interceptor to append `Authorization: Bearer <token>` to requests.

## Verification
- Commands:
  - `cd frontend && npm run dev`
- Expected results:
  - Entering correct credentials logs user in and redirects based on role.
  - Invalid credentials display an alert or error message.

## Exit Criteria
- User can log in.
- Axios requests automatically attach JWT.
