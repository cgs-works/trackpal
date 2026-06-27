# TPL-12 Silent External Admin Menu Guard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop cross-tenant `/menu` bot loops, keep Client Context Shortcut private to the sending admin, and preserve normal code/client flows.

**Architecture:** Keep the urgent fix small and local to TrackPal. The backend becomes the source of truth for deciding when an inbound exact `/menu` came from another active tenant/admin and should be silenced; the existing n8n workflow keeps handling `no_reply + status="closed" + close_jid` without structural rewiring. In parallel, harden `from_me` admin resolution in backend so private shortcut replies keep using the tenant admin JID even when n8n parsed the outgoing event ambiguously, and extend the Parse Input filter to ignore the known not-registered bot echoes that create ping-pong loops.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy async, pytest, httpx AsyncClient, n8n workflow JSON, JavaScript Code nodes, Ruff, project docs in `docs/architecture/`.

---

## File map

- `backend/app/repositories/tenants_repository.py`
  - Add a focused cross-tenant lookup helper: `get_active_by_whatsapp_identity(...)`.
  - Keep phone matching variant-based (`digits` + `+digits`) and LID matching exact.

- `backend/app/api/v1/endpoints/integrations/console.py`
  - Add `_should_silence_external_admin_menu(...)` near the routing helpers.
  - Call it in the unregistered known-tenant branch before resuming/starting unauthenticated `codigo` flow.
  - Harden `_handle_from_me_routing(...)` so authoritative admin identity comes from the resolved tenant first, then fallback payloads.
  - Replace raw `admin_jid` uses with a resolved canonical admin JID where private replies are required.

- `backend/tests/test_tenants_repository.py` **(new)**
  - Focused regression tests for the new tenant identity helper.

- `backend/tests/test_whatsapp_external_admin_menu_guard.py` **(new)**
  - Focused endpoint tests for:
    - silent external admin `/menu`
    - preserved `code` flow
    - preserved active-client behavior
    - corrected `reply_to` / `close_jid` fallback for `from_me` shortcut replies

- `backend/tests/test_n8n_whatsapp_workflow.py`
  - Extend workflow-export regression tests to lock the Parse Input not-registered echo filter.

- `n8n/TrackPal WhatsApp Bot.json`
  - Update only the `Parse input` Code node JS to ignore the Spanish and English not-registered bot echoes.
  - Do not rewire the workflow graph.

- `docs/architecture/whatsapp-console-flow.md`
  - Document the silent external-admin `/menu` backend branch and the authoritative admin-phone fallback in `from_me` routing.

- `docs/architecture/n8n-workflow.md`
  - Document the Parse Input not-registered echo filter and confirm the existing `IF no reply -> Check close session -> Close session` path handles the silent close contract.

- `docs/architecture/evolution-integration.md`
  - Add a brief note that deployed `fromMe=true` payloads are expected to include `adminJid=instance.Jid`, and rollout must verify that assumption.

## Task 1: Lock the tenant-identity lookup contract  [x]

**Skills to read before starting:**
- `superpowers:test-driven-development`
- `python-pro`
- `fastapi-expert`

**Files:**
- Create: `backend/tests/test_tenants_repository.py`
- Modify: `backend/app/repositories/tenants_repository.py`
- Test: `backend/tests/test_tenants_repository.py`

- [x] **Step 1: Write the failing repository regression tests**

Create `backend/tests/test_tenants_repository.py` with this exact content:

