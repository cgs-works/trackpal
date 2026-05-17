# Product Goals & Use Cases

## Overview

Trackpal is a multi-tenant platform that enables a Master operator to manage WhatsApp-based service delivery. The Master creates and manages tenants (service recipients), each with their own Evolution API WhatsApp instance.

## Core Use Cases

### Master Console (WhatsApp)

The Master interacts with the system via a WhatsApp chatbot to:
1. **View tenants** — List all tenants with active/inactive counts and status
2. **Create tenants** — Step-by-step form collecting name, email, phone, username, Evolution instance name, and password
3. **Edit tenants** — Update tenant fields (name, email, phone, Evolution instance)
4. **Deactivate tenants** — Disable tenant login and identification, revoke active sessions
5. **Reactivate tenants** — Restore deactivated tenants
6. **Delete tenants** — Permanently remove inactive tenants plus their Evolution API instance

### Web Dashboard

- **Master Dashboard**: Full tenant management UI (CRUD, activate/deactivate, delete) with summary cards and modal forms — accessible at `/master/dashboard`
- **Tenant Dashboard**: Self-service profile management and password change — accessible at `/admin/dashboard`

### REST API

Programmatic tenant management for the frontend SPA:
- JWT-based authentication with access/refresh token rotation
- Role-based authorization (master vs tenant)
- Full tenant CRUD with Evolution instance lifecycle

## User Roles

| Role | Capabilities |
|------|-------------|
| Master | Full access via WhatsApp Console + REST API. Manages all tenants. |
| Tenant | Limited REST API access (own profile only). Cannot access WhatsApp Console. |

## Non-Goals

- Self-registration: Tenants are created only by the Master
- WhatsApp message routing for tenants: Only the Master console uses WhatsApp
- Multi-language: All user-facing text is Spanish
