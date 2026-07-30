# Gmail-Only Mailbox Connection Design

**Date:** 2026-07-30  
**Status:** Approved design  
**Scope:** TrackPal backend, frontend, private Help content, project documentation, and the public `trackpal-landing` repository

## Summary

TrackPal will support Gmail as its only production mailbox provider. Tenant Admins will connect the Central Lookup Mailbox through a two-step Gmail Setup Assistant using a Google app password. An optional Google OAuth connection remains available only when a frontend build-time release gate explicitly exposes it.

Microsoft, Outlook, and generic mailbox-provider support will be removed end-to-end. TrackPal will stop exposing IMAP terminology or configurable server details to users, while retaining Gmail IMAP internally as the implementation behind app-password connections.

The design is based on current official provider guidance:

- Google no longer supports third-party clients that authenticate with only the normal Google Account username and password. Eligible accounts with 2-Step Verification can use a 16-character app password when Sign in with Google is unavailable.
- Outlook.com requires OAuth2/Modern Authentication for IMAP.
- Exchange Online has disabled Basic Authentication for IMAP, and Microsoft states that this also prevents app passwords from working with applications that lack Modern Authentication.

Because TrackPal's password-based adapter uses Basic IMAP login, an Outlook app-password tutorial would be inaccurate. Microsoft support is therefore removed rather than presented as a connection method that may fail.

## Goals

1. Make Gmail the only supported mailbox provider.
2. Replace the technical IMAP form with a beginner-friendly, two-step Gmail Setup Assistant.
3. Never ask for or recommend the user's primary Google Account password.
4. Test an app password before persisting it.
5. Keep Google OAuth available as an optional new-connection path controlled by a frontend release gate that defaults to off.
6. Expand the existing mailbox Help topic with an accurate bilingual app-password tutorial based on official Google guidance.
7. Remove Microsoft and Outlook from code, tests, documentation, legal copy, and public product copy.
8. Preserve secret handling, tenant isolation, and the existing on-demand access-code lookup behavior.

## Non-Goals

- Supporting Outlook.com, Microsoft 365, Exchange Online, or Microsoft Graph.
- Supporting arbitrary IMAP providers or user-configurable mail servers.
- Accepting a normal Gmail password as a fallback.
- Implementing OAuth2 over IMAP.
- Revoking Google app passwords automatically; Google does not expose the generated credential as a revocable OAuth grant TrackPal can manage.
- Using the frontend OAuth release gate as a security control or backend feature kill switch.
- Creating a separate Help topic for app-password setup.

## Domain Language

### Central Lookup Mailbox

The Tenant's single connected Gmail account used to find access-code messages requested through TrackPal.

User-facing Spanish: **Correo central de búsqueda**.  
User-facing English: **Central Lookup Mailbox**.

### App Password

A Google-generated, revocable credential used instead of the account's primary password. It is the default Gmail connection method.

Avoid: email password, Gmail password, IMAP password.

### Google Connection

The optional Google OAuth method that grants TrackPal read-only Gmail access through Google's authorization screen.

OAuth may remain in technical or legal explanations, but the primary customer-facing label is **Conexión con Google** / **Google Connection**.

### Gmail Setup Assistant

The two-step Settings experience that first helps the Tenant Admin create an app password and then accepts the Google email address and generated credential.

Avoid exposing: IMAP, host, port, SSL, Basic Authentication.

### OAuth Connection Availability

Whether a frontend build offers the action for starting a new Google OAuth connection. This is not an operational OAuth kill switch and does not revoke or stop an existing OAuth mailbox.

## Product Decisions

### Gmail is the only provider

The production mailbox model no longer varies by provider. It varies only by authentication method:

```text
auth_method:
- app_password
- oauth
```

The backend owns Gmail connection details for app-password authentication:

```text
host = imap.gmail.com
port = 993
TLS = enabled
```

These values are not accepted from or returned to the product UI.

### OAuth release gate

The frontend adds:

```env
VITE_GMAIL_OAUTH_CONNECT_ENABLED=false
```

Rules:

