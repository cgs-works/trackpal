# Quality Guidelines

> Backend quality gates used in Trackpal.

## Required Patterns

- Async FastAPI handlers and SQLAlchemy async sessions.
- Thin endpoint handlers, business logic in services.
- Reusable query logic in repositories.
- Shared input normalization via `app/core/input_validation/*`.
- i18n-aware user errors via `UserFacingError` + endpoint translation.

## Forbidden Patterns

- New monolith files >500 LoC (target <=300 when feasible).
- SQL in API endpoints unless urgent temporary hotfix.
- Hardcoded frontend-visible translation strings in services.
- Committing debug prints/temp code.

## Scenario: WhatsApp tenant subscriptions prompts must use i18n keys

### 1. Scope / Trigger
- Trigger: tenant console subscriptions edit prompts were hardcoded in Spanish inside service constants.

### 2. Signatures
- Constants contract:
  - `SUBSCRIPTIONS_EDIT_PROMPT_KEYS: dict[str, str]` (field -> i18n key)
- Runtime contract:
  - `self._t(key: str, **kwargs) -> str` resolves locale-aware message.

### 3. Contracts
- `subscription_constants.py` must expose keys, not localized message bodies.
- `subscriptions_edit.py` must call `_t(...)` for prompt rendering.
- WA catalogs must contain matching keys in both ES and EN.

### 4. Validation & Error Matrix
- Unknown edit field -> `KEY_SUBSCRIPTIONS_EDIT_ERROR_INVALID_FIELD`.
- Missing i18n key -> engine fallback warning + non-crash response.

### 5. Good/Base/Bad Cases
- Good: map `"streaming_email" -> "wa.tenant.subscriptions.edit.streaming_email_prompt"` then `_t(...)`.
- Base: keep field routing map (`1..7`) unchanged.
- Bad: inline `"✏️ *Editar Suscripción* ..."` in constants.

### 6. Tests Required
- Focused backend tests:
  - tenant console edit flow + subscriptions flow tests.
  - assert responses vary by locale/catalog and include expected key content.
- Regression: run WhatsApp tenant console subset.

### 7. Wrong vs Correct
#### Wrong
```python
SUBSCRIPTIONS_EDIT_PROMPTS = {"streaming_email": "✏️ *Editar Suscripción* ..."}
```
#### Correct
```python
SUBSCRIPTIONS_EDIT_PROMPT_KEYS = {
    "streaming_email": "wa.tenant.subscriptions.edit.streaming_email_prompt",
}
prompt = self._t(SUBSCRIPTIONS_EDIT_PROMPT_KEYS[field])
```

## Scenario: WhatsApp tenant subscriptions filtered list must be interactive and paginated

### 1. Scope / Trigger
- Trigger: filtered subscriptions list mixed hardcoded Spanish labels and inconsistent navigation (`0` missing in some views, no stable pagination commands).

### 2. Signatures
- Formatter signature:
  - `_format_subscription_list(..., page: int = 1, total_pages: int = 1) -> str`
- Flow handlers:
  - `_handle_subscriptions_filter(...)` initializes paginated list context.
  - `_handle_subscriptions_list(...)` routes `8/9` navigation and `1..7` selection.

### 3. Contracts
- Session temp contract:
  - `temp_data['status']`: selected filter status
  - `temp_data['page']`: current page (1-based)
- Selection map contract:
  - Rebuilt per page with keys `"1".."7"` only.
- Command contract in list step:
  - `0` cancel/exit (global reset path)
  - `8` previous page (if `page > 1`)
  - `9` next page (if `page < total_pages`)
- WA i18n keys required in ES/EN catalogs:
  - list header, status labels, detail labels, page navigation labels.

### 4. Validation & Error Matrix
- `8` on first page -> localized invalid option/keep page.
- `9` on last page -> localized invalid option/keep page.
- Selection outside `1..7` current map -> localized invalid option.
- Missing i18n key -> fallback warning; response must not crash.

### 5. Good/Base/Bad Cases
- Good: list with >7 records shows 7 items + `8`/`9` nav + `0` cancel.
- Base: list with <=7 records shows only `1..N` + `0` cancel.
- Bad: rendering all subscriptions in one page or mapping `8/9` to subscription IDs.

