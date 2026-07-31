# Service Icon Selector Design

**Date:** 2026-07-31
**Status:** Approved
**Scope:** End-to-end optional Service Icons for production and Demo Catalogs

## Summary

TrackPal will let each Tenant Admin assign, replace, or remove an optional SVG-based Service Icon while creating or editing a Catalog Service. The selector will search the complete Iconify catalog directly from the browser, show the selected collection's author and license, and persist only an Icon Reference such as `simple-icons:netflix`.

TrackPal will not scrape All SVG Icons, copy SVG files, proxy Iconify searches through the backend, or make Iconify availability part of the Service CRUD path. Existing and unavailable icons fall back to the generic `Package` representation.

## Context and Constraints

All SVG Icons has no supported public API for this use case, disallows its search and API paths in `robots.txt`, and documents that its previews are served through Iconify. Iconify provides supported search, collection metadata, and SVG delivery interfaces for the same open-source icon ecosystem.

The approved constraints are:

- Use Iconify as the technical source.
- Search the complete catalog rather than a curated subset.
- Do not store SVG markup or files in TrackPal.
- Preserve original palette colors where supplied by an icon set.
- Keep Service Icons optional.
- Display collection, author, license, and license link before selection.
- Do not translate search terms automatically.
- Do not block Service creation or editing when Iconify is unavailable.
- Show icons on all relevant Web and public catalog surfaces; WhatsApp remains text-only.

## Domain Model

### Service Icon

An optional visual mark chosen by a Tenant Admin for a Catalog Service. Missing or unavailable icons use a generic representation and do not change the Service's identity or behavior.

### Icon Reference

An external, portable identity for a Service Icon. It is distinct from the SVG asset and can travel through production, Demo, subscription, export, and Public API Catalog views.

The persisted representation is a provider-qualified Iconify identifier:

```text
<prefix>:<name>
```

Example:

```text
simple-icons:netflix
```

## Considered Approaches

### 1. Direct Iconify integration — selected

The browser searches Iconify and renders icons through the Iconify React library. The backend stores only the Icon Reference.

**Advantages**

- No TrackPal SVG storage or catalog replication.
- Minimum backend and operational complexity.
- Browser and Iconify caches handle repeated icon loads.
- Iconify remains replaceable behind a focused frontend module.

**Trade-offs**

- Tenant and public catalog browsers contact Iconify directly.
- Rendering depends on Iconify availability and therefore requires a local fallback.

### 2. TrackPal backend search proxy — rejected

The backend would query Iconify and temporarily cache search metadata while browsers continued to load SVGs from Iconify.

This adds rate limiting, caching, outbound backend networking, and another failure path without removing the external rendering dependency.

### 3. Self-hosted Iconify — rejected

TrackPal would operate an Iconify API and synchronize icon collections.

This contradicts the requirement not to copy the catalog and introduces disproportionate storage, synchronization, licensing, and operational work.

## Architecture

### Persistence

Add a nullable `icon` column to `services`. The column stores only the Icon Reference.

- Existing Services migrate with `icon = null`.
- `ServiceCreate`, `ServiceUpdate`, and `ServiceResponse` include `icon`.
- On create, an omitted or empty icon becomes `null`.
- On update, omitting `icon` preserves the current reference, while explicit `null` removes it.
- Backend validation is syntactic and local. It enforces a bounded length and the Iconify `prefix:name` shape without contacting Iconify.
- A saved reference is not silently cleared if the upstream icon later disappears.

### Contract propagation

The Icon Reference must be propagated anywhere a Service is represented visually or exported:

- Admin Catalog Service reads and mutations.
- Production Catalog Store contracts.
- Subscription creation/editing selectors and subscription rows or cards.
- Client dashboard subscription responses.
- Public API Catalog Service payloads.
- Tenant Data Export catalog records.
- Demo Workspace Service records and baseline data.

WhatsApp menus and messages continue to use Service names only.

### Public API Catalog

The public payload exposes the reference as:

```json
{
  "name": "Netflix",
  "icon": "simple-icons:netflix",
  "plans": []
}
```

