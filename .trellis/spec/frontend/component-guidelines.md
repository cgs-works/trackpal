# Component Guidelines

> Vue component patterns used in Trackpal.

## Overview

- Vue 3 Composition API with `<script setup>`.
- Current UI mostly page components under `views/`.
- Reusable components can be extracted when duplication appears.

## Component Structure

Typical order:
1. `<script setup>` imports/state/computed/actions
2. template markup
3. scoped/global style if needed (project mostly uses global `style.css`)

Examples:
- `frontend/src/views/LoginView.vue`
- `frontend/src/views/TenantDashboardView.vue`
- `frontend/src/views/SubscriptionsView.vue`

## Props Conventions

- Keep props minimal and explicit when extracted components are introduced.
- For current view-heavy structure, prefer store/composable reads over deep prop drilling.

## Styling Patterns

- Primary styles in `frontend/src/style.css`.
- View-specific layout classes in template markup.
- Keep consistency with existing spacing/utility patterns already in views.

## Accessibility

- Use semantic controls (`button`, `label`, `input`).
- Error text visible and understandable.
- Preserve keyboard submit flows in login/forms.

## Common Mistakes

- Overloading one view with unrelated responsibilities.
- Direct API mutation without error feedback.
- Hardcoding i18n strings where catalog/store should supply text.

## Scenario: Tenant subscriptions i18n hardcode removal

### 1. Scope / Trigger
- Trigger: frontend tenant subscriptions view had hardcoded ES strings in errors, labels, placeholders, and button titles.

### 2. Signatures
- View contract: `useI18nStore().t(key: string): string` must be used for UI text.

### 3. Contracts
- Required catalog keys (prefix `frontend.subscriptions.`):
  - `error_load`, `error_reveal`, `error_reminder_settings`
  - `reveal`, `hide`, `optional`, `day`
  - `recipient_mode_tenant_only`, `recipient_mode_client_only`, `recipient_mode_both`
  - `placeholder_profile_name`, `placeholder_cancel_reason`, `placeholder_custom_day`
- Request/response API contracts unchanged.

### 4. Validation & Error Matrix
- Missing i18n key -> fallback/placeholder text from i18n engine (must not crash render).
- API error in subscriptions flows -> must pass translated fallback via `getApiError(error, i18nStore.t(...))`.

### 5. Good/Base/Bad Cases
- Good: `:title="i18nStore.t('frontend.subscriptions.reveal')"`.
- Base: timezone IDs (`UTC`, `Europe/Madrid`) kept raw as data labels.
- Bad: `getApiError(error, 'No se pudieron cargar las suscripciones.')`.

### 6. Tests Required
- Frontend build: `cd frontend && npm run build`.
- Manual assertions:
  - locale switch updates subscriptions labels/placeholders/actions.
  - reveal/hide title switches translated.
  - translated fallback messages shown on API failures.

### 7. Wrong vs Correct
#### Wrong
```vue
errorMessage.value = getApiError(error, 'No se pudieron revelar las credenciales.')
```
#### Correct
```vue
errorMessage.value = getApiError(error, i18nStore.t('frontend.subscriptions.error_reveal'))
```