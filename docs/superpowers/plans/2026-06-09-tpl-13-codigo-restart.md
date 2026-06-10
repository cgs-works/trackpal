# TPL-13 Codigo Restart Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `code|codigo|código` restart the codigo flow from `awaiting_result` for both tenant-admin and unauthenticated flows, while best-effort cancelling only the session-linked active lookup job.

**Architecture:** Add one small repository helper that safely marks a session-linked `mail_lookup_job` as failed with `error_code="user_cancelled"` only when the job is still active. Then update the two `awaiting_result` handlers to intercept restart trigger words, best-effort cancel the current job, clear the Redis conversation session, and rebuild the service-list step instead of replying `wa.tenant.codigo.still_checking`.

**Tech Stack:** Python 3.11, FastAPI endpoint handlers, SQLAlchemy async ORM, Redis-backed `WhatsAppSessionService`, pytest + pytest-asyncio.

---

## Read this first

1. `docs/superpowers/specs/2026-06-09-tpl-13-codigo-restart-design.md`
2. `backend/app/services/whatsapp_tenant_console_service/service.py:197-311` (read-only context: active-flow routing happens before top-level codigo triggers)
3. `backend/app/services/whatsapp_tenant_console_service/codigo_flow.py:85-181,346-457`
4. `backend/app/api/v1/endpoints/integrations/console_handlers.py:463-550,847-1041`
5. `backend/app/repositories/mailbox_lookup_repository.py:43-141`
6. `backend/tests/test_mailbox_persistence.py:158-313`
7. `backend/tests/test_tenant_console_service.py:1801-2588`
8. `backend/tests/test_whatsapp_endpoint.py:932-1665`
9. `docs/architecture/whatsapp-console-flow.md:287-360`

## File map

- **Modify:** `backend/app/repositories/mailbox_lookup_repository.py`
  - Add `cancel_active_job_if_present()`.
  - Do **not** add a new job status.
  - Do **not** add schema changes.
- **Modify:** `backend/tests/test_mailbox_persistence.py`
  - Add repository tests for the new cancellation helper.
- **Modify:** `backend/app/services/whatsapp_tenant_console_service/codigo_flow.py`
  - Add tenant restart-trigger behavior inside `_handle_codigo_awaiting_result()`.
- **Modify:** `backend/tests/test_tenant_console_service.py`
  - Add tenant-unit tests for restart, terminal/no-op, malformed UUID, and non-trigger behavior.
- **Modify:** `backend/app/api/v1/endpoints/integrations/console_handlers.py`
  - Add unauthenticated restart-trigger behavior inside `_handle_unauth_codigo_result()`.
- **Modify:** `backend/tests/test_whatsapp_endpoint.py`
  - Add endpoint-level unauthenticated regression tests.
- **Modify:** `docs/architecture/whatsapp-console-flow.md`
  - Document restart-from-`awaiting_result` semantics and the session-linked best-effort cancellation rule.

## Guardrails

- Only cancel the job referenced by `session.temp_data["lookup_job_id"]`.
- Only mutate jobs in `pending` or `processing`.
- If `lookup_job_id` is missing, malformed, terminal, or the DB call fails, **still restart the flow**.
- Preserve existing `1` / `2` / `0` behavior.
- Keep changes surgical; do not refactor unrelated codigo flow code.

---

### Task 1: Add the repository helper for safe session-linked cancellation

**Relevant skills during execution:**
- `superpowers:test-driven-development`
- `python-pro`

**Files:**
- Modify: `backend/app/repositories/mailbox_lookup_repository.py:43-141`
- Test: `backend/tests/test_mailbox_persistence.py:158-313`

- [x] **Step 1: Write the failing repository tests**

Add these tests inside `TestMailboxLookupRepository` in `backend/tests/test_mailbox_persistence.py`, immediately after `test_get_job_with_tenant_scope`:

