# Tenant Account Deletion and Data Export in a Multi-Tenant SaaS

**Research date:** 2026-07-22  
**Context:** one customer account equals one `Tenant`  
**Status:** factual research note; not an implementation decision or legal advice

## Question

What practices should a multi-tenant SaaS follow when a customer asks to export its data or delete its account?

## Executive summary

1. **Tenant offboarding and privacy-right requests are different workflows.** A tenant can be a company, while GDPR and CCPA/CPRA rights belong to natural persons. Closing a tenant may still erase personal data about its owner, administrators, clients, and message recipients, but a full-tenant export is not automatically the same as a GDPR Article 15 access response or Article 20 portability response. [S1] [S4]
2. **Separate account closure, tenant export, data-subject access/portability, and data-subject erasure.** They differ in requester authority, scope, exceptions, deadlines, and the rights of other people represented in the tenant's records. [S1] [S2] [S3]
3. **Use an inventory-driven, asynchronous deletion saga.** The workflow should revoke access immediately, then track deletion across PostgreSQL, Redis, external services, workflow execution history, logs, exports, and backups. A request should not be marked complete while a required store or processor is still pending or has failed.
4. **A recovery grace period is a product choice, not erasure.** It can protect against accidental account closure, but it must not silently extend a valid statutory deadline. GDPR requires action without undue delay and generally within one month; California generally requires fulfillment within 45 days, with the respective allowed extensions and notices. [S1] [S2] [S5]
5. **Exports are high-risk authorization operations.** Derive the tenant scope from the authenticated principal and server-side authorization policy, re-authenticate for the sensitive action, and test that changing any tenant or object identifier cannot disclose or delete another tenant's data. [S6] [S7]
6. **Do not export operational secrets by default.** Password hashes, refresh tokens, OAuth tokens, Evolution instance tokens, encryption keys, session identifiers, and ephemeral access codes are not portability data and can create an account-takeover path. The export manifest should disclose exclusions.
7. **Backups need a documented erasure strategy.** If immediate selective deletion is not technically possible, erased data should be put beyond use, expire under a defined backup schedule, and be suppressed or erased before a restored backup returns to production. [S2]
8. **Cryptographic erase is not a shortcut unless key isolation supports it.** It is suitable only when the target data was always encrypted and all relevant key copies can be sanitized. In shared storage, deleting a shared application key would affect every tenant; tenant-level crypto-erasure therefore requires tenant-specific key hierarchy and complete key-copy control. [S9]

## 1. Distinguish the four requests

| Request | Authorized requester | Typical scope | Main governing basis |
|---|---|---|---|
| **Close the Tenant account** | Tenant owner or an administrator with explicit organization authority; a platform Master only under documented support/governance rules | Contract, subscription, tenant-owned business records, integrations, users, and tenant resources | SaaS contract, retention policy, applicable law |
| **Export the Tenant** | Tenant owner or explicitly authorized tenant administrator | Tenant business data and tenant-controlled records, subject to third-party rights and secret exclusions | Product/contractual offboarding feature |
| **Access or portability request by a person** | The data subject or a verified authorized agent | Personal data about that person; Article 20 is narrower than a full access copy | GDPR Articles 15 and 20; CCPA/CPRA right to know/access [S1] [S3] [S5] |
| **Erase a person's data** | The data subject or a verified authorized agent | Personal data about that person, subject to statutory grounds and exceptions | GDPR Article 17; CCPA/CPRA deletion right [S1] [S2] [S4] |

### Why the distinction matters

- GDPR defines personal data by reference to an identified or identifiable **natural person**. A company tenant is not itself a GDPR data subject, although its records can contain personal data about many people. [S1]
- CCPA defines a consumer as a **natural person who is a California resident**. Its deletion right concerns that consumer's personal information, not automatically every record owned by the consumer's employer or business tenant. [S4] [S11]
- GDPR Article 20 portability applies only when processing is automated and based on consent or contract, and only to personal data concerning the person that the person provided to the controller. A full tenant dump can therefore be broader than the legal portability set. [S1] [S3]
- A full tenant export may contain the personal data of clients or other users. GDPR Article 20 states that portability must not adversely affect the rights and freedoms of others. [S1]

