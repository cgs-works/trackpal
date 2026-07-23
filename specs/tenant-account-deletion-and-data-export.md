# Spec: Tenant account deletion and basic data export

Status: active
Owner: human
Created: 2026-07-22

## Problem

TrackPal does not currently let a Tenant Admin export the Tenant's principal business data or close the Tenant account without Master assistance. Tenant deletion is a Master-only operation, is limited to inactive Tenants, and is exposed through both the web dashboard and the Master WhatsApp Console. The current service deletes the Evolution instance before committing the database transaction, so an external success followed by a database failure can leave TrackPal and Evolution inconsistent.

Tenant Admins need two separate self-service capabilities:

1. generate a human-oriented ZIP containing the Tenant's principal account and business data; and
2. permanently close the Tenant account after an explicit warning, password verification, and typed confirmation.

The export is an optional convenience offered before deletion, not a prerequisite for deletion. It is a basic product export rather than a full tenant dump, an import format, or a formal data-subject access/portability response.

The confirmed product direction intentionally limits deletion to TrackPal's PostgreSQL, Redis, and R2 data. Evolution, Google/Microsoft OAuth grants, n8n execution data, and Render logs remain outside the deletion scope. The confirmed direction also uses the existing public R2 bucket for export artifacts. These choices are captured as accepted risks and must not be described as security best practices.

## Goals

- Let the authenticated owner of a Tenant generate a basic ZIP export without Master assistance.
- Make export available to both Starter and Pro Tenants.
- Let an authenticated Master generate and download the same export for any Tenant.
- Keep export and account deletion as separate operations, while offering export before destructive confirmation.
- Generate exports asynchronously from a consistent database snapshot taken when the worker starts.
- Produce localized JSON and CSV files using a versioned public export vocabulary rather than database table or column names.
- Include only the Tenant profile, clients, catalog, and subscriptions.
- Exclude all passwords, PINs, tokens, hashes, credentials, internal operational records, settings, and history.
- Allow only one current export per Tenant and keep a ready artifact for 72 hours.
- Let the Tenant owner permanently close an active account from the web without Master approval or a recovery window.
- Require the actor's current password and a localized typed phrase before deletion.
- Use the same backend deletion operation for owner-initiated and Master-initiated web deletion.
- Treat a committed PostgreSQL hard deletion as the success gate for account closure.
- Attempt Redis and R2 cleanup without allowing their failure to block the PostgreSQL deletion.
- Remove Tenant deletion from the Master WhatsApp Console and direct Master to the web dashboard.
- Preserve only a minimal backup-suppression marker for the lifetime of affected backups.

## Non-Goals

- Do not implement GDPR/CCPA access, portability, or erasure request intake.
- Do not implement legal holds, retention orders, legal archives, or a Master retention-management interface.
- Do not implement billing cancellation or financial-record retention; TrackPal does not store financial records in this scope.
- Do not create a full Tenant dump or a round-trip import format.
- Do not export Tenant settings, mailbox configuration, access-control blocks, help acknowledgements, API keys, code-service selections, reminder settings/logs, subscription events, lookup jobs, delivery logs, sessions, metrics, or application logs.
- Do not export password hashes, subscription passwords, profile PINs, Evolution tokens, OAuth/IMAP secrets, refresh-token hashes, API keys, session values, or signed/public object URLs.
- Do not call Evolution, Google, Microsoft, n8n, or Render as part of account deletion.
- Do not retry, track, or display third-party deletion because third-party deletion is outside scope.
- Do not notify the owner by email or WhatsApp when the owner or Master deletes the Tenant.
- Do not retain a deletion receipt, deletion audit trail, external-processor acknowledgement, or user-visible deletion status.
- Do not add a cancellation or recovery period after destructive confirmation.
- Do not require an export or completed download before deletion.
- Do not require password reauthentication to create or download an export.
- Do not let users manually delete a generated export before its 72-hour expiry.
- Do not preserve visible export history after an artifact expires.
- Do not move export or suppression objects to a new private bucket in this scope; the existing public R2 bucket is a confirmed, accepted risk.
- Do not preserve deleted usernames, client prefixes, phone numbers, emails, or Evolution instance names against immediate reuse.

## Current Behavior

TrackPal has one owner `User` for each `Tenant`. Client profiles have separate `User` rows. Deleting the owner user cascades through the Tenant and most tenant-scoped records, while client user rows must be loaded and deleted explicitly. Refresh sessions cascade from their owning users.

The existing REST deletion endpoint:

- is authorized only for Master;
- accepts a Tenant identifier directly;
- rejects active Tenants;
- returns no content after deletion;
- invokes the shared Tenant deletion service.

The existing deletion service:

- loads the Tenant and rejects it while active;
- loads and deletes client users and then the owner user;
- flushes the database deletion;
- calls Evolution instance deletion;
- rolls back if Evolution deletion fails;
- commits PostgreSQL only after Evolution succeeds;
- does not explicitly clear Redis Tenant sessions/context, R2 artifacts, queued work, OAuth grants, n8n executions, logs, or backups.

