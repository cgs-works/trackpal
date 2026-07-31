# Tenant Deletion

TrackPal supports two deletion paths:

1. **Tenant Admin self-service deletion** — Immediate irreversible deletion of the active Tenant from My Account Data tab.
2. **Master deletion** — Deactivate-first lifecycle in the Master Dashboard with strong confirmation.

Both paths share the same external-first, fail-closed coordinator that purges export artifacts, deletes the Evolution instance, commits the database cascade, and tears down sessions.

## Actors

| Actor | Can delete | Scope | Precondition |
|-------|-----------|-------|-------------|
| Tenant Admin | Own active Tenant | Self-service via My Account Data tab | Tenant must be active |
| Master | Any inactive Tenant | Master Dashboard | Tenant must be inactive (deactivated first) |
| Master Support Context | No self-service deletion | N/A | Guides back to Master Dashboard |

## Endpoints

- `POST /api/v1/me/delete-account` — Tenant Admin self-deletion (password + destructive word)
- `POST /api/v1/tenants/{tenant_id}/delete` — Master deletion of inactive Tenant (password + destructive word)

## Step-up Authentication

Deletion requires both:

1. **Current actor password** — Shared three-attempt/fifteen-minute rate limiter (same as export step-up). Fails closed when Redis HA cannot enforce the limiter.
2. **Locale-aware destructive word** — `ELIMINAR` for Spanish, `DELETE` for English (case-insensitive after trimming).

One generic localized authentication error is returned when either input is wrong, without revealing which one failed.

## Deletion Sequence

```
1. Validate preconditions (role, active/inactive, locale)
2. Cancel in-flight export job → wait up to 30s for safe checkpoint
3. Purge current, previous, and partial R2 export objects
4. Delete Evolution instance (idempotent)
5. Delete database identities and Tenant-owned records through cascades:
   - Users (Tenant Admin User, Client Users) → RefreshSessions cascade
   - Clients → all linked records cascade
   - Catalog (Services, Plans) → Subscriptions, Events, ReminderLogs cascade
   - TenantMailbox → MailLookupJobs, DeliveryLogs cascade
   - TenantSettings, ExportJobs, BlockedClients, TenantCodeServiceSelections
   - TenantHelpAcknowledgements
6. Delete stored mailbox app-password credentials (NO provider revocation)
7. Clear frontend auth and redirect to login (Tenant Admin self-deletion)
```

## Fail-closed External Cleanup

External cleanup (R2, Evolution) runs **before** the database commit in this order:

1. **R2 purge**: Delete current, previous/partial export objects. Failure preserves the Tenant and returns a retryable error.
2. **Evolution instance deletion**: Idempotent `DELETE /instance/delete/{name}`. 404 is handled gracefully. Failure preserves the Tenant for retry.

If external cleanup fails, the Tenant remains fully present and the operation can be retried. A rare final database commit failure after successful external cleanup leaves the Tenant temporarily present; retrying the same operation completes deletion safely because external objects are already absent.

## What is deleted

- Tenant record, sole Tenant Admin User identity, Client Users
- Clients, Catalog (Services, Plans), Subscriptions, SubscriptionEvents, SubscriptionReminderLogs
- SubscriptionReminderSettings, TenantSettings
- TenantMailbox (app passwords), MailLookupJobs, MailCodeDeliveryLogs
- ExportJobs, BlockedClients, TenantCodeServiceSelections
- TenantHelpAcknowledgements
- Database refresh sessions (via cascades)

## What is NOT deleted

- **Google app password**: TrackPal deletes its encrypted local copy. Revoke the generated app password separately from your Google Account if you no longer need it.
- Infrastructure backups and logs (follow operational retention policies)
- WhatsApp/Session Redis keys (best-effort cleanup; keys expire in 5 minutes)

## Post-deletion

- Tenant Admin self-deletion: clears frontend auth and all feature stores, redirects to login with localized confirmation
- Master deletion: returns success; the Master Dashboard refreshes the tenant list
- No application tombstone is retained
- Re-authentication as the same Tenant Admin identity is impossible

## Observability

Logs record safe actor, Tenant, state, and outcome metadata. They never contain passwords, confirmation words, signed URLs, object contents, exported values, decrypted values, or object keys.

## Related Documentation

- [ADR-0002: Immediate Confirmed Tenant Deletion](../adr/0002-immediate-confirmed-tenant-deletion.md)
- [Product Goals](../project-pdr/product-goals.md)
- [Business Rules](../project-pdr/business-rules.md)
- [Tenant Data Export](tenant-data-export.md)
- [Evolution Integration](evolution-integration.md)
- [Logging Guidelines](../code-standard/logging-guidelines.md)
