"""Centralized input validation policy for sensitive identity/contact fields.

This module is the single source of truth for field validation and
normalization rules used by API schemas, services, and WhatsApp flows.
"""

from .contact_validators import validate_email, validate_phone
from .errors import InputValidationError
from .general_validators import (
    validate_client_local_username,
    validate_client_prefix,
    validate_full_name,
    validate_password_policy,
    validate_username,
)
from .phone_utils import _strip_phone_suffixes

__all__ = [
    "InputValidationError",
    "validate_client_local_username",
    "validate_client_prefix",
    "validate_email",
    "validate_full_name",
    "validate_password_policy",
    "validate_phone",
    "validate_username",
    "_strip_phone_suffixes",
]
