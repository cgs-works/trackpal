---
name: Trackpal
description: Multi-tenant platform for managing WhatsApp-based service delivery.
colors:
  primary: "#2563eb"
  error: "#dc2626"
  neutral-bg: "#f9fafb"
  neutral-surface: "#ffffff"
  neutral-text: "#1f2937"
  neutral-border: "#e5e7eb"
  neutral-border-hover: "#d1d5db"
typography:
  body:
    fontFamily: "system-ui, 'Segoe UI', Roboto, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "normal"
rounded:
  sm: "6px"
  md: "8px"
  lg: "12px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "24px"
  xl: "32px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.neutral-surface}"
    rounded: "{rounded.md}"
    padding: "10px 12px"
---

# Design System: Trackpal

## 1. Overview

**Creative North Star: "The Expert's Console"**

Trackpal is a professional, clean, and functional SaaS platform. It feels snappy, reliable, and out of the way, favoring information density and structural constraints over decoration. The aesthetic philosophy is rooted in utilitarian clarity—every visual element serves a workflow purpose. It explicitly rejects dense corporate software bloat, empty minimalism that wastes space, and superficial visual trends like glassmorphism or excessive shadows.

**Key Characteristics:**
- High-craft but invisible (tools should get out of the way)
- Structured by spacing, not lines (where possible)
- Functional visual hierarchy

## 2. Colors

The palette is restrained, using tinted neutrals for structure and a single primary accent for action.

### Primary
- **Clear Blue** (#2563eb): Used exclusively for primary actions and active states.

### Secondary
- **Alert Red** (#dc2626): Used for errors and destructive actions.

### Neutral
- **Background Slate** (#f9fafb): The default app background.
- **Surface White** (#ffffff): Elevated container background.
- **Ink Gray** (#1f2937): Primary text color.
- **Subtle Border** (#e5e7eb): Structural borders and dividers.
- **Input Border** (#d1d5db): Form control boundaries.

**The One Voice Rule.** The primary accent is used strictly for primary actions. Never use it for decoration or passive states.

## 3. Typography

**Display Font:** system-ui, 'Segoe UI', Roboto, sans-serif
**Body Font:** system-ui, 'Segoe UI', Roboto, sans-serif

**Character:** Utilitarian, fast-loading, native feel.

### Hierarchy
- **Body** (400, 1rem, 1.5): Standard UI text, labels, and paragraph content.

**The System Native Rule.** Rely on the OS default system font to ensure maximum performance and familiarity.

## 4. Elevation

The system is primarily flat. Depth is conveyed through subtle borders and background contrast rather than heavy shadows.

**The Flat-By-Default Rule.** Surfaces are flat at rest. Depth is reserved for modals, popovers, and focus states.

## 5. Components

### Buttons
- **Shape:** Soft edges (8px radius)
- **Primary:** Clear Blue background, Surface White text, padding: 10px 12px.
- **Hover / Focus:** Slight opacity shift or deeper blue.

### Cards / Containers
- **Corner Style:** Rounded (12px radius)
- **Background:** Surface White
- **Shadow Strategy:** Flat with a Subtle Border (1px solid).
- **Internal Padding:** 32px

### Inputs / Fields
- **Style:** 1px Input Border, Surface White background, 8px radius.
- **Focus:** Primary color border shift and focus ring.

## 6. Do's and Don'ts

### Do:
- **Do** align form elements strictly to the grid.
- **Do** use the single primary color only for the main call to action on a screen.

### Don't:
- **Don't** use classic dense corporate software patterns (bloated, slow, overwhelming).
- **Don't** use empty excessive minimalism (too much white space at the cost of information density).
- **Don't** use excessive visual decoration (no glassmorphism, unnecessary shadows, or decorative gradients).
