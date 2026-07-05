# Design: Tenant WhatsApp Self-Linking

## Metadata

- Change: `tenant-whatsapp-self-linking`
- Phase: SDD design
- Skill resolution: `paths-injected`
- Inputs read:
  - `openspec/changes/tenant-whatsapp-self-linking/proposal.md`
  - `openspec/changes/tenant-whatsapp-self-linking/specs/whatsapp-link/spec.md`
  - `openspec/changes/tenant-whatsapp-self-linking/specs/whatsapp-link-ui/spec.md`
  - Relevant backend/frontend implementation files listed in this design
- Scope: TrackPal backend/frontend WhatsApp self-linking flow. No database schema changes.

## Goals

Enable a Pro tenant admin, or a master user in support context, to manage the tenant's existing Evolution Go WhatsApp instance from **Settings > WhatsApp**:

1. Read current connection status.
2. Request an 8-digit pairing code using the stored tenant phone.
3. Request and refresh a QR code.
4. Temporarily disconnect by logging out the Evolution instance without deleting it.

## Existing Code Findings

- `EvolutionClient` is a module singleton: `backend/app/services/evolution_client/client.py` exposes `evolution_client = EvolutionClient()`.
- Existing Evolution methods use global API-key auth through `self._headers`.
- Tenant instance tokens are stored encrypted in `Tenant.evolution_instance_token`; runtime calls must use `decrypt_value()`.
- `Tenant` already contains all required fields: `evolution_instance_name`, `evolution_instance_token`, `whatsapp_phone`, `plan`, `is_active`.
- `backend/app/api/v1/endpoints/tenants.py` is master-only and must not be extended for tenant self-service.
- Active tenant context already exists in `backend/app/api/dependencies.py` through `ActiveTenantId`, `CurrentUser`, `TenantPlanDep`, and `ProTenantId`.
- Actual backend i18n files are `catalogs_en_general.py`, `catalogs_es_general.py`, `catalogs_en_frontend.py`, and `catalogs_es_frontend.py` under `backend/app/core/i18n/`.
- Frontend is Vite/React, shadcn `base-nova`, alias `@`, icon library `lucide`, and `rsc: false`; no `"use client"` directive is required.
- `frontend/src/components/ui/tabs.tsx` is not currently present; add it via shadcn or implement an accessible fallback if CLI use is deferred.

## Architecture Decisions

### AD1: Add a tenant-scoped API router

Create `backend/app/api/v1/endpoints/whatsapp_link.py` with prefix `/tenant/whatsapp-link`. Do not extend `tenants.py`, because tenant self-linking needs active tenant context and tenant/master authorization rather than master-only CRUD authorization.

### AD2: Add a focused service layer

Create `backend/app/services/whatsapp_link_service.py` so endpoints remain thin. The service owns tenant lookup, active/config validation, token decryption, already-connected checks, and Evolution orchestration.

### AD3: Use instance-token Evolution auth only for lifecycle methods

The four new `EvolutionClient` methods must never use `self._headers` because it contains the global API key. Add a separate helper:

```python
def _instance_headers(self, instance_token: str) -> dict[str, str]:
    return {"Content-Type": "application/json", "apikey": instance_token}
```

### AD4: Default Evolution routes are token-scoped; route mapping stays isolated

The proposal/spec name token-scoped instance endpoints such as `POST /instance/logout`. Use route constants inside `EvolutionClient`:

| Client method | Default Evolution route | Auth |
|---|---|---|
| `get_instance_status` | `GET /instance/status` | `apikey: INSTANCE_TOKEN` |
| `get_qr_code` | `GET /instance/qr` | `apikey: INSTANCE_TOKEN` |
| `pair_instance` | `POST /instance/pair` | `apikey: INSTANCE_TOKEN` |
| `logout_instance` | `POST /instance/logout` | `apikey: INSTANCE_TOKEN` |

Each method still accepts `instance_name` per spec and normalizes it with `_instance_name()` for logging, diagnostics, and compatibility. If the deployed Evolution Go server requires path-parameter variants such as `/instance/status/{instance_name}`, only these route constants/helpers change; endpoint and service contracts remain stable.

