# Gmail-Only Mailbox Connection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace TrackPal's Google/Microsoft/custom mailbox configuration with a Gmail-only, app-password-first connection flow, while retaining optional Google OAuth behind a frontend new-connection release gate.

**Architecture:** The backend stores one Gmail mailbox per Tenant and dispatches by `auth_method` (`app_password` or `oauth`), with Gmail server details hidden behind a fixed app-password adapter. The frontend presents a two-step Gmail Setup Assistant and opens the existing mailbox Help topic through a stable contextual-help interface. Microsoft and generic provider support are removed from the application and public landing copy.

**Tech Stack:** Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2 async, Alembic, pytest, React 19, TypeScript strict mode, Zustand, Vitest, Testing Library, Tailwind CSS v4, private Markdown Help compiler, Next.js 15 landing.

## Global Constraints

- Gmail is the only production mailbox provider.
- Supported production authentication methods are exactly `app_password` and `oauth`.
- Never accept, request, recommend, log, or persist the user's primary Google Account password.
- The app-password adapter always uses `imap.gmail.com`, port `993`, with TLS enabled; these values are never accepted from or returned to the product UI.
- User-facing copy must not expose **IMAP**, host, port, SSL, Basic Authentication, Microsoft, or Outlook.
- `VITE_GMAIL_OAUTH_CONNECT_ENABLED` defaults to disabled and enables only the UI for starting new Google OAuth connections when its exact value is `true`.
- The frontend OAuth gate is not a backend kill switch and does not revoke or stop an existing OAuth mailbox.
- Keep the Google OAuth callback path `/api/v1/tenant/mailbox/oauth/google/callback` unchanged.
- Preserve `gmail.readonly openid email`, the OAuth disclosure, affirmative consent, and Google Limited Use language.
- App-password credentials and OAuth tokens remain encrypted at rest with the existing Fernet module.
- Validate a new app password before changing persistence; a failed replacement leaves any existing mailbox unchanged.
- The private Help tutorial stays inside `tenant-admin.mailbox`; do not create a separate topic.
- Allowed external Help destinations are exactly `https://myaccount.google.com/apppasswords` and `https://support.google.com/accounts/answer/185833`.
- English and Spanish Help metadata and external URL sets must remain in parity.
- No new runtime dependencies.

## File and Module Map

### New focused modules

- `backend/app/services/gmail_app_password.py` — fixed Gmail connection settings, password normalization, validation interface, and safe error codes.
- `backend/tests/test_gmail_app_password.py` — unit tests for the Gmail app-password module.
- `backend/alembic/versions/e019fe74cab9_make_mailbox_gmail_only.py` — deterministic data conversion and schema reduction.
- `backend/tests/test_mailbox_api.py` — authenticated Gmail mailbox endpoint contract and atomic persistence tests.
- `frontend/src/features/help/contextual-help.ts` — event interface for opening an authorized contextual Help target.
- `frontend/src/features/help/components/__tests__/safe-markdown.spec.tsx` — ordered-list and external-link rendering tests.
- `frontend/src/features/admin/components/gmail-setup-assistant.tsx` — disconnected two-step Gmail setup experience.
- `frontend/src/features/admin/components/__tests__/gmail-setup-assistant.spec.tsx` — focused assistant behavior tests.
- `frontend/src/features/admin/mailbox-config.ts` — Gmail OAuth new-connection release gate.

### Removed modules

- `backend/app/services/oauth_service/microsoft.py`
- `backend/app/services/mail_lookup_worker/providers/_microsoft.py`

### Renamed implementation module

- `backend/app/services/mail_lookup_worker/providers/_imap.py` -> `backend/app/services/mail_lookup_worker/providers/_gmail_app_password.py`

### Existing modules that remain the main seams

- `backend/app/api/v1/endpoints/mailbox.py` — authenticated mailbox connect/test/disconnect and Google OAuth routes.
- `backend/app/services/oauth_service/service.py` — Google-only OAuth orchestration.
- `backend/app/services/mail_lookup_worker/providers/__init__.py` — dispatch by authentication method.
- `frontend/src/features/admin/components/mailbox-section.tsx` — mailbox loading, connected state, and mutations.
- `frontend/src/features/help/components/contextual-help-sheet.tsx` — authorized Help target resolution and panel state.
- `backend/app/help/compiler.py` — private Help validation and artifact compilation.

---

### Task 1: Create the Gmail app-password validation module

**Files:**
- Create: `backend/app/services/gmail_app_password.py`
- Create: `backend/tests/test_gmail_app_password.py`
- Modify: `backend/app/services/imap_service.py`
- Modify: `backend/tests/test_mailbox_oauth_imap.py:568-648`

**Interfaces:**
- Consumes: `test_imap_connection(host, port, ssl, username, password)` from `app.services.imap_service`.
- Produces:
  - `GMAIL_IMAP_HOST: Final[str] = "imap.gmail.com"`
  - `GMAIL_IMAP_PORT: Final[int] = 993`
  - `GMAIL_IMAP_SSL: Final[bool] = True`
  - `GmailAppPasswordError(code: Literal["authentication_rejected", "timeout", "unavailable"])`
  - `normalize_app_password(raw: str) -> str`
  - `validate_gmail_app_password(mailbox_email: str, raw_password: str) -> Awaitable[str]`, returning the normalized credential after successful Gmail authentication.

- [ ] **Step 1: Write failing normalization and fixed-configuration tests**

```python
# backend/tests/test_gmail_app_password.py
from unittest.mock import AsyncMock

import pytest

from app.services import gmail_app_password


def test_normalize_app_password_removes_grouping_spaces() -> None:
    assert gmail_app_password.normalize_app_password(" abcd efgh ijkl mnop ") == (
        "abcdefghijklmnop"
    )


@pytest.mark.asyncio
async def test_validate_uses_fixed_gmail_settings(monkeypatch) -> None:
    connect = AsyncMock(return_value=None)
    monkeypatch.setattr(gmail_app_password, "test_imap_connection", connect)

    normalized = await gmail_app_password.validate_gmail_app_password(
        "codes@example.com", "abcd efgh ijkl mnop"
    )

    assert normalized == "abcdefghijklmnop"
    connect.assert_awaited_once_with(
        host="imap.gmail.com",
        port=993,
        ssl=True,
        username="codes@example.com",
        password="abcdefghijklmnop",
    )
```

- [ ] **Step 2: Write failing safe-error mapping tests**

```python
@pytest.mark.asyncio
@pytest.mark.parametrize(
    (error_type, expected_code),
    [
        (gmail_app_password.ImapAuthenticationError, "authentication_rejected"),
        (gmail_app_password.ImapTimeoutError, "timeout"),
        (gmail_app_password.ImapUnavailableError, "unavailable"),
    ],
)
async def test_validate_maps_imap_failures(monkeypatch, error_type, expected_code) -> None:
    monkeypatch.setattr(
        gmail_app_password,
        "test_imap_connection",
        AsyncMock(side_effect=error_type("provider detail that must not escape")),
    )

    with pytest.raises(gmail_app_password.GmailAppPasswordError) as captured:
        await gmail_app_password.validate_gmail_app_password(
            "codes@example.com", "abcdefghijklmnop"
        )

    assert captured.value.code == expected_code
    assert "provider detail" not in str(captured.value)
```

- [ ] **Step 3: Run the new tests and verify they fail**

Run: `cd backend && uv run pytest tests/test_gmail_app_password.py -q`  
Expected: FAIL because the Gmail module and typed IMAP errors do not exist.

- [ ] **Step 4: Add typed IMAP test errors**