**Practical consequence:** expose separate request types and record which one is being fulfilled. Do not treat a generic “delete my account” button as the sole intake path for every privacy request.

## 2. Primary-source legal baseline

### 2.1 GDPR and UK GDPR

- Article 15 gives a data subject access to personal data concerning them and contextual information including processing purposes, data categories, recipients, retention, and sources. [S1]
- Article 17 requires erasure without undue delay when one of its grounds applies. The right is not absolute; exceptions include legal obligations, public-interest processing, qualifying research or archives, and the establishment, exercise, or defence of legal claims. [S1] [S2]
- Article 19 requires a controller to communicate an erasure to recipients to whom the data was disclosed unless doing so is impossible or requires disproportionate effort, and to identify those recipients to the data subject on request. [S1] [S2]
- Article 20 requires a structured, commonly used, machine-readable format and transmission without hindrance when its conditions apply. [S1] [S3]
- Article 28 requires a processor to assist its controller with data-subject rights and, at the controller's choice after service ends, delete or return personal data and delete copies unless law requires storage. Contracts with processors and subprocessors need to make this operationally possible. [S1]
- The controller generally must respond within one month. The period may be extended by two further months for complex or numerous requests, but the person must be informed of the extension and reasons within the first month. Identity evidence must be proportionate to actual doubt. [S1] [S2]
- For backups, the ICO states that a valid request applies to backup systems as well as live systems. Where immediate overwrite is not feasible, backup data should be put beyond use, used for no other purpose, and replaced under the established backup schedule; the organization should explain this clearly to the person. [S2]

### 2.2 CCPA/CPRA

- California Civil Code §1798.105 requires a covered business receiving a verifiable deletion request to delete the consumer's personal information, direct service providers and contractors to delete it, and notify third parties to whom it sold or shared the information unless impossible or disproportionate. [S4]
- The statute permits limited retention where reasonably necessary for listed purposes, including completing a transaction, security and integrity, debugging, compatible internal uses, and legal obligations. [S4]
- A confidential deletion-request record may be retained only for permitted purposes such as preventing future sale or legal compliance. It should not become a shadow profile. [S4]
- §1798.130 generally requires fulfillment within 45 days, permits one additional 45-day extension when reasonably necessary with timely notice, and requires a readily usable format that can be transmitted without hindrance. Authentication may be required when reasonable for the sensitivity of the requested information. [S5]
- Information collected to verify a request may be used only for verification, must not be retained longer than necessary for verification, and must not be used for unrelated purposes. [S5]

### 2.3 Retention exceptions and legal holds

A deletion pipeline needs a per-record decision, not a blanket “retain everything for compliance” flag:

1. identify the exact law, claim, or contractual basis;
2. retain only the fields and time period required;
3. restrict retained records from normal product use;
4. record the reason, approver, review date, and expiry;
5. delete or de-identify the record when the exception expires.

Pseudonymization is not the same as anonymization under GDPR when the person remains identifiable using additional information. [S1]

## 3. Recommended reference workflow

The steps below are engineering recommendations. Their exact timing and authority rules must be set by product policy and applicable law.

### 3.1 Tenant export

```text
requested
  -> identity_and_authority_verified
  -> scope_frozen
  -> generating
  -> ready
  -> downloaded | expired
  -> artifact_deleted
```

1. **Authenticate and authorize**
   - Require a fresh authentication factor or recent-login check for a full tenant export.
   - Verify that the requester is the current tenant owner or has an explicit export permission.
   - Resolve `tenant_id` from the authenticated server-side context. If an object or tenant ID appears in the route, body, or job payload, independently authorize it.
   - Record the purpose: contractual tenant export, Article 15 access, Article 20 portability, or CCPA access.

