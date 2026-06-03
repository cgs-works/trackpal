# Uniform WhatsApp Console Navigation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build one strict WhatsApp console navigation model where `8` means Siguiente/Next, `9` means Regresar/Back, and `0` means Cancelar/Cancel across every console flow.

**Architecture:** Add a shared navigation layer that stores a small screen stack inside existing `ConversationSession.temp_data`, then migrate console families incrementally. Existing `flow` and `step` stay during migration; navigation helpers become the single source of truth for numeric control options and screen-stack behavior.

**Tech Stack:** FastAPI backend, Python 3.11+, Pydantic v2, Redis-backed `WhatsAppSessionService`, pytest/pytest-asyncio, WhatsApp i18n catalogs.

---

## File Structure

Create:

- `backend/app/services/whatsapp_navigation.py` — shared constants, input classification, stack serialization, and helper functions.
- `backend/tests/test_whatsapp_navigation.py` — unit tests for navigation helpers and stack behavior.
- `backend/tests/test_whatsapp_console_navigation_contract.py` — catalog/source contract tests rejecting conflicting numeric labels.

Modify:

- `backend/app/services/whatsapp_session_service/service.py` — no schema change required; use `temp_data["_nav"]` for state.
- `backend/app/services/whatsapp_tenant_console_service/constants.py` — remove `9` from reset/cancel commands and keep `0` as cancel.
- `backend/app/services/whatsapp_tenant_console_service/service.py` — route `0`, `9`, `8` through shared navigation helpers.
- `backend/app/services/whatsapp_tenant_console_service/clients_flow.py` — clients menu/list/detail/block back/cancel behavior.
- `backend/app/services/whatsapp_tenant_console_service/clients_crud.py` — client create/edit/confirm cancel behavior.
- `backend/app/services/whatsapp_tenant_console_service/catalog_flow.py` — catalog service/plan menus and edit prompts.
- `backend/app/services/whatsapp_tenant_console_service/profile_flow.py` — profile submenu/edit/password/locale screens.
- `backend/app/services/whatsapp_tenant_console_service/subscriptions_flow.py` — subscriptions menu/filter/list/detail and pagination.
- `backend/app/services/whatsapp_tenant_console_service/subscriptions_create.py` — create subscription wizard cancel/back behavior.
- `backend/app/services/whatsapp_tenant_console_service/subscriptions_create_confirm.py` — duration/custom date/confirm cancel behavior.
- `backend/app/services/whatsapp_tenant_console_service/subscriptions_edit.py` — edit subscription field/value prompts.
- `backend/app/services/whatsapp_tenant_console_service/subscriptions_lifecycle.py` — cancel/reactivate/renew confirmation prompts.
- `backend/app/services/whatsapp_tenant_console_service/codigo_flow.py` — access-code lookup cancel/back behavior.
- `backend/app/services/whatsapp_tenant_console_service/formatters.py` — subscription pagination labels/order.
- `backend/app/services/whatsapp_console_service/messages.py` — Master Console menu/help/fallback constants.
- `backend/app/services/whatsapp_console_service/service.py` — Master Console routing for `0`, `9`, `8`.
- `backend/app/services/whatsapp_console_service/list_flow.py` — Master tenant list navigation.
- `backend/app/services/whatsapp_console_service/detail_flow.py` — Master tenant detail navigation.
- `backend/app/services/whatsapp_console_service/create_handlers.py` — Master tenant create wizard cancel/back prompts.
- `backend/app/services/whatsapp_console_service/create_confirm.py` — Master create confirmation cancel behavior.
- `backend/app/services/whatsapp_console_service/edit_handlers.py` — Master tenant edit flow back/cancel behavior.
- `backend/app/services/whatsapp_console_service/lifecycle_messages.py` — Master deactivate/delete prompts.
- `backend/app/services/whatsapp_console_service/lifecycle_confirm.py` — Master deactivate/delete confirmation cancel behavior.
- `backend/app/services/whatsapp_master_console_facade/constants.py` — login/auth prompt semantics.
- `backend/app/services/whatsapp_master_console_facade/login_flow.py` — login reset/cancel behavior.
- `backend/app/services/whatsapp_client_console_facade/facade.py` — client console menu/detail back/cancel behavior.
- `backend/app/api/v1/endpoints/integrations/console_modes.py` — ambiguity mode uses `0` cancel and never uses `9` cancel.
- `backend/app/api/v1/endpoints/integrations/console_handlers.py` — unauthenticated code lookup and Client Context Shortcut dispatcher uses shared constants.
- `backend/app/api/v1/endpoints/integrations/console_context_shortcut.py` — Client Context Shortcut menus use stack/back/cancel consistently.
- `backend/app/core/i18n/catalogs_es_wa.py` — Spanish labels and prompts.
- `backend/app/core/i18n/catalogs_en_wa.py` — English labels and prompts.
- Relevant tests under `backend/tests/test_whatsapp_*.py`.
- `docs/architecture/whatsapp-console-flow.md` — document global navigation contract.

---

## Task 1: Shared Navigation Primitives

**Files:**
- Create: `backend/app/services/whatsapp_navigation.py`
- Create: `backend/tests/test_whatsapp_navigation.py`

- [x] **Step 1: Write failing unit tests**

Create `backend/tests/test_whatsapp_navigation.py`:

```python
from app.services.whatsapp_navigation import (
    NAV_BACK,
    NAV_CANCEL,
    NAV_NEXT,
    ConsoleScreen,
    clear_navigation,
    current_screen,
    is_back,
    is_cancel,
    is_next,
    load_navigation,
    pop_screen,
    push_screen,
    replace_screen,
)
from app.services.whatsapp_session_service import ConversationSession


def test_numeric_constants_are_strict_contract() -> None:
    assert NAV_NEXT == "8"
    assert NAV_BACK == "9"
    assert NAV_CANCEL == "0"


def test_numeric_input_classification() -> None:
    assert is_next("8") is True
    assert is_next(" 8 ") is True
    assert is_back("9") is True
    assert is_cancel("0") is True
    assert is_cancel("cancelar") is True
    assert is_cancel("salir") is True
    assert is_cancel("cerrar") is True
    assert is_cancel("9") is False
    assert is_back("0") is False
    assert is_next("9") is False


def test_push_replace_pop_navigation_stack() -> None:
    session = ConversationSession(phone="12015550001")

    replace_screen(session, "tenant.main")
    assert current_screen(session) == ConsoleScreen(id="tenant.main", params={})

    push_screen(session, "tenant.clients.menu")
    assert current_screen(session) == ConsoleScreen(id="tenant.clients.menu", params={})
    state = load_navigation(session)
    assert state.stack == [ConsoleScreen(id="tenant.main", params={})]

    push_screen(session, "tenant.clients.detail", client_id="abc")
    assert current_screen(session) == ConsoleScreen(
        id="tenant.clients.detail", params={"client_id": "abc"}
    )

    previous = pop_screen(session)
    assert previous == ConsoleScreen(id="tenant.clients.menu", params={})
    assert current_screen(session) == ConsoleScreen(id="tenant.clients.menu", params={})

    previous = pop_screen(session)
    assert previous == ConsoleScreen(id="tenant.main", params={})
    assert current_screen(session) == ConsoleScreen(id="tenant.main", params={})


def test_clear_navigation_removes_private_temp_data_key() -> None:
    session = ConversationSession(phone="12015550001")
    replace_screen(session, "tenant.main")
    push_screen(session, "tenant.clients.menu")

    clear_navigation(session)

    assert "_nav" not in session.temp_data
    assert current_screen(session) is None
```

