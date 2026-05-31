# Frontend Components

Reusable Vue 3 panels extracted from dashboard views for modularity. All components use `<script setup>` Composition API and `useI18nStore()` for translated strings.

## Component List

| Component | Integrated In | Purpose |
|-----------|---------------|---------|
| `CatalogPanel.vue` | MasterDashboardView, TenantDashboardView | Service and plan CRUD |
| `ClientManagementPanel.vue` | TenantDashboardView | Client CRUD with forms |
| `CodeServicesGlobalPanel.vue` | MasterDashboardView | Global code-service activation toggles |
| `CodeServicesTenantPanel.vue` | TenantDashboardView | Per-tenant code-service multi-select |
| `MailboxConfigPanel.vue` | TenantDashboardView | Mailbox configuration (IMAP, OAuth) |

## CatalogPanel

Manages the tenant catalog: services and their plans.

- Loads services via `GET /api/v1/catalog/services`
- Loads plans via `GET /api/v1/catalog/services/{id}/plans`
- Create/edit/delete operations for services and plans
- Handles duplicate name errors (409) from backend
- Shows user-facing errors with locale-aware messages via `i18nStore`

## ClientManagementPanel

Full client lifecycle management for tenant admins.

- Loads clients via `GET /api/v1/clients`
- Create form: `full_name`, `local_username`, `phone`, `password` (label uses `frontend.clients.password` i18n key)
- Edit form: `full_name`, `username`, `phone` (password hidden on edit)
- Activate / deactivate with confirmation
- Delete inactive clients
- Subscriptions link per client row (routes to `/admin/subscriptions?client={id}`)

## CodeServicesGlobalPanel

Master-only panel for controlling which code-extraction services are globally active.

- Loads status via `GET /api/v1/code-services/global`
- Toggle switches per service key
- Save calls `PUT /api/v1/code-services/global`
- Empty-state: shows `frontend.code_services.none` when catalog empty

## CodeServicesTenantPanel

Tenant panel for selecting which services appear in their WhatsApp code flow.

- Loads selection via `GET /api/v1/code-services/tenants/current`
- Multi-select checkboxes per service
- Disabled services show greyed out (globally inactive)
- Save calls `PUT /api/v1/code-services/tenants/current`
- Loads fresh data before showing success confirmation to avoid stale state

## MailboxConfigPanel

Tenant panel for mailbox configuration used in code extraction.

- Shows current mailbox status: `disconnected`, `connected`, `error`, `revoked`
- IMAP configure: `mailbox_email`, `imap_host`, `imap_port`, `imap_ssl`, `imap_password`
- OAuth connect: buttons for Google and Microsoft, open provider auth URL
- Test connection via `POST /api/v1/tenant/mailbox/test`
- Disconnect via `POST /api/v1/tenant/mailbox/disconnect`
- Handles 404 as "not configured" (not a global error)

## Patterns

All components follow these conventions:

- API calls through `api` instance from `services/api.js`
- Error messages from `getApiError(error, fallback)` helper
- i18n text via `i18nStore.t(key)` imported from `stores/i18n.js`
- Props for parent-view integration (e.g., `mailbox` prop on MailboxConfigPanel)
- Events emitted (`updated`) for parent coordination