### AD5: Disconnect is logout-only and idempotent from the product perspective

Disconnect calls Evolution logout. It must not call `delete_instance`, clear tenant fields, or re-register webhooks. If Evolution reports the instance is already logged out, the backend should still return 200 when feasible.

### AD6: Localized backend errors + frontend i18n UI

Backend errors use `UserFacingError` codes translated with `translate_error(locale, exc)` into `HTTPException.detail`. Frontend displays backend `detail` strings when present and uses `frontend.whatsapp_link.*` keys for labels, instructions, buttons, fallbacks, and toasts.

### AD7: Polling is a dedicated frontend hook

Create `useWhatsAppLinkPolling()` to encapsulate 5s polling, 60s timeout, unmount cleanup, success callback, timeout callback, and error surfacing.

## Backend Design

### Router and Endpoints

File: `backend/app/api/v1/endpoints/whatsapp_link.py`

```python
router = APIRouter(prefix="/tenant/whatsapp-link", tags=["tenant-whatsapp-link"])
```

Public contract:

| Method | Path | Response | Notes |
|---|---|---|---|
| `GET` | `/api/v1/tenant/whatsapp-link/status` | `{ connected: bool, phone: str | null, instance_name: str }` | `connected` is true only when Evolution reports both `connected` and `loggedIn` true. |
| `POST` | `/api/v1/tenant/whatsapp-link/pair` | `{ code: str }` | Request body is `{}` only; phone comes from `tenant.whatsapp_phone`. |
| `GET` | `/api/v1/tenant/whatsapp-link/qr` | `{ qrcode: str }` | Base64 PNG string; frontend normalizes to a data URL. |
| `POST` | `/api/v1/tenant/whatsapp-link/disconnect` | `{ connected: false }` | Logout only; preserves instance and tenant fields. |

Endpoint signatures:

```python
@router.get("/status", response_model=WhatsAppLinkStatusResponse)
async def get_status(db: DbDep, tenant_id: ActiveTenantId, current_user: CurrentUser, tenant_plan: TenantPlanDep): ...

@router.post("/pair", response_model=WhatsAppPairResponse)
async def pair(payload: WhatsAppPairRequest, db: DbDep, tenant_id: ActiveTenantId, current_user: CurrentUser, tenant_plan: TenantPlanDep): ...

@router.get("/qr", response_model=WhatsAppQrResponse)
async def get_qr(db: DbDep, tenant_id: ActiveTenantId, current_user: CurrentUser, tenant_plan: TenantPlanDep): ...

@router.post("/disconnect", response_model=WhatsAppDisconnectResponse)
async def disconnect(db: DbDep, tenant_id: ActiveTenantId, current_user: CurrentUser, tenant_plan: TenantPlanDep): ...
```

Authorization flow:

1. `CurrentUser` validates JWT.
2. `ActiveTenantId` resolves active tenant context and blocks clients.
3. Explicitly require `current_user.role in ("tenant", "master")`.
4. Enforce Pro gate only for tenant users: if `current_user.role == "tenant" and tenant_plan != TENANT_PLAN_PRO`, return 404 (`Not found`) to match existing Pro feature concealment.
5. Master support context bypasses plan gate per BR10.
6. Service verifies tenant exists and is active before calling Evolution.

### Pydantic Schemas

File: `backend/app/schemas/whatsapp_link.py`

```python
from pydantic import BaseModel, ConfigDict, Field

class WhatsAppLinkStatusResponse(BaseModel):
    connected: bool
    phone: str | None
    instance_name: str

class WhatsAppPairRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

class WhatsAppPairResponse(BaseModel):
    code: str = Field(min_length=1)

class WhatsAppQrResponse(BaseModel):
    qrcode: str = Field(min_length=1)

class WhatsAppDisconnectResponse(BaseModel):
    connected: bool = False
```

### WhatsApp Link Service

File: `backend/app/services/whatsapp_link_service.py`