```python
# backend/app/services/imap_service.py
class ImapConnectionError(Exception):
    """Base class for safe IMAP connection-test failures."""


class ImapAuthenticationError(ImapConnectionError):
    """The server rejected the supplied username or credential."""


class ImapTimeoutError(ImapConnectionError):
    """The connection attempt exceeded the configured timeout."""


class ImapUnavailableError(ImapConnectionError):
    """The server could not be reached or the connection failed."""
```

Update `test_imap_connection()` so `asyncio.TimeoutError` raises `ImapTimeoutError`, connection construction failures raise `ImapUnavailableError`, and `imaplib.IMAP4.error` from `login()` raises `ImapAuthenticationError`. Do not include the password in any message.

- [ ] **Step 5: Implement the Gmail app-password module**

```python
# backend/app/services/gmail_app_password.py
from __future__ import annotations

from typing import Final, Literal

from app.services.imap_service import (
    ImapAuthenticationError,
    ImapTimeoutError,
    ImapUnavailableError,
    test_imap_connection,
)

GMAIL_IMAP_HOST: Final = "imap.gmail.com"
GMAIL_IMAP_PORT: Final = 993
GMAIL_IMAP_SSL: Final = True


class GmailAppPasswordError(Exception):
    def __init__(
        self,
        code: Literal["authentication_rejected", "timeout", "unavailable"],
    ) -> None:
        self.code = code
        super().__init__(code)


def normalize_app_password(raw: str) -> str:
    return "".join(raw.strip().split())


async def validate_gmail_app_password(
    mailbox_email: str,
    raw_password: str,
) -> str:
    normalized = normalize_app_password(raw_password)
    if not normalized:
        raise GmailAppPasswordError("authentication_rejected")
    try:
        await test_imap_connection(
            host=GMAIL_IMAP_HOST,
            port=GMAIL_IMAP_PORT,
            ssl=GMAIL_IMAP_SSL,
            username=mailbox_email,
            password=normalized,
        )
    except ImapAuthenticationError as exc:
        raise GmailAppPasswordError("authentication_rejected") from exc
    except ImapTimeoutError as exc:
        raise GmailAppPasswordError("timeout") from exc
    except ImapUnavailableError as exc:
        raise GmailAppPasswordError("unavailable") from exc
    return normalized
```

- [ ] **Step 6: Update the existing IMAP utility tests for typed errors**

Replace assertions for the generic `ImapConnectionError` in `backend/tests/test_mailbox_oauth_imap.py` with the appropriate subclass and retain one assertion that all subclasses inherit from `ImapConnectionError`.

- [ ] **Step 7: Run focused tests**

Run: `cd backend && uv run pytest tests/test_gmail_app_password.py tests/test_mailbox_oauth_imap.py -q`  
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/gmail_app_password.py backend/app/services/imap_service.py backend/tests/test_gmail_app_password.py backend/tests/test_mailbox_oauth_imap.py
git commit -m "feat(mailbox): validate Gmail app passwords"
```

---

### Task 2: Replace the persistence and mailbox endpoint contract

**Files:**
- Create: `backend/alembic/versions/e019fe74cab9_make_mailbox_gmail_only.py`
- Create: `backend/tests/test_mailbox_api.py`
- Modify: `backend/app/models/tenant_mailbox.py`
- Modify: `backend/app/schemas/mailbox.py:1-90`
- Modify: `backend/app/api/v1/endpoints/mailbox.py:55-155`
- Modify: `backend/app/api/v1/endpoints/_mailbox_helpers.py:1-130`
- Modify: `backend/tests/test_mailbox_persistence.py`

**Interfaces:**
- Consumes: `validate_gmail_app_password()` and Gmail error codes from Task 1.
- Produces:
  - `MailboxAuthMethod.oauth = "oauth"`
  - `MailboxAuthMethod.app_password = "app_password"`
  - `GmailAppPasswordConnectRequest(mailbox_email: str, app_password: str)`
  - `PUT /api/v1/tenant/mailbox/` validates Gmail first, then atomically creates or replaces the mailbox.
  - `MailboxResponse` without `provider`, `imap_host`, `imap_port`, or `imap_ssl`.
  - `TenantMailbox.app_password_encrypted`.

- [ ] **Step 1: Write failing schema tests**

```python
# replace the old provider/IMAP tests in test_mailbox_persistence.py
from pydantic import ValidationError

from app.schemas.mailbox import GmailAppPasswordConnectRequest, MailboxAuthMethod


def test_gmail_connect_request_requires_email_and_app_password() -> None:
    payload = GmailAppPasswordConnectRequest(
        mailbox_email="codes@example.com",
        app_password="abcd efgh ijkl mnop",
    )
    assert payload.mailbox_email == "codes@example.com"
    assert payload.app_password == "abcd efgh ijkl mnop"
    assert MailboxAuthMethod.app_password.value == "app_password"


def test_gmail_connect_request_rejects_empty_password() -> None:
    with pytest.raises(ValidationError):
        GmailAppPasswordConnectRequest(
            mailbox_email="codes@example.com", app_password=""
        )
```

- [ ] **Step 2: Write failing endpoint success and response-shape tests**

```python
# backend/tests/test_mailbox_api.py
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from app.core.encryption import decrypt_value
from app.models import Tenant, TenantMailbox


async def _tenant_headers(client) -> dict[str, str]:
    login = await client.post(
        "/api/v1/auth/login",
        json={"username": "tenant", "password": "tenant-password"},
    )
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


