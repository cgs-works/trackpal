"""Per-message locale context variable for the Tenant Console."""

from __future__ import annotations

import contextvars

_current_locale: contextvars.ContextVar[str] = contextvars.ContextVar("wa_locale", default="es")


def set_locale(locale: str) -> contextvars.Token[str]:
    """Set locale for current message context."""
    return _current_locale.set(locale)


def reset_locale(token: contextvars.Token[str]) -> None:
    """Reset locale context."""
    _current_locale.reset(token)


def get_locale() -> str:
    """Get current message locale."""
    return _current_locale.get()