```python
    async def test_cancel_active_job_if_present_marks_pending_job_failed(self, db_session):
        tenant = await _seed_tenant(db_session)
        mb = await _seed_mailbox(db_session, tenant.id)
        job = await mailbox_lookup_repository.create_job(
            db_session,
            tenant.id,
            mb.id,
            "netflix",
        )

        cancelled = await mailbox_lookup_repository.cancel_active_job_if_present(
            db_session,
            job.id,
            tenant_id=tenant.id,
        )

        assert cancelled is True
        assert job.status == "failed"
        assert job.error_code == "user_cancelled"
        assert job.error_detail_safe == "User restarted codigo flow"
        assert job.completed_at is not None

    async def test_cancel_active_job_if_present_leaves_completed_job_unchanged(self, db_session):
        tenant = await _seed_tenant(db_session)
        mb = await _seed_mailbox(db_session, tenant.id)
        job = await mailbox_lookup_repository.create_job(
            db_session,
            tenant.id,
            mb.id,
            "netflix",
        )
        await mailbox_lookup_repository.transition_status(db_session, job, "processing")
        await mailbox_lookup_repository.transition_status(
            db_session,
            job,
            "completed",
            result_type="code",
            result_value_encrypted=encrypt_value("227597"),
        )
        original_completed_at = job.completed_at

        cancelled = await mailbox_lookup_repository.cancel_active_job_if_present(
            db_session,
            job.id,
            tenant_id=tenant.id,
        )

        assert cancelled is False
        assert job.status == "completed"
        assert job.error_code is None
        assert job.completed_at == original_completed_at

    async def test_cancel_active_job_if_present_returns_false_for_missing_job(self, db_session):
        tenant = await _seed_tenant(db_session)

        cancelled = await mailbox_lookup_repository.cancel_active_job_if_present(
            db_session,
            uuid.uuid4(),
            tenant_id=tenant.id,
        )

        assert cancelled is False
```

- [x] **Step 2: Run the repository tests to verify they fail**

Run:

```bash
cd backend && uv run pytest \
  tests/test_mailbox_persistence.py::TestMailboxLookupRepository::test_cancel_active_job_if_present_marks_pending_job_failed \
  tests/test_mailbox_persistence.py::TestMailboxLookupRepository::test_cancel_active_job_if_present_leaves_completed_job_unchanged \
  tests/test_mailbox_persistence.py::TestMailboxLookupRepository::test_cancel_active_job_if_present_returns_false_for_missing_job \
  -v
```

Expected: FAIL with an error similar to:

```text
AttributeError: module 'app.repositories.mailbox_lookup_repository' has no attribute 'cancel_active_job_if_present'
```

- [x] **Step 3: Write the minimal repository implementation**

Add this function to `backend/app/repositories/mailbox_lookup_repository.py` right after `get_job()` and before `list_pending_jobs()`:

```python
async def cancel_active_job_if_present(
    db: AsyncSession,
    job_id: UUID,
    tenant_id: UUID | None = None,
) -> bool:
    """Best-effort cancel for a session-linked active lookup job.

    Returns ``True`` only when an active job (``pending`` or ``processing``)
    was mutated to ``failed``. Returns ``False`` for missing jobs and for jobs
    that are already terminal.

    The helper does not commit; callers keep transaction control.
    """
    job = await get_job(db, job_id, tenant_id=tenant_id)
    if job is None:
        return False

    if job.status not in {"pending", "processing"}:
        return False

    job.status = "failed"
    job.completed_at = datetime.now(timezone.utc)
    job.error_code = "user_cancelled"
    job.error_detail_safe = "User restarted codigo flow"
    await db.flush()
    return True
```

Also update `__all__` at the bottom of the same file:

```python
__all__ = [
    "create_job",
    "get_job",
    "cancel_active_job_if_present",
    "list_pending_jobs",
    "transition_status",
    "expire_stale_jobs",
    "delete_expired_jobs",
]
```

- [x] **Step 4: Run the repository tests to verify they pass**

Run:

```bash
cd backend && uv run pytest \
  tests/test_mailbox_persistence.py::TestMailboxLookupRepository::test_cancel_active_job_if_present_marks_pending_job_failed \
  tests/test_mailbox_persistence.py::TestMailboxLookupRepository::test_cancel_active_job_if_present_leaves_completed_job_unchanged \
  tests/test_mailbox_persistence.py::TestMailboxLookupRepository::test_cancel_active_job_if_present_returns_false_for_missing_job \
  -v
```

