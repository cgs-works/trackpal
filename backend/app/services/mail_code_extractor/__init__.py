"""Mail code extraction — versioned regex catalog + pure extractor."""

from ._types import ExtractionRule, ResultType
from .catalog_v1 import CATALOG_V1, get_service_entry
from .extractor import (
    ExtractedCode,
    ParsedEmail,
    extract_from_body,
    extract_newest_from_emails,
    match_subject,
    normalize_body,
)

__all__ = [
    "CATALOG_V1",
    "ExtractedCode",
    "ExtractionRule",
    "ParsedEmail",
    "ResultType",
    "extract_from_body",
    "extract_newest_from_emails",
    "get_service_entry",
    "match_subject",
    "normalize_body",
]
