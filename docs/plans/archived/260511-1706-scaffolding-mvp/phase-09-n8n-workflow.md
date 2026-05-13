# Phase 9: n8n WhatsApp Bot Workflow

**Complexity:** M
**Dependencies:** Phase 4 (Tenants CRUD), Phase 3 (Identify endpoint + API Key)

## Objective

Implement the real n8n workflow for the WhatsApp bot: webhook from Evolution API, identify user via Trackpal API with API Key, interactive menu, session management via data table, and CRUD tenants via HTTP requests to the backend.

## Preconditions

- Trackpal API deployed and accessible from n8n instance.
- Evolution API instance available with webhook URL configured.
- N8N_API_KEY configured in Trackpal backend env.
- Data table in n8n for session management.

## Tasks

1. **Create data table for sessions** via n8n_manage_datatable:
   - Table: `wa_sessions`
   - Columns: phone (string), step (string), temp_data (json), created_at (datetime), updated_at (datetime)

2. **Create workflow** via n8n_create_workflow or n8n_deploy_template:
   - Name: "Trackpal WhatsApp Bot"

3. **Webhook node**: Configure to receive POST from Evolution API.
   - Parse incoming payload (phone number, message text, instance name)

4. **Code node (Parse input)**: Extract phone, message, instance from Evolution API payload.

5. **HTTP Request node (Identify user)**:
   - Method: GET
   - URL: `{{$env.TRACKPAL_API_URL}}/api/v1/integrations/n8n/identify?phone={{phone}}`
   - Headers: `X-API-Key: {{$env.N8N_API_KEY}}`
   - Handle 404 response (user not found → send "Access denied" via Evolution API)

6. **Switch node (Route by role)**:
   - If role = 'master' → continue
   - Else → send "Este servicio solo está disponible para el Master" via Evolution API

7. **Code node (Get/Create session)**:
   - Query data table for active session by phone
   - Return: session exists + step + temp_data, or null

8. **IF node (Has session?)**:
   - Yes → route to step handler
   - No → show main menu

9. **Main menu**: Code node that formats and sends menu via Evolution API:

   ```
   📋 Master Trackpal
   1. Crear tenant
   2. Listar tenants
   3. Ver tenant
   4. Editar tenant
   5. Desactivar tenant
   6. Reactivar tenant
   7. Eliminar tenant
   8. Ayuda
   ─────────────────
   Elige una opción:
   ```

10. **Switch node (Route by menu choice)**:
    - Routes 1-8 to corresponding handlers
    - Default → send "Opción inválida" + menu

11. **Session step handlers** (each is a sub-flow):
    - **Create flow** (steps: awaiting_full_name → awaiting_email → awaiting_username → awaiting_password_choice → awaiting_password_manual → done)
      - Password choice: "Generar contraseña automáticamente (1) o ingresarla manualmente (2)?"
      - If auto: create tenant via API with auto_generate_password=true
      - If manual: ask for password, then create tenant via API
      - On success: show tenant details + password (if auto-generated, show once)
      - Clear session
    - **List flow**: GET /api/v1/tenants → format → send via Evolution API
    - **View flow**: ask tenant ID → GET /api/v1/tenants/{id} → show details
    - **Edit flow**: ask tenant ID → show current data → ask fields to update → PUT /api/v1/tenants/{id}
    - **Deactivate flow**: ask tenant ID → PATCH /api/v1/tenants/{id}/deactivate → confirm
    - **Reactivate flow**: ask tenant ID → PATCH /api/v1/tenants/{id}/activate → confirm
    - **Delete flow**: ask tenant ID → confirm → DELETE /api/v1/tenants/{id} (only if inactive)
    - **Help**: show instructions

12. **Error handling**:
    - Add Error Trigger node for workflow-level error handling
    - Send friendly error message via Evolution API on failures
    - Log errors to n8n data table for debugging

## Verification

- Tools: validate_workflow (after creation + after each edit), n8n_autofix_workflow if issues found
- Manual: Send WhatsApp message to Evolution API instance → verify menu appears
- Manual: Test each menu option end-to-end
- Manual: Verify session persists across messages (multi-step flows)
- Manual: Verify API Key auth works (invalid key → 401, workflow handles gracefully)

## Exit Criteria

- [ ] Workflow created and validated
- [ ] Webhook receives messages from Evolution API
- [ ] Identify endpoint authenticates correctly with API Key
- [ ] Main menu renders and accepts numeric choices
- [ ] Create tenant flow (both auto and manual password) works end-to-end
- [ ] All CRUD operations functional via WhatsApp
- [ ] Session management works (multi-step flows don't reset)
- [ ] Error handling sends friendly messages on failures