### 6. Tests Required
- Focused backend tests:
  - tenant console subscriptions list flow with >7 records.
  - assert page transitions on `8`/`9`.
  - assert `selection_map` keys limited to `1..7` each page.
  - assert `0` appears in rendered list and still exits flow.
- Regression command:
  - `cd backend && uv run pytest tests/test_tenant_console_service.py -v -k "subscriptions"`

### 7. Wrong vs Correct
#### Wrong
```python
for i, subscription in enumerate(all_subscriptions, 1):
    options.append(f"{i}️⃣ ...")
# No explicit 0, no page navigation
```
#### Correct
```python
visible = filtered[(page-1)*7 : page*7]
session.selection_map = {str(i): sub.id for i, sub in enumerate(visible, 1)}
# 8 prev if page>1, 9 next if page<total_pages, 0 cancel always
```

## Scenario: External API integration contract must be verified against deployed server

### 1. Scope / Trigger
- Trigger: Integration code written for Evolution Go (Go/Gin) while deployed server was Evolution API v2.4.0 (Node/Express). Result: 403 "This name 'undefined'" because Express didn't parse body the same way.

### 2. Signatures
- Server probe: `GET $BASE_URL/` returns `{"version":"2.4.0", ..., "manager":"..."}` + headers reveal framework (`X-Powered-By: Express` vs Gin)
- Direct test: `curl -v $BASE_URL/instance/create` with exact payload proves whether contract is correct

### 3. Contracts
- Before coding against any external API endpoint, verify:
  1. Deployed server version via root `/` endpoint
  2. Actual response headers (framework signature)
  3. Raw curl test of target endpoint with example payload
  4. Response shape matches documented contract
- If docs live in a local repo, they may describe a different version than deployed

### 4. Validation & Error Matrix
- 403 + "name 'undefined'" + `X-Powered-By: Express` → server is Node/Express, not Go/Gin
- 401/403 with no body → `apikey` header mismatch
- 200 with unexpected response shape → docs contract != deployed contract

### 5. Good/Base/Bad Cases
- Good: Probe server first, confirm version matches expected contract, then write integration
- Base: Write code against local docs, test against deployed, debug mismatch
- Bad: Write code against local docs, ship, discover mismatch only after deployment

### 6. Tests Required
- Integration test should probe `GET $BASE_URL/` and assert `version` in response as a connectivity check
- Mock-based unit tests must not silently pass when real contract differs

### 7. Wrong vs Correct
#### Wrong (blind trust)
```python
# Code written against local evolution-go repo docs
# but deployed server is evolution-api v2.4.0 (Express)
payload = {"name": name, "token": token}
response = await client.post("/instance/create", json=payload)
# → 403 "This name 'undefined'", server didn't parse correctly
```
#### Correct (probe first)
```python
# Probe server first
root = await client.get("/")
version = root.json().get("version")

# If version != expected, stop or adapt
if version != config.expected_evolution_version:
    logger.warning(f"Server version {version} != expected {config.expected_evolution_version}")

# Test raw endpoint before integrating
probe = await client.post("/instance/create", json={"name": "ping", "token": "ping"})
assert probe.status_code != 403, f"Body parsing failed for /instance/create"
```

## Scenario: WhatsApp client console must route by instance before identity

### 1. Scope / Trigger
- Trigger: client WhatsApp console required same phone in different tenants to not leak data, and same phone as tenant+client within one tenant to prompt mode selection.

### 2. Signatures
- Console endpoint: `POST /api/v1/integrations/n8n/console` accepts `{"instance": str, "phone": str, "message": str}`.
- Routing entry:
  - `_route_by_instance(instance: str, phone: str, msg: str) -> WhatsAppConsoleResponse`
- Ambiguity handler:
  - `_handle_ambiguity(phone: str, msg: str, locale: str) -> WhatsAppConsoleResponse`
- Redis session key for mode:
  - `wa:mode:{phone}` stores `"tenant"` or `"client"` value

### 3. Contracts
- Config env var: `MASTER_WHATSAPP_INSTANCE` — literal name of master instance.
- If `instance == MASTER_WHATSAPP_INSTANCE`: route only to master flow. Never fallback to tenant/client.
- If `instance != MASTER_WHATSAPP_INSTANCE`:
  1. Lookup tenant by `evolution_instance_name` via `tenants_repository.get_by_instance()`.
  2. Within resolved tenant: check `tenant.whatsapp_phone` (tenant admin) and `clients` table by `(tenant_id, phone)`.
