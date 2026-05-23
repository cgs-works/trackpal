# PRD: Python-Centered i18n for Trackpal System

> Created: 2026-05-22 23:30:01  
> Source: Brainstorm / GrillMe session  
> Status: Validated

## 1. Executive Summary

Trackpal needs end-to-end internationalization for tenant-facing and client-facing system text, with Python backend as source of truth across dashboard web UI, tenant WhatsApp console, n8n-driven outbound messaging, and master-to-tenant messages. Tenant language preference must persist in database, default to English, and take effect immediately across all channels. Phase 1 supports only English and Spanish, with English as source language and fallback. Intended next step: planning.

## 2. Problem Statement

Current system text is largely hardcoded in Spanish across backend, WhatsApp console flows, n8n fallback messaging, and frontend UI. This conflicts with new product requirement: tenant chooses language, and that choice must govern all tenant/client-visible system messages. Without central i18n, system risks duplicate text stores, inconsistent behavior across channels, and inability to localize messages sent by n8n or master workflows.

Affected parties:
- Tenant admins using dashboard and WhatsApp console
- Clients receiving tenant-generated reminders/messages
- Master users sending system messages to tenants
- Developers maintaining duplicated text in backend, frontend, and n8n

Triggers:
- Need multilingual operation with English default
- Need persistent tenant-level language selection
- Need n8n and WhatsApp responses to honor same tenant locale

## 3. Goals

- Centralize system text translation with backend Python as source of truth.
- Persist tenant locale and apply it immediately across web, WhatsApp, n8n, and master-to-tenant communication.
- Deliver phase 1 support for English and Spanish only.
- Ensure every visible system message in phase 1 has localized behavior with English fallback.

## 4. Non-Goals

- No client-specific language preference or override in phase 1.
- No i18n for master internal dashboard/conversation UI; master remains fixed Spanish.
- No translation of tenant-owned business data such as service names, plan names, client names, or other user-authored content.
- No database-managed translation CMS in phase 1.
- No support for languages beyond `en` and `es` in phase 1.

## 5. Users / Stakeholders

- Primary user or stakeholder: Tenant admin
- Secondary users or stakeholders: Tenant clients receiving messages; master users sending messages to tenants
- Admin/operator/developer concerns, if applicable:
  - avoid duplicated translation logic across backend, frontend, and n8n
  - maintain predictable fallback behavior
  - keep tenant locale as single source of preference truth

## 6. Requirements

### Functional Requirements

- FR-1: System must persist tenant language preference on tenant record, with default `en` for new tenants.
- FR-1a: Migration strategy must preserve current experience for existing tenants; planner must define safe backfill behavior for pre-existing tenant records.
- FR-2: Tenant must be able to change language from web dashboard and tenant WhatsApp console.
- FR-3: Language change must take effect immediately for subsequent responses/messages, including active WhatsApp sessions.
- FR-4: Backend must act as translation source for tenant/client-visible system text.
- FR-4a: Translation templates must support named placeholders such as `{tenant_name}`, `{expires_at}`, and `{days_left}`.
- FR-5: Dashboard web must render tenant-visible system text according to tenant locale.
- FR-5a: Planner must define frontend consumption contract so Vue can consume backend-provided translations without maintaining separate source-of-truth catalogs.
- FR-5b: Frontend must fetch locale catalog at login and refetch immediately after tenant language change.
- FR-6: Tenant WhatsApp console must render all prompts, menus, validation messages, and flow replies according to tenant locale.
- FR-6a: WhatsApp translation lookup must occur at runtime per request/session locale, not at module import/class-definition time.
- FR-7: n8n-sent messages to tenant and client must use tenant locale.
- FR-7a: n8n must act only as transport for tenant/client-facing localized text; backend must provide final rendered message content.
- FR-8: Master-to-tenant system messages/reminders must use tenant locale.
- FR-9: Master internal UI and master internal console text remain fixed Spanish.
- FR-10: If Spanish translation missing for key, system must fall back to English rather than fail.
- FR-11: Translation storage in phase 1 must live in versioned code files, not database.
- FR-12: Only system/UI text is translated; user-authored business data remains unchanged.
- FR-13: Translation engine design must accept explicit `locale` input so future phase can support per-client locale without reworking core translation primitives.
- FR-14: Backend must keep translation catalogs in memory at process runtime rather than reading files on every request/message.
- FR-15: Dates, times, and numbers visible to tenant/client in phase 1 must be formatted by backend according to locale.
- FR-16: Background jobs and async reminder flows must resolve tenant locale through security-compatible backend context, without assuming interactive request context.
- FR-17: Implementation phase must include systematic audit of hardcoded tenant/client-visible strings across backend, frontend, and n8n.

### Non-Functional Requirements

