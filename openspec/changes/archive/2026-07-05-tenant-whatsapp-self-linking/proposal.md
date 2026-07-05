# Proposal: Tenant WhatsApp Self-Linking

## Problem Statement

When a new tenant is created, `TenantService.create_tenant()` calls `EvolutionClient.create_instance()` which creates an Evolution Go instance. However, the WhatsApp connection is **not** completed — the instance remains in `connected: false, loggedIn: false` state. The **master** must manually relay a QR code or pairing code to the tenant via WhatsApp. This creates:

1. **Operational bottleneck**: Every new tenant requires master intervention to complete WhatsApp linking, blocking on master availability.
2. **Coordination overhead**: Master must share QR/pairing code out-of-band (WhatsApp message, email, etc.), which is slow and error-prone.
3. **No tenant autonomy**: Tenants cannot disconnect or reconnect their own WhatsApp instance — any change requires master support.
4. **No visibility**: Tenants have no way to see their WhatsApp connection status from the admin panel.

## User Stories

### Primary: Tenant connects WhatsApp
> As a tenant admin, I want to link my WhatsApp number to my instance from the admin panel, so I can start using WhatsApp services without waiting for the master.

### Primary: Tenant checks connection status
> As a tenant admin, I want to see whether my WhatsApp is connected or disconnected in Settings, so I know my service status at a glance.

### Secondary: Tenant disconnects WhatsApp
> As a tenant admin, I want to temporarily unlink my WhatsApp from my instance, so I can re-link to a different number or troubleshoot connectivity.

### Secondary: Tenant reconnects after disconnect
> As a tenant admin, I want to re-link my WhatsApp after a temporary disconnect, so I can resume services without master intervention.

## Scope

### In Scope (v1)

- **Settings > WhatsApp section** visible only for Pro tenants
- **Status display**: Phone number, connection state (Connected / Disconnected / Connecting)
- **Pairing Code flow**: Auto-fills phone from `tenant.whatsapp_phone`, displays 8-digit code with instructions
- **QR Code flow**: Displays QR code image with instructions and auto-refresh on expiry
- **Connection polling**: Polls `/instance/status` every 5s after pairing attempt, with timeout (60s)
- **Post-conexión feedback**: Toast notification "¡WhatsApp vinculado exitosamente!"
- **Disconnect**: Temporary unlink via `POST /instance/logout` (instance stays, tenant can re-link)
- **Re-vinculación guard**: Reject with error if instance already connected
- **Block if no phone**: If tenant has no `whatsapp_phone`, section shows message "Configure su número de teléfono primero"
- **Full i18n**: All UI text in ES/EN catalogs

### Non-Goals (v1)

- **Passkey/WebAuthn ceremony** (complex, rare — documented as known limitation)
- **WhatsApp console linking** (user chose frontend web only)
- **Automatic reconnection** on disconnect
- **Master-initiated linking for tenant** (existing flow remains as fallback)
- **Multi-device support** (out of scope for v1)
- **Webhook re-registration** after re-link (existing webhook persists)

## Business Rules

| # | Rule | Rationale |
|---|------|-----------|
| BR1 | Section visible **only** for `plan === "pro"` tenants | Pro-only feature, consistent with other Pro-gated settings |
| BR2 | Phone is auto-filled from `tenant.whatsapp_phone` — **no manual input** | Phone always matches the instance; prevents mismatch |
| BR3 | If `whatsapp_phone` is null, section is blocked with message | Cannot pair without a phone number |
| BR4 | Reject pairing if instance already `connected: true, loggedIn: true` | Prevents duplicate connections; existing master flow remains |
| BR5 | Disconnect calls `POST /instance/logout` — instance is **not** deleted | Temporary unlink only; tenant can re-link later |
| BR6 | After successful connection, show toast: "¡WhatsApp vinculado exitosamente!" | Confirms success to user |
| BR7 | QR code auto-refreshes on expiry (~40s window) | QR codes expire; polling + refresh needed |
| BR8 | Connection polling timeout: 60 seconds | Prevent indefinite loading state |
| BR9 | Error handling: Evolution API downtime → "Service unavailable" message | Graceful degradation |
| BR10 | Master support context: section visible regardless of tenant plan | Master support bypasses Pro gate |

## Acceptance Criteria

### Backend

| AC | Criterion |
|----|-----------|
| BE1 | `GET /api/v1/tenant/whatsapp-link/status` returns `{ connected: bool, phone: str | null, instance_name: str }` |
| BE2 | `POST /api/v1/tenant/whatsapp-link/pair` accepts `{}` (phone from tenant), returns `{ code: str }` |
| BE3 | `GET /api/v1/tenant/whatsapp-link/qr` returns `{ qrcode: str }` (base64 PNG) |
| BE4 | `POST /api/v1/tenant/whatsapp-link/disconnect` calls Evolution `POST /instance/logout` |
| BE5 | All endpoints require JWT + active tenant context (tenant or master) |
| BE6 | All endpoints validate: tenant active, `evolution_instance_name` set, `evolution_instance_token` set |
| BE7 | Pair/QR endpoints reject with 409 if instance already connected |
| BE8 | Pair/QR endpoints reject with 400 if `whatsapp_phone` is null |
| BE9 | New `EvolutionClient` methods: `get_instance_status`, `get_qr_code`, `pair_instance`, `logout_instance` using instance token auth |
| BE10 | All error messages use `UserFacingError` codes with i18n keys |
| BE11 | No database schema changes required |

