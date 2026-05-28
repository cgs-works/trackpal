# Design — Fix n8n mail lookup 404

## Context

Observed failure:
- `POST /api/v1/integrations/n8n/console` returned `lookup_job_id` + `tenant_id`.
- Immediate poll `GET /api/v1/integrations/n8n/mail/lookups/{job_id}?tenant_id=...` returned 404.
- Supabase query by that `job_id` returned no row.

Root-cause hypothesis validated by code path:
- `codigo` flow creates job with `flush` and stores `pending_job_id` in session before durable commit boundary.
- Handler later emits `lookup_job_id` even when durability boundary is not guaranteed.

## Goals

1. Never emit `lookup_job_id` unless row exists durably in `mail_lookup_jobs`.
2. Keep strict tenant isolation in poll (`tenant_id` required + scoped query).
3. Preserve current UX contract (`buscando...` immediate reply, then n8n poll).

## Chosen Architecture

## 1) Full decoupling of `codigo_flow`

`codigo_flow` stops doing direct DB/Redis side-effects for job lifecycle.
It will only:
- validate flow state
- validate selected service and target email
- return intent payload for lookup creation

No `create_job`, no enqueue, no commit from flow module.

## 2) Central transaction boundary in integration handler

Transaction + orchestration moves to central handler path (tenant console integration layer):
- create job
- commit durable row
- enqueue to Redis
- resolve `tenant_id`
- clear `pending_job_id` only after success path above
- emit response with `lookup_job_id` + `tenant_id`

This ensures response contract is produced only after durable persistence.

## 3) Enqueue failure policy (compensating)

If `create_job+commit` succeeded but enqueue fails:
- compensation transaction tries hard-delete created job
- if delete fails, mark job `failed` with `error_code=queue_unavailable`, log critical
- response must not include `lookup_job_id`

## 4) Session state policy

`pending_job_id` cleanup timing:
- clear only after commit + enqueue + `tenant_id` resolution success
- keep state on earlier failure to avoid silent loss and enable controlled retry

## 5) Tenant source policy

`tenant_id` in response resolved via owner identity (`tenants_repository.get_by_owner(identity.user_id)`) per current isolation model.

## Non-Goals

- No relaxation of poll tenant scoping.
- No n8n schema redesign.
- No outbox implementation in this task.

## Affected Modules

- `backend/app/services/whatsapp_tenant_console_service/codigo_flow.py`
- `backend/app/api/v1/endpoints/integrations/console_handlers.py`
- Possibly small helper extraction under integrations endpoints/services for orchestration clarity.

## Risks and Mitigations

1. **Behavior drift in tenant flow**
   - Mitigation: regression tests for code/codigo path and session behavior.
2. **Compensation race/partial failure**
   - Mitigation: explicit fallback to `failed` terminal state + critical logs.
3. **Cross-tenant leakage**
   - Mitigation: keep existing `tenant_id` required poll check unchanged; add tests for wrong tenant_id.

## Validation Plan

- Backend unit + integration tests (required).
- n8n production execution evidence (required): execution IDs showing returned `lookup_job_id` then poll non-404 for correct tenant.