2. **Freeze and document scope**
   - Create an immutable request record with `request_id`, tenant, requester, request type, policy version, requested scope, and cutoff time.
   - Use a database snapshot or explicit `as_of` boundary so related files do not represent different points in time.
   - Define whether changes after the cutoff are excluded or trigger regeneration.

3. **Generate asynchronously**
   - Return `202 Accepted` with a non-enumerable job identifier for large exports.
   - Read in bounded pages or with server-side cursors; do not load the whole tenant into memory.
   - Apply tenant scope to every query and storage key, including association and event tables.
   - Make the job idempotent by tenant, request type, scope hash, and idempotency key.

4. **Package a portable result**
   - Use a versioned ZIP containing a UTF-8 `manifest.json` plus JSON/JSONL as the canonical representation. CSV can be included for tabular convenience.
   - The manifest should include schema version, generation and cutoff timestamps, included datasets, field descriptions, row counts, file checksums, exclusions, and known retention exceptions.
   - Preserve stable business identifiers and relationships needed to interpret the data. Internal authorization claims and secrets should be excluded.
   - Include original uploaded files only when the tenant is authorized to receive them and third-party rights have been considered.

5. **Deliver securely**
   - Prefer an authenticated download endpoint for the strongest identity binding.
   - If object storage is used, create a private, encrypted, tenant-prefixed object and issue a short-lived signed URL only after a fresh authorization check.
   - AWS documents that presigned URLs are bearer tokens usable by anyone who possesses them until expiry; they are not intrinsically bound to the user after issuance. Keep the lifetime short, avoid logging the URL, and delete the artifact on expiry. [S10]

6. **Close the artifact lifecycle**
   - Log generation, download, expiry, and purge events without logging the export contents or signed URL.
   - Delete failed partial artifacts and completed artifacts after the declared TTL.
   - A successful tenant export does not cancel or delete the tenant unless the requester separately confirmed that action.

### 3.2 Tenant deletion

```text
requested
  -> identity_and_authority_verified
  -> retention_assessed
  -> scheduled
  -> access_revoked
  -> deleting
  -> processors_pending
  -> backup_expiry_pending
  -> completed | completed_with_documented_exceptions
```

1. **Verify authority and intent**
   - Require recent re-authentication; OWASP identifies missing password confirmation for sensitive operations as a broken-authentication risk. [S7]
   - Show the tenant name and impact summary, require explicit confirmation, and send an out-of-band notice to other owners if the product supports multiple owners.
   - Do not require an export as a condition of deletion, but offer it before destructive work begins.

2. **Assess contract, billing, and retention**
   - Stop future billing according to the contract; preserve only legally required financial records in a restricted archive.
   - Resolve active disputes, legal holds, and statutory retention by dataset and field.
   - Inform the requester what will be deleted, retained, put beyond use in backups, and when.

3. **Schedule or execute**
   - For ordinary product closure, a documented cancellation window may be offered.
   - For an accepted statutory erasure request, do not let a recovery window cause the legal response deadline to be missed. “Scheduled” or soft-deleted data remains personal data until it is erased or irreversibly anonymized.

4. **Revoke access immediately**
   - Mark the tenant non-operational.
   - Revoke refresh sessions, access tokens, API keys, active WhatsApp/Redis sessions, OAuth credentials, and background-job admission.
   - Stop reminders, mailbox lookup, and outbound messages before destructive tasks race with deletion.

5. **Run a durable deletion saga**
   - Commit the deletion request and outbox/task records before calling external systems.
   - Give every store or processor an idempotent step with `pending`, `running`, `succeeded`, `failed`, and `not_applicable` states.
   - Retry transient failures with bounded exponential backoff and send exhausted failures to manual review.
   - Do not report completion while a required processor deletion is merely queued.