@pytest.mark.asyncio
async def test_connect_app_password_validates_before_persisting(
    client, db_session, active_tenant_user, monkeypatch
) -> None:
    validate = AsyncMock(return_value="abcdefghijklmnop")
    monkeypatch.setattr(
        "app.api.v1.endpoints.mailbox.validate_gmail_app_password", validate
    )

    response = await client.put(
        "/api/v1/tenant/mailbox/",
        json={
            "mailbox_email": "codes@example.com",
            "app_password": "abcd efgh ijkl mnop",
        },
        headers=await _tenant_headers(client),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["auth_method"] == "app_password"
    assert body["status"] == "connected"
    assert "provider" not in body
    assert "imap_host" not in body
    validate.assert_awaited_once_with(
        "codes@example.com", "abcd efgh ijkl mnop"
    )

    tenant_id = (
        await db_session.execute(
            select(Tenant.id).where(Tenant.owner_user_id == active_tenant_user.id)
        )
    ).scalar_one()
    db_session.expire_all()
    mailbox = (
        await db_session.execute(
            select(TenantMailbox).where(TenantMailbox.tenant_id == tenant_id)
        )
    ).scalar_one()
    assert decrypt_value(mailbox.app_password_encrypted) == "abcdefghijklmnop"
```

- [ ] **Step 3: Write failing atomic-replacement and safe-error tests**

Add tests that seed a working `app_password` mailbox, make `validate_gmail_app_password()` raise each `GmailAppPasswordError`, call `PUT /tenant/mailbox/`, and assert:

```python
assert response.status_code in {400, 503}
assert response.json()["detail"] in {
    "gmail_app_password_rejected",
    "gmail_connection_unavailable",
}
assert decrypt_value(mailbox.app_password_encrypted) == "old-working-password"
assert mailbox.mailbox_email == "old@example.com"
```

Map `authentication_rejected` to HTTP 400 and both `timeout` and `unavailable` to HTTP 503.

- [ ] **Step 4: Run the new contract tests and verify failure**

Run: `cd backend && uv run pytest tests/test_mailbox_api.py tests/test_mailbox_persistence.py -q`  
Expected: FAIL because the Gmail-only schema, model, migration, and endpoint do not exist.

- [ ] **Step 5: Implement the Gmail-only model and schemas**

```python
# backend/app/schemas/mailbox.py
class MailboxAuthMethod(str, Enum):
    oauth = "oauth"
    app_password = "app_password"


class GmailAppPasswordConnectRequest(BaseModel):
    mailbox_email: str = Field(min_length=3, max_length=255)
    app_password: str = Field(min_length=1, max_length=500)
```

Remove `MailboxProvider` and provider/server fields. In `TenantMailbox`, remove `provider`, `imap_host`, `imap_port`, and `imap_ssl`, and rename the mapped credential to `app_password_encrypted`.

- [ ] **Step 6: Add the deterministic Alembic migration**

The upgrade must execute these operations in order:

```python
op.execute("""
DELETE FROM tenant_mailboxes
WHERE NOT (
  (provider = 'google' AND auth_method = 'oauth')
  OR (
    provider = 'imap_custom'
    AND auth_method = 'imap_app_password'
    AND lower(imap_host) = 'imap.gmail.com'
    AND coalesce(imap_port, 993) = 993
    AND coalesce(imap_ssl, true) = true
  )
)
""")
op.execute("""
UPDATE tenant_mailboxes
SET auth_method = 'app_password'
WHERE auth_method = 'imap_app_password'
""")
op.alter_column(
    "tenant_mailboxes",
    "imap_password_encrypted",
    new_column_name="app_password_encrypted",
)
op.drop_column("tenant_mailboxes", "imap_host")
op.drop_column("tenant_mailboxes", "imap_port")
op.drop_column("tenant_mailboxes", "imap_ssl")
op.drop_column("tenant_mailboxes", "provider")
op.create_check_constraint(
    "ck_tenant_mailboxes_auth_method",
    "tenant_mailboxes",
    "auth_method IN ('oauth', 'app_password')",
)
```

The downgrade must execute this order so the new check constraint never blocks restoration: drop `ck_tenant_mailboxes_auth_method`; restore the four dropped columns as nullable; derive `provider='google'` for OAuth and `provider='imap_custom'` for app-password rows; restore Gmail server values for app-password rows; map `app_password` back to `imap_app_password`; rename the encrypted column back; then make `provider` non-null after population.

- [ ] **Step 7: Implement validate-before-persist in the endpoint**

Use `GmailAppPasswordConnectRequest` as the PUT payload. Call validation before loading or mutating the existing mailbox. After success, create or update with:

```python
values = {
    "mailbox_email": payload.mailbox_email,
    "auth_method": "app_password",
    "status": "connected",
    "app_password_encrypted": encrypt_value(normalized_password),
    "oauth_provider_user_id": None,
    "oauth_provider_email": None,
    "oauth_access_token_encrypted": None,
    "oauth_refresh_token_encrypted": None,
    "oauth_token_expires_at": None,
    "oauth_scope": None,
    "last_connection_test_at": datetime.now(timezone.utc),
    "last_connection_error": None,
}
```

Commit once after mutation. Do not persist a disconnected intermediate row.

- [ ] **Step 8: Update response and stored-connection tests**

Update `_mailbox_helpers.mailbox_response()` and `_perform_imap_test()` to use `app_password_encrypted` and fixed Gmail settings. Rename the internal helper to `_perform_app_password_test()` and route `auth_method == "app_password"` to it. Remove the endpoint restriction that prevented testing OAuth, because `_perform_oauth_test()` already provides the correct test path.

- [ ] **Step 9: Validate the migration and focused backend contract**

Run:

```bash
cd backend
uv run alembic upgrade head --sql > ../.tmp-gmail-mailbox-migration.sql
uv run pytest tests/test_gmail_app_password.py tests/test_mailbox_api.py tests/test_mailbox_persistence.py -q
uv run ruff check app/models/tenant_mailbox.py app/schemas/mailbox.py app/api/v1/endpoints/mailbox.py app/api/v1/endpoints/_mailbox_helpers.py app/services/gmail_app_password.py tests/test_gmail_app_password.py tests/test_mailbox_api.py tests/test_mailbox_persistence.py
```

Expected: migration SQL contains the data conversion, credential rename, dropped provider/server columns, and auth-method constraint; tests and Ruff pass.

- [ ] **Step 10: Commit**

```bash
git add backend/alembic/versions/e019fe74cab9_make_mailbox_gmail_only.py backend/app/models/tenant_mailbox.py backend/app/schemas/mailbox.py backend/app/api/v1/endpoints/mailbox.py backend/app/api/v1/endpoints/_mailbox_helpers.py backend/tests/test_mailbox_api.py backend/tests/test_mailbox_persistence.py
git commit -m "feat(mailbox): persist Gmail-only connections"
```

---

### Task 3: Make OAuth and mailbox fetching Google-only

**Files:**
- Delete: `backend/app/services/oauth_service/microsoft.py`
- Delete: `backend/app/services/mail_lookup_worker/providers/_microsoft.py`
- Rename: `backend/app/services/mail_lookup_worker/providers/_imap.py` -> `backend/app/services/mail_lookup_worker/providers/_gmail_app_password.py`
- Rename: `backend/tests/test_mailbox_oauth_imap.py` -> `backend/tests/test_mailbox_google_connections.py`
- Modify: `backend/app/core/config.py:33-46`
- Modify: `backend/.env.example:43-54`
- Modify: `backend/app/services/oauth_service/__init__.py`
- Modify: `backend/app/services/oauth_service/service.py`
- Modify: `backend/app/api/v1/endpoints/mailbox.py:155-230`
- Modify: `backend/app/services/mail_lookup_worker/providers/__init__.py`
- Modify: `backend/app/services/mail_lookup_worker/providers/_gmail_app_password.py`
- Modify: `backend/app/services/mail_lookup_worker/_helpers.py:30-45`
- Modify: `backend/tests/test_mailbox_google_connections.py`
- Modify: `backend/tests/test_mailbox_lookup_worker.py`
- Modify: `backend/tests/test_mailbox_lookup_api.py`
- Modify: `backend/tests/test_mailbox_cleanup.py`
- Modify: `backend/tests/test_access_control_api.py`
- Modify: `backend/tests/test_whatsapp_endpoint.py`
- Modify: `backend/tests/test_whatsapp_external_admin_menu_guard.py`

**Interfaces:**
- Consumes: Gmail-only `TenantMailbox` and `app_password_encrypted` from Task 2.
- Produces:
  - `MailboxOAuthService.start_oauth(db, tenant_id)`
  - `MailboxOAuthService.complete_oauth(db, code, state)`
  - Google-only state tokens containing `tenant_id`, nonce, expiry, and type.
  - `fetch_recent_emails()` dispatching only by `auth_method`.
  - `fetch_gmail_app_password_emails(mailbox, window_minutes)`.
  - Metrics use `provider="gmail"`; `method` remains `oauth` or `app_password`.

- [ ] **Step 1: Rewrite OAuth tests to state the Google-only interface**

After `git mv`, remove every Microsoft import and test. Add or retain tests equivalent to:

```python
def test_state_token_contains_no_provider() -> None:
    tenant_id = uuid.uuid4()
    payload = _decode_state_token(_create_state_token(tenant_id))
    assert payload is not None
    assert payload["tenant_id"] == str(tenant_id)
    assert "provider" not in payload


@pytest.mark.asyncio
async def test_start_oauth_is_google_only() -> None:
    result = await oauth_service.start_oauth(None, uuid.uuid4())
    assert "accounts.google.com" in result.auth_url


@pytest.mark.asyncio
async def test_google_oauth_replaces_app_password(db_session, monkeypatch) -> None:
    # Seed auth_method="app_password" with encrypted app_password.
    # Mock Google exchange/user info.
    # Complete OAuth and assert app_password_encrypted is None,
    # auth_method == "oauth", and status == "connected".
```

- [ ] **Step 2: Add failing provider-dispatch tests**

```python
@pytest.mark.asyncio
async def test_fetch_dispatches_oauth_to_gmail(monkeypatch) -> None:
    mailbox = TenantMailbox(auth_method="oauth")
    fetch = AsyncMock(return_value=[])
    monkeypatch.setattr(pmod, "fetch_google_emails", fetch)
    await pmod.fetch_recent_emails(mailbox, 5, db=AsyncMock())
    fetch.assert_awaited_once()


@pytest.mark.asyncio
async def test_fetch_dispatches_app_password_to_gmail_adapter(monkeypatch) -> None:
    mailbox = TenantMailbox(auth_method="app_password")
    fetch = AsyncMock(return_value=[])
    monkeypatch.setattr(pmod, "fetch_gmail_app_password_emails", fetch)
    await pmod.fetch_recent_emails(mailbox, 5)
    fetch.assert_awaited_once_with(mailbox, 5)
```

- [ ] **Step 3: Run the Google connection and worker tests to verify failure**

Run: `cd backend && uv run pytest tests/test_mailbox_google_connections.py tests/test_mailbox_lookup_worker.py -q`  
Expected: FAIL while provider branching and old module names remain.

- [ ] **Step 4: Simplify OAuth state and orchestration**

Change the state interface to:

```python
def _create_state_token(tenant_id: UUID) -> str:
    payload = {
        "tenant_id": str(tenant_id),
        "nonce": secrets.token_urlsafe(16),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=10),
        "type": "oauth_state",
    }
    return jwt.encode(payload, settings.secret_key, algorithm=STATE_ALGORITHM)
