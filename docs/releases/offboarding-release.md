# Tenant Data Export and Tenant Deletion release gate

This is the release checklist for the Tenant Data Export and Tenant Deletion feature. It is a **how-to guide for release owners**, not a user manual.

## Release policy

Tenant Data Export and Tenant Deletion have one frontend gate each: the Data tab is always visible in My Account, and the export/deletion UI is rendered from the backend API responses. The feature is considered released when the backend API and frontend My Account Data tab are deployed together.

## Automated release checks

Run these commands from a clean checkout of the release commit:

```bash
cd backend
uv run pytest -v

cd ../frontend
npm test -- --run
npm run build
```

The automated test suite covers:

- Export job lifecycle: pending, processing, ready, failed, cancellation states
- 24-hour cooldown enforcement
- 72-hour ready/failed expiry and cleanup
- Replacement with previous-artifact preservation
- Three retries with backoff classification
- 30-minute recoverable lease
- Presigned URL expiry capped to object lifetime
- Authorized Tenant Admin and Master export
- Cross-Tenant denial, Client denial, Starter access to preserved Pro data
- Password step-up with three-attempt/fifteen-minute rate limit
- Step-up fail-closed when Redis HA is unavailable
- Locale-aware destructive word validation
- Tenant Deletion full cascades and session teardown
- R2 and Evolution failure rollback
- Idempotent retry after partial external cleanup
- Encrypted app-password deletion without provider revocation
- Best-effort Redis cleanup
- Master inactive precondition and Tenant Admin active self-deletion

### Frontend tests

Frontend tests cover:

- My Account tab rendering (Profile, Security, Data)
- Tenant Admin vs Master Support Context visibility
- Export status polling states (empty, pending, processing, ready, failed, cancelled)
- Export request, cancel, and download flows
- Cooldown and expiry display
- Actor attribution labels
- Deletion dialog flow (password, destructive word, loading, error, success)
- Successful logout and redirect after deletion

## Manual browser QA matrix

Record the browser, viewport, locale, account/plan, result, and evidence link for every row.

| Surface | Locale | Viewport | Required checks | Status |
|---------|--------|----------|----------------|--------|
| Tenant Admin Starter | Spanish | Desktop | Export empty state, request, status polling, download, cooldown | Pending sign-off |
| Tenant Admin Starter | Spanish | Mobile | Data tab responsive, export dialogs fit viewport | Pending sign-off |
| Tenant Admin Starter | English | Desktop | Export flow, README locale matches account | Pending sign-off |
| Tenant Admin Starter | English | Mobile | Mobile layout, no overflow | Pending sign-off |
| Tenant Admin Pro | Spanish | Desktop | Export includes Clients, Catalog, Subscriptions | Pending sign-off |
| Tenant Admin Pro | Spanish | Mobile | Data tab with full Pro export | Pending sign-off |
| Tenant Admin Pro | English | Desktop | Export flow, danger zone, deletion confirmation | Pending sign-off |
| Tenant Admin Pro | English | Mobile | Danger zone, deletion dialog layout | Pending sign-off |
| Master Dashboard | Spanish | Desktop | Export active/inactive Tenant, shared job state | Pending sign-off |
| Master Dashboard | English | Desktop | Export status, download from Master Dashboard | Pending sign-off |
| Master Support Context | English | Desktop | Data tab visible, no Security tab, no delete action | Pending sign-off |

### Operational checks

| Check | Description | Status |
|-------|-------------|--------|
| Private bucket exists | `trackpal-exports-private` bucket created with no public custom domain | Pending sign-off |
| Export bucket credentials | `EXPORT_R2_*` variables set in deployment environment | Pending sign-off |
| Diagnostic bucket unchanged | Existing `trackpal-debug` bucket configuration not modified | Pending sign-off |
| Export bucket lifecycle | Lifecycle rule configured to expire objects older than 7 days (safety net) | Pending sign-off |
| Presigned URL limits | CORS and presigned URL behavior configured per export bucket | Pending sign-off |
| CORS configuration | Export bucket does not have permissive CORS for public origins | Pending sign-off |

### Deletion checks

| Check | Description | Status |
|-------|-------------|--------|
| Tenant Admin self-deletion | Delete active Tenant, verify redirect to login | Pending sign-off |
| Master deletion | Deactivate, then delete inactive Tenant via Master Dashboard | Pending sign-off |
| Export cleanup | Verify export artifacts removed after deletion | Pending sign-off |
| Evolution cleanup | Verify Evolution instance deleted after Tenant deletion | Pending sign-off |
| Re-authentication | Verify deleted Tenant Admin cannot log in again | Pending sign-off |

## Release evidence

The first implementation covers export and deletion with backend pytest and frontend Vitest tests. Manual browser QA is required for responsive layout, dialog interaction, mobile overflow, keyboard operation, and real deployment integration.

Attach completed QA notes to the issue or release record.

## Related Documentation

- [Tenant Data Export](../architecture/tenant-data-export.md)
- [Tenant Deletion](../architecture/tenant-deletion.md)
- [Product Goals](../project-pdr/product-goals.md)
- [Business Rules](../project-pdr/business-rules.md)
