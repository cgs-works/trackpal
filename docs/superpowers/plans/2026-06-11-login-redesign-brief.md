# Design Brief: Login Page — Dark Split Layout

## 1. Feature Summary

Redesign the TrackPal login page from a centered card to a **split-layout dark-first gateway**. Left panel: branded atmospheric visual with the TrackPal identity. Right panel: the authentication form. The login should feel like entering a premium operations tool, not a generic admin panel.

## 2. Primary User Action

Sign in with username and password. The form must be the clear focal point on the right side — zero ambiguity about what to do.

## 3. Design Direction

**Color strategy:** Restrained. Dark surfaces carry the atmosphere; the form side stays clean and readable. One restrained accent (the existing primary or a subtle cool tone) for focus rings and the primary action button.

**Scene sentence:** An operations admin opens TrackPal after hours — dark room, screen glow, the tool should feel like a calm extension of their focused state, not a bright interruption.

**Anchor references:**
- **Raycast / Arc** — dark-first, slight glow on focus, glass-adjacent but restrained, modern without flash
- **Linear login** — split layout with atmospheric left panel, clean form on right

**Dark mode:** Default dark. User can toggle to light via a small switch in the top-right corner of the form side. The `.dark` class on `<html>` drives the theme; tokens already exist in `index.css`.

## 4. Scope

- **Fidelity:** Production-ready
- **Breadth:** One screen (login)
- **Interactivity:** Fully functional — form submission, locale toggle, dark/light switch, error states, loading state
- **Time intent:** Ship it

## 5. Layout Strategy

**Split layout, two halves:**

- **Left panel (branded):** Dark surface with an abstract geometric composition — subtle grid lines, a faint accent glow, and the TrackPal wordmark. NOT a literal illustration, NOT a stock photo, NOT a gradient mesh. Think: a quiet, structured pattern that evokes "ledger" or "operations grid" — like looking at a dark spreadsheet at night. The composition should feel alive but calm. Subtle CSS-only animation (slow-moving grid pulse or faint radial glow) is welcome if it stays below the threshold of attention.

- **Right panel (form):** Clean dark surface (or light in light mode). The form lives here with generous padding, clear hierarchy, and Raycast-inspired focus glow on inputs. Locale selector and dark/light toggle sit at the top-right corner, small and unobtrusive.

**Visual hierarchy on the form side:**
1. TrackPal wordmark or logo (small, top-left of form panel)
2. "Sign In" heading
3. Form fields (username, password) — the main event
4. Sign In button — full width, primary action
5. Locale selector + theme toggle — subtle, secondary

## 6. Key States

| State | What the user sees |
|-------|-------------------|
| Default | Empty form, ready to type |
| Focused | Input border glows with restrained accent (Raycast-style) |
| Loading | Button shows spinner + "Signing in..." text, form disabled |
| Error | Inline error message below the form, destructive color, no alert banner |
| Success | Brief pause, then redirect (no success toast needed) |
| Locale switched | All labels update reactively, layout stays stable |

## 7. Interaction Model

- **Form submit:** Enter key or click "Sign In" button. Button disables + shows loading state.
- **Locale toggle:** Dropdown or pill toggle (en/es) in the top corner. Instant label update.
- **Theme toggle:** Small sun/moon icon button. Toggles `.dark` class. Persists to localStorage.
- **Focus:** Inputs get a subtle glow ring on focus (not the default browser outline). The glow should feel like a restrained version of Raycast's focus treatment.
- **Keyboard:** Full tab order, visible focus indicators, Escape doesn't close anything (there's nothing to close).

## 8. Content Requirements

- **Heading:** "Sign In" (en) / "Iniciar sesión" (es)
- **Labels:** Username/Usuario, Password/Contraseña
- **Button:** "Sign In"/"Ingresar" (default), "Signing in..."/"Ingresando..." (loading)
- **Error copy:** API error detail or "Could not sign in" / "No se pudo iniciar sesión"
- **Locale selector:** "Language:" / "Idioma:" with en/es options
- **Brand mark:** "TrackPal" wordmark on the left panel
- **Empty states:** N/A (login has no empty state)
- **No images required** — the left panel is pure CSS/composition.

## 9. Recommended References

- `colorize.md` — for the dark surface palette and accent glow treatment
- `animate.md` — for the subtle left-panel animation and focus transitions
- `layout.md` — for the split-layout responsive behavior
- `clarify.md` — for form labels, error messages, button copy

## 10. Open Questions

None — direction is locked. Split layout, dark-first with toggle, Raycast/Arc glow aesthetic, CSS-only left panel composition.
