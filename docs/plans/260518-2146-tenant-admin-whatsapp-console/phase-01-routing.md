# Phase 01: Routing by Role

## Objective

- Add role-based bifurcation in `POST /api/v1/integrations/n8n/console` so the same webhook can route Master, Tenant Admin, client-role, and unknown phones predictably.

## Complexity / Risk

- Complexity: S
- Risk: Low

## Scope

- Files/modules this phase may touch:
  - `backend/app/api/v1/endpoints/integrations.py`
  - `backend/tests/test_whatsapp_endpoint.py`
- Files/modules this phase must not touch:
  - `backend/app/services/whatsapp_master_console_facade.py`
  - n8n workflow JSON
  - Evolution API configuration

## Preconditions

- Current `/n8n/console` behavior is understood.
- `AuthService.identify_by_phone()` behavior for master/tenant/client/unknown is confirmed.
- **FINDING 3: `integrations.py` builds the Master path inline.** There is no `_handle_master_console()` helper. The executor MUST extract the inline Master logic into this helper FIRST, with no behavior change, THEN add the tenant branch beside it.
- **FINDING 4: Existing endpoint tests expect unknown and tenant phones to receive the Master login prompt.** Once routing is added, these assertions will fail. The executor MUST update them in this phase (or explicitly defer to Phase 06, but if deferred, set `xfail` to document the expected failure).

## Tasks

1. **Extract inline Master path into `_handle_master_console()` helper.**
   - Read `integrations.py` and capture the exact inline path that builds the Master flow.
   - Wrap it in `_handle_master_console()` with identical behavior — no changes.
   - Verify no Master behavior regression before proceeding.
2. Introduce a clean branching structure around `auth_service.identify_by_phone(db, phone)`.
   - Normalize the phone exactly once.
   - Call `identify_by_phone()` before constructing the role-specific reply path.
3. Add `_handle_tenant_console()` beside the extracted Master helper.
   - Keep `_handle_master_console()` behavior-preserving.
4. Implement role branches in `n8n_console()` / `whatsapp_console()`.
   - `master` → `_handle_master_console()` (extracted in step 1).
   - `tenant` → `_handle_tenant_console()`.
   - `client` → explicit admin-only rejection reply.
   - `None` / unknown → explicit no-access reply.
5. **Update endpoint contract tests to match new routing contract.**
   - Unknown phone: expect no-access reply, NOT Master login prompt.
   - Tenant phone: expect tenant menu, NOT Master login prompt.
   - Client phone: expect admin-only rejection.
   - Master phone: expect Master path unchanged.
   - JID normalization, response shape, Redis-unavailable: remain covered.
6. Preserve the existing Redis failure contract.
   - Missing Redis manager still returns `ContingencyReplyPolicy.TEMPORARY_UNAVAILABLE`.
   - Redis infrastructure exceptions still map to the same reply, not HTTP 500.
   - Application bugs still surface as 500 for observability.
7. Keep tenant-session namespacing as a logical-phone concern.
   - `_handle_tenant_console()` should pass `admin:{phone}` into the tenant facade/service path rather than changing `WhatsAppSessionService.SESSION_KEY_PREFIX`.
8. Record the new reply expectations for each role in `SUMMARY.md` during execution.

## Acceptance Criteria

- User-visible or system-observable result:
  - Master phones still enter the Master Console path.
  - Tenant phones are routed to the tenant console path.
  - Client-role phones are rejected with an admin-only message.
  - Unknown phones are rejected with a no-access message.
  - Redis-unavailable behavior remains a reply payload, not a 500.
- Required changed files:
  - `backend/app/api/v1/endpoints/integrations.py`
  - `backend/tests/test_whatsapp_endpoint.py`
- Required unchanged behavior:
  - API key authentication stays unchanged.
  - Response shape remains `{ "reply": string }`.
  - Master Console orchestration logic remains unchanged from the caller perspective.

## Verification

- Commands:
  - `cd backend && uv run pytest tests/test_whatsapp_endpoint.py -q`
- Expected results:
  - Endpoint tests pass for master, tenant, client, unknown, missing Redis, and JID-normalized phone scenarios.
- Evidence to record in `SUMMARY.md`:
  - pytest command and pass/fail summary.
  - Final branch/reply behavior for each role.

## Idempotence and Recovery

- Safe to re-run:
  - Endpoint tests with fake Redis manager are safe to rerun.
- Recovery if interrupted:
  - Keep the current Master inline block working until tenant-branch imports and helper wiring are complete.
- Rollback notes:
  - Remove tenant branch and helper imports, then restore the previous inline Master-only path if needed.

## Exit Criteria

- [ ] Endpoint calls `identify_by_phone()` before choosing a console path.
- [ ] Tenant route exists and is reachable.
- [ ] Client-role route returns an explicit rejection.
- [ ] Unknown phones return an explicit rejection.
- [ ] Master path remains behavior-compatible.
- [ ] Redis failure handling remains unchanged.
- [ ] Endpoint tests reflect the new routing contract.
