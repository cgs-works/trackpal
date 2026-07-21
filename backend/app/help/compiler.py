"""Validate and compile private Help Markdown topics."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import yaml

SUPPORTED_LOCALES = ("en", "es")
ALLOWED_AUDIENCES = {"tenant_admin", "client"}
ALLOWED_PLANS = {"starter", "pro"}
ALLOWED_CHANNELS = {"web", "whatsapp"}
ALLOWED_MODULES = {
    "dashboard",
    "clients",
    "catalog",
    "subscriptions",
    "settings",
    "help",
}
ALLOWED_CAPABILITIES = {"tenant_dashboard"}
ALLOWED_ROUTES = {"/admin/dashboard"}
ALLOWED_HELP_TARGETS = {"admin.dashboard"}
REQUIRED_FIELDS = {
    "id",
    "audience",
    "plans",
    "channels",
    "module",
    "capabilities",
    "route",
    "help_targets",
    "title",
    "summary",
    "search_tags",
    "synonyms",
    "related_topics",
}
OPTIONAL_FIELDS = {"tour"}
LOCALIZED_FIELDS = {"title", "summary", "search_tags", "synonyms"}
ID_PATTERN = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$")
HTML_PATTERN = re.compile(r"(?is)<\s*(?:/?\s*[a-zA-Z][^>]*|!--|!doctype\b|\?.*?\?)")
EXECUTABLE_PATTERN = re.compile(
    r"(?im)(?:javascript\s*:|data\s*:\s*text/html|\bon[a-z]+\s*=|^\s*(?:import|export)\s+|^\s*[{}])"
)


class HelpValidationError(ValueError):
    """Raised when a Help topic violates the authoring contract."""


class HelpCompiler:
    """Compile mirrored Markdown topics into a deterministic private artifact."""

    def __init__(self, source_dir: Path) -> None:
        self.source_dir = source_dir

    def compile(self) -> dict[str, Any]:
        topics_by_locale: dict[str, list[dict[str, Any]]] = {}
        ids_by_locale: dict[str, set[str]] = {}
        locale_dirs = {path.name for path in self.source_dir.iterdir() if path.is_dir()}
        unknown_locales = locale_dirs - set(SUPPORTED_LOCALES)
        if unknown_locales:
            raise HelpValidationError(
                f"Unknown Help locales: {sorted(unknown_locales)}"
            )

        for locale in SUPPORTED_LOCALES:
            locale_dir = self.source_dir / locale
            if not locale_dir.is_dir():
                raise HelpValidationError(f"Missing locale directory: {locale}")
            paths = sorted(locale_dir.rglob("*.md"))
            if not paths:
                raise HelpValidationError(f"Locale has no Markdown topics: {locale}")

            ids: set[str] = set()
            topics: list[dict[str, Any]] = []
            for path in paths:
                topic = self._compile_topic(path, locale)
                topic_id = topic["id"]
                if topic_id in ids:
                    raise HelpValidationError(f"Duplicate topic id: {topic_id}")
                ids.add(topic_id)
                topics.append(topic)
            topics_by_locale[locale] = sorted(topics, key=lambda topic: topic["id"])
            ids_by_locale[locale] = ids

        if ids_by_locale["en"] != ids_by_locale["es"]:
            raise HelpValidationError("English and Spanish topic IDs must have parity")

        self._validate_metadata_parity(topics_by_locale)
        self._validate_related_topics(topics_by_locale)

        search_by_locale = {
            locale: [
                {
                    "id": topic["id"],
                    "title": topic["title"],
                    "terms": [
                        topic["title"],
                        topic["summary"],
                        *topic["search_tags"],
                        *topic["synonyms"],
                        topic["body"],
                    ],
                }
                for topic in topics
            ]
            for locale, topics in topics_by_locale.items()
        }
        return {
            "schema_version": 1,
            "content_version": "help-tracer-1",
            "frontend_target_contract_version": "1",
            "locales": list(SUPPORTED_LOCALES),
            "topics": topics_by_locale,
            "search": search_by_locale,
        }

    def _compile_topic(self, path: Path, locale: str) -> dict[str, Any]:
        frontmatter, body = _split_frontmatter(path)
        self._validate_frontmatter(frontmatter, path)
        _reject_unsafe_content(body, path)

        topic_id = _string(frontmatter, "id", path)
        return {
            "id": topic_id,
            "locale": locale,
            "audience": _string(frontmatter, "audience", path),
            "plans": _string_list(frontmatter, "plans", path),
            "channels": _string_list(frontmatter, "channels", path),
            "module": _string(frontmatter, "module", path),
            "capabilities": _string_list(frontmatter, "capabilities", path),
            "route": _string(frontmatter, "route", path),
            "help_targets": _string_list(frontmatter, "help_targets", path),
            "title": _string(frontmatter, "title", path),
            "summary": _string(frontmatter, "summary", path),
            "search_tags": _string_list(frontmatter, "search_tags", path),
            "synonyms": _string_list(frontmatter, "synonyms", path),
            "related_topics": _string_list(frontmatter, "related_topics", path),
            "tour": frontmatter.get("tour"),
            "body": body.strip(),
        }

    def _validate_frontmatter(self, frontmatter: dict[str, Any], path: Path) -> None:
        keys = set(frontmatter)
        unknown = keys - REQUIRED_FIELDS - OPTIONAL_FIELDS
        missing = REQUIRED_FIELDS - keys
        if unknown:
            raise HelpValidationError(
                f"Unknown frontmatter fields in {path.name}: {sorted(unknown)}"
            )
        if missing:
            raise HelpValidationError(
                f"Missing frontmatter fields in {path.name}: {sorted(missing)}"
            )

        topic_id = _string(frontmatter, "id", path)
        if not ID_PATTERN.fullmatch(topic_id):
            raise HelpValidationError(f"Invalid topic id in {path.name}: {topic_id}")
        if _string(frontmatter, "audience", path) not in ALLOWED_AUDIENCES:
            raise HelpValidationError(f"Unknown audience in {path.name}")
        plans = _string_list(frontmatter, "plans", path)
        if not plans or any(plan not in ALLOWED_PLANS for plan in plans):
            raise HelpValidationError(f"Unknown plan in {path.name}")
        channels = _string_list(frontmatter, "channels", path)
        if not channels or any(channel not in ALLOWED_CHANNELS for channel in channels):
            raise HelpValidationError(f"Unknown channel in {path.name}")
        module = _string(frontmatter, "module", path)
        if module not in ALLOWED_MODULES:
            raise HelpValidationError(f"Unknown module in {path.name}")
        capabilities = _string_list(frontmatter, "capabilities", path)
        if not capabilities or any(
            capability not in ALLOWED_CAPABILITIES for capability in capabilities
        ):
            raise HelpValidationError(f"Unknown capability in {path.name}")
        route = _string(frontmatter, "route", path)
        if route not in ALLOWED_ROUTES:
            raise HelpValidationError(f"Unknown route in {path.name}: {route}")
        targets = _string_list(frontmatter, "help_targets", path)
        if not targets or any(target not in ALLOWED_HELP_TARGETS for target in targets):
            raise HelpValidationError(f"Unknown Help target in {path.name}")
        for field in ("title", "summary"):
            if not _string(frontmatter, field, path).strip():
                raise HelpValidationError(f"Empty {field} in {path.name}")
        for field in ("search_tags", "synonyms", "related_topics"):
            _string_list(frontmatter, field, path)
        for value in _iter_strings(frontmatter):
            _reject_unsafe_content(value, path)

        tour = frontmatter.get("tour")
        if tour is None:
            return
        if not isinstance(tour, dict):
            raise HelpValidationError(f"Invalid tour metadata in {path.name}")
        unknown_tour_fields = set(tour) - {
            "release_id",
            "order",
            "target",
            "conditional",
        }
        if unknown_tour_fields:
            raise HelpValidationError(f"Unknown tour fields in {path.name}")
        if not isinstance(tour.get("release_id"), str) or not isinstance(
            tour.get("order"), int
        ):
            raise HelpValidationError(f"Incomplete tour metadata in {path.name}")

    def _validate_metadata_parity(
        self, topics_by_locale: dict[str, list[dict[str, Any]]]
    ) -> None:
        english = {topic["id"]: topic for topic in topics_by_locale["en"]}
        spanish = {topic["id"]: topic for topic in topics_by_locale["es"]}
        for topic_id, english_topic in english.items():
            spanish_topic = spanish[topic_id]
            for field in REQUIRED_FIELDS - LOCALIZED_FIELDS:
                if english_topic[field] != spanish_topic[field]:
                    raise HelpValidationError(
                        f"Topic metadata parity mismatch for {topic_id}: {field}"
                    )
            if english_topic["tour"] != spanish_topic["tour"]:
                raise HelpValidationError(
                    f"Topic metadata parity mismatch for {topic_id}: tour"
                )

    def _validate_related_topics(
        self, topics_by_locale: dict[str, list[dict[str, Any]]]
    ) -> None:
        known_ids = {topic["id"] for topic in topics_by_locale["en"]}
        for topics in topics_by_locale.values():
            for topic in topics:
                unknown = set(topic["related_topics"]) - known_ids
                if unknown:
                    raise HelpValidationError(
                        f"Unknown related topic in {topic['id']}: {sorted(unknown)}"
                    )


def compile_help(source_dir: Path) -> dict[str, Any]:
    """Compile the Help source directory into a JSON-serializable artifact."""

    return HelpCompiler(source_dir).compile()


def _split_frontmatter(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise HelpValidationError(f"Missing frontmatter in {path.name}")
    try:
        closing_index = lines.index("---", 1)
    except ValueError as exc:
        raise HelpValidationError(f"Unclosed frontmatter in {path.name}") from exc
    raw_frontmatter = "\n".join(lines[1:closing_index])
    try:
        parsed = yaml.safe_load(raw_frontmatter)
    except yaml.YAMLError as exc:
        raise HelpValidationError(f"Invalid frontmatter in {path.name}") from exc
    if not isinstance(parsed, dict):
        raise HelpValidationError(f"Frontmatter must be a mapping in {path.name}")
    body = "\n".join(lines[closing_index + 1 :])
    if not body.strip():
        raise HelpValidationError(f"Empty Markdown body in {path.name}")
    return parsed, body


def _string(frontmatter: dict[str, Any], field: str, path: Path) -> str:
    value = frontmatter.get(field)
    if not isinstance(value, str):
        raise HelpValidationError(
            f"Frontmatter field {field} must be a string in {path.name}"
        )
    return value


def _string_list(frontmatter: dict[str, Any], field: str, path: Path) -> list[str]:
    value = frontmatter.get(field)
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise HelpValidationError(
            f"Frontmatter field {field} must be a string list in {path.name}"
        )
    return value


def _iter_strings(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for nested in value.values():
            yield from _iter_strings(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _iter_strings(nested)


def _reject_unsafe_content(value: str, path: Path) -> None:
    if HTML_PATTERN.search(value) or EXECUTABLE_PATTERN.search(value):
        raise HelpValidationError(f"Unsafe Markdown content in {path.name}")


def write_artifact(artifact: dict[str, Any], destination: Path) -> None:
    """Write an artifact with stable formatting for source control."""

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