The Master web dashboard has a simple destructive alert and calls the direct deletion endpoint. It does not request the Master's password or a typed phrase. On success, it reloads the Tenant list and shows a toast.

The Master WhatsApp Console exposes deletion for inactive Tenants and requires typed confirmation. Existing lifecycle tests cover the inactive-only rule and confirmation behavior.

The Tenant Settings page is available to Starter and Pro Tenant Admins and uses a category list with one active panel. It has no Data and account category. Post-authenticated copy is loaded from the backend i18n catalog in English or Spanish.

TrackPal has no Tenant export model, API, job, worker, artifact lifecycle, or export audit model. The mailbox subsystem provides an existing pattern for a database-backed job, a Redis queue, a background worker started from FastAPI lifespan, and a periodic cleanup loop.

The current R2 integration is S3-compatible, is configured for diagnostic uploads, and can return a public URL from the existing public bucket. There is no private export-artifact abstraction.

Redis is configured with primary and backup clients behind a failover manager. Normal operations run against the active store rather than broadcasting to both. Relevant Tenant console and context keys use five-minute TTLs, including admin sessions and client-context shortcuts.

Backend tests use pytest, an in-memory SQLite database, `httpx.AsyncClient` with ASGI transport, fake Redis implementations, and disabled Evolution credentials. Frontend tests use Vitest, Testing Library, and module mocks. Existing settings tests already exercise section visibility for Starter, Pro, and Master support context.

## Desired Behavior

### Roles and surfaces

- A Tenant Admin may export or delete only the Tenant they own. The backend derives the Tenant from the authenticated user and never trusts a Tenant identifier supplied by the owner client.
- A Master may export or delete any Tenant through explicit administrative routes containing the target Tenant identifier.
- Every owner and Master status/download/deletion operation performs object-level authorization server-side.
- Clients cannot export or delete a Tenant.
- Export and deletion are available for both Starter and Pro Tenants.
- Owner self-service appears in a new **Data and account** category in Tenant Settings.
- Master export and deletion are available from the web Tenant-management surface.
- Master deletion is removed from WhatsApp. The old WhatsApp menu action and recognized legacy command respond that Tenant deletion is available only from the web dashboard.

### Basic export scope

The export contains only four public datasets:

1. **Account**: public Tenant profile data and the owner's username, Tenant plan, and creation/update timestamps.
2. **Clients**: client name, username, phone, active status, and creation/update timestamps.
3. **Catalog**: services and plans, including their public relationships and timestamps.
4. **Subscriptions**: client, service, and plan references; streaming email; profile name; duration; start, expiry, cancellation, status, and timestamps.

The exporter must never read or serialize subscription password ciphertext/plaintext, profile PIN ciphertext/plaintext, password hashes, refresh-token hashes, Evolution credentials, API keys, mailbox secrets, OAuth tokens, IMAP passwords, session values, or internal error payloads.

Subscription event history and reminder delivery history are excluded even though subscriptions themselves are included.

### Export presentation contract

- The ZIP format is versioned independently from the database schema.
- The locale is frozen from the Tenant's server-side locale when the export request is accepted.
- File names, JSON property names, CSV headers, category names, descriptions, and README content use the frozen Tenant locale.
- The public export vocabulary does not reuse database table or column names merely by translating them.
- Relationships use export-local identifiers, such as `CLIENT-001`/`CLIENTE-001` and `SUBSCRIPTION-001`/`SUSCRIPCION-001`, rather than internal UUIDs.
- Export-local identifiers are deterministic within one ZIP and unique within their category. They do not need to remain stable across separately generated ZIPs.
- The ZIP includes a localized README and a manifest containing at least format version, locale, request identifier, generation time, snapshot time, included categories, explicit excluded categories, record counts, file sizes, and checksums.
- JSON is the complete representation. CSV mirrors the useful flat views for account, clients, services, plans, and subscriptions.
- CSV output neutralizes spreadsheet-formula injection in user-controlled values.
- Text is UTF-8 and timestamps use ISO 8601 with an explicit timezone.
- The archive is built with bounded memory and without loading an arbitrarily large Tenant into one in-memory object.

### Export lifecycle

The current export has this state machine:

```text
pending -> generating -> ready
                     -> failed
ready -> artifact/request purged after 72 hours
failed -> pending when the actor explicitly retries
pending|generating|ready|failed -> removed when the Tenant is deleted
```

