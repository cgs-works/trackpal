# Tenant Data Export

Tenant Data Export produces a portable, business-facing snapshot of a Tenant's TrackPal data. It is available to Tenant Admins (self-service via My Account Data tab) and Master users (via Master Dashboard).

## Actors

| Actor | Can export | Scope | Step-up required |
|-------|-----------|-------|-----------------|
| Tenant Admin | Own active Tenant | Self-service via My Account Data tab | Password |
| Master | Any active or inactive Tenant | Master Dashboard by Target Tenant ID | Master password |

Master can export both active and inactive Tenants without requiring a support context. Master and Tenant Admin share the same account-level job, cooldown, and artifact.

## Endpoints

### Self-service (Tenant Admin)

- `POST /api/v1/me/export` — Request new export (password step-up required)
- `GET /api/v1/me/export` — Get latest export status (204 if none)
- `POST /api/v1/me/export/cancel` — Cancel pending/processing job
- `GET /api/v1/me/export/download` — Get presigned download URL for latest ready export

### Master-scoped

- `POST /api/v1/tenants/{tenant_id}/export` — Request export for Tenant (Master password step-up)
- `GET /api/v1/tenants/{tenant_id}/export` — Get export status for Tenant
- `POST /api/v1/tenants/{tenant_id}/export/cancel` — Cancel export for Tenant
- `GET /api/v1/tenants/{tenant_id}/export/download` — Get presigned download URL for Tenant's ready export

## Step-up Authentication

Export generation requires password re-entry using a shared three-attempt/fifteen-minute rate limiter:

- Three failed password attempts per actor in a sliding fifteen-minute window
- Successful step-up resets the counter
- Fails closed when Redis HA cannot enforce the limiter
- Returns one generic localized authentication error rather than revealing which input failed
- Downloading a ready export does NOT require password reauthentication

## Job Lifecycle

| State | Description |
|-------|-------------|
| `pending` | Created, awaiting worker pick-up |
| `processing` | Worker has claimed the job with a 30-minute recoverable lease |
| `ready` | Artifact uploaded and available for download for 72 hours |
| `failed` | Generation failed after 3 retries with backoff; metadata removed after 72 hours |
| `cancelled` | Cancelled by authorized actor |

### Lifecycle rules

1. **One current job per Tenant**: Only one logical export exists at a time. A new request replaces the current ready/preparing job.
2. **24-hour cooldown**: One new generation per Tenant every 24 hours, shared across Tenant Admin and Master.
3. **Replacement**: The previous ready artifact remains downloadable while a replacement is pending. After upload confirmation, the new artifact is exposed and the previous object is purged.
4. **Cancellation**: Authorized actors can cancel pending/processing jobs. Workers observe cancellation checkpoints and purge partial uploads. Tenant Deletion uses the same mechanism.
5. **72-hour availability**: Ready objects are available for 72 hours from `ready_at`. At expiry, TrackPal stops signing URLs, deletes the object, and removes user-visible metadata. Status and download requests also reconcile ready jobs against R2, clearing stale metadata when an object was removed externally. R2 lifecycle rules are a safety net.
6. **Presigned URLs**: 15-minute lifetime, capped to remaining object lifetime. URL reuse is allowed within its lifetime. URLs are never logged or persisted.
7. **Actor attribution**: UI labels are localized "You" / "Support" style without exposing usernames or IDs.

## Export Bundle

One ZIP named `<slugged-account-name>-data-<account-local-timestamp>.zip` containing:

| File | Format | Contents |
|------|--------|----------|
| `account-profile.csv` | CSV | account_name, whatsapp_phone, login_username, current_plan, preferred_language, time_zone, currency |
| `client-data.csv` | CSV | client_name, login_username, whatsapp_phone, account_status, registered_on, last_updated_on |
| `service-catalog.csv` | CSV | service_name, service_icon, service_created_on, service_updated_on, plan_name, plan_price, plan_created_on, plan_updated_on |
| `subscription-snapshot.csv` | CSV | client_name, client_login_username, service_name, plan_name, service_account_email, service_profile_name, subscription_duration, started_on, expires_on, cancelled_on, subscription_status, recorded_on, last_updated_on |
| `blocked-phones.csv` | CSV | phone, blocked_at |
| `trackpal-data.json` | JSON | export_metadata, account_profile, client_accounts, service_catalog, subscription_snapshot, blocked_phone_list |
| `README.txt` | Text | Localized explanation of files, fields, omissions, codes, and custody |

