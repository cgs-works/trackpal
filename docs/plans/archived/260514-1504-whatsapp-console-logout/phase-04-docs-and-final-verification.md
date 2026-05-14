# Phase 4 — Docs + final verification

**Complexity:** S

## Objective

Document the contextual meaning of `0` and ensure the full backend suite passes.

## Tasks (2–10 min each)

1. **Update docs to reflect the new semantics**
   - Edit one (keep minimal):
     - `docs/architecture/n8n-workflow.md` (add a short note under “What the backend does”) OR
     - `README.md` if it contains Master Console usage notes.
   - Document:
     - `0` logs out only when authenticated and at top-level.
     - `0` cancels sub-flows.
     - `menu` after logout restarts the login flow.

2. **Run full backend test suite**
   - `cd backend && uv run pytest -v`

3. **Sanity-check n8n remains transport-only**
   - Confirm `n8n/Trackpal WhatsApp Bot.json` needs no changes.

## Verification

- `cd backend && uv run pytest -v`

## Exit Criteria

- Docs mention the new `0` behavior and how to re-enter after logout.
- All backend tests pass.
- No n8n logic changes required.