```

Remove Microsoft branches and imports. OAuth completion always uses Google exchange/user-info helpers, stores `auth_method="oauth"`, clears `app_password_encrypted`, and records metrics with `provider="gmail"`.

- [ ] **Step 5: Keep only Google OAuth routes**

Use literal routes:

```python
@router.post("/oauth/google/start", response_model=OAuthStartResponse)
async def oauth_start(db: DbDep, tenant_id: ActiveTenantId):
    return await oauth_service.start_oauth(db, tenant_id)


@router.get("/oauth/google/callback", response_class=HTMLResponse)
async def oauth_callback(db: DbDep, code: str = Query(...), state: str = Query(...)):
    await oauth_service.complete_oauth(db, code, state)
    await db.commit()
    return HTMLResponse(content=_oauth_callback_html("success"))
```

A request to `/oauth/microsoft/start` must return 404 because no route exists.

- [ ] **Step 6: Rename and simplify the Gmail app-password fetch adapter**

The renamed adapter must:

```python
host = GMAIL_IMAP_HOST
port = GMAIL_IMAP_PORT
ssl = GMAIL_IMAP_SSL
password = _get_app_password(mailbox)
```

Read `mailbox.app_password_encrypted`, retain `BODY.PEEK[]`, and keep protocol-specific log/error details internal. Export `fetch_gmail_app_password_emails`.

- [ ] **Step 7: Dispatch only by authentication method**

```python
elif mailbox.auth_method == "oauth":
    if db is None:
        raise NonTransientProviderError(
            "DB session required for OAuth fetch",
            error_code="provider_config_error",
        )
    emails = await fetch_google_emails(mailbox, window_minutes, db=db)
elif mailbox.auth_method == "app_password":
    emails = await fetch_gmail_app_password_emails(mailbox, window_minutes)
else:
    raise NonTransientProviderError(
        f"Unsupported auth method: {mailbox.auth_method}",
        error_code="provider_config_error",
    )
```

`resolve_provider_label()` returns `"gmail"` when a mailbox is present and `"unknown"` otherwise.

- [ ] **Step 8: Remove Microsoft configuration and update all mailbox fixtures**

Delete Microsoft settings from `config.py` and `.env.example`. Update every `TenantMailbox(...)` fixture found by:

```bash
rg -n 'provider=|"provider":|imap_app_password|imap_password_encrypted|imap_host|imap_port|imap_ssl' backend/tests backend/app
```

Production fixtures use `auth_method="oauth"` or `auth_method="app_password"`. App-password fixtures use `app_password_encrypted`. Remove provider/server keys rather than replacing them.

- [ ] **Step 9: Run the backend mailbox and dependent tests**

Run:

```bash
cd backend
uv run pytest tests/test_gmail_app_password.py tests/test_mailbox_api.py tests/test_mailbox_google_connections.py tests/test_mailbox_persistence.py tests/test_mailbox_lookup_worker.py tests/test_mailbox_lookup_api.py tests/test_mailbox_cleanup.py tests/test_mailbox_metrics.py tests/test_access_control_api.py tests/test_whatsapp_endpoint.py tests/test_whatsapp_external_admin_menu_guard.py -q
uv run ruff check app/core/config.py app/services/oauth_service app/services/mail_lookup_worker app/api/v1/endpoints/mailbox.py tests/test_mailbox_google_connections.py tests/test_mailbox_lookup_worker.py
```

Expected: PASS with no import of Microsoft modules and no old mailbox field references.

- [ ] **Step 10: Commit**

```bash
git add -A backend/app/services/oauth_service backend/app/services/mail_lookup_worker backend/app/core/config.py backend/.env.example backend/app/api/v1/endpoints/mailbox.py backend/tests
git commit -m "refactor(mailbox): remove non-Gmail providers"
```

---

### Task 4: Add safe Gmail tutorial capabilities to private Help

**Files:**
- Modify: `backend/app/help/compiler.py`
- Modify: `backend/help/en/tenant-admin/mailbox.md`
- Modify: `backend/help/es/tenant-admin/mailbox.md`
- Modify: `backend/app/help/artifact.json`
- Modify: `backend/tests/test_help_contract.py`
- Modify: `backend/tests/test_help_hardening.py`
- Create: `frontend/src/features/help/components/__tests__/safe-markdown.spec.tsx`
- Modify: `frontend/src/features/help/components/safe-markdown.tsx`

**Interfaces:**
- Produces:
  - Help compiler validation for HTTPS external links.
  - External hostname allow-list: `myaccount.google.com`, `support.google.com`.
  - Locale parity check for external destination URL sets.
  - SafeMarkdown support for ordered lists and allowed external links.
  - Expanded bilingual `tenant-admin.mailbox` tutorial.

- [ ] **Step 1: Write failing compiler allow-list and parity tests**

```python
# backend/tests/test_help_hardening.py

def test_compiler_rejects_unknown_external_help_host(tmp_path: Path) -> None:
    source_dir = tmp_path / "help"
    shutil.copytree(SOURCE_DIR, source_dir)
    path = source_dir / "en" / "tenant-admin" / "mailbox.md"
    path.write_text(
        path.read_text(encoding="utf-8")
        + "\n\n[Unsafe](https://example.com/account)\n",
        encoding="utf-8",
    )
    with pytest.raises(HelpValidationError, match="external Help host"):
        compile_help(source_dir)


def test_compiler_rejects_external_url_locale_mismatch(tmp_path: Path) -> None:
    source_dir = tmp_path / "help"
    shutil.copytree(SOURCE_DIR, source_dir)
    path = source_dir / "es" / "tenant-admin" / "mailbox.md"
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "https://support.google.com/accounts/answer/185833",
            "https://myaccount.google.com/apppasswords",
        ),
        encoding="utf-8",
    )
    with pytest.raises(HelpValidationError, match="external URL parity"):
        compile_help(source_dir)
```

Also add coverage for `http://support.google.com/...` rejection.

- [ ] **Step 2: Write failing SafeMarkdown rendering tests**

