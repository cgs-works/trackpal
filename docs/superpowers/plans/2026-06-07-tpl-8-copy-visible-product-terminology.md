# TPL-8 Copy Visible y Terminología de Producto Implementation Plan

> **REQUIRED SUB-SKILL:** Use the executing-plans skill to implement this plan task-by-task.

**Goal:** Eliminar `tenant` del copy visible dentro del alcance TPL-8, aplicar la terminología aprobada por contexto, corregir mojibake en las cadenas tocadas y dejar sincronizados tests y documentación user-facing.

**Architecture:** El cambio es quirúrgico y se limita a values/literales visibles. No se renombran entidades internas, rutas, keys i18n ni artefactos de dominio. La implementación se divide en tres bloques: copy hardcoded del Master Console, catálogos i18n/frontend, y documentación/tests alineados con el nuevo vocabulario.

**Tech Stack:** Python 3.14, FastAPI, catálogos i18n en Python dicts, Vue 3 + Vite, pytest, Vitest, ripgrep.


### Task 1: Lock down the Master Console copy contract in backend tests

**TDD scenario:** Modifying tested code — run existing tests first

**Files:**
- Modify: `backend/tests/test_contingency_reply_policy.py`
- Modify: `backend/tests/test_whatsapp_menu_flow.py`
- Modify: `backend/tests/test_whatsapp_list_select_flow.py`
- Modify: `backend/tests/test_whatsapp_lifecycle_flow.py`
- Modify: `backend/tests/test_whatsapp_endpoint.py`

**Step 1: Update the failing expectations to the new visible terminology**

Replace old assertions like:

```python
assert "Ver Tenants" in reply
assert "Crear Tenant" in reply
assert "Lista de Tenants" in reply
assert "Detalle del Tenant" in reply
```

with approved visible copy, for example:

```python
assert "Ver empresas" in reply
assert "Crear empresa" in reply
assert "Lista de empresas" in reply
assert "Detalle de la empresa" in reply
```

For lifecycle tests, keep semantic fallback assertions when appropriate:

```python
assert "Desactivar empresa" in reply or "desactivar" in reply.lower()
assert "Eliminar empresa" in reply or "eliminar" in reply.lower()
```

**Step 2: Run focused tests to verify they fail before implementation**

Run:

```bash
cd backend && uv run pytest tests/test_contingency_reply_policy.py tests/test_whatsapp_menu_flow.py tests/test_whatsapp_list_select_flow.py tests/test_whatsapp_lifecycle_flow.py tests/test_whatsapp_endpoint.py -q
```

Expected: FAIL because runtime strings still contain `Tenant` / `Tenants`.

**Step 3: Do not fix tests yet beyond the new contract**

Only update assertions for approved copy. Do not loosen them to generic substrings unless the test is intentionally semantic.

**Step 4: Commit the red test update**

```bash
git add backend/tests/test_contingency_reply_policy.py backend/tests/test_whatsapp_menu_flow.py backend/tests/test_whatsapp_list_select_flow.py backend/tests/test_whatsapp_lifecycle_flow.py backend/tests/test_whatsapp_endpoint.py
git commit -m "test: lock visible master console terminology"
```

---

### Task 2: Implement Master Console hardcoded copy changes

**TDD scenario:** Modifying tested code — make the red tests pass with minimal implementation

**Files:**
- Modify: `backend/app/services/whatsapp_console_service/messages.py`
- Modify: `backend/app/services/whatsapp_console_service/formatters.py`
- Modify: `backend/app/services/whatsapp_console_service/create_confirm.py`
- Modify: `backend/app/services/whatsapp_console_service/edit_messages.py`
- Modify: `backend/app/services/whatsapp_console_service/edit_handlers.py`
- Modify: `backend/app/services/whatsapp_console_service/lifecycle_messages.py`
- Modify: `backend/app/services/contingency_reply_policy/policy.py`

**Step 1: Change only visible strings, not identifiers**

Apply the approved terminology:

```python
MAIN_MENU = (
    "🤖 *TrackPal Master Console*\n\n"
    "1️⃣ Ver empresas\n"
    "2️⃣ Crear empresa\n"
    "3️⃣ Desactivar empresa\n"
    "4️⃣ Eliminar empresa\n"
    "5️⃣ Ayuda\n\n"
    "0️⃣ Cerrar sesión\n\n"
    "Responde con el número de la opción deseada."
)
```