- Creating an export returns `202 Accepted` with an opaque request identifier and a safe status representation.
- There is at most one current export record per Tenant.
- Creating while the current export is `pending`, `generating`, or unexpired `ready` returns that current export instead of creating another.
- Creating while the current export is `failed` requeues the same current request as an explicit retry.
- Each generation run attempts transient failures at most three times with bounded exponential backoff.
- Permanent validation failures fail immediately.
- Failed partial artifacts are deleted when possible and always use the same 72-hour lifecycle-managed prefix so abandoned parts expire.
- The snapshot timestamp is the start of the worker's consistent database transaction, not the HTTP request timestamp.
- The worker claims jobs idempotently so concurrent worker processes cannot generate competing artifacts for the same request.
- A ready artifact expires 72 hours after successful generation.
- Expiry deletes the R2 object and the current export request record. No expired item remains visible in the application.
- A periodic cleanup removes export audit rows older than 12 months while the Tenant exists.
- Deleting the Tenant removes its current export request and all export audit rows regardless of age.

### Export API behavior

Owner routes:

- `POST /api/v1/tenant-exports` creates, returns, or retries the owner's current export.
- `GET /api/v1/tenant-exports/current` returns the owner's current safe status or a non-disclosing not-found response.
- `GET /api/v1/tenant-exports/{request_id}/download` streams an authorized ready artifact.

Master routes:

- `POST /api/v1/tenants/{tenant_id}/exports` creates, returns, or retries the target Tenant's current export.
- `GET /api/v1/tenants/{tenant_id}/exports/current` returns that Tenant's current safe status.
- `GET /api/v1/tenants/{tenant_id}/exports/{request_id}/download` streams the authorized ready artifact.

Status responses contain only opaque request ID, status, attempts, request/generation/readiness/expiry timestamps, and a safe localized failure category where relevant. They never expose an R2 key, direct public URL, signed URL, Tenant secrets, record contents, or internal traceback.

Downloads:

- require a current authenticated owner or Master session;
- do not require password reauthentication;
- may be repeated until expiry or Tenant deletion;
- stream through the backend;
- use content disposition and content type appropriate for a ZIP;
- do not extend the 72-hour expiry;
- do not delete the artifact after download.

The application does not expose a manual artifact-delete endpoint.

### Export audit

TrackPal records a minimal database audit event for:

- request accepted;
- generation started;
- generation succeeded or failed;
- download started/completed as observable by the backend;
- artifact/request expiry.

Audit records contain Tenant association, opaque request ID, actor ID and role, event type, timestamp, and safe outcome only. They do not contain export contents, object keys, direct URLs, credentials, IP payloads, or request bodies. Audit records are retained for 12 months while the Tenant exists and are hard-deleted with the Tenant.

### Export storage

- Artifacts use the existing S3-compatible R2 client, credentials, bucket, and public-bucket configuration.
- Objects use an unpredictable, Tenant-separated export prefix and are never linked from unauthenticated TrackPal UI.
- The backend does not return the direct R2 public URL or object key.
- R2 Lifecycle is configured to delete the export/partial-artifact prefix after three days.
- The downloaded ZIP has no application-level password.
- The accepted public-bucket exposure is documented in Risks / Open Questions and is not represented as private storage.

### Tenant deletion interaction

The Data and account section shows export and deletion as independent blocks. Selecting deletion opens a two-step modal.

Step 1 displays the approved warning and offers to generate an export or continue without one.

Approved English meaning:

> This action will close your account and permanently delete the data stored by TrackPal. You will not be able to recover it.
>
> If you want to keep a copy of your principal data, generate and download your export before continuing. If you continue without downloading it, TrackPal will not be able to recover it or be responsible for the resulting loss from your decision.

The production English and Spanish copy must be maintained in the backend i18n catalog. The approved Spanish copy is:

> Esta acción cerrará tu cuenta y eliminará permanentemente los datos almacenados por TrackPal. No podrás recuperarlos.
>
> Si deseas conservar una copia de tus datos principales, genera y descarga tu exportación antes de continuar. Si continúas sin descargarla, TrackPal no podrá recuperarla ni responder por la pérdida resultante de tu decisión.

Step 2 requires:

- the actor's current password;
- the localized phrase `ELIMINAR MI CUENTA` for Spanish or `DELETE MY ACCOUNT` for English;
- a destructive submit action that remains disabled until both fields are present.

Phrase comparison trims leading/trailing whitespace and is case-insensitive. The backend validates the phrase for the server-recognized interface locale; frontend-only validation is not sufficient.

Password confirmation is rate-limited by actor and IP to five failed attempts in 15 minutes. Further deletion-confirmation attempts receive a safe temporary lock response until the window expires. This lock does not disable normal login.

There is no grace period and no post-confirmation cancellation.

### Interaction with an export

- If no export exists, Step 1 offers **Export first** and **Continue without export**.
- Choosing **Export first** starts or returns the current export, closes the deletion modal, and leaves the Data and account section showing status.
- Destructive confirmation is offered again only after the requested ZIP is ready if the user follows the export-first branch.
- If generation fails, the UI offers **Retry export** or **Continue to deletion**.
- If an export is still pending/generating and the actor starts deletion independently, the UI offers **Wait for export** or **Delete now**.
- Choosing **Delete now** cancels/removes the export job and best-effort deletes partial artifacts before continuing.
- If a ready ZIP has not been downloaded, deletion remains allowed after an explicit reminder that the ZIP will also be removed.
- A ready or failed current export is removed with the Tenant. R2 failure does not block Tenant deletion; an undeleted object remains subject to the three-day lifecycle.

