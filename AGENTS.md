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
- **JS/React**: React 19 + TypeScript (strict mode), Zustand stores, TanStack Router, Tailwind CSS v4, shadcn/ui.
- No pre-commit hooks.

## Agent skills

### Issue tracker

Issues viven en GitHub Issues (`gh` CLI). PRs externos NO son superficie de requests. See `docs/agents/issue-tracker.md`.

### Triage labels

Cinco roles canónicos mapeados a labels de GitHub. See `docs/agents/triage-labels.md`.

### Domain docs

Multi-context: backend, frontend, n8n como contextos separados. `CONTEXT-MAP.md` en raíz. See `docs/agents/domain.md`.

## Key Patterns & Gotchas

1. **DATA_ENCRYPTION_KEY** must be set before any app import. Test conftest sets it via `os.environ`.
2. **WhatsApp session model**: admin session key = `session:admin:{phone}`, client context = `wa:client_ctx:{admin_phone}`, unauth codigo = `session:unreg:{key}`. TTL 5 min for all sessions (aligned with Evolution Go auto-close timeout).
3. **close_jid propagation**: n8n uses fallback chain `close_jid → reply_to → remoteJid`. Always set `close_jid` to canonical phone JID (e.g. `584243106642@s.whatsapp.net`) to avoid LID fallback which Evolution Go can't match.
4. **Active-flow cancel**: universal cancel handler catches `0`/`salir`/`cancelar` before step-specific handlers. Verify route is reachable when adding new steps.
5. **Redis HA**: Primary + backup URLs must be reachable. Circuit breaker opens after 3 failures.
6. **Alembic autogenerate** needs running DB with models imported in `env.py`.
7. **Seed script** idempotent — safe to run on every deploy.
