# Product Goals & Use Cases

## Overview

Trackpal is a multi-tenant platform that enables a Master operator to manage WhatsApp-based service delivery. The Master creates and manages tenants (service recipients), each with their own Evolution API WhatsApp instance. Tenants manage clients, catalog, profiles, and subscriptions through REST and WhatsApp.

## Core Use Cases

### Master Console (WhatsApp)

The Master interacts with the system via a WhatsApp chatbot to:
1. **View tenants** — List all tenants with active/inactive counts and status
2. **Create tenants** — Step-by-step form collecting name, email, phone, username, Evolution instance name, and password
3. **Edit tenants** — Update tenant fields (name, email, phone, Evolution instance)
4. **Deactivate tenants** — Disable tenant login and identification, revoke active sessions
5. **Reactivate tenants** — Restore deactivated tenants
6. **Delete tenants** — Permanently remove inactive tenants plus their Evolution API instance

### Tenant Console (WhatsApp)

Tenant admins interact with the system via a WhatsApp chatbot to:
1. **Manage clients** — List, create, edit, deactivate, reactivate, delete their own clients
2. **Manage catalog** — View and edit service and plan names
3. **Manage profile** — View and edit own profile data, change password
4. **Manage subscriptions** — List, create, edit, cancel, renew, reactivate, reveal credentials

### Web Dashboard

- **Master Dashboard**: Full tenant management UI (CRUD, activate/deactivate, delete) with summary cards and modal forms — accessible at `/master/dashboard`
- **Tenant Dashboard**: Self-service profile management, password change, and subscriptions page — accessible at `/admin/dashboard` and `/admin/subscriptions`
- **Client Dashboard**: Readonly profile view and password change for end-customers — accessible at `/client/dashboard`

### REST API

Programmatic tenant management for the frontend SPA:
- JWT-based authentication with access/refresh token rotation
- Role-based authorization (master vs tenant vs client)
- Full tenant CRUD with Evolution instance lifecycle
- Catalog management (services, plans), Client management, and Subscriptions

## User Roles

| Role | Capabilities |
|------|-------------|
| Master | Full access via WhatsApp Console + REST API. Manages all tenants and system config. |
| Tenant | Manages own profile, catalog, clients, and subscriptions via REST API and WhatsApp Tenant Console. |
| Client | Read-only access to their own profile and password management. Tenant-prefixed login. |

## Non-Goals

- Self-registration: Tenants are created only by the Master
- Client WhatsApp access: Clients do not get WhatsApp console access
- Multi-language: All user-facing text is Spanish