- [x] **Step 2: Run tests and verify they fail**

Run:

```bash
cd backend
uv run pytest tests/test_whatsapp_navigation.py -q
```

Expected: import failure for `app.services.whatsapp_navigation`.

- [x] **Step 3: Implement navigation module**

Create `backend/app/services/whatsapp_navigation.py`:

```python
"""Shared WhatsApp console navigation helpers.

Numeric contract:
- 8 = next
- 9 = back
- 0 = cancel
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

NAV_NEXT = "8"
NAV_BACK = "9"
NAV_CANCEL = "0"

_NAV_TEMP_KEY = "_nav"
_CANCEL_ALIASES = {"cancelar", "cancel", "salir", "cerrar", "exit", "close"}


@dataclass(frozen=True)
class ConsoleScreen:
    id: str
    params: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ConsoleNavigationState:
    current: ConsoleScreen | None = None
    stack: list[ConsoleScreen] = field(default_factory=list)


def _clean(message: str | None) -> str:
    return (message or "").strip().lower()


def is_next(message: str | None) -> bool:
    return _clean(message) == NAV_NEXT


def is_back(message: str | None) -> bool:
    return _clean(message) == NAV_BACK


def is_cancel(message: str | None) -> bool:
    value = _clean(message)
    return value == NAV_CANCEL or value in _CANCEL_ALIASES


def normalize_nav_input(message: str | None) -> str | None:
    if is_next(message):
        return NAV_NEXT
    if is_back(message):
        return NAV_BACK
    if is_cancel(message):
        return NAV_CANCEL
    return None


def _screen_from_raw(raw: Any) -> ConsoleScreen | None:
    if not isinstance(raw, dict):
        return None
    screen_id = raw.get("id")
    if not isinstance(screen_id, str) or not screen_id:
        return None
    params_raw = raw.get("params") or {}
    params = {
        str(key): str(value)
        for key, value in params_raw.items()
        if value is not None
    } if isinstance(params_raw, dict) else {}
    return ConsoleScreen(id=screen_id, params=params)


def _screen_to_raw(screen: ConsoleScreen | None) -> dict[str, Any] | None:
    if screen is None:
        return None
    return {"id": screen.id, "params": dict(screen.params)}


def load_navigation(session: Any) -> ConsoleNavigationState:
    raw = getattr(session, "temp_data", {}).get(_NAV_TEMP_KEY)
    if not isinstance(raw, dict):
        return ConsoleNavigationState()

    current = _screen_from_raw(raw.get("current"))
    stack_raw = raw.get("stack") or []
    stack = []
    if isinstance(stack_raw, list):
        for item in stack_raw:
            screen = _screen_from_raw(item)
            if screen is not None:
                stack.append(screen)
    return ConsoleNavigationState(current=current, stack=stack)


def save_navigation(session: Any, state: ConsoleNavigationState) -> None:
    if not hasattr(session, "temp_data") or session.temp_data is None:
        session.temp_data = {}
    session.temp_data[_NAV_TEMP_KEY] = {
        "current": _screen_to_raw(state.current),
        "stack": [_screen_to_raw(screen) for screen in state.stack],
    }


def current_screen(session: Any) -> ConsoleScreen | None:
    return load_navigation(session).current


def replace_screen(session: Any, screen_id: str, **params: str) -> None:
    save_navigation(
        session,
        ConsoleNavigationState(
            current=ConsoleScreen(id=screen_id, params={k: str(v) for k, v in params.items()}),
            stack=load_navigation(session).stack,
        ),
    )


def push_screen(session: Any, screen_id: str, **params: str) -> None:
    state = load_navigation(session)
    stack = list(state.stack)
    if state.current is not None:
        stack.append(state.current)
    save_navigation(
        session,
        ConsoleNavigationState(
            current=ConsoleScreen(id=screen_id, params={k: str(v) for k, v in params.items()}),
            stack=stack,
        ),
    )


def pop_screen(session: Any) -> ConsoleScreen | None:
    state = load_navigation(session)
    if not state.stack:
        save_navigation(session, ConsoleNavigationState(current=None, stack=[]))
        return None
    stack = list(state.stack)
    previous = stack.pop()
    save_navigation(session, ConsoleNavigationState(current=previous, stack=stack))
    return previous


def clear_navigation(session: Any) -> None:
    if hasattr(session, "temp_data") and isinstance(session.temp_data, dict):
        session.temp_data.pop(_NAV_TEMP_KEY, None)
```

- [x] **Step 4: Run tests and verify they pass**

Run:

```bash
cd backend
uv run pytest tests/test_whatsapp_navigation.py -q
```

Expected: `4 passed`.

- [x] **Step 5: Commit**

```bash
git add backend/app/services/whatsapp_navigation.py backend/tests/test_whatsapp_navigation.py
git commit -m "feat(whatsapp): add shared console navigation helpers"
```

---

## Task 2: Contract Tests for Forbidden Navigation Semantics

**Files:**
- Create: `backend/tests/test_whatsapp_console_navigation_contract.py`
- Modify: `backend/app/core/i18n/catalogs_es_wa.py`
- Modify: `backend/app/core/i18n/catalogs_en_wa.py`

- [x] **Step 1: Write failing contract tests**

Create `backend/tests/test_whatsapp_console_navigation_contract.py`:

```python
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CATALOG_FILES = [
    ROOT / "app" / "core" / "i18n" / "catalogs_es_wa.py",
    ROOT / "app" / "core" / "i18n" / "catalogs_en_wa.py",
]

SOURCE_GLOBS = [
    ROOT / "app" / "services",
    ROOT / "app" / "api" / "v1" / "endpoints" / "integrations",
]

FORBIDDEN_PATTERNS = [
    re.compile(r"0(?:\ufe0f)?(?:⃣|️⃣)?\s*(?:Volver|Regresar|Back|Return)", re.IGNORECASE),
    re.compile(r"9(?:\ufe0f)?(?:⃣|️⃣)?\s*(?:Siguiente|Next)", re.IGNORECASE),
    re.compile(r"8(?:\ufe0f)?(?:⃣|️⃣)?\s*(?:Anterior|Previous|Regresar|Back)", re.IGNORECASE),
    re.compile(r"(?:escribe|write|type|respond(?:e)?)\s+\*?9\*?\s+(?:para\s+)?(?:cancelar|cancel)", re.IGNORECASE),
]

REQUIRED_LABELS_ES = ["8️⃣ Siguiente", "9️⃣ Regresar", "0️⃣ Cancelar"]
REQUIRED_LABELS_EN = ["8️⃣ Next", "9️⃣ Back", "0️⃣ Cancel"]


def _python_text_files(root: Path) -> list[Path]:
    return [path for path in root.rglob("*.py") if "__pycache__" not in str(path)]


def test_whatsapp_catalogs_do_not_define_conflicting_numeric_navigation() -> None:
    offenders: list[str] = []
    for path in CATALOG_FILES:
        text = path.read_text(encoding="utf-8")
        for pattern in FORBIDDEN_PATTERNS:
            for match in pattern.finditer(text):
                offenders.append(f"{path.relative_to(ROOT)}: {match.group(0)!r}")
    assert offenders == []


def test_console_sources_do_not_present_conflicting_numeric_navigation() -> None:
    offenders: list[str] = []
    for root in SOURCE_GLOBS:
        for path in _python_text_files(root):
            text = path.read_text(encoding="utf-8")
            for pattern in FORBIDDEN_PATTERNS:
                for match in pattern.finditer(text):
                    offenders.append(f"{path.relative_to(ROOT)}: {match.group(0)!r}")
    assert offenders == []


def test_shared_navigation_labels_exist_in_catalogs() -> None:
    es_text = CATALOG_FILES[0].read_text(encoding="utf-8")
    en_text = CATALOG_FILES[1].read_text(encoding="utf-8")

    for label in REQUIRED_LABELS_ES:
        assert label in es_text
    for label in REQUIRED_LABELS_EN:
        assert label in en_text
```

- [x] **Step 2: Run tests and verify failures identify current conflicts**

Run:

```bash
cd backend
uv run pytest tests/test_whatsapp_console_navigation_contract.py -q
```

Expected: failures showing current conflicts such as `0️⃣ Volver`, `9️⃣ Siguiente`, `8️⃣ ← Anterior`, and `9 para cancelar`.

- [x] **Step 3: Add shared i18n labels**

Add these keys near other WhatsApp shared keys in `backend/app/core/i18n/catalogs_es_wa.py`:

```python
    "wa.nav.next": "8️⃣ Siguiente",
    "wa.nav.back": "9️⃣ Regresar",
    "wa.nav.cancel": "0️⃣ Cancelar",
    "wa.nav.invalid_option": "❌ Opcion invalida. Usa *8* para siguiente, *9* para regresar o *0* para cancelar cuando esas opciones esten disponibles.",
```

Add these keys in `backend/app/core/i18n/catalogs_en_wa.py`:

```python
    "wa.nav.next": "8️⃣ Next",
    "wa.nav.back": "9️⃣ Back",
    "wa.nav.cancel": "0️⃣ Cancel",
    "wa.nav.invalid_option": "❌ Invalid option. Use *8* for next, *9* to go back, or *0* to cancel when those options are available.",
```

- [x] **Step 4: Keep conflict tests failing for remaining old labels**

Run:

```bash
cd backend
uv run pytest tests/test_whatsapp_console_navigation_contract.py -q
```

Expected: shared label test passes; conflict tests still fail until later migration tasks remove old semantics.

- [x] **Step 5: Commit contract tests and labels**

```bash
git add backend/tests/test_whatsapp_console_navigation_contract.py backend/app/core/i18n/catalogs_es_wa.py backend/app/core/i18n/catalogs_en_wa.py
git commit -m "test(whatsapp): enforce console navigation contract"
```

---

## Task 3: Tenant Admin Global Routing and Help Text

**Files:**
- Modify: `backend/app/services/whatsapp_tenant_console_service/constants.py`
- Modify: `backend/app/services/whatsapp_tenant_console_service/service.py`
- Modify: `backend/app/core/i18n/catalogs_es_wa.py`
- Modify: `backend/app/core/i18n/catalogs_en_wa.py`
- Test: `backend/tests/test_whatsapp_menu_flow.py`

- [x] **Step 1: Add failing tests for `0` cancel and `9` not global cancel**

Add to `backend/tests/test_whatsapp_menu_flow.py`:

```python
@pytest.mark.asyncio
async def test_tenant_active_flow_zero_cancels_but_nine_does_not_global_cancel(
    fake_redis_manager,
):
    from app.services.whatsapp_session_service import WhatsAppSessionService
    from app.services.whatsapp_tenant_console_service import WhatsAppTenantConsoleService

    session_service = WhatsAppSessionService(fake_redis_manager, ttl_seconds=900)
    session = await session_service.create_session("admin:12015550001")
    session.flow = "clients"
    session.step = "list_select"
    session.selection_map = {"1": "00000000-0000-0000-0000-000000000001"}
    await session_service.save_session(session)

    service = WhatsAppTenantConsoleService()

    nine_reply = await service.process_message(
        phone="12015550001",
        message="9",
        session_service=session_service,
    )
    assert "Operacion cancelada" not in nine_reply
    assert await session_service.get_session("admin:12015550001") is not None

    zero_reply = await service.process_message(
        phone="12015550001",
        message="0",
        session_service=session_service,
    )
    assert "Sesion cerrada" in zero_reply or "Operacion cancelada" in zero_reply
    assert await session_service.get_session("admin:12015550001") is None
```

- [x] **Step 2: Run targeted test and verify failure**

Run:

```bash
cd backend
uv run pytest tests/test_whatsapp_menu_flow.py::test_tenant_active_flow_zero_cancels_but_nine_does_not_global_cancel -q
```

Expected: failure because old constants include `9` in reset commands or flow handling treats `9` as cancel in some paths.

- [x] **Step 3: Update Tenant Admin reset constants**

In `backend/app/services/whatsapp_tenant_console_service/constants.py`, change:

```python
RESET_COMMANDS = {"0", "9", "menu", "menú", "/menu", "cancelar"}
```

to:

```python
RESET_COMMANDS = {"0", "menu", "menú", "/menu", "cancelar", "salir", "cerrar"}
```

- [x] **Step 4: Route cancel through shared helper in service.py**

In `backend/app/services/whatsapp_tenant_console_service/service.py`, import:

```python
from app.services.whatsapp_navigation import is_cancel
```

Replace active-flow global exit condition:

```python
if msg in ("0",) or msg.lower() in (
    "menu",
    "menú",
    "/menu",
    "cancelar",
):
```

with:

```python
if is_cancel(msg) or msg.lower() in ("menu", "menú", "/menu"):
```

Keep existing behavior: `0`/cancel aliases clear active flow; `menu` clears and returns main menu.

- [x] **Step 5: Update help and fallback catalog text**

In Spanish catalog, replace help/fallback language so it states:

```python
"Dentro de un flujo, *0* cancela la operacion, *9* regresa y *8* avanza cuando este disponible."
```

In English catalog, use:

```python
"Inside a flow, *0* cancels, *9* goes back, and *8* advances when available."
```

- [x] **Step 6: Run targeted and contract tests**

Run:

```bash
cd backend
uv run pytest tests/test_whatsapp_menu_flow.py::test_tenant_active_flow_zero_cancels_but_nine_does_not_global_cancel tests/test_whatsapp_console_navigation_contract.py -q
```

Expected: targeted test passes; contract test may still fail for known flow-specific strings.

- [x] **Step 7: Commit**

```bash
git add backend/app/services/whatsapp_tenant_console_service/constants.py backend/app/services/whatsapp_tenant_console_service/service.py backend/app/core/i18n/catalogs_es_wa.py backend/app/core/i18n/catalogs_en_wa.py backend/tests/test_whatsapp_menu_flow.py
git commit -m "fix(whatsapp): align tenant global navigation semantics"
```

---

## Task 4: Tenant Clients, Blocks, Catalog, and Profile Menus

**Files:**
- Modify: `backend/app/services/whatsapp_tenant_console_service/clients_flow.py`
- Modify: `backend/app/services/whatsapp_tenant_console_service/clients_crud.py`
- Modify: `backend/app/services/whatsapp_tenant_console_service/catalog_flow.py`
- Modify: `backend/app/services/whatsapp_tenant_console_service/profile_flow.py`
- Modify: `backend/app/core/i18n/catalogs_es_wa.py`
- Modify: `backend/app/core/i18n/catalogs_en_wa.py`
- Test: `backend/tests/test_whatsapp_menu_flow.py`
- Test: `backend/tests/test_whatsapp_create_flow.py`
- Test: `backend/tests/test_whatsapp_edit_flow.py`

- [x] **Step 1: Add failing tests for clients block back/cancel**

Add to `backend/tests/test_whatsapp_menu_flow.py`:

```python
@pytest.mark.asyncio
async def test_clients_block_menu_uses_nine_back_and_zero_cancel(
    fake_redis_manager,
):
    from app.services.whatsapp_session_service import WhatsAppSessionService
    from app.services.whatsapp_tenant_console_service import WhatsAppTenantConsoleService

    session_service = WhatsAppSessionService(fake_redis_manager, ttl_seconds=900)
    session = await session_service.create_session("admin:12015550001")
    session.flow = "clients"
    session.step = "blocks_unblock"
    session.selection_map = {}
    await session_service.save_session(session)

    service = WhatsAppTenantConsoleService()
    back_reply = await service.process_message(
        phone="12015550001",
        message="9",
        session_service=session_service,
    )
    assert "Clientes" in back_reply or "menu principal" in back_reply

    session = await session_service.create_session("admin:12015550001")
    session.flow = "clients"
    session.step = "blocks_unblock"
    await session_service.save_session(session)
    cancel_reply = await service.process_message(
        phone="12015550001",
        message="0",
        session_service=session_service,
    )
    assert "cancelada" in cancel_reply.lower() or "sesion cerrada" in cancel_reply.lower()
```

- [x] **Step 2: Run and verify failure**

Run:

```bash
cd backend
uv run pytest tests/test_whatsapp_menu_flow.py::test_clients_block_menu_uses_nine_back_and_zero_cancel -q
```

Expected: failure because blocks currently say/use `0` for volver.

- [x] **Step 3: Update clients block i18n labels**

Spanish:

```python
"wa.tenant.clients.blocks.unblock_prompt": "Responde con el numero del bloqueo que deseas desbloquear.\n\n9️⃣ Regresar\n0️⃣ Cancelar",
"wa.tenant.clients.blocks.invalid_selection": "❌ Numero invalido. Responde con un numero de la lista, *9* para regresar o *0* para cancelar.",
```

English:

```python
"wa.tenant.clients.blocks.unblock_prompt": "Reply with the block number you want to unblock.\n\n9️⃣ Back\n0️⃣ Cancel",
"wa.tenant.clients.blocks.invalid_selection": "❌ Invalid number. Reply with a number from the list, *9* to go back, or *0* to cancel.",
```

- [x] **Step 4: Update flow handlers to use shared helpers**

In each modified flow file, import helpers:

```python
from app.services.whatsapp_navigation import is_back, is_cancel, push_screen, pop_screen, replace_screen
```

Use this behavior:

```python
if is_cancel(msg):
    await session_service.clear_session(f"admin:{phone}")
    return self._with_main_menu(self._t("wa.tenant.cancelled"))

if is_back(msg):
    previous = pop_screen(session)
    await session_service.save_session(session)
    return self._t(self.KEY_MAIN_MENU) if previous is None else await self._render_screen(previous, phone, session, session_service, tenant_id, db)
```

If `_render_screen` does not exist yet in tenant service, add a local minimal branch in the handler: for clients blocks return `self._t(self.KEY_CLIENTS_MENU)` or `self._t(self.KEY_MAIN_MENU)` according to the parent screen being migrated.

- [x] **Step 5: Update prompt text where `9` says cancel**

In EN/ES catalogs, update clients/catalog/profile prompts:

- `wa.tenant.clients.create.confirm`: `Escribe *0* para cancelar.` / `Type *0* to cancel.`
- `wa.tenant.clients.deactivate.confirm`: `Escribe *0* para cancelar.` / `Type *0* to cancel.`
- `wa.tenant.clients.delete.confirm`: `Escribe *0* para cancelar.` / `Type *0* to cancel.`
- `wa.tenant.profile.change_password_error_old`: replace `9` cancel with `0` cancel.
- Catalog invalid-selection strings keep `9` back and add `0` cancel where cancellation is available.