### Owner deletion API and result

`POST /api/v1/account/deletion` accepts the current password and localized confirmation phrase. The target Tenant is derived exclusively from the authenticated owner.

On success:

- the API returns a success response only after PostgreSQL commits;
- all access and refresh sessions cease to authorize because the owner and session rows no longer exist;
- the frontend clears local tokens and all Tenant caches without requiring a successful logout call;
- the frontend navigates to a public final page stating that the account is closed and cannot be recovered;
- the final page has a button to go to login;
- no later email, WhatsApp message, or status update is sent.

If PostgreSQL deletion fails, the transaction is rolled back, the API returns an error, the frontend keeps the user on the confirmation surface, and the final page is not shown.

Duplicate submission after a committed deletion returns a non-disclosing terminal response that lets the frontend remain on the final page without recreating side effects.

### Master deletion API and result

`POST /api/v1/tenants/{tenant_id}/deletion` accepts the Master's own current password and localized confirmation phrase.

- Master can delete active or inactive Tenants.
- The owner does not approve the operation and receives no notification.
- The same internal deletion service and PostgreSQL success gate are used as for owner deletion.
- On success, Master remains authenticated, returns to the Tenant list, sees a localized success toast, and the list is refreshed.
- Cross-role and cross-object authorization failures use a non-disclosing forbidden/not-found response.
- The existing direct `DELETE /api/v1/tenants/{tenant_id}` behavior is retired so web callers cannot bypass password and phrase verification.

### PostgreSQL deletion contract

- Active status does not block deletion after valid confirmation.
- The deletion transaction explicitly deletes every client `User` row and the owner `User` row.
- Tenant cascades remove all current tenant-scoped operational records, including profile/settings, clients, services, plans, subscriptions and their children, reminders, mailbox data and lookup jobs, delivery logs, blocks, API keys, help acknowledgements, code-service selections, export requests, and export audits.
- Refresh sessions for owner and client users are removed.
- Global service-governance rows and other shared platform configuration are not deleted.
- Database tests prove that no Tenant-owned or associated user/session rows remain after success.
- The former Evolution deletion call is removed from this transaction and is not replaced by another external-provider call.
- Once the transaction commits, previously unique username, client prefix, phone, email where constrained, and Evolution instance name values may be reused immediately.

### Redis and R2 cleanup contract

Before or around the PostgreSQL deletion transaction, TrackPal makes one best-effort cleanup pass:

- remove deterministically attributable Tenant admin sessions and context keys from both configured Redis stores rather than only the currently active failover target;
- remove queued Tenant export work;
- remove the current/partial export artifact from R2.

Redis or R2 failure:

- is logged safely without credentials, object URLs, or exported content;
- does not roll back or prevent PostgreSQL deletion;
- is not retried or exposed to the user;
- leaves Redis data to its existing approximately five-minute TTL;
- leaves R2 export data to its maximum three-day lifecycle.

This accepted behavior means "immediate deletion" is defined as immediate loss of TrackPal account access after PostgreSQL commit, not verified physical deletion from every store at the same instant.

### Explicitly excluded external systems

Account deletion makes no deletion, logout, revocation, or pruning call to:

- Evolution instances or provider-side WhatsApp state;
- Google or Microsoft OAuth grants;
- n8n execution or binary data;
- Render logs, metrics, or traces.

Tests assert these integrations are not invoked by the new deletion service. Existing data in those systems may remain after the TrackPal account is closed.

### Backup suppression marker

Before or during deletion, TrackPal makes a best-effort write of a minimal, non-identifying suppression marker that survives a PostgreSQL restore. The marker:

- contains an HMAC or equivalent opaque derivation of the Tenant ID rather than name, email, phone, username, or business data;
- exists only to prevent a restored backup from reactivating the deleted Tenant;
- remains for at least the maximum retention of every backup that could contain the Tenant;
- is checked by a restore runbook before restored data is made available;
- is removed after all affected backups have expired.

The marker may use the existing R2 bucket because no separate suppression store was selected. In accordance with the confirmed R2 failure policy, marker-write failure does not block PostgreSQL deletion. That weakens restore protection and is an accepted risk.

### WhatsApp retirement

- Master WhatsApp menus no longer present Tenant deletion as an action.
- A recognized legacy deletion action does not call the Tenant service and replies that deletion is available only from the web dashboard.
- Existing WhatsApp tests that expect inactive-Tenant deletion are replaced with tests for menu removal and the web-direction response.
- Tenant Admin and Client WhatsApp behavior is otherwise unchanged.

## Acceptance Criteria

### Authorization and availability

