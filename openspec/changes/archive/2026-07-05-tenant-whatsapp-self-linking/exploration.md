# Exploration: Tenant WhatsApp Self-Linking

## Status
completed

## Executive Summary

The feature enables tenant admins to self-link their WhatsApp number to their Evolution Go instance from the frontend admin panel, eliminating the current manual bottleneck where the master must send a QR code or pairing code via WhatsApp.

**Current state**: When a tenant is created, `TenantService.create_tenant()` calls `EvolutionClient.create_instance()` which creates the instance in Evolution Go. However, the WhatsApp connection is NOT completed — the instance remains in `connected: false, loggedIn: false` state. The master must manually relay a QR code or pairing code to the tenant.

**Target state**: The tenant opens Settings > WhatsApp in the admin panel, sees their connection status, and can initiate pairing (code or QR) directly. After entering the pairing code in WhatsApp, polling confirms the connection automatically.

## Surface Area Mapping

### Backend

#### EvolutionClient — New Methods Needed
File: `backend/app/services/evolution_client/client.py`

Current methods: `create_instance`, `register_webhook`, `delete_instance`

New methods to add:
1. `get_instance_status(instance_token: str) -> dict` — Calls `GET /instance/status` with instance token header. Returns `{connected, loggedIn, name, myJid}`.
2. `get_qr_code(instance_token: str) -> dict` — Calls `GET /instance/qr` with instance token header. Returns `{qrcode, code}` (base64 PNG).
3. `pair_instance(instance_token: str, phone: str) -> dict` — Calls `POST /instance/pair` with instance token header and `{phone}` body. Returns `{code}` (8-digit pairing code).
4. `connect_instance(instance_token: str, webhook_url: str) -> dict` — Calls `POST /instance/connect` with instance token header. Initiates QR-based connection flow.

**Auth pattern**: These endpoints use the **instance token** (stored encrypted in `tenants.evolution_instance_token`), NOT the global `EVOLUTION_API_KEY`. The token must be decrypted at runtime.

#### New API Endpoints — Tenant-Scoped
File: `backend/app/api/v1/endpoints/` (new module or extend tenants)

New endpoints under `/api/v1/tenant/whatsapp-link/` (JWT + active tenant context):

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/api/v1/tenant/whatsapp-link/status` | Get WhatsApp connection status for current tenant's instance |
| `POST` | `/api/v1/tenant/whatsapp-link/pair` | Initiate pairing via phone number, returns 8-digit code |
| `GET` | `/api/v1/tenant/whatsapp-link/qr` | Get QR code image (base64 PNG) for scanning |

**Validation rules**:
- Tenant must be active (`is_active=True`)
- Tenant must have `evolution_instance_name` set
- Tenant must have `evolution_instance_token` set (encrypted)
- For `/pair`: reject if instance already connected (`connected: true, loggedIn: true`)
- For `/qr`: reject if instance already connected

#### TenantService — New Methods
File: `backend/app/services/tenant_service/`

New methods:
1. `get_whatsapp_status(db, tenant_id) -> dict` — Decrypt token, call EvolutionClient, return status
2. `get_whatsapp_qr(db, tenant_id) -> dict` — Decrypt token, call EvolutionClient, return QR
3. `pair_whatsapp(db, tenant_id, phone) -> dict` — Validate not connected, decrypt token, call EvolutionClient pair, return code

### Frontend

#### New Section in SettingsPage
File: `frontend/src/features/admin/components/whatsapp-link-section.tsx`

New component `WhatsappLinkSection` that:
1. Shows current connection status (Connected / Disconnected / Connecting)
2. If disconnected: shows "Vincular WhatsApp" button
3. On click: opens dialog/tabs with two options:
   - **Pairing Code tab**: Input phone number → shows 8-digit code with instructions
   - **QR Code tab**: Shows QR code image with instructions
4. Polls status every 5 seconds while connecting
5. Shows success/error states

#### SettingsPage Integration
File: `frontend/src/features/admin/components/settings-page.tsx`

Add new section to `SectionId` type and `buildSections()`:
```
{ id: "whatsapp-link", title: "WhatsApp", description: "Vincular número de WhatsApp", icon: MessageSquare }
```

#### New API Functions
File: `frontend/src/features/admin/services/whatsapp-link-api.ts`

```typescript
export async function getWhatsAppStatus(): Promise<WhatsAppStatus>
export async function pairWhatsApp(phone: string): Promise<{ code: string }>
export async function getWhatsAppQR(): Promise<{ qrcode: string; code: string }>
```

### Database
**No schema changes needed.** Evolution Go tracks connection status externally. The tenant model already has all required fields:
- `evolution_instance_name` — used to identify the instance
- `evolution_instance_token` — encrypted token used for instance-scoped API calls
- `whatsapp_phone` — tenant's phone number (may be used for pairing)

### Tests

#### Backend Tests
- `test_whatsapp_link_status.py` — Test status endpoint (connected/disconnected/error states)
- `test_whatsapp_link_pair.py` — Test pairing flow (success, already connected, missing instance)
- `test_whatsapp_link_qr.py` — Test QR code retrieval
- EvolutionClient unit tests for new methods (mock httpx)
- Integration tests with mocked Evolution API

#### Frontend Tests
- `whatsapp-link-section.spec.tsx` — Test component rendering, status display, pairing flow
- API function tests with mocked axios

## Risks

| Risk | Mitigation |
|------|------------|
| Evolution API downtime | Graceful error handling, show "Service unavailable" message |
| QR code expiration (~40s) | Auto-refresh QR on expiry, show countdown timer |
| Passkey requirement (some accounts) | v1 ignores passkey flow; document as known limitation. Future: support passkey ceremony via browser extension |
| Token decryption failure | Return clear error, suggest re-creating tenant |
| Race condition: master connects while tenant tries | Status check before pairing, reject with clear message |

## Dependencies

- Evolution Go must be running and accessible
- `EVOLUTION_API_URL` and `EVOLUTION_API_KEY` must be configured
- `DATA_ENCRYPTION_KEY` must be set for token decryption
- Frontend i18n keys need to be added for the new section

## Non-Goals (v1)
- Passkey/WebAuthn ceremony support (complex, rare)
- WhatsApp console-based linking (user chose frontend only)
- Automatic reconnection on disconnect
- Master-initiated linking for tenant (existing flow remains as fallback)

## Artifacts
- This exploration document

## Next Recommended
`sdd-proposal` — Create a formal proposal/PRD with problem statement, user stories, and acceptance criteria.
