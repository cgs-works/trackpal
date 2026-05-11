# Phase 1: Project scaffolding

**Complexity:** M
**Dependencies:** None

## Objective
Establish the initial monorepo structure with a Python backend and Vue frontend.

## Preconditions
- Git repo initialized.

## Tasks
1. Context: Create the root directory structure (`backend/` and `frontend/`).
2. Implement backend:
   - Run `uv init` in `backend/`.
   - Add dependencies: `fastapi`, `uvicorn`, `sqlalchemy`, `asyncpg`, `alembic`, `pydantic`, `pydantic-settings`, `python-jose`, `passlib`, `bcrypt`.
   - Add dev dependencies: `pytest`, `httpx`, `aiosqlite`, `pytest-asyncio`.
   - Create basic FastAPI structure (`main.py`, `core/`, `api/`).
3. Implement frontend:
   - Run Vite to create the Vue 3 + TypeScript app in `frontend/`.
   - Add `vue-router`, `pinia`, `axios`.
4. Implement configuration:
   - Create `.env.example` with Supabase connection string and JWT config.

## Verification
- Commands:
  - `cd backend && uv run uvicorn app.main:app --reload &`
  - `cd frontend && npm run dev`
- Expected results:
  - FastAPI responds at `http://localhost:8000/docs`
  - Vue dev server responds at `http://localhost:5173`

## Exit Criteria
- `backend/` has UV `pyproject.toml` and basic app structure.
- `frontend/` has Vue 3 + Vite structure.
