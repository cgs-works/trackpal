"""Pure mail code extraction catalog and functions."""

from .catalog import CATALOG_V1, get_service_entry
from .extractor import (
    ExtractedCode,
    ExtractedEmail,
    ParsedEmail,
    extract_from_body,
    extract_newest_from_emails,
    extract_newest_with_source,
    match_subject,
    normalize_body,
)
from .types import ExtractionRule, ResultType

__all__ = [
    "CATALOG_V1",
    "ExtractedCode",
    "ExtractedEmail",
    "ExtractionRule",
    "ParsedEmail",
    "ResultType",
    "extract_from_body",
    "extract_newest_from_emails",
    "extract_newest_with_source",
    "get_service_entry",
    "match_subject",
    "normalize_body",
]