- Missing, empty, or any value other than the exact string `true` means disabled.
- Disabled hides every control that starts a new Google OAuth flow.
- Enabled exposes the Google Connection alternative, existing disclosure, privacy link, affirmative consent checkbox, and continuation action.
- The gate does not alter backend endpoints, refresh behavior, lookup processing, or an already connected OAuth mailbox.
- A connected or revoked OAuth mailbox remains visible so the Tenant Admin can test or disconnect it. When the gate is off, the UI does not offer OAuth reconnection; the user may disconnect and use an app password.

The name deliberately includes `CONNECT` so operators do not mistake the value for a complete OAuth shutdown.

## Data Model

The `tenant_mailboxes` record remains one-to-one with a Tenant.

The target production fields are:

- `id`
- `tenant_id`
- `mailbox_email`
- `auth_method`: `app_password | oauth`
- `status`: `disconnected | connected | error | revoked`
- `app_password_encrypted`
- OAuth access token, refresh token, expiry, Google account identifier, and Google account email fields
- last connection test timestamp and safe error value
- created and updated timestamps

The implementation removes:

- provider as a variable production field
- `microsoft`
- `imap_custom`
- `imap_host`
- `imap_port`
- `imap_ssl`

`imap_password_encrypted` is renamed to `app_password_encrypted`.

### Migration

The migration is deterministic even though no production mailbox data needs preservation:

1. Preserve Google OAuth rows as `auth_method=oauth`.
2. Preserve password rows only when they represent Gmail (`imap.gmail.com`, port 993, TLS enabled), converting them to `auth_method=app_password`.
3. Remove Microsoft and unsupported custom-provider rows.
4. Rename the encrypted credential column.
5. Drop provider and configurable server columns.
6. Replace old constraints with the Gmail-only authentication-method constraint.

The Demo Mailbox remains a browser-local representation. Its display should identify Gmail without exposing connection controls, while its demo-only method remains outside the production persistence contract.

## Backend Modules and Interfaces

### App-password connection

The existing mailbox update operation becomes a Gmail app-password connection interface. The request contains only:

```json
{
  "mailbox_email": "codes@example.com",
  "app_password": "generated Google credential"
}
```

The backend:

1. Trims surrounding whitespace and removes grouping spaces from the supplied app password.
2. Does not attempt to identify a normal password by format; Gmail authentication is the source of truth.
3. Connects to Gmail using the fixed server configuration.
4. Persists the mailbox only after successful authentication.
5. Encrypts the normalized app password with the existing encryption module.
6. Records the mailbox as connected and records the successful test timestamp in the same operation.
7. Leaves persistence unchanged if authentication, networking, or timeout validation fails.

If a mailbox already exists and the operation is invoked directly, TrackPal validates the new credential first and replaces the existing method and secrets atomically only after success. A failed replacement leaves the working connection unchanged.

The interface may retain the current mailbox route to minimize caller surface, but provider and server fields are removed from its schema.

### Google OAuth

- Keep Google OAuth authorization, callback, token exchange, refresh, revocation handling, Gmail API fetch, disclosure, and affirmative consent.
- Keep the existing Google callback path to avoid unnecessary Google Console redirect-URI changes.
- Remove provider branching from the Google OAuth module where it no longer adds value.
- Remove Microsoft configuration, OAuth helpers, Graph adapter, routing branches, and tests.
- OAuth start and callback routes accept Google only.

### Lookup worker

The mailbox fetch seam routes by authentication method:

- `oauth` -> Gmail API adapter
- `app_password` -> Gmail app-password adapter using fixed Gmail IMAP settings

Rename generic IMAP modules and error language where doing so improves locality, while keeping protocol terminology inside implementation-level code when technically useful.

### Observability

Mailbox metrics and structured logs use Gmail as the fixed provider and retain authentication method as the varying dimension. Remove Microsoft-specific labels and branches without changing the existing secret-redaction policy.

## Frontend Experience

### Disconnected state

The Settings category opens the Gmail Setup Assistant.

#### Step 1: Create an app password

Show:

- Gmail and Central Lookup Mailbox heading.
- Explanation that Google generates a credential specifically for TrackPal.
- Explicit statement that TrackPal never requests the primary Google Account password.
- Short prerequisites and three-step summary.
- **Open Google** action to `https://myaccount.google.com/apppasswords`.
- **View full tutorial** action when private Help is enabled.
- **I already have the password** action to advance.

