# Frontend Redesign Design

Date: 2026-06-10
Status: Draft for review
Scope: Frontend redesign from zero for Trackpal using Tailwind CSS v4 and shadcn-based UI primitives

## 1. Goal

Redesign the Trackpal frontend from zero around a compact, operational product UI.

The redesign should:
- replace the current mixed raw-CSS UI direction with a cohesive system
- adopt shadcn-style primitives across the application UI
- preserve business flows while rethinking navigation and screen structure
- support real dual-theme operation from the system layer
- create a reusable base that works for master, tenant, and client roles

This is a product UI redesign, not a marketing site refresh.

## 2. Product direction

The target feel is:
- compact
- precise
- fast
- high-clarity
- identity-aware, but not decorative

Reference character:
- closest to Raycast-like product polish
- grounded by the restraint of serious operational software

Rejected directions:
- hero-style dashboards
- generic dark SaaS gradients
- floating glass panels
- ornamental metric cards as the default layout
- landing-page copy inside authenticated views

## 3. Primary design slice

The first design slice is:
- Login
- App shell

This slice will define the visual and structural rules for the rest of the product.

## 4. Chosen design approach

Selected approach: **System-first**

We will redesign from the system outward:
1. define tokens, theming, shell rules, and component rules
2. build the new login and app shell on top of that base
3. migrate role-specific screens into the new shell and component system

Why this approach:
- it makes shadcn a real foundation instead of a cosmetic add-on
- it gives consistent behavior across all roles
- it reduces visual drift between views
- it supports a proper dual-theme system

## 5. Architecture of the new UI

### 5.1 Foundation

The new frontend UI will be built on:
- Vue 3
- Tailwind CSS v4
- a Vue-compatible shadcn implementation for primitives and patterns

shadcn will supply the base primitives for interaction patterns, but Trackpal will define its own:
- tokens
- component variants
- spacing rules
- navigation patterns
- page composition rules

The result should feel like one product system, not a collection of stock shadcn demos.

### 5.2 Shell

The primary shell will be a compact command-workspace layout:
- fixed left sidebar in desktop contexts
- thin topbar for page context and global actions
- central content area optimized for dense operational work

The shell should avoid oversized headers and decorative framing. Pages should start close to the work.

### 5.3 Navigation

Navigation will be rethought from the current structure, but core routes and business capabilities remain intact.

Primary grouping should follow user tasks, not old page boundaries:
- Overview
- Clients
- Catalog
- Subscriptions
- Settings

This grouping is the desired target for tenant-facing navigation and should also inform master/client adaptations where applicable.

## 6. Visual language

### 6.1 Tone

The interface should feel:
- controlled
- modern
- dense without being cramped
- calm in color
- explicit in hierarchy

### 6.2 Shape and surfaces

- border radii should stay restrained
- surfaces should be clean and stable
- panels should look anchored, not floating
- cards should be used only when they improve structure
- nested card stacks should be avoided

### 6.3 Color strategy

The redesign must support **dual theme from the start**.

#### Light theme
- clean and productive
- not beige, not marketing-like
- enough contrast for long operational sessions

#### Dark theme
- serious and stable
- no neon accents
- no blue-black gradient clichés

Color should be token-driven and implemented once at the system level, then inherited by components and screens.

### 6.4 Typography

- hierarchy should come from size, weight, spacing, and placement
- avoid theatrical display headings
- prefer short, direct page titles
- labels and table text must stay highly readable

## 7. Login design

The login should carry more identity than the rest of the product, but still belong to the same system.

Target composition:
- two-zone layout
- one zone for controlled brand/context presence
- one zone for the authentication form

Rules:
- no landing-page storytelling
- no decorative filler blocks
- no oversized welcome section
- fast path to authentication

The login should feel like the front door to a serious product, not a separate microsite.

## 8. App shell design

### 8.1 Desktop

- sidebar is the main navigation anchor
- topbar is thin and functional
- content headers are short
- primary actions sit close to page content
- spacing is tighter than the current UI, but still readable

### 8.2 Tablet and mobile

- sidebar becomes a sheet/drawer
- topbar gains importance as the control surface
- tables and forms adapt without collapsing into meaningless long stacks
- the redesign must keep structural clarity on smaller screens

### 8.3 Cross-role consistency

Master, tenant, and client experiences should share the same shell language.

What changes by role:
- available navigation items
- visible tools
- permissions
- domain content

What should not change by role:
- shell DNA
- component behavior
- visual hierarchy principles
- theming model

## 9. Component system scope

The redesign should standardize these core UI pieces first:
- buttons
- text inputs
- textareas
- selects
- checkboxes / switches / radios as needed
- dialogs
- drawers / sheets
- dropdown menus
- tabs
- table wrappers
- badges for state
- page headers
- sidebar navigation items
- empty states
- loading states
- error states

Each component should have Trackpal-specific styling and consistent states for:
- default
- hover
- focus
- active
- disabled
- error, when applicable

## 10. Screen composition rules

Pages should be structured for work, not presentation.

Preferred patterns:
- short page header
- local actions near the relevant block
- filters near the table or collection they affect
- dialogs only for destructive or high-risk confirmations
- inline validation and inline feedback wherever possible

Avoid:
- large decorative summary banners
- repeated explanation copy under every heading
- excessive empty spacing
- visual wrappers that exist only to feel premium

## 11. States and feedback

Every redesigned screen must explicitly handle:
- loading
- empty
- error
- success
- disabled

Rules:
- no ambiguous blank states
- no isolated spinner without context
- inline errors near the failed action
- toast messages for short confirmations only
- richer error explanation should stay in context, not be hidden in a toast

The redesign must respect the existing i18n model from the start.

## 12. Accessibility requirements

The redesign should include these as baseline expectations:
- visible focus states in both themes
- keyboard-friendly navigation for sidebar, menus, dialogs, and forms
- contrast that remains dependable in light and dark modes
- status communication that does not rely on color alone

## 13. Testing expectations for the redesign

The redesign should improve frontend testability instead of reducing it.

Initial test priorities:
- login render and interaction flow
- app shell render and navigation structure
- theme switching behavior
- core component states for critical primitives
- baseline form states and feedback behavior

Testing should verify the structural behavior of the new foundation before large-scale screen migration.

## 14. Rollout intent

The redesign should be implemented in layers:
1. foundation and theme system
2. login and shell
3. shared components
4. screen-by-screen migration for role-specific views

This sequencing keeps the redesign controlled and reduces one-off styling decisions.

## 15. Out of scope for this design

This design does not include:
- backend changes
- new product features unrelated to the redesign
- route/business-flow rewrites that change core product capabilities
- speculative design-system expansion beyond the components needed for the first migration wave

## 16. Success criteria

The redesign is successful when:
- the frontend has one coherent visual system
- shadcn-based primitives are used consistently across the UI
- login and app shell define a strong reusable base
- light and dark themes both feel native
- master, tenant, and client views feel like one product family
- the UI becomes cleaner, faster to scan, and easier to extend
