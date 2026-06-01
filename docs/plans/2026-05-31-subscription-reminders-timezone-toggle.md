# Subscription Reminders Timezone/Toggle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make subscription reminders respect each tenant's IANA timezone and configured reminder threshold time, add a tenant-controlled enable/disable toggle, and change n8n to poll every 30 minutes instead of running once per day.

**Architecture:** Keep scheduling logic in the FastAPI backend and keep n8n as a transport-only workflow. Add `reminders_enabled` to tenant reminder settings, validate timezones using Python's IANA support, expose a backend timezone catalog with external-provider fallback, and refactor reminder payload generation to evaluate tenant-local windows in batch without N+1 queries.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy async, PostgreSQL/Alembic, httpx, Vue 3 + Vite, n8n JSON workflow.

**GitHub Issue:** #32 — https://github.com/wilfredocamacho/trackpal/issues/32
**GitHub PR:** #33 — https://github.com/wilfredocamacho/trackpal/pull/33

---

## File map

### Backend
- Create: `backend/alembic/versions/ce10fe74caa9_subscription_reminders_timezone_toggle.py`
- Create: `backend/app/services/subscription_service/timezone_catalog.py`
- Create: `backend/app/services/subscription_service/timezone_catalog_fallback.py`
- Create: `backend/app/services/subscription_job_service/reminder_schedule.py`
- Modify: `backend/app/models/subscription.py`
- Modify: `backend/app/schemas/subscription/create_update.py`
- Modify: `backend/app/schemas/subscription/responses.py`
- Modify: `backend/app/api/v1/endpoints/subscriptions/settings.py`
- Modify: `backend/app/services/subscription_service/reminder_settings.py`
- Modify: `backend/app/services/subscription_service/__init__.py`
- Modify: `backend/app/services/subscription_job_service/reminder_payloads.py`
- Modify: `backend/app/services/subscription_job_service/__init__.py`
- Modify: `backend/tests/test_subscriptions.py`

### Frontend
- Create: `frontend/src/components/subscriptions/ReminderSettingsModal.vue`
- Modify: `frontend/src/views/SubscriptionsView.vue`

### i18n
- Modify: `backend/app/core/i18n/catalogs_es_frontend.py`
- Modify: `backend/app/core/i18n/catalogs_en_frontend.py`

### n8n + docs
- Modify: `n8n/Trackpal Subscription Reminders.json`
- Modify: `docs/architecture/subscriptions.md`
- Modify: `docs/architecture/n8n-workflow.md`
- Modify: `docs/architecture/api-layer.md`

> Note: `n8n/Trackpal Subscription Reminders.json` is already locally modified in the current worktree. Re-read it and inspect `git diff -- n8n/Trackpal\ Subscription\ Reminders.json` before editing so this plan does not overwrite unrelated local changes.

---

### Task 1: Persist `reminders_enabled` and extend the reminder settings API

**Files:**
- Create: `backend/alembic/versions/ce10fe74caa9_subscription_reminders_timezone_toggle.py`
- Modify: `backend/app/models/subscription.py`
- Modify: `backend/app/schemas/subscription/create_update.py`
- Modify: `backend/app/schemas/subscription/responses.py`
- Modify: `backend/app/services/subscription_service/reminder_settings.py`
- Modify: `backend/tests/test_subscriptions.py`

- [x] **Step 1: Write the failing API/defaults test for `reminders_enabled`**

```python
@pytest.mark.asyncio
async def test_subscription_api_settings_defaults_include_toggle(
    client,
    active_tenant_user,
):
    headers = await _login_headers(client, "tenant", "tenant-password")

    response = await client.get("/api/v1/subscription-settings", headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["reminders_enabled"] is False
    assert body["timezone"] == "UTC"
    assert body["warning_days"] == [7, 3, 1]
    assert body["reminder_time"] == "09:00"
    assert body["recipient_mode"] == "tenant_only"
```

- [x] **Step 2: Write the failing update/roundtrip test for `reminders_enabled`**