And in formatters:

```python
header = (
    "📋 *Lista de empresas*\n"
    f"Activas: {active_count} | Inactivas: {inactive_count}\n\n"
)
```

```python
return (
    f"👤 *Detalle de la empresa*\n\n"
    ...
)
```

**Step 2: Apply the same rule across create/edit/lifecycle/fallback copy**

Examples:

```python
"✏️ *Crear empresa*"
"✏️ *Editar empresa*"
"✅ *Empresa creada exitosamente*"
"✅ *Empresa actualizada exitosamente*"
"⚠️ *Desactivar empresa*"
"⚠️ *Eliminar empresa*"
```

Keep internal names like `tenant_service`, `list_tenants`, `selected_tenant_id`, etc.

**Step 3: Update contingency reset text to match the new visible menu**

```python
"1️⃣ Ver empresas\n"
"2️⃣ Crear empresa\n"
"3️⃣ Desactivar empresa\n"
"4️⃣ Eliminar empresa\n"
```

**Step 4: Re-run the focused backend suite**

Run:

```bash
cd backend && uv run pytest tests/test_contingency_reply_policy.py tests/test_whatsapp_menu_flow.py tests/test_whatsapp_list_select_flow.py tests/test_whatsapp_lifecycle_flow.py tests/test_whatsapp_endpoint.py -q
```

Expected: PASS.

**Step 5: Run a static check for old visible strings in the hardcoded Master Console files**

Run:

```bash
rg -n "Ver Tenants|Crear Tenant|Desactivar Tenant|Eliminar Tenant|Lista de Tenants|Detalle del Tenant|Editar Tenant|Tenant creado exitosamente|tenant actualizado exitosamente" backend/app/services/whatsapp_console_service backend/app/services/contingency_reply_policy/policy.py
```

Expected: no matches.

**Step 6: Commit**

```bash
git add backend/app/services/whatsapp_console_service/messages.py backend/app/services/whatsapp_console_service/formatters.py backend/app/services/whatsapp_console_service/create_confirm.py backend/app/services/whatsapp_console_service/edit_messages.py backend/app/services/whatsapp_console_service/edit_handlers.py backend/app/services/whatsapp_console_service/lifecycle_messages.py backend/app/services/contingency_reply_policy/policy.py
git commit -m "feat: update visible master console terminology"
```

---

### Task 3: Lock down frontend + WhatsApp catalog expectations

**TDD scenario:** Modifying tested code — add/adjust focused assertions before implementation

**Files:**
- Modify: `backend/tests/test_whatsapp_client_context_shortcut.py`
- Modify: `backend/tests/test_client_console_service.py`
- Modify: `backend/tests/test_whatsapp_credential_auth_flow.py` (only if exact visible copy assumptions need alignment)
- Optionally modify: `backend/tests/test_i18n.py` if a direct catalog rendering assertion is cleaner than flow-level assertions

**Step 1: Add focused assertions for the catalog outputs that must change**

Examples of direct expectations:

```python
assert "Proveedor:" in t("es", "wa.client.profile.body", **params)
assert "Provider:" in t("en", "wa.client.profile.body", **params)
assert "chat privado de Tenant" not in t("es", "wa.tenant.client_context.collision", **params)
assert "private Tenant chat" not in t("en", "wa.tenant.client_context.collision", **params)
```

For legacy keys, assert the intended outcome explicitly:

- if they remain, they must not expose `Tenant`
- if they are removed, add the reference-search verification in the implementation task instead of forcing runtime assertions

**Step 2: Add focused assertions for client-visible provider terminology**

If `test_client_console_service.py` already exercises the rendered profile, prefer assertions like:

```python
assert "Proveedor:" in reply
assert "Tenant:" not in reply
```

**Step 3: Run the focused tests and verify they fail**

Run:

```bash
cd backend && uv run pytest tests/test_whatsapp_client_context_shortcut.py tests/test_client_console_service.py -q
```

Expected: FAIL while the catalogs still expose `Tenant` / broken Spanish strings.

**Step 4: Commit the red tests**

```bash
git add backend/tests/test_whatsapp_client_context_shortcut.py backend/tests/test_client_console_service.py backend/tests/test_i18n.py backend/tests/test_whatsapp_credential_auth_flow.py
git commit -m "test: lock visible catalog terminology"
```

Only include files actually changed.

