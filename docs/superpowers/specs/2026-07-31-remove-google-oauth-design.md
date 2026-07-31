# Remove Google OAuth from Mailbox Ingestion

**Status:** Approved

**Date:** 2026-07-31

## Goal

Remove Google OAuth mailbox connectivity from TrackPal and make Gmail App Password Connection the only production Mailbox connection method. Remove the OAuth implementation vertically across the backend, database, frontend, tests, configuration, generated Help, and current documentation while preserving TrackPal's JWT/Bearer authentication.

## Scope

This change removes Google OAuth only from Mailbox ingestion. It does not replace or rename FastAPI's `OAuth2PasswordBearer` mechanism used to transport TrackPal JWTs.

The implementation will also remove historical documents that describe Google OAuth as a supported Mailbox connection method:

- `docs/verification/google-oauth-demo.md`
- `docs/superpowers/plans/2026-07-30-gmail-only-mailbox-connection.md`
- `docs/superpowers/specs/2026-07-30-gmail-only-mailbox-connection-design.md`

Published Alembic migrations remain immutable even when they contain historical OAuth schema definitions. This removal design and its implementation plan remain as the intentional record explaining why the support was removed.

## Domain Model

### Mailbox

A Mailbox is the Tenant's single connected Gmail account used to retrieve access-code messages. It is connected exclusively through an App Password Connection.

### App Password Connection

App Password Connection is the sole production Mailbox connection method. It uses a Google-generated, revocable app password rather than the Google Account's primary password.

The domain no longer contains a variable Mailbox authentication method. Consequently, `auth_method` is removed instead of being retained with the constant value `app_password`.

### Retired Terms and States

The following concepts leave the active domain:

- Google Connection
- OAuth Mailbox
- OAuth token refresh
- OAuth grant revocation
- Mailbox `revoked` status
- `mailbox_revoked` worker outcome

An invalid or revoked app password is represented by the existing safe app-password authentication failure, not by an OAuth-specific revoked state.

## Architecture

### Mailbox API Module

The authenticated Mailbox interface remains small:

- get the current Mailbox;
- connect or replace it after validating an app password;
- test the stored connection;
- disconnect it.

The module no longer exposes OAuth start or callback routes. No compatibility route or HTTP 410 response is added; the removed routes return the router's normal 404 response.

### Mail Fetching Module

The Mail Lookup Worker continues to call one narrow `fetch_recent_emails(...)` interface. That module hides credential decryption, fixed Gmail IMAP settings, network access, and provider error translation.

The implementation becomes Gmail app-password-only. The authentication-method dispatcher and Gmail API OAuth adapter are removed. A test replacement may remain internal to the module, but production callers do not select an adapter or authentication method.

This preserves a deep module: callers know the Mailbox, lookup window, returned messages, and stable error modes, while IMAP details remain local to the implementation.

### Frontend Mailbox Module

The Settings Mailbox surface opens directly into the Gmail Setup Assistant. The assistant contains only:

1. instructions for creating a Google app password;
2. Gmail address and app-password collection;
3. connection validation feedback.

The method selector, OAuth disclosure, consent checkbox, popup, `BroadcastChannel`, OAuth callback messages, OAuth feature gate, and OAuth API function are removed.

The production `Mailbox` contract no longer contains `auth_method`. Demo Mailbox remains a separate browser-local representation and does not introduce a production authentication discriminator.

## Database Migration

A new forward Alembic migration performs the destructive transition. Existing published migrations are not edited.

### Upgrade

The migration executes in this order:

1. Drop the existing `ck_tenant_mailboxes_auth_method` constraint.
2. Delete every `tenant_mailboxes` row whose `auth_method = 'oauth'`.
3. Drop the OAuth credential and identity columns:
   - `oauth_provider_user_id`
   - `oauth_provider_email`
   - `oauth_access_token_encrypted`
   - `oauth_refresh_token_encrypted`
   - `oauth_token_expires_at`
   - `oauth_scope`
4. Drop `auth_method` because App Password Connection is the only remaining method.

Rows connected through app passwords remain intact, including their encrypted app password and connection monitoring fields.

### Downgrade

The downgrade restores the removed nullable OAuth columns and restores `auth_method` with `app_password` populated for surviving rows. It restores the historical constraint allowing `oauth` and `app_password` so the previous application version can start.

The downgrade cannot recover deleted OAuth Mailbox rows or token values. This irreversibility must be documented in the migration and deployment notes.

## Backend Changes

The implementation removes:

- `backend/app/services/oauth_service/`;
- `backend/app/services/mail_lookup_worker/providers/_google.py`;
- OAuth routes and callback HTML from the Mailbox endpoint;
- OAuth service construction and OAuth connection tests from `_mailbox_helpers.py`;
- OAuth configuration fields and `.env.example` entries;
- OAuth schemas and response fields;
- OAuth columns from `TenantMailbox`;
- OAuth and revoked status branches from worker provider types and worker error handling;
- OAuth-specific metrics and labels;
- imports and package exports made obsolete by these deletions.

The app-password connection retains validate-before-persist behavior. A rejected replacement must leave an existing Mailbox unchanged.

