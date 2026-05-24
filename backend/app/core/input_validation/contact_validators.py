"""Contact field validators (email, phone)."""

from __future__ import annotations

import re

import phonenumbers
from email_validator import EmailNotValidError, validate_email as _validate_email_lib

from .errors import InputValidationError
from .phone_utils import _strip_phone_suffixes


def validate_email(value: str | None, *, required: bool = False) -> str | None:
    """Validate and normalize an email address.

    Uses ``email_validator`` for syntax validation and normalization
    with ``check_deliverability=False`` (no DNS, MX, or SMTP checks).
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
        result = _validate_email_lib(value.strip(), check_deliverability=False)
        return result.normalized
    except EmailNotValidError as exc:
        raise InputValidationError(
            field="email",
            message=str(exc),
            code="email_invalid",
        ) from exc


def validate_phone(value: str | None, *, required: bool = False) -> str | None:
    """Validate and normalize a phone number.

    Uses ``phonenumbers`` library for E.164 validation. Accepts input
    with or without leading ``+``. Returns digits-only canonical form
    (no ``+`` prefix) as required for storage and lookup.

    Also strips WhatsApp JID suffixes (``@c.us``, ``@s.whatsapp.net``)
    and device suffixes (``:device``) before validation.
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
    raw = _strip_phone_suffixes(raw)
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
    has_plus = raw.startswith("+")
    digits_part = raw[1:] if has_plus else raw
    if "+" in digits_part:
        raise InputValidationError(
            field="phone",
            message="Phone number contains invalid plus sign placement.",
            code="phone_invalid_plus",
        )
    if re.search(r"\d\s*(?:ext|x|extension|#)\s*\d", digits_part, re.IGNORECASE):
        raise InputValidationError(
            field="phone",
            message="Phone number contains extension or unsupported suffix.",
            code="phone_extension_suffix",
        )
    remaining_junk = re.sub(r"[\d\s\-().]", "", digits_part)
    if remaining_junk:
        raise InputValidationError(
            field="phone",
            message="Phone number contains invalid characters.",
            code="phone_invalid_chars",
        )
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
        e164 = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        return e164.lstrip("+")
    except phonenumbers.NumberParseException as exc:
        raise InputValidationError(
            field="phone",
            message="Phone number could not be parsed.",
            code="phone_parse_error",
        ) from exc
