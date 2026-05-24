# Research Report: i18n & Tenant Subscription WhatsApp Flow Improvements

## 1. Admin Panel "Contraseña Inicial" Hardcoded Label Fix

### Context & Finding
In the tenant web admin panel, under the "Club de Clientes" (Client management section), the label for the initial password input of a new client is currently hardcoded in Spanish as "Contraseña inicial" (with lowercase/uppercase variants depending on context).

### Exact Location
- **File Path**: `frontend/src/views/TenantDashboardView.vue`
- **Line (~100-110 in Template)**:
  ```html
  <label v-if="!isEditingClient">
    Contraseña inicial
    <input v-model="clientForm.password" type="password" autocomplete="new-password" required />
  </label>
  ```

### Proposed Resolution & Key Paths
To localize this string appropriately following the project guidelines:
1. Define a new i18n key in both frontend catalog translation files:
   - **File**: `backend/app/core/i18n/catalogs_es_frontend.py`
     - **Key**: `"frontend.clients.initial_password": "Contraseña inicial"`
   - **File**: `backend/app/core/i18n/catalogs_en_frontend.py`
     - **Key**: `"frontend.clients.initial_password": "Initial password"`
2. Replace the hardcoded string in the Vue template with:
   - `{{ i18nStore.t('frontend.clients.initial_password') }}`

---

## 2. WhatsApp Subscriptions Status-Filter & Lists Hardcoded Spanish Text

### Context & Finding
In the WhatsApp tenant admin console, when listing subscriptions, several texts such as the list title `"📋 *Suscripciones*"` and the subscription status labels (`"Activa"`, `"Expirada"`, `"Cancelada"`) are hardcoded in Spanish within formatting helpers rather than using `_i18n_t`.

### Exact Location
- **File Path**: `backend/app/services/whatsapp_tenant_console_service/formatters.py`
- **Function**: `_format_subscription_list(subscriptions: list[Any], show_status: bool = True) -> tuple[str, dict[str, str]]`
- **Hardcoded Codes**:
  - The list title/header prefix: `"📋 *Suscripciones*\n\n"`
  - The status translation maps:
    ```python
    status_name = {
        "active": "Activa",
        "expired": "Expirada",
        "cancelled": "Cancelada",
    }.get(sub.status, sub.status)
    ```

### Proposed i18n Translation Keys
We need to leverage `_i18n_t(ctx.get_locale(), ...)` (or the custom shorthand helper `_t` defined in `formatters.py`).
The following keys should be added/re-used:
- **Keys to Add/Use in `backend/app/core/i18n/catalogs_es_wa.py`**:
  - `"wa.tenant.subscriptions.list.header"`: `"📋 *Suscripciones*\n\n"`
  - `"wa.tenant.subscriptions.status.active"`: `"Activa"`
  - `"wa.tenant.subscriptions.status.expired"`: `"Expirada"`
  - `"wa.tenant.subscriptions.status.cancelled"`: `"Cancelada"`
- **Keys to Add/Use in `backend/app/core/i18n/catalogs_en_wa.py`**:
  - `"wa.tenant.subscriptions.list.header"`: `"📋 *Subscriptions*\n\n"`
  - `"wa.tenant.subscriptions.status.active"`: `"Active"`
  - `"wa.tenant.subscriptions.status.expired"`: `"Expired"`
  - `"wa.tenant.subscriptions.status.cancelled"`: `"Cancelled"`

---

## 3. WhatsApp Subscription Navigation Behavior Map

### Current Navigation Behavior
1. **Interactive Navigation**:
   - `0` is registered globally as part of `RESET_COMMANDS = {"0", "menu", "menú", "/menu", "cancelar"}`.
   - Any message in `RESET_COMMANDS` completely terminates the active flow and returns to the main menu (or exits entirely if there was no active flow).
2. **Current Meaning of 0 & Missing Options**:
   - In `wa.tenant.subscriptions.menu` (`KEY_SUBSCRIPTIONS_MENU`), option `0️⃣ Volver al menú principal` is shown, which resets the session.
   - In `wa.tenant.subscriptions.filter_prompt` (`KEY_SUBSCRIPTIONS_FILTER_PROMPT`), option `0️⃣ Volver` is listed. Escribiendo `0` actually terminates/cancels the flow completely due to the global `RESET_COMMANDS` handler intercepting it in `service.py:172` and returning the main menu.
   - In `_format_subscription_list` (subscriptions list display): There is currently **no 0 option** shown to go back to the previous screen or cancel/exit from the list, nor are there any back/next paging options (i.e., `9️⃣ Siguiente` or `8️⃣ Anterior`).

---

## 4. Subscriptions Pagination Logic & Propose Changes

### Current Behavior / Issue
- Currently, `list_subscriptions` fetches **all** tenant subscriptions matching the status filter.
- The list formatter `_format_subscription_list` takes the entire list, maps items from `1` to `N`, and prints all of them in a single massive WhatsApp message.
- If there are 20+ subscriptions, the message is extremely long, and the user cannot easily navigate them since the selection map is capped by index.

### Proposed Pagination Logic (8 items per page)
To enforce a clean, user-friendly 8 subscriptions per page pagination:

1. **Session & State Management**:
   - Store the current page index (`page`) and the selected status filter in the session (`session.temp_data`).
   - For example: `session.temp_data = {"status": msg, "page": 1}`.

2. **The Pagination Keys & Formatting Options**:
   - Out of the 10 standard single digits (`1-9`, `0`):
     - `1` through `8` will map to actual subscription list items.
     - `9` will act as a multi-functional navigation option:
       - If there is a next page: `9️⃣ Siguiente` (Next page) is shown.
       - If on subsequent pages and there is no next page, or as a general back/previous option, we can use `9` for Next / Back depending on availability, or introduce `8` for Previous and `9` for Next (which means list items can be maximum 7 per page).
       - *Alternatively (Recommended)*: List 8 items (keys `1-8`). Let `9` represent the Next page if another page exists, and if we are on page > 1, let `9` cycle or use another character, or list a helper indicator. If we want both Back and Next, we limit list items to 7 (keys `1-7`), keeping `8` for Prev and `9` for Next.
       - Let's propose: **7 items per page max**, with:
         - `8️⃣ Anterior` (Previous page) — only if `page > 1`.
         - `9️⃣ Siguiente` (Next page) — only if `has_more`.
         - `0️⃣ Volver/Salir` (Cancel/Exit to main menu or filter menu) — which is already handled by `RESET_COMMANDS`.

3. **Updating handlers inside `subscriptions_flow.py`**:
   - When entering `_handle_subscriptions_filter`, store the status choice in `session.temp_data["status"]` and set `session.temp_data["page"] = 1`.
   - Implement page slicing on the fetched subscriptions list: `start = (page - 1) * 7`, `end = start + 7`.
   - Slice the subscriptions list: `page_subs = subscriptions[start:end]`.
   - Update `_format_subscription_list` to handle page state, render only the active page slice, append the navigation options (`8️⃣` and `9️⃣`), and map selection values:
     - Map `msg == "8"` to trigger a page decrement.
     - Map `msg == "9"` to trigger a page increment.
     - Map `msg == "0"` to clear the session/flow (default reset command behavior).

4. **Edge Cases to Preserve**:
   - **Less than 7 items total**: Do not show paging buttons `8` or `9`.
   - **Exactly 7 items on previous page / Next page empty**: Bound checks to prevent out-of-range navigation.
   - **Dynamic Selection Map**: The selection map should only resolve `1` to `7` keys to their respective subscription UUIDs on the current page. Let `8` and `9` do flow actions instead of mapping to subscription UUIDs.
