# I18n / Localization System

Trackpal uses a Python-centered i18n system. Backend is translation source-of-truth; English default with Spanish as primary secondary locale. Tenants persist locale preference; catalogs are in-memory Python dicts loaded at import.

## Architecture

```
┌────────────────────────────────────────────────────┐
│ Backend i18n Engine (app/core/i18n/)               │
│  _CATALOG_EN, _CATALOG_ES → _MERGED[locale]        │
│  t(locale, key, **params) → str                    │
│  get_merged_catalog(locale) → dict                 │
└──────────┬─────────────────────────────────────────┘
           │
           │  resolve_locale() from tenant DB record
           │  ContextVar per-message in WhatsApp console
           ▼
┌─────────────────────────┬──────────────────────────┐
│ REST API Endpoints      │ WhatsApp Console Service   │
│  UserFacingError →      │  _t() reads _current_locale│
│   translate_error()     │  ContextVar per message    │
│  /i18n/catalog →        │                           │
│   merged catalog +      │                           │
│   locale                │                           │
└──────────┬──────────────┴──────────┬────────────────┘
           │                         │
           ▼                         ▼
┌─────────────────┐    ┌─────────────────────────────┐
│ Frontend Vue SPA│    │ n8n (pure transport,        │
│  i18n Pinia     │    │  no translation logic)      │
│  store → t()    │    │  Backend renders messages   │
└─────────────────┘    └─────────────────────────────┘
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

Column `tenants.locale` stores per-tenant locale. Migration `cd8efe74caa1`:

1. Add nullable column
2. Backfill existing rows to `es` (preserve Spanish experience)
3. Set not-null with server default `en`

Exposed via `GET /api/v1/me` → `ProfileResponse.locale`. Updated via `PUT /api/v1/me` with `ProfileUpdate.locale` validated against `VALID_LOCALES`.

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
| `wa.tenant.subscriptions.*` | WhatsApp tenant console — subscriptions | `wa.tenant.subscriptions.list.header`, `wa.tenant.subscriptions.status.active`, `wa.tenant.subscriptions.list.page_prev` |
| `frontend.*` | Vue SPA web UI | `frontend.login.title`, `frontend.clients.password` |

Total: ~838 string entries across both catalogs.

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

## Locale Resolution

### REST API Endpoints

`resolve_locale(db, tenant_id)` in `app/api/dependencies.py`:

```python
async def resolve_locale(db: AsyncSession, tenant_id: UUID) -> str:
    result = await db.execute(select(Tenant.locale).where(Tenant.id == tenant_id))
    row = result.scalar_one_or_none()
    return row if row else "en"
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

The facade resolves locale once per message from `tenant.locale` and passes it to `WhatsAppTenantConsoleService.process_message()`.

### n8n / Background Flows

Subscription job service resolves locale per reminder batch from tenant record using the existing DB session + RLS context.

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

- `tenant` role: reads `Tenant.locale` via `owner_user_id`
- `client` role: reads `Tenant.locale` via `Client → Tenant` join
- Master/unknown: returns English catalog

## Frontend I18n Store

File: `frontend/src/stores/i18n.js`. Pinia store:

```javascript
const useI18nStore = defineStore('i18n', () => {
  const locale = ref('en')
  const strings = ref({})
  const isLoaded = ref(false)

  async function loadCatalog() {
    const response = await api.get('/i18n/catalog')
    locale.value = data.locale
    strings.value = data.catalog
  }

  function t(key, params) {
    // Lookup key, warn in dev if missing
    // Apply params via string replace
  }
})
```

Catalog loaded on:

- **Login**: `LoginView` calls `i18nStore.loadCatalog()` after successful auth
- **Page refresh**: `main.js` checks `authStore.isAuthenticated` and preloads catalog
- **Locale change**: Tenant profile save triggers catalog refetch for immediate UI update

Frontend holds zero translation strings as source-of-truth. All strings come from backend catalog.

## N8n Integration

n8n workflows do not own or generate translation strings. All user-facing messages are rendered by the backend before returning to n8n. n8n acts as pure transport:

- **WhatsApp Bot**: Backend `WhatsappTenantConsoleFacade` returns fully localized reply text
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