6. **Delete or restrict each data location**
   - Hard-delete tenant-owned operational rows and explicitly delete identity rows that do not cascade from the tenant.
   - Remove Redis keys, queues, deduplication records, search indexes, generated exports, and object-store files.
   - Delete or revoke integrations and instruct processors/subprocessors to erase applicable data.
   - For legally retained records, remove non-required fields and prevent normal application queries from reading them.

7. **Reconcile backups**
   - Record the backup sets and expiry dates that can still contain tenant data.
   - Keep those copies beyond normal use and ensure restore runbooks reapply the erasure before production access is enabled. [S2]
   - Cryptographic erase may be used only when its key and encryption preconditions are demonstrably satisfied. NIST requires that relevant data never existed unencrypted and that all target-key copies can be sanitized. [S9]

8. **Complete with minimal evidence**
   - Store a deletion receipt containing request/job IDs, timestamps, policy version, step outcomes, exception categories, and processor acknowledgements.
   - Minimize direct identifiers. Hashing an identifier does not automatically make it anonymous; apply a lawful purpose and retention limit to the receipt itself. [S1]
   - Notify the requester of completion or documented exceptions, then remove the contact channel if it is also subject to deletion.

## 4. Store-by-store coverage for TrackPal

| Location | Tenant data or risk | Required offboarding check | TrackPal evidence |
|---|---|---|---|
| **PostgreSQL tenant rows** | Tenant profile, settings, clients, catalog, subscriptions, events, reminders, mailbox configuration, lookup jobs, delivery logs, blocks, and service selections | Enumerate every FK path; verify hard deletion or documented retention; test zero remaining tenant-scoped rows | `docs/architecture/database-schema.md` [T1] |
| **PostgreSQL identity rows** | Tenant owner and each client have separate `users` rows; refresh sessions belong to users | Explicitly delete owner/client users and refresh sessions; do not assume deleting `tenants` deletes parent `users` rows | `backend/app/services/tenant_service/mutations.py:198-237` [T5] |
| **Encrypted application fields** | Evolution token, mailbox OAuth/IMAP secrets, subscription password/PIN | Delete ciphertext and any separate key material; never place plaintext secrets in the export | `docs/architecture/database-schema.md`; `docs/architecture/mailbox-ingestion.md` [T1] [T3] |
| **Redis primary and backup** | WhatsApp sessions, client context, unauthenticated sessions, mailbox queues/results | Delete tenant/user/session keys from both configured Redis systems; remove queued jobs or make workers reject deleted tenants | `docs/architecture/system-overview.md`; `docs/architecture/mailbox-ingestion.md` [T2] [T3] |
| **Evolution Go/API** | Tenant WhatsApp instance, webhook configuration, provider-side sessions and message-related state | Invoke idempotent instance deletion and retain an acknowledgement/error state | `docs/architecture/evolution-integration.md`; `backend/app/services/tenant_service/mutations.py:198-237` [T4] [T5] |
| **Google/Microsoft mailbox authorization** | Refresh/access tokens are deleted locally, but the external OAuth grant may remain | Revoke or disconnect provider authorization where supported, then delete local token ciphertext; Google documents its token-revocation endpoint | Google OAuth 2.0 server docs [S12]; `docs/architecture/mailbox-ingestion.md` [T3] |
| **n8n** | Webhook and reminder payloads can appear in saved execution data | Configure minimal execution saving and pruning; determine how to locate/delete tenant-bearing execution records and any binary data | n8n execution-data documentation [S13]; `docs/architecture/system-overview.md` [T2] |
| **Application and platform logs** | Names, phones, emails, tenant IDs, JIDs, request bodies, errors, and signed URLs may leak into logs | Inventory log sinks and retention; delete where required or retain only under documented basis; prevent secrets and sensitive data at ingestion | OWASP Logging Cheat Sheet [S8]; `docs/code-standard/logging-guidelines.md` [T6] |
| **Metrics and traces** | Labels can accidentally contain tenant identifiers or personal data | Use bounded non-personal labels; document retention and deletion capability | OWASP Logging Cheat Sheet [S8] |
| **Database/platform backups** | Deleted PostgreSQL records may remain in snapshots | Document provider retention, beyond-use controls, expiry, and restore-time erasure replay | ICO backup guidance [S2] |
| **Future export storage** | Export archives concentrate the tenant's data | Private encryption, tenant-prefixed keys, short download TTL, artifact auto-purge, and orphan cleanup | AWS presigned URL documentation [S10] |
| **Shared global tables** | Global service definitions or system configuration may not belong to one tenant | Delete tenant associations, not legitimate global records; verify that global rows do not embed tenant personal data | `docs/architecture/database-schema.md` [T1] |