TrackPal does not expose embedded SVG or guarantee provider availability. Public consumers choose their own Iconify renderer and fallback.

### Demo Workspace

The Demo Workspace schema version will be migrated so older valid workspaces receive `icon: null` without losing business changes. The Pro baseline will assign representative Icon References to its Services so prospects can evaluate icon rendering and editing.

Demo mutations use the same Service data-source contract as production and remain browser-local.

## Deep Module Design

The design concentrates external catalog complexity behind two small interfaces.

### `IconPicker` module

The external interface contains only the facts a form caller needs:

```ts
interface IconPickerProps {
  open: boolean;
  value: string | null;
  initialQuery?: string;
  onOpenChange: (open: boolean) => void;
  onSelect: (icon: string | null) => void;
}
```

The module hides:

- debounce and minimum-query rules;
- request cancellation;
- pagination;
- in-memory search caching;
- Iconify response parsing;
- collection metadata lookup;
- license visibility and confirmation rules;
- responsive layout;
- loading, empty, error, and retry states.

Deleting this module would force that complexity into every form, so the module provides real depth and locality.

### Internal `IconCatalog` seam

The picker uses an internal interface for the true external dependency:

```ts
interface IconCatalog {
  search(query: string, start?: number): Promise<IconSearchPage>;
  describe(icon: string): Promise<IconDetails>;
}
```

- Production uses an Iconify HTTP adapter.
- Tests use a deterministic fake adapter.
- The internal seam is not exposed to Catalog forms.

### `ServiceIcon` module

Callers provide an Icon Reference, accessible label, and presentation classes. The module hides Iconify rendering, load failure detection, original palette behavior, and the generic fallback.

This keeps rendering behavior consistent across Catalog, subscriptions, client dashboard, and Demo views.

## Selector Experience

The approved layout is a large dialog with a search grid and detail panel.

### Desktop

- Search and icon grid on the left.
- Large selected-icon preview and metadata on the right.
- Collection, author, license title, and official license link remain visible before confirmation.

### Mobile

- Search and grid appear first.
- The selected-icon detail panel stacks below the grid.
- Controls remain reachable without horizontal scrolling.

### Form integration

- Replace the narrow inline create control and rename-only dialog with one reusable Service form dialog for both create and edit operations.
- The Service form contains the name and optional icon fields; destructive deletion remains a separate flow.
- The current selection appears beside **Choose icon** and **Remove icon** actions.
- Opening the picker uses the current Service name as the initial query.
- Choosing a result updates only temporary form state.
- The Icon Reference is persisted only when the Service form is saved.
- Removing the icon is explicit and saves `null`.

### Search behavior

- Start searching after at least two characters.
- Debounce input by 300 milliseconds.
- Cancel obsolete requests with `AbortController`.
- Request 64 results per page and use Iconify's `start` pagination for more results.
- Cache repeated searches in memory for the current browser session.
- Do not translate Spanish terms; send the entered text directly.

### Accessibility

- The dialog has an accessible title and description.
- Results use keyboard-navigable selection semantics.
- Each result identifies the icon and collection in its accessible name.
- Selection is not communicated by color alone.
- Loading, error, empty, and result-count changes use restrained announcements.
- The detail panel's license link is keyboard accessible.

### Internationalization

All TrackPal-owned labels, messages, empty states, errors, and actions use the backend i18n catalog. Provider collection names, author names, and license titles remain upstream metadata and are not translated.

## Data Flow

1. The Tenant Admin opens the picker from a Service form.
2. The picker waits for a valid debounced query.
3. The Iconify adapter calls `https://api.iconify.design/search`.
4. The adapter normalizes Icon References and collection metadata into the internal model.
5. The picker renders results through `@iconify/react` and shows details for the active result.
6. Confirming returns the Icon Reference to temporary form state.
7. Saving the Service sends the optional Icon Reference to TrackPal.
8. The backend validates and persists the reference without remote I/O.
9. Existing Catalog invalidation reloads the Service and propagates the icon to dependent views.

## Failure Handling