- Only one match → route to that identity flow.
- Both match (tenant + client) → prompt mode selection, persist decision in Redis `wa:mode:{phone}`.
- Mode persists until `0`, `salir`, or `/menu`.
- Exit (`0` / `salir`) must return `status="closed"` in response payload for n8n/Evolution Go `change-status` node.
- Response shape is `WhatsAppConsoleResponse(reply=..., status=str|None)`. `status` field is omitted when `None` via `model_serializer`.

### 4. Validation & Error Matrix
- Unknown instance (no tenant found) → respond with access denied.
- Client not precreated/inactive → respond `"Acceso denegado, no tienes una cuenta activa."` (via i18n key `wa.client.access_denied`).
- Tenant inactive → respond access denied.
- Duplicate phone within same tenant (legacy data) → respond generic error message without stacktrace (no 500).
- Mode prompt invalid input → loop back to prompt.
- Exit from ambiguity → clear `wa:mode:{phone}` from Redis, return `status="closed"`.

### 5. Good/Base/Bad Cases
- Good: tenant-instance A → client in tenant A → access own profiles/subscriptions. Same phone in tenant B → no data leak.
- Good: phone is both tenant admin and client in same instance → mode prompt works, chosen mode persists until exit.
- Base: phone not registered in resolved tenant → access denied generic.
- Bad: mixing tenant A client data into tenant B response.
- Bad: sending `status="closed"` on non-exit responses (breaks compatibility).

### 6. Tests Required
- Client console tests must cover:
  - `instance == MASTER_WHATSAPP_INSTANCE` routes to master only
  - tenant instance resolves correct tenant
  - client in tenant A data isolated from tenant B
  - same phone as tenant+client → ambiguity prompt shows
  - ambiguity mode selection persists across messages until exit
  - `/menu` and `0` reset mode and return `status="closed"`
  - inactive client gets access denied
  - inactive tenant blocks client
- Regression: existing tenant console wizard, master console, and WhatsApp endpoint tests pass unchanged.
- Command: `cd backend && uv run pytest tests/test_client_console_service.py -v`.

### 7. Wrong vs Correct
#### Wrong
```python
# Global precedence: master > tenant > client by phone only
# No instance scoping — client from tenant A can leak into tenant B
user = await identify_by_phone(phone)
if user.role == "master":
    return master_flow(...)
elif user.role == "tenant":
    return tenant_flow(...)
```

#### Correct
```python
# Instance-first routing
if instance == config.master_whatsapp_instance:
    return master_flow(phone, msg)

tenant = await tenants_repository.get_by_instance(db, instance)
if not tenant:
    return access_denied(locale)

# Resolve identity within tenant context
tenant_match = tenant.whatsapp_phone == phone
client_match = await clients_repository.get_active_client_by_tenant_phone(db, tenant.id, phone)

if tenant_match and client_match:
    return handle_ambiguity(phone, msg, locale)
elif tenant_match:
    return tenant_flow(phone, msg, tenant)
elif client_match:
    return client_flow(phone, msg, client_match)
else:
    return access_denied(locale)
```

## Scenario: WhatsApp LID must never be normalized as phone

### 1. Scope / Trigger
- Trigger: inbound WhatsApp payload arrives with `remoteJid`/sender as `@lid`, and normalization strips suffix then uses LID digits as canonical phone.

### 2. Signatures
- n8n Parse Input must forward:
  - `phone` from `senderPn` only (when available)
  - `sender_lid` separately for `@lid` paths
- Backend endpoint request shape supports optional LID:
  - `{"phone": str|None, "sender_lid": str|None, "instance": str|None, "message": str}`

### 3. Contracts
- `normalize_phone()` returns `None` for inputs containing `@lid`.
- Identity resolution precedence:
  1. canonical phone lookup
  2. fallback LID lookup (`whatsapp_lid`)
- Instance-first routing (`_route_by_instance`) must support LID for tenant/client branches and ambiguity handling.
- Progressive fill required: when request has `senderPn` + `senderLid`, persist/update `whatsapp_lid` on matched identity.
- n8n must preserve original `remoteJid` for outbound reply target.