```python
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

class WhatsAppLinkService:
    async def get_status(self, db: AsyncSession, tenant_id: UUID) -> WhatsAppLinkStatusResponse: ...
    async def request_pairing_code(self, db: AsyncSession, tenant_id: UUID) -> WhatsAppPairResponse: ...
    async def get_qr_code(self, db: AsyncSession, tenant_id: UUID) -> WhatsAppQrResponse: ...
    async def disconnect(self, db: AsyncSession, tenant_id: UUID) -> WhatsAppDisconnectResponse: ...
```

Internal helpers:

```python
async def _get_configured_tenant(db: AsyncSession, tenant_id: UUID) -> Tenant:
    """Validate tenant exists, is active, and has instance name/token."""

async def _get_instance_credentials(db: AsyncSession, tenant_id: UUID) -> tuple[Tenant, str, str]:
    """Return tenant, normalized instance_name, decrypted instance_token."""

async def _ensure_not_connected(instance_name: str, instance_token: str) -> None:
    """Raise UserFacingError('whatsapp_link.already_connected') when both flags are true."""
```

Validation and error mapping:

| Condition | Service error code | HTTP status |
|---|---|---:|
| Missing tenant / inactive tenant | `tenant_not_found` or endpoint 403/404 depending dependency path | 403/404 |
| Missing `evolution_instance_name` or `evolution_instance_token` | `whatsapp_link.instance_not_configured` | 400 |
| Token decrypt failure / decrypted token empty | `whatsapp_link.invalid_instance_token` | 502 |
| Missing `whatsapp_phone` for pair/QR | `whatsapp_link.phone_required` | 400 |
| Already connected before pair/QR | `whatsapp_link.already_connected` | 409 |
| Evolution timeout/network/5xx | `whatsapp_link.service_unavailable` | 503 |
| Evolution 401/403 | `whatsapp_link.invalid_instance_token` | 502 |
| Unclassified Evolution 4xx | `whatsapp_link.request_failed` | 502 |

Endpoint mapping constant:

```python
ERROR_STATUS = {
    "whatsapp_link.instance_not_configured": status.HTTP_400_BAD_REQUEST,
    "whatsapp_link.phone_required": status.HTTP_400_BAD_REQUEST,
    "whatsapp_link.already_connected": status.HTTP_409_CONFLICT,
    "whatsapp_link.service_unavailable": status.HTTP_503_SERVICE_UNAVAILABLE,
    "whatsapp_link.invalid_instance_token": status.HTTP_502_BAD_GATEWAY,
    "whatsapp_link.request_failed": status.HTTP_502_BAD_GATEWAY,
}
```

### EvolutionClient Methods

Modify `backend/app/services/evolution_client/client.py`.

New exception:

```python
class EvolutionClientError(RuntimeError):
    def __init__(self, code: str, *, status_code: int | None = None) -> None:
        self.code = code
        self.status_code = status_code
        super().__init__(code)
```

New method signatures:

```python
async def get_instance_status(self, instance_name: str, instance_token: str) -> dict[str, Any]: ...
async def get_qr_code(self, instance_name: str, instance_token: str) -> dict[str, Any]: ...
async def pair_instance(self, instance_name: str, instance_token: str, phone: str) -> dict[str, Any]: ...
async def logout_instance(self, instance_name: str, instance_token: str) -> None: ...
```

Recommended internal request helper:

```python
async def _send_instance_request(
    self,
    method: str,
    path: str,
    *,
    instance_name: str,
    instance_token: str,
    json: dict[str, Any] | None = None,
) -> Any:
    if not self.base_url:
        raise EvolutionClientError("service_unavailable")
    normalized_instance_name = self._instance_name(instance_name)
    async with httpx.AsyncClient(base_url=self.base_url, timeout=30.0) as client:
        try:
            response = await client.request(
                method,
                path,
                json=json,
                headers=self._instance_headers(instance_token),
            )
            if response.status_code in {401, 403}:
                raise EvolutionClientError("invalid_instance_token", status_code=response.status_code)
            if response.status_code >= 500:
                raise EvolutionClientError("service_unavailable", status_code=response.status_code)
            response.raise_for_status()
        except httpx.RequestError as exc:
            logger.warning("Evolution instance request failed instance=%s path=%s", normalized_instance_name, path, exc_info=True)
            raise EvolutionClientError("service_unavailable") from exc
        except httpx.HTTPStatusError as exc:
            raise EvolutionClientError("request_failed", status_code=exc.response.status_code) from exc
    return self._response_data(response.json()) if response.content else None
```

