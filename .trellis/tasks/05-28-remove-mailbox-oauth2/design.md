# Design — Remove OAuth2, IMAP-only mailbox

## Scope

Cross-layer removal of OAuth2 mailbox integration while preserving IMAP ingestion pipeline.

## Current Components Affected

- Backend endpoint layer: `backend/app/api/v1/endpoints/mailbox.py`
- OAuth service layer: `backend/app/services/oauth_service/*`
- Frontend mailbox UI: `frontend/src/components/MailboxConfigPanel.vue`
- Config surface: `backend/app/core/config.py`, `.env.example`, docs
- Tests: `backend/tests/test_mailbox_oauth_imap.py` and related mailbox flow tests

## Target Architecture

1. Mailbox auth model: IMAP app-password only (`provider=imap_custom`, `auth_method=imap_app_password`).
2. API contract:
   - Keep: CRUD/test/disconnect mailbox endpoints.
   - Remove: OAuth start/callback endpoints.
3. Worker/provider contract:
   - Preserve IMAP provider and lookup pipeline unchanged.
   - OAuth providers can be removed from provider selection path (or made unreachable) in same refactor.
4. UI:
   - Present IMAP form as only connection method.
   - Remove OAuth provider select and popup flow.

## Risk Points

- Hidden dependencies on OAuth enum/values in schemas and repositories.
- Tests coupled to mixed OAuth+IMAP behavior.
- Stale docs/env keys causing operator confusion.

## Mitigations

- Remove routes first, then remove service wiring, then UI, then tests/docs.
- Run targeted mailbox/auth/lookup tests after each phase.
- Keep data compatibility by not dropping columns in this task unless necessary.
