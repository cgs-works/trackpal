# Remove Google OAuth from Mailbox Ingestion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove Google OAuth and its verification-only `trackpal_demo` service from TrackPal, leaving Gmail App Password Connection as the sole production Mailbox connection method.

**Architecture:** Collapse Mailbox authentication to one deep app-password module: the Mailbox interface exposes get/connect/test/disconnect, while the worker's `fetch_recent_emails(mailbox, window_minutes)` interface hides fixed Gmail IMAP details. A forward Alembic migration deletes OAuth Mailboxes, OAuth columns, `auth_method`, and `trackpal_demo` state without rewriting published migration history.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2 async, Alembic, PostgreSQL, pytest, React 19, TypeScript 6 strict mode, Zustand, Vitest, Vite, bilingual compiled Markdown Help.

## Global Constraints

- Remove Google OAuth only from Mailbox ingestion; preserve FastAPI `OAuth2PasswordBearer` and TrackPal JWT/Bearer login behavior.
- Gmail App Password Connection is the sole production Mailbox connection method; do not retain a constant `auth_method` field.
- Delete existing OAuth Mailbox rows and all `oauth_*` columns through a new migration; do not edit published Alembic migrations.
- Delete `trackpal_demo`, its global status, tenant selections, extractor, UI/WhatsApp catalog entries, verification fixture, and tests.
- Validate a submitted Gmail app password before reading or mutating an existing Mailbox; a failed replacement must preserve the existing connection.
- Removed OAuth routes use normal 404 routing behavior; do not add compatibility endpoints or HTTP 410 handlers.
- Keep `gmail_app_password_rejected` for HTTP 400 and `gmail_connection_unavailable` for HTTP 503.
- Do not expose IMAP host, port, SSL, or the account's primary Google password in user-facing copy.
- Preserve English/Spanish Help parity and regenerate `backend/app/help/artifact.json` from source Markdown.
- OAuth references may remain only in immutable migrations, the removal spec/plan, TrackPal JWT/Bearer transport, the new destructive migration, and negative route-regression tests.
- Execute tasks sequentially. Each task completes its full red-green-refactor cycle and commit before the next task begins.

---

## File Map

### Database transition

- Create `backend/alembic/versions/e020fe74cac0_remove_mailbox_oauth.py` — destructive forward migration and compatibility downgrade.
- Create `backend/tests/test_remove_mailbox_oauth_migration.py` — operation-order, dropped-column, and irreversible-data contract tests.

### Backend Mailbox module

- Modify `backend/app/models/tenant_mailbox.py` — app-password-only persistence model.
- Modify `backend/app/schemas/mailbox.py` — Mailbox responses without authentication discriminators or OAuth identity.
- Modify `backend/app/api/v1/endpoints/mailbox.py` — get/connect/test/disconnect only.
- Modify `backend/app/api/v1/endpoints/_mailbox_helpers.py` — direct app-password testing and fixed metric label.
- Modify `backend/app/services/mail_lookup_worker/providers/__init__.py` — one production fetch implementation behind `fetch_recent_emails`.
- Modify `backend/app/services/mail_lookup_worker/providers/_types.py` — retain only app-password-relevant provider errors.
- Modify `backend/app/services/mail_lookup_worker/_helpers.py` — remove OAuth-only database forwarding from the fetch interface.
- Modify `backend/app/services/mail_lookup_worker/worker.py` — remove revoked/permission OAuth branches.
- Modify `backend/app/core/config.py`, `backend/.env.example`, and `backend/app/services/__init__.py` — remove OAuth configuration and exports.
- Delete `backend/app/services/oauth_service/__init__.py`, `backend/app/services/oauth_service/google.py`, and `backend/app/services/oauth_service/service.py`.
- Delete `backend/app/services/mail_lookup_worker/providers/_google.py`.
- Rename `backend/tests/test_mailbox_google_connections.py` to `backend/tests/test_imap_service.py`, retaining only IMAP connection behavior.
- Update Mailbox fixtures and assertions across backend tests so no active model construction passes `auth_method` or OAuth columns.

### Verification-only Code Service

- Delete `backend/app/services/mail_code_extractor/catalog/trackpal_demo.py`.
- Modify `backend/app/services/mail_code_extractor/catalog/__init__.py`, `backend/app/schemas/code_services.py`, `backend/app/services/whatsapp_tenant_console_service/constants.py`, and `backend/app/services/whatsapp_tenant_console_service/codigo_flow.py` — remove `trackpal_demo` from every active catalog.
- Modify `backend/tests/test_mail_code_extractor.py`, `backend/tests/test_code_services.py`, and `backend/tests/test_tenant_console_service.py` — enforce the six-service catalog.
- Delete `backend/tests/test_trackpal_demo_verification.py` and `docs/verification/trackpal-demo-code-email.html`.

### Frontend Mailbox module

- Modify `frontend/src/features/admin/services/settings-api.ts` — production `Mailbox` has no `auth_method`; remove OAuth start call.
- Modify `frontend/src/features/admin/components/gmail-setup-assistant.tsx` — instructions and credentials only.
- Modify `frontend/src/features/admin/components/mailbox-section.tsx` — no OAuth selector, method label, popup, or callback listener.
- Modify `frontend/src/features/demo/services/demo-settings.ts` — Demo Mailbox uses the same discriminator-free shape.
- Modify focused frontend tests to assert the single app-password path.
- Modify backend-served frontend i18n catalogs to remove OAuth, revoked-state, and method-selector keys.
- Delete `frontend/src/features/admin/mailbox-config.ts` and remove `VITE_GMAIL_OAUTH_CONNECT_ENABLED` from `frontend/.env.example`.

### Documentation and Help

- Modify bilingual Mailbox, export, and deletion Help sources and `backend/tests/test_help_contract.py`.
- Regenerate `backend/app/help/artifact.json` with `backend/scripts/compile_help.py`.
- Update current architecture, schema, codebase, product, release, and summary documentation listed in Task 5.
- Delete `docs/verification/google-oauth-demo.md` and the prior hybrid Superpowers plan/spec.

---

### Task 1: Add the destructive database migration

**Files:**
- Create: `backend/alembic/versions/e020fe74cac0_remove_mailbox_oauth.py`
- Create: `backend/tests/test_remove_mailbox_oauth_migration.py`