```python
@pytest.mark.asyncio
async def test_subscription_api_settings_update_persists_toggle_and_timezone(
    client,
    active_tenant_user,
):
    headers = await _login_headers(client, "tenant", "tenant-password")

    update_response = await client.put(
        "/api/v1/subscription-settings",
        json={
            "reminders_enabled": True,
            "timezone": "America/Bogota",
            "warning_days": [5, 2],
            "reminder_time": "08:30",
            "recipient_mode": "tenant_only",
        },
        headers=headers,
    )
    assert update_response.status_code == 200, update_response.text

    get_response = await client.get("/api/v1/subscription-settings", headers=headers)
    assert get_response.status_code == 200
    body = get_response.json()
    assert body["reminders_enabled"] is True
    assert body["timezone"] == "America/Bogota"
    assert body["warning_days"] == [5, 2]
    assert body["reminder_time"] == "08:30"
```

- [x] **Step 3: Run the targeted tests to verify they fail first**

Run:

```bash
cd backend
uv run pytest tests/test_subscriptions.py -k "settings_defaults_include_toggle or settings_update_persists_toggle_and_timezone" -v
```

Expected: FAIL because the response schema and persistence layer do not include `reminders_enabled` yet.

- [x] **Step 4: Add the DB column and ORM field**

```python
# backend/app/models/subscription.py
class SubscriptionReminderSettings(Base, TimestampMixin):
    __tablename__ = "subscription_reminder_settings"

    # ... existing fields ...

    reminders_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=false(),
        nullable=False,
    )
```

```python
# backend/alembic/versions/ce10fe74caa9_subscription_reminders_timezone_toggle.py
from alembic import op
import sqlalchemy as sa

revision = "ce10fe74caa9"
down_revision = "cd7efe74caa0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "subscription_reminder_settings",
        sa.Column(
            "reminders_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("subscription_reminder_settings", "reminders_enabled")
```

- [x] **Step 5: Extend request/response schemas and default-setting creation**

```python
# backend/app/schemas/subscription/create_update.py
class SubscriptionReminderSettingsUpdate(BaseModel):
    model_config = ConfigDict()

    reminders_enabled: Optional[bool] = None
    timezone: Optional[str] = None
    warning_days: Optional[list[int]] = None
    reminder_time: Optional[str] = None
    recipient_mode: Optional[str] = None
```

```python
# backend/app/schemas/subscription/responses.py
class SubscriptionReminderSettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    reminders_enabled: bool
    timezone: str
    warning_days: list[int]
    reminder_time: str
    recipient_mode: str
    created_at: datetime
    updated_at: datetime
```

```python
# backend/app/services/subscription_service/reminder_settings.py
settings = SubscriptionReminderSettings(
    tenant_id=tenant_id,
    reminders_enabled=False,
    timezone="UTC",
    warning_days=[7, 3, 1],
    reminder_time="09:00",
    recipient_mode="tenant_only",
)

if "reminders_enabled" in update_data:
    settings.reminders_enabled = update_data["reminders_enabled"]
```

- [x] **Step 6: Run the targeted tests again**

Run:

```bash
cd backend
uv run pytest tests/test_subscriptions.py -k "settings_defaults_include_toggle or settings_update_persists_toggle_and_timezone" -v
```

Expected: PASS.

- [x] **Step 7: Commit Task 1**

```bash
git add \
  backend/alembic/versions/ce10fe74caa9_subscription_reminders_timezone_toggle.py \
  backend/app/models/subscription.py \
  backend/app/schemas/subscription/create_update.py \
  backend/app/schemas/subscription/responses.py \
  backend/app/services/subscription_service/reminder_settings.py \
  backend/tests/test_subscriptions.py

git commit -m "feat(subscriptions): add reminder enable toggle"
```

---

### Task 2: Add timezone validation and a backend timezone catalog with safe fallback

**Files:**
- Create: `backend/app/services/subscription_service/timezone_catalog.py`
- Create: `backend/app/services/subscription_service/timezone_catalog_fallback.py`
- Modify: `backend/app/api/v1/endpoints/subscriptions/settings.py`
- Modify: `backend/app/services/subscription_service/__init__.py`
- Modify: `backend/app/schemas/subscription/create_update.py`
- Modify: `backend/tests/test_subscriptions.py`

- [x] **Step 1: Write the failing invalid-timezone validation test**