```python
import pytest

from app.models import Tenant, User
from app.repositories import tenants_repository

pytestmark = pytest.mark.asyncio


async def _create_tenant(
    db_session,
    *,
    username: str,
    client_prefix: str,
    name: str,
    phone: str | None,
    whatsapp_lid: str | None = None,
    is_active: bool = True,
):
    user = User(username=username, password_hash="x", role="tenant")
    db_session.add(user)
    await db_session.flush()

    tenant = Tenant(
        owner_user_id=user.id,
        client_prefix=client_prefix,
        name=name,
        whatsapp_phone=phone,
        whatsapp_lid=whatsapp_lid,
        is_active=is_active,
    )
    db_session.add(tenant)
    await db_session.commit()
    return tenant


async def test_get_active_by_whatsapp_identity_matches_normalized_phone(db_session):
    tenant = await _create_tenant(
        db_session,
        username="tenant_phone_lookup",
        client_prefix="tp01",
        name="Tenant Phone Lookup",
        phone="+584243106642",
    )

    found = await tenants_repository.get_active_by_whatsapp_identity(
        db_session,
        phone_digits="584243106642",
    )

    assert found is not None
    assert found.id == tenant.id


async def test_get_active_by_whatsapp_identity_matches_whatsapp_lid(db_session):
    tenant = await _create_tenant(
        db_session,
        username="tenant_lid_lookup",
        client_prefix="tl01",
        name="Tenant LID Lookup",
        phone=None,
        whatsapp_lid="77988435632309@lid",
    )

    found = await tenants_repository.get_active_by_whatsapp_identity(
        db_session,
        whatsapp_lid="77988435632309@lid",
    )

    assert found is not None
    assert found.id == tenant.id


async def test_get_active_by_whatsapp_identity_ignores_inactive_tenant(db_session):
    await _create_tenant(
        db_session,
        username="tenant_inactive_lookup",
        client_prefix="ti01",
        name="Tenant Inactive Lookup",
        phone="+584243106643",
        is_active=False,
    )

    found = await tenants_repository.get_active_by_whatsapp_identity(
        db_session,
        phone_digits="584243106643",
    )

    assert found is None


async def test_get_active_by_whatsapp_identity_returns_none_without_identity(db_session):
    found = await tenants_repository.get_active_by_whatsapp_identity(
        db_session,
        phone_digits=None,
        whatsapp_lid=None,
    )

    assert found is None
```

- [x] **Step 2: Run the new repository tests and verify they fail**

Run:

```bash
cd backend && uv run pytest tests/test_tenants_repository.py -q
```

Expected: FAIL with `AttributeError` because `tenants_repository.get_active_by_whatsapp_identity` does not exist yet.

- [x] **Step 3: Implement the minimal repository helper**

In `backend/app/repositories/tenants_repository.py`, make these edits:

1. Extend imports:

```python
from sqlalchemy import func, or_, select
```

```python
from app.core.phone import normalize_phone
```

2. Add this helper above `update_tenant_lid(...)`:

```python
async def get_active_by_whatsapp_identity(
    db: AsyncSession,
    *,
    phone_digits: str | None = None,
    whatsapp_lid: str | None = None,
) -> Tenant | None:
    """Get an active tenant by WhatsApp phone or LID identity.

    Phone matching accepts both canonical digits-only values and legacy
    `+`-prefixed values stored in the database.
    """
    phone_norm = normalize_phone(phone_digits) if phone_digits else None
    lid = (whatsapp_lid or "").strip() or None

    if not phone_norm and not lid:
        return None

    stmt = select(Tenant).options(selectinload(Tenant.owner)).where(Tenant.is_active)

    phone_variants = [phone_norm, f"+{phone_norm}"] if phone_norm else []
    if phone_variants and lid:
        stmt = stmt.where(
            or_(
                Tenant.whatsapp_phone.in_(phone_variants),
                Tenant.whatsapp_lid == lid,
            )
        )
    elif phone_variants:
        stmt = stmt.where(Tenant.whatsapp_phone.in_(phone_variants))
    else:
        stmt = stmt.where(Tenant.whatsapp_lid == lid)

    result = await db.execute(stmt)
    return result.scalar_one_or_none()
```

3. Add the function to `__all__`:

```python
    "get_active_by_whatsapp_identity",
```

- [x] **Step 4: Re-run the repository tests and lint the file**

Run:

```bash
cd backend && uv run pytest tests/test_tenants_repository.py -q
cd backend && uv run ruff check app/repositories/tenants_repository.py tests/test_tenants_repository.py
```

Expected:
- `4 passed`
- Ruff exits with status 0 and no findings.

- [x] **Step 5: Commit the repository helper**

```bash
git add backend/app/repositories/tenants_repository.py backend/tests/test_tenants_repository.py
git commit -m "feat: add tenant whatsapp identity lookup"
```

## Task 2: Lock and implement backend routing for silent external admin `/menu`  [x]

**Skills to read before starting:**
- `superpowers:test-driven-development`
- `python-pro`
- `fastapi-expert`
- `systematic-debugging` **only if the new endpoint tests fail for a reason you did not expect**