**Interfaces:**
- Consumes: Alembic head `e019fe74cab9`; tables `tenant_mailboxes`, `tenant_code_service_selections`, and `code_service_global_status`.
- Produces: a schema where `tenant_mailboxes` has `mailbox_email`, `status`, `app_password_encrypted`, connection-monitoring fields, IDs, and timestamps, but no `auth_method` or `oauth_*` fields; no active `trackpal_demo` database rows.

- [ ] **Step 1: Write migration contract tests**

Create `backend/tests/test_remove_mailbox_oauth_migration.py` with an operation recorder and these assertions:

```python
from __future__ import annotations

import importlib.util
from pathlib import Path


MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "e020fe74cac0_remove_mailbox_oauth.py"
)


def _load_migration_module():
    spec = importlib.util.spec_from_file_location("remove_mailbox_oauth", MIGRATION_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class _FakeOp:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

    def execute(self, sql: str) -> None:
        self.calls.append(("execute", (sql,), {}))

    def drop_constraint(self, name: str, table: str, type_: str = "") -> None:
        self.calls.append(("drop_constraint", (name, table, type_), {}))

    def create_check_constraint(self, name: str, table: str, condition: str) -> None:
        self.calls.append(("create_check_constraint", (name, table, condition), {}))

    def drop_column(self, table: str, column: str) -> None:
        self.calls.append(("drop_column", (table, column), {}))

    def add_column(self, table: str, column: object) -> None:
        self.calls.append(("add_column", (table, column), {}))

    def alter_column(self, table: str, column: str, **kwargs: object) -> None:
        self.calls.append(("alter_column", (table, column), kwargs))


def test_upgrade_deletes_oauth_and_verification_rows_before_dropping_columns(monkeypatch):
    module = _load_migration_module()
    fake = _FakeOp()
    monkeypatch.setattr(module, "op", fake)

    module.upgrade()

    assert fake.calls[0][:2] == (
        "drop_constraint",
        ("ck_tenant_mailboxes_auth_method", "tenant_mailboxes", "check"),
    )
    sql = [call[1][0] for call in fake.calls if call[0] == "execute"]
    assert "auth_method = 'oauth'" in sql[0]
    assert "tenant_code_service_selections" in sql[1]
    assert "service_key = 'trackpal_demo'" in sql[1]
    assert "code_service_global_status" in sql[2]
    first_drop = next(i for i, call in enumerate(fake.calls) if call[0] == "drop_column")
    last_delete = max(i for i, call in enumerate(fake.calls) if call[0] == "execute")
    assert last_delete < first_drop


def test_upgrade_drops_oauth_columns_and_auth_method(monkeypatch):
    module = _load_migration_module()
    fake = _FakeOp()
    monkeypatch.setattr(module, "op", fake)

    module.upgrade()

    dropped = {call[1][1] for call in fake.calls if call[0] == "drop_column"}
    assert dropped == {
        "oauth_provider_user_id",
        "oauth_provider_email",
        "oauth_access_token_encrypted",
        "oauth_refresh_token_encrypted",
        "oauth_token_expires_at",
        "oauth_scope",
        "auth_method",
    }


def test_downgrade_restores_legacy_shape_and_global_demo_service(monkeypatch):
    module = _load_migration_module()
    fake = _FakeOp()
    monkeypatch.setattr(module, "op", fake)

    module.downgrade()

    added = {call[1][1].name for call in fake.calls if call[0] == "add_column"}
    assert added == {
        "auth_method",
        "oauth_provider_user_id",
        "oauth_provider_email",
        "oauth_access_token_encrypted",
        "oauth_refresh_token_encrypted",
        "oauth_token_expires_at",
        "oauth_scope",
    }
    sql = " ".join(call[1][0] for call in fake.calls if call[0] == "execute")
    assert "SET auth_method = 'app_password'" in sql
    assert "VALUES ('trackpal_demo', true)" in sql
    constraints = [call for call in fake.calls if call[0] == "create_check_constraint"]
    assert constraints[0][1][2] == "auth_method IN ('oauth', 'app_password')"
```

- [ ] **Step 2: Run the migration tests and verify the file is missing**

Run:

```bash
cd backend
uv run pytest tests/test_remove_mailbox_oauth_migration.py -v
```

Expected: FAIL while loading `e020fe74cac0_remove_mailbox_oauth.py` because the migration has not been created.

- [ ] **Step 3: Implement the migration**

Create `backend/alembic/versions/e020fe74cac0_remove_mailbox_oauth.py`:

```python
"""Remove Mailbox OAuth and the verification-only TrackPal Demo service.

Revision ID: e020fe74cac0
Revises: e019fe74cab9
Create Date: 2026-07-31 00:00:00.000000

The upgrade irreversibly deletes OAuth Mailbox rows and tenant selections for
trackpal_demo. The downgrade restores schema compatibility and the global
service row, but cannot reconstruct deleted credentials or selections.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e020fe74cac0"
down_revision: str | None = "e019fe74cab9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OAUTH_COLUMNS = (
    "oauth_provider_user_id",
    "oauth_provider_email",
    "oauth_access_token_encrypted",
    "oauth_refresh_token_encrypted",
    "oauth_token_expires_at",
    "oauth_scope",
)


def upgrade() -> None:
    op.drop_constraint(
        "ck_tenant_mailboxes_auth_method",
        "tenant_mailboxes",
        type_="check",
    )
    op.execute("DELETE FROM tenant_mailboxes WHERE auth_method = 'oauth'")
    op.execute(
        "DELETE FROM tenant_code_service_selections "
        "WHERE service_key = 'trackpal_demo'"
    )
    op.execute(
        "DELETE FROM code_service_global_status "
        "WHERE service_key = 'trackpal_demo'"
    )
    for column in _OAUTH_COLUMNS:
        op.drop_column("tenant_mailboxes", column)
    op.drop_column("tenant_mailboxes", "auth_method")


def downgrade() -> None:
    op.add_column(
        "tenant_mailboxes",
        sa.Column("auth_method", sa.String(50), nullable=True),
    )
    op.execute("UPDATE tenant_mailboxes SET auth_method = 'app_password'")
    op.alter_column("tenant_mailboxes", "auth_method", nullable=False)

    op.add_column(
        "tenant_mailboxes",
        sa.Column("oauth_provider_user_id", sa.String(255), nullable=True),
    )
    op.add_column(
        "tenant_mailboxes",
        sa.Column("oauth_provider_email", sa.String(255), nullable=True),
    )
    op.add_column(
        "tenant_mailboxes",
        sa.Column("oauth_access_token_encrypted", sa.String(2000), nullable=True),
    )
    op.add_column(
        "tenant_mailboxes",
        sa.Column("oauth_refresh_token_encrypted", sa.String(500), nullable=True),
    )
    op.add_column(
        "tenant_mailboxes",
        sa.Column("oauth_token_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "tenant_mailboxes",
        sa.Column("oauth_scope", sa.String(500), nullable=True),
    )
    op.create_check_constraint(
        "ck_tenant_mailboxes_auth_method",
        "tenant_mailboxes",
        "auth_method IN ('oauth', 'app_password')",
    )
    op.execute(
        "INSERT INTO code_service_global_status (service_key, is_active) "
        "VALUES ('trackpal_demo', true) "
        "ON CONFLICT (service_key) DO NOTHING"
    )
```

