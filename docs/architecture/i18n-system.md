# I18n / Localization System

TrackPal uses a Python-centered i18n system. Backend is translation source-of-truth; English default with Spanish as primary secondary locale. Tenants persist locale preference; catalogs are in-memory Python dicts loaded at import.

## Architecture

```
┌───────────────────────────────────────────────────┐
│ Backend i18n Engine (app/core/i18n/)               │
│  _CATALOG_EN, _CATALOG_ES → _MERGED[locale]        │
│  t(locale, key, **params) → str                    │
│  get_merged_catalog(locale) → dict                 │
└──────────┬────────────────────────────────────────┘
           │
           │  resolve_locale() from tenant DB record
           │  ContextVar per-message in WhatsApp console
           ▼
┌─────────────────────────┬──────────────────────────┐
│ REST API Endpoints      │ WhatsApp Console Service  │
│  UserFacingError →      │  _t() reads _current_locale│
│   translate_error()     │  ContextVar per message    │
│  /i18n/catalog →        │                           │
│   merged catalog +      │                           │
│   locale                │                           │
└──────────┬──────────────┴──────────┬────────────────┘
           │                         │
           ▼                         ▼
┌──────────────────────┐  ┌──────────────────────────┐
│ Frontend             │  │ n8n (pure transport,     │
│  (React + Zustand)   │  │  no translation logic)   │
│  i18n store → t()    │  │  Backend renders messages│
└──────────────────────┘  └──────────────────────────┘
```

## Locales

| Code | Name | Use |
|------|------|-----|
| `en` | English | Default for new tenants |
| `es` | Español | Backfilled for existing tenants |

Defined in `app/core/__init__.py`:

```python
VALID_LOCALES: tuple[str, ...] = ("en", "es")
```

## Tenant Locale Persistence

Production Tenant locale is stored in the `tenant_settings` table. Each production tenant has a single row in this table, with `tenant_id` as primary key and foreign key to `tenants.id`. Migration `d011fe74cab0` created the table, backfilled locale values from the previous `tenants.locale` column and legacy `subscription_reminder_settings.timezone`, then dropped both obsolete columns.

Demo identities keep their creation locale in the nullable `tenants.demo_locale` field. This is only the initial seed for the browser-local Demo Workspace; Demo locale changes continue to use the local workspace settings and never create or update `tenant_settings`.

Exposed via:
- `GET /api/v1/tenant-settings` — Read-only endpoint for locale (and timezone)
- `PUT /api/v1/tenant-settings` — Update locale (and timezone)
- `GET /api/v1/me` → `ProfileResponse.locale` — Read-only projection for convenience (locale is not writable through `/me`)