**Files:**
- Create: `backend/tests/test_whatsapp_external_admin_menu_guard.py`
- Modify: `backend/app/api/v1/endpoints/integrations/console.py`
- Test: `backend/tests/test_whatsapp_external_admin_menu_guard.py`
- Regression: `backend/tests/test_whatsapp_endpoint.py`

- [x] **Step 1: Write focused endpoint regression tests**

Create `backend/tests/test_whatsapp_external_admin_menu_guard.py` with this exact content:

```python
from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.models import Client, CodeServiceGlobalStatus, Tenant, TenantCodeServiceSelection, TenantMailbox, User

pytestmark = pytest.mark.asyncio

ENDPOINT = "/api/v1/integrations/n8n/console"
TEST_INSTANCE = "test-tenant-instance"


class _FakeRedis:
    def __init__(self) -> None:
        self._store: dict[str, str] = {}
        self._ttls: dict[str, int] = {}

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None, keepttl: bool = False) -> None:
        self._store[key] = value
        if ex is not None:
            self._ttls[key] = ex
        elif not keepttl:
            self._ttls.pop(key, None)

    async def expire(self, key: str, time: int) -> int:
        if key in self._store:
            self._ttls[key] = time
            return 1
        return 0

    async def delete(self, key: str) -> int:
        self._ttls.pop(key, None)
        return 1 if self._store.pop(key, None) is not None else 0

    async def lpush(self, key: str, value: str) -> int:
        self._store[key] = value
        return 1


class _FakeManager:
    def __init__(self, *, used_backup: bool = False, fail_on_execute: bool = False) -> None:
        from app.core.redis_client import RedisUnavailableError

        self._redis = _FakeRedis()
        self._used_backup = used_backup
        self._fail_on_execute = fail_on_execute
        self._RedisUnavailableError = RedisUnavailableError

    @property
    def used_backup(self) -> bool:
        return self._used_backup

    async def execute(self, operation_name: str, async_callable):
        if self._fail_on_execute:
            raise self._RedisUnavailableError("Both Redis stores unavailable")
        return await async_callable(self._redis)


async def _setup_tenant_with_instance(db_session, active_tenant_user) -> Tenant:
    result = await db_session.execute(
        select(Tenant).where(Tenant.owner_user_id == active_tenant_user.id)
    )
    tenant = result.scalar_one_or_none()
    assert tenant is not None
    tenant.evolution_instance_name = TEST_INSTANCE
    tenant.locale = "es"
    await db_session.commit()
    return tenant


async def _setup_tenant_for_codigo(db_session, active_tenant_user) -> Tenant:
    tenant = await _setup_tenant_with_instance(db_session, active_tenant_user)

    db_session.add(
        TenantMailbox(
            tenant_id=tenant.id,
            mailbox_email="tech@example.com",
            provider="imap",
            auth_method="password",
            status="connected",
        )
    )
    db_session.add(CodeServiceGlobalStatus(service_key="netflix", is_active=True))
    db_session.add(
        TenantCodeServiceSelection(tenant_id=tenant.id, service_key="netflix")
    )
    await db_session.commit()
    return tenant


async def _create_other_active_tenant(
    db_session,
    *,
    username: str = "other-tenant",
    client_prefix: str = "tnb01",
    phone: str = "+12015550003",
    whatsapp_lid: str | None = None,
) -> Tenant:
    other_user = User(username=username, password_hash="x", role="tenant")
    db_session.add(other_user)
    await db_session.flush()

    other_tenant = Tenant(
        owner_user_id=other_user.id,
        client_prefix=client_prefix,
        name="Other Active Tenant",
        whatsapp_phone=phone,
        whatsapp_lid=whatsapp_lid,
        is_active=True,
        evolution_instance_name="other-instance",
    )
    db_session.add(other_tenant)
    await db_session.commit()
    return other_tenant


async def test_external_tenant_admin_menu_is_silenced_and_closed(
    client, db_session, active_tenant_user
):
    await _setup_tenant_with_instance(db_session, active_tenant_user)
    await _create_other_active_tenant(db_session)

    fake_mgr = _FakeManager(used_backup=False)
    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={
                "phone": "+12015550003",
                "message": "/menu",
                "instance": TEST_INSTANCE,
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "reply": "",
        "no_reply": True,
        "status": "closed",
        "close_jid": "12015550003@s.whatsapp.net",
    }


async def test_external_tenant_admin_code_still_reaches_unauthenticated_codigo(
    client, db_session, active_tenant_user
):
    await _setup_tenant_for_codigo(db_session, active_tenant_user)
    await _create_other_active_tenant(db_session)

    fake_mgr = _FakeManager(used_backup=False)
    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={
                "phone": "+12015550003",
                "message": "code",
                "instance": TEST_INSTANCE,
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )

    assert response.status_code == 200
    body = response.json()
    assert body.get("no_reply") is not True
    assert "Netflix" in body["reply"]


async def test_external_tenant_admin_menu_is_not_silenced_when_sender_is_active_client(
    client, db_session, active_tenant_user
):
    tenant = await _setup_tenant_with_instance(db_session, active_tenant_user)
    await _create_other_active_tenant(db_session)

    client_user = User(username="dual-role-client", password_hash="x", role="client")
    db_session.add(client_user)
    await db_session.flush()
    db_session.add(
        Client(
            tenant_id=tenant.id,
            owner_user_id=client_user.id,
            full_name="Dual Role Client",
            username=f"{tenant.client_prefix}_dualrole",
            phone="+12015550003",
            is_active=True,
        )
    )
    await db_session.commit()

    fake_mgr = _FakeManager(used_backup=False)
    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={
                "phone": "+12015550003",
                "message": "/menu",
                "instance": TEST_INSTANCE,
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )

    assert response.status_code == 200
    body = response.json()
    assert body.get("no_reply") is not True
    assert body["reply"]
    assert "no tienes una cuenta registrada" not in body["reply"].lower()


async def test_from_me_menu_uses_tenant_owner_fallback_for_reply_to_when_admin_payload_is_ambiguous(
    client, db_session, active_tenant_user
):
    tenant = await _setup_tenant_with_instance(db_session, active_tenant_user)

    fake_mgr = _FakeManager(used_backup=False)
    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={
                "phone": "+12015559999",
                "message": "/menu",
                "instance": TEST_INSTANCE,
                "from_me": True,
                "admin_phone": "+12015559999",
                "target_phone": "+12015559999",
                "target_jid": "12015559999@s.whatsapp.net",
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["reply_to"] == "12015550002@s.whatsapp.net"
    assert body["close_jid"] == "12015550002@s.whatsapp.net"
    assert body["reply"]
    assert "gesti" in body["reply"].lower() or "client management" in body["reply"].lower()
```

