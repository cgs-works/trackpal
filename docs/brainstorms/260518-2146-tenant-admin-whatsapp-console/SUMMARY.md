# Brainstorm: Tenant Admin WhatsApp Console

## Metadata
- Date: 2026-05-18
- Status: Draft
- Plan ref: `.plannotator/plans/plan-tenant-admin-whatsapp-con-2026-05-19-approved.md`

## Problem Statement

Tenant Admins need to manage their clients, catalog (services/plans), and profile
from WhatsApp, mirroring the Master Console experience but scoped to their own tenant data.

The existing approved plan has architectural gaps that need resolution before implementation.

## Key Decisions

### 1. Routing Strategy
**Decision**: Same trigger `/menu` for both Master and Tenant Admin.
**Rationale**: Evolution API forwards ALL `/menu` messages to the same n8n webhook.
The backend differentiates by phone number identity (role detection via `identify_by_phone()`).
**Files affected**: `integrations.py` only (routing logic in `POST /n8n/console`).
No changes to Evolution API or n8n workflow.

### 2. Authentication Model
**Decision**: Auto-auth by phone number. No login flow, no lockout, no `WhatsAppAuthSession`.
**Rationale**: Tenant Admin is identified automatically via `AuthService.identify_by_phone()`.
"Cerrar sesión" clears the conversation session (`session:admin:{phone}`) only.
Session TTL: 15 minutes (same as Master conversation sessions).

### 3. Service Architecture
**Decision**: New `WhatsAppTenantConsoleService` (separate from Master).
**Rationale**: Flows are sufficiently different (clients vs tenants, catalog read-only+edit vs CRUD).
Avoids risk of breaking Master Console during refactors.
New protocol classes: `ClientServiceProtocol`, `CatalogServiceProtocol`.

### 4. Catalog Scope
**Decision**: Read + edit name and description only. No creation, no price editing.
**Rationale**: Creation is too complex for WhatsApp input. Price requires numeric validation unsuitable for chat.

### 5. Redis Session Keys
**Decision**: `session:admin:{phone}` prefix via `WhatsAppSessionService` (no service changes needed).
**Rationale**: Existing service accepts any phone/identifier string.

## Architecture

```
Evolution API (trigger: "/menu")
  -> n8n Workflow existente (trackpal-whatsapp-bot)
  -> POST /api/v1/integrations/n8n/console

  integrations.py (routing unificado por rol)
  +-- role == "master" -> WhatsAppMasterConsoleFacade (sin cambios)
  +-- role == "tenant" -> WhatsAppTenantConsoleFacade (nuevo)
        +-- WhatsAppSessionService (session:admin:{phone})
        +-- WhatsAppTenantConsoleService (nuevo)
        |   +-- Flujo Clientes -> ClientService + ClientServiceProtocol
        |   +-- Flujo Catalogo -> CatalogService + CatalogServiceProtocol
        |   +-- Flujo Perfil -> ProfileService (directo)
        +-- Sin auth session / login flow / lockout
```

## Scenarios Covered

1. **Phone not found** -> "No tienes cuenta de administrador asociada a este numero."
2. **Tenant inactive** -> "Tu cuenta esta desactivada."
3. **Client role sends /menu** -> "Consola solo para administradores."
4. **Master sends /menu** -> Master Console (existing, unchanged)
5. **Tenant admin sends /menu** -> Tenant Admin Console
6. **Zero contextual handling** -> Cancel flow (inside flow) / Exit (main menu)
7. **Invalid input** -> Spanish error + reprompt
8. **Empty client list** -> "No tienes clientes" + suggestion to create
9. **Delete active client** -> Error, must deactivate first

## Gaps Resolved from Original Plan

| # | Gap in Original Plan | Resolution |
|---|----------------------|------------|
| 1 | Multiple webhooks in Evolution API | Not needed - single trigger /menu, routing by role in backend |
| 2 | Contradiction: auto-auth + "Cerrar sesion" | "Cerrar sesion" = clear conversation session only |
| 3 | How to resolve tenant_id | Helper from identify_by_phone() response |
| 4 | Missing adapter pattern | ClientServiceProtocol, CatalogServiceProtocol |
| 5 | Redis key collision | session:admin:{phone} prefix |
| 6 | What about client role sending /menu | Explicit rejection |
| 7 | Profile editable fields | full_name, email, phone, password. username read-only |
| 8 | Catalog editable fields exactly | Service: name, description. Plan: name, description only |

## Files Changed

| File | Change |
|------|--------|
| `backend/app/api/v1/endpoints/integrations.py` | Routing by role in POST /n8n/console |
| `backend/app/services/whatsapp_tenant_console_facade.py` | **New** - facade without auth |
| `backend/app/services/whatsapp_tenant_console_service.py` | **New** - full service |
| `backend/app/services/__init__.py` | Export new symbols |

**Not changed**: Evolution API, n8n workflow, WhatsAppSessionService, WhatsAppAuthSessionService,
any existing Master Console code.

## Testing

18 test scenarios across facade, flows, and edge cases.
Mocks: AuthService, ClientService, CatalogService, ProfileService, WhatsAppSessionService.
No Redis required in tests.