```tsx
// frontend/src/features/help/components/__tests__/safe-markdown.spec.tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SafeMarkdown } from "../safe-markdown";

describe("SafeMarkdown", () => {
  it("renders ordered tutorial steps", () => {
    render(<SafeMarkdown source={"1. Enable 2-Step Verification.\n2. Create the password."} />);
    expect(screen.getByRole("list")).toHaveClass("list-decimal");
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
  });

  it("renders allowed Google links safely", () => {
    render(
      <SafeMarkdown
        source={"[Open Google](https://myaccount.google.com/apppasswords)"}
      />,
    );
    expect(screen.getByRole("link", { name: "Open Google" })).toHaveAttribute(
      "target",
      "_blank",
    );
    expect(screen.getByRole("link", { name: "Open Google" })).toHaveAttribute(
      "rel",
      "noopener noreferrer",
    );
  });

  it("does not create a link for an unknown host", () => {
    render(<SafeMarkdown source={"[Unsafe](https://example.com)"} />);
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 3: Run Help tests and verify failure**

Run:

```bash
cd backend && uv run pytest tests/test_help_contract.py tests/test_help_hardening.py -q
cd ../frontend && npm test -- --run src/features/help/components/__tests__/safe-markdown.spec.tsx
```

Expected: FAIL because links and ordered lists are not supported or validated.

- [ ] **Step 4: Add compiler link validation**

Use `urllib.parse.urlsplit` and a Markdown link regex that captures all link destinations. Relative `.md` links remain allowed. Separate extraction from validation so metadata parity does not need filesystem paths:

```python
ALLOWED_EXTERNAL_HELP_HOSTS = {"myaccount.google.com", "support.google.com"}


def _absolute_link_destinations(body: str) -> set[str]:
    return {
        destination
        for destination in MARKDOWN_LINK_PATTERN.findall(body)
        if urlsplit(destination).scheme or urlsplit(destination).netloc
    }


def _validate_external_help_links(body: str, path: Path) -> None:
    for destination in _absolute_link_destinations(body):
        parsed = urlsplit(destination)
        if parsed.scheme != "https":
            raise HelpValidationError(f"External Help URL must use HTTPS in {path.name}")
        if parsed.hostname not in ALLOWED_EXTERNAL_HELP_HOSTS:
            raise HelpValidationError(f"Unknown external Help host in {path.name}")
```

Call `_validate_external_help_links(body, path)` while compiling each source file. Store no new artifact field. During metadata parity validation, compare `_absolute_link_destinations(english_topic["body"])` with the Spanish set and raise `HelpValidationError("External URL parity mismatch for <topic-id>")` when they differ.

- [ ] **Step 5: Extend SafeMarkdown without adding a Markdown dependency**

Add:

```tsx
const ALLOWED_EXTERNAL_HELP_HOSTS = new Set([
  "myaccount.google.com",
  "support.google.com",
]);

function allowedExternalHelpUrl(value: string): string | null {
  try {
    const url = new URL(value);
    return url.protocol === "https:" && ALLOWED_EXTERNAL_HELP_HOSTS.has(url.hostname)
      ? url.toString()
      : null;
  } catch {
    return null;
  }
}
```

Render blocks whose every line matches `/^\d+\.\s+/` as `<ol className="... list-decimal ...">`. Use this combined token pattern for inline bold and HTTPS links:

```tsx
const INLINE_TOKEN_PATTERN = /(\*\*[^*]+\*\*|\[[^\]]+\]\(https:\/\/[^)]+\))/g;
```

For a link token, extract label and destination with `/^\[([^\]]+)\]\((https:\/\/[^)]+)\)$/`. Render:

```tsx
const href = allowedExternalHelpUrl(destination);
return href ? (
  <a
    key={`${href}-${index}`}
    href={href}
    target="_blank"
    rel="noopener noreferrer"
    className="font-medium text-primary underline-offset-4 hover:underline"
  >
    {label}
  </a>
) : (
  label
);
```

Unknown or malformed destinations therefore degrade to plain label text.

- [ ] **Step 6: Replace the mailbox Help body and search terms**

Both locales must remove Microsoft, Outlook, and user-facing IMAP. Include the two exact official URLs, an ordered setup sequence, app-password eligibility causes, normal-password prohibition, revocation after a main-password change, recovery instructions, and conditional wording for Google Connection.

Update the existing contract test to assert:

```python
for locale in ("en", "es"):
    body = topics_by_locale[locale]["tenant-admin.mailbox"]["body"]
    assert "myaccount.google.com/apppasswords" in body
    assert "support.google.com/accounts/answer/185833" in body
    assert "Microsoft" not in body
    assert "Outlook" not in body
```

Use localized equivalents for the primary-password and 2-Step Verification assertions.

- [ ] **Step 7: Recompile and verify the private Help artifact**

Run:

```bash
cd backend
uv run python -m scripts.compile_help
uv run python -m scripts.verify_help_release
uv run pytest tests/test_help_contract.py tests/test_help_hardening.py tests/test_help_release.py -q
cd ../frontend
npm test -- --run src/features/help/components/__tests__/safe-markdown.spec.tsx
```

Expected: artifact changes only reflect the source Markdown/compiler output; all checks pass.

- [ ] **Step 8: Commit**

```bash
git add backend/app/help/compiler.py backend/help/en/tenant-admin/mailbox.md backend/help/es/tenant-admin/mailbox.md backend/app/help/artifact.json backend/tests/test_help_contract.py backend/tests/test_help_hardening.py frontend/src/features/help/components/safe-markdown.tsx frontend/src/features/help/components/__tests__/safe-markdown.spec.tsx
git commit -m "feat(help): document Gmail app-password setup"
```

---

### Task 5: Add a contextual Help request interface

**Files:**
- Create: `frontend/src/features/help/contextual-help.ts`
- Modify: `frontend/src/features/help/components/contextual-help-sheet.tsx`
- Modify: `frontend/src/features/help/components/__tests__/contextual-help-sheet.spec.tsx`

**Interfaces:**
- Consumes: `HelpTargetId` and existing authorized Help index/topic operations.
- Produces:
  - `CONTEXTUAL_HELP_REQUEST_EVENT = "trackpal:contextual-help-request"`
  - `requestContextualHelp(target: HelpTargetId): void`
  - Contextual Help Sheet accepts a requested target without DOM click simulation.

- [ ] **Step 1: Write the failing event-driven Help test**

```tsx
import { act, render, screen, waitFor } from "@testing-library/react";
import { HELP_TARGETS } from "../../help-targets";
import { requestContextualHelp } from "../../contextual-help";

it("opens a requested authorized target without unmounting local state", async () => {
  vi.mocked(getHelpIndex).mockResolvedValue({
    schema_version: 1,
    content_version: "help-client-manual-1",
    frontend_target_contract_version: "2",
    locale: "en",
    topics: [
      {
        id: "tenant-admin.mailbox",
        title: "Central mailbox",
        summary: "Gmail guidance",
        module: "settings",
        route: "/admin/settings",
        order: 70,
        help_targets: [HELP_TARGETS.mailbox],
        safe_navigation: {
          route: "/admin/settings",
          settings_category: "mailbox",
        },
      },
    ],
  });
  vi.mocked(getHelpTopic).mockResolvedValue({
    ...topic,
    id: "tenant-admin.mailbox",
    title: "Central mailbox",
    help_targets: [HELP_TARGETS.mailbox],
    body: "# Gmail setup\n\nTutorial body.",
  });

  render(
    <>
      <input aria-label="Draft email" defaultValue="unsaved@example.com" />
      <ContextualHelpSheet />
    </>,
  );

  act(() => requestContextualHelp(HELP_TARGETS.mailbox));

  await waitFor(() => expect(screen.getByText("Tutorial body.")).toBeInTheDocument());
  expect(screen.getByLabelText("Draft email")).toHaveValue("unsaved@example.com");
  expect(getHelpTopic).toHaveBeenCalledWith("tenant-admin.mailbox");
});
```

- [ ] **Step 2: Run the contextual Help test and verify failure**

Run: `cd frontend && npm test -- --run src/features/help/components/__tests__/contextual-help-sheet.spec.tsx`  
Expected: FAIL because `requestContextualHelp` does not exist and the sheet only opens from its button.

- [ ] **Step 3: Implement the request interface**

```ts
// frontend/src/features/help/contextual-help.ts
import type { HelpTargetId } from "./help-targets";