Expected: PASS for all 3 tests.

- [x] **Step 5: Commit the repository helper**

Run:

```bash
git add backend/app/repositories/mailbox_lookup_repository.py backend/tests/test_mailbox_persistence.py
git commit -m "feat: add codigo lookup cancellation helper"
```

---

### Task 2: Restart the tenant-admin codigo flow from `awaiting_result`

**Relevant skills during execution:**
- `superpowers:test-driven-development`
- `superpowers:systematic-debugging`
- `python-pro`

**Files:**
- Modify: `backend/app/services/whatsapp_tenant_console_service/codigo_flow.py:346-457`
- Test: `backend/tests/test_tenant_console_service.py:2523-2590`
- Read-only reference: `backend/app/services/whatsapp_tenant_console_service/service.py:197-255`

- [x] **Step 1: Write the failing tenant-flow tests**

Add these tests near the existing `_handle_codigo_awaiting_result` tests in `backend/tests/test_tenant_console_service.py`:

```python
    async def test_codigo_awaiting_result_trigger_restarts_flow_and_cancels_active_job(
        self,
        console_service: WhatsAppTenantConsoleService,
    ) -> None:
        mock_db = AsyncMock()
        tenant_id = uuid4()
        lookup_job_id = uuid4()
        mock_session_service = AsyncMock()
        mock_session = SimpleNamespace(
            temp_data={
                "lookup_job_id": str(lookup_job_id),
                "service_key": "netflix",
                "target_email": "user@example.com",
            }
        )
        restart_reply = "📩 Buscar código\n\n[1] Netflix\n\n0️⃣ Cancelar"

        with (
            patch(
                "app.services.whatsapp_tenant_console_service.codigo_flow.mailbox_lookup_repository.cancel_active_job_if_present",
                AsyncMock(return_value=True),
            ) as cancel_job,
            patch.object(
                console_service,
                "_start_codigo_flow",
                AsyncMock(return_value=restart_reply),
            ) as start_flow,
        ):
            reply = await console_service._handle_codigo_awaiting_result(
                phone="+10000000000",
                msg=" code ",
                session=mock_session,
                session_service=mock_session_service,
                tenant_id=tenant_id,
                db=mock_db,
            )

        assert reply == restart_reply
        cancel_job.assert_awaited_once_with(
            mock_db,
            lookup_job_id,
            tenant_id=tenant_id,
        )
        mock_db.commit.assert_awaited_once()
        mock_session_service.clear_session.assert_awaited_once_with("admin:+10000000000")
        start_flow.assert_awaited_once_with(
            "+10000000000",
            mock_session_service,
            tenant_id,
            mock_db,
            started_from_menu=False,
            role="tenant",
        )

    async def test_codigo_awaiting_result_trigger_restarts_when_cancel_helper_noops(
        self,
        console_service: WhatsAppTenantConsoleService,
    ) -> None:
        mock_db = AsyncMock()
        tenant_id = uuid4()
        lookup_job_id = uuid4()
        mock_session_service = AsyncMock()
        mock_session = SimpleNamespace(temp_data={"lookup_job_id": str(lookup_job_id)})
        restart_reply = "📩 Buscar código\n\n[1] Netflix\n\n0️⃣ Cancelar"

        with (
            patch(
                "app.services.whatsapp_tenant_console_service.codigo_flow.mailbox_lookup_repository.cancel_active_job_if_present",
                AsyncMock(return_value=False),
            ) as cancel_job,
            patch.object(
                console_service,
                "_start_codigo_flow",
                AsyncMock(return_value=restart_reply),
            ) as start_flow,
        ):
            reply = await console_service._handle_codigo_awaiting_result(
                phone="+10000000000",
                msg="código",
                session=mock_session,
                session_service=mock_session_service,
                tenant_id=tenant_id,
                db=mock_db,
            )

        assert reply == restart_reply
        cancel_job.assert_awaited_once_with(
            mock_db,
            lookup_job_id,
            tenant_id=tenant_id,
        )
        mock_db.commit.assert_not_awaited()
        start_flow.assert_awaited_once()

    async def test_codigo_awaiting_result_trigger_restarts_with_invalid_lookup_job_id(
        self,
        console_service: WhatsAppTenantConsoleService,
    ) -> None:
        mock_db = AsyncMock()
        tenant_id = uuid4()
        mock_session_service = AsyncMock()
        mock_session = SimpleNamespace(temp_data={"lookup_job_id": "not-a-uuid"})
        restart_reply = "📩 Buscar código\n\n[1] Netflix\n\n0️⃣ Cancelar"

        with (
            patch(
                "app.services.whatsapp_tenant_console_service.codigo_flow.mailbox_lookup_repository.cancel_active_job_if_present",
                AsyncMock(),
            ) as cancel_job,
            patch.object(
                console_service,
                "_start_codigo_flow",
                AsyncMock(return_value=restart_reply),
            ) as start_flow,
        ):
            reply = await console_service._handle_codigo_awaiting_result(
                phone="+10000000000",
                msg="codigo",
                session=mock_session,
                session_service=mock_session_service,
                tenant_id=tenant_id,
                db=mock_db,
            )

        assert reply == restart_reply
        cancel_job.assert_not_called()
        mock_db.commit.assert_not_awaited()
        start_flow.assert_awaited_once()

    async def test_codigo_awaiting_result_non_trigger_still_returns_still_checking(
        self,
        console_service: WhatsAppTenantConsoleService,
    ) -> None:
        mock_session_service = AsyncMock()
        mock_session = SimpleNamespace(temp_data={})

        reply = await console_service._handle_codigo_awaiting_result(
            phone="+10000000000",
            msg="hola",
            session=mock_session,
            session_service=mock_session_service,
            tenant_id=uuid4(),
            db=AsyncMock(),
        )

        assert "todavia buscando" in reply.lower() or "still" in reply.lower()
```