- [ ] Starter and Pro Tenant owners can see and use Data and account in Tenant Settings.
- [ ] A Tenant owner can create, inspect, download, and retry only their own export.
- [ ] A Tenant owner can delete only their own Tenant; a supplied alternate Tenant identifier cannot change the target.
- [ ] Master can export or delete any selected Tenant through administrative web routes.
- [ ] Clients and unauthenticated callers cannot create, inspect, download, retry, or delete Tenant resources.
- [ ] Every request/status/download route rejects a mismatched Tenant/request identifier without exposing whether another Tenant's resource exists.

### Export content and format

- [ ] A generated ZIP contains localized README, manifest, JSON, and CSV representations for account, clients, services/plans, and subscriptions.
- [ ] The ZIP uses a versioned public vocabulary and contains no database table/column names as its schema.
- [ ] The ZIP contains export-local relationship identifiers and no internal UUIDs.
- [ ] English and Spanish exports use the request's frozen server-side Tenant locale.
- [ ] JSON and CSV record counts and relationships agree with the consistent snapshot timestamp in the manifest.
- [ ] Password hashes, refresh-token hashes, API keys, Evolution credentials, subscription passwords, profile PINs, OAuth/IMAP secrets, session values, settings, histories, and operational records are absent from every file.
- [ ] Manifest checksums and file sizes match the archive contents.
- [ ] User-controlled CSV values cannot execute as spreadsheet formulas when opened in common spreadsheet software.
- [ ] Large export generation uses bounded memory and paginated/streamed reads.

### Export lifecycle and storage

- [ ] Export creation returns `202` and at most one current request exists per Tenant.
- [ ] Repeated creation while pending/generating/ready returns the current request instead of creating a second job.
- [ ] A failed request can be explicitly retried and each generation run makes at most three transient attempts.
- [ ] Competing workers cannot both claim or publish the same export.
- [ ] The snapshot timestamp is recorded when the worker begins its consistent transaction.
- [ ] A ready ZIP can be downloaded repeatedly through an authorized backend endpoint until expiry.
- [ ] Status and download responses never expose the R2 object key or direct public URL.
- [ ] R2 artifacts and current request records are purged after 72 hours; expired exports leave no visible history.
- [ ] There is no user-facing/manual export-delete API.
- [ ] Partial artifacts are removed when possible and expire through the same three-day R2 Lifecycle rule.
- [ ] Minimal export audit events are retained for 12 months while the Tenant exists and are deleted with the Tenant.

### Owner deletion

- [ ] The two-step modal shows the approved localized warning and offers export before confirmation without requiring it.
- [ ] Correct current password and the localized phrase are both required server-side.
- [ ] Phrase comparison is case-insensitive and trims only exterior whitespace.
- [ ] Five failed password confirmations within 15 minutes trigger the deletion-only cooldown for that actor and IP.
- [ ] Active Tenant owners can delete without Master approval or a recovery window.
- [ ] PostgreSQL success removes the owner, all client users, refresh sessions, and every tenant-scoped operational/export/audit row.
- [ ] A PostgreSQL failure rolls back deletion, returns an error, and does not show the final page.
- [ ] After success, old access/refresh tokens fail, frontend state is cleared, and the public final page offers a login button.
- [ ] No email or WhatsApp notification and no deletion receipt/audit record is created.
- [ ] Deleted unique identifiers can be reused immediately.

### Master deletion and WhatsApp

- [ ] Master can delete active or inactive Tenants from web after verifying the Master's own password and localized phrase.
- [ ] Master remains logged in and returns to a refreshed Tenant list with a localized success message.
- [ ] The owner receives no notification for a Master-initiated deletion.
- [ ] The old direct Master DELETE operation cannot bypass the unified confirmation service.
- [ ] Master WhatsApp menus no longer offer Tenant deletion.
- [ ] A legacy WhatsApp deletion attempt directs Master to the web and performs no deletion.

### Store and provider boundaries

- [ ] Deletion attempts attributable session/context cleanup against both configured Redis stores.
- [ ] Deletion attempts current and partial export cleanup in R2.
- [ ] Redis/R2 cleanup failure does not prevent a successful PostgreSQL deletion.
- [ ] Tests demonstrate the accepted residual windows: approximately five minutes for Redis keys and up to 72 hours for R2 export objects.
- [ ] Deletion does not call Evolution, Google, Microsoft, n8n, or Render integrations.
- [ ] A minimal opaque backup-suppression marker is written best-effort and the restore runbook checks it before production activation.

### Localization, UI, and documentation

- [ ] All authenticated UI copy and error categories are present in English and Spanish backend catalogs; no new user-facing string is hardcoded.
- [ ] Data and account appears for Starter, Pro, and Master support context without exposing unrelated Pro-only settings to Starter.
- [ ] Export status covers pending, generating, ready, and failed, including retry and continue-to-deletion actions.
- [ ] A generating export offers wait or delete-now; a ready undownloaded export does not block deletion.
- [ ] Architecture, API, database, frontend, Redis, business-rule, and user-help documentation reflects the implemented behavior and its exclusions.