- [ ] **Step 4: Run migration verification**

Run:

```bash
cd backend
uv run pytest tests/test_remove_mailbox_oauth_migration.py -v
uv run alembic heads
uv run ruff check alembic/versions/e020fe74cac0_remove_mailbox_oauth.py tests/test_remove_mailbox_oauth_migration.py
```

Expected: migration tests PASS, Ruff PASS, and Alembic reports only `e020fe74cac0 (head)`.

- [ ] **Step 5: Commit the migration**

```bash
git add backend/alembic/versions/e020fe74cac0_remove_mailbox_oauth.py backend/tests/test_remove_mailbox_oauth_migration.py
git commit -m "refactor(mailbox): remove OAuth schema"
```

---

### Task 2: Collapse the backend Mailbox module to App Password Connection

**Files:**
- Modify: `backend/app/models/tenant_mailbox.py:1-64`
- Modify: `backend/app/schemas/mailbox.py:1-82`
- Modify: `backend/app/api/v1/endpoints/mailbox.py:1-209`
- Modify: `backend/app/api/v1/endpoints/_mailbox_helpers.py:1-126`
- Modify: `backend/app/services/mail_lookup_worker/providers/__init__.py:1-103`
- Modify: `backend/app/services/mail_lookup_worker/providers/_types.py:1-80`
- Modify: `backend/app/services/mail_lookup_worker/_helpers.py:45-80`
- Modify: `backend/app/services/mail_lookup_worker/worker.py:28-55,220-340`
- Modify: `backend/app/core/config.py:1-42`
- Modify: `backend/.env.example:41-48`
- Modify: `backend/app/services/__init__.py:1-55`
- Delete: `backend/app/services/oauth_service/__init__.py`
- Delete: `backend/app/services/oauth_service/google.py`
- Delete: `backend/app/services/oauth_service/service.py`
- Delete: `backend/app/services/mail_lookup_worker/providers/_google.py`
- Rename: `backend/tests/test_mailbox_google_connections.py` → `backend/tests/test_imap_service.py`
- Modify tests: `backend/tests/test_mailbox_api.py`, `backend/tests/test_mailbox_persistence.py`, `backend/tests/test_mailbox_cleanup.py`, `backend/tests/test_mailbox_lookup_api.py`, `backend/tests/test_mailbox_lookup_worker.py`, `backend/tests/test_gmail_app_password_provider.py`, `backend/tests/test_access_control_api.py`, `backend/tests/test_whatsapp_endpoint.py`, `backend/tests/test_whatsapp_external_admin_menu_guard.py`, `backend/tests/test_demo_integration_gate.py`, `backend/tests/test_mailbox_metrics.py`

**Interfaces:**
- Consumes: migration contract from Task 1; `validate_gmail_app_password(email, password) -> str`; fixed Gmail constants from `app.services.gmail_app_password`.
- Produces: `MailboxResponse` without `auth_method` or OAuth identity fields; `fetch_recent_emails(mailbox: TenantMailbox, window_minutes: int) -> list[EmailMessage]`; Mailbox HTTP interface limited to GET/PUT/POST test/POST disconnect.

- [ ] **Step 1: Rewrite Mailbox API and persistence tests for the final contract**

In `backend/tests/test_mailbox_api.py`, remove OAuth fixtures and assert the final response shape and removed routes:

```python
assert response.status_code == 200
body = response.json()
assert body["mailbox_email"] == "codes@example.com"
assert body["status"] == "connected"
assert "auth_method" not in body
assert not any(key.startswith("oauth_") for key in body)

@pytest.mark.asyncio
async def test_removed_oauth_routes_return_404(client, active_tenant_user) -> None:
    headers = await _tenant_headers(client)
    start = await client.post(
        "/api/v1/tenant/mailbox/oauth/google/start",
        headers=headers,
    )
    callback = await client.get(
        "/api/v1/tenant/mailbox/oauth/google/callback",
        params={"code": "removed", "state": "removed"},
    )
    assert start.status_code == 404
    assert callback.status_code == 404
```

Replace the existing OAuth replacement fixture with an app-password Mailbox and verify that a successful replacement updates the encrypted credential:

```python
old = TenantMailbox(
    tenant_id=tenant_id,
    mailbox_email="old@example.com",
    status="connected",
    app_password_encrypted=encrypt_value("old-password"),
)
# After PUT:
assert mailbox.mailbox_email == "new@example.com"
assert decrypt_value(mailbox.app_password_encrypted) == "new-normalized-pw"
```

In `backend/tests/test_mailbox_persistence.py`, remove `MailboxAuthMethod`, construct `TenantMailbox` without `auth_method`, change the status update case from `revoked` to `error`, and use these enum assertions:

```python
assert MailboxStatus.connected.value == "connected"
assert LookupJobStatus.completed.value == "completed"
assert LookupResultType.code.value == "code"
```

- [ ] **Step 2: Rewrite worker tests for the narrow fetch interface**

In `backend/tests/test_mailbox_lookup_worker.py`, remove `RevokedMailboxError`, `mailbox_revoked`, and `permission_denied` cases. Keep app-password-relevant safe codes:

```python
@pytest.mark.asyncio
async def test_auth_failed_error(self, db_session):
    job = await self._run_stub(
        db_session,
        NonTransientProviderError("Gmail app-password authentication failed"),
    )
    assert job.status == "failed"
    assert job.error_code == "auth_failed"

@pytest.mark.asyncio
async def test_provider_config_error(self, db_session):
    job = await self._run_stub(
        db_session,
        NonTransientProviderError(
            "No app password stored",
            error_code="provider_config_error",
        ),
    )
    assert job.status == "failed"
    assert job.error_code == "provider_config_error"
```

Update every `StubProvider.fetch_recent` override to accept only `(mailbox, window_minutes)`. Remove `auth_method` from `_seed_mailbox` fixtures in this file and in the other test files listed above.

- [ ] **Step 3: Preserve only IMAP tests from the mixed OAuth test file**

Run:

```bash
git mv backend/tests/test_mailbox_google_connections.py backend/tests/test_imap_service.py
```

Reduce `backend/tests/test_imap_service.py` to the imports and `TestImapService` class currently under the `# ─── IMAP Service` heading. The retained import block is:

```python
import asyncio
import imaplib
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.services.imap_service import (
    ImapAuthenticationError,
    ImapConnectionError,
    ImapTimeoutError,
    ImapUnavailableError,
    test_imap_connection as _test_imap_connection,
)
```

Delete all Google provider, state-token, OAuth orchestration, exclusivity, auth-method dispatch, Gmail API refresh, and OAuth helper tests from that file.

- [ ] **Step 4: Run the focused tests and verify they fail against the old implementation**

Run:

```bash
cd backend
uv run pytest \
  tests/test_mailbox_api.py \
  tests/test_mailbox_persistence.py \
  tests/test_mailbox_lookup_worker.py \
  tests/test_imap_service.py \
  -v
```

Expected: FAIL because responses and models still expose `auth_method`/OAuth fields, removed routes still exist, the provider interface still accepts OAuth parameters, and revoked behavior still exists.

- [ ] **Step 5: Remove OAuth and `auth_method` from the persistence and schema interfaces**

Reduce `TenantMailbox` to the following Mailbox-specific fields:

```python
class TenantMailbox(Base, TimestampMixin):
    __tablename__ = "tenant_mailboxes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    mailbox_email: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), default="disconnected", server_default="disconnected", nullable=False
    )
    app_password_encrypted: Mapped[str | None] = mapped_column(String(500), nullable=True)
    last_connection_test_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_connection_error: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    tenant = relationship("Tenant")
```

In `backend/app/schemas/mailbox.py`, delete `MailboxAuthMethod`, remove `revoked` from `MailboxStatus`, delete `OAuthStartResponse`, and make `MailboxResponse` contain only:

```python
class MailboxResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    mailbox_email: str
    status: str
    last_connection_test_at: datetime | None = None
    last_connection_error: str | None = None
    created_at: datetime
    updated_at: datetime
```

- [ ] **Step 6: Simplify Mailbox endpoints and connection testing**

In `backend/app/api/v1/endpoints/mailbox.py`, remove `Query`, `HTMLResponse`, `DemoGuardrailError`, `OAuthStartResponse`, callback HTML, and both OAuth routes. Build upsert values without discriminator or token-clearing fields:

```python
values = {
    "mailbox_email": payload.mailbox_email,
    "status": "connected",
    "app_password_encrypted": encrypt_value(normalized_password),
    "last_connection_test_at": now,
    "last_connection_error": None,
}
```

In `_mailbox_helpers.py`, make response conversion and tests app-password-only:

```python
def mailbox_response(mb: TenantMailbox) -> MailboxResponse:
    return MailboxResponse(
        id=mb.id,
        tenant_id=mb.tenant_id,
        mailbox_email=mb.mailbox_email,
        status=mb.status,
        last_connection_test_at=mb.last_connection_test_at,
        last_connection_error=mb.last_connection_error,
        created_at=mb.created_at,
        updated_at=mb.updated_at,
    )

async def test_mailbox_connection(db, mailbox: TenantMailbox) -> MailboxTestResponse:
    return await _perform_app_password_test(db, mailbox)
```

Use `method="app_password"` for both successful and failed `mailbox_test_total` increments. Delete all OAuth service imports and `_perform_oauth_test`.

- [ ] **Step 7: Deepen the Mail fetching module around one production implementation**

Replace provider dispatch with this interface in `providers/__init__.py`:

```python
async def fetch_recent_emails(
    mailbox: TenantMailbox,
    window_minutes: int,
) -> list[EmailMessage]:
    if active_provider is not None:
        return await active_provider.fetch_recent(mailbox, window_minutes)
    return await fetch_gmail_app_password_emails(mailbox, window_minutes)
```

Change `StubProvider.fetch_recent` to the same arguments. Remove `AsyncSession`, `_google`, OAuth dispatch, unsupported-method errors, and `RevokedMailboxError` exports.

Change `fetch_with_retry` to:

```python
async def fetch_with_retry(
    mailbox: TenantMailbox,
    window_minutes: int,
) -> list[EmailMessage] | None:
    for attempt in range(_MAX_RETRIES):
        try:
            return await fetch_recent_emails(mailbox, window_minutes)
        except NonTransientProviderError:
            raise
        # retain the existing transient retry branches and backoff
```

Call it from `worker.py` as `emails = await fetch_with_retry(mailbox, window_minutes)`. Remove the `RevokedMailboxError` import/catch and delete `mailbox_revoked` and `permission_denied` from `_NON_TRANSIENT_SAFE_DETAIL`. In `_types.py`, delete `RevokedMailboxError` and document only `auth_failed` and `provider_config_error`.

- [ ] **Step 8: Delete OAuth runtime files and configuration**

Delete the four runtime files:

```bash
rm -rf backend/app/services/oauth_service
rm -f backend/app/services/mail_lookup_worker/providers/_google.py
```

Remove `MailboxOAuthService` from `backend/app/services/__init__.py`. Remove `google_oauth_client_id`, `google_oauth_client_secret`, and `google_oauth_redirect_uri` from `backend/app/core/config.py`. Remove the `GOOGLE_OAUTH_*` block from `backend/.env.example`.

