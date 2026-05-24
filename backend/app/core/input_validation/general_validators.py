"""General identity field validators (username, name, prefix, password)."""

from __future__ import annotations

import re
import unicodedata

from .errors import InputValidationError


def validate_username(value: str) -> str:
    """Validate and normalize a username.

    Rules:
    * Required, non-empty string.
    * Maximum 20 characters.
    * Must start with a lowercase ASCII letter (``a``-``z``).
    * Remaining characters: lowercase ASCII letters (``a``-``z``),
      digits (``0``-``9``), underscore (``_``).
    * No uppercase, spaces, punctuation, or special characters.
    """
    if not value or not isinstance(value, str) or not value.strip():
        raise InputValidationError(
            field="username",
            message="Username is required.",
            code="username_required",
        )
    stripped = value.strip()
    if value != stripped:
        raise InputValidationError(
            field="username",
            message="Username must not start or end with spaces.",
            code="username_leading_trailing_spaces",
        )
    if len(stripped) > 20:
        raise InputValidationError(
            field="username",
            message="Username must be at most 20 characters.",
            code="username_too_long",
        )
    if not re.match(r"^[a-z][a-z0-9_]*$", stripped):
        raise InputValidationError(
            field="username",
            message="Username must start with a lowercase letter and contain only "
            "lowercase letters, digits, and underscores.",
            code="username_invalid",
        )
    return stripped


def validate_client_prefix(value: str) -> str:
    """Validate and normalize tenant client prefix.

    Rules:
    * Required, non-empty string.
    * Trim and lowercase.
    * 1-5 characters.
    * Lowercase ASCII letters and digits only.
    * Must start with a lowercase ASCII letter to keep technical usernames valid.
    """
    if not value or not isinstance(value, str) or not value.strip():
        raise InputValidationError(
            field="client_prefix",
            message="Client prefix is required.",
            code="client_prefix_required",
        )
    stripped = value.strip().lower()
    if len(stripped) > 5:
        raise InputValidationError(
            field="client_prefix",
            message="Client prefix must be at most 5 characters.",
            code="client_prefix_too_long",
        )
    if not re.match(r"^[a-z][a-z0-9]{0,4}$", stripped):
        raise InputValidationError(
            field="client_prefix",
            message=(
                "Client prefix must start with a lowercase letter and contain only "
                "lowercase letters and digits."
            ),
            code="client_prefix_invalid",
        )
    return stripped


def validate_client_local_username(value: str) -> str:
    """Validate tenant-local client username.

    Mirrors standard username rules but allows a longer local part so the
    technical username ``<client_prefix>_<local_username>`` stays within
    ``users.username`` length limits.
    """
    if not value or not isinstance(value, str) or not value.strip():
        raise InputValidationError(
            field="local_username",
            message="Client local username is required.",
            code="client_local_username_required",
        )
    stripped = value.strip()
    if value != stripped:
        raise InputValidationError(
            field="local_username",
            message="Client local username must not start or end with spaces.",
            code="client_local_username_leading_trailing_spaces",
        )
    if len(stripped) > 94:
        raise InputValidationError(
            field="local_username",
            message="Client local username must be at most 94 characters.",
            code="client_local_username_too_long",
        )
    if not re.match(r"^[a-z][a-z0-9_]*$", stripped):
        raise InputValidationError(
            field="local_username",
            message="Client local username must start with a lowercase letter and contain "
            "only lowercase letters, digits, and underscores.",
            code="client_local_username_invalid",
        )
    return stripped


def validate_password_policy(value: str) -> str:
    """Validate password policy minimums."""
    if not value or not isinstance(value, str):
        raise InputValidationError(
            field="password",
            message="Password is required.",
            code="password_required",
        )
    if len(value) < 6:
        raise InputValidationError(
            field="password",
            message="Password must be at least 6 characters.",
            code="password_too_short",
        )
    return value


def validate_full_name(value: str) -> str:
    """Validate and normalize a full name.

    Rules:
    * Required, non-empty string (after stripping).
    * Reject leading/trailing whitespace.
    * Allow only Unicode letters, digits, and spaces.
    * Reject punctuation, slashes, and other special characters.
    * Collapse multiple internal spaces to one in the returned value.
    """
    if not value or not isinstance(value, str):
        raise InputValidationError(
            field="full_name",
            message="Full name is required.",
            code="full_name_required",
        )
    stripped = value.strip()
    if not stripped:
        raise InputValidationError(
            field="full_name",
            message="Full name is required.",
            code="full_name_required",
        )
    if value != stripped:
        raise InputValidationError(
            field="full_name",
            message="Full name must not start or end with spaces.",
            code="full_name_leading_trailing_spaces",
        )
    for ch in stripped:
        cat = unicodedata.category(ch)
        if cat.startswith("L") or cat.startswith("N") or ch == " ":
            continue
        raise InputValidationError(
            field="full_name",
            message="Full name may only contain letters, numbers, and spaces.",
            code="full_name_invalid_chars",
        )
    normalized = re.sub(r" {2,}", " ", stripped)
    return normalized