```python
@pytest.mark.asyncio
async def test_subscription_settings_rejects_invalid_timezone(
    client,
    active_tenant_user,
):
    headers = await _login_headers(client, "tenant", "tenant-password")

    response = await client.put(
        "/api/v1/subscription-settings",
        json={"timezone": "Mars/Phobos"},
        headers=headers,
    )

    assert response.status_code in (400, 409, 422)
    assert "timezone" in response.text.lower()
```

- [x] **Step 2: Write the failing timezone-catalog endpoint tests**

```python
@pytest.mark.asyncio
async def test_subscription_timezone_catalog_endpoint_returns_items(
    client,
    active_tenant_user,
):
    headers = await _login_headers(client, "tenant", "tenant-password")

    response = await client.get("/api/v1/subscription-settings/timezones", headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert isinstance(body, list)
    assert any(item["value"] == "UTC" for item in body)
    assert all("label" in item for item in body)
```

```python
@pytest.mark.asyncio
async def test_subscription_timezone_catalog_endpoint_uses_fallback_on_provider_error(
    client,
    active_tenant_user,
    monkeypatch,
):
    headers = await _login_headers(client, "tenant", "tenant-password")

    async def _boom():
        raise RuntimeError("provider down")

    monkeypatch.setattr(
        "app.api.v1.endpoints.subscriptions.settings.subscription_service.list_timezones",
        _boom,
    )

    response = await client.get("/api/v1/subscription-settings/timezones", headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert any(item["value"] == "America/Bogota" for item in body)
```

- [x] **Step 3: Run the targeted tests to confirm failure**

Run:

```bash
cd backend
uv run pytest tests/test_subscriptions.py -k "invalid_timezone or timezone_catalog_endpoint" -v
```

Expected: FAIL because validation and endpoint support do not exist yet.

- [x] **Step 4: Add a bundled fallback catalog and provider wrapper**

```python
# backend/app/services/subscription_service/timezone_catalog_fallback.py
FALLBACK_TIMEZONES = [
    {"value": "UTC", "label": "UTC (UTC+00:00)"},
    {"value": "America/Bogota", "label": "America/Bogota (UTC-05:00)"},
    {"value": "America/Mexico_City", "label": "America/Mexico_City (UTC-06:00)"},
    {"value": "America/New_York", "label": "America/New_York (UTC-05:00/-04:00)"},
    {"value": "Europe/Madrid", "label": "Europe/Madrid (UTC+01:00/+02:00)"},
]
```

```python
# backend/app/services/subscription_service/timezone_catalog.py
from zoneinfo import ZoneInfo
import httpx

from .timezone_catalog_fallback import FALLBACK_TIMEZONES


def is_valid_timezone(value: str) -> bool:
    try:
        ZoneInfo(value)
        return True
    except Exception:
        return False


async def list_timezones() -> list[dict[str, str]]:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get("https://timeapi.io/api/TimeZone/AvailableTimeZones")
            response.raise_for_status()
        items = response.json()
        return [
            {"value": tz, "label": tz}
            for tz in items
            if isinstance(tz, str) and is_valid_timezone(tz)
        ] or FALLBACK_TIMEZONES
    except Exception:
        return FALLBACK_TIMEZONES
```

- [x] **Step 5: Wire validation and the new endpoint into the existing subscription settings flow**

```python
# backend/app/schemas/subscription/create_update.py
from app.services.subscription_service.timezone_catalog import is_valid_timezone

@field_validator("timezone")
@classmethod
def validate_timezone(cls, v: Optional[str]) -> Optional[str]:
    if v is None:
        return v
    if not is_valid_timezone(v):
        raise ValueError("timezone must be a valid IANA timezone")
    return v
```

```python
# backend/app/api/v1/endpoints/subscriptions/settings.py
@settings_router.get("/timezones")
async def list_subscription_timezones(
    db: DbDep,
    tenant_id: ActiveTenantId,
    current_user: CurrentUser,
):
    require_tenant_or_master(current_user)
    return await subscription_service.list_timezones()
```

```python
# backend/app/services/subscription_service/__init__.py
from app.services.subscription_service.timezone_catalog import list_timezones

class SubscriptionService:
    list_timezones = staticmethod(list_timezones)
```

- [x] **Step 6: Run the targeted tests again**

Run:

