# Implementation Plan — Remove OAuth2, keep IMAP-only

## Phase 1 — Backend API + schemas

- Remove OAuth start/callback handlers from `backend/app/api/v1/endpoints/mailbox.py`.
- Ensure mailbox upsert/test/disconnect paths work for IMAP-only.
- If schema enums/validators include OAuth-only values for this flow, tighten to IMAP-only where safe.

Validation:
- Run mailbox endpoint tests.

## Phase 2 — Service/provider cleanup

- Remove mailbox OAuth orchestration dependencies from mailbox path.
- Remove or isolate OAuth provider code paths so lookup pipeline relies on IMAP mailbox configs only.
- Keep job creation/poll endpoints intact.

Validation:
- Run mailbox lookup API + worker tests.

## Phase 3 — Frontend simplification

- Update `MailboxConfigPanel.vue` to IMAP-only UX.
- Remove OAuth buttons, states, popup handling, and related messages.

Validation:
- Frontend build.

## Phase 4 — Tests + docs + config

- Rewrite/remove OAuth-specific tests from `test_mailbox_oauth_imap.py`.
- Keep IMAP-focused tests.
- Update docs and env examples to IMAP-only mailbox setup.

Validation:
- Targeted test suite + optional full backend suite.

## Rollback

- Revert commit batch if IMAP flow regresses.
- Keep changes grouped by phase to allow surgical rollback.
