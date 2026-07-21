---
status: accepted
---

# Use Markdown topics as the canonical user-help capability registry

TrackPal will keep each user-help topic in a Markdown file whose frontmatter identifies its capability, audience, plans, channel, contextual UI target, and optional orientation-tour step. The build will validate these topics and produce a compiled help artifact that the backend serves only through an authenticated, role-aware, plan-aware, and locale-aware API; the public Vite bundle will not contain the private manual content. The in-app manuals and Tenant Admin orientation tour will consume this same source so maintainers edit user-help content in one place. CI contract checks will block changes when capability metadata, Spanish/English topic parity, role or plan visibility, routes, actions, or tour targets no longer agree with the implemented product.

## Considered Options

Deriving prose from application code cannot explain workflows, limits, or recovery states adequately. Keeping the manual, tour, or capability registry in separate TypeScript, YAML, screenshots, or manually synchronized documents would create additional sources of truth and increase drift risk.

## Consequences

The Markdown frontmatter schema and stable capability and UI-target identifiers become product contracts. Application changes that affect user-visible capabilities must update the corresponding topics and pass the contract checks before merging.
