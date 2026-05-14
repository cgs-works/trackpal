# Phase 4 — n8n workflow sanitization (placeholders + no instance filter)

**Complexity:** S

## Objective

Keep n8n as transport-only and make the versioned workflow safe to commit by:

- Removing any **instance-based access filtering**.
- Removing committed **secrets** (backend API key, Evolution API key, prod URLs) and replacing them with placeholders/env references.

## Tasks (2–10 min each)

1. **Remove the instance filter node**
   - Edit: `n8n/Trackpal WhatsApp Bot.json`
   - Remove node `Is Sublify?` and its connections.
   - Connect `Parse input` directly to `Console call`.

2. **Replace backend URL with an env placeholder/expression**
   - In the `Console call` node:
     - Replace `https://trackpal-backend.onrender.com` with `{{$env.TRACKPAL_BACKEND_URL}}` (or the repo’s preferred env name).
     - Keep path `/api/v1/integrations/n8n/console`.

3. **Replace backend API key with an env placeholder/expression**
   - In the `Console call` headers:
     - Replace the literal `X-API-Key` value with `{{$env.TRACKPAL_N8N_API_KEY}}`.

4. **Replace Evolution API URL + key with env placeholders**
   - In `Evolution API Send`:
     - URL base becomes `{{$env.TRACKPAL_EVOLUTION_API_URL}}/message/sendText/{{$json.instance}}`.
     - Header `apikey` becomes `{{$env.TRACKPAL_EVOLUTION_API_KEY}}`.

5. **Ensure placeholders are consistent with docs**
   - Edit: `docs/architecture/n8n-workflow.md`
   - Update the “Configuration” section to:
     - Prefer `$env.*` usage (since it’s export-friendly).
     - Document the required env vars names chosen above.

6. **Add a lightweight “no secrets in export” check step**
   - Document a manual check command in the plan (and optionally in `docs/architecture/n8n-workflow.md`):
     - Search the workflow export for known secret patterns and ensure only placeholders remain.

## Verification

- Validate JSON:
  - `python -m json.tool "n8n/Trackpal WhatsApp Bot.json" > NUL`
- Confirm the instance filter is gone:
  - `rg -n "Is Sublify\?" "n8n/Trackpal WhatsApp Bot.json"` → **no matches**
- Confirm no obvious secrets remain in the export (examples):
  - `rg -n "onrender\.com|X-API-Key\"\s*:\s*\"[A-Za-z0-9]|apikey\"\s*:\s*\"[A-Za-z0-9]" "n8n/Trackpal WhatsApp Bot.json"`
  - Expect matches only for header *names*, not real secret *values*.

## Exit Criteria

- n8n workflow no longer blocks by instance name.
- Workflow JSON contains no real API keys or production URLs.
- Docs accurately describe how to deploy the workflow using env vars.