---

### Task 4: Implement frontend + WhatsApp catalog copy changes

**TDD scenario:** Modifying tested code — make focused catalog tests pass

**Files:**
- Modify: `backend/app/core/i18n/catalogs_es_frontend.py`
- Modify: `backend/app/core/i18n/catalogs_en_frontend.py`
- Modify: `backend/app/core/i18n/catalogs_es_wa.py`
- Modify: `backend/app/core/i18n/catalogs_en_wa.py`

**Step 1: Update frontend visible values only**

Required minimum changes:

```python
"frontend.dashboard.master_support": "Estás gestionando el catálogo de esta empresa en modo soporte"
"frontend.dashboard.tenant.exit_tenant": "Salir de la empresa"
"frontend.subscriptions.recipient_mode_tenant_only": "Solo administración"
"frontend.subscriptions.recipient_mode_both": "Administración y cliente"
"frontend.dashboard.client.tenant": "Proveedor"
```

```python
"frontend.dashboard.master_support": "You are managing this business catalog in support mode."
"frontend.dashboard.tenant.exit_tenant": "Exit business context"
"frontend.subscriptions.recipient_mode_tenant_only": "Admin only"
"frontend.subscriptions.recipient_mode_both": "Admin and client"
"frontend.dashboard.client.tenant": "Provider"
```

**Step 2: Fix the WhatsApp client/context values**

Required minimum changes:

```python
"wa.client.profile.body": "👤 *Mi Perfil*\n\nNombre: {full_name}\nProveedor: {tenant_name}\nTeléfono: {phone}\nEstado: {status}"
```

```python
"wa.client.profile.body": "👤 *My Profile*\n\nName: {full_name}\nProvider: {tenant_name}\nPhone: {phone}\nStatus: {status}"
```

```python
"wa.tenant.client_context.collision": "⚠️ Ya tienes una gestión del cliente abierta. Envía *0* en tu chat privado de administración antes de abrir otra."
```

```python
"wa.tenant.client_context.collision": "⚠️ You already have a client management session open. Send *0* in your private admin chat before opening another one."
```

**Step 3: Resolve the legacy client-context key decision surgically**

Search first:

```bash
rg -n "wa\.tenant\.client_context\.(active|inactive)\.(menu_text|invalid_option)" backend frontend backend/tests
```

Then do one of:

- **No references found:** remove the four keys in ES + EN
- **References found:** keep them, but update their visible values so they do not expose `Tenant`

Do not guess. Search first, then act.

**Step 4: Re-run focused backend tests**

Run:

```bash
cd backend && uv run pytest tests/test_whatsapp_client_context_shortcut.py tests/test_client_console_service.py -q
```

Expected: PASS.

**Step 5: Run static checks for the exact hotspots**

Run:

```bash
rg -n "frontend\.dashboard\.master_support|frontend\.dashboard\.tenant\.exit_tenant|frontend\.subscriptions\.recipient_mode_tenant_only|frontend\.subscriptions\.recipient_mode_both|frontend\.dashboard\.client\.tenant" backend/app/core/i18n/catalogs_*_frontend.py
```

```bash
rg -n "wa\.client\.profile\.body|wa\.tenant\.client_context\.collision|wa\.tenant\.client_context\.active\.menu_text|wa\.tenant\.client_context\.active\.invalid_option|wa\.tenant\.client_context\.inactive\.menu_text|wa\.tenant\.client_context\.inactive\.invalid_option" backend/app/core/i18n/catalogs_*_wa.py
```

Inspect the matches to verify visible values only.

**Step 6: Commit**

```bash
git add backend/app/core/i18n/catalogs_es_frontend.py backend/app/core/i18n/catalogs_en_frontend.py backend/app/core/i18n/catalogs_es_wa.py backend/app/core/i18n/catalogs_en_wa.py
git commit -m "feat: update visible product terminology catalogs"
```

---

### Task 5: Update Master Dashboard visible copy and documentation examples

**TDD scenario:** Trivial change — use judgment, then verify thoroughly

**Files:**
- Modify: `frontend/src/views/MasterDashboardView.vue`
- Modify: `docs/architecture/whatsapp-console-flow.md`
- Modify: `docs/architecture/n8n-workflow.md`
- Modify: `docs/project-pdr/business-rules.md`
- Optionally modify: any other `docs/` file with literal user-facing examples found during search