### Export contract

1. Field names are stable English `snake_case` business-facing names, not database column names.
2. CSV uses UTF-8 with BOM, comma delimiter, standard quoting, and formula-injection neutralization.
3. JSON is UTF-8 with `null` for missing optional values.
4. Timestamps are ISO 8601 with explicit offset in the account timezone.
5. Record ordering: Clients by `login_username`; Catalog by `service_name`, `plan_name`; Subscriptions by `started_on` descending; blocked phones by `phone`.
6. `service_icon` is the optional Iconify `prefix:name` reference (e.g. `simple-icons:netflix`). TrackPal does not include the SVG asset. External consumers must resolve icons via the Iconify CDN or provide their own fallback. Export format version is `2`.
7. Services without Plans emit one CSV row with empty Plan fields and a JSON object with an empty `plans` list.
8. Access Control rows with only a WhatsApp LID are deliberately omitted.
9. README is localized; filenames, JSON keys, CSV headers, and machine values remain English.

### Stable-contract changes (ADR 0003 revision)

The following columns were added to the export stable contract:

| File | New column | Type | Source | Notes |
|------|-----------|------|--------|-------|
| `account-profile.csv` | `currency` | string | `TenantSettings.currency` | ISO 4217 code; empty when unset |
| `service-catalog.csv` | `plan_price` | string | `Plan.price` | Formatted as `"{price:.2f}"` when set; empty when `None` |

These columns are appended after their respective logical groupings and are reflected in both CSV headers and JSON keys. Export format version remains `2`.

### Deliberate exclusions

- Internal UUIDs, database IDs, client passwords, subscription passwords, profile PINs, secret-presence indicators
- Mailbox login credentials or app passwords, Evolution tokens, Public API Keys
- Subscription Events, reminder logs, lookup jobs, delivery logs
- WhatsApp LIDs, LID-only Access Control rows, internal settings
- Tenant ID, actor IDs, and other internal identifiers

### Plan policy

Export is independent of the current plan. Starter Tenants receive preserved Pro data (Clients, Catalog, Subscriptions) even though the corresponding modules remain gated in the UI.

## Storage Boundary

Tenant Data Export uses a **dedicated private Cloudflare R2 bucket** with:

- Separate endpoint, access key, secret, and bucket name from the public diagnostic R2 bucket (`trackpal-debug`)
- No public custom domain
- Random, non-PII object keys (no account name, username, Tenant ID, or actor ID)
- Provider-managed encryption at rest
- No ZIP-level password
- Bucket lifecycle rule as a safety net for object expiry

The export storage adapter (`app/services/export_storage/`) supports upload, metadata lookup, delete, presigned GET generation, and a deterministic fake adapter for tests. Missing export-storage configuration fails explicitly; it never falls back to the diagnostic bucket.

### Configuration

Environment variables (see `backend/.env.example`):

- `EXPORT_R2_ACCESS_KEY_ID` — R2 access key for the export bucket
- `EXPORT_R2_SECRET_ACCESS_KEY` — R2 secret access key
- `EXPORT_R2_BUCKET_NAME` — Bucket name (default `trackpal-exports-private`)
- `EXPORT_R2_ENDPOINT_URL` — R2 endpoint URL
- `EXPORT_SIGNED_URL_TTL_SECONDS` — Presigned URL lifetime (default 900 = 15 minutes)

## Snapshot Consistency

All files are generated from one point-in-time database snapshot without locking user writes. Both CSV and JSON are built from the same DTO graph so record counts and field values cannot disagree. Changes after the snapshot appear only in a later export.

## Observability

Exports record safe job/deletion transitions, actor ID, Tenant ID, counts, attempts, duration, and outcome. Logs never contain passwords, confirmation words, signed URLs, object contents, exported values, decrypted values, or object keys containing PII.

## Related Documentation

- [Product Goals](../project-pdr/product-goals.md)
- [Business Rules](../project-pdr/business-rules.md)
- [Tenant Deletion](tenant-deletion.md)
- [ADR-0003: Tenant Data Export Domain Contract](../adr/0003-tenant-export-domain-contract.md)
- [Backend Structure](../codebase/backend-structure.md)
- [Frontend Architecture](frontend-architecture.md)
- [Logging Guidelines](../code-standard/logging-guidelines.md)