### 4. Validation & Error Matrix
- `@s.whatsapp.net` + valid phone -> existing flow unchanged.
- `@lid` + `senderPn` -> resolves by phone; `whatsapp_lid` gets updated.
- `@lid` without `senderPn`, known `whatsapp_lid` -> resolves by LID.
- `@lid` without mapping -> deterministic unknown-access reply.

### 5. Good/Base/Bad Cases
- Good: sender `123@s.whatsapp.net`, senderLid present -> reply works, LID persisted.
- Base: sender only `abc@lid`, already mapped -> resolve by LID and continue flow.
- Bad: treating `abc@lid` digits as phone and searching phone columns.

### 6. Tests Required
- `tests/test_phone_normalizer.py`:
  - assert `@lid` input returns `None`.
- `tests/test_whatsapp_endpoint.py`:
  - `@s.whatsapp.net` regression pass
  - `@lid` + `senderPn` resolves and persists LID
  - `@lid` + persisted LID resolves
  - unknown `@lid` denied deterministically
  - instance-first tenant/client LID routing and ambiguity branch deterministic

### 7. Wrong vs Correct
#### Wrong
```python
phone = normalize_phone("12345678901234@lid")  # "12345678901234"
identity = await auth_service.identify_by_phone(db, phone)
```

#### Correct
```python
phone = normalize_phone(sender_pn) if sender_pn else None
sender_lid = raw_sender_lid if raw_sender_lid and raw_sender_lid.endswith("@lid") else None
identity = await auth_service.identify_by_contact(db, phone=phone, sender_lid=sender_lid)
```

## Scenario: Mail lookup polling contract must be tenant-scoped and target-email-bound

### 1. Scope / Trigger

- Trigger: n8n mail lookup polling (`/integrations/n8n/mail/lookups/{job_id}`) and worker extraction flow for tenant mailbox codes.

### 2. Signatures

- API create: `POST /api/v1/integrations/n8n/mail/lookups`
- API poll: `GET /api/v1/integrations/n8n/mail/lookups/{job_id}?tenant_id=<uuid>`
- Request schema: `LookupCreateRequest(service_key, target_email, tenant_instance|tenant_id)`
- Response schema: `LookupStatusResponse(job_id, status, result_type, result_value?, error_code?)`

### 3. Contracts

- `tenant_id` is mandatory for poll in n8n integration path.
- `job_id` must always be resolved with tenant scope (never raw job lookup only).
- `target_email` is required on create.
- Worker must filter candidate emails by `target_email` content semantics (subject/body), not only provider recipient headers.
- WhatsApp->n8n handoff must carry both `lookup_job_id` and `tenant_id` for polling.

### 4. Validation & Error Matrix

- Missing `tenant_id` on poll -> 422 validation error.
- `job_id` not owned by `tenant_id` -> 404 not found.
- Missing/invalid `target_email` -> safe validation error (`missing_target_email` / 400).
- OAuth refresh `invalid_grant` -> mailbox `revoked`, clear tokens, job fails with safe `error_code=mailbox_revoked`.
- Non-transient provider failures -> explicit safe `error_code` (`auth_failed`, `permission_denied`, `provider_config_error`), not generic `internal_error`.

### 5. Good/Base/Bad Cases

- Good: tenant polls own job with `tenant_id`; target email present in mail body; returns `code|url`.
- Base: tenant polls own job, no matching mail in 5m window; returns `not_found`.
- Bad: tenant B polls tenant A job by guessed `job_id`; endpoint leaks status/result.

### 6. Tests Required

- API integration:
  - poll without `tenant_id` -> 422
  - cross-tenant poll with valid foreign `job_id` -> 404
  - create without `target_email` -> validation error
- Worker/service:
  - `target_email` content filter accepts matching subject/body and rejects non-matching candidates
  - OAuth refresh success path retries provider fetch
  - OAuth `invalid_grant` marks mailbox revoked and maps error code safely
- WhatsApp console contract:
  - when `lookup_job_id` present, response also includes `tenant_id` for n8n polling scope

### 7. Wrong vs Correct

#### Wrong

```python
job = await mailbox_lookup_repository.get_job(db, job_id)
```

#### Correct

