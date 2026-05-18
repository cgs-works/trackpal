"""Centralized input validation policy for sensitive identity/contact fields.

This module is the single source of truth for field validation and
normalization rules used by API schemas, services, and WhatsApp flows.
"""

from __future__ import annotations

import re
import unicodedata

import phonenumbers
from email_validator import EmailNotValidError, validate_email as _validate_email_lib


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


def validate_username(value: str) -> str:
    """Validate and normalize a username.

    Rules:

    * Required, non-empty string.
    * Maximum 20 characters.
    * Must start with a lowercase ASCII letter (``a``-``z``).
    * Remaining characters: lowercase ASCII letters (``a``-``z``),
      digits (``0``-``9``), underscore (``_``).
    * No uppercase, spaces, punctuation, or special characters.

    Returns:
        The validated username (unchanged if valid).

    Raises:
        InputValidationError: If the value does not meet the rules.
    """
    if not value or not isinstance(value, str) or not value.strip():
        raise InputValidationError(
            field="username",
            message="Username is required.",
            code="username_required",
        )

    stripped = value.strip()

    # Reject leading or trailing whitespace (must not silently strip)
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
            message="Client local username must start with a lowercase letter and contain only lowercase letters, digits, and underscores.",
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

    Returns:
        Normalized full name with internal spaces collapsed.

    Raises:
        InputValidationError: If the value does not meet the rules.
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

    # Reject leading/trailing whitespace
    if value != stripped:
        raise InputValidationError(
            field="full_name",
            message="Full name must not start or end with spaces.",
            code="full_name_leading_trailing_spaces",
        )

    # Allow only Unicode letters (L*), digits (N*), and spaces
    for ch in stripped:
        cat = unicodedata.category(ch)
        if cat.startswith("L") or cat.startswith("N") or ch == " ":
            continue
        raise InputValidationError(
            field="full_name",
            message="Full name may only contain letters, numbers, and spaces.",
            code="full_name_invalid_chars",
        )

    # Collapse multiple internal spaces to one
    normalized = re.sub(r" {2,}", " ", stripped)

    return normalized


def validate_email(
    value: str | None, *, required: bool = False
) -> str | None:
    """Validate and normalize an email address.

    Uses ``email_validator`` for syntax validation and normalization
    with ``check_deliverability=False`` (no DNS, MX, or SMTP checks).

    Args:
        value: The email string to validate, or ``None``.
        required: If ``True``, ``None``/empty raises an error.
            If ``False``, ``None`` is returned as-is (optional field).

    Returns:
        Normalized email string, or ``None`` for optional empty input.

    Raises:
        InputValidationError: If validation fails.
    """
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            raise InputValidationError(
                field="email",
                message="Email is required.",
                code="email_required",
            )
        return None

    try:
        result = _validate_email_lib(
            value.strip(),
            check_deliverability=False,
        )
        return result.normalized
    except EmailNotValidError as exc:
        raise InputValidationError(
            field="email",
            message=str(exc),
            code="email_invalid",
        ) from exc


def _strip_phone_suffixes(raw: str) -> str:
    """Strip WhatsApp JID suffix and device suffix from a phone string.

    Handles:

    * WhatsApp JID suffixes (``@c.us``, ``@s.whatsapp.net``)
    * Device suffixes after ``:``

    Args:
        raw: Raw phone string potentially containing suffixes.

    Returns:
        Clean phone string with suffixes removed.
    """
    if "@" in raw:
        raw = raw.split("@", 1)[0]
    if ":" in raw:
        raw = raw.split(":", 1)[0]
    return raw


def validate_phone(
    value: str | None, *, required: bool = False
) -> str | None:
    """Validate and normalize a phone number.

    Uses ``phonenumbers`` library for E.164 validation. Accepts input
    with or without leading ``+``. Returns digits-only canonical form
    (no ``+`` prefix) as required for storage and lookup.

    Also strips WhatsApp JID suffixes (``@c.us``, ``@s.whatsapp.net``)
    and device suffixes (``:device``) before validation, preserving
    existing JID cleanup behaviour.

    Args:
        value: The phone string to validate, or ``None``.
        required: If ``True``, ``None``/empty raises an error.
            If ``False``, ``None`` is returned as-is (optional field).

    Returns:
        Canonical digits-only phone string, or ``None`` for optional
        empty input.

    Raises:
        InputValidationError: If validation fails.
    """
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            raise InputValidationError(
                field="phone",
                message="Phone is required.",
                code="phone_required",
            )
        return None

    raw = value.strip()

    # Strip WhatsApp JID suffix and device suffix (same as normalize_phone)
    raw = _strip_phone_suffixes(raw)

    # After stripping suffixes, treat empty same as blank/None
    if not raw or not raw.strip():
        if required:
            raise InputValidationError(
                field="phone",
                message="Phone is required.",
                code="phone_required",
            )
        return None

    if not re.search(r"\d", raw):
        raise InputValidationError(
            field="phone",
            message="Phone must contain at least one digit.",
            code="phone_no_digits",
        )

    # Reject noisy/non-E.164 inputs before phonenumbers parsing

    # Check plus sign: must be exactly zero or one, at the start only
    has_plus = raw.startswith("+")
    digits_part = raw[1:] if has_plus else raw
    if "+" in digits_part:
        raise InputValidationError(
            field="phone",
            message="Phone number contains invalid plus sign placement.",
            code="phone_invalid_plus",
        )

    # Reject common extension patterns: ext, x, extension, # followed by digits
    if re.search(r"\d\s*(?:ext|x|extension|#)\s*\d", digits_part, re.IGNORECASE):
        raise InputValidationError(
            field="phone",
            message="Phone number contains extension or unsupported suffix.",
            code="phone_extension_suffix",
        )

    # Reject characters that are not valid in phone formatting
    # Allow: digits, spaces, dashes, parens, dots, plus (already validated as first char)
    remaining_junk = re.sub(r"[\d\s\-().]", "", digits_part)
    if remaining_junk:
        raise InputValidationError(
            field="phone",
            message="Phone number contains invalid characters.",
            code="phone_invalid_chars",
        )

    # Add + if not present for phonenumbers E.164 parsing
    if not has_plus:
        raw = "+" + raw

    try:
        parsed = phonenumbers.parse(raw, None)
        if not phonenumbers.is_valid_number(parsed):
            raise InputValidationError(
                field="phone",
                message="Phone number is not a valid international number.",
                code="phone_invalid",
            )
        # Return digits-only (E164 without +)
        e164 = phonenumbers.format_number(
            parsed, phonenumbers.PhoneNumberFormat.E164
        )
        return e164.lstrip("+")
    except phonenumbers.NumberParseException as exc:
        raise InputValidationError(
            field="phone",
            message="Phone number could not be parsed.",
            code="phone_parse_error",
        ) from exc