export const CONTEXTUAL_HELP_REQUEST_EVENT = "trackpal:contextual-help-request";

export function requestContextualHelp(target: HelpTargetId): void {
  window.dispatchEvent(
    new CustomEvent<HelpTargetId>(CONTEXTUAL_HELP_REQUEST_EVENT, { detail: target }),
  );
}
```

- [ ] **Step 4: Teach ContextualHelpSheet to resolve an explicit target**

Refactor `openHelp()` into a `useCallback` that accepts `requestedTarget?: HelpTargetId`, falling back to `findActiveHelpTarget()` only for the existing toolbar button. Register a `useEffect` listener for `CONTEXTUAL_HELP_REQUEST_EVENT` and call `openHelp(event.detail)`. Include `openHelp` in the effect dependencies and remove the listener on unmount. Keep version checks and backend authorization unchanged.

- [ ] **Step 5: Run the contextual Help tests**

Run: `cd frontend && npm test -- --run src/features/help/components/__tests__/contextual-help-sheet.spec.tsx`  
Expected: PASS for toolbar, client target, explicit mailbox target, local state, and focus restoration tests.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/features/help/contextual-help.ts frontend/src/features/help/components/contextual-help-sheet.tsx frontend/src/features/help/components/__tests__/contextual-help-sheet.spec.tsx
git commit -m "feat(help): open contextual topics by target"
```

---

### Task 6: Build the Gmail Setup Assistant and frontend release gate

**Files:**
- Create: `frontend/src/features/admin/components/gmail-setup-assistant.tsx`
- Create: `frontend/src/features/admin/components/__tests__/gmail-setup-assistant.spec.tsx`
- Modify: `frontend/src/features/admin/components/mailbox-section.tsx`
- Modify: `frontend/src/features/admin/components/__tests__/mailbox-section.spec.tsx`
- Modify: `frontend/src/features/admin/services/settings-api.ts:33-60,139-176`
- Create: `frontend/src/features/admin/mailbox-config.ts`
- Modify: `frontend/src/features/demo/services/demo-settings.ts:218-235`
- Modify: `frontend/.env.example`
- Modify: `backend/app/core/i18n/catalogs_en_frontend.py:470-535`
- Modify: `backend/app/core/i18n/catalogs_es_frontend.py:470-535`

**Interfaces:**
- Consumes: Gmail-only backend response from Tasks 2-3 and `requestContextualHelp()` from Task 5.
- Produces:
  - `isGmailOAuthConnectEnabled(): boolean`
  - `GmailAppPasswordConnect { mailbox_email: string; app_password: string }`
  - `connectGmail(payload): Promise<Mailbox>`
  - `startGoogleOAuth(): Promise<{ auth_url: string; state: string }>`
  - `GmailSetupAssistant` props:

```ts
interface GmailSetupAssistantProps {
  oauthConnectEnabled: boolean;
  onConnect(payload: GmailAppPasswordConnect): Promise<boolean>;
  onStartOAuth(): Promise<void>;
}
```

- [ ] **Step 1: Write failing release-gate tests**

```ts
// add to gmail-setup-assistant.spec.tsx
import { isGmailOAuthConnectEnabled } from "@/features/admin/mailbox-config";

beforeEach(() => {
  vi.unstubAllEnvs();
});

it.each([undefined, "", "false", "TRUE", "1"])(
  "keeps Gmail OAuth hidden for %s",
  (value) => {
    vi.stubEnv("VITE_GMAIL_OAUTH_CONNECT_ENABLED", value);
    expect(isGmailOAuthConnectEnabled()).toBe(false);
  },
);

it("enables Gmail OAuth only for exact true", () => {
  vi.stubEnv("VITE_GMAIL_OAUTH_CONNECT_ENABLED", "true");
  expect(isGmailOAuthConnectEnabled()).toBe(true);
});
```

- [ ] **Step 2: Write failing assistant navigation and official-link tests**

```tsx
it("guides the user from app-password instructions to credentials", async () => {
  const user = userEvent.setup();
  render(
    <GmailSetupAssistant
      oauthConnectEnabled={false}
      onConnect={vi.fn()}
      onStartOAuth={vi.fn()}
    />,
  );

  expect(screen.getByText("frontend.mailbox.app_password_step_title")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "frontend.mailbox.open_google" })).toHaveAttribute(
    "href",
    "https://myaccount.google.com/apppasswords",
  );
  expect(screen.queryByText("OAuth")).not.toBeInTheDocument();
  expect(screen.queryByText(/Microsoft|Outlook|IMAP/i)).not.toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "frontend.mailbox.have_app_password" }));
  expect(screen.getByLabelText("frontend.mailbox.google_email")).toBeInTheDocument();
  expect(screen.getByLabelText("frontend.mailbox.app_password")).toBeInTheDocument();
});
```

- [ ] **Step 3: Write failing connect, failure-clearing, and Help tests**

Add tests that:

```tsx
const connect = vi.fn().mockResolvedValue(true);
// Fill business@example.com and "abcd efgh ijkl mnop".
// Click Connect Gmail.
expect(connect).toHaveBeenCalledWith({
  mailbox_email: "business@example.com",
  app_password: "abcd efgh ijkl mnop",
});
```

For `onConnect.mockResolvedValue(false)`, assert the email remains and the app-password field becomes empty. Mock `requestContextualHelp` and assert **View full tutorial** requests `HELP_TARGETS.mailbox`. When `VITE_PRIVATE_HELP_ENABLED=false`, assert that tutorial action is absent but the Google link remains.

- [ ] **Step 4: Write failing optional OAuth and connected-state tests**

Update `mailbox-section.spec.tsx` so:

- default/missing OAuth flag does not render the OAuth disclosure or start action;
- exact `true` renders **Use Google Connection**;
- selecting it renders the disclosure and requires consent before `startGoogleOAuth()`;
- a connected `auth_method="oauth"` mailbox remains visible when the flag is false;
- status copy uses `frontend.mailbox.method_google_connection` or `frontend.mailbox.method_app_password` and never contains IMAP.

Remove the obsolete provider-switch test.

- [ ] **Step 5: Run frontend mailbox tests and verify failure**

Run:

```bash
cd frontend
npm test -- --run src/features/admin/components/__tests__/gmail-setup-assistant.spec.tsx src/features/admin/components/__tests__/mailbox-section.spec.tsx
```

Expected: FAIL because the assistant, release gate, and Gmail-only client types do not exist.

- [ ] **Step 6: Implement frontend configuration and client contracts**

```ts
// frontend/src/features/admin/mailbox-config.ts
export function isGmailOAuthConnectEnabled(): boolean {
  return import.meta.env.VITE_GMAIL_OAUTH_CONNECT_ENABLED === "true";
}
```