- [x] **Step 2: Run the tenant-flow tests to verify they fail**

Run:

```bash
cd backend && uv run pytest \
  tests/test_tenant_console_service.py::TestCodigoFlow::test_codigo_awaiting_result_trigger_restarts_flow_and_cancels_active_job \
  tests/test_tenant_console_service.py::TestCodigoFlow::test_codigo_awaiting_result_trigger_restarts_when_cancel_helper_noops \
  tests/test_tenant_console_service.py::TestCodigoFlow::test_codigo_awaiting_result_trigger_restarts_with_invalid_lookup_job_id \
  tests/test_tenant_console_service.py::TestCodigoFlow::test_codigo_awaiting_result_non_trigger_still_returns_still_checking \
  -v
```

Expected: FAIL because `_handle_codigo_awaiting_result()` still falls through to `wa.tenant.codigo.still_checking` for fresh `code|codigo|código` input.

- [x] **Step 3: Implement tenant restart-trigger handling**

In `backend/app/services/whatsapp_tenant_console_service/codigo_flow.py`, update `_handle_codigo_awaiting_result()` immediately **after** the existing lookup-job status read and **before** the `msg.strip() == "1"` branch.

Insert this block:

```python
    restart_trigger = msg.strip().lower() in ("codigo", "código", "code")
    if restart_trigger:
        if lookup_job_id and db is not None:
            try:
                cancelled = await mailbox_lookup_repository.cancel_active_job_if_present(
                    db,
                    UUID(lookup_job_id),
                    tenant_id=tenant_id,
                )
                if cancelled:
                    await db.commit()
            except ValueError:
                logger.warning(
                    "Ignoring invalid lookup job id during codigo restart: %s",
                    lookup_job_id,
                )
            except Exception:
                logger.exception(
                    "Failed to cancel lookup job %s during codigo restart",
                    lookup_job_id,
                )
                try:
                    await db.rollback()
                except Exception:
                    logger.exception(
                        "Failed to rollback after codigo restart cancellation error"
                    )

        await session_service.clear_session(f"admin:{phone}")
        return await self._start_codigo_flow(
            phone,
            session_service,
            tenant_id,
            db,
            started_from_menu=False,
            role="tenant",
        )
```