Response normalization rules:

- Reuse `_response_data()` to unwrap `{ "data": ... }`.
- Status returns raw normalized dict; service computes `connected = data.get("connected") is True and data.get("loggedIn") is True`.
- Pair accepts response fields `code` or `pairingCode` and returns `{ "code": value }`.
- QR accepts `qrcode`, `qr`, or `base64` and returns `{ "qrcode": value }`.
- Log `instance_name` but never log `instance_token`.

### Backend Data Flow Diagrams

#### Status

```text
Settings UI
  -> GET /api/v1/tenant/whatsapp-link/status (JWT)
    -> FastAPI resolves active tenant context
    -> WhatsAppLinkService validates tenant + instance config
    -> decrypt_value(tenant.evolution_instance_token)
    -> EvolutionClient.get_instance_status(instance_name, token)
      -> GET /instance/status with apikey: INSTANCE_TOKEN
    <- Evolution { connected, loggedIn, ... }
    -> connected = connected && loggedIn
  <- { connected, phone: tenant.whatsapp_phone, instance_name }
```

#### Pairing Code

```text
User clicks Generate Code
  -> POST /api/v1/tenant/whatsapp-link/pair body {}
    -> validate tenant, Pro gate, instance config, phone present
    -> decrypt instance token
    -> get_instance_status(...)
    -> if connected && loggedIn: 409 already_connected
    -> pair_instance(instance_name, token, tenant.whatsapp_phone)
      -> POST /instance/pair with apikey: INSTANCE_TOKEN and { phone }
  <- { code }
Frontend displays code and starts status polling every 5s up to 60s
```

#### QR

```text
User opens QR tab / refreshes QR
  -> GET /api/v1/tenant/whatsapp-link/qr
    -> validate tenant, instance config, phone present
    -> decrypt instance token
    -> get_instance_status(...)
    -> if connected && loggedIn: 409 already_connected
    -> get_qr_code(instance_name, token)
      -> GET /instance/qr with apikey: INSTANCE_TOKEN
  <- { qrcode }
Frontend renders PNG, starts polling, refreshes QR near expiry while disconnected
```

#### Disconnect

```text
User confirms Disconnect
  -> POST /api/v1/tenant/whatsapp-link/disconnect
    -> validate tenant and instance config
    -> decrypt token
    -> logout_instance(instance_name, token)
      -> POST /instance/logout with apikey: INSTANCE_TOKEN
    -> no DB fields cleared; no instance delete
  <- { connected: false }
Frontend clears pairing state and shows disconnected UI
```

## Frontend Design

### API Service

File: `frontend/src/features/admin/services/whatsapp-link-api.ts`

```typescript
import api from "@/lib/api";

export interface WhatsAppLinkStatus {
  connected: boolean;
  phone: string | null;
  instance_name: string;
}

export interface PairingCodeResponse { code: string }
export interface QRCodeResponse { qrcode: string }
export interface DisconnectResponse { connected: false }

export async function getWhatsAppLinkStatus(): Promise<WhatsAppLinkStatus> {
  const { data } = await api.get<WhatsAppLinkStatus>("/tenant/whatsapp-link/status");
  return data;
}

export async function requestPairingCode(): Promise<PairingCodeResponse> {
  const { data } = await api.post<PairingCodeResponse>("/tenant/whatsapp-link/pair", {});
  return data;
}

export async function getQRCode(): Promise<QRCodeResponse> {
  const { data } = await api.get<QRCodeResponse>("/tenant/whatsapp-link/qr");
  return data;
}

export async function disconnectWhatsApp(): Promise<DisconnectResponse> {
  const { data } = await api.post<DisconnectResponse>("/tenant/whatsapp-link/disconnect");
  return data;
}
```

### Polling Hook

