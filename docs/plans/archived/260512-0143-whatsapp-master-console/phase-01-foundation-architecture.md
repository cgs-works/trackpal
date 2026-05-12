# Phase 1: Foundation and Architecture Alignment

**Complexity:** M
**Dependencies:** None

## Objective

- Document and prepare the architectural shift to Redis-backed backend-owned WhatsApp Master Console state without changing product behavior yet.

## Preconditions

- PRD is approved at `docs/prds/260512-0143-whatsapp-master-console/PRD.md`.
- Existing backend tests pass before starting.
- No implementation from earlier brainstorming attempts remains in the working tree.

## Tasks

1. Context: read the PRD, `CONTEXT.md`, `CONTEXT-MAP.md`, and ADRs for auth and n8n/Evolution integration.
2. Context: inspect backend configuration patterns and dependency management.
3. Document: add an ADR for Redis-backed WhatsApp Master Console session state.
4. Document: update n8n/Evolution architecture docs to state n8n is transport-only for the Master Console.
5. Implement: add Redis URL/configuration setting using the existing settings pattern.
6. Implement: add Redis client initialization/lifecycle in the backend core layer.
7. Implement: add Redis dependency package using the existing backend dependency manager.
8. Verify: run the existing backend test suite to confirm no behavior changed.
9. Confirm: ensure documentation states Redis is ephemeral session state, not business data persistence.

## Verification

- Commands:
  - `cd backend && uv run pytest -v`
- Expected results:
  - Existing backend test suite passes.
  - Redis configuration does not require Redis to be available for unrelated tests.
  - ADR and architecture docs clearly describe backend-owned conversation logic and n8n transport-only responsibility.

## Exit Criteria

- Redis configuration is available through backend settings.
- Redis client lifecycle/dependency pattern is in place.
- ADR exists for Redis-backed WhatsApp Master Console session state.
- n8n/Evolution documentation no longer implies n8n owns Master Console conversation state.
- Existing tests pass.
