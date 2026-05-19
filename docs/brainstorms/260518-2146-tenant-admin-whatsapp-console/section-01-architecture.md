# Architecture - Tenant Admin WhatsApp Console

## Message Flow

```
WhatsApp Tenant Admin -> Evolution API (trigger: "/menu")
  -> n8n Webhook (/webhook/trackpal-whatsapp-bot)
  -> Parse Input (Code node - normalizes phone, message, instance)
  -> Config (Set node - injects backend URL, API key)
  -> POST /api/v1/integrations/n8n/console

  Backend: integrations.py
  +-- 1. Normalize phone
  +-- 2. identify_by_phone(db, phone)
  |   +-- None -> "No tienes acceso"
  |   +-- role=master -> WhatsAppMasterConsoleFacade.process_message()
  |   +-- role=tenant -> WhatsAppTenantConsoleFacade.process_message()
  |   +-- role=client -> "Consola solo para administradores"
  +-- 3. Return reply text -> n8n -> Evolution API sendText
```

## Key Design Decision: Single Endpoint

Both Master and Tenant Admin use the SAME endpoint (`POST /api/v1/integrations/n8n/console`)
and the SAME n8n workflow. The differentiation happens inside the backend:

```python
identity = await auth_service.identify_by_phone(db, phone)
if identity and identity["role"] == "master":
    return await _handle_master_console(request, db, identity)
elif identity and identity["role"] == "tenant":
    return await _handle_tenant_console(request, db, identity)
```

This avoids:
- A new n8n workflow
- A new Evolution API trigger
- A new backend endpoint
- Changes to existing Master Console code

## WhatsAppTenantConsoleFacade

Unlike `WhatsAppMasterConsoleFacade`, this facade:

- Has NO login flow (auto-auth by phone)
- Has NO lockout check
- Has NO WhatsAppAuthSessionService
- Uses `session:admin:{phone}` as Redis key prefix
- Validates tenant exists AND is active before proceeding
- "0" at main menu -> clears conversation session + returns goodbye
- "0" inside flow -> handled by service (cancel current operation)

## Session Management

| Aspect | Master Console | Tenant Admin Console |
|--------|----------------|----------------------|
| Auth session | wa:auth:{phone} (Redis) | None (auto-auth) |
| Conversation session | session:{phone} (Redis) | session:admin:{phone} (Redis) |
| Login flow | Username + password | None |
| Lockout | 5 fails -> 5 min lock | None |
| Session TTL | 15 min (both) | 15 min (conversation only) |
| "0" -> Logout | Clears auth + conversation + Evolution chat | Clears conversation only |

## No-Go Areas (Explicit Scope Exclusions)

- Creation of services/plans from WhatsApp
- Price editing in catalog
- Evolution API management from Tenant Console
- Dashboard/statistics
- Web dashboard changes
- Changes to n8n workflow or Evolution API configuration