Do **not** change the existing `1`, `2`, `0`, or fallback semantics outside this new trigger branch.

- [x] **Step 4: Run the tenant-flow tests to verify they pass**

Run:

```bash
cd backend && uv run pytest \
  tests/test_tenant_console_service.py::TestCodigoFlow::test_codigo_awaiting_result_trigger_restarts_flow_and_cancels_active_job \
  tests/test_tenant_console_service.py::TestCodigoFlow::test_codigo_awaiting_result_trigger_restarts_when_cancel_helper_noops \
  tests/test_tenant_console_service.py::TestCodigoFlow::test_codigo_awaiting_result_trigger_restarts_with_invalid_lookup_job_id \
  tests/test_tenant_console_service.py::TestCodigoFlow::test_codigo_awaiting_result_non_trigger_still_returns_still_checking \
  tests/test_tenant_console_service.py::TestCodigoFlow::test_codigo_awaiting_result_retry_allows_pending_job \
  tests/test_tenant_console_service.py::TestCodigoFlow::test_codigo_awaiting_result_back_reopens_services_even_if_job_pending \
  -v
```

Expected: PASS for all 6 tests.

- [x] **Step 5: Commit the tenant-flow fix**

Run:

```bash
git add backend/app/services/whatsapp_tenant_console_service/codigo_flow.py backend/tests/test_tenant_console_service.py
git commit -m "fix: restart tenant codigo flow from awaiting result"


---

### Task 3: Restart the unauthenticated codigo flow from `awaiting_result`

**Relevant skills during execution:**
- `superpowers:test-driven-development`
- `superpowers:systematic-debugging`
- `python-pro`
- `fastapi-expert`

**Files:**
- Modify: `backend/app/api/v1/endpoints/integrations/console_handlers.py:847-1041`
- Test: `backend/tests/test_whatsapp_endpoint.py:932-1665`
- Read-only reference: `backend/app/api/v1/endpoints/integrations/console.py:304-390`

- [ ] **Step 1: Write the failing unauthenticated endpoint tests**

First add this small helper near `_reach_unauth_codigo_confirm_step()` in `backend/tests/test_whatsapp_endpoint.py`:

```python
async def _seed_unauth_codigo_awaiting_result(
    fake_mgr: _FakeManager,
    tenant_id,
    *,
    phone: str = "12015559999",
    lookup_job_id: str = "",
) -> str:
    import json

    tenant_prefix = str(tenant_id)[:8]
    session_key = f"session:unreg:{tenant_prefix}:{phone}"
    await fake_mgr._redis.set(
        session_key,
        json.dumps(
            {
                "phone": f"unreg:{tenant_prefix}:{phone}",
                "flow": "codigo",
                "step": "awaiting_result",
                "selected_tenant_id": None,
                "temp_data": {
                    "lookup_job_id": lookup_job_id,
                    "service_key": "netflix",
                    "target_email": "user@example.com",
                },
                "selection_map": {},
            }
        ),
        ex=300,
    )
    return session_key