- Performance: i18n must add less than 50ms overhead to affected WhatsApp/API response paths.
- Reliability: Missing translation must not break flow; fallback to English required.
- Security/privacy: Locale persistence must follow existing tenant authorization boundaries; no cross-tenant locale leakage.
- Accessibility/UX: Language switch must be discoverable in tenant profile/settings and produce immediate user-visible effect.
- Compatibility/backward compatibility: New tenants default to English, while migration strategy for existing tenants must preserve current Spanish experience safely.
- Observability/logging: Missing translation keys and fallback events must emit warning logs plus simple counters/metrics, without leaking sensitive message content.

## 7. User Flows / System Flows

- Flow 1: New tenant default locale
  1. Master creates tenant.
  2. Tenant record persists locale `en` by default.
  3. Tenant first sees dashboard/WhatsApp/system messages in English.

- Flow 2: Tenant changes locale in web dashboard
  1. Tenant opens profile/settings.
  2. Tenant selects `es` or `en`.
  3. Backend persists new locale on tenant record.
  4. Frontend refetches locale catalog immediately.
  5. Next rendered dashboard content and subsequent outbound messages use new locale.

- Flow 3: Tenant changes locale in WhatsApp console
  1. Tenant enters profile/settings flow in WhatsApp console.
  2. Tenant selects `es` or `en`.
  3. Backend persists new locale on tenant record.
  4. Very next reply in same active session uses new locale.

- Flow 4: n8n outbound message generation
  1. n8n triggers backend-facing reminder or console flow.
  2. Backend resolves tenant locale.
  3. Backend generates final translated system text.
  4. n8n relays message without owning independent translation catalog.

- Flow 5: Master-to-tenant communication
  1. Master action targets specific tenant.
  2. Backend resolves tenant locale.
  3. Outbound tenant-facing message is rendered in tenant locale.

## 8. Data, State, and API Expectations

- Inputs:
  - tenant locale selection values: `en`, `es`
  - current tenant context for authenticated dashboard and WhatsApp flows
  - n8n/backend jobs requiring tenant-facing text generation
- Outputs:
  - localized API-visible text for tenant dashboard
  - localized WhatsApp reply strings
  - localized outbound reminder/message payloads sent through n8n/Evolution
- Persisted state:
  - tenant locale field on `tenants` table
- Data ownership/source of truth:
  - `tenants.locale` is single source of truth for language preference
  - backend code files are source of truth for translation catalogs
- API/CLI/UI contracts:
  - tenant-facing API surface must expose and accept tenant locale where needed
  - frontend must have defined backend contract for translation catalog retrieval or equivalent runtime translation payloads
  - frontend translation delivery in phase 1 uses backend-provided locale catalog fetched at login and after locale change
  - tenant profile/configuration UI must support viewing/updating locale
  - WhatsApp tenant profile flow must support viewing/updating locale
  - backend-to-n8n integration should provide already-localized text rather than require n8n-side translation ownership

## 9. Edge Cases and Error Handling

- Missing `es` translation key → fall back to English.
- Existing tenant created before migration → planner must preserve current Spanish experience via safe migration/backfill strategy.
- Tenant changes locale during active WhatsApp session → next reply immediately uses new locale.
- n8n job sends message after locale changed → message uses current persisted tenant locale at send/generation time.
- Dashboard needs locale-specific date/time/number formatting → backend returns correctly formatted values.
- Async jobs need `tenants.locale` under RLS-sensitive execution path → planner must define secure context resolution strategy.
- Unsupported locale input → reject and preserve prior locale.
- Master internal UI text requested for i18n → out of scope; remain Spanish.
- User-authored business strings containing Spanish/English text → pass through unchanged, not machine-translated.

## 10. Decisions Resolved During GrillMe