## 5. TrackPal current-state observations

These observations describe the repository on the research date; they are not a completed design.

### Existing strengths

- Tenant data uses explicit `tenant_id` ownership and PostgreSQL RLS for documented core tables. Composite foreign keys prevent some cross-tenant relationships. [T1]
- Tenant deletion is restricted to inactive tenants. The service explicitly loads and deletes client users and the tenant owner user, allowing cascades to remove dependent tenant records and refresh sessions. [T5]
- Evolution instance deletion is already part of tenant lifecycle deletion, and its client treats a missing instance as an idempotent outcome. [T4] [T5]
- The WhatsApp Master flow requires a typed confirmation before tenant deletion. [T7]
- Mail lookup results are mostly ephemeral and mailbox jobs and delivery logs already have short retention rules. [T3]

### Gaps to resolve before claiming complete offboarding

- The REST tenant deletion endpoint is Master-only and directly invokes synchronous hard deletion. The repository does not document a tenant-owner self-service offboarding request, durable deletion job, status resource, completion receipt, legal-hold evaluation, or export API. [T6] [T5]
- `delete_tenant()` flushes database deletion, calls Evolution, and then commits. External and database state cannot be atomically committed together; a process or commit failure after successful Evolution deletion can leave a retained tenant with a missing external instance. A durable saga/outbox would make state and retries observable. [T5]
- The current deletion function does not explicitly clear Redis session/context keys, cancel queued mailbox work, revoke external OAuth grants, inspect n8n execution data, reconcile logs, or track backups. [T5]
- The current model has one tenant owner, so authority is simple today. Any future multi-admin or ownership-transfer feature will need explicit `export_tenant` and `delete_tenant` permissions and rules for notifying co-owners. [T1]
- RLS and application-level tenant filtering must both be covered by negative tests. OWASP requires object-level authorization for every endpoint that accepts an object identifier; UUID unpredictability is not authorization. [S6]

## 6. API and job shape

A possible resource-oriented shape is:

```http
POST /api/v1/tenant-exports
GET  /api/v1/tenant-exports/{request_id}
POST /api/v1/tenant-exports/{request_id}/download
DELETE /api/v1/tenant-exports/{request_id}

POST /api/v1/tenant-deletion-requests
GET  /api/v1/tenant-deletion-requests/{request_id}
POST /api/v1/tenant-deletion-requests/{request_id}/confirm
DELETE /api/v1/tenant-deletion-requests/{request_id}  # only while cancellable
```

Recommended properties:

- derive the subject tenant from authenticated context for tenant self-service;
- allow a Master to specify a tenant only through a separately authorized administrative route;
- accept an `Idempotency-Key` on creation;
- return `202 Accepted` for asynchronous work;
- keep status responses free of personal data and secrets;
- use opaque request IDs and enforce object authorization on every status/download/cancel call;
- generate the signed URL on demand instead of persisting it;
- make deletion steps safe to replay after timeout or worker restart;
- retain a machine-readable per-step manifest for operational evidence.

## 7. Security and privacy controls

### Authorization and identity

- Re-authenticate for export and deletion; do not rely only on a long-lived browser session. [S7]
- Verify object-level authorization in every endpoint, worker, repository query, and download path. [S6]
- Never trust `tenant_id` merely because it is a UUID or came from the frontend.
- Rate-limit request creation and confirmation, but do not use rate limiting as authorization.
- Notify the account contact of a deletion request and of material status changes.

