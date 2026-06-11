---
name: Trackpal
description: Calm operations UI for WhatsApp-based tenant, subscription, and mailbox-code workflows.
colors:
  background: "oklch(1 0 0)"
  foreground: "oklch(0.145 0 0)"
  card: "oklch(1 0 0)"
  primary: "oklch(0.205 0 0)"
  primary-foreground: "oklch(0.985 0 0)"
  secondary: "oklch(0.97 0 0)"
  muted: "oklch(0.97 0 0)"
  muted-foreground: "oklch(0.556 0 0)"
  border: "oklch(0.922 0 0)"
  ring: "oklch(0.708 0 0)"
  destructive: "oklch(0.577 0.245 27.325)"
typography:
  display:
    fontFamily: "Geist Variable, sans-serif"
    fontSize: "3rem"
    fontWeight: 800
    lineHeight: 1
    letterSpacing: "-0.025em"
  headline:
    fontFamily: "Geist Variable, sans-serif"
    fontSize: "1.5rem"
    fontWeight: 700
    lineHeight: 1.2
  title:
    fontFamily: "Geist Variable, sans-serif"
    fontSize: "1rem"
    fontWeight: 500
    lineHeight: 1.375
  body:
    fontFamily: "Geist Variable, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "Geist Variable, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 500
    lineHeight: 1
rounded:
  sm: "calc(var(--radius) * 0.6)"
  md: "calc(var(--radius) * 0.8)"
  lg: "var(--radius)"
  xl: "calc(var(--radius) * 1.4)"
spacing:
  xs: "0.25rem"
  sm: "0.5rem"
  md: "1rem"
  lg: "1.5rem"
  xl: "2rem"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.primary-foreground}"
    rounded: "{rounded.lg}"
    height: "2rem"
    padding: "0 0.625rem"
  button-outline:
    backgroundColor: "{colors.background}"
    textColor: "{colors.foreground}"
    rounded: "{rounded.lg}"
    height: "2rem"
    padding: "0 0.625rem"
  card:
    backgroundColor: "{colors.card}"
    textColor: "{colors.foreground}"
    rounded: "{rounded.xl}"
    padding: "1rem"
  input:
    backgroundColor: "transparent"
    textColor: "{colors.foreground}"
    rounded: "{rounded.lg}"
    height: "2rem"
    padding: "0.25rem 0.625rem"
---

# Design System: Trackpal

## 1. Overview

**Creative North Star: "The Operations Ledger"**

Trackpal should feel like a calm operational ledger: clear enough for repeated daily work, stable enough for credential and subscription tasks, and quiet enough that WhatsApp, tenant, mailbox, and role boundaries stay legible. The current React frontend establishes a shadcn/base-nova foundation: Geist Variable, neutral OKLCH tokens, compact controls, rounded-lg buttons and inputs, rounded-xl cards, borders, muted fills, and visible focus rings.

This system is product-first. Familiar controls are an asset. Future screens should look trustworthy to operators who manage tenants, clients, subscriptions, mailbox connections, and access-code workflows in Spanish-first contexts. It explicitly rejects generic SaaS-card aesthetics: gradient hero text, repeated metric-card scaffolds, decorative dashboards, startup-template polish, and motion that does not improve state comprehension.

**Key Characteristics:**
- Restrained neutral surfaces with near-black primary actions.
- Comfortable and calm density: not sparse marketing, not cramped infrastructure UI.
- Role-aware layouts where master, tenant, and client capabilities are unmistakable.
- Bilingual-ready labels, forms, tables, and validation messages.
- State vocabulary that uses text, shape, iconography, and tone rather than color alone.

## 2. Colors

The palette is **Ink and Porcelain**: porcelain-white work surfaces, ink-black action hierarchy, soft neutral dividers, and destructive red reserved for real risk.

### Primary
- **Ledger Ink** (`colors.primary`): Primary actions, selected navigation, and the strongest text/action moments. Use it sparingly so the interface reads as controlled, not decorated.

### Neutral
- **Porcelain Surface** (`colors.background`, `colors.card`): Default page and panel surface. This is the main working material.
- **Operator Ink** (`colors.foreground`): Body text, titles, labels, and table data. Do not lighten core reading text for elegance.
- **Soft Divider** (`colors.border`, `colors.input`): Borders, inputs, card outlines, and separators. It should structure without creating grid noise.
- **Muted Panel** (`colors.muted`, `colors.secondary`, `colors.accent`): Secondary surface fills, card footers, inactive toolbar states, and quiet grouped regions.
- **Muted Ink** (`colors.muted-foreground`): Secondary descriptions and helper text. Use only where lower emphasis is appropriate; never for required labels or critical status.
- **Focus Ring Neutral** (`colors.ring`): Keyboard focus and active field treatment through ring opacity, not decorative glow.

### Tertiary
- **Risk Red** (`colors.destructive`): Destructive actions, validation errors, and irreversible warnings. Pair with explicit text and accessible icons; never rely on red alone.

### Named Rules
**The ≤10% Ink Rule.** Primary ink is for action and selection. If a screen is mostly primary color, the hierarchy has failed.

