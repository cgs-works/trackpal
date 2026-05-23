"""User-facing error contract for i18n-aware service exceptions."""

from __future__ import annotations

from typing import Any


class UserFacingError(ValueError):
    """Error raised by services for user-facing messages.

    Subclasses ``ValueError`` so existing ``except ValueError`` handlers
    in WhatsApp console still catch it without crashing (Phase 3 will
    explicitly handle ``UserFacingError``).
    """

    def __init__(self, code: str, *, params: dict[str, Any] | None = None) -> None:
        self.code = code
        self.params = params or {}
        super().__init__(code)


def translate_error(locale: str, err: UserFacingError) -> str:
    """Translate a ``UserFacingError`` into a localized message string.

    Wraps ``app.core.i18n.t()`` using the error's code as the catalog key.
    """
    from app.core.i18n import t

    return t(locale, f"errors.{err.code}", **err.params)