- [x] **Step 2: Run the new endpoint tests and verify they fail for the right reason**

Run:

```bash
cd backend && uv run pytest tests/test_whatsapp_external_admin_menu_guard.py -q
```

Expected: FAIL because:
- `/menu` from another tenant currently returns `wa.client.not_registered` instead of a silent closed response.
- the ambiguous `from_me` shortcut response still lacks the canonical admin `reply_to` / `close_jid` fallback.

- [x] **Step 3: Implement the backend guard and authoritative admin fallback**

In `backend/app/api/v1/endpoints/integrations/console.py`, make the following edits.

1. Add this helper after `_jid_phone(...)`:

```python
async def _should_silence_external_admin_menu(
    *,
    tenant: Tenant,
    phone_digits: str | None,
    sender_lid: str | None,
    message: str,
    db: AsyncSession,
) -> bool:
    if message.strip() != "/menu":
        return False

    if phone_digits and tenant.whatsapp_phone:
        tenant_phone = normalize_phone(tenant.whatsapp_phone)
        if tenant_phone and tenant_phone == phone_digits:
            return False

    tenant_lid = getattr(tenant, "whatsapp_lid", None)
    if sender_lid and tenant_lid and sender_lid == tenant_lid:
        return False

    try:
        matched_tenant = await tenants_repository.get_active_by_whatsapp_identity(
            db,
            phone_digits=phone_digits,
            whatsapp_lid=sender_lid,
        )
    except Exception:
        logger.exception(
            "External admin /menu lookup failed for tenant=%s phone=%s lid=%s",
            tenant.id,
            phone_digits,
            sender_lid,
        )
        return False

    return bool(matched_tenant and matched_tenant.id != tenant.id)
```

2. In the unregistered branch inside `_route_by_instance(...)`, replace the old `close_jid` assignment and insert the guard before any unauthenticated `codigo` session resume:

```python
    msg_lower = message.strip().lower()
    close_jid = _phone_close_jid(phone_digits) or _canonical_jid(sender_lid) or sender_lid

    blocked = await blocked_clients_repository.find_active(
        db,
        tenant.id,
        phone=phone_digits if phone_digits else None,
        whatsapp_lid=sender_lid,
    )
    if blocked:
        return WhatsAppConsoleResponse(reply="", no_reply=True)

    if await _should_silence_external_admin_menu(
        tenant=tenant,
        phone_digits=phone_digits if phone_digits else None,
        sender_lid=sender_lid,
        message=message,
        db=db,
    ):
        logger.info(
            "external_admin_menu_silenced tenant=%s phone=%s lid=%s",
            tenant.id,
            phone_digits,
            sender_lid,
        )
        if close_jid:
            return WhatsAppConsoleResponse(
                reply="",
                no_reply=True,
                status="closed",
                close_jid=close_jid,
            )
        logger.warning(
            "external_admin_menu_missing_close_target tenant=%s phone=%s lid=%s",
            tenant.id,
            phone_digits,
            sender_lid,
        )
        return WhatsAppConsoleResponse(reply="", no_reply=True)
```

3. In `_handle_from_me_routing(...)`, replace the admin-identity bootstrap with this block:

```python
    resolved_admin_phone = (
        normalize_phone(tenant.whatsapp_phone) if tenant.whatsapp_phone else None
    )
    if not resolved_admin_phone and admin_phone:
        resolved_admin_phone = normalize_phone(admin_phone)
    if not resolved_admin_phone:
        logger.warning(
            "from_me_admin_identity_unresolved tenant=%s instance=%s target_jid=%s",
            tenant.id,
            instance,
            target_jid,
        )
        return WhatsAppConsoleResponse(reply="", no_reply=True)

    resolved_admin_jid = (
        _canonical_jid(admin_jid)
        or admin_jid
        or f"{resolved_admin_phone}@s.whatsapp.net"
    )
    preferred_close_jid = _phone_close_jid(resolved_admin_phone) or resolved_admin_jid
```

4. In the rest of `_handle_from_me_routing(...)`, replace every private-reply use of raw `admin_jid` with `resolved_admin_jid`:

```python
    is_self_target = (
        phone_self_target
        or lid_self_target
        or (resolved_admin_jid and target_jid and resolved_admin_jid == target_jid)
    )
```

```python
            close_jids = _client_context_close_jids(
                context_data.get("temp_data", {}), resolved_admin_jid
            )
```

```python
        return WhatsAppConsoleResponse(reply="", no_reply=True, reply_to=resolved_admin_jid)
```

```python
    if message.strip().lower() not in ("/menu", "menu"):
        return WhatsAppConsoleResponse(reply="", no_reply=True, reply_to=resolved_admin_jid)
```

```python
            "admin_jid": resolved_admin_jid,
```

```python
    return WhatsAppConsoleResponse(
        reply=reply,
        reply_to=resolved_admin_jid,
        close_jid=preferred_close_jid,
    )
```

- [x] **Step 4: Run the focused backend tests plus the existing endpoint regression file**

Run:

```bash
cd backend && uv run pytest tests/test_tenants_repository.py tests/test_whatsapp_external_admin_menu_guard.py tests/test_whatsapp_endpoint.py -q
cd backend && uv run ruff check app/api/v1/endpoints/integrations/console.py tests/test_whatsapp_external_admin_menu_guard.py
```

Expected:
- all new tests pass
- existing `test_whatsapp_endpoint.py` still passes
- Ruff exits with status 0.

- [x] **Step 5: Commit the backend routing fix**

```bash
git add backend/app/api/v1/endpoints/integrations/console.py backend/tests/test_whatsapp_external_admin_menu_guard.py
git commit -m "fix: silence external admin menu in tenant routing"
```

## Task 3: Lock and implement the workflow bot-echo filter  [x]

**Skills to read before starting:**
- `superpowers:test-driven-development`
- `n8n-code-javascript`
- `n8n-expression-syntax`
- `n8n-node-configuration`
- `n8n-validation-expert` **only if the workflow contract tests and the JSON edit disagree**

**Files:**
- Modify: `backend/tests/test_n8n_whatsapp_workflow.py`
- Modify: `n8n/TrackPal WhatsApp Bot.json`
- Test: `backend/tests/test_n8n_whatsapp_workflow.py`