- [ ] **Step 9: Finish fixture-only backend test updates**

Remove `auth_method=...` from every `TenantMailbox` fixture in:

```text
backend/tests/test_access_control_api.py
backend/tests/test_gmail_app_password_provider.py
backend/tests/test_mailbox_cleanup.py
backend/tests/test_mailbox_lookup_api.py
backend/tests/test_whatsapp_endpoint.py
backend/tests/test_whatsapp_external_admin_menu_guard.py
```

Use the final fixture shape consistently:

```python
TenantMailbox(
    tenant_id=tenant_id,
    mailbox_email="codes@tenant.com",
    status="connected",
    app_password_encrypted=encrypt_value("app-password"),
)
```

Tests that replace fetching with `StubProvider` may omit `app_password_encrypted`; tests that invoke the real Gmail provider must include it. Remove the OAuth start route from the parametrized Demo guardrail list in `backend/tests/test_demo_integration_gate.py`. In `backend/tests/test_mailbox_metrics.py`, change the sample provider label from `google` to `gmail` and remove `"oauth_"` from `allowed_prefixes`. 

- [ ] **Step 10: Run the backend Mailbox verification set**

Run:

```bash
cd backend
uv run pytest \
  tests/test_remove_mailbox_oauth_migration.py \
  tests/test_mailbox_api.py \
  tests/test_mailbox_persistence.py \
  tests/test_mailbox_cleanup.py \
  tests/test_mailbox_lookup_api.py \
  tests/test_mailbox_lookup_worker.py \
  tests/test_gmail_app_password_provider.py \
  tests/test_imap_service.py \
  tests/test_access_control_api.py \
  tests/test_whatsapp_endpoint.py \
  tests/test_whatsapp_external_admin_menu_guard.py \
  tests/test_demo_integration_gate.py \
  tests/test_mailbox_metrics.py \
  -v
uv run ruff check app tests
uv run ruff format --check app tests
```

Expected: all selected tests PASS and Ruff reports no issues.

- [ ] **Step 11: Commit the backend runtime removal**

```bash
git add backend/.env.example backend/app backend/tests
git commit -m "refactor(mailbox): remove Google OAuth runtime"
```

---

### Task 3: Remove the verification-only TrackPal Demo Code Service

**Files:**
- Delete: `backend/app/services/mail_code_extractor/catalog/trackpal_demo.py`
- Modify: `backend/app/services/mail_code_extractor/catalog/__init__.py:1-22`
- Modify: `backend/app/schemas/code_services.py:8-22`
- Modify: `backend/app/services/whatsapp_tenant_console_service/constants.py:224-235`
- Modify: `backend/app/services/whatsapp_tenant_console_service/codigo_flow.py:25-42`
- Modify: `backend/tests/test_mail_code_extractor.py`
- Modify: `backend/tests/test_code_services.py:104-120`
- Modify: `backend/tests/test_tenant_console_service.py:2035-2070`
- Delete: `backend/tests/test_trackpal_demo_verification.py`
- Delete: `docs/verification/trackpal-demo-code-email.html`

**Interfaces:**
- Consumes: database deletion from Task 1.
- Produces: exactly six supported Code Service keys: `disney`, `hbo_max`, `netflix`, `prime_video`, `spotify`, and `universal_plus`.

- [ ] **Step 1: Change tests to reject the removed service**

In `backend/tests/test_mail_code_extractor.py`, delete the TrackPal Demo constant, subject tests, extraction class, and parametrized examples. Replace the catalog assertion with:

```python
def test_catalog_has_expected_services(self):
    assert set(CATALOG_V1) == {
        "disney",
        "hbo_max",
        "netflix",
        "prime_video",
        "spotify",
        "universal_plus",
    }
    assert "trackpal_demo" not in CATALOG_V1
```

In `backend/tests/test_code_services.py`, import `TenantCodeServiceUpdateRequest`, remove the TrackPal Demo label assertion, and add a validation regression:

```python
from app.schemas.code_services import (
    VALID_SERVICE_KEYS,
    TenantCodeServiceUpdateRequest,
)


def test_removed_trackpal_demo_key_is_invalid() -> None:
    request = TenantCodeServiceUpdateRequest(service_keys=["trackpal_demo"])
    with pytest.raises(ValueError, match="trackpal_demo"):
        request.validate_keys()
```

Update the WhatsApp mapping expectation in `backend/tests/test_tenant_console_service.py`:

```python
expected_keys = [
    "disney",
    "hbo_max",
    "netflix",
    "prime_video",
    "spotify",
    "universal_plus",
]
```

- [ ] **Step 2: Run the focused service tests and verify they fail**

Run:

```bash
cd backend
uv run pytest \
  tests/test_mail_code_extractor.py \
  tests/test_code_services.py \
  tests/test_tenant_console_service.py::TestCodigoFlow::test_codigo_index_to_service_key_mapping \
  -v
```

Expected: FAIL because `trackpal_demo` remains registered and accepted.

- [ ] **Step 3: Remove the service from every active catalog**

Delete the extractor and verification files:

```bash
rm -f backend/app/services/mail_code_extractor/catalog/trackpal_demo.py
rm -f backend/tests/test_trackpal_demo_verification.py
rm -f docs/verification/trackpal-demo-code-email.html
```

Remove `TRACKPAL_DEMO_ENTRY` import and mapping from `catalog/__init__.py`. Remove the `trackpal_demo` entry from `SUPPORTED_CODE_SERVICES`, `STREAMING_SERVICE_KEYS`, and `_CODIGO_SERVICE_LABELS`. The final key list must remain alphabetical by visible label:

```python
STREAMING_SERVICE_KEYS: list[str] = [
    "disney",
    "hbo_max",
    "netflix",
    "prime_video",
    "spotify",
    "universal_plus",
]
```

- [ ] **Step 4: Run Code Service verification**

Run:

```bash
cd backend
uv run pytest tests/test_mail_code_extractor.py tests/test_code_services.py tests/test_tenant_console_service.py -v
uv run ruff check app/services/mail_code_extractor app/schemas/code_services.py app/services/whatsapp_tenant_console_service tests/test_mail_code_extractor.py tests/test_code_services.py tests/test_tenant_console_service.py
```