```ts
// settings-api.ts
export type MailboxAuthMethod = "app_password" | "oauth" | "demo";

export interface Mailbox {
  id: string;
  tenant_id: string;
  mailbox_email: string;
  auth_method: MailboxAuthMethod;
  status: string;
  last_connection_test_at: string | null;
  last_connection_error: string | null;
  created_at: string;
  updated_at: string;
}

export interface GmailAppPasswordConnect {
  mailbox_email: string;
  app_password: string;
}

export async function connectGmail(payload: GmailAppPasswordConnect): Promise<Mailbox> {
  const { data } = await api.put("/tenant/mailbox/", payload);
  return data;
}

export async function startGoogleOAuth(): Promise<{ auth_url: string; state: string }> {
  const { data } = await api.post("/tenant/mailbox/oauth/google/start");
  return data;
}
```

Update the Demo Mailbox to the reduced response shape with `auth_method: "demo"` and no provider/server fields.

- [ ] **Step 7: Implement the two-step Gmail Setup Assistant**

Use local state for `step: "instructions" | "credentials" | "oauth"`, email, app password, password visibility, and submitting status. The tutorial button calls:

```ts
requestContextualHelp(HELP_TARGETS.mailbox);
```

The Google link uses `target="_blank"` and `rel="noopener noreferrer"`. On a false result from `onConnect`, clear only the app-password state. The optional OAuth path owns its consent checkbox and resets consent after starting or leaving the OAuth step.

- [ ] **Step 8: Rewrite MailboxSection around the assistant**

`MailboxSection` retains loading, cache invalidation, BroadcastChannel completion, test, and disconnect behavior. Its app-password handler returns `Promise<boolean>`:

```ts
async function handleConnectAppPassword(
  payload: GmailAppPasswordConnect,
): Promise<boolean> {
  try {
    await connectGmail(payload);
    useSettingsStore.getState().clearSettingsCache();
    await loadMailboxData();
    toast.success(t("frontend.mailbox.success_connected"));
    return true;
  } catch (error) {
    toast.error(mailboxErrorMessage(error));
    return false;
  }
}
```

Map backend detail codes:

- `gmail_app_password_rejected` -> app-password rejection translation.
- `gmail_connection_unavailable` -> retry/unavailable translation.
- otherwise -> generic save error.

- [ ] **Step 9: Replace mailbox i18n copy and environment example**

Remove Microsoft, Outlook, custom provider, host, port, SSL, and user-facing IMAP keys. Add bilingual keys for assistant steps, official Google action, tutorial action, eligibility explanation, primary-password warning, method labels, back, show/hide password, and safe error messages.

Append to `frontend/.env.example`:

```env
# Exposes only the UI for starting new Gmail OAuth connections.
# Existing OAuth mailboxes remain operational when this is false.
VITE_GMAIL_OAUTH_CONNECT_ENABLED=false
```

- [ ] **Step 10: Run frontend and i18n tests**

Run:

```bash
cd frontend
npm test -- --run src/features/admin/components/__tests__/gmail-setup-assistant.spec.tsx src/features/admin/components/__tests__/mailbox-section.spec.tsx src/features/help/components/__tests__/contextual-help-sheet.spec.tsx
npm run lint
npm run build
cd ../backend
uv run pytest tests/test_i18n.py -q
uv run ruff check app/core/i18n/catalogs_en_frontend.py app/core/i18n/catalogs_es_frontend.py
```

Expected: all pass; production build contains the Gmail assistant and defaults OAuth connection availability to false.

- [ ] **Step 11: Commit**

```bash
git add frontend/src/features/admin/components/gmail-setup-assistant.tsx frontend/src/features/admin/components/mailbox-section.tsx frontend/src/features/admin/components/__tests__/gmail-setup-assistant.spec.tsx frontend/src/features/admin/components/__tests__/mailbox-section.spec.tsx frontend/src/features/admin/services/settings-api.ts frontend/src/features/admin/mailbox-config.ts frontend/src/features/demo/services/demo-settings.ts frontend/.env.example backend/app/core/i18n/catalogs_en_frontend.py backend/app/core/i18n/catalogs_es_frontend.py
git commit -m "feat(frontend): add Gmail setup assistant"
```

---

### Task 7: Synchronize TrackPal architecture and product documentation

**Files:**
- Modify: `docs/architecture/mailbox-ingestion.md`
- Modify: `docs/architecture/database-schema.md`
- Modify: `docs/architecture/api-layer.md`
- Modify: `docs/architecture/tenant-deletion.md`
- Modify: `docs/architecture/user-help-system.md`
- Modify: `docs/codebase/backend-structure.md`
- Modify: `docs/codebase/frontend-components.md`
- Modify: `docs/project-pdr/product-goals.md`
- Modify: `docs/project-pdr/business-rules.md`
- Modify: `docs/project-pdr/user-help-requirements.md`
- Modify: `docs/releases/user-help-release.md`
- Modify: `backend/CONTEXT.md`
- Modify: `frontend/CONTEXT.md`

**Interfaces:**
- Consumes: implemented names, routes, data fields, Help behavior, and release gate from Tasks 1-6.
- Produces: current-state documentation with no active Microsoft or generic-provider claims.

- [ ] **Step 1: Update mailbox architecture and API contracts**

Document:

```text
PUT /tenant/mailbox/          Gmail app-password validate-and-connect
GET /tenant/mailbox/          Reduced Gmail mailbox response
POST /tenant/mailbox/test     Tests either app_password or oauth
POST /tenant/mailbox/oauth/google/start
GET /tenant/mailbox/oauth/google/callback
POST /tenant/mailbox/disconnect
```

State that app-password connection validation happens before persistence and Gmail server details are fixed implementation details.

- [ ] **Step 2: Update schema, lifecycle, deletion, metrics, and codebase references**

Replace provider-based language with Gmail/auth-method language. Document `app_password_encrypted`, removal of configurable server fields, fixed `provider="gmail"` metrics, provider-side revocation responsibilities, renamed adapter, and deleted Microsoft modules.

- [ ] **Step 3: Update Help and product requirements**

Describe the two-step Gmail Setup Assistant, contextual tutorial panel, official Google links, exact Help URL allow-list, frontend OAuth connection availability gate, and mandatory Spanish/English desktop/mobile QA.

- [ ] **Step 4: Verify stale references are intentional only**

Run:

```bash
rg -n "Microsoft|Outlook|imap_custom|imap_app_password|IMAP custom|custom IMAP" backend/app frontend/src docs backend/CONTEXT.md frontend/CONTEXT.md \
  --glob '!docs/superpowers/specs/2026-07-30-gmail-only-mailbox-connection-design.md' \
  --glob '!docs/superpowers/plans/2026-07-30-gmail-only-mailbox-connection.md'
```

Expected: no active product/code references. Protocol-level `IMAP` may remain only in internal Gmail adapter or architecture explanations that explicitly mark it as hidden implementation detail.

- [ ] **Step 5: Run documentation-adjacent checks**

Run:

```bash
cd backend
uv run python -m scripts.verify_help_release
uv run pytest tests/test_help_contract.py tests/test_help_hardening.py tests/test_help_release.py tests/test_i18n.py -q
uv run ruff check .
cd ../frontend
npm run lint
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add docs backend/CONTEXT.md frontend/CONTEXT.md
git commit -m "docs(mailbox): document Gmail-only connections"
```

---

### Task 8: Remove Microsoft from the public landing and legal copy