Refer to [database-schema.md](database-schema.md#tenantsettings--tenant_settings-table) for the table definition.

## Backend i18n Engine (`app/core/i18n/`)

### Catalogs

Two immutable Python dicts defined in code:

- `_CATALOG_EN` — English strings (all keys, source of truth)
- `_CATALOG_ES` — Spanish strings (subset; missing keys fall back to English)

Organized by prefix:

| Prefix | Domain | Example |
|--------|--------|---------|
| `error.*` | Backend API errors | `error.auth.invalid_credentials` |
| `errors.*` | Business logic errors | `errors.client_not_found` |
| `reminder.*` | Subscription reminders | `reminder.subscription.expiring` |
| `wa.tenant.*` | WhatsApp tenant console — general | `wa.tenant.main_menu` |
| `wa.tenant.client_context.*` | WhatsApp tenant console — client context shortcut | `wa.tenant.client_context.menu.unregistered_unblocked`, `wa.tenant.client_context.closed` |
| `wa.nav.*` | Shared navigation labels across all WhatsApp consoles | `wa.nav.next`, `wa.nav.back`, `wa.nav.cancel`, `wa.nav.invalid_option` |
| `wa.tenant.subscriptions.*` | WhatsApp tenant console — subscriptions | `wa.tenant.subscriptions.list.header`, `wa.tenant.subscriptions.status.active`, `wa.tenant.subscriptions.list.page_prev` |
| `frontend.*` | Frontend web UI | `frontend.login.title`, `frontend.clients.password` |

Total: ~1500 string entries across both catalogs (merged per locale).

### Merged Catalog

At import time, `_MERGED` dict is precomputed per locale:

```python
for loc in VALID_LOCALES:
    base = dict(_CATALOGS.get(loc, {}))
    if loc != "en":
        for k, v in _CATALOG_EN.items():
            base.setdefault(k, v)
    _MERGED[loc] = base
```

Non-English locales get all English keys added as fallbacks. English locale uses `_CATALOG_EN` directly.

### `t()` Function

```python
def t(locale: str, key: str, /, **params: Any) -> str:
```

- Lookup key in merged catalog for requested locale
- If found and locale is not English, warn if key missing from raw locale catalog
- If not found, fall back to English merged catalog
- If still not found, return key itself (defensive fallback)
- Named params injected via `str.format(**params)`

Missing keys log `logger.warning` and increment `missing_key_counter` (per-process `Counter`). Logs at 1st, 10th, 100th, 1000th, and every 10000th occurrence to avoid spam.

### `get_merged_catalog()`

Returns a copy of the precomputed merged catalog for a locale. Used by the `/i18n/catalog` endpoint to serve frontend.

### Locale Names

```python
LOCALE_NAMES: Final[dict[str, str]] = {
    "en": "English",
    "es": "Español",
}
```

## User-Facing Errors (`app/core/errors.py`)

```python
class UserFacingError(ValueError):
    def __init__(self, code: str, *, params: dict[str, Any] | None = None) -> None:
        self.code = code
        self.params = params or {}

def translate_error(locale: str, err: UserFacingError) -> str:
    """Translate a UserFacingError into a localized message string."""
```

Services raise `UserFacingError("client_not_found")` with a machine-readable code. `translate_error()` maps to i18n key `errors.client_not_found`. Endpoints catch `UserFacingError` before `ValueError` and translate before raising `HTTPException`.

Demo lifecycle and containment outcomes are an intentional exception: `demo_operation_blocked`, `demo_ended`, and `demo_credentials_replaced` are stable machine-readable response codes rather than translated prose. The frontend maps them to localized authenticated or public copy. This keeps auth/session routing deterministic while preserving natural English and Spanish user messages.

## Locale Resolution

### REST API Endpoints

`resolve_locale(db, tenant_id)` in `app/repositories/tenant_settings_repository.py`:

```python
async def resolve_locale(db: AsyncSession, tenant_id: UUID) -> str:
    result = await db.execute(
        select(TenantSettings.locale).where(TenantSettings.tenant_id == tenant_id)
    )
    row = result.scalar_one_or_none()
    return row or "en"
```

**Critical**: `resolve_locale()` must be called *before* mutating service calls. Post-rollback RLS context loss means the tenant row may not be accessible after a failed transaction. Pattern:

```python
try:
    result = await service.do_mutate(db, tenant_id, ...)
except UserFacingError as exc:
    locale = await resolve_locale(db, tenant_id)  # Must be before the failed mutation
    raise HTTPException(..., detail=translate_error(locale, exc))
```

### WhatsApp Tenant Console

The facade resolves locale once per message from `TenantSettings.locale` (via `tenant_settings_repository.resolve_locale_by_owner()`) and passes it to `WhatsAppTenantConsoleService.process_message()`.

### n8n / Background Flows

Subscription job service resolves locale per reminder batch from `TenantSettings` (via `tenant_settings_repository`) using the existing DB session + RLS context.

## WhatsApp Console ContextVar

`WhatsAppTenantConsoleService` uses a `ContextVar` for per-message locale:

```python
_current_locale: contextvars.ContextVar[str] = contextvars.ContextVar("wa_locale", default="es")
```

Set at the start of `process_message()` and reset in `finally`:

```python
if locale is not None:
    _token = _current_locale.set(locale)
try:
    # ... handler methods call self._t(key) ...
finally:
    if _token is not None:
        _current_locale.reset(_token)
```

Convenience helper `_t(key, **params)` reads `_current_locale.get()` automatically, avoiding threading locale through 40+ handler methods.

## I18n Catalog Endpoint

`GET /api/v1/i18n/catalog` — Authenticated. Returns merged catalog for current user's tenant locale:

```json
{
  "locale": "es",
  "locale_name": "Español",
  "catalog": { "frontend.login.title": "Iniciar sesión", ... }
}
```

Role resolution:

- Production `tenant` role: reads `TenantSettings.locale` via `tenant_settings_repository.resolve_locale_by_owner()`
- Demo `tenant` role: may request `?locale=en|es`; the endpoint returns that catalog without persisting the current workspace locale server-side. The initial locale comes from `demo_locale`, while later changes come from the browser-local Demo Workspace.
- `client` role: reads `TenantSettings.locale` via `tenant_settings_repository.resolve_locale_by_client()` (joins `Client → TenantSettings` through `client.tenant_id`)
- Master/unknown: returns English catalog; locale query overrides are ignored outside Demo Tenants

## Frontend I18n Store

File: `frontend/src/i18n/index.ts`. Plain module (not Zustand):

```typescript
let currentLocale = 'en';
let catalog: Record<string, string> = {};

export async function loadCatalog() {
  const response = await api.get('/i18n/catalog')
  currentLocale = response.data.locale
  catalog = response.data.catalog
}

export function t(key: string, params?: Record<string, string>) {
  let value = catalog[key] ?? key
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      value = value.replace(new RegExp(`\\{${k}\\}`, 'g'), v)
    }
  }
  return value
}

export function getLocale() { return currentLocale }
```

Catalog loaded on authenticated lifecycle:

- **After login success**: authenticated app loads `/i18n/catalog`
- **Page refresh**: `main.ts` checks `authStore.isAuthenticated` and preloads catalog
- **Locale change**: Tenant settings save through `PUT /api/v1/tenant-settings` triggers catalog refetch for immediate UI update

### Pre-auth public i18n (frontend-only)

Login, Demo Ended, and other unauthenticated routes use local frontend catalog files, independent from backend `/i18n/catalog`:

- `frontend/src/i18n/public.json` — source for public translations (`en`, `es`)
- `frontend/src/i18n/usePublicI18n.js` — locale resolver + `t(key)` helper
- Default locale on first visit: `en`
- Selected locale persisted in `localStorage.publicLocale`

Boundary:
- Pre-auth views do **not** call backend i18n endpoint.
- Authenticated views continue using backend catalog through `frontend/src/i18n/index.ts`.

## N8n Integration

n8n workflows do not own or generate translation strings. All user-facing messages are rendered by the backend before returning to n8n. n8n acts as pure transport:

- **WhatsApp Bot**: Backend `WhatsappTenantConsoleFacade` returns fully localized reply text. The Client Context Shortcut renders all menus server-side through `wa.tenant.client_context.*` keys, including contextual menus for unregistered, blocked, active, and inactive client targets.
- **Context Shortcut close flow**: Option `0` inside a context session returns `status="closed"` and `close_jid`; the close message uses `wa.tenant.client_context.closed`.
- **Reminders**: `SubscriptionJobService._render_reminder_message()` uses `t()` with tenant locale
- n8n never calls `t()`, never resolves locale, never manipulates message content beyond phone normalization

## Migration Strategy

- Backfill: existing tenants get `es` (preserve Spanish experience)
- New tenants: default `en`
- Adding keys: safe, backward-compatible
- Removing keys: requires audit + test updates
- Missing key behavior: English fallback + warning log + counter increment

## Scope Boundaries

| In scope | Out of scope |
|----------|-------------|
| Tenant locale persistence | Client-specific locale override |
| EN + ES catalogs | Additional locales |
| Backend, frontend, WhatsApp console | Master dashboard/console (stays Spanish) |
| User-facing error translation | Business data translation (names, plans) |
| Code-defined catalogs | CMS/DB-managed translations |