```python
job = await mailbox_lookup_repository.get_job(db, job_id, tenant_id=tenant_id)
```

## Scenario: WhatsApp `codigo` lookup must be durable before poll handoff

### 1. Scope / Trigger

- Trigger: backend returned `lookup_job_id` and `tenant_id` to n8n, but immediate poll returned 404 and DB had no row for that `job_id`.
- Root condition: `codigo` flow emitted poll contract before durable DB commit boundary.

### 2. Signatures

- Tenant console integration response contract:
  - `WhatsAppConsoleResponse(reply: str, lookup_job_id?: str, tenant_id?: str)`
- Poll contract:
  - `GET /api/v1/integrations/n8n/mail/lookups/{job_id}?tenant_id=<uuid>`
- Central orchestration boundary:
  - `mailbox_lookup_repository.create_job(...)`
  - `db.flush()` + `db.commit()` before emitting `lookup_job_id`
  - `enqueue_job(redis_manager, job.id)`

### 3. Contracts

- `codigo_flow` is dialog-only for lookup creation trigger:
  - validates service/email
  - stores lookup intent in session temp data
  - does not persist job and does not enqueue
- Integration handler owns lifecycle:
  - read intent
  - create job + commit durable row
  - enqueue worker job
  - resolve tenant scope
  - clear pending intent after success path
  - emit `lookup_job_id` and `tenant_id` only on success
- `tenant_id` remains required in poll API; no scope relaxation.

### 4. Validation & Error Matrix

- Intent missing in session -> reply only, no `lookup_job_id`.
- Mailbox missing/disconnected -> safe reply, no `lookup_job_id`.
- `create_job`/commit fails -> safe reply, no `lookup_job_id`.
- Enqueue fails after commit -> compensating delete attempt.
- Compensating delete fails -> mark job `failed` with `error_code=queue_unavailable`, critical log, no `lookup_job_id`.
- Poll with wrong `tenant_id` -> 404.

### 5. Good/Base/Bad Cases

- Good: tenant sends final `codigo` email step; response includes `lookup_job_id` and DB row exists immediately.
- Base: flow returns `buscando...` without lookup fields when mailbox unavailable.
- Bad: returning `lookup_job_id` from uncommitted transaction or from session-only state.

### 6. Tests Required

- Unit/flow tests:
  - `codigo_flow` does not create/enqueue directly.
  - session stores intent payload, not `pending_job_id` generated by flow side-effects.
- Handler tests:
  - returns `lookup_job_id` only after commit+enqueue success.
  - enqueue failure path compensates and suppresses lookup fields.
- Integration API tests:
  - response lookup contract job is pollable with correct `tenant_id` (not 404).
  - poll with wrong `tenant_id` remains 404.

### 7. Wrong vs Correct

#### Wrong

```python
# Flow creates row + flush only, then handler returns lookup_job_id.
job = await mailbox_lookup_repository.create_job(...)
await db.flush()
return WhatsAppConsoleResponse(lookup_job_id=str(job.id), tenant_id=tenant_id)
```

#### Correct

```python
# Flow stores intent; handler orchestrates durable creation.
job = await mailbox_lookup_repository.create_job(...)
await db.flush()
await db.commit()  # durability boundary

if not await enqueue_job(redis_manager, job.id):
    # compensate: delete or mark failed(queue_unavailable)
    ...
    return WhatsAppConsoleResponse(reply=reply)

return WhatsAppConsoleResponse(
    reply=reply,
    lookup_job_id=str(job.id),
    tenant_id=str(tenant.id),
)
```

## Scenario: WhatsApp console global-exit contract inside active flows

### 1. Scope / Trigger
- Trigger: legacy master/tenant/client sub-flows treated `0` as local cancel or invalid input, causing inconsistent exit behavior and broken close-session detection.

### 2. Signatures
- Entry points:
  - `WhatsAppMasterConsoleFacade.process_message(...)`
  - `WhatsAppTenantConsoleFacade.process_message(...)`
  - `WhatsAppClientConsoleFacade.process_message(...)`
- Response contract:
  - `WhatsAppConsoleResponse(reply: str, status: str | None = None)`