## Edge Cases

- The owner changes locale after requesting an export: the request keeps its frozen locale.
- The worker starts after Tenant data changes: the manifest snapshot begins at worker start and does not claim the earlier request time as its data cutoff.
- The Tenant has no clients, catalog entries, or subscriptions: the ZIP still contains valid empty localized datasets and accurate zero counts.
- A user-controlled value starts with `=`, `+`, `-`, or `@`: CSV serialization prevents formula execution while JSON preserves the original value.
- A Tenant is large enough to exceed memory if fully materialized: generation remains bounded and either succeeds or fails safely without publishing a partial archive as ready.
- Two create requests arrive concurrently: one current request wins and both responses identify it.
- Two workers receive the same job: only the database claimant generates and publishes.
- A worker crashes after upload but before marking ready: the object remains under lifecycle cleanup and a retry does not publish two current artifacts.
- R2 upload succeeds after the Tenant was deleted: the worker rechecks request/Tenant state before publication and deletes or abandons the object under the lifecycle prefix.
- The artifact expires during a download: a download authorized before expiry may finish, but no new download begins after expiry.
- The R2 object is missing while status says ready: download returns a safe failure and the current request becomes failed or is purged without exposing the key.
- Export generation reaches three transient failures: status becomes failed and UI offers manual retry or deletion.
- The user chooses export first and then independently chooses delete while generation is running: UI offers wait or delete-now, and delete-now removes/cancels current export state.
- Password is valid but phrase is wrong, or vice versa: no destructive work begins.
- Deletion is submitted twice: the second request is terminal and non-disclosing and cannot recreate work.
- Redis primary is available but backup cleanup fails, or the reverse: PostgreSQL deletion still commits and the missed key relies on TTL.
- R2 deletion fails: the account still closes and the object relies on Lifecycle.
- PostgreSQL fails after best-effort Redis/R2 cleanup: the transaction rolls back; the user can log in again, regenerate an export, and retry deletion.
- A Master deletes a Tenant while the owner is using it: PostgreSQL commit invalidates subsequent owner/client requests and the owner receives no out-of-band notice.
- A Master deletes a Tenant while an export download is active: no new access is granted after deletion; in-flight transport behavior must not restore the request record.
- A deleted username, client prefix, phone, email, or Evolution instance name is immediately reused: TrackPal permits it even if an excluded external provider still has state under the old identity.
- The backup-suppression marker cannot be written: deletion still succeeds under the confirmed best-effort policy and emits only a safe operational log.
- An old backup is restored: the restore procedure must reconcile the surviving suppression registry before any restored Tenant can authenticate.

## Suggested Approach

### Backend boundaries

Introduce a dedicated export domain rather than adding export logic to the existing Tenant mutation service:

- an export request model for the single current request and state machine;
- an export audit model with a Tenant cascade and 12-month cleanup;
- repositories that claim work atomically and page each allowed dataset with explicit Tenant predicates;
- a serializer that owns the public localized schema and export-local identifiers;
- an archive builder that writes to a bounded temporary/spooled file, computes checksums, and uploads without blocking the async event loop;
- an R2 artifact adapter that never returns the direct public URL to API callers;
- a worker/cleanup pair following the existing database-job, Redis-queue, lifespan-task, and periodic-cleanup conventions.

Use one consistent PostgreSQL transaction for the export snapshot. On PostgreSQL, use an isolation level that preserves a stable view while all allowed datasets are read. Keep the serializer independent from ORM field names so schema translations and future database migrations do not silently alter the public format.

Claim jobs with a conditional status transition and make publication idempotent. Check that the Tenant and current request still exist immediately before marking an uploaded object ready.

Store all export and partial objects under a dedicated prefix in the existing bucket. Provision an R2 Lifecycle rule for that prefix at three days. Treat lifecycle configuration as deployment configuration verified by a manual integration check, not as an assumption hidden in application code.

### API boundaries

Keep owner and Master route shapes separate so owner routes never accept a target Tenant identifier. Share service methods only after each route resolves and authorizes its actor/target.

Use opaque request IDs and safe status schemas. Stream downloads through FastAPI after rechecking role, Tenant, request ownership, status, and expiry. Never include an R2 URL/key in models returned to the frontend.

Create a deletion-confirmation schema carrying password and phrase. Reuse the password verifier directly against the already authenticated actor rather than calling normal login, because normal Tenant login rejects inactive accounts and has different side effects. Implement the five-attempt/15-minute deletion-only limiter in shared state suitable for multiple web processes.

### Deletion boundary

Replace the inactive-only, Evolution-coupled mutation with one unified account-deletion service:

1. authorize the actor/target and verify rate limit, password, and phrase;
2. capture only the identifiers needed for best-effort Redis/R2 cleanup;
3. cancel/remove export job admission and attempt R2 cleanup;
4. attempt attributable key deletion against primary and backup Redis independently;
5. write the opaque backup-suppression marker best-effort;
6. enter the internal Tenant RLS context;
7. explicitly delete client users and then the owner user so cascades remove the Tenant graph;
8. commit PostgreSQL;
9. return the role-appropriate success result.