```

Then add these endpoint tests after the existing unauth codigo retry test block:

```python
async def test_unregistered_codigo_trigger_restarts_awaiting_result_and_cancels_active_job(
    client, db_session, active_tenant_user
):
    tenant = await _setup_tenant_for_codigo(db_session, active_tenant_user)
    fake_mgr = _FakeManager(used_backup=False)
    lookup_job_id = uuid4()
    session_key = await _seed_unauth_codigo_awaiting_result(
        fake_mgr,
        tenant.id,
        lookup_job_id=str(lookup_job_id),
    )

    with (
        patch(
            "app.api.v1.endpoints.integrations.console.get_redis_manager",
            return_value=fake_mgr,
        ),
        patch(
            "app.api.v1.endpoints.integrations.console_handlers.mailbox_lookup_repository.cancel_active_job_if_present",
            AsyncMock(return_value=True),
        ) as cancel_job,
    ):
        response = await client.post(
            ENDPOINT,
            json={
                "phone": "+12015559999",
                "message": " code ",
                "instance": TEST_INSTANCE,
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )

    assert response.status_code == 200
    body = response.json()
    assert "Netflix" in body["reply"]
    assert "todavia buscando" not in body["reply"].lower()
    assert "still checking" not in body["reply"].lower()

    called = cancel_job.await_args
    assert called.args[1] == lookup_job_id
    assert called.kwargs["tenant_id"] == tenant.id

    import json

    saved = json.loads(await fake_mgr._redis.get(session_key))
    assert saved["step"] == "service"
    assert saved["temp_data"]["codigo_effective_keys"] == ["netflix"]
    assert saved["temp_data"]["codigo_current_page"] == 0


async def test_unregistered_codigo_trigger_restarts_when_cancel_helper_noops(
    client, db_session, active_tenant_user
):
    tenant = await _setup_tenant_for_codigo(db_session, active_tenant_user)
    fake_mgr = _FakeManager(used_backup=False)
    lookup_job_id = uuid4()
    session_key = await _seed_unauth_codigo_awaiting_result(
        fake_mgr,
        tenant.id,
        lookup_job_id=str(lookup_job_id),
    )

    with (
        patch(
            "app.api.v1.endpoints.integrations.console.get_redis_manager",
            return_value=fake_mgr,
        ),
        patch(
            "app.api.v1.endpoints.integrations.console_handlers.mailbox_lookup_repository.cancel_active_job_if_present",
            AsyncMock(return_value=False),
        ) as cancel_job,
    ):
        response = await client.post(
            ENDPOINT,
            json={
                "phone": "+12015559999",
                "message": "codigo",
                "instance": TEST_INSTANCE,
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )

    assert response.status_code == 200
    body = response.json()
    assert "Netflix" in body["reply"]

    called = cancel_job.await_args
    assert called.args[1] == lookup_job_id
    assert called.kwargs["tenant_id"] == tenant.id

    import json

    saved = json.loads(await fake_mgr._redis.get(session_key))
    assert saved["step"] == "service"


async def test_unregistered_codigo_trigger_restarts_with_invalid_lookup_job_id(
    client, db_session, active_tenant_user
):
    tenant = await _setup_tenant_for_codigo(db_session, active_tenant_user)
    fake_mgr = _FakeManager(used_backup=False)
    session_key = await _seed_unauth_codigo_awaiting_result(
        fake_mgr,
        tenant.id,
        lookup_job_id="not-a-uuid",
    )

    with (
        patch(
            "app.api.v1.endpoints.integrations.console.get_redis_manager",
            return_value=fake_mgr,
        ),
        patch(
            "app.api.v1.endpoints.integrations.console_handlers.mailbox_lookup_repository.cancel_active_job_if_present",
            AsyncMock(),
        ) as cancel_job,
    ):
        response = await client.post(
            ENDPOINT,
            json={
                "phone": "+12015559999",
                "message": "código",
                "instance": TEST_INSTANCE,
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )

    assert response.status_code == 200
    body = response.json()
    assert "Netflix" in body["reply"]
    cancel_job.assert_not_called()

    import json

    saved = json.loads(await fake_mgr._redis.get(session_key))
    assert saved["step"] == "service"


async def test_unregistered_codigo_non_trigger_still_returns_still_checking(
    client, db_session, active_tenant_user
):
    tenant = await _setup_tenant_for_codigo(db_session, active_tenant_user)
    fake_mgr = _FakeManager(used_backup=False)
    await _seed_unauth_codigo_awaiting_result(
        fake_mgr,
        tenant.id,
        lookup_job_id="",
    )

    with patch(
        "app.api.v1.endpoints.integrations.console.get_redis_manager",
        return_value=fake_mgr,
    ):
        response = await client.post(
            ENDPOINT,
            json={
                "phone": "+12015559999",
                "message": "hola",
                "instance": TEST_INSTANCE,
            },
            headers={"X-API-Key": settings.n8n_api_key},
        )

    assert response.status_code == 200
    body = response.json()
    assert "todavia buscando" in body["reply"].lower() or "still checking" in body["reply"].lower()
```

- [ ] **Step 2: Run the unauthenticated endpoint tests to verify they fail**

Run:

```bash
cd backend && uv run pytest \
  tests/test_whatsapp_endpoint.py::test_unregistered_codigo_trigger_restarts_awaiting_result_and_cancels_active_job \
  tests/test_whatsapp_endpoint.py::test_unregistered_codigo_trigger_restarts_when_cancel_helper_noops \
  tests/test_whatsapp_endpoint.py::test_unregistered_codigo_trigger_restarts_with_invalid_lookup_job_id \
  tests/test_whatsapp_endpoint.py::test_unregistered_codigo_non_trigger_still_returns_still_checking \
  -v
```

Expected: FAIL because the existing unauthenticated `awaiting_result` handler still treats fresh `code|codigo|código` input as `still_checking`.

- [ ] **Step 3: Implement unauthenticated restart-trigger handling**

In `backend/app/api/v1/endpoints/integrations/console_handlers.py`, update `_handle_unauth_codigo_result()` immediately **after** the existing job lookup block and **before** the `if not job_done:` branch.

Insert this block:

```python
    restart_trigger = msg.strip().lower() in ("codigo", "código", "code")
    if restart_trigger:
        if lookup_job_id:
            try:
                cancelled = await mailbox_lookup_repository.cancel_active_job_if_present(
                    db,
                    UUID(lookup_job_id),
                    tenant_id=tenant.id,
                )
                if cancelled:
                    await db.commit()
            except ValueError:
                logger.warning(
                    "Ignoring invalid lookup job id during unauth codigo restart: %s",
                    lookup_job_id,
                )
            except Exception:
                logger.exception(
                    "Failed to cancel lookup job %s during unauth codigo restart",
                    lookup_job_id,
                )
                try:
                    await db.rollback()
                except Exception:
                    logger.exception(
                        "Failed to rollback after unauth codigo restart cancellation error"
                    )

        await session_service.clear_session(session_key)
        effective_keys = await code_services_repository.get_effective_service_keys(
            db,
            tenant.id,
        )
        if not effective_keys:
            return WhatsAppConsoleResponse(
                reply=_i18n_t(locale, "wa.tenant.codigo.no_code_services_client")
            )

        service_list = _build_unauth_service_page(effective_keys, 0, locale)
        new_session = await session_service.create_session(session_key)
        new_session.flow = _UNAUTH_CODIGO_FLOW
        new_session.step = _UNAUTH_CODIGO_STEP_SERVICE
        new_session.temp_data = {
            "codigo_effective_keys": effective_keys,
            "codigo_current_page": 0,
        }
        await session_service.save_session(new_session)
        return WhatsAppConsoleResponse(
            reply=_i18n_t(
                locale,
                "wa.tenant.codigo.service_prompt",
                service_list=service_list,
            )
        )
```

Do **not** change the existing retry (`1`), back (`2`), cancel (`0`), or unknown-message fallback behavior.

- [ ] **Step 4: Run the unauthenticated endpoint tests to verify they pass**

Run:

```bash
cd backend && uv run pytest \
  tests/test_whatsapp_endpoint.py::test_unregistered_codigo_trigger_restarts_awaiting_result_and_cancels_active_job \
  tests/test_whatsapp_endpoint.py::test_unregistered_codigo_trigger_restarts_when_cancel_helper_noops \
  tests/test_whatsapp_endpoint.py::test_unregistered_codigo_trigger_restarts_with_invalid_lookup_job_id \
  tests/test_whatsapp_endpoint.py::test_unregistered_codigo_non_trigger_still_returns_still_checking \
  tests/test_whatsapp_endpoint.py::test_unregistered_codigo_result_retry_requeues_even_if_old_job_pending \
  -v
```

Expected: PASS for all 5 tests.

- [ ] **Step 5: Commit the unauthenticated-flow fix**

Run:

```bash
git add backend/app/api/v1/endpoints/integrations/console_handlers.py backend/tests/test_whatsapp_endpoint.py
git commit -m "fix: restart unauth codigo flow from awaiting result"
```

---

### Task 4: Update docs and run the full verification pass

**Relevant skills during execution:**
- `docs`
- `superpowers:verification-before-completion`
- `requesting-code-review`

**Files:**
- Modify: `docs/architecture/whatsapp-console-flow.md:329-360`
- Verify: `backend/tests/test_mailbox_persistence.py`, `backend/tests/test_tenant_console_service.py`, `backend/tests/test_whatsapp_endpoint.py`

- [ ] **Step 1: Update the architecture doc**

In `docs/architecture/whatsapp-console-flow.md`, update the tenant post-result table row and the unauthenticated flow description.

Replace the current tenant post-result table block with this version:

```markdown
#### Post-result response (``awaiting_result`` step)

| User input | Behavior |
|------------|----------|
| ``1`` | **Retry** — re-set ``pending_lookup_intent`` with same service_key/target_email. Backend creates a new lookup job. Returns "buscando...". |
| ``2`` | **Back to services** — clear session, show codigo service list again (page 0). |
| ``0`` | **Cancel** — clear session, return goodbye, n8n closes Evolution session. |
| ``code`` / ``codigo`` / ``código`` | **Restart** — best-effort cancel the active lookup job referenced by the current Redis session, clear the session, and start codigo again from service selection. |
| Other | **Still checking** — keep session alive, return "Still searching..." with retry/back/cancel options. |
```

Then replace the last sentence of the unauthenticated step 6 with this version:

```markdown
6. When the user replies to the result notification, ``_handle_unauth_codigo_result`` handles: ``1`` Retry, ``2`` Back to services, ``0`` Cancel, and ``code|codigo|código`` Restart (best-effort cancelling only the session-linked ``lookup_job_id`` before rebuilding the service list).
```

- [ ] **Step 2: Run the focused regression suite**

Run:

```bash
cd backend && uv run pytest \
  tests/test_mailbox_persistence.py::TestMailboxLookupRepository \
  tests/test_tenant_console_service.py::TestCodigoFlow \
  tests/test_whatsapp_endpoint.py -k "codigo" \
  -v
```

Expected: PASS for the repository tests, tenant codigo tests, and codigo-related endpoint tests.

- [ ] **Step 3: Run the full backend test suite**

Run:

```bash
cd backend && uv run pytest
```

Expected: PASS for the full backend suite.

- [ ] **Step 4: Commit docs and verified finish state**

Run:

```bash
git add docs/architecture/whatsapp-console-flow.md
git commit -m "docs: describe codigo restart from awaiting result"
```

- [ ] **Step 5: Request review before claiming completion**

Use the review workflow after tests are green:

```text
Relevant next skill: superpowers:requesting-code-review
Ask for review only after attaching the exact verification evidence:
- repository helper tests passed
- tenant codigo tests passed
- unauth codigo endpoint tests passed
- full backend suite passed
```

---

## Final verification checklist

- [ ] `cancel_active_job_if_present()` exists and is exported.
- [ ] The helper only mutates `pending` / `processing` jobs.
- [ ] Tenant `awaiting_result` treats `code|codigo|código` as restart.
- [ ] Unauth `awaiting_result` treats `code|codigo|código` as restart.
- [ ] Malformed `lookup_job_id` does not block restart.
- [ ] Unknown non-trigger messages still return `still_checking`.
- [ ] Docs explain the new restart behavior and the session-linked cancellation scope.
- [ ] `cd backend && uv run pytest` passed.

## Self-review

- **Spec coverage:** Covered repository helper, tenant restart path, unauth restart path, malformed-ID resilience, unchanged `1/2/0` semantics, docs, and verification.
- **Placeholder scan:** No `TODO`, `TBD`, “similar to above”, or unspecified commands remain.
- **Type consistency:** The plan consistently uses `cancel_active_job_if_present(db, job_id, tenant_id=...)`, `lookup_job_id`, `pending|processing`, and `error_code="user_cancelled"` across all tasks.