File: `frontend/src/features/admin/hooks/use-whatsapp-link-polling.ts`

```typescript
interface UseWhatsAppLinkPollingOptions {
  enabled: boolean;
  intervalMs?: number; // default 5000
  timeoutMs?: number;  // default 60000
  onStatus: (status: WhatsAppLinkStatus) => void;
  onConnected: (status: WhatsAppLinkStatus) => void;
  onTimeout: () => void;
  onError: (error: unknown) => void;
}

export function useWhatsAppLinkPolling(options: UseWhatsAppLinkPollingOptions): {
  isPolling: boolean;
  elapsedMs: number;
  stop: () => void;
}
```

Behavior:

- Poll immediately when `enabled` becomes true, then every 5s.
- Stop and call `onConnected` once when `status.connected === true`.
- Stop and call `onTimeout` after 60s.
- Clear timers on unmount or when disabled.
- For transient status errors, surface `onError` but continue until timeout unless implementation decides to stop on auth/permission responses.

### Settings Page Integration

Modify `frontend/src/features/admin/components/settings-page.tsx`:

- Import `MessageCircle` (or `MessageSquare`) from `lucide-react`.
- Import `WhatsappLinkSection`.
- Extend `SectionId` with `"whatsapp-link"`.
- Add section under existing `showProSettings` gate:

```typescript
...(showProSettings ? [{
  id: "whatsapp-link" as const,
  title: t("frontend.whatsapp_link.section_title"),
  description: t("frontend.whatsapp_link.section_description"),
  icon: MessageCircle,
}] : []),
```

- Add render switch case:

```tsx
case "whatsapp-link":
  return <WhatsappLinkSection />;
```

This reuses the current `showProSettings = !isStarterTenantAdmin || isMasterSupportContext` behavior for BR1 and BR10.

### Component Hierarchy

File: `frontend/src/features/admin/components/whatsapp-link-section.tsx`

```text
WhatsappLinkSection
├─ WhatsAppStatusSummary
│  ├─ phone row
│  ├─ instance row
│  └─ WhatsAppConnectionBadge
├─ Alert                         [load/error/service unavailable, retry]
├─ PhoneRequiredAlert            [status.phone === null]
├─ ConnectedActions              [status.connected]
│  └─ DisconnectConfirmDialog
└─ PairingTabs                   [phone exists and not connected]
   ├─ PairingCodeTab
   │  ├─ Generate code Button
   │  ├─ PairingCodeDisplay
   │  └─ Instructions list
   └─ QRCodeTab
      ├─ QR image card
      ├─ refresh countdown
      ├─ Refresh Button
      └─ Instructions list
```

Primary state:

```typescript
type Flow = "pairing-code" | "qr-code";
type BadgeState = "connected" | "disconnected" | "connecting";

const [status, setStatus] = useState<WhatsAppLinkStatus | null>(null);
const [activeFlow, setActiveFlow] = useState<Flow>("pairing-code");
const [pairingCode, setPairingCode] = useState<string | null>(null);
const [qrCode, setQrCode] = useState<string | null>(null);
const [qrExpiresAt, setQrExpiresAt] = useState<number | null>(null);
const [isInitialLoading, setIsInitialLoading] = useState(true);
const [isRequestingPair, setIsRequestingPair] = useState(false);
const [isRequestingQr, setIsRequestingQr] = useState(false);
const [isDisconnecting, setIsDisconnecting] = useState(false);
const [error, setError] = useState<string | null>(null);
const [timeoutError, setTimeoutError] = useState(false);
const [pollingEnabled, setPollingEnabled] = useState(false);
```

Derived UI:

```typescript
const connected = status?.connected === true;
const hasPhone = !!status?.phone;
const badgeState: BadgeState = pollingEnabled ? "connecting" : connected ? "connected" : "disconnected";
```

### QR Refresh

- When QR tab is active and QR is loaded, set `qrExpiresAt = Date.now() + 40_000`.
- Refresh automatically around 35s if still disconnected and polling is active.
- Provide a manual refresh button.
- Clear QR timer when connected, disconnected flow resets, or component unmounts.

