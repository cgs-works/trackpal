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
    params = (
        {str(key): str(value) for key, value in params_raw.items() if value is not None}
        if isinstance(params_raw, dict)
        else {}
    )
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
        return None
    stack = list(state.stack)
    previous = stack.pop()
    save_navigation(session, ConsoleNavigationState(current=previous, stack=stack))
    return previous


def clear_navigation(session: Any) -> None:
    if hasattr(session, "temp_data") and isinstance(session.temp_data, dict):
        session.temp_data.pop(_NAV_TEMP_KEY, None)