## Frontend Changes

The implementation removes:

- `frontend/src/features/admin/mailbox-config.ts`;
- `VITE_GMAIL_OAUTH_CONNECT_ENABLED` from `frontend/.env.example`;
- `startGoogleOAuth()` and OAuth response types;
- `oauth` from production Mailbox types;
- OAuth selector and consent states from `GmailSetupAssistant`;
- popup opening and `BroadcastChannel` handling from `MailboxSection`;
- OAuth-specific translations and tests.

The final assistant starts at the app-password instructions and preserves current responsive behavior, validation, loading states, safe error messages, and Help links.

## Runtime Flow

1. The Tenant Admin opens Mailbox Settings.
2. The Gmail Setup Assistant explains how to create an app password.
3. The Tenant Admin submits the Gmail address and app password.
4. The backend validates the credential against fixed Gmail IMAP settings before reading or mutating the existing Mailbox.
5. On success, the backend encrypts and persists the normalized app password and records a successful connection test.
6. Mail Lookup Jobs call the Mail fetching module, which reads recent Gmail messages through the app-password implementation.
7. Testing a connection repeats the stored-credential check.
8. Disconnecting deletes the Mailbox configuration and its encrypted credential.

## Error Handling

The supported connection errors remain:

- rejected credential: HTTP 400 with `gmail_app_password_rejected`;
- timeout or Gmail connectivity failure: HTTP 503 with `gmail_connection_unavailable`;
- missing Mailbox: the existing HTTP 404 response;
- unsupported removed OAuth routes: normal HTTP 404 routing behavior.

The worker retains transient and non-transient provider errors needed by app-password fetching. OAuth-only `RevokedMailboxError`, `mailbox_revoked`, token permission errors, and token refresh branches are removed.

Tenants whose OAuth Mailbox rows are deleted by the migration see the Mailbox as unconfigured and must reconnect with an app password.

## Documentation Changes

Update all current documentation to describe App Password Connection as the sole Mailbox method, including:

- `docs/SUMMARY.md`;
- Mailbox, API, schema, deletion, export, code-services, and product documentation where relevant;
- `backend/CONTEXT.md` and `frontend/CONTEXT.md`;
- bilingual Tenant Admin Mailbox Help;
- generated `backend/app/help/artifact.json`;
- environment examples and codebase structure references.

Remove OAuth verification instructions and the prior hybrid-connection Superpowers plan/spec listed in Scope.

References unrelated to Mailbox OAuth remain, especially TrackPal JWT/Bearer authentication and immutable historical Alembic migrations.

## Testing Strategy

### Migration Tests

Verify that the new migration:

- deletes OAuth Mailbox rows;
- preserves app-password Mailbox rows and encrypted credentials;
- removes all OAuth columns and `auth_method` on upgrade;
- restores the historical column shape and constraint on downgrade;
- documents that deleted OAuth data is not recoverable.

### Backend Tests

Verify through public module interfaces that:

- Mailbox connect validates before persistence;
- failed replacement preserves the prior connection;
- connection test uses the stored app password;
- disconnect removes the Mailbox;
- OAuth routes return 404;
- the worker fetch interface invokes only the app-password implementation;
- OAuth-specific tests and test fixtures are removed rather than retained as dead compatibility tests.

Run the full backend suite and Ruff checks.

### Frontend Tests

Verify that:

- the Gmail Setup Assistant starts with app-password instructions;
- Gmail address and app-password submission still work;
- no selector, OAuth consent, popup, feature flag, or callback listener exists;
- connected and disconnected Mailbox states render correctly without `auth_method`;
- Demo Mailbox behavior remains isolated and functional.

Run focused Vitest suites, the full frontend test suite, and the production build.

### Documentation Tests

Regenerate and verify the Help artifact. Update Help contract tests so the tutorial describes only the app-password flow.

## Acceptance Criteria

1. Production Mailbox connectivity works only with a Gmail app password.
2. Existing OAuth Mailbox rows are deleted during migration.
3. The final database schema has no OAuth columns and no `auth_method` column.
4. No OAuth start, callback, refresh, Gmail API fetch, consent, popup, or feature-gate code remains.
5. No OAuth-specific runtime metric, status, error class, schema, environment variable, or translation remains.
6. Current product, architecture, Help, and verification documentation no longer presents Google OAuth as supported.
7. The prior hybrid implementation plan, design, and verification guide are removed.
8. JWT/Bearer login behavior remains unchanged.
9. Google OAuth references remain only where required to migrate or remove historical state, preserve JWT/Bearer transport, document this removal, or assert through negative regression tests that removed routes stay absent.
10. Backend tests, frontend tests, Ruff, frontend production build, Alembic validation, and Help verification pass.

## Non-Goals

- Rewriting or squashing published Alembic migrations.
- Replacing TrackPal JWT/Bearer authentication.
- Supporting automatic conversion from OAuth tokens to an app password.
- Revoking Google grants remotely before deleting local OAuth rows.
- Adding another mailbox provider or authentication method.
- Refactoring unrelated Mail Lookup Worker, Settings, authentication, or Help behavior.