```typescript
function getQrImageSrc(qrcode: string): string {
  return qrcode.startsWith("data:") ? qrcode : `data:image/png;base64,${qrcode}`;
}
```

### Error Extraction

```typescript
type ApiErrorDetail = string | Array<{ msg?: string }>;

function getApiErrorMessage(error: unknown, fallbackKey: string): string {
  const detail = (error as { response?: { data?: { detail?: ApiErrorDetail } } }).response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    return detail.map((item) => item.msg || t("frontend.whatsapp_link.error_unknown")).join("; ");
  }
  return t(fallbackKey);
}
```

### shadcn/UI Composition Notes

- Use existing `Card`, `Button`, `Alert`, `Badge`, `Skeleton`, `AlertDialog`, and `Sheet` patterns.
- Add `Tabs` via shadcn for Pairing Code / QR. Project uses base primitives, so follow the generated component API and use `render` where base-ui triggers require it.
- Use full `CardHeader` / `CardTitle` / `CardDescription` / `CardContent` composition for subcards.
- Use `Alert`, `AlertTitle`, `AlertDescription`, `AlertAction` for error/block states.
- Use `Badge` variants (`default`, `secondary`, `outline`) instead of raw status colors.
- Button loading states use a lucide spinner icon with `data-icon="inline-start"`, disabled button, and translated loading text.
- Use flex `gap-*`; avoid `space-x-*` / `space-y-*`.

## Frontend Data Flow Diagrams

### Initial Render

```text
SettingsPage builds sections
  -> showProSettings true for Pro tenant or master support context
  -> user selects WhatsApp
    -> WhatsappLinkSection mounts
      -> getWhatsAppLinkStatus()
      -> Skeleton while loading
      -> status.connected ? ConnectedActions : PairingTabs/PhoneRequiredAlert
```

### Pairing Code Success

```text
User clicks Generate Code
  -> requestPairingCode()
  <- { code }
  -> display code
  -> set pollingEnabled true
  -> polling hook calls status every 5s
  <- connected false ...
  <- connected true
  -> stop polling
  -> toast.success(t("frontend.whatsapp_link.success_linked"))
  -> render connected state and Disconnect button
```

### Polling Timeout

```text
Pair/QR flow starts
  -> status poll every 5s
  -> 60s elapsed without connected
  -> stop polling
  -> set timeoutError true
  -> Alert with t("frontend.whatsapp_link.error_timeout") and Retry button
```

## i18n Key Design

### Backend error keys

Use `UserFacingError` codes under `whatsapp_link.*`; `translate_error()` adds the `errors.` prefix.

Add to `backend/app/core/i18n/catalogs_en_general.py` and `backend/app/core/i18n/catalogs_es_general.py`:

| Code | Catalog key |
|---|---|
| `whatsapp_link.instance_not_configured` | `errors.whatsapp_link.instance_not_configured` |
| `whatsapp_link.phone_required` | `errors.whatsapp_link.phone_required` |
| `whatsapp_link.already_connected` | `errors.whatsapp_link.already_connected` |
| `whatsapp_link.service_unavailable` | `errors.whatsapp_link.service_unavailable` |
| `whatsapp_link.invalid_instance_token` | `errors.whatsapp_link.invalid_instance_token` |
| `whatsapp_link.request_failed` | `errors.whatsapp_link.request_failed` |

### Frontend UI keys

Use `frontend.whatsapp_link.*` and add translations to `catalogs_en_frontend.py` and `catalogs_es_frontend.py`:

