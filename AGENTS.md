# AGENTS.md

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

## Project Guidelines

### Documentation
- `docs/SUMMARY.md` is the entry point. Read before assuming architecture.
- Agent should update docs when changing behavior.

### Testing

**Backend (pytest)**: `cd backend && uv run pytest`
- Framework: pytest 9 + pytest-asyncio, SQLite in-memory.
- Fixtures: `backend/tests/conftest.py`
- Mocking: Evolution API disabled via `evolution_client.api_key = ""`
- HTTP client: `httpx.AsyncClient` with ASGITransport

**Frontend (vitest)**: `cd frontend && npm test`
- jsdom environment, `vi.mock("axios", ...)` pattern in store tests
- Test files: `frontend/src/**/__tests__/*.spec.js`

### Code Style

- **Python**: Ruff (`ruff check .`, `ruff format .`) with defaults.
- **JS/Vue**: Composition API `<script setup>`, Pinia stores, Vue Router. Plain ESM (no TypeScript).
- No pre-commit hooks.

### Key Patterns & Gotchas

1. **DATA_ENCRYPTION_KEY** must be set before any app import. Test conftest sets it via `os.environ`.
2. **WhatsApp session model**: admin session key = `session:admin:{phone}`, client context = `wa:client_ctx:{admin_phone}`, unauth codigo = `session:unreg:{key}`. TTL 5 min for all sessions (aligned with Evolution Go auto-close timeout).
3. **close_jid propagation**: n8n uses fallback chain `close_jid → reply_to → remoteJid`. Always set `close_jid` to canonical phone JID (e.g. `584243106642@s.whatsapp.net`) to avoid LID fallback which Evolution Go can't match.
4. **Active-flow cancel**: universal cancel handler catches `0`/`salir`/`cancelar` before step-specific handlers. Verify route is reachable when adding new steps.
5. **Redis HA**: Primary + backup URLs must be reachable. Circuit breaker opens after 3 failures.
6. **Alembic autogenerate** needs running DB with models imported in `env.py`.
7. **Seed script** idempotent — safe to run on every deploy.