| Decision | Chosen Answer | Rationale | Alternatives / Rejected Options |
|---|---|---|---|
| Translation ownership | Backend as source | Avoid duplication across web, WhatsApp, and n8n; central consistency | Frontend/backend split; frontend-only web |
| Preference scope | Single tenant locale | Simple model; one locale governs tenant and client-facing system text | Client override |
| Locale effect timing | Immediate total | Better UX; preference persistence reflected instantly | Next session; jobs-only delayed |
| Phase 1 coverage | All visible system text | Avoid mixed-language UX | UX-only subset; messaging-only |
| Source language | English | Matches default locale and future extensibility | Spanish source; mixed source |
| Missing translation behavior | Fallback to English | Preserve continuity and avoid broken flows | Visible error; hide text |
| Master internal language | Fixed Spanish | Limits phase 1 scope while meeting tenant-facing needs | Fixed English; configurable master |
| Locale change channels | Web + WhatsApp | Omnichannel consistency for tenant self-service | Web only; WhatsApp only |
| New tenant initial locale | Default English | Simple default with later self-service change | Choose at create; infer by country |
| Existing tenant migration | Preserve Spanish behavior | Avoid surprise language regression for current tenants | Blind backfill to English |
| i18n content scope | System/UI text only | Avoid phase 1 data-model expansion for business content | Include catalogs; everything editable |
| n8n translation source | Backend generates final text | Prevent duplicated templates in n8n | n8n-local translations; hybrid |
| Preference storage | `tenants.locale` | Single source of truth on tenant model | Profile field; separate settings table |
| Translation storage | Versioned code files | Simple, auditable, enough for `en/es` | Database; mixed |
| Runtime translation lookup | Dynamic by locale at request time | Required for WhatsApp/session correctness | Static class-definition translation |
| Frontend translation delivery | Backend-defined contract | Needed to keep backend source-of-truth promise | Implicit/undefined frontend behavior |
| Frontend translation fetch timing | Login + language change | Fresh enough without per-route overhead | Every navigation; login only |
| Placeholder contract | Named braces | Safer and clearer across locales/channels | Positional placeholders; manual string building |
| Backend translation cache | In-memory process cache | Avoid request-time file I/O and latency | Read per request; Redis cache |
| Locale formatting owner | Backend formats | Preserves backend source-of-truth across channels | Frontend formats; mixed by channel |
| Fallback observability | Warning log + counter | Detect gaps without breaking UX | Log only; no observability |
| Performance target | <50ms extra overhead | Sets explicit ceiling for i18n cost | Non-numeric target; looser budget |
| Async job locale access | Secure context resolution | Preserve security while supporting background work | Ignore RLS; duplicate locale in jobs |
| Hardcoded string audit | Systematic sweep | Reduce untranslated leaks in legacy code | Touched modules only; QA-only detection |
| WhatsApp active-session behavior | Immediate change | Same locale behavior across channels | Hold until restart; ask restart |
| Tenant selector placement | Tenant profile/settings | Natural home for preference | Initial screen only; both |

## 11. Open Questions

No material open questions remain.

## 12. Constraints and Risks

| Constraint/Risk | Impact | Mitigation |
|---|---|---|
| Existing backend and frontend text is largely hardcoded | High migration surface, inconsistent missed strings risk | Plan phased inventory and replacement by module/channel |
| Frontend currently owns visible UI copy locally | Backend-as-source requirement needs explicit contract design | Planner should define minimal contract for web i18n delivery |
| n8n currently contains static Spanish fallback messaging | Mixed ownership risk if left unchanged | Move fallback/templated tenant-facing text ownership to backend |
| WhatsApp templates currently live as class constants in Spanish | Broad refactor needed in console services | Centralize translation lookup and replace inline constants incrementally |
| No frontend test suite exists | Higher regression risk for web i18n UI | Rely on manual QA plus build verification; consider minimal smoke checks in plan |
| Migration/backfill for existing tenants | Wrong defaults or null locales may leak inconsistent behavior; English backfill may regress current tenants | Add DB default for new rows and preserve Spanish behavior for existing tenant rows in migration plan |
| Future client-specific locale support | Hardcoding tenant-only assumptions could force rewrite later | Keep translation primitive parameterized by explicit locale string |
| Translation performance regression | i18n may slow webhook/API responses if implemented naively | Keep catalogs in memory and validate <50ms added overhead |
| RLS-sensitive background locale reads | Async flows may fail or bypass security incorrectly | Plan explicit secure access pattern for jobs/reminders |
| Incomplete hardcoded-text migration | Legacy Spanish strings may leak into production | Require systematic search/audit across backend, frontend, and n8n |

## 13. Acceptance Criteria

- [ ] New tenant records persist locale `en` by default.
- [ ] Existing tenant records are migrated/backfilled with behavior that preserves current Spanish experience.
- [ ] Tenant can view and change locale from dashboard profile/settings.
- [ ] Tenant can view and change locale from WhatsApp tenant profile/settings flow.
- [ ] After locale change, next dashboard response/rendered system text uses new locale.
- [ ] After locale change during active WhatsApp session, next reply uses new locale.
- [ ] n8n-sent tenant/client messages use current tenant locale.
- [ ] Master-to-tenant system messages use current tenant locale.
- [ ] If `es` translation missing for any shipped key, user sees English fallback, not error.
- [ ] Master internal dashboard/conversation text remains Spanish.
- [ ] User-authored business data remains untranslated and displayed as stored.
- [ ] WhatsApp tenant console text is resolved dynamically from locale at runtime, not frozen by module-load constants.
- [ ] Frontend uses backend-defined translation contract without becoming independent source of translation truth.
- [ ] Frontend fetches locale catalog at login and refetches it immediately after tenant language change.
- [ ] Translation templates support named placeholders consistently across backend/web/WhatsApp/n8n usage.
- [ ] Backend formats locale-sensitive dates, times, and numbers for tenant/client-visible system output.
- [ ] Translation catalogs are served from in-memory runtime cache, not read from disk per request.
- [ ] Fallback to English emits warning log and counter/metric.
- [ ] i18n overhead stays below 50ms extra on affected WhatsApp/API paths.
- [ ] Implementation includes systematic audit for hardcoded tenant/client-visible strings across backend, frontend, and n8n.