**Files:**
- Modify: `E:/Documentos/GitHub/trackpal-landing/src/src/lib/privacy-policy-content.ts`
- Modify: `E:/Documentos/GitHub/trackpal-landing/src/src/lib/terms-of-service-content.ts`
- Modify: `E:/Documentos/GitHub/trackpal-landing/src/src/lib/about-content.ts`
- Modify: `E:/Documentos/GitHub/trackpal-landing/src/src/dictionaries/en.json`
- Modify: `E:/Documentos/GitHub/trackpal-landing/src/src/dictionaries/es.json`
- Modify: `E:/Documentos/GitHub/trackpal-landing/src/src/__tests__/PrivacyPolicyDocument.test.tsx`
- Modify: `E:/Documentos/GitHub/trackpal-landing/src/src/__tests__/AboutContent.test.ts`
- Modify: `E:/Documentos/GitHub/trackpal-landing/src/src/__tests__/DictionaryShape.test.ts`
- Modify: `E:/Documentos/GitHub/trackpal-landing/docs/adr/0001-privacy-policy-scope-and-data-roles.md`

**Interfaces:**
- Consumes: final Gmail connection semantics from the TrackPal implementation.
- Produces: bilingual public copy that distinguishes OAuth read-only permission from TrackPal's limited use of an encrypted app password.

- [ ] **Step 1: Write failing landing assertions**

Update tests to require:

```ts
const rendered = JSON.stringify({ privacyPolicyContent, aboutContent, en, es });
expect(rendered).not.toMatch(/Microsoft|Outlook/);
expect(rendered).toMatch(/app password|contraseña de aplicación/i);
expect(rendered).toMatch(/Google API Services User Data Policy|Política de Datos de Usuario/);
```

In `AboutContent.test.ts`, assert Google is named, Microsoft is absent, and the behavior is described as limited to reading without claiming every credential is a scope-limited read-only permission.

- [ ] **Step 2: Run landing tests and verify failure**

Run: `cd E:/Documentos/GitHub/trackpal-landing/src && npm run test:run -- src/__tests__/PrivacyPolicyDocument.test.tsx src/__tests__/AboutContent.test.ts src/__tests__/DictionaryShape.test.ts`  
Expected: FAIL because current content names Outlook/Microsoft and treats all mailbox access as a read-only provider permission.

- [ ] **Step 3: Update the Privacy Policy in both locales**

Required content:

- Gmail is the only connected mailbox.
- TrackPal may store an encrypted Google app password or encrypted OAuth tokens, depending on the chosen method.
- OAuth uses `gmail.readonly` and remains subject to Google Limited Use.
- With an app password, TrackPal's implementation uses the credential only to read recent messages needed for requested code lookup; the credential itself is not described as scope-limited.
- Disconnecting removes local encrypted credentials; the owner separately revokes the app password or OAuth grant in Google.
- Remove the Microsoft provider row and all Google/Microsoft combined language.
- Set the policy effective date to the implementation release date, `July 30, 2026` / `30 de julio de 2026`, unless release occurs later; if later, use the actual release date consistently.

- [ ] **Step 4: Update Terms, About, homepage dictionaries, FAQ, and ADR**

Replace every Gmail/Outlook choice with Gmail-only language. Use behavior-based copy such as:

```text
TrackPal uses the connected Gmail account only to read recent access-code messages needed for a requested lookup. TrackPal does not send, edit, or delete email.
```

Do not label the app-password credential itself as a read-only permission. Preserve Google OAuth revocation language and add app-password revocation where relevant.

- [ ] **Step 5: Verify public-copy consistency**

Run:

```bash
cd E:/Documentos/GitHub/trackpal-landing
rg -n "Microsoft|Outlook" src docs --glob '!node_modules/**' --glob '!.next/**'
cd src
npm run test:run
npm run build
```

Expected: grep returns no active references; 203-or-more tests pass and Next.js production build succeeds.

- [ ] **Step 6: Commit in the landing repository**

```bash
cd E:/Documentos/GitHub/trackpal-landing
git add docs/adr/0001-privacy-policy-scope-and-data-roles.md src/src/lib/privacy-policy-content.ts src/src/lib/terms-of-service-content.ts src/src/lib/about-content.ts src/src/dictionaries/en.json src/src/dictionaries/es.json src/src/__tests__/PrivacyPolicyDocument.test.tsx src/src/__tests__/AboutContent.test.ts src/src/__tests__/DictionaryShape.test.ts
git commit -m "docs(mailbox): describe Gmail-only access"
```

---

### Task 9: Run full cross-repository verification and manual QA

**Files:**
- Verify only; modify a file only to fix a failure traced to Tasks 1-8.

**Interfaces:**
- Consumes: all completed tasks and both repository commits.
- Produces: release evidence that backend, frontend, Help, migration, and landing are mutually consistent.

- [ ] **Step 1: Run the complete backend suite and static checks**

Run:

```bash
cd E:/Documentos/GitHub/trackpal/backend
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run alembic heads
uv run alembic upgrade head --sql > ../.tmp-gmail-mailbox-full.sql
uv run python -m scripts.verify_help_release
```

Expected:

- Full pytest suite passes.
- Ruff lint and format checks pass.
- Alembic reports only head `e019fe74cab9`.
- Offline SQL includes the Gmail-only mailbox migration.
- Checked-in Help artifact matches source.

- [ ] **Step 2: Run the complete frontend suite**

Run:

```bash
cd E:/Documentos/GitHub/trackpal/frontend
npm test -- --run
npm run lint
npm run build
```

Expected: all Vitest tests pass, ESLint exits zero, and TypeScript/Vite production build succeeds.

- [ ] **Step 3: Run the complete landing suite**

Run:

```bash
cd E:/Documentos/GitHub/trackpal-landing/src
npm run test:run
npm run build
```

Expected: all landing tests and Next.js production build pass.

- [ ] **Step 4: Perform repository-wide stale-reference and diff checks**

Run:

```bash
cd E:/Documentos/GitHub/trackpal
git diff --check
rg -n "microsoft_oauth|fetch_microsoft_emails|imap_custom|imap_app_password" backend frontend docs \
  --glob '!docs/superpowers/specs/2026-07-30-gmail-only-mailbox-connection-design.md' \
  --glob '!docs/superpowers/plans/2026-07-30-gmail-only-mailbox-connection.md'
git status --short

cd E:/Documentos/GitHub/trackpal-landing
git diff --check
rg -n "Microsoft|Outlook" src docs --glob '!node_modules/**' --glob '!.next/**'
git status --short
```

Expected: no stale implementation/product references, no whitespace errors, and only intentional uncommitted verification artifacts. Delete `.tmp-gmail-mailbox-migration.sql` and `.tmp-gmail-mailbox-full.sql` before final status.

- [ ] **Step 5: Complete manual Gmail Setup Assistant QA**

Verify in Spanish and English, desktop and mobile:

1. With `VITE_GMAIL_OAUTH_CONNECT_ENABLED=false`, only the app-password assistant appears.
2. Step 1 opens Google's app-password page in a new tab.
3. **View full tutorial** opens the mailbox topic in the contextual side panel and preserves assistant state.
4. Step 2 contains only Google email and app-password fields.
5. Show/hide credential works and no value reaches browser storage.
6. Rejected credentials preserve email, clear the password, show the safe message, and create no mailbox row.
7. Successful validation produces Connected status and the App Password method label.
8. Test Connection and Disconnect work.
9. With `VITE_GMAIL_OAUTH_CONNECT_ENABLED=true`, Google Connection appears as secondary, disclosure and consent are required, and the callback reconnects the status card.
10. An existing OAuth mailbox remains visible when the flag returns to false.
11. No user-facing surface displays IMAP, Microsoft, Outlook, host, port, or SSL.

- [ ] **Step 6: Commit only verified fixes, if any**

If verification required a correction, stage only that correction with its regression test and use an accurately scoped conventional commit. If no correction was needed, do not create an empty commit.

- [ ] **Step 7: Record final evidence in the completion response**

Report exact test counts, build results, Alembic head, Help verification result, manual QA rows completed, both repository commit hashes, and any intentionally deferred operational step such as enabling Google OAuth in a specific deployment.