```bash
cd backend
uv run pytest tests/test_subscriptions.py -k "invalid_timezone or timezone_catalog_endpoint" -v
```

Expected: PASS.

- [x] **Step 7: Commit Task 2**

```bash
git add \
  backend/app/services/subscription_service/timezone_catalog.py \
  backend/app/services/subscription_service/timezone_catalog_fallback.py \
  backend/app/api/v1/endpoints/subscriptions/settings.py \
  backend/app/services/subscription_service/__init__.py \
  backend/app/schemas/subscription/create_update.py \
  backend/tests/test_subscriptions.py

git commit -m "feat(subscriptions): add timezone catalog and validation"
```

---

### Task 3: Refactor reminder generation for tenant-local scheduling and batched loading

**Files:**
- Create: `backend/app/services/subscription_job_service/reminder_schedule.py`
- Modify: `backend/app/services/subscription_job_service/reminder_payloads.py`
- Modify: `backend/app/services/subscription_job_service/__init__.py`
- Modify: `backend/tests/test_subscriptions.py`

- [x] **Step 1: Write the failing tenant-local scheduling tests**

```python
@pytest.mark.asyncio
async def test_subscription_reminders_skip_when_toggle_disabled(
    client,
    db_session,
    active_tenant_user,
):
    api_key = settings.n8n_api_key
    tenant = await _tenant_for_user(db_session, active_tenant_user)
    sub_client, service, plan = await _create_subscription_dependencies(db_session, tenant, "toggleoff")
    now = datetime.now(timezone.utc)
    headers = await _login_headers(client, "tenant", "tenant-password")

    await client.put(
        "/api/v1/subscription-settings",
        json={
            "reminders_enabled": False,
            "timezone": "America/Bogota",
            "warning_days": [7],
            "reminder_time": "00:00",
            "recipient_mode": "tenant_only",
        },
        headers=headers,
    )

    create_response = await client.post(
        "/api/v1/subscriptions",
        json=_subscription_payload(
            sub_client,
            service,
            plan,
            streaming_password="pwd",
            duration_type="custom",
            starts_at=now.isoformat(),
            expires_at=(now + timedelta(days=7)).isoformat(),
        ),
        headers=headers,
    )
    assert create_response.status_code == 201

    pending_response = await client.post(
        "/api/v1/subscriptions/reminders/pending",
        headers={"X-API-Key": api_key},
    )
    assert pending_response.status_code == 200
    assert pending_response.json()["items"] == []
```

```python
@pytest.mark.asyncio
async def test_subscription_reminders_honor_tenant_local_threshold(
    client,
    db_session,
    active_tenant_user,
    monkeypatch,
):
    api_key = settings.n8n_api_key
    tenant = await _tenant_for_user(db_session, active_tenant_user)
    sub_client, service, plan = await _create_subscription_dependencies(db_session, tenant, "bogota930")
    headers = await _login_headers(client, "tenant", "tenant-password")

    fixed_now = datetime(2026, 6, 1, 14, 30, tzinfo=timezone.utc)  # 09:30 America/Bogota

    class _FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed_now if tz else fixed_now.replace(tzinfo=None)

    monkeypatch.setattr(
        "app.services.subscription_job_service.reminder_payloads.datetime",
        _FixedDateTime,
    )
    monkeypatch.setattr(
        "app.services.subscription_job_service.reminder_schedule.datetime",
        _FixedDateTime,
    )

    await client.put(
        "/api/v1/subscription-settings",
        json={
            "reminders_enabled": True,
            "timezone": "America/Bogota",
            "warning_days": [7],
            "reminder_time": "09:00",
            "recipient_mode": "tenant_only",
        },
        headers=headers,
    )

    create_response = await client.post(
        "/api/v1/subscriptions",
        json=_subscription_payload(
            sub_client,
            service,
            plan,
            streaming_password="pwd",
            duration_type="custom",
            starts_at=fixed_now.isoformat(),
            expires_at=(fixed_now + timedelta(days=7)).isoformat(),
        ),
        headers=headers,
    )
    assert create_response.status_code == 201

    pending_response = await client.post(
        "/api/v1/subscriptions/reminders/pending",
        headers={"X-API-Key": api_key},
    )
    assert pending_response.status_code == 200
    assert len(pending_response.json()["items"]) == 1
```