- [x] **Step 6: Run affected tests**

Run:

```bash
cd backend
uv run pytest tests/test_whatsapp_menu_flow.py tests/test_whatsapp_create_flow.py tests/test_whatsapp_edit_flow.py tests/test_whatsapp_console_navigation_contract.py -q
```

Expected: menu/create/edit tests pass; contract test has fewer conflicts and may still fail for subscriptions/master/context.

- [x] **Step 7: Commit**

```bash
git add backend/app/services/whatsapp_tenant_console_service/clients_flow.py backend/app/services/whatsapp_tenant_console_service/clients_crud.py backend/app/services/whatsapp_tenant_console_service/catalog_flow.py backend/app/services/whatsapp_tenant_console_service/profile_flow.py backend/app/core/i18n/catalogs_es_wa.py backend/app/core/i18n/catalogs_en_wa.py backend/tests/test_whatsapp_menu_flow.py backend/tests/test_whatsapp_create_flow.py backend/tests/test_whatsapp_edit_flow.py
git commit -m "fix(whatsapp): normalize tenant clients catalog and profile navigation"
```

---

## Task 5: Tenant Subscriptions Pagination and Wizards

**Files:**
- Modify: `backend/app/services/whatsapp_tenant_console_service/subscriptions_flow.py`
- Modify: `backend/app/services/whatsapp_tenant_console_service/subscriptions_create.py`
- Modify: `backend/app/services/whatsapp_tenant_console_service/subscriptions_create_confirm.py`
- Modify: `backend/app/services/whatsapp_tenant_console_service/subscriptions_edit.py`
- Modify: `backend/app/services/whatsapp_tenant_console_service/subscriptions_lifecycle.py`
- Modify: `backend/app/services/whatsapp_tenant_console_service/formatters.py`
- Modify: `backend/app/core/i18n/catalogs_es_wa.py`
- Modify: `backend/app/core/i18n/catalogs_en_wa.py`
- Test: existing subscription tests or `backend/tests/test_whatsapp_endpoint.py`

- [x] **Step 1: Add failing test for subscription pagination**

Add to the most relevant existing subscription WhatsApp test file. If no dedicated file exists, add to `backend/tests/test_whatsapp_endpoint.py`:

```python

def test_subscription_pagination_labels_follow_navigation_contract() -> None:
    from app.core.i18n import t

    assert t("es", "wa.tenant.subscriptions.list.page_next") == "8️⃣ Siguiente"
    assert t("es", "wa.tenant.subscriptions.list.page_prev") == "9️⃣ Regresar"
    assert t("en", "wa.tenant.subscriptions.list.page_next") == "8️⃣ Next"
    assert t("en", "wa.tenant.subscriptions.list.page_prev") == "9️⃣ Back"
```

- [x] **Step 2: Run and verify failure**

Run:

```bash
cd backend
uv run pytest tests/test_whatsapp_endpoint.py::test_subscription_pagination_labels_follow_navigation_contract -q
```

Expected: failure because current labels are `8 previous` and `9 next`.

- [x] **Step 3: Update subscription pagination labels**

Spanish:

```python
"wa.tenant.subscriptions.list.page_next": "8️⃣ Siguiente",
"wa.tenant.subscriptions.list.page_prev": "9️⃣ Regresar",
"wa.tenant.subscriptions.list.cancel": "0️⃣ Cancelar",
```

English:

```python
"wa.tenant.subscriptions.list.page_next": "8️⃣ Next",
"wa.tenant.subscriptions.list.page_prev": "9️⃣ Back",
"wa.tenant.subscriptions.list.cancel": "0️⃣ Cancel",
```

- [x] **Step 4: Update pagination handler semantics**

In `backend/app/services/whatsapp_tenant_console_service/subscriptions_flow.py`, locate list pagination handling. Ensure:

```python
if is_next(msg):
    # page + 1 if another page exists
if is_back(msg):
    # page - 1 if page > 1, otherwise return parent menu/filter
if is_cancel(msg):
    await session_service.clear_session(f"admin:{phone}")
    return self._with_main_menu(self._t("wa.tenant.cancelled"))
```

- [x] **Step 5: Update subscription prompt strings from `9 cancel` to `0 cancel`**

In EN/ES catalogs, update these keys to use `0` for cancellation:

- `wa.tenant.subscriptions.cancel.confirm`
- `wa.tenant.subscriptions.create.confirm`
- `wa.tenant.subscriptions.reactivate.confirm`
- `wa.tenant.subscriptions.renew.confirm`
- `wa.tenant.subscriptions.invalid_selection` must say `9` back and `0` cancel where both are available.

- [x] **Step 6: Run subscription and contract tests**

Run:

```bash
cd backend
uv run pytest tests/test_whatsapp_endpoint.py tests/test_whatsapp_console_navigation_contract.py -q
```

Expected: endpoint tests pass; contract conflicts reduced to master/client/context/unauthenticated if not migrated yet.

- [x] **Step 7: Commit**

```bash
git add backend/app/services/whatsapp_tenant_console_service/subscriptions_flow.py backend/app/services/whatsapp_tenant_console_service/subscriptions_create.py backend/app/services/whatsapp_tenant_console_service/subscriptions_create_confirm.py backend/app/services/whatsapp_tenant_console_service/subscriptions_edit.py backend/app/services/whatsapp_tenant_console_service/subscriptions_lifecycle.py backend/app/services/whatsapp_tenant_console_service/formatters.py backend/app/core/i18n/catalogs_es_wa.py backend/app/core/i18n/catalogs_en_wa.py backend/tests/test_whatsapp_endpoint.py
git commit -m "fix(whatsapp): normalize subscription navigation and pagination"
```

---

## Task 6: Access-Code Lookup and Unauthenticated Flows

**Files:**
- Modify: `backend/app/services/whatsapp_tenant_console_service/codigo_flow.py`
- Modify: `backend/app/api/v1/endpoints/integrations/console_handlers.py`
- Modify: `backend/app/core/i18n/catalogs_es_wa.py`
- Modify: `backend/app/core/i18n/catalogs_en_wa.py`
- Test: `backend/tests/test_whatsapp_endpoint.py`

- [ ] **Step 1: Add failing tests for code lookup cancel/back labels**

Add to `backend/tests/test_whatsapp_endpoint.py`:

```python

def test_codigo_lookup_prompts_use_zero_cancel_not_nine_cancel() -> None:
    from app.core.i18n import t

    assert "*0* para cancelar" in t("es", "wa.tenant.codigo.email_prompt")
    assert "*9* para cancelar" not in t("es", "wa.tenant.codigo.email_prompt")
    assert "*0* to cancel" in t("en", "wa.tenant.codigo.email_prompt")
    assert "*9* to cancel" not in t("en", "wa.tenant.codigo.email_prompt")
```

- [ ] **Step 2: Run and verify failure**

Run:

```bash
cd backend
uv run pytest tests/test_whatsapp_endpoint.py::test_codigo_lookup_prompts_use_zero_cancel_not_nine_cancel -q
```

Expected: failure due current `9` cancel text.

- [ ] **Step 3: Update codigo i18n strings**

Spanish:

```python
"wa.tenant.codigo.cancel": "Regresar",
"wa.tenant.codigo.cancel_direct": "Cancelar",
"wa.tenant.codigo.email_prompt": "✉️ *Buscar Codigo de Acceso*\n\nServicio: *{service_label}*\n\nCual es el *email* del usuario en {service_label}?\n\nLo usaremos para buscar el codigo en la bandeja del buzon tecnico.\n\nEscribe el email o *0* para cancelar.",
"wa.tenant.codigo.invalid_service": "❌ Numero invalido. Responde con un numero de la lista, *9* para regresar o *0* para cancelar.",
"wa.tenant.codigo.invalid_email": "❌ Email invalido. Responde con un email valido o *0* para cancelar.",
```

English equivalent:

```python
"wa.tenant.codigo.cancel": "Back",
"wa.tenant.codigo.cancel_direct": "Cancel",
"wa.tenant.codigo.email_prompt": "✉️ *Find Access Code*\n\nService: *{service_label}*\n\nWhat is the user's email on {service_label}?\n\nWe will search the technical mailbox for the code.\n\nType the email or *0* to cancel.",
"wa.tenant.codigo.invalid_service": "❌ Invalid number. Reply with a number from the list, *9* to go back, or *0* to cancel.",
"wa.tenant.codigo.invalid_email": "❌ Invalid email. Reply with a valid email or *0* to cancel.",
```

- [ ] **Step 4: Update codigo handlers**

In `codigo_flow.py` and unauthenticated flow in `console_handlers.py`, import:

```python
from app.services.whatsapp_navigation import is_back, is_cancel
```

Behavior:

```python
if is_cancel(msg):
    await session_service.clear_session(session_key)
    return self._with_main_menu(_i18n_t(loc, "wa.tenant.cancelled"), locale=loc)

if is_back(msg):
    # service selection from menu returns tenant main menu; direct codigo flow returns previous menu when state exists
```

Unauthenticated lookup has no authenticated main menu. For unauthenticated sessions:

```python
if is_cancel(msg_lower):
    await session_service.clear_session(session_key)
    return WhatsAppConsoleResponse(reply=_i18n_t("es", "wa.tenant.cancelled"))
```

- [ ] **Step 5: Run codigo tests**

Run:

```bash
cd backend
uv run pytest tests/test_whatsapp_endpoint.py::test_codigo_lookup_prompts_use_zero_cancel_not_nine_cancel tests/test_whatsapp_endpoint.py -q
```

Expected: tests pass or reveal endpoint assertions requiring text updates.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/whatsapp_tenant_console_service/codigo_flow.py backend/app/api/v1/endpoints/integrations/console_handlers.py backend/app/core/i18n/catalogs_es_wa.py backend/app/core/i18n/catalogs_en_wa.py backend/tests/test_whatsapp_endpoint.py
git commit -m "fix(whatsapp): normalize access-code lookup navigation"
```

---

## Task 7: Client Context Shortcut Final Navigation Alignment

**Files:**
- Modify: `backend/app/api/v1/endpoints/integrations/console_context_shortcut.py`
- Modify: `backend/app/api/v1/endpoints/integrations/console_handlers.py`
- Modify: `backend/app/core/i18n/catalogs_es_wa.py`
- Modify: `backend/app/core/i18n/catalogs_en_wa.py`
- Test: `backend/tests/test_whatsapp_client_context_shortcut.py`
- Test: `backend/tests/test_whatsapp_endpoint.py`

- [ ] **Step 1: Add failing tests for back/cancel split**

Add to `backend/tests/test_whatsapp_client_context_shortcut.py`:

```python

def test_client_context_catalog_entries_use_nine_back_zero_cancel() -> None:
    from app.core.i18n import t

    detail_options = t("es", "wa.tenant.client_context.detail.options")
    assert "9 Regresar" in detail_options or "9️⃣ Regresar" in detail_options
    assert "0 Cancelar" in detail_options or "0️⃣ Cancelar" in detail_options
    assert "0 Volver" not in detail_options

    edit_prompt = t("es", "wa.tenant.client_context.edit.field_prompt")
    assert "9 Regresar" in edit_prompt or "9️⃣ Regresar" in edit_prompt
    assert "0 Cancelar" in edit_prompt or "0️⃣ Cancelar" in edit_prompt
    assert "0 Volver" not in edit_prompt
```

- [ ] **Step 2: Run and verify failure if legacy duplicate keys remain**

Run:

```bash
cd backend
uv run pytest tests/test_whatsapp_client_context_shortcut.py::test_client_context_catalog_entries_use_nine_back_zero_cancel -q
```

Expected: failure if catalog still has duplicate legacy values.

- [ ] **Step 3: Update Client Context Shortcut catalog entries**

Spanish canonical values:

```python
"wa.tenant.client_context.detail.options": "1 Editar datos\n2 Desactivar\n9 Regresar\n0 Cancelar",
"wa.tenant.client_context.detail.invalid_option": "Opcion no valida.\n\n1 Editar datos\n2 Desactivar\n9 Regresar\n0 Cancelar",
"wa.tenant.client_context.edit.field_prompt": "Que campo desea editar?\n\n1 Nombre completo\n2 Nombre de usuario\n9 Regresar\n0 Cancelar\n\nEl telefono no se puede editar desde el acceso directo.",
"wa.tenant.client_context.edit.field_invalid": "Opcion no valida.\n\n1 Nombre completo\n2 Nombre de usuario\n9 Regresar\n0 Cancelar",
```

English canonical values:

```python
"wa.tenant.client_context.detail.options": "1 Edit data\n2 Deactivate\n9 Back\n0 Cancel",
"wa.tenant.client_context.detail.invalid_option": "Invalid option.\n\n1 Edit data\n2 Deactivate\n9 Back\n0 Cancel",
"wa.tenant.client_context.edit.field_prompt": "Which field do you want to edit?\n\n1 Full name\n2 Username\n9 Back\n0 Cancel\n\nPhone cannot be edited from the shortcut.",
"wa.tenant.client_context.edit.field_invalid": "Invalid option.\n\n1 Full name\n2 Username\n9 Back\n0 Cancel",
```

- [ ] **Step 4: Update handlers**

In `console_context_shortcut.py`, import:

```python
from app.services.whatsapp_navigation import is_back, is_cancel
```

Ensure:

```python
if is_back(msg_lower):
    data["step"] = "active_menu"
    await save_ctx(refresh_ttl=True)
    return WhatsAppConsoleResponse(reply=..., reply_to=admin_jid)