### Audit

OWASP identifies user deletion and data export as events worth auditing, but also says access tokens, passwords, encryption keys, sensitive personal data, and many session values should not be logged directly. [S8]

A minimal event can contain:

```json
{
  "event": "tenant_deletion_step",
  "request_id": "opaque-id",
  "actor_id": "internal-id",
  "tenant_ref": "restricted-internal-ref",
  "step": "evolution_instance",
  "result": "succeeded",
  "occurred_at": "RFC3339 timestamp",
  "policy_version": "v1"
}
```

Do not log export contents, credentials, request bodies containing personal data, or signed download URLs.

### Temporary export artifacts

- private bucket/container only;
- server-side encryption and least-privilege write/read/delete roles;
- unpredictable object keys with tenant and request separation;
- short URL and artifact TTLs;
- checksum and content-length verification;
- cleanup of failed multipart uploads and abandoned jobs;
- no CDN/public caching;
- authenticated regeneration of an expired URL.

## 8. Failure modes to test

| Failure | Expected behavior |
|---|---|
| Requester changes a route tenant ID | `403` or non-disclosing `404`; no job or side effect |
| Export query omits a tenant predicate | RLS blocks cross-tenant rows; test fails before release |
| Large tenant exceeds memory | Export streams/pages with bounded memory and resumable job state |
| Worker crashes midway | The same request resumes idempotently without duplicating artifacts or notifications |
| Evolution is unavailable | Database request remains pending/failed with retry; tenant is not falsely reported deleted |
| Evolution deletion succeeds but the worker crashes | Retry treats provider “not found” as success and continues |
| Redis primary or backup is unavailable | Step remains incomplete and alerts; stale sessions are not ignored in the completion claim |
| OAuth revocation fails | Local credentials are disabled/deleted, provider step retries, and manual action is visible |
| n8n keeps execution payloads | Retention/deletion step remains open until policy is satisfied |
| Signed URL leaks | Short expiry limits exposure; artifact can be deleted; a new URL requires authentication |
| Backup restore contains erased tenant | Restore gate reapplies the deletion suppression list before production access |
| Legal hold exists for one dataset | Only that dataset/fields are restricted and retained; other tenant data is deleted |
| Duplicate deletion request arrives | Same effective request/result; no duplicate destructive race |
| Notification channel is deleted too early | Completion notice is queued/sent before the final contact field is erased |

## 9. Acceptance criteria for a future implementation

1. A versioned data inventory maps every tenant dataset to owner, controller/processor role, export rule, retention period, deletion method, backup behavior, and subprocessor.
2. Tenant closure, full tenant export, personal-data access/portability, and personal-data erasure are distinct request types.
3. Only the authorized tenant owner/administrator or separately authorized Master can create, inspect, download, confirm, or cancel a request.
4. Cross-tenant negative tests cover every API, background worker, database query, object key, and status/download endpoint.
5. Export uses a consistent cutoff, bounded memory, a documented schema, a manifest, and no default secret export.
6. Export artifacts are private, encrypted, short-lived, auditable, and automatically deleted.
7. Access is revoked before destructive deletion starts, and background jobs cannot recreate tenant data.
8. Every deletion target has an idempotent, observable step with retry and manual escalation.
9. PostgreSQL tests prove there are no orphan tenant, client, user, refresh-session, mailbox, subscription, or selection records after hard deletion, except documented retained records.
10. Redis primary and backup, Evolution, OAuth grants, n8n execution data, logs, and exports are included in completion checks.
11. A backup restore drill proves erased tenant data cannot become active again.
12. Completion receipts contain enough evidence to audit the process but follow their own purpose and retention limits.
13. User-facing status and notices accurately distinguish deleted, retained under exception, processor pending, and backup-expiry pending states.
14. Operational runbooks define ownership, alerts, retry limits, manual remediation, and how to answer the requester within applicable deadlines.

## 10. Questions that must be answered before design