- [x] **Step 1: Add the failing workflow-export regression test**

Append this test to `backend/tests/test_n8n_whatsapp_workflow.py`:

```python
def test_parse_input_filters_not_registered_bot_echoes_without_dropping_from_me() -> None:
    js = _workflow_nodes()["Parse input"]["parameters"]["jsCode"]

    assert "no tienes una cuenta registrada" in js
    assert "you do not have a registered account" in js
    assert "if (!fromMe && looksLikeTrackPalGeneratedReply)" in js
```

- [x] **Step 2: Run the workflow regression tests and verify they fail**

Run:

```bash
cd backend && uv run pytest tests/test_n8n_whatsapp_workflow.py -q
```

Expected: FAIL because the current Parse Input JS does not yet include the Spanish and English `not registered` fragments.

- [x] **Step 3: Update only the Parse Input filter in the workflow export**

In `n8n/TrackPal WhatsApp Bot.json`, inside node `Parse input`, replace the `looksLikeTrackPalGeneratedReply` block with this exact code:

```javascript
const looksLikeTrackPalGeneratedReply =
  lowerMessage.includes('no tienes acceso a la consola') ||
  lowerMessage.includes('access denied, you do not have an active account') ||
  lowerMessage.includes('servicio temporalmente no disponible') ||
  lowerMessage.includes('temporarily unavailable') ||
  lowerMessage.includes('no tienes una cuenta registrada') ||
  lowerMessage.includes('you do not have a registered account');

if (!fromMe && looksLikeTrackPalGeneratedReply) {
  return [];
}
```

Do not change node names, connections, `reply_to` expressions, or the `IF no reply` branch.

- [x] **Step 4: Verify the workflow JSON and tests now pass**

Run:

```bash
python - <<'PY'
from pathlib import Path
import json
path = Path('n8n/TrackPal WhatsApp Bot.json')
json.loads(path.read_text(encoding='utf-8'))
print('workflow json ok')
PY
cd backend && uv run pytest tests/test_n8n_whatsapp_workflow.py -q
```

Expected:
- `workflow json ok`
- workflow regression suite passes.

- [x] **Step 5: Commit the workflow filter change**

```bash
git add n8n/TrackPal\ WhatsApp\ Bot.json backend/tests/test_n8n_whatsapp_workflow.py
git commit -m "fix: filter not-registered bot echoes in workflow"
```

## Task 4: Update docs and run full verification including the Evolution Go rollout gate  [x]

**Skills to read before starting:**
- `docs`
- `superpowers:verification-before-completion`
- `n8n-mcp-tools-expert` **only if you import the workflow into a live n8n instance through MCP**

**Files:**
- Modify: `docs/architecture/whatsapp-console-flow.md`
- Modify: `docs/architecture/n8n-workflow.md`
- Modify: `docs/architecture/evolution-integration.md`
- Verify: `backend/tests/test_tenants_repository.py`
- Verify: `backend/tests/test_whatsapp_external_admin_menu_guard.py`
- Verify: `backend/tests/test_n8n_whatsapp_workflow.py`
- Verify: `backend/tests/test_whatsapp_endpoint.py`
- Verify: `n8n/TrackPal WhatsApp Bot.json`
- Verify: `E:/Documentos/GitHub/evolution-go/pkg/webhook/service/listener.go`

- [x] **Step 1: Update `docs/architecture/whatsapp-console-flow.md`**

Make these text edits:

1. In the instance-first routing section, replace the unregistered bullet with:

```markdown
- Unregistered identity → check for Client Messaging Blocks first, then silently close exact `/menu` from another active TrackPal tenant/admin who is not a client of the receiving tenant, then resume/start unauthenticated code lookup for ``codigo``/``código``/``code``, or return ``not_registered`` with ``status="closed"`` and ``close_jid``.
```

2. In the From-me Contextual Routing section, replace step 1 and step 7 with:

```markdown
1. **Resolve admin identity**: derive the authoritative admin phone from the tenant resolved by `instance` first, then fall back to payload `admin_phone` only when the tenant record has no usable WhatsApp phone.
```

```markdown
7. **Return contextual response**: reply with the context initiation message and ``reply_to=<resolved admin jid>`` so n8n sends the reply privately to the admin chat even when the original outgoing webhook payload was ambiguous.
```