Do not call Evolution or any other excluded provider. Do not create a durable deletion request, saga, receipt, or retry queue.

Expand the deletion inventory test whenever a new tenant-scoped model is introduced. Shared global rows must remain untouched.

### Frontend boundaries

Add one Data and account settings section for both plans. Keep export state local to a focused service/store or query abstraction with in-flight request deduplication consistent with existing frontend state patterns. Poll only while pending/generating and stop on ready, failed, auth loss, unmount, or deletion.

Implement the owner deletion flow as a two-step accessible destructive dialog. The export-first branch returns to status rather than nesting long-running progress inside the dialog. After owner success, synchronously clear local auth and settings/catalog caches and navigate to a public final route; do not call an endpoint that requires the now-deleted refresh session.

Replace the Master dashboard's simple alert with the same confirmation component configured for the selected Tenant and Master actor. After success, keep Master auth intact and reload the list.

Use backend i18n keys for every authenticated label, state, error, warning, phrase prompt, final-page message, and toast. Add a stable contextual-help target for the new settings category.

### Test seams

Prefer four observable seams:

1. **Backend API tests** as the primary seam for authorization, one-current-export behavior, safe status, download isolation, owner/Master confirmation, hard-deletion inventory, and PostgreSQL rollback.
2. **Export worker/service tests** for snapshot packaging, localized public schema, forbidden-field absence, checksums, bounded paging, retry/claim behavior, R2 calls, expiry, and audit retention.
3. **Frontend component tests** for Data and account availability, export statuses, two-step deletion behavior, final owner route, and Master list refresh.
4. **WhatsApp lifecycle tests** for deletion-menu removal and web direction with no service call.

Use fake Redis primary/backup clients and a stubbed S3-compatible client. Do not require real R2, Evolution, OAuth, n8n, or Render access in automated tests.

### Rejected alternatives

The confirmed design rejects the following alternatives for this scope:

- full Tenant export;
- internal UUIDs in the export;
- credential export or a second encrypted credential archive;
- a private/dedicated R2 bucket;
- signed URLs or direct streaming without a retained artifact;
- one-download-only artifacts;
- manual artifact deletion;
- password reauthentication for export;
- deletion grace period;
- deletion saga, retries, receipt, or completion notification;
- deletion/revocation in external providers;
- legal-hold management;
- continued Master deletion through WhatsApp.

## Testing Plan

Minimum targeted backend validation:

```bash
cd backend
uv run pytest -k "tenant_export or tenant_account_deletion or whatsapp_master_delete_redirect"
```

Minimum targeted frontend validation:

```bash
cd frontend
npm test -- --run -t "Data and account|tenant export|tenant deletion"
```

Full backend validation and Python style checks:

```bash
cd backend
uv run pytest
ruff check .
ruff format --check .
```

Full frontend validation:

```bash
cd frontend
npm test -- --run
npm run lint
npm run build
```

Required backend automated coverage:

- API authorization matrix for unauthenticated, Client, owner, other owner, Master, and mismatched request/Tenant identifiers.
- One-current-export concurrency and idempotent worker claim.
- English and Spanish ZIP golden-structure assertions without snapshotting volatile timestamps.
- Forbidden-field scan across every ZIP entry.
- Manifest count/checksum verification and export-local relationship integrity.
- CSV formula-injection cases.
- Empty and large paginated Tenant datasets.
- Three-attempt transient retry and immediate permanent failure.
- Repeated authorized downloads and expiry behavior.
- R2 missing-object, upload failure, partial artifact, and lifecycle-prefix behavior with a stubbed client.
- Export audit creation, 12-month cleanup, and Tenant cascade.
- Correct and incorrect password/phrase cases plus five-attempt cooldown.
- Owner and Master deletion of active Tenants.
- Complete post-delete inventory across owner/client users, refresh sessions, every tenant-scoped model, export request/audit, and unchanged global rows.
- PostgreSQL failure rollback.
- Redis primary/backup deletion attempts and accepted failure behavior.
- R2 cleanup attempt and accepted failure behavior.
- Assertions that Evolution/OAuth/n8n adapters are not called.
- Immediate identifier reuse after deletion.
- Best-effort suppression-marker shape and restore-filter behavior.
- WhatsApp menu removal and web-direction reply.

Required frontend automated coverage:

- Data and account visibility for Starter, Pro, and Master support context.
- Export creation, polling, ready, failed, retry, repeated download, and 72-hour expiry UI.
- Export-first deletion branch.
- Wait/delete-now behavior during generation.
- Ready-but-not-downloaded warning without blocking deletion.
- Password/phrase gating, localized phrase display, server error, and cooldown response.
- Owner success clears local auth/cache and renders the public final page with login navigation.
- Master success preserves Master auth, returns to the Tenant list, refreshes data, and shows localized confirmation.
- No hardcoded authenticated copy in the new components.

