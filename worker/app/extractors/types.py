"""Type definitions for the mail code extraction catalog."""

from typing import Literal, TypedDict

ResultType = Literal["code", "url"]


class ExtractionRule(TypedDict):
    """Single extraction pattern."""

    regex: str
    type: ResultType
    desc: str


class ServiceEntry(TypedDict):
    """Catalog entry for one streaming service."""

    service_name: str
    subject_patterns: list[str]
    extraction_rules: list[ExtractionRule]