Expected: all tests PASS and Ruff reports no issues.

- [ ] **Step 5: Commit the verification service removal**

```bash
git add backend/app/services/mail_code_extractor backend/app/schemas/code_services.py backend/app/services/whatsapp_tenant_console_service backend/tests docs/verification/trackpal-demo-code-email.html
git commit -m "refactor(code-services): remove OAuth verification service"
```

---

### Task 4: Simplify the frontend to the sole app-password path

**Files:**
- Modify: `frontend/src/features/admin/services/settings-api.ts:29-48,112-140`
- Modify: `frontend/src/features/admin/components/gmail-setup-assistant.tsx:1-351`
- Modify: `frontend/src/features/admin/components/mailbox-section.tsx:1-350`
- Modify: `frontend/src/features/demo/services/demo-settings.ts:217-231`
- Modify: `frontend/src/features/admin/components/__tests__/gmail-setup-assistant.spec.tsx`
- Modify: `frontend/src/features/admin/components/__tests__/mailbox-section.spec.tsx`
- Modify: `backend/app/core/i18n/catalogs_en_frontend.py:470-526`
- Modify: `backend/app/core/i18n/catalogs_es_frontend.py:470-526`
- Modify: `frontend/.env.example:1-9`
- Delete: `frontend/src/features/admin/mailbox-config.ts`

**Interfaces:**
- Consumes: backend `MailboxResponse` from Task 2.
- Produces: `Mailbox` without `auth_method`; `GmailSetupAssistantProps` with only `onConnect(payload) -> Promise<boolean>`; no OAuth API call or feature gate.

- [ ] **Step 1: Rewrite Gmail Setup Assistant tests for one path**

Remove release-gate and OAuth consent tests from `gmail-setup-assistant.spec.tsx`. Render the final interface:

```tsx
render(<GmailSetupAssistant onConnect={connect} />);

expect(
  screen.getByText("frontend.mailbox.app_password_step_title"),
).toBeInTheDocument();
expect(
  screen.getByRole("link", { name: "frontend.mailbox.open_google" }),
).toHaveAttribute("href", "https://myaccount.google.com/apppasswords");
expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
expect(
  screen.queryByText("frontend.mailbox.use_google_connection"),
).not.toBeInTheDocument();
```

Retain tests for instruction-to-credentials navigation, payload submission, clearing only the failed password, contextual Help, and disabled private Help.

- [ ] **Step 2: Rewrite MailboxSection tests without OAuth browser primitives**

Delete `mockStartGoogleOAuth`, `BroadcastChannelStub`, `window.open`, flag tests, OAuth Mailbox fixtures, and method-label assertions. Use this connected shape:

```tsx
useSettingsStore.setState({
  mailbox: {
    id: "m1",
    tenant_id: "t1",
    mailbox_email: "admin@gmail.com",
    status: "connected",
    last_connection_test_at: null,
    last_connection_error: null,
    created_at: "2025-01-01T00:00:00Z",
    updated_at: "2025-01-01T00:00:00Z",
  },
  mailboxLoaded: true,
});

render(<MailboxSection />);
expect(screen.getByText("admin@gmail.com")).toBeInTheDocument();
expect(screen.getByText("frontend.mailbox.status_connected")).toBeInTheDocument();
expect(screen.queryByText("frontend.mailbox.method_google_connection")).not.toBeInTheDocument();
```

Retain the safe unknown-error test and the unconfigured assistant test.

- [ ] **Step 3: Run focused frontend tests and verify they fail**

Run:

```bash
cd frontend
npm test -- --run \
  src/features/admin/components/__tests__/gmail-setup-assistant.spec.tsx \
  src/features/admin/components/__tests__/mailbox-section.spec.tsx
```

Expected: FAIL because the components still require OAuth props, render method selection, and consume `auth_method`.

- [ ] **Step 4: Simplify frontend types and demo data**

In `settings-api.ts`, delete `MailboxAuthMethod`, remove `auth_method` from `Mailbox`, and delete `startGoogleOAuth()`:

```ts
export interface Mailbox {
  id: string;
  tenant_id: string;
  mailbox_email: string;
  status: string;
  last_connection_test_at: string | null;
  last_connection_error: string | null;
  created_at: string;
  updated_at: string;
}
```

Remove `auth_method: "demo"` from `fixedMailbox()` in `frontend/src/features/demo/services/demo-settings.ts`.

- [ ] **Step 5: Simplify GmailSetupAssistant to two app-password steps**

Use this public interface and state:

```tsx
export interface GmailSetupAssistantProps {
  onConnect(payload: GmailAppPasswordConnect): Promise<boolean>;
}

type Step = "instructions" | "credentials";

export function GmailSetupAssistant({ onConnect }: GmailSetupAssistantProps) {
  const [step, setStep] = useState<Step>("instructions");
  // retain email, appPassword, showPassword, submitting, and privateHelpEnabled
}
```

Delete `MethodSelector`, `OAuthConsent`, `oauthConnectEnabled`, `onStartOAuth`, OAuth consent/submitting state, and return-to-selector logic. `AppPasswordInstructions` needs only `privateHelpEnabled` and `onContinue`; `CredentialsForm` retains its Back button to return to instructions.

- [ ] **Step 6: Remove OAuth behavior from MailboxSection**

Remove `startGoogleOAuth`, `isGmailOAuthConnectEnabled`, `methodLabel`, the `BroadcastChannel` effect, and `handleOAuthStart`. Do not render a method label under the Mailbox email. The unconfigured state becomes:

```tsx
{!isDemo && <GmailSetupAssistant onConnect={onConnect} />}
```

Remove OAuth props from `MailboxConfiguration` and its call site. Keep loading, app-password connect, test, disconnect, Demo hiding, and safe toast behavior unchanged.

- [ ] **Step 7: Remove OAuth environment and translation surface**

Delete `frontend/src/features/admin/mailbox-config.ts` and remove the OAuth block from `frontend/.env.example`.

From both frontend i18n catalogs, remove these keys:

```text
frontend.mailbox.method
frontend.mailbox.status_revoked
frontend.mailbox.oauth_consent_title
frontend.mailbox.oauth_consent_data
frontend.mailbox.oauth_consent_transfer
frontend.mailbox.oauth_consent_storage
frontend.mailbox.oauth_consent_checkbox
frontend.mailbox.oauth_consent_privacy
frontend.mailbox.continue_google
frontend.mailbox.use_google_connection
frontend.mailbox.method_google_connection
frontend.mailbox.method_app_password
frontend.mailbox.setup_method_title
frontend.mailbox.oauth_started
frontend.mailbox.oauth_connected
frontend.mailbox.error_oauth
frontend.mailbox.oauth_reconnect
```

Retain the app-password, status connected/disconnected/error, test, disconnect, and safe error keys.

- [ ] **Step 8: Run frontend verification**

Run:

```bash
cd frontend
npm test -- --run \
  src/features/admin/components/__tests__/gmail-setup-assistant.spec.tsx \
  src/features/admin/components/__tests__/mailbox-section.spec.tsx
npm run build
npm run lint
```

Expected: focused tests PASS, TypeScript/Vite build PASS, and ESLint PASS.

- [ ] **Step 9: Commit the frontend simplification**

```bash
git add frontend backend/app/core/i18n/catalogs_en_frontend.py backend/app/core/i18n/catalogs_es_frontend.py
git commit -m "refactor(mailbox): keep app-password UI only"
```

---

### Task 5: Update Help, current documentation, and historical artifacts

**Files:**
- Modify: `backend/help/en/tenant-admin/mailbox.md`
- Modify: `backend/help/es/tenant-admin/mailbox.md`
- Modify: `backend/help/en/tenant-admin/data-export.md`
- Modify: `backend/help/es/tenant-admin/data-export.md`
- Modify: `backend/help/en/tenant-admin/delete-account.md`
- Modify: `backend/help/es/tenant-admin/delete-account.md`
- Modify: `backend/tests/test_help_contract.py:444-493`
- Modify generated: `backend/app/help/artifact.json`
- Modify: `docs/SUMMARY.md`
- Modify: `docs/architecture/api-layer.md`
- Modify: `docs/architecture/code-services.md`
- Modify: `docs/architecture/database-schema.md`
- Modify: `docs/architecture/mailbox-ingestion.md`
- Modify: `docs/architecture/tenant-data-export.md`
- Modify: `docs/architecture/tenant-deletion.md`
- Modify: `docs/codebase/backend-structure.md`
- Modify: `docs/codebase/frontend-components.md`
- Modify: `docs/project-pdr/business-rules.md`
- Modify: `docs/project-pdr/product-goals.md`
- Modify: `docs/project-pdr/user-help-requirements.md`
- Modify: `docs/releases/offboarding-release.md`
- Delete: `docs/verification/google-oauth-demo.md`
- Delete: `docs/superpowers/plans/2026-07-30-gmail-only-mailbox-connection.md`
- Delete: `docs/superpowers/specs/2026-07-30-gmail-only-mailbox-connection-design.md`

**Interfaces:**
- Consumes: final backend/frontend behavior from Tasks 2-4.
- Produces: bilingual Help and current project documentation that describe only Gmail App Password Connection and six supported Code Services.

- [ ] **Step 1: Change Help contract tests to forbid the retired path**

Replace `test_mailbox_help_mentions_google_connection_is_conditional` with:

```python
def test_mailbox_help_describes_only_app_password_connection() -> None:
    artifact = compile_help(SOURCE_DIR)
    topics_by_locale = {
        locale: {topic["id"]: topic for topic in artifact["topics"][locale]}
        for locale in ("en", "es")
    }

    for locale in ("en", "es"):
        body = topics_by_locale[locale]["tenant-admin.mailbox"]["body"]
        assert "myaccount.google.com/apppasswords" in body
        assert "OAuth" not in body
        assert "Google Connection" not in body
        assert "Conexión de Google" not in body
```

Add explicit export/deletion assertions:

```python
def test_mailbox_secret_help_copy_is_app_password_only() -> None:
    artifact = compile_help(SOURCE_DIR)
    topics = {
        locale: {topic["id"]: topic for topic in artifact["topics"][locale]}
        for locale in ("en", "es")
    }

    export_en = topics["en"]["tenant-admin.data-export"]["body"]
    export_es = topics["es"]["tenant-admin.data-export"]["body"]
    delete_en = topics["en"]["tenant-admin.delete-account"]["body"]
    delete_es = topics["es"]["tenant-admin.delete-account"]["body"]

    assert "Mailbox login credentials or app passwords" in export_en
    assert "Credenciales de inicio de sesión del correo o contraseñas de aplicación" in export_es
    assert "Google app password" in delete_en
    assert "Contraseña de aplicación de Google" in delete_es
    for body in (export_en, export_es, delete_en, delete_es):
        assert "OAuth" not in body
```

- [ ] **Step 2: Run Help tests and verify the old copy fails**

Run:

```bash
cd backend
uv run pytest tests/test_help_contract.py -v
```

Expected: FAIL because bilingual Mailbox Help still contains the Google Connection section and the checked-in artifact still matches old sources.

- [ ] **Step 3: Update bilingual Help sources**

Delete the entire `Google Connection (OAuth)` / `Conexión de Google (OAuth)` sections from the Mailbox topics.

Use these exclusion phrases in data export:

```markdown
- Mailbox login credentials or app passwords
```

```markdown
- Credenciales de inicio de sesión del correo o contraseñas de aplicación
```

Replace provider-grant deletion language with app-password ownership language:

```markdown
- **Google app password**: TrackPal deletes its encrypted local copy. Revoke the generated app password separately from your Google Account if you no longer need it.
```

```markdown
- **Contraseña de aplicación de Google**: TrackPal elimina su copia local cifrada. Revoca por separado la contraseña de aplicación generada desde tu Cuenta de Google si ya no la necesitas.
```

- [ ] **Step 4: Regenerate and verify the Help artifact**

Run:

```bash
cd backend
uv run python scripts/compile_help.py
uv run pytest tests/test_help_contract.py -v
```

Expected: compiler prints `Compiled private Help artifact`; all Help contract tests PASS.

- [ ] **Step 5: Update current architecture and product documentation**

Apply these exact semantic changes:

```text
docs/SUMMARY.md
- Describe Mailbox Ingestion as Gmail app-password-only.
- Remove the Google OAuth Demo verification entry and empty Verification Guides section.

docs/architecture/mailbox-ingestion.md
- Backend API responsibility: Mailbox CRUD, app-password validation, lookup create/poll.
- Data model: no auth_method or oauth_* fields; statuses disconnected/connected/error.
- Delete the Google OAuth Connection section, OAuth routes, OAuth metrics, OAuth security bullets, and OAuth reconnect runbook branch.
- Worker fetches through the fixed Gmail app-password implementation.

docs/architecture/api-layer.md
- Keep GET/PUT/test/disconnect Mailbox endpoints only.

docs/architecture/database-schema.md
- Remove auth_method and every oauth_* row from tenant_mailboxes.

docs/architecture/code-services.md
- Remove trackpal_demo from the supported-service table and delete its verification note.

docs/architecture/tenant-data-export.md
- Exclude Mailbox credentials/app passwords without OAuth-token language.

docs/architecture/tenant-deletion.md
- Describe encrypted app-password deletion and owner-managed Google revocation only.

docs/codebase/backend-structure.md
- Remove oauth_service and _google provider entries; describe one Gmail app-password fetch implementation.

docs/codebase/frontend-components.md
- Describe the two-step app-password assistant without an optional connection method.

docs/project-pdr/business-rules.md
- Mailbox has one connection mechanism and no revoked OAuth state.
- Demo guardrails occur before persistence, queueing, or external-client calls.

docs/project-pdr/product-goals.md
- Mailbox ingestion uses Gmail app passwords; remove OAuth/IMAP dual-method and grant-revocation language.

docs/project-pdr/user-help-requirements.md
- Mailbox Help covers Gmail app password, test, and disconnect.

docs/releases/offboarding-release.md
- Verify encrypted app-password deletion rather than OAuth-token deletion.
```

- [ ] **Step 6: Delete retired historical artifacts**

Run:

```bash
rm -f docs/verification/google-oauth-demo.md
rm -f docs/superpowers/plans/2026-07-30-gmail-only-mailbox-connection.md
rm -f docs/superpowers/specs/2026-07-30-gmail-only-mailbox-connection-design.md
```

Do not delete `docs/superpowers/specs/2026-07-31-remove-google-oauth-design.md` or this implementation plan; they are the approved removal record.

- [ ] **Step 7: Verify documentation has no active support claims**

Run from the repository root:

```bash
git grep -n -i -E 'Google OAuth|OAuth tokens|OAuth grant|oauth/google|VITE_GMAIL_OAUTH|GOOGLE_OAUTH' -- \
  docs backend/help frontend/.env.example backend/.env.example \
  ':!docs/superpowers/specs/2026-07-31-remove-google-oauth-design.md' \
  ':!docs/superpowers/plans/2026-07-31-remove-google-oauth.md'
```

Expected: no matches.

Run:

```bash
git grep -n trackpal_demo -- \
  docs backend/help \
  ':!docs/superpowers/specs/2026-07-31-remove-google-oauth-design.md' \
  ':!docs/superpowers/plans/2026-07-31-remove-google-oauth.md'
```

Expected: no matches.

- [ ] **Step 8: Commit documentation and Help**

```bash
git add backend/help backend/app/help/artifact.json backend/tests/test_help_contract.py docs
git commit -m "docs(mailbox): document app-password-only ingestion"
```

---

### Task 6: Run the complete removal verification

**Files:**
- Verify only; modify a file only when a command exposes a concrete defect caused by Tasks 1-5.

**Interfaces:**
- Consumes: all previous task outputs.
- Produces: evidence that the repository builds, tests, migrates, documents, and scans as app-password-only.

- [ ] **Step 1: Run the full backend suite**

Run with a 600-second timeout:

```bash
cd backend
uv run pytest
```

Expected: full suite PASS with no OAuth service import, missing model-field, removed Code Service, or Help artifact failures.

- [ ] **Step 2: Run backend formatting and static checks**

```bash
cd backend
uv run ruff check .
uv run ruff format --check .
uv run alembic heads
```

Expected: Ruff PASS and Alembic reports only `e020fe74cac0 (head)`.

- [ ] **Step 3: Run the full frontend suite and production checks**

```bash
cd frontend
npm test -- --run
npm run build
npm run lint
```

Expected: all Vitest suites PASS, strict TypeScript/Vite build PASS, and ESLint PASS.

- [ ] **Step 4: Recompile Help and prove the artifact is stable**

```bash
cd backend
uv run python scripts/compile_help.py
git diff --exit-code -- app/help/artifact.json
uv run pytest tests/test_help_contract.py -v
```

Expected: recompilation creates no diff and Help tests PASS.

- [ ] **Step 5: Scan active code and configuration for removed surfaces**

Run from the repository root:

```bash
git grep -n -i -E 'google_oauth|gmail_oauth|mailbox_oauth|oauth/google|gmail\.googleapis\.com' -- \
  backend/app backend/tests backend/.env.example frontend/src frontend/.env.example \
  ':!backend/tests/test_mailbox_api.py'
```

Expected: no matches. `backend/tests/test_mailbox_api.py` is excluded only because it intentionally asserts the removed routes return 404.

Run:

```bash
git grep -n -E 'auth_method|oauth_provider_|oauth_access_token|oauth_refresh_token|oauth_token_expires_at|oauth_scope' -- \
  backend/app frontend/src
```

Expected: no matches.

Run:

```bash
git grep -n trackpal_demo -- \
  backend/app backend/tests frontend/src docs \
  ':!docs/superpowers/specs/2026-07-31-remove-google-oauth-design.md' \
  ':!docs/superpowers/plans/2026-07-31-remove-google-oauth.md'
```

Expected: no matches. Historical and destructive Alembic migrations are intentionally outside this scan.

- [ ] **Step 6: Inspect the final repository diff and status**

```bash
git status --short
git diff --check
git log -6 --oneline --decorate
```

Expected: no uncommitted files, no whitespace errors, and one focused commit per completed task after the design/spec commits.

- [ ] **Step 7: Commit only concrete verification fixes, if any**

If Steps 1-6 required corrections, stage only those corrections and run:

```bash
git commit -m "fix(mailbox): complete OAuth removal verification"
```

If no correction was required, do not create an empty commit.
