# User Help System Architecture

## Purpose

This document explains the approved architecture for TrackPal's private Markdown-backed manuals and Tenant Admin Orientation Tour. Product behavior and content requirements are defined in [User Help and Tenant Orientation Requirements](../project-pdr/user-help-requirements.md). The source-of-truth decision is recorded in [ADR-0001](../adr/0001-markdown-capability-registry-for-user-help.md).

## System Boundary

```text
Repository Markdown topics
        │
        ▼
Build validator and compiler
        │
        ├── validates capability contracts and locale parity
        └── emits versioned private Help artifact
                         │
                         ▼
Authenticated Help API ────────── Tenant Help state
        │                         (acknowledged Tour Releases)
        ▼
React Help client
        ├── Help Center and full-text search
        ├── Contextual Help Sheet
        └── React Joyride Orientation Tour
```

The public Vite bundle contains the Help client and presentation components, but not manual prose or private search data. The first tracer is a single bilingual Tenant Admin Dashboard topic; the Help navigation and page remain behind `VITE_PRIVATE_HELP_ENABLED=false` by default until the full Help release is complete.

## Tracer implementation

- Markdown sources live under `backend/help/{en,es}/tenant-admin/` and are compiled by `backend/scripts/compile_help.py`.
- `app.help.compiler` rejects unknown frontmatter, unsafe Markdown, duplicate IDs, invalid routes or targets, and Spanish/English metadata drift.
- The generated artifact is private backend data at `backend/app/help/artifact.json`; it is never imported by the frontend build.
- Authenticated Tenant Admins and Clients use `GET /api/v1/help`, `GET /api/v1/help/topics/{topic_id}`, and `GET /api/v1/help/search`. Each operation filters by the caller's audience, Tenant plan, and locale; Master users and Master Support Context receive 404.
- The common Tenant Admin release includes mirrored Dashboard, Language, Profile, Password, and WhatsApp topics for Starter and Pro.
- Dashboard and Settings use semantic targets such as `data-help-id="admin.dashboard"` and `data-help-id="admin.settings.profile"`; these identifiers are independent of translated labels and CSS.
- The Help Center groups topics by the same module order as the Tenant Admin navigation and exposes only declarative, allow-listed module or Settings-category links.
- The shared Tenant Admin layout provides contextual Help in a responsive Sheet. It resolves the most specific current target, loads the authorized topic, and leaves the underlying screen mounted so local form state is preserved.

## Canonical Markdown Source

Help topics use safe Markdown with strict frontmatter. Raw HTML, scripts, MDX, and executable components are rejected.

Spanish and English live in mirrored directories and share the same topic IDs, metadata shape, capability references, links, and Tour Release membership. Localized prose, headings, search synonyms, and tour copy may differ.

A topic frontmatter contract must identify at least:

- Stable topic ID
- Audience: `tenant_admin` or `client`
- Eligible plans
- Channels: Web, WhatsApp, or both
- Module and capability IDs
- Related route or Settings category
- Stable `data-help-id` targets
- Explicit navigation order and allow-listed safe navigation destination
- Search tags and maintained synonyms
- Related topic IDs
- Optional Tour Release, order, target, safe preparation action, and conditional-target rule

The compiler treats IDs and visibility metadata as product contracts. Prose remains human-authored Markdown.

## Compiled Help Artifact

The build produces a versioned artifact containing:

- Artifact schema version
- Content version or source revision
- Localized authorized-topic payloads
- Role and plan visibility metadata
- Module navigation trees
- Full-text search index data
- Internal-link graph
- Contextual-help target map
- Tour Release definitions and steps
- Expected frontend target-contract version

The artifact is built once per application release. Runtime users never modify it.

## Authentication and Authorization

The Help API applies the same authenticated identity and active Tenant context used by the product.

- **Tenant Admin**: receives Tenant Admin topics filtered to the Tenant's current plan and locale.
- **Client**: receives Client topics for the associated Pro Tenant and locale.
- **Master and Master Support Context**: receive no Tenant Admin or Client Help surface.
- **Unauthenticated user**: receives no manual index, content, search data, or tour definition.

Authorization is enforced by the backend. Frontend filtering is presentation only and must not be treated as a security boundary.

## API Responsibilities

The private API should expose cohesive user-facing operations rather than raw repository files:

- Get the authorized Help navigation and artifact compatibility metadata
- Get one authorized localized topic
- Search authorized localized topics
- Get an eligible unseen Tour Release
- Replay an eligible Tour Release from Help
- Mark a Tour Release completed or skipped for the active Tenant

Topic and search endpoints must return not-found behavior for content outside the caller's role or plan, consistent with existing plan gates.

The API must not expose filesystem paths, raw frontmatter, unpublished topics, or another Tenant's Help state.

## Tenant Help State

Orientation state is Tenant-scoped because onboarding belongs to the business rather than an individual Tenant Admin.

The state model records acknowledgements keyed by:

- Tenant
- Tour Release ID
- Status: completed or skipped
- Acknowledgement timestamp

A unique Tenant and Tour Release constraint prevents duplicate acknowledgements. Closing after confirmation records skipped. Unexpected failures, missing required targets, Help API errors, and artifact incompatibility record nothing.

Initial Starter, initial Pro, Starter-to-Pro, and future feature-announcement tours are separate Tour Releases. Eligibility is declared in the compiled artifact and evaluated against plan and acknowledged releases.

## Frontend Surfaces

### Routes

Tenant Admin and Client layouts receive dedicated authenticated Help Center routes. Help appears at the bottom of each role's navigation before account/logout.