**Step 1: Update the visible literals in `MasterDashboardView.vue`**

Target strings include:

```vue
const modalTitle = computed(() => (isEditMode.value ? 'Edit Business' : 'Create Business'))
```

```vue
<span>Total Businesses</span>
```

And user-facing success/error/confirm strings such as:

```js
successMessage.value = 'Business updated successfully.'
successMessage.value = 'Business created successfully.'
errorMessage.value = 'Cannot delete active business. Deactivate first.'
window.confirm(`Delete business ${tenant.full_name}? This action cannot be undone.`)
```

Keep JS variable names like `tenant`, `loadTenants`, `toggleTenantStatus`, etc.

**Step 2: Update only literal user-facing docs examples**

Examples to fix:

- `docs/architecture/whatsapp-console-flow.md`
  - menu table rows `Ver Tenants`, `Crear Tenant`, etc.
- `docs/architecture/n8n-workflow.md`
  - example replies containing `📋 *Lista de Tenants*`
- `docs/project-pdr/business-rules.md`
  - master menu literal

Do **not** rewrite technical references like `Tenant locale`, `Tenant scope`, `Tenant service`, or `/tenants/...`.

**Step 3: Run static search across docs + dashboard**

Run:

```bash
rg -n "Ver Tenants|Crear Tenant|Desactivar Tenant|Eliminar Tenant|Lista de Tenants|Detalle del Tenant|Tenant:" frontend/src/views/MasterDashboardView.vue docs/architecture/whatsapp-console-flow.md docs/architecture/n8n-workflow.md docs/project-pdr/business-rules.md
```

Expected: no matches.

**Step 4: Run frontend tests**

Run:

```bash
cd frontend && npm test
```

Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/src/views/MasterDashboardView.vue docs/architecture/whatsapp-console-flow.md docs/architecture/n8n-workflow.md docs/project-pdr/business-rules.md
git commit -m "docs: align visible terminology and dashboard copy"
```

---

### Task 6: Final verification sweep

**TDD scenario:** Verification before completion

**Files:**
- No new files required

**Step 1: Run the backend suite required by this change**

Run:

```bash
cd backend && uv run pytest tests/test_contingency_reply_policy.py tests/test_whatsapp_menu_flow.py tests/test_whatsapp_lifecycle_flow.py tests/test_whatsapp_list_select_flow.py tests/test_whatsapp_create_flow.py tests/test_whatsapp_endpoint.py tests/test_whatsapp_client_context_shortcut.py tests/test_client_console_service.py -q
```

If additional assertions were changed in other files, include them too.

**Step 2: Run frontend tests again if the dashboard file changed after the last pass**

Run:

```bash
cd frontend && npm test
```

**Step 3: Run the static copy audit for the exact in-scope surfaces**

Run:

```bash
rg -n "Tenant|Tenants|tenant" frontend/src/views/MasterDashboardView.vue backend/app/core/i18n/catalogs_*_frontend.py backend/app/core/i18n/catalogs_*_wa.py backend/app/services/whatsapp_console_service backend/app/services/contingency_reply_policy/policy.py docs/architecture/whatsapp-console-flow.md docs/architecture/n8n-workflow.md docs/project-pdr/business-rules.md -S
```

Expected:
- only acceptable internal/technical occurrences remain
- no user-facing literal in scope shows old terminology

**Step 4: Run formatting/lint checks only if your edits introduced formatting drift**

Optional:

```bash
cd backend && uv run ruff check .
cd backend && uv run ruff format --check .
```

**Step 5: Final commit if verification required follow-up edits**

```bash
git add -A
git commit -m "test: verify visible terminology rollout"
```

Only create this commit if verification forced a real code/doc/test adjustment.

---

## Execution notes

- Keep every change traceable to TPL-8 visible copy requirements.
- Do not rename internal `Tenant` artifacts.
- Prefer exact assertions over vague substring dilution.
- For legacy keys: search references first, then remove or sanitize.
- For docs: update literal user-facing examples, not technical vocabulary.

## Success criteria

Implementation is complete only when:

- no in-scope user-facing surface still shows `tenant` / `Tenant` / `Tenants`
- frontend + WhatsApp copy follows the approved context-specific terminology
- mojibake is fixed in all touched strings
- affected tests pass without being weakened unnecessarily
- docs with literal visible examples are synchronized
- internal domain names remain unchanged