```python
@pytest.mark.asyncio
async def test_subscription_reminders_do_not_send_before_local_threshold(
    client,
    db_session,
    active_tenant_user,
    monkeypatch,
):
    api_key = settings.n8n_api_key
    tenant = await _tenant_for_user(db_session, active_tenant_user)
    sub_client, service, plan = await _create_subscription_dependencies(db_session, tenant, "madrid-before")
    headers = await _login_headers(client, "tenant", "tenant-password")

    fixed_now = datetime(2026, 6, 1, 6, 45, tzinfo=timezone.utc)  # before 09:00 in Europe/Madrid

    class _FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed_now if tz else fixed_now.replace(tzinfo=None)

    monkeypatch.setattr(
        "app.services.subscription_job_service.reminder_payloads.datetime",
        _FixedDateTime,
    )
    monkeypatch.setattr(
        "app.services.subscription_job_service.reminder_schedule.datetime",
        _FixedDateTime,
    )

    await client.put(
        "/api/v1/subscription-settings",
        json={
            "reminders_enabled": True,
            "timezone": "Europe/Madrid",
            "warning_days": [7],
            "reminder_time": "09:00",
            "recipient_mode": "tenant_only",
        },
        headers=headers,
    )

    create_response = await client.post(
        "/api/v1/subscriptions",
        json=_subscription_payload(
            sub_client,
            service,
            plan,
            streaming_password="pwd",
            duration_type="custom",
            starts_at=fixed_now.isoformat(),
            expires_at=(fixed_now + timedelta(days=7)).isoformat(),
        ),
        headers=headers,
    )
    assert create_response.status_code == 201

    pending_response = await client.post(
        "/api/v1/subscriptions/reminders/pending",
        headers={"X-API-Key": api_key},
    )
    assert pending_response.status_code == 200
    assert pending_response.json()["items"] == []
```

- [x] **Step 2: Run the targeted scheduling tests to see them fail**

Run:

```bash
cd backend
uv run pytest tests/test_subscriptions.py -k "toggle_disabled or honor_tenant_local_threshold or do_not_send_before_local_threshold" -v
```

Expected: FAIL because current logic ignores the toggle and tenant-local timezone threshold.

- [x] **Step 3: Extract timezone-aware scheduling helpers into a focused module**

```python
# backend/app/services/subscription_job_service/reminder_schedule.py
from datetime import datetime
from zoneinfo import ZoneInfo


def get_tenant_now(now_utc: datetime, timezone_name: str) -> datetime:
    return now_utc.astimezone(ZoneInfo(timezone_name))


def is_threshold_reached(now_utc: datetime, timezone_name: str, reminder_time: str) -> bool:
    tenant_now = get_tenant_now(now_utc, timezone_name)
    hour, minute = reminder_time.split(":")
    threshold = tenant_now.replace(
        hour=int(hour),
        minute=int(minute),
        second=0,
        microsecond=0,
    )
    return tenant_now >= threshold


def get_days_until_expiry(now_utc: datetime, expires_at: datetime, timezone_name: str) -> int:
    tenant_today = now_utc.astimezone(ZoneInfo(timezone_name)).date()
    tenant_expiry = expires_at.astimezone(ZoneInfo(timezone_name)).date()
    return (tenant_expiry - tenant_today).days
```

- [x] **Step 4: Replace N+1 reminder generation with batched loading and the new local-time helpers**

```python
# backend/app/services/subscription_job_service/reminder_payloads.py
settings_stmt = select(SubscriptionReminderSettings).where(
    SubscriptionReminderSettings.tenant_id.in_(tenant_ids)
)
tenants_stmt = select(Tenant).where(Tenant.id.in_(tenant_ids))

settings_rows = (await db.execute(settings_stmt)).scalars().all()
tenant_rows = (await db.execute(tenants_stmt)).scalars().all()
settings_map = {row.tenant_id: row for row in settings_rows}
tenant_map = {row.id: row for row in tenant_rows}

for sub in subs:
    settings = settings_map.get(sub.tenant_id)
    if settings is None or not settings.reminders_enabled:
        continue
    tenant = tenant_map.get(sub.tenant_id)
    if tenant is None:
        continue
    if not is_threshold_reached(now, settings.timezone, settings.reminder_time):
        continue
    days_until_expiry = get_days_until_expiry(now, sub.expires_at, settings.timezone)
    if days_until_expiry not in settings.warning_days:
        continue
    # create logs and payloads exactly once per recipient
```