1. In each market, is TrackPal the controller/business, a processor/service provider for the tenant, or both for different datasets?
2. Which jurisdictions and contractual retention rules apply to tenant, client, subscription, and invoice data?
3. Should a tenant owner be able to self-delete, or must a Master approve? What evidence establishes organizational authority?
4. Is a recovery window desired for ordinary closure, and how will statutory erasure requests bypass or fit within it?
5. What billing/payment provider exists or is planned, and which records must be retained there?
6. What are the actual PostgreSQL backup and Render log retention periods, and can restored data be gated before use?
7. Does the deployed n8n save successful, failed, manual, or progress execution data, and where is binary data stored?
8. Does Evolution retain message content or only instance/session metadata, and what acknowledgement proves instance deletion?
9. Should a contractual tenant export include subscription credentials? The safer default is no; any exception needs separate explicit authorization, encryption, and product policy.
10. Which user notification channel remains available after access revocation and before final erasure?
11. Are there analytics, error tracking, support tools, email providers, or object stores not yet represented in the architecture documentation?
12. What evidence and retention period are required for deletion receipts and backup suppression markers?

## Sources

All external sources below are statutes, regulators, standards bodies, upstream security guidance, or first-party service documentation.

- **[S1]** European Union, General Data Protection Regulation, consolidated text: <https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:02016R0679-20160504>
- **[S2]** UK Information Commissioner's Office, *Right to erasure*: <https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/individual-rights/individual-rights/right-to-erasure/>
- **[S3]** European Data Protection Board, *Guidelines on the right to data portability under Regulation 2016/679, WP242 rev.01*: <https://www.edpb.europa.eu/documents/guideline/guidelines-on-the-right-to-data-portability-under-regulation-2016679-wp242_en>
- **[S4]** California Civil Code §1798.105, *Consumers' Right to Delete Personal Information*: <https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=CIV&sectionNum=1798.105>
- **[S5]** California Civil Code §1798.130, *Notice, Disclosure, Correction, and Deletion Requirements*: <https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=CIV&sectionNum=1798.130>
- **[S6]** OWASP API Security Top 10 2023, *API1: Broken Object Level Authorization*: <https://owasp.org/API-Security/editions/2023/en/0xa1-broken-object-level-authorization/>
- **[S7]** OWASP API Security Top 10 2023, *API2: Broken Authentication*: <https://owasp.org/API-Security/editions/2023/en/0xa2-broken-authentication/>
- **[S8]** OWASP Cheat Sheet Series, *Logging Cheat Sheet*: <https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html>
- **[S9]** NIST SP 800-88 Rev. 2, *Guidelines for Media Sanitization* (2025): <https://doi.org/10.6028/NIST.SP.800-88r2>
- **[S10]** Amazon Web Services, *Download and upload objects with presigned URLs*: <https://docs.aws.amazon.com/AmazonS3/latest/userguide/using-presigned-url.html>
- **[S11]** California Civil Code §1798.140, *Definitions*: <https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=CIV&sectionNum=1798.140>
- **[S12]** Google Identity, *Using OAuth 2.0 for Web Server Applications* (token revocation section): <https://developers.google.com/identity/protocols/oauth2/web-server#tokenrevoke>
- **[S13]** n8n, *Manage execution data*: <https://docs.n8n.io/deploy/host-n8n/configure-n8n/scaling/manage-execution-data>

### TrackPal repository evidence

- **[T1]** `docs/architecture/database-schema.md`
- **[T2]** `docs/architecture/system-overview.md`
- **[T3]** `docs/architecture/mailbox-ingestion.md`
- **[T4]** `docs/architecture/evolution-integration.md`
- **[T5]** `backend/app/services/tenant_service/mutations.py:198-237`
- **[T6]** `backend/app/api/v1/endpoints/tenants.py:106-118` and `docs/code-standard/logging-guidelines.md`
- **[T7]** `backend/tests/test_whatsapp_lifecycle_flow.py:590-673`