Required manual/integration checks before promotion from draft:

- In a non-production R2 environment configured like deployment, verify that the export prefix is publicly reachable when its object key is known, document that accepted exposure, and verify three-day Lifecycle deletion.
- Generate representative English and Spanish ZIPs and inspect them with common ZIP, JSON, and spreadsheet tools.
- Interrupt a large download and confirm it remains downloadable until expiry.
- Disable Redis primary, backup, and R2 in turn and confirm PostgreSQL deletion still succeeds under the accepted policy.
- Force a PostgreSQL failure and confirm no final owner/Master success UI is shown.
- Confirm old owner/client tokens fail after deletion.
- Confirm Evolution instance, OAuth grant, n8n execution data, and Render logs are unchanged by deletion.
- Run a backup-restore drill that applies the suppression registry before enabling authentication.
- Verify responsive and keyboard-accessible dialog behavior on desktop and mobile.

## Documentation Updates

Update the following documentation areas when behavior changes:

- **Documentation Summary**: add the draft/implemented capability to the relevant architecture and product navigation once promoted.
- **System Overview**: describe the export worker, R2 artifact lifecycle, web-only deletion surfaces, and intentionally excluded providers.
- **API Layer**: document owner and Master export/status/download/deletion contracts, authorization, rate limiting, and retired direct deletion behavior.
- **Database Schema**: document export request/audit records, cascades, one-current-export constraint, and suppression marker metadata if represented in the application schema.
- **Redis HA**: document best-effort cleanup against primary and backup and the accepted TTL fallback.
- **Frontend Architecture**: document Data and account, the owner final page, Master confirmation flow, polling, and all-plan availability.
- **WhatsApp Console Flow**: remove Master Tenant deletion and document the web-direction response.
- **I18n System**: document localized export schemas and the confirmed destructive phrases/copy.
- **Business Rules**: distinguish basic product export from formal privacy requests and define the local-only deletion boundary.
- **User Help System and Tenant Admin manual**: explain export scope/exclusions, 72-hour availability, deletion irreversibility, export-first choice, and lack of recovery.
- **Backend and Frontend Structure references**: add the new export/deletion modules and test seams after implementation.
- **Tenant Account Deletion and Data Export research note**: add a short implementation-status reference while preserving the note as factual research rather than rewriting it as a product decision.
- **Deployment/runbook documentation**: record R2 Lifecycle configuration, export audit cleanup, suppression-marker retention, and restore gating.

## Risks / Open Questions

### Confirmed and accepted product/security risks

- **Public export artifacts**: the existing R2 bucket is public. Anyone who obtains or guesses an object key may bypass backend authorization and download highly sensitive Tenant/client data. Unpredictable keys reduce discoverability but are not access control. A private bucket remains the recommended remediation outside this scope.
- **Public suppression markers**: opaque HMAC markers reveal less than raw identifiers, but the public bucket still exposes object existence and metadata to anyone with a key.
- **Incomplete deletion boundary**: Evolution, OAuth providers, n8n, and Render can retain Tenant-related data after TrackPal presents account closure as complete.
- **Potentially misleading product copy**: the approved non-technical warning says TrackPal data will be permanently deleted but does not explain the excluded external systems or temporary Redis/R2 residual windows.
- **No external cleanup/retry**: TrackPal neither attempts nor tracks deletion in excluded providers.
- **No deletion evidence**: without a receipt or audit trail, TrackPal cannot later prove which cleanup steps ran or whether Redis/R2 cleanup failed.
- **Export without reauthentication**: a stolen authenticated session can create and repeatedly download a full basic export.
- **Best-effort local cleanup**: Redis/R2 failures do not block success, so data can remain for five minutes or 72 hours respectively.
- **Best-effort restore protection**: suppression-marker failure does not block deletion, so a later backup restore may reintroduce the Tenant.
- **Immediate identifier reuse**: a new Tenant can collide with state intentionally left in Evolution, OAuth, n8n, logs, or older backups.
- **No owner notice for Master deletion**: Master can delete an active Tenant without warning or confirmation from the owner.

### Operational facts to verify before promotion

- The actual maximum PostgreSQL backup retention period and the process that sets suppression-marker expiry to at least that duration.
- The exact deployed R2 public-access behavior and whether the configured public domain exposes every object under the export prefix.
- That an R2 Lifecycle rule can be provisioned for the export prefix at the required three-day retention in every environment.
- The largest realistic Tenant record count, expected ZIP size, worker runtime, temporary disk availability, and Render request/worker limits.
- Whether deployment runs more than one web process, which affects worker claim concurrency and deletion-confirmation rate limiting.
- The restore operator and runbook location responsible for applying suppression markers before production activation.

No additional product decision is required to keep this document in draft. The confirmed risks above must remain visible during review and must not be silently reclassified as best-practice controls.