```text
frontend.whatsapp_link.section_title
frontend.whatsapp_link.section_description
frontend.whatsapp_link.heading
frontend.whatsapp_link.description
frontend.whatsapp_link.phone_label
frontend.whatsapp_link.instance_label
frontend.whatsapp_link.status_connected
frontend.whatsapp_link.status_disconnected
frontend.whatsapp_link.status_connecting
frontend.whatsapp_link.no_phone_title
frontend.whatsapp_link.no_phone_description
frontend.whatsapp_link.pairing_tab
frontend.whatsapp_link.qr_tab
frontend.whatsapp_link.generate_code
frontend.whatsapp_link.generating_code
frontend.whatsapp_link.pairing_code_label
frontend.whatsapp_link.pairing_code_instructions
frontend.whatsapp_link.qr_instructions
frontend.whatsapp_link.refresh_qr
frontend.whatsapp_link.refreshing_qr
frontend.whatsapp_link.qr_expires_in
frontend.whatsapp_link.disconnect
frontend.whatsapp_link.disconnecting
frontend.whatsapp_link.disconnect_confirm_title
frontend.whatsapp_link.disconnect_confirm_description
frontend.whatsapp_link.success_linked
frontend.whatsapp_link.success_disconnected
frontend.whatsapp_link.error_load
frontend.whatsapp_link.error_pair
frontend.whatsapp_link.error_qr
frontend.whatsapp_link.error_disconnect
frontend.whatsapp_link.error_timeout
frontend.whatsapp_link.error_unknown
frontend.whatsapp_link.retry
```

## File Changes and Estimates

### Backend

| File | Change | Est. lines |
|---|---|---:|
| `backend/app/services/evolution_client/client.py` | Add `EvolutionClientError`, instance-token headers, 4 lifecycle methods, response normalization | +120 |
| `backend/app/services/evolution_client/__init__.py` | Export `EvolutionClientError` if tests/services import it | +2 |
| `backend/app/services/whatsapp_link_service.py` | New service for tenant validation, decrypt, Evolution orchestration | +180 |
| `backend/app/schemas/whatsapp_link.py` | New Pydantic V2 request/response schemas | +45 |
| `backend/app/api/v1/endpoints/whatsapp_link.py` | New router, DI, auth/plan gate, error translation | +130 |
| `backend/app/api/v1/router.py` | Import/include router | +3 |
| `backend/app/core/i18n/catalogs_en_general.py` | Backend error translations | +8 |
| `backend/app/core/i18n/catalogs_es_general.py` | Backend error translations | +8 |
| `backend/app/core/i18n/catalogs_en_frontend.py` | UI translations | +35 |
| `backend/app/core/i18n/catalogs_es_frontend.py` | UI translations | +35 |
| `backend/tests/test_evolution_client_whatsapp_link.py` | Unit tests for auth/routes/errors/normalization | +180 |
| `backend/tests/test_whatsapp_link_api.py` | Endpoint/service tests with mocked Evolution client | +320 |

Backend estimate: ~1,066 added/modified lines.

### Frontend

| File | Change | Est. lines |
|---|---|---:|
| `frontend/src/features/admin/services/whatsapp-link-api.ts` | Typed API functions | +55 |
| `frontend/src/features/admin/hooks/use-whatsapp-link-polling.ts` | Polling hook | +100 |
| `frontend/src/features/admin/components/whatsapp-link-section.tsx` | Main section and subcomponents | +360 |
| `frontend/src/features/admin/components/settings-page.tsx` | Add section id/menu/render/icon | +20 |
| `frontend/src/components/ui/tabs.tsx` | Add shadcn Tabs component if not installed | +90 |
| `frontend/src/features/admin/services/__tests__/whatsapp-link-api.spec.ts` | API service tests | +80 |
| `frontend/src/features/admin/hooks/__tests__/use-whatsapp-link-polling.spec.tsx` | Hook fake-timer tests | +120 |
| `frontend/src/features/admin/components/__tests__/whatsapp-link-section.spec.tsx` | Component state/flow tests | +280 |
| `frontend/src/features/admin/components/__tests__/settings-page.spec.tsx` | Add WhatsApp visibility tests and component mock | +50 |

Frontend estimate: ~1,155 added/modified lines.

## Test Strategy

### Backend: EvolutionClient

1. `get_instance_status` sends `apikey: instance-token`, not the global key.
2. `get_qr_code` sends instance-token auth and normalizes `qrcode` from supported response fields.
3. `pair_instance` sends `{ "phone": phone }`, instance-token auth, and normalizes `code` / `pairingCode`.
4. `logout_instance` sends instance-token auth and does not use global key.
5. 401/403 raises `EvolutionClientError("invalid_instance_token")`.
6. 5xx and `httpx.RequestError` raise `EvolutionClientError("service_unavailable")`.
7. Missing base URL for runtime lifecycle calls raises service unavailable rather than silently succeeding.