**The No Decorative Accent Rule.** Do not introduce indigo, gradients, or arbitrary success colors as ornament. Every non-neutral color must represent state, risk, selection, or a documented data role.

## 3. Typography

**Display Font:** Geist Variable (with sans-serif fallback)  
**Body Font:** Geist Variable (with sans-serif fallback)  
**Label/Mono Font:** Geist Variable unless a true code/identifier context requires mono later.

**Character:** One disciplined sans-serif carries the product. It should feel precise, current, and unshowy. The hierarchy comes from weight, size, spacing, and placement—not font novelty.

### Hierarchy
- **Display** (800, `3rem`, line-height `1`): Rare product-level headings and transitional scaffold pages. Do not use fluid hero typography for app views.
- **Headline** (700, `1.5rem`, line-height `1.2`): Page titles, modal titles, and major dashboard sections.
- **Title** (500, `1rem`, line-height `1.375`): Card titles, panel headings, table group labels, and compact section heads.
- **Body** (400, `1rem`, line-height `1.5`): Form help, descriptions, empty-state copy, and prose. Keep long explanatory copy within 65–75ch.
- **Label** (500, `0.875rem`, line-height `1`): Form labels, compact nav items, table headers, and button text. Avoid all-caps tracking as a section scaffold.

### Named Rules
**The One-Family Rule.** Product UI uses Geist for everything until a real data-display need proves otherwise. No display fonts in controls, labels, tables, or form fields.

**The No Gradient Text Rule.** Gradient text is prohibited. Emphasis comes from hierarchy, not background-clip decoration.

## 4. Elevation

Trackpal uses **tonal layers**: borders, muted fills, and spacing establish depth first. Shadows are not part of the core vocabulary yet; when introduced, they should appear as interaction feedback or for overlays, not as permanent decoration on every card.

### Named Rules
**The Border-Before-Shadow Rule.** Start with `ring-foreground/10`, `border-border`, muted footers, and spacing. Add shadow only when a surface must float above another surface.

**The State-Only Motion Rule.** Motion is 150–250ms and explains state: hover, focus, loading, expansion, or route feedback. No choreographed page-load sequences.

## 5. Components

### Buttons
- **Shape:** Gently rounded compact controls (`rounded-lg`, height `2rem`).
- **Primary:** Ledger Ink background with Porcelain text; used for the one main action in a local region.
- **Hover / Focus:** Hover darkens through token mixing; focus uses visible ring (`ring-3`, `ring/50`). Active may move by 1px only where the base component already does it.
- **Secondary / Ghost / Tertiary:** Outline, secondary, ghost, destructive, and link variants come from the installed shadcn button component. Do not override their color vocabulary with raw Tailwind colors.

### Cards / Containers
- **Corner Style:** Rounded, contained, and calm (`rounded-xl`).
- **Background:** Porcelain Surface with Operator Ink text.
- **Shadow Strategy:** Flat by default; use a subtle ring (`ring-foreground/10`) and muted footer fills before adding shadows.
- **Border:** Tokenized border/ring only.
- **Internal Padding:** Default card spacing is `1rem`; small cards use `0.75rem`.

### Inputs / Fields
- **Style:** Compact field height (`2rem`), rounded-lg border, transparent surface, readable placeholder color.
- **Focus:** Border shifts to ring color and adds a visible three-pixel focus ring.
- **Error / Disabled:** `aria-invalid` must trigger destructive border/ring; disabled controls lower opacity and stop pointer interaction.

### Navigation
- **Style:** Simple top-level navigation exists in the scaffold. Future authenticated surfaces should use consistent active states, role-aware destinations, and clear separation between master, tenant, and client contexts.
- **Typography:** Small-medium labels with direct wording. Avoid decorative section eyebrows.
- **Mobile Treatment:** Collapse structurally; do not rely on shrinking type scales.

### Status Indicators
- **Style:** Status badges must use semantic tokens or documented status roles. Pair hue with text/icon/state names.
- **Risk:** Destructive actions and credential reveal moments need confirmation, explicit copy, and non-color-only affordances.

## 6. Do's and Don'ts

### Do:
- **Do** preserve the shadcn/base-nova token system in `frontend/src/index.css`; extend tokens there instead of scattering raw colors.
- **Do** keep product screens comfortable and calm: compact enough for repeat operators, spacious enough for Spanish labels and validation text.
- **Do** make role boundaries obvious through navigation, copy, permissions, and page structure.
- **Do** use visible focus rings, keyboard-reachable controls, and non-color-only status cues.
- **Do** use cards only when they clarify containment; tables, panels, sections, and inline flows are often better for operational work.

### Don't:
- **Don't** use generic SaaS-card aesthetics: gradient hero text, repeated metric-card scaffolds, decorative dashboards, startup-template polish, or visual effects that do not improve operator confidence.
- **Don't** use `background-clip: text` gradients. The current scaffold pattern should be removed, not expanded.
- **Don't** add colored side-stripe borders, glassmorphism, decorative blur cards, or arbitrary high z-index values.
- **Don't** use muted gray for required labels, important data, or core body copy.
- **Don't** hardcode raw Tailwind colors for component variants when semantic tokens or installed shadcn variants exist.