## 14. Verification Strategy

- Tests/checks needed:
  - backend tests for locale persistence, fallback behavior, and localized WhatsApp/API responses
  - backend tests for n8n/message-generation locale behavior
  - backend tests for named placeholder interpolation and locale-specific formatting
  - backend tests for in-memory translation catalog loading/cache behavior
  - migration tests or validation for existing tenant default/backfill
  - focused frontend verification for locale switch rendering and persistence
  - verification that locale catalog refetch happens on login and after locale change
  - verification or measurement of i18n overhead against <50ms target on affected paths
  - systematic search/audit output for hardcoded Spanish strings in backend, frontend, and n8n
- Manual QA needed:
  - tenant dashboard locale toggle `en ↔ es`
  - tenant WhatsApp locale toggle within active session
  - n8n reminder dispatch in both locales
  - master-to-tenant message path in both locales
- Build/lint/typecheck expectations:
  - backend pytest subset/full as risk warrants
  - frontend build must pass
  - any touched workflow JSON or related config should remain valid
- Rollback/recovery validation, if applicable:
  - confirm safe rollback path for migration adding locale column/default
  - confirm system behavior if locale field absent/null during deployment window
  - confirm existing tenants do not unexpectedly flip from Spanish to English after migration

## 15. Planning Handoff

Use this section as input for Planner.

- Recommended planning path:
  - design backend i18n core first
  - define tenant locale persistence/API contract
  - adapt WhatsApp and n8n flows
  - adapt dashboard web consumption/rendering
  - verify end-to-end fallback behavior
- Suggested phase boundaries:
  1. Data model + backend i18n primitives
  2. Tenant locale read/write surfaces (API + WhatsApp)
  3. Backend channel migration (WhatsApp, reminders, master-to-tenant)
  4. Dashboard web localization integration with explicit backend translation contract
  5. QA/fallback sweep
- Files/modules likely involved:
  - `backend/app/models/tenant.py`
  - `backend/app/schemas/` related tenant/profile/me/dashboard schemas
  - `backend/app/api/v1/endpoints/` tenant/profile/integrations/dashboard endpoints
  - `backend/app/services/whatsapp_*`
  - `backend/app/services/subscription_job_service.py` and reminder/message generation paths
  - `backend/app/core/` new i18n module(s)
  - `frontend/src/views/TenantDashboardView.vue`
  - `frontend/src/views/LoginView.vue` and other tenant-facing views as needed
  - `frontend/src/services/api.js`, `frontend/src/stores/auth.js`, router-adjacent UI if locale metadata needed
  - `n8n/Trackpal WhatsApp Bot.json`
  - `n8n/Trackpal Subscription Reminders.json`
- Commands/docs to inspect:
  - `docs/architecture/frontend-architecture.md`
  - `docs/architecture/whatsapp-console-flow.md`
  - `docs/architecture/n8n-workflow.md`
  - `docs/code-standard/backend-conventions.md`
  - `docs/code-standard/frontend-conventions.md`
  - `rg` across backend/frontend/n8n for hardcoded Spanish strings and response templates
- Known implementation constraints:
  - backend is strict async FastAPI stack
  - frontend has no TypeScript and no test harness
  - tenant console strings currently exist as Spanish class constants
  - n8n workflow currently contains Spanish fallback text
  - master internal surfaces must remain Spanish while outbound tenant-facing messages localize
  - frontend contract for consuming backend-owned translations must be defined during planning
  - existing tenants likely expect Spanish and cannot be blindly switched to English
  - formatting contract for placeholders/dates/numbers must stay consistent across web, WhatsApp, and n8n
  - backend i18n lookup must avoid per-request file I/O to satisfy latency target
  - async job locale resolution must be compatible with security/RLS constraints
- Minimum viable scope:
  - persist `tenants.locale`
  - central backend translation lookup with English fallback
  - localized tenant WhatsApp + n8n + master-to-tenant outbound text
  - localized tenant dashboard-visible system text
  - tenant locale update from web and WhatsApp profile/settings
  - login-time and language-change-time frontend catalog fetch/refetch
  - named placeholder support, backend-side locale formatting, and fallback observability
