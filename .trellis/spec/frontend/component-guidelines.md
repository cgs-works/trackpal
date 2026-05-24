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