- [x] **Step 5: Add a regression test that invalid tenant timezone skips only one tenant, not the whole batch**

```python
@pytest.mark.asyncio
async def test_subscription_reminders_skip_invalid_timezone_without_breaking_batch(
    client,
    db_session,
    active_tenant_user,
    tenant_headers,
):
    api_key = settings.n8n_api_key
    valid_tenant = await _tenant_for_user(db_session, active_tenant_user)
    valid_client, valid_service, valid_plan = await _create_subscription_dependencies(
        db_session,
        valid_tenant,
        "validtz",
    )

    now = datetime.now(timezone.utc)
    create_response = await client.post(
        "/api/v1/subscriptions",
        json=_subscription_payload(
            valid_client,
            valid_service,
            valid_plan,
            streaming_password=None,
            duration_type="custom",
            starts_at=now.isoformat(),
            expires_at=(now + timedelta(days=7)).isoformat(),
        ),
        headers=tenant_headers,
    )
    assert create_response.status_code == 201

    await client.put(
        "/api/v1/subscription-settings",
        json={
            "reminders_enabled": True,
            "timezone": "America/Bogota",
            "warning_days": [7],
            "reminder_time": "00:00",
            "recipient_mode": "tenant_only",
        },
        headers=tenant_headers,
    )

    invalid_owner = User(username="tenant-invalid-tz", password_hash="x", role="tenant")
    db_session.add(invalid_owner)
    await db_session.flush()
    invalid_tenant = Tenant(
        owner_user_id=invalid_owner.id,
        client_prefix="itx01",
        name="Invalid TZ Tenant",
        whatsapp_phone="+12015550999",
        is_active=True,
    )
    db_session.add(invalid_tenant)
    await db_session.flush()
    invalid_client, invalid_service, invalid_plan = await _create_subscription_dependencies(
        db_session,
        invalid_tenant,
        "invalidtz",
    )
    invalid_settings = SubscriptionReminderSettings(
        tenant_id=invalid_tenant.id,
        reminders_enabled=True,
        timezone="Invalid/Timezone",
        warning_days=[7],
        reminder_time="00:00",
        recipient_mode="tenant_only",
    )
    db_session.add(invalid_settings)
    db_session.add(
        Subscription(
            tenant_id=invalid_tenant.id,
            client_id=invalid_client.id,
            service_id=invalid_service.id,
            plan_id=invalid_plan.id,
            streaming_email="invalid@example.com",
            streaming_password_encrypted=None,
            profile_name=None,
            profile_pin_encrypted=None,
            duration_type="custom",
            starts_at=now,
            expires_at=now + timedelta(days=7),
            status="active",
        )
    )
    await db_session.commit()

    response = await client.post(
        "/api/v1/subscriptions/reminders/pending",
        headers={"X-API-Key": api_key},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["tenant_id"] == str(valid_tenant.id)
```

- [x] **Step 6: Run the reminder test block again**

Run:

```bash
cd backend
uv run pytest tests/test_subscriptions.py -k "subscription_reminders_" -v
```

Expected: PASS for the new scheduling cases and existing reminder cases.

- [x] **Step 7: Commit Task 3**

```bash
git add \
  backend/app/services/subscription_job_service/reminder_schedule.py \
  backend/app/services/subscription_job_service/reminder_payloads.py \
  backend/app/services/subscription_job_service/__init__.py \
  backend/tests/test_subscriptions.py

git commit -m "feat(reminders): honor tenant local time windows"
```

---

### Task 4: Update the tenant reminder settings UX and hide config behind the toggle

**Files:**
- Create: `frontend/src/components/subscriptions/ReminderSettingsModal.vue`
- Modify: `frontend/src/views/SubscriptionsView.vue`
- Modify: `backend/app/core/i18n/catalogs_es_frontend.py`
- Modify: `backend/app/core/i18n/catalogs_en_frontend.py`

- [x] **Step 1: Add the new frontend copy keys before wiring the component**