If OAuth connection availability is enabled, show **Use Google Connection** as a secondary path. It must not compete visually with the primary assistant.

#### Step 2: Connect Gmail

Show only:

- Google email address
- App password
- Show/hide credential control
- Back
- Connect Gmail

Do not restrict the address to `@gmail.com`, because eligible Google Workspace mailboxes may use business domains.

### Submission behavior

- Disable duplicate submissions while validating.
- On success, replace the assistant with the connected status card.
- On failure, preserve the email address and clear the app-password field.
- Do not keep the credential in browser storage or Zustand persistence.

### Connected state

Display the mailbox email, status, and a localized method label:

- **App Password**
- **Google Connection**

Retain Test Connection and Disconnect actions. Do not display IMAP server details.

### Contextual Help interface

Add a narrow Help module interface such as:

```ts
requestContextualHelp(HELP_TARGETS.mailbox)
```

The shared Contextual Help Sheet listens for the request, resolves the authorized topic through the existing Help index and target contract, and opens the topic without navigating or unmounting the Settings form.

The interface accepts a stable Help target rather than a translated title, DOM click simulation, or arbitrary topic content.

## Help Content

Expand the existing mirrored topic:

```text
tenant-admin.mailbox
```

Do not create a separate tutorial topic.

The English and Spanish bodies cover:

1. What the Central Lookup Mailbox does.
2. Why a business-managed mailbox is preferred.
3. The difference between a primary password and a Google app password.
4. Enabling 2-Step Verification.
5. Opening Google's App Passwords page.
6. Naming the credential TrackPal.
7. Copying the generated credential and entering it in TrackPal.
8. Connecting and confirming the expected Connected state.
9. Revoking or replacing the app password.
10. Diagnosing unavailable app passwords and connection errors.
11. Using Google Connection only when the current TrackPal deployment visibly offers it.

### Official limitations

The topic explains that App Passwords may be unavailable when:

- 2-Step Verification is not enabled.
- 2-Step Verification is configured only with security keys.
- The account is managed by a work, school, or other organization that restricts the feature.
- Advanced Protection is enabled.

It also explains that changing the main Google Account password revokes existing app passwords.

If app passwords are unavailable and Google Connection is not shown, the account cannot connect to that TrackPal deployment. The product must not recommend enabling less-secure-app access or entering the primary password.

### Safe Help rendering

Extend the private Help renderer and compiler only for the tutorial capabilities required here:

- ordered lists
- HTTPS Markdown links
- external links opened with `target="_blank"` and `rel="noopener noreferrer"`
- an explicit hostname allow-list containing `myaccount.google.com` and `support.google.com`
- locale parity for the set of external destination URLs

Reject non-HTTPS URLs, unknown hosts, malformed destinations, and executable or raw HTML content.

Official Help destinations:

- `https://myaccount.google.com/apppasswords`
- `https://support.google.com/accounts/answer/185833`

## Error Handling

Map implementation failures to safe, actionable product messages:

### Authentication rejected

Explain that Gmail did not accept the credential and that the user must generate a new app password rather than enter the primary account password.

Do not claim to know whether the user entered a normal password; Gmail's response is authoritative.

### Timeout or network failure

Explain that TrackPal could not reach Gmail and that no connection was saved. Allow retry.

### Feature unavailable

Explain the official Google eligibility causes. Offer Google Connection only when the frontend gate exposes it.

### OAuth revoked

Keep the revoked status. If Google Connection is available, offer reconnection; otherwise direct the user to disconnect and use an app password.

### Secret safety

Never log or return:

- app passwords
- OAuth access or refresh tokens
- raw Gmail authentication responses containing credential material
- complete email bodies

Continue storing only safe connection error information.

## Privacy and Public Copy

The public landing repository must remove Microsoft and Outlook from:

- Privacy Policy
- Terms of Service
- About content
- homepage data-use copy
- dictionaries
- tests
- the privacy ADR

The revised privacy language distinguishes the two Gmail methods:

- Google OAuth uses the restricted `gmail.readonly` permission and remains subject to the Google API Services User Data Policy, including Limited Use.
- An app password is encrypted at rest and used by TrackPal only to read recent messages needed for requested access-code searches.
- The app-password credential itself is not a technically read-only Google permission. Product copy must describe TrackPal's limited behavior rather than falsely describe the credential as scope-limited.
- Disconnecting TrackPal deletes the locally stored encrypted credential. The account owner must separately revoke an app password or OAuth grant in Google when provider-side revocation is desired.

Update the public document effective date when the behavior ships.

## Documentation Updates

Update all current-state documentation that describes Microsoft or generic IMAP support, including:

- `backend/CONTEXT.md`
- `frontend/CONTEXT.md`
- mailbox ingestion architecture
- database schema reference
- backend structure
- frontend components
- product goals
- business rules
- tenant deletion documentation
- user Help architecture and requirements
- environment examples
- release guidance affected by the new Help content

User-facing documentation may include IMAP only when quoting or linking external technical material; TrackPal product labels must not use it.

## Testing Strategy

### Backend

- Gmail-only request and response schemas.
- App-password whitespace normalization.
- Successful validation before encrypted persistence.
- Authentication failure writes no mailbox or credential changes.
- Timeout and network failure write no mailbox changes.
- Google OAuth start, callback, refresh, revoked state, and Gmail API fetching.
- Removal or rejection of Microsoft and unsupported provider routes.
- Lookup routing for `oauth` and `app_password`.
- Migration preservation and removal cases.
- Secret-safe error behavior.

### Frontend

- OAuth connection action hidden when the variable is missing, empty, or false.
- OAuth connection action visible only for exact `true`.
- Existing OAuth mailbox status remains visible when the gate is off.
- Two-step assistant navigation and back behavior.
- Official Google destination.
- Contextual Help request opens the mailbox topic.
- Help-disabled behavior hides only the full-tutorial action.
- Credential visibility control.
- Duplicate-submit prevention.
- Success state.
- Failure preserves email and clears app password.
- Connected status labels contain no IMAP terminology.

### Help

- English and Spanish metadata parity.
- Tutorial text and maintained search terms.
- Ordered-list rendering.
- Allowed Google links render safely.
- Unknown hosts and non-HTTPS links fail compilation.
- External destination parity between locales.
- Compiled artifact matches checked-in Markdown.

### Public landing

- No Microsoft or Outlook references remain in active product, legal, About, or mailbox copy.
- Google OAuth Limited Use declaration remains present.
- App-password handling is described accurately.
- English and Spanish content remain structurally aligned.

### Verification commands

Run the complete backend and frontend suites, Ruff, frontend lint and production build, Help compiler/release verification, migration SQL validation, and the landing repository's complete tests and production build.

## Rollout

1. Deploy backend schema and Gmail-only behavior.
2. Deploy the updated Help artifact and frontend with `VITE_GMAIL_OAUTH_CONNECT_ENABLED=false`.
3. Deploy synchronized public legal and product copy.
4. Manually verify the Gmail app-password flow in Spanish and English on desktop and mobile.
5. Enable `VITE_GMAIL_OAUTH_CONNECT_ENABLED=true` only in deployments that intentionally offer the verified restricted-scope OAuth path.

The backend and frontend changes should ship atomically because the mailbox request and response contracts change.

## Official Sources Reviewed

- Google Account Help, **Sign in with app passwords**: `https://support.google.com/accounts/answer/185833`
- Gmail Help, **Add Gmail to another email client**: `https://support.google.com/mail/answer/7126229`
- Google Account Help, **Less secure apps & your Google Account**: `https://support.google.com/accounts/answer/6010255`
- Microsoft Support, **POP, IMAP, and SMTP settings for Outlook.com**: `https://support.microsoft.com/en-us/office/pop-imap-and-smtp-settings-for-outlook-com-d088b986-291d-42b8-9564-9c414e2aa040`
- Microsoft Learn, **Deprecation of Basic authentication in Exchange Online**: `https://learn.microsoft.com/en-us/exchange/clients-and-mobile-in-exchange-online/deprecation-of-basic-authentication-exchange-online`
- Microsoft Learn, **Authenticate an IMAP, POP or SMTP connection using OAuth**: `https://learn.microsoft.com/en-us/exchange/client-developer/legacy-protocols/how-to-authenticate-an-imap-pop-smtp-application-by-using-oauth`