### Search API unavailable

- Show a localized error and retry action inside the picker.
- Preserve the current form and icon selection.
- Allow the dialog to close.
- Do not block saving the Service with its existing icon or no icon.

### Individual icon load failure

- Only the affected result or `ServiceIcon` instance falls back.
- The rest of the result grid remains usable.

### Saved icon removed upstream

- Render the generic `Package` fallback.
- Retain the saved Icon Reference so the Tenant Admin can inspect or replace it.
- Do not mutate business data during rendering.

### Missing license metadata

- The icon may be previewed.
- Confirmation remains disabled until collection metadata is available because the approved experience requires visible license information before selection.

### Invalid Icon Reference

- Backend validation rejects malformed input.
- The frontend associates the validation message with the Service icon field.

## Security and Privacy

- Do not render raw SVG strings with `dangerouslySetInnerHTML`.
- Use the Iconify React renderer and provider-qualified identifiers.
- Validate all persisted references independently of the frontend.
- Treat upstream author and license text as display data, not trusted HTML.
- Document that browsers displaying icons contact Iconify and are subject to Iconify's availability and privacy practices.

## Testing Strategy

Automated tests must not depend on live Iconify access.

### Backend tests

- Migration preserves existing Services with `icon = null`.
- Create, update, clear, and retrieve valid Icon References.
- Reject malformed and overlong references.
- Preserve cross-Tenant isolation.
- Propagate icons through Public API Catalog and Client dashboard contracts.
- Include Icon References in Tenant Data Export.
- Verify Service mutations perform no Iconify network calls.

### Frontend module tests

Test through the `IconPicker` and `ServiceIcon` interfaces using a fake Icon Catalog adapter.

- Minimum query length and debounce.
- Obsolete request cancellation.
- Search success, pagination, empty state, error, and retry.
- Selection, replacement, and removal.
- License metadata and disabled confirmation when metadata is missing.
- Keyboard navigation and accessible names.
- Original palette rendering behavior.
- Generic fallback for null, malformed, missing, and failed icons.

### Feature integration tests

- Create and edit a production Service with an icon.
- Preserve current icon when Iconify search fails.
- Explicitly clear an icon.
- Display icons in Catalog, subscription selectors and summaries, and Client dashboard.
- Persist, migrate, reset, and render Demo Service icons without production Catalog requests.
- Expose Icon References in public catalog payloads.

### Manual verification

- Desktop and mobile layouts.
- Light and dark themes.
- Monochrome and multicolor collections.
- Search, pagination, license link, choose, replace, and remove flows.
- Simulated offline and 5xx states.
- Existing Service with no icon.
- Production Tenant, Master Support Context, and Pro Demo Account.

## Documentation Impact

Implementation must update behavior documentation for:

- Frontend architecture and reusable components.
- Database schema and Catalog API contracts.
- Public API Catalog response examples and developer handoff snippets.
- Tenant Data Export fields.
- Demo Workspace schema and baseline behavior.
- Domain context glossary entries for Service Icon and Icon Reference.

## Acceptance Criteria

1. Each Tenant can assign, replace, or remove an optional icon from the complete searchable Iconify catalog.
2. TrackPal persists only an Icon Reference and never stores SVG markup or icon files.
3. Collection, author, license, and license link are visible before choosing an icon.
4. Original icon palettes are preserved when supplied by the collection.
5. Existing and unavailable icons use a generic fallback.
6. Iconify failure never blocks Service CRUD or TrackPal catalog responses.
7. The icon appears consistently across the approved production, Demo, subscription, client, export, and public catalog surfaces.
8. WhatsApp remains text-only.
9. Automated tests use fakes or mocks rather than live Iconify requests.

## Documentation Sources

- Iconify documentation library: `/websites/iconify_design`
- Icon search: `https://iconify.design/docs/api/search.html`
- Collections metadata: `https://iconify.design/docs/api/collections.html`
- SVG endpoint: `https://iconify.design/docs/api/svg.html`
- React icon loading: `https://iconify.design/docs/icon-components/react/load-icon.html`