```python
# backend/app/core/i18n/catalogs_es_frontend.py
"frontend.subscriptions.reminders_enabled": "Activar recordatorios automáticos",
"frontend.subscriptions.reminder_time_threshold": "Enviar recordatorios a partir de las",
"frontend.subscriptions.reminder_time_help": "Los recordatorios nunca se enviarán antes de esta hora en tu zona horaria. Si el sistema se retrasa, se enviarán después, tan pronto como sea posible.",
"frontend.subscriptions.timezone_loading_error": "No se pudo cargar la lista de zonas horarias.",
```

```python
# backend/app/core/i18n/catalogs_en_frontend.py
"frontend.subscriptions.reminders_enabled": "Enable automatic reminders",
"frontend.subscriptions.reminder_time_threshold": "Send reminders starting at",
"frontend.subscriptions.reminder_time_help": "Reminders will never be sent before this time in your time zone. If the system is delayed, they will be sent afterward as soon as possible.",
"frontend.subscriptions.timezone_loading_error": "Could not load time zone options.",
```

- [x] **Step 2: Extract the reminder settings modal out of the oversized `SubscriptionsView.vue` file**

```vue
<!-- frontend/src/components/subscriptions/ReminderSettingsModal.vue -->
<script setup>
import { computed, ref, watch } from 'vue'
import api from '../../services/api'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  settings: { type: Object, required: true },
  saving: { type: Boolean, default: false },
  i18nStore: { type: Object, required: true },
})

const emit = defineEmits(['update:modelValue', 'save'])
const timezoneOptions = ref([])
const timezoneError = ref('')

async function loadTimezones() {
  try {
    const response = await api.get('/subscription-settings/timezones')
    timezoneOptions.value = Array.isArray(response.data) ? response.data : []
  } catch (error) {
    timezoneError.value = props.i18nStore.t('frontend.subscriptions.timezone_loading_error')
    timezoneOptions.value = []
  }
}

watch(() => props.modelValue, (open) => {
  if (open) loadTimezones()
})
</script>
```

- [x] **Step 3: Render the toggle-first UX with hidden configuration when disabled**

```vue
<template>
  <div v-if="modelValue" class="modal-overlay" @click.self="emit('update:modelValue', false)">
    <div class="modal">
      <div class="modal-body">
        <label class="toggle-row">
          <input v-model="settings.reminders_enabled" type="checkbox" />
          {{ i18nStore.t('frontend.subscriptions.reminders_enabled') }}
        </label>

        <template v-if="settings.reminders_enabled">
          <label>
            {{ i18nStore.t('frontend.subscriptions.timezone') }}
            <select v-model="settings.timezone">
              <option v-for="tz in timezoneOptions" :key="tz.value" :value="tz.value">{{ tz.label }}</option>
            </select>
          </label>

          <label>
            {{ i18nStore.t('frontend.subscriptions.reminder_time_threshold') }}
            <input v-model="settings.reminder_time" type="time" />
            <small>{{ i18nStore.t('frontend.subscriptions.reminder_time_help') }}</small>
          </label>
        </template>
      </div>
    </div>
  </div>
</template>
```

- [x] **Step 4: Replace the inline modal logic in `SubscriptionsView.vue` with the new component contract**

```vue
<script setup>
import ReminderSettingsModal from '../components/subscriptions/ReminderSettingsModal.vue'

const reminderSettings = ref({
  reminders_enabled: false,
  timezone: 'UTC',
  warning_days: [7, 3, 1],
  reminder_time: '09:00',
  recipient_mode: 'tenant_only',
})
</script>

<template>
  <ReminderSettingsModal
    v-model="showReminderSettings"
    :settings="reminderSettings"
    :saving="isSaving"
    :i18n-store="i18nStore"
    @save="saveReminderSettings"
  />
</template>
```

- [x] **Step 5: Run the frontend build as the verification gate**

Run:

```bash
cd frontend
npm run build
```

Expected: successful production build with no Vue compile errors.

- [x] **Step 6: Commit Task 4**

```bash
git add \
  frontend/src/components/subscriptions/ReminderSettingsModal.vue \
  frontend/src/views/SubscriptionsView.vue \
  backend/app/core/i18n/catalogs_es_frontend.py \
  backend/app/core/i18n/catalogs_en_frontend.py

git commit -m "feat(frontend): add reminder toggle-first settings UX"
```

