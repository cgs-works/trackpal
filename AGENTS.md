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