### 3. Contracts
- `0` is reserved for global exit only.
- `9` is local back action in interactive flows.
- Global exit must clear auth/conversation state and return goodbye reply compatible with i18n.
- n8n close-session detection depends on backend `status="closed"` in merge payload when exiting.

### 4. Validation & Error Matrix
- `0` during active flow -> logout path (not local cancel/menu).
- `9` in steps with back support -> previous step/menu.
- Unknown action in step -> localized invalid-option prompt; no implicit exit.
- Merge payload missing `status` -> n8n cannot close session reliably.

### 5. Good/Base/Bad Cases
- Good: user in edit/create/detail step sends `0` -> session cleared + logout confirmation.
- Base: user sends `menu` or `/menu` -> reset/menu contract preserved.
- Bad: `0` treated as field value or local cancel in CRUD step.

### 6. Tests Required
- `tests/test_whatsapp_logout_flow.py`: assert auth session cleared and no touch on `0`.
- Master legacy flow tests: use `menu` for reset behavior where contract is reset-not-exit.
- Endpoint integration tests: assert exit responses include closure-compatible semantics.

### 7. Wrong vs Correct
#### Wrong
```python
if msg == "0":
    return self._with_main_menu("🚫 Operación cancelada.")
```
#### Correct
```python
if msg == "0":
    await auth_session_service.clear_auth_session(phone)
    return self._goodbye_reply(locale)
```

## Scenario: Code-services governance contract (global catalog + tenant selection)

### 1. Scope / Trigger
- Trigger: Bug 05 introduced separate code-service governance and required strict API/DB contracts across backend + UI + WhatsApp.

### 2. Signatures
- Models/migration:
  - `code_service_global_status(service_key PK, is_active, updated_at)`
  - `tenant_code_service_selections(tenant_id, service_key FK -> code_service_global_status.service_key)`
- APIs:
  - `PUT /api/v1/code-services/global`
  - `PUT /api/v1/code-services/tenants/me`
  - `PUT /api/v1/code-services/tenants/{tenant_id}`

### 3. Contracts
- Source of truth for allowed keys is backend catalog.
- Tenant selection persisted by full replacement (last-write-wins transaction).
- Effective WhatsApp list = `tenant_selected ∩ global_active`, sorted by visible label.
- Invalid `service_key` must return HTTP 400 (not 422).
- Globally disabled but tenant-selected services remain persisted and must be represented as disabled in UI.

### 4. Validation & Error Matrix
- Unknown key in payload -> `400 invalid_service_key`.
- Missing FK consistency in DB -> migration/model bug; prevent by FK on `service_key`.
- Empty tenant selection -> no fallback list; role-specific no-config messaging.

### 5. Good/Base/Bad Cases
- Good: tenant sends valid subset; backend replaces selection atomically.
- Base: master toggles service inactive; tenant selection remains stored but unavailable in effective list.
- Bad: endpoint relies only on Pydantic enum and returns 422, violating product contract.

### 6. Tests Required
- `tests/test_code_services.py`: strict 400 on invalid keys, permission matrix, replacement semantics.
- `tests/test_tenant_console_service.py`: code flow reflects effective list and no-config behavior.
- Migration/ORM checks: FK from tenant selection to global table enforced.

### 7. Wrong vs Correct
#### Wrong
```python
class TenantCodeServiceUpdateRequest(BaseModel):
    service_keys: list[Literal[...]]
# invalid payload returns 422
```
#### Correct
```python
payload.validate_keys()  # manual contract validation
if error:
    raise HTTPException(status_code=400, detail="invalid_service_key")
```

## Testing Requirements

- Run backend suite before completion: `cd backend && uv run pytest -v`.
- For scoped edits run focused tests first, then full suite.
- Keep async test patterns from `backend/tests/conftest.py` fixtures.
- Always probe external API endpoints directly with curl before assuming contract from docs.

## Review Checklist

- Layering respected (`api -> services -> repositories`).
- Endpoint status codes unchanged unless intentional.
- Imports stable through package `__init__.py` re-exports.
- No secrets in logs/errors.
- LoC policy respected; debt explicitly documented for 201-240 range.

## Evidence examples

- Full-suite baseline used in refactor: `781 passed, 1 skipped`.
- Endpoint package modularization: `backend/app/api/v1/endpoints/subscriptions/*`.
- Repository migration examples: `backend/app/repositories/*`.