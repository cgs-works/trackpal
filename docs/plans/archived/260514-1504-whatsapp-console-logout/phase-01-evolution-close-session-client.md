# Phase 1 — Evolution API close-session client

**Complexity:** M

## Objective

Add a backend client method that can mark a WhatsApp chat/session as `closed` in Evolution API for a specific `(instance, remoteJid)` pair.

This phase is safe to ship on its own because it does not change console behavior yet; it only adds a capability + tests.

## Tasks (2–10 min each)

1. **Locate/confirm Evolution API close-session endpoint contract**
   - Check any internal notes, Evolution API docs, or previously validated requests.
   - Output: confirmed HTTP method + path + JSON payload fields (must include `remoteJid` and `status="closed"`).
   - If no repo docs exist, document the chosen contract in-code as a docstring and in the unit test name.

2. **Add a method to `EvolutionClient`**
   - Edit: `backend/app/services/evolution_client.py`
   - Add e.g.:
     - `async def close_chat_session(self, *, instance: str, remote_jid: str) -> None`
   - Behaviors:
     - No-op (log warning) when `EVOLUTION_API_URL` or `EVOLUTION_API_KEY` is missing (match existing client style).
     - Uses `httpx.AsyncClient` with sane timeout (match existing `30.0`).
     - Raises on non-2xx (via `raise_for_status`) so callers can decide how to handle.

3. **Add unit tests for the new method**
   - New file: `backend/tests/test_evolution_client.py`
   - Patch/mocks:
     - Patch `httpx.AsyncClient` to capture the requested URL + payload.
   - Cover:
     - Correct path is called for a known instance.
     - Payload includes `remoteJid` and `status: "closed"`.
     - When api key/url missing, method returns without calling httpx.

## Verification

- `cd backend && uv run pytest tests/test_evolution_client.py -v`

## Exit Criteria

- `EvolutionClient` exposes a tested `close_chat_session()` (or equivalent) method.
- The method’s endpoint/payload are documented and captured in a unit test.
- No WhatsApp console behavior changes are introduced yet.