- [x] **Step 2: Update `docs/architecture/n8n-workflow.md`**

Make these text edits:

1. In Parse Input normalisation logic, add this bullet after the existing generated-reply filter sentence:

```markdown
- Suppresses known TrackPal-generated not-registered replies (`no tienes una cuenta registrada` / `you do not have a registered account`) when they re-enter the webhook as inbound bot echoes, preventing tenant-to-tenant ping-pong loops.
```

2. In the `IF no reply` / `Check Close Session` discussion, add this sentence:

```markdown
The existing `IF no reply -> Check Close Session -> Close Session` path already supports backend responses shaped as `reply=""`, `no_reply=true`, `status="closed"`, `close_jid="..."`; no workflow rewiring is required for the silent external-admin `/menu` guard.
```

- [x] **Step 3: Update `docs/architecture/evolution-integration.md`**

Under the `from_me` trigger dispatch section, add this exact note:

```markdown
TrackPal's private admin shortcut flow assumes deployed `fromMe=true` webhook payloads include `adminJid=instance.Jid`. The TrackPal backend now falls back to the tenant record when that payload is ambiguous, but rollout should still verify that the deployed Evolution Go build and instance data emit `adminJid` for private admin-chat follow-up messages.
```

- [x] **Step 4: Run the full automated verification suite**

Run:

```bash
cd backend && uv run pytest tests/test_tenants_repository.py tests/test_whatsapp_external_admin_menu_guard.py tests/test_n8n_whatsapp_workflow.py tests/test_whatsapp_endpoint.py -q
cd backend && uv run ruff check app/repositories/tenants_repository.py app/api/v1/endpoints/integrations/console.py tests/test_tenants_repository.py tests/test_whatsapp_external_admin_menu_guard.py tests/test_n8n_whatsapp_workflow.py tests/test_whatsapp_endpoint.py
python - <<'PY'
from pathlib import Path
import json
path = Path('n8n/TrackPal WhatsApp Bot.json')
json.loads(path.read_text(encoding='utf-8'))
print('workflow json ok')
PY
rg -n "external TrackPal tenant/admin|not-registered replies|authoritative admin phone|silent external-admin" docs/architecture/whatsapp-console-flow.md docs/architecture/n8n-workflow.md docs/architecture/evolution-integration.md
```

Expected:
- pytest passes
- Ruff passes
- `workflow json ok`
- `rg` finds the new documentation text.

- [x] **Step 5: Run the live rollout gate before closing the issue**

Do these checks in order:

1. Open `E:/Documentos/GitHub/evolution-go/pkg/webhook/service/listener.go` and verify the deployed source branch still builds payloads with `adminJid = instance.Jid` for `fromMe=true` dispatch.
2. Import `n8n/TrackPal WhatsApp Bot.json` into the target n8n instance.
3. Run this manual scenario:
   - Tenant A sends `/menu` to Tenant B.
   - Tenant A must receive the private contextual menu.
   - Tenant B must receive **no** not-registered reply.
4. Run this manual scenario:
   - Tenant A replies `1` inside the private shortcut chat.
   - The contextual flow must continue.
   - Tenant A's Evolution Go session must **not** be closed unexpectedly.
5. Inspect the live n8n execution input for the private follow-up message and confirm `adminJid` is non-empty.
6. If `adminJid` is empty in live `fromMe=true` follow-up events, **stop rollout** and deploy the current `evolution-go` build before marking TPL-12 complete.

- [x] **Step 6: Commit the doc updates**

```bash
git add docs/architecture/whatsapp-console-flow.md docs/architecture/n8n-workflow.md docs/architecture/evolution-integration.md
git commit -m "docs: document silent external admin menu guard"
```

## Self-review

- **Spec coverage:** covered backend silent `/menu` guard, active-client exclusion, exact `/menu` scope, preserved `code/codigo/código`, authoritative admin fallback for `reply_to`, workflow not-registered echo filter, existing no-reply close path, docs, and the live Evolution Go verification gate.
- **Placeholder scan:** no `TODO`, `TBD`, or “implement later” markers remain; each task includes file paths, code, commands, and expected outcomes.
- **Type consistency:** the plan consistently uses `get_active_by_whatsapp_identity`, `_should_silence_external_admin_menu`, `resolved_admin_jid`, `close_jid`, and `no_reply` across tasks.