---

### Task 5: Update the n8n reminder workflow and refresh docs

**Files:**
- Modify: `n8n/Trackpal Subscription Reminders.json`
- Modify: `docs/architecture/subscriptions.md`
- Modify: `docs/architecture/n8n-workflow.md`
- Modify: `docs/architecture/api-layer.md`

- [x] **Step 1: Re-read the current workflow file and inspect the local diff before editing**

Run:

```bash
git diff -- "n8n/Trackpal Subscription Reminders.json"
python -m json.tool "n8n/Trackpal Subscription Reminders.json" > NUL
```

Expected: you see any unrelated local edits first, and the JSON parses cleanly before modification.

- [x] **Step 2: Change the n8n schedule trigger from daily-at-09:00 to every 30 minutes**

```json
{
  "parameters": {
    "rule": {
      "interval": [
        {
          "field": "minutes",
          "minutesInterval": 30
        }
      ]
    }
  },
  "name": "Schedule Trigger"
}
```

If the target n8n schema requires a slightly different shape, keep the behavioral contract identical: run every 30 minutes, not daily.

- [x] **Step 3: Update docs to reflect the new runtime contract**

```md
# docs/architecture/subscriptions.md
- reminder settings include `reminders_enabled`, IANA `timezone`, `warning_days`, `reminder_time`, and `recipient_mode`
- `reminder_time` means the tenant-local threshold after which reminders may be sent
- the n8n workflow polls every 30 minutes
```

```md
# docs/architecture/n8n-workflow.md
- Subscription Reminders workflow runs every 30 minutes
- backend determines timezone eligibility and deduplicates reminder generation
- n8n remains transport-only and contains no tenant-timezone logic
```

```md
# docs/architecture/api-layer.md
- `GET /api/v1/subscription-settings/timezones`
- `GET/PUT /api/v1/subscription-settings` include `reminders_enabled`
```

- [x] **Step 4: Validate the workflow JSON and run the focused backend reminder suite one last time**

Run:

```bash
python -m json.tool "n8n/Trackpal Subscription Reminders.json" > NUL
cd backend
uv run pytest tests/test_subscriptions.py -k "subscription_reminder or subscription_api_settings" -v
```

Expected: JSON parses cleanly and backend reminder/settings tests pass.

- [x] **Step 5: Commit Task 5**

```bash
git add \
  "n8n/Trackpal Subscription Reminders.json" \
  docs/architecture/subscriptions.md \
  docs/architecture/n8n-workflow.md \
  docs/architecture/api-layer.md

git commit -m "chore(reminders): switch workflow to 30 minute polling"
```

---

## Final verification checklist

- [x] Run backend subscription tests:

```bash
cd backend
uv run pytest tests/test_subscriptions.py -v
```

Expected: PASS.

- [x] Run frontend build:

```bash
cd frontend
npm run build
```

Expected: PASS.

- [x] Validate the reminder workflow JSON:

```bash
python -m json.tool "n8n/Trackpal Subscription Reminders.json" > NUL
```

Expected: no output, exit code 0.

- [x] Inspect final diff before handoff:

```bash
git status --short
git diff --stat
```

Expected: only the intended backend, frontend, n8n, and docs files are changed.

## Execution handoff

This plan is intended for **subagent-driven execution**.

Recommended execution contract:

1. dispatch one fresh subagent per task;
2. review the diff and test output after each task commit;
3. only continue to the next task when the previous task is verified;
4. preserve the TDD order inside each task.

## Self-review notes

- **Spec coverage:** The plan covers the toggle, IANA timezone validation, backend-served timezone catalog, tenant-local threshold semantics, batching/N+1 removal, n8n 30-minute polling, frontend UX updates, and docs refresh.
- **Placeholder scan:** The only variable piece is the exact n8n schedule JSON shape; the behavioral contract is explicit and should be matched to the editor-exported schema if it differs slightly.
- **Type consistency:** The plan consistently uses `reminders_enabled`, `timezone`, `warning_days`, `reminder_time`, and `recipient_mode` across backend, frontend, API, and docs.
