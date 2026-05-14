# Phase 5 — Documentation updates + full verification

**Complexity:** S

## Objective

Bring documentation in line with the new WhatsApp credential-authenticated console and complete final verification.

## Tasks (2–10 min each)

1. **Update ADR-0004 to remove “identify Master by phone” assumption**
   - Edit: `docs/adr/0004-sesion-whatsapp-redis.md`
   - Update the flow section to:
     - Require `wa:auth:{phone}` (auth session) before delegating to CRUD/menu.
     - Describe that phone is now **session context**, not primary identity.

2. **Update ADR-0003 to reinforce transport-only + no identity resolution in n8n**
   - Edit: `docs/adr/0003-integracion-n8n-y-evolution-api.md`
   - Ensure it explicitly states:
     - n8n does not filter instances for access.
     - n8n does not call `/identify` for Master Console authorization.

3. **Update architecture docs to match reality**
   - Edit: `docs/architecture/data-flow.md`
     - Add a short “WhatsApp Master Console (credential auth)” sub-flow describing login → auth session → console.
   - Edit: `docs/architecture/n8n-workflow.md`
     - Ensure placeholders/env var names match Phase 4.

4. **Add a short operational note about security trade-off**
   - Where appropriate (ADR or architecture doc):
     - Explicitly state the accepted trade-off: password over WhatsApp in exchange for flexibility.
     - Mention lockout mitigation and 15m TTL.

5. **Run full backend test suite and confirm no regressions**
   - Execute:
     - `cd backend && uv run pytest -v`

6. **Manual smoke checklist (local)**
   - Using `curl` or http client against local dev server (optional):
     - Unauthenticated request returns username prompt.
     - Successful login returns main menu.
     - After deleting auth key in Redis (or waiting TTL), next message prompts login again.

## Verification

- Documentation builds (basic sanity):
  - Ensure markdown files render and links resolve (manual).
- Backend tests:
  - `cd backend && uv run pytest -v`

## Exit Criteria

- ADRs and architecture docs no longer claim phone is the Master identity for WhatsApp.
- n8n export is secret-free and transport-only.
- Full backend test suite is green.