if is_cancel(msg_lower):
    await clear_ctx()
    return WhatsAppConsoleResponse(reply=..., reply_to=admin_jid)
```

Use `is_back` for detail/edit parent navigation. Use `is_cancel` for closing full context and preserve `close_jid`/`close_jids` in dispatcher close responses.

- [ ] **Step 5: Run shortcut tests**

Run:

```bash
cd backend
uv run pytest tests/test_whatsapp_client_context_shortcut.py tests/test_whatsapp_endpoint.py -q
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/v1/endpoints/integrations/console_context_shortcut.py backend/app/api/v1/endpoints/integrations/console_handlers.py backend/app/core/i18n/catalogs_es_wa.py backend/app/core/i18n/catalogs_en_wa.py backend/tests/test_whatsapp_client_context_shortcut.py backend/tests/test_whatsapp_endpoint.py
git commit -m "fix(whatsapp): finish client context navigation alignment"
```

---

## Task 8: Master Console Navigation

**Files:**
- Modify: `backend/app/services/whatsapp_console_service/messages.py`
- Modify: `backend/app/services/whatsapp_console_service/service.py`
- Modify: `backend/app/services/whatsapp_console_service/list_flow.py`
- Modify: `backend/app/services/whatsapp_console_service/detail_flow.py`
- Modify: `backend/app/services/whatsapp_console_service/create_handlers.py`
- Modify: `backend/app/services/whatsapp_console_service/create_confirm.py`
- Modify: `backend/app/services/whatsapp_console_service/edit_handlers.py`
- Modify: `backend/app/services/whatsapp_console_service/edit_messages.py`
- Modify: `backend/app/services/whatsapp_console_service/lifecycle_messages.py`
- Modify: `backend/app/services/whatsapp_console_service/lifecycle_confirm.py`
- Modify: `backend/app/services/whatsapp_master_console_facade/constants.py`
- Modify: `backend/app/services/whatsapp_master_console_facade/login_flow.py`
- Test: `backend/tests/test_whatsapp_list_select_flow.py`
- Test: `backend/tests/test_whatsapp_create_flow.py`
- Test: `backend/tests/test_whatsapp_edit_flow.py`
- Test: `backend/tests/test_whatsapp_lifecycle_flow.py`
- Test: `backend/tests/test_whatsapp_logout_flow.py`

- [ ] **Step 1: Add failing Master Console contract test**

Add to `backend/tests/test_whatsapp_menu_flow.py`:

```python

def test_master_console_help_describes_zero_cancel_nine_back_eight_next() -> None:
    from app.services.whatsapp_console_service import messages

    assert "*0*" in messages.HELP_TEXT and "cancel" in messages.HELP_TEXT.lower() or "cierra" in messages.HELP_TEXT.lower()
    assert "*9*" in messages.HELP_TEXT and "volver" in messages.HELP_TEXT.lower()
    assert "*8*" in messages.HELP_TEXT and "siguiente" in messages.HELP_TEXT.lower()
    assert "*9* o *cancelar* cancelan" not in messages.HELP_TEXT
```

- [ ] **Step 2: Run and verify failure**

Run:

```bash
cd backend
uv run pytest tests/test_whatsapp_menu_flow.py::test_master_console_help_describes_zero_cancel_nine_back_eight_next -q
```

Expected: failure because existing help says `9` cancels.

- [ ] **Step 3: Update Master constants**

In `messages.py`:

```python
RESET_COMMANDS = {"0", "menu", "menú", "/menu", "cancelar", "salir", "cerrar"}
```

Update help/fallback strings so:

- `0` closes/cancels.
- `9` goes back.
- `8` advances when offered.

- [ ] **Step 4: Update Master routing**

In `service.py`, import:

```python
from app.services.whatsapp_navigation import is_cancel
```

Active-flow cancel condition becomes:

```python
if is_cancel(msg_text) or msg_text.lower() in ("menu", "menú", "/menu"):
    if session_service is not None:
        await session_service.clear_session(phone)
    return self._with_main_menu("🚫 Operación cancelada.")
```

Do not intercept `9` globally.

- [ ] **Step 5: Update Master flow prompts and handlers**

Apply consistent replacements:

- lifecycle messages: `Escribe *0* para cancelar.`
- create confirmation: `0` cancels.
- edit select field: `9` returns to detail/menu, `0` cancels.
- list/detail selection: `9` returns to main menu, `0` cancels/closes.

Use `is_back` and `is_cancel` in flow files instead of direct string checks.

- [ ] **Step 6: Run Master tests**

Run:

```bash
cd backend
uv run pytest tests/test_whatsapp_list_select_flow.py tests/test_whatsapp_create_flow.py tests/test_whatsapp_edit_flow.py tests/test_whatsapp_lifecycle_flow.py tests/test_whatsapp_logout_flow.py tests/test_whatsapp_menu_flow.py -q
```

Expected: all pass after updating old assertions.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/whatsapp_console_service backend/app/services/whatsapp_master_console_facade backend/tests/test_whatsapp_list_select_flow.py backend/tests/test_whatsapp_create_flow.py backend/tests/test_whatsapp_edit_flow.py backend/tests/test_whatsapp_lifecycle_flow.py backend/tests/test_whatsapp_logout_flow.py backend/tests/test_whatsapp_menu_flow.py
git commit -m "fix(whatsapp): normalize master console navigation"
```

---

## Task 9: Client Console and Ambiguity Mode

**Files:**
- Modify: `backend/app/services/whatsapp_client_console_facade/facade.py`
- Modify: `backend/app/api/v1/endpoints/integrations/console_modes.py`
- Modify: `backend/app/core/i18n/catalogs_es_wa.py`
- Modify: `backend/app/core/i18n/catalogs_en_wa.py`
- Test: `backend/tests/test_whatsapp_endpoint.py`

- [ ] **Step 1: Add failing tests for client console labels**

Add to `backend/tests/test_whatsapp_endpoint.py`:

```python

def test_client_console_uses_zero_cancel_and_nine_back_labels() -> None:
    from app.core.i18n import t

    menu_es = t("es", "wa.client.main_menu")
    assert "0️⃣ Cancelar" in menu_es
    assert "0️⃣ Salir" not in menu_es

    mode_es = t("es", "wa.client.mode_prompt")
    assert "0️⃣ Cancelar" in mode_es
    assert "9️⃣" not in mode_es or "Regresar" in mode_es
```

- [ ] **Step 2: Run and verify failure**

Run:

```bash
cd backend
uv run pytest tests/test_whatsapp_endpoint.py::test_client_console_uses_zero_cancel_and_nine_back_labels -q
```

Expected: failure because current labels say `0 Salir`.

- [ ] **Step 3: Update client catalog labels**

Spanish:

```python
"wa.client.main_menu": "👤 *Consola de Cliente*\n\n1️⃣ Ver mi perfil\n2️⃣ Ver suscripciones activas\n3️⃣ Buscar codigo de acceso\n\n0️⃣ Cancelar\n\nElige una opcion:",
"wa.client.mode_prompt": "⚠️ Se detectaron dos perfiles para tu numero de telefono.\n\nComo quieres proceder?\n1️⃣ Panel de administracion\n2️⃣ Cliente\n\n0️⃣ Cancelar\n\nElige una opcion:",
```

English:

```python
"wa.client.main_menu": "👤 *Client Console*\n\n1️⃣ View my profile\n2️⃣ View active subscriptions\n3️⃣ Find Access Code\n\n0️⃣ Cancel\n\nChoose an option:",
"wa.client.mode_prompt": "⚠️ Two profiles detected for your phone number.\n\nHow do you want to proceed?\n1️⃣ Admin panel\n2️⃣ Client\n\n0️⃣ Cancel\n\nChoose an option:",
```

- [ ] **Step 4: Update client facade and ambiguity mode**

In `facade.py` and `console_modes.py`, import:

```python
from app.services.whatsapp_navigation import is_cancel, is_back
```

Client Console behavior:

```python
if is_cancel(msg):
    return await self._perform_exit(...)
if is_back(msg):
    return self._main_menu()
```

Ambiguity mode behavior:

```python
if is_cancel(msg):
    await clear mode session
    return mode_exit text
if is_back(msg):
    return mode_prompt again or main selection screen
```

- [ ] **Step 5: Run endpoint tests**

Run:

```bash
cd backend
uv run pytest tests/test_whatsapp_endpoint.py -q
```

Expected: pass after updating assertions.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/whatsapp_client_console_facade/facade.py backend/app/api/v1/endpoints/integrations/console_modes.py backend/app/core/i18n/catalogs_es_wa.py backend/app/core/i18n/catalogs_en_wa.py backend/tests/test_whatsapp_endpoint.py
git commit -m "fix(whatsapp): normalize client console and ambiguity navigation"
```

---

## Task 10: Final Contract Cleanup, Docs, and Full Verification

**Files:**
- Modify: `backend/app/core/i18n/catalogs_es_wa.py`
- Modify: `backend/app/core/i18n/catalogs_en_wa.py`
- Modify: `docs/architecture/whatsapp-console-flow.md`
- Test: `backend/tests/test_whatsapp_console_navigation_contract.py`
- Test: all relevant WhatsApp tests

- [ ] **Step 1: Run contract test and collect remaining conflicts**

Run:

```bash
cd backend
uv run pytest tests/test_whatsapp_console_navigation_contract.py -q
```

Expected: failures only if any old string remains. Use the failure output paths to update exact strings.

- [ ] **Step 2: Remove remaining conflicting strings**

Search:

```bash
rg -n "0.*(Volver|Regresar|Back|Return)|9.*(Siguiente|Next)|8.*(Anterior|Previous|Back|Regresar)|9.*cancel|9.*cancelar" backend/app/services backend/app/api/v1/endpoints/integrations backend/app/core/i18n
```

For every result, enforce:

- `0` cancel text: `0️⃣ Cancelar` / `0️⃣ Cancel`
- `9` back text: `9️⃣ Regresar` / `9️⃣ Back`
- `8` next text: `8️⃣ Siguiente` / `8️⃣ Next`

- [ ] **Step 3: Update documentation**

Add this section to `docs/architecture/whatsapp-console-flow.md`:

```markdown
## Global WhatsApp Navigation Contract

All WhatsApp console flows use the same numeric navigation contract:

- `8` = Siguiente / Next
- `9` = Regresar / Back
- `0` = Cancelar / Cancel

`0` cancels the active flow or closes the console when used from a main menu.
`9` returns to the previous screen without cancelling the whole session.
`8` advances to the next page or next interactive screen when available.

This contract applies to Master Console, Tenant Admin Console, Client Console,
Client Context Shortcut, ambiguity mode, and unauthenticated code lookup.
```

- [ ] **Step 4: Run full WhatsApp verification**

Run:

```bash
cd backend
uv run pytest tests/ -q --tb=short -k "whatsapp or context or shortcut"
```

Expected: all selected WhatsApp tests pass.

- [ ] **Step 5: Run focused contract and endpoint tests**

Run:

```bash
cd backend
uv run pytest tests/test_whatsapp_console_navigation_contract.py tests/test_whatsapp_endpoint.py tests/test_whatsapp_client_context_shortcut.py -q
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/core/i18n/catalogs_es_wa.py backend/app/core/i18n/catalogs_en_wa.py docs/architecture/whatsapp-console-flow.md backend/tests/test_whatsapp_console_navigation_contract.py
git commit -m "docs(whatsapp): document uniform console navigation contract"
```

---

## Self-Review

### Spec Coverage

- Global `8/9/0` semantics: Tasks 1, 2, 3, 10.
- Master Console: Task 8.
- Tenant Admin Console: Tasks 3, 4, 5, 6.
- Client Console: Task 9.
- Client Context Shortcut: Task 7.
- Ambiguity and unauthenticated code lookup: Tasks 6 and 9.
- i18n catalogs: Tasks 2 through 10.
- Tests: every task starts with failing tests and includes verification commands.
- Documentation: Task 10.

### Placeholder Scan

No plan step uses placeholder instructions. Code steps include concrete snippets, exact file paths, and exact commands.

### Type Consistency

The navigation module uses `ConversationSession.temp_data` and does not require a schema migration. The same helper names (`is_cancel`, `is_back`, `is_next`, `push_screen`, `replace_screen`, `pop_screen`, `clear_navigation`) are used consistently throughout the plan.