### Backend: API/Service

1. `GET /status` returns connected true only when both Evolution flags are true.
2. `GET /status` returns connected false when either flag is false.
3. Missing instance name/token returns 400 translated detail.
4. Pair returns `{ code }`; client-supplied phone is rejected by schema (`extra="forbid"`).
5. Pair with no phone returns 400.
6. Pair when already connected returns 409 and does not call `pair_instance`.
7. QR returns `{ qrcode }` and rejects already-connected/no-phone cases.
8. Disconnect calls `logout_instance` and returns 200 `{ connected: false }`, including already-disconnected behavior where Evolution allows it.
9. Evolution downtime maps to 503 translated detail.
10. Invalid instance token maps to 502 translated support message.
11. Missing JWT returns 401.
12. Client role returns 403.
13. Starter tenant admin cannot access (404 recommended for concealment).
14. Master support context can access starter tenant.
15. EN/ES catalogs contain all `errors.whatsapp_link.*` and `frontend.whatsapp_link.*` keys.

### Frontend: API Service

Assert exact axios calls:

- `api.get("/tenant/whatsapp-link/status")`
- `api.post("/tenant/whatsapp-link/pair", {})`
- `api.get("/tenant/whatsapp-link/qr")`
- `api.post("/tenant/whatsapp-link/disconnect")`

### Frontend: Polling Hook

Use fake timers:

1. Polls immediately, then every 5 seconds.
2. Stops on connected and calls `onConnected` once.
3. Stops at 60 seconds and calls `onTimeout`.
4. Clears timers on unmount.
5. Surfaces transient poll errors through `onError`.

### Frontend: Component

1. Initial load shows skeleton then phone/status.
2. Connected state shows connected badge and Disconnect button.
3. No phone state shows block alert and no pairing tabs.
4. Pairing code flow displays returned code and starts polling.
5. Polling success updates UI to connected and calls `toast.success` with `frontend.whatsapp_link.success_linked`.
6. QR tab loads QR image with `data:image/png;base64,...` source.
7. QR auto-refresh calls `getQRCode` again near expiry while disconnected.
8. Polling timeout shows timeout alert and retry action.
9. Disconnect confirmation calls API and returns UI to disconnected state.
10. Backend error `detail` is displayed when present; fallback translation key is used otherwise.

### Frontend: Settings Page

Update existing `settings-page.spec.tsx`:

- Mock `WhatsappLinkSection`.
- Pro tenant sees `frontend.whatsapp_link.section_title`.
- Starter tenant admin does not see WhatsApp section.
- Master support context with starter plan sees WhatsApp section.

## Rollout Plan

1. Deploy backend first; router is additive and unused until frontend ships.
2. Verify `EVOLUTION_API_URL`, `EVOLUTION_API_KEY`, and `DATA_ENCRYPTION_KEY` in target environment.
3. Smoke-test one tenant with known valid instance token:
   - status,
   - pairing code,
   - QR retrieval,
   - logout.
4. Deploy frontend with the Settings section gated to Pro/master-support.
5. Monitor logs and response metrics for `EvolutionClientError`, 503, and 502 rates.
6. If production Evolution route shape differs, patch only `EvolutionClient` route mapping.

## Rollback Considerations

- Remove `api_router.include_router(whatsapp_link.router)` from `backend/app/api/v1/router.py`.
- Revert frontend Settings section integration and remove the WhatsApp component/service/hook.
- Leave i18n keys in catalogs if desired; unused keys are harmless.
- No database rollback is required.
- No tenant fields are mutated by this feature, so rollback does not affect existing tenants or the master fallback flow.

## Known Limitations

- Passkey/WebAuthn-required WhatsApp accounts are not supported in v1.
- No link/unlink audit trail is added.
- No automatic webhook re-registration after relink; existing webhook persistence is assumed.
- Multi-device management is out of scope.