The existing mobile layouts need a shared role-aware navigation drawer because their current headers do not expose module navigation. The drawer must render the same authorized destinations as desktop, including Help.

### Help Center

The Help Center consumes the authorized navigation tree, search endpoint, and topic endpoint. It uses:

- A topic navigator and search area
- A readable article column
- An optional wide-screen on-page table of contents
- A mobile topic Sheet
- Safe “Go to module” navigation

### Contextual Help

Visible screens and Settings categories declare stable `data-help-id` values. “Help about this screen” resolves the current target to an authorized topic and opens it in a side Sheet without navigating away or unmounting the active form.

### Orientation Tour

React Joyride 3 is the tour engine. TrackPal owns the custom tooltip, styling, route coordination, safe panel preparation, lifecycle handling, and mobile Sheet presentation.

The coordinator must:

1. Fetch one eligible Tour Release after Tenant Admin authentication.
2. Confirm artifact and frontend target-contract compatibility.
3. Resolve the current plan and viewport sequence.
4. Navigate to the step route.
5. Open only a declared safe view or Settings category.
6. Wait for the stable `data-help-id` target.
7. Display the step or apply its explicit conditional-target rule.
8. Acknowledge only explicit completion or confirmed skip.

Tour steps never call mutation services or secret-reveal operations.

## Responsive and Accessible Behavior

Desktop tour steps use anchored popovers. Mobile steps spotlight the target while rendering content and controls in a bottom Sheet.

All Help surfaces must support:

- Keyboard-only navigation
- Focus restoration after closing Help or the tour
- Visible focus rings
- Semantic headings and landmarks
- Screen-reader names for tour progress and controls
- WCAG 2.2 AA contrast
- Non-color-only status communication
- Longer Spanish and English labels
- Reduced motion, including disabling or replacing spotlight transitions

## Search

The compiler creates locale-specific full-text data from authorized topic fields and Markdown text. Search includes maintained beginner-friendly synonyms without changing canonical product labels.

The backend filters the searchable corpus by audience, plan, and locale before matching or constructing excerpts. Search results contain only authorized topic IDs, titles, matched excerpts, module labels, and routes into the Help Center.

## Safe Navigation

A Help topic may navigate to an authorized route and optionally request that a safe Settings category open. The navigation contract is declarative and allow-listed.

Help may not:

- Submit forms
- Persist edits
- Create or delete records
- Change status
- Reveal credentials
- Connect or disconnect integrations
- Generate or revoke keys
- Open destructive confirmations

## Failure Isolation

Help is non-critical to core TrackPal operations.

- Help API failure leaves the application usable and exposes Retry in Help.
- Manual content remains available when its artifact is authorized but its tour or contextual target-contract version differs from the frontend.
- Contextual Help reports an unavailable target rather than guessing a topic during version mismatch; the tour remains disabled during version mismatch.
- Unexpected missing required targets stop the tour safely and leave the Tour Release unseen.
- Logout, login, role changes, and Tenant context changes clear Help indexes, topics, and tour state from frontend memory.
- Private manual prose is not persisted to browser storage.

## Contract Validation

The highest automated test seam is the compiled Help artifact and its authenticated API behavior. This one seam validates the authoring source, authorization, plan filtering, locale parity, links, search, and Tour Release definitions without coupling tests to Markdown parser internals.

Build and CI validation covers:

- Frontmatter schema and safe-Markdown policy
- Unique and known IDs
- Spanish/English parity
- Known roles, plans, channels, modules, actions, routes, and targets
- Internal links and navigation allow-list
- Tour Release ordering, maximum seven steps, and eligibility
- Artifact schema and target-contract versions

Backend API tests cover:

- Tenant Admin Starter/Pro filtering
- Client filtering
- denial for Master, Master Support Context, unauthenticated users, and wrong-plan topics
- search authorization
- unseen, completed, skipped, replayed, upgrade, and update Tour Releases
- idempotent acknowledgement
- Help API failure isolation

Frontend unit and integration tests cover:

- Help navigation grouping, target resolution, safe navigation, and contextual Sheet behavior
- cache clearing on authentication or Tenant changes
- manual-visible/tour-disabled version mismatch
- safe route and Settings preparation
- completion and confirmed-skip callbacks
- desktop popover and mobile Sheet state
- reduced-motion and keyboard behavior where jsdom can verify it

The approved first version uses mandatory manual browser QA instead of automated E2E. Manual QA is therefore a release gate, not optional verification.

## Implementation Sequence

1. Complete a code-backed capability inventory and reconcile stale project documentation.
2. Define the Markdown frontmatter and artifact schemas and add the build validator/compiler.
3. Add Tenant-scoped Tour Release acknowledgement storage and authenticated Help API operations.
4. Add Help state management, routes, full-text search, Help Center, and contextual Sheet.
5. Add the shared Admin/Client mobile navigation drawer and stable `data-help-id` contracts.
6. Integrate React Joyride with route-aware, plan-aware, responsive sequences.
7. Author mirrored Spanish/English Tenant Admin and Client topics from implemented behavior.
8. Add contract, API, and frontend tests.
9. Complete the mandatory manual QA matrix before exposing the atomic release.

## Related Documentation

- [User Help and Tenant Orientation Requirements](../project-pdr/user-help-requirements.md)
- [ADR-0001: Use Markdown topics as the canonical user-help capability registry](../adr/0001-markdown-capability-registry-for-user-help.md)
- [Frontend Architecture](frontend-architecture.md)
- [WhatsApp Console Flow](whatsapp-console-flow.md)
- [Product Goals](../project-pdr/product-goals.md)
- [Business Rules](../project-pdr/business-rules.md)
