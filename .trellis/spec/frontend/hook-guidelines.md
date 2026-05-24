# Hook Guidelines

> Custom hook/composable guidance for current frontend.

## Overview

Project currently uses stores + view logic; no dedicated `composables/` folder yet.
Equivalent shared stateful logic lives in Pinia stores.

## Current Pattern

- Reusable state/actions go to `stores/*` first.
- If reusable view-only logic grows, create `src/composables/useXxx.js`.
- Keep API transport in `services/api.js`, not in composable/store internals unless specific domain module needed.

## Data Fetching

- Axios via `src/services/api.js`.
- Interceptors handle auth token injection and global 401 flow.
- Login uses direct axios call pattern documented in conventions to avoid recursion.

## Naming Conventions

- Future composables: `useSomething.js`.
- Return plain refs/computed/functions; avoid hidden side effects.

## Common Mistakes

- Mixing router guard logic into arbitrary view methods.
- Duplicating same async fetch/error mapping across views instead of extracting shared helper/store action.

## Examples

- Shared state pattern today: `frontend/src/stores/auth.js`, `frontend/src/stores/i18n.js`.
- HTTP handling pattern: `frontend/src/services/api.js`.