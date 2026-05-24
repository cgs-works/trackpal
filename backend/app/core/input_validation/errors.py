"""Input validation error type."""

from __future__ import annotations


class InputValidationError(ValueError):
    """Raised when a field value fails validation.

    Attributes:
        field: The name of the field that failed validation.
        message: Human-readable error description.
        code: Machine-readable error code for programmatic handling.
    """

    def __init__(self, field: str, message: str, code: str) -> None:
        self.field = field
        self.message = message
        self.code = code
        super().__init__(message)