### Frontend

| AC | Criterion |
|----|-----------|
| FE1 | Settings section "WhatsApp" appears only for Pro tenants (or Master support context) |
| FE2 | Section shows phone number, connection status badge, and action button |
| FE3 | Pairing Code tab: shows 8-digit code with instructions (Spanish + English) |
| FE4 | QR Code tab: shows QR image with instructions and auto-refresh timer |
| FE5 | Status polling starts after initiating pair/QR, polls every 5s |
| FE6 | Polling stops on success (connected) or timeout (60s) |
| FE7 | Success triggers Sonner toast: "¡WhatsApp vinculado exitosamente!" |
| FE8 | Disconnect button calls `POST /api/v1/tenant/whatsapp-link/disconnect` |
| FE9 | If no `whatsapp_phone`, section shows block message instead of pairing UI |
| FE10 | All text uses `t()` with i18n keys — no hardcoded strings |
| FE11 | Error states display translated error messages |

## Affected Areas

### Backend

| Area | Change Type | Files |
|------|-------------|-------|
| EvolutionClient | New methods | `backend/app/services/evolution_client/client.py` |
| WhatsApp Link API | New module | `backend/app/api/v1/endpoints/whatsapp_link.py` |
| Router registration | Add new router | `backend/app/api/v1/router.py` |
| i18n catalogs | New error keys | `backend/app/core/i18n/_catalog_en.py`, `_catalog_es.py` |
| Tests | New test files | `backend/tests/test_whatsapp_link_*.py` |

### Frontend

| Area | Change Type | Files |
|------|-------------|-------|
| WhatsApp Link Section | New component | `frontend/src/features/admin/components/whatsapp-link-section.tsx` |
| Settings Page | Add section | `frontend/src/features/admin/components/settings-page.tsx` |
| API Service | New service file | `frontend/src/features/admin/services/whatsapp-link-api.ts` |
| i18n catalogs | New keys | Backend `frontend.*` keys served via `/i18n/catalog` |

### Database

**No changes.** Evolution Go tracks connection status externally. The tenant model already has all required fields (`evolution_instance_name`, `evolution_instance_token`, `whatsapp_phone`).

## Implementation Plan

### Phase 1: Backend API

1. Add `get_instance_status`, `get_qr_code`, `pair_instance`, `logout_instance` to `EvolutionClient`
2. Create `whatsapp_link.py` endpoint module with status, pair, qr, disconnect endpoints
3. Register router in `backend/app/api/v1/router.py`
4. Add i18n error keys to both catalogs
5. Write backend tests

### Phase 2: Frontend Integration

1. Create `whatsapp-link-api.ts` service with typed API functions
2. Create `whatsapp-link-section.tsx` component with:
   - Status display (phone, badge)
   - Pairing Code tab
   - QR Code tab
   - Connection polling logic
   - Toast notification on success
3. Integrate into `settings-page.tsx` (Pro-only section)
4. Add i18n keys for all UI text

### Phase 3: Polish & Edge Cases

1. Error handling for Evolution API downtime
2. QR code auto-refresh on expiry
3. Disconnect flow with confirmation
4. Mobile responsiveness
5. Accessibility (ARIA labels, keyboard navigation)

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Evolution API downtime | Pairing fails | Graceful error handling; show "Service unavailable" with retry option |
| QR code expiration (~40s) | User misses window | Auto-refresh QR on expiry; show countdown timer |
| Passkey requirement (some accounts) | Pairing blocked | v1 ignores passkey flow; document as known limitation |
| Token decryption failure | Cannot authenticate with Evolution | Return clear error, suggest contacting support |
| Race condition: master connects while tenant tries | Duplicate connection | Status check before pairing; reject with clear message |
| Re-link after disconnect loses webhook | Messages stop flowing | Existing webhook persists (not re-registered on re-link) |

## Rollback Plan

- **Backend**: Remove `whatsapp_link.py` router and EvolutionClient methods
- **Frontend**: Remove section from settings page, delete component and API service
- **No database rollback needed**: No schema changes in v1
- **Zero risk to existing functionality**: Feature is purely additive; master-initiated linking remains as fallback

## Success Criteria

| Metric | Target |
|--------|--------|
| Tenant self-linking success rate | > 90% of attempts result in connected state |
| Master intervention for linking | Reduced by > 80% for Pro tenants |
| Average time to connect | < 2 minutes (from opening Settings to connected) |
| Error rate | < 5% of attempts fail (excluding user cancellation) |
| User satisfaction | Positive feedback on reduced coordination overhead |

## Open Questions

1. **Webhook re-registration**: After disconnect + re-link, does the existing webhook persist? (Assumed: yes, based on Evolution Go behavior)
2. **Multi-device**: Should v1 support WhatsApp multi-device linking? (Assumed: no, out of scope)
3. **Connection history**: Should we log link/unlink events for audit? (Assumed: no, not in v1)
