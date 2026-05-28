# Remove OAuth2 mailbox flow and keep IMAP app-password only

## Goal

Simplify Trackpal mailbox ingestion by removing OAuth2 (Google/Microsoft) and supporting only IMAP app-password configuration.

## Requirements

1. Remove OAuth2 capability from backend API surface.
   - Remove OAuth start/callback routes for mailbox.
   - Remove OAuth orchestration usage from mailbox configuration flows.
2. Keep mailbox ingestion operational with IMAP app-password only.
   - Tenant can configure mailbox email + IMAP host/port/SSL + app password.
   - Existing lookup job flow (`codigo`) remains functional.
3. Remove OAuth2 controls from frontend mailbox panel.
   - No Google/Microsoft connect actions.
   - IMAP-only UX remains clear and usable.
4. Clean configuration and docs.
   - Remove OAuth env vars from active config usage and docs where mailbox setup is described.
   - Update architecture docs to IMAP-only model.
5. Tests updated to reflect IMAP-only model.
   - Remove/replace OAuth-centric tests.
   - Keep regression coverage for IMAP setup + mailbox lookup flow.

## Non-Goals

- Adding new mailbox protocols (POP3/Graph API/etc.).
- Building a new forwarding architecture in this task.

## Constraints

- No breakage in existing tenant mailbox lookup flow.
- Keep migrations/data model stable unless strictly required.
- Follow current file size policy (<500 LoC).

## Acceptance Criteria

- [ ] Backend no longer exposes `/tenant/mailbox/oauth/{provider}/start` and `/tenant/mailbox/oauth/{provider}/callback`.
- [ ] Frontend mailbox panel shows only IMAP app-password setup path.
- [ ] Mailbox create/update/test/disconnect works with IMAP-only flow.
- [ ] `codigo` lookup path still creates and polls jobs successfully.
- [ ] OAuth-specific config/docs references removed or marked deprecated.
- [ ] Relevant backend/frontend tests pass after refactor.
