"""Validate and compile private Help Markdown topics."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import yaml

SUPPORTED_LOCALES = ("en", "es")
ARTIFACT_SCHEMA_VERSION = 1
FRONTEND_TARGET_CONTRACT_VERSION = "2"
ALLOWED_AUDIENCES = {"tenant_admin", "client"}
ALLOWED_PLANS = {"starter", "pro"}
ALLOWED_CHANNELS = {"web", "whatsapp"}
ALLOWED_MODULES = {
    "dashboard",
    "clients",
    "catalog",
    "subscriptions",
    "settings",
    "profile",
    "password",
    "whatsapp",
    "help",
    "data",
}
ALLOWED_CAPABILITIES = {
    "tenant_access_code_lookup",
    "tenant_access_control",
    "tenant_catalog",
    "tenant_clients",
    "tenant_code_services",
    "tenant_dashboard",
    "tenant_mailbox",
    "tenant_public_api",
    "tenant_settings",
    "tenant_subscriptions",
    "tenant_whatsapp",
    "tenant_data_export",
    "tenant_delete_account",
    "client_dashboard",
    "client_profile",
    "client_subscriptions",
    "client_password",
    "client_whatsapp",
}
ALLOWED_ROUTES = {
    "/admin/dashboard",
    "/admin/clients",
    "/admin/catalog",
    "/admin/subscriptions",
    "/admin/settings",
    "/admin/help",
    "/client/dashboard",
    "/client/profile",
    "/client/help",
}
ALLOWED_HELP_TARGETS = {
    "admin.dashboard",
    "admin.clients",
    "admin.catalog",
    "admin.subscriptions",
    "admin.settings",
    "admin.settings.language",
    "admin.settings.reminders",
    "admin.settings.timezone",
    "admin.settings.public-api",
    "admin.settings.whatsapp",
    "admin.settings.code-services",
    "admin.settings.mailbox",
    "admin.settings.access-control",
    "admin.settings.profile",
    "admin.settings.password",
    "admin.settings.my-account",
    "admin.settings.data-tab",
    "admin.settings.danger-zone",
    "admin.help",
    "client.dashboard",
    "client.profile",
    "client.subscriptions",
    "client.password",
}
ALLOWED_SETTINGS_CATEGORIES = {
    "access-control",
    "code-services",
    "data",
    "locale",
    "mailbox",
    "password",
    "profile",
    "public-api",
    "reminders",
    "timezone",
    "whatsapp-link",
}
ALLOWED_EXTERNAL_HELP_URLS = {
    "https://myaccount.google.com/apppasswords",
    "https://support.google.com/accounts/answer/185833",
}
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
    "order",
    "safe_navigation",
}
OPTIONAL_FIELDS = {"safe_links", "tour"}
LOCALIZED_FIELDS = {"title", "summary", "search_tags", "synonyms"}
TOUR_RELEASE_PATTERN = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$")
ID_PATTERN = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$")
HTML_PATTERN = re.compile(r"(?is)<\s*(?:/?\s*[a-zA-Z][^>]*|!--|!doctype\b|\?.*?\?)")
EXECUTABLE_PATTERN = re.compile(
    r"(?im)(?:javascript\s*:|data\s*:\s*text/html|\bon[a-z]+\s*=|^\s*(?:import|export)\s+|^\s*[{}])"
)
MARKDOWN_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


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
        tour_releases = self._compile_tour_releases(topics_by_locale)

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
            "schema_version": ARTIFACT_SCHEMA_VERSION,
            "content_version": "help-client-manual-1",
            "frontend_target_contract_version": FRONTEND_TARGET_CONTRACT_VERSION,
            "locales": list(SUPPORTED_LOCALES),
            "topics": topics_by_locale,
            "search": search_by_locale,
            "tour_releases": tour_releases,
        }

    def _compile_topic(self, path: Path, locale: str) -> dict[str, Any]:
        frontmatter, body = _split_frontmatter(path)
        self._validate_frontmatter(frontmatter, path)
        _reject_unsafe_content(body, path)
        _validate_external_help_links(body, path)

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
            "order": _positive_int(frontmatter, "order", path),
            "safe_navigation": _safe_navigation(frontmatter, path),
            "safe_links": _safe_navigation_list(
                frontmatter.get("safe_links", []), path
            ),
            "tour": _tour_entries(
                frontmatter.get("tour"),
                path,
                targets=_string_list(frontmatter, "help_targets", path),
                topic_plans=_string_list(frontmatter, "plans", path),
            ),
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
        audience = _string(frontmatter, "audience", path)
        if audience == "tenant_admin" and not route.startswith("/admin/"):
            raise HelpValidationError(
                f"Tenant Admin topic must use an admin route in {path.name}"
            )
        if audience == "client" and not route.startswith("/client/"):
            raise HelpValidationError(
                f"Client topic must use a client route in {path.name}"
            )
        targets = _string_list(frontmatter, "help_targets", path)
        if (module != "help" and not targets) or any(
            target not in ALLOWED_HELP_TARGETS for target in targets
        ):
            raise HelpValidationError(f"Unknown Help target in {path.name}")
        if audience == "tenant_admin" and any(
            target.startswith("client.") for target in targets
        ):
            raise HelpValidationError(
                f"Tenant Admin topic cannot use a Client target in {path.name}"
            )
        if audience == "client" and any(
            not target.startswith("client.") for target in targets
        ):
            raise HelpValidationError(
                f"Client topic cannot use a Tenant Admin target in {path.name}"
            )
        if audience == "client" and frontmatter.get("tour") is not None:
            raise HelpValidationError(
                f"Client topic cannot declare an orientation tour in {path.name}"
            )
        for navigation in [_safe_navigation(frontmatter, path)] + _safe_navigation_list(
            frontmatter.get("safe_links", []), path
        ):
            navigation_route = navigation["route"]
            if audience == "tenant_admin" and not navigation_route.startswith(
                "/admin/"
            ):
                raise HelpValidationError(
                    f"Tenant Admin topic cannot navigate to a Client route in {path.name}"
                )
            if audience == "client" and not navigation_route.startswith("/client/"):
                raise HelpValidationError(
                    f"Client topic cannot navigate to a Tenant Admin route in {path.name}"
                )
        _positive_int(frontmatter, "order", path)
        _safe_navigation(frontmatter, path)
        _safe_navigation_list(frontmatter.get("safe_links", []), path)
        for field in ("title", "summary"):
            if not _string(frontmatter, field, path).strip():
                raise HelpValidationError(f"Empty {field} in {path.name}")
        for field in ("search_tags", "synonyms", "related_topics"):
            _string_list(frontmatter, field, path)
        for value in _iter_strings(frontmatter):
            _reject_unsafe_content(value, path)

        _tour_entries(
            frontmatter.get("tour"),
            path,
            targets=targets,
            topic_plans=plans,
        )

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
            if english_topic["safe_links"] != spanish_topic["safe_links"]:
                raise HelpValidationError(
                    f"Topic metadata parity mismatch for {topic_id}: safe_links"
                )
            if _tour_contract(english_topic["tour"]) != _tour_contract(
                spanish_topic["tour"]
            ):
                raise HelpValidationError(
                    f"Topic metadata parity mismatch for {topic_id}: tour"
                )
            english_links = _absolute_link_destinations(english_topic["body"])
            spanish_links = _absolute_link_destinations(spanish_topic["body"])
            if english_links != spanish_links:
                raise HelpValidationError(
                    f"External URL parity mismatch for {topic_id}"
                )

    def _compile_tour_releases(
        self, topics_by_locale: dict[str, list[dict[str, Any]]]
    ) -> dict[str, list[dict[str, Any]]]:
        releases_by_locale: dict[str, list[dict[str, Any]]] = {}
        for locale, topics in topics_by_locale.items():
            releases: dict[str, list[dict[str, Any]]] = {}
            for topic in topics:
                for tour in topic["tour"] or []:
                    releases.setdefault(tour["release_id"], []).append(
                        {
                            "topic_id": topic["id"],
                            "related_topics": topic["related_topics"],
                            "title": tour.get("title", topic["title"]),
                            "content": tour.get("content", topic["body"]),
                            "summary": topic["summary"],
                            "route": topic["route"],
                            "settings_category": topic["safe_navigation"][
                                "settings_category"
                            ],
                            "target": tour["target"],
                            "conditional": tour.get("conditional", False),
                            "order": tour["order"],
                            "plans": tour["plans"],
                        }
                    )
            releases_by_locale[locale] = []
            for release_id, steps in sorted(releases.items()):
                steps.sort(key=lambda step: (step["order"], step["topic_id"]))
                if len(steps) > 7 or len({step["order"] for step in steps}) != len(
                    steps
                ):
                    raise HelpValidationError(
                        f"Tour release {release_id} must have 1-7 unique ordered steps"
                    )
                if [step["order"] for step in steps] != list(range(1, len(steps) + 1)):
                    raise HelpValidationError(
                        f"Tour release {release_id} steps must be ordered from 1"
                    )
                plans = sorted({plan for step in steps for plan in step["plans"]})
                releases_by_locale[locale].append(
                    {"release_id": release_id, "plans": plans, "steps": steps}
                )
        english = [release["release_id"] for release in releases_by_locale["en"]]
        spanish = [release["release_id"] for release in releases_by_locale["es"]]
        if english != spanish:
            raise HelpValidationError(
                "English and Spanish tour releases must have parity"
            )
        return releases_by_locale

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

    artifact = HelpCompiler(source_dir).compile()
    validate_artifact(artifact)
    return artifact


def validate_artifact(
    artifact: dict[str, Any], *, allow_target_contract_mismatch: bool = False
) -> None:
    """Validate the versioned artifact contract before it can be published."""

    if not isinstance(artifact, dict):
        raise HelpValidationError("Help artifact must be a mapping")
    if artifact.get("schema_version") != ARTIFACT_SCHEMA_VERSION:
        raise HelpValidationError(
            "Incompatible Help artifact schema version: "
            f"{artifact.get('schema_version')!r}"
        )
    if (
        not allow_target_contract_mismatch
        and artifact.get("frontend_target_contract_version")
        != FRONTEND_TARGET_CONTRACT_VERSION
    ):
        raise HelpValidationError(
            "Incompatible Help frontend target contract version: "
            f"{artifact.get('frontend_target_contract_version')!r}"
        )
    if not isinstance(artifact.get("frontend_target_contract_version"), str):
        raise HelpValidationError("Help artifact target contract version is missing")
    if set(artifact.get("locales", [])) != set(SUPPORTED_LOCALES):
        raise HelpValidationError(
            "Help artifact locales do not match the supported locales"
        )
    for key in ("content_version", "topics", "search", "tour_releases"):
        if key not in artifact:
            raise HelpValidationError(f"Help artifact is missing {key}")
    for locale in SUPPORTED_LOCALES:
        for key in ("topics", "search", "tour_releases"):
            if locale not in artifact[key]:
                raise HelpValidationError(
                    f"Help artifact is missing {locale} {key} data"
                )


def _absolute_link_destinations(body: str) -> set[str]:
    """Extract absolute link destinations from Markdown body."""
    return {
        destination
        for _, destination in MARKDOWN_LINK_PATTERN.findall(body)
        if urlsplit(destination).scheme or urlsplit(destination).netloc
    }


def _validate_external_help_links(body: str, path: Path) -> None:
    """Validate that external links use HTTPS and exact allowed URLs."""
    for destination in _absolute_link_destinations(body):
        parsed = urlsplit(destination)
        if parsed.scheme != "https":
            raise HelpValidationError(
                f"External Help URL must use HTTPS in {path.name}"
            )
        if destination not in ALLOWED_EXTERNAL_HELP_URLS:
            raise HelpValidationError(
                f"External Help URL not on allow-list in {path.name}"
            )


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


def _positive_int(frontmatter: dict[str, Any], field: str, path: Path) -> int:
    value = frontmatter.get(field)
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise HelpValidationError(
            f"Frontmatter field {field} must be a positive integer in {path.name}"
        )
    return value


def _tour_entries(
    value: Any,
    path: Path,
    *,
    targets: list[str] | None = None,
    topic_plans: list[str] | None = None,
) -> list[dict[str, Any]] | None:
    if value is None:
        return None
    entries = [value] if isinstance(value, dict) else value
    if not isinstance(entries, list) or not entries:
        raise HelpValidationError(f"Invalid tour metadata in {path.name}")

    validated: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise HelpValidationError(f"Invalid tour metadata in {path.name}")
        unknown = set(entry) - {
            "release_id",
            "order",
            "target",
            "conditional",
            "plans",
            "title",
            "content",
        }
        if unknown:
            raise HelpValidationError(f"Unknown tour fields in {path.name}")

        release_id = entry.get("release_id")
        order = entry.get("order")
        target = entry.get("target")
        conditional = entry.get("conditional", False)
        title = entry.get("title")
        content = entry.get("content")
        tour_plans = entry.get("plans", topic_plans)
        if (
            not isinstance(release_id, str)
            or not TOUR_RELEASE_PATTERN.fullmatch(release_id)
            or not isinstance(order, int)
            or isinstance(order, bool)
            or order < 1
            or not isinstance(target, str)
            or (targets is not None and target not in targets)
            or not isinstance(conditional, bool)
            or not isinstance(tour_plans, list)
            or not tour_plans
            or any(plan not in ALLOWED_PLANS for plan in tour_plans)
            or (
                topic_plans is not None
                and any(plan not in topic_plans for plan in tour_plans)
            )
            or (title is not None and (not isinstance(title, str) or not title.strip()))
            or (
                content is not None
                and (not isinstance(content, str) or not content.strip())
            )
        ):
            raise HelpValidationError(f"Incomplete tour metadata in {path.name}")
        validated.append(
            {
                "release_id": release_id,
                "order": order,
                "target": target,
                "conditional": conditional,
                "plans": tour_plans,
                **({"title": title} if title is not None else {}),
                **({"content": content} if content is not None else {}),
            }
        )
    return validated


def _tour_contract(value: list[dict[str, Any]] | None) -> list[dict[str, Any]] | None:
    if value is None:
        return None
    return [
        {
            key: entry[key]
            for key in ("release_id", "order", "target", "conditional", "plans")
        }
        for entry in value
    ]


def _safe_navigation(frontmatter: dict[str, Any], path: Path) -> dict[str, str | None]:
    value = frontmatter.get("safe_navigation")
    declared_route = _string(frontmatter, "route", path)
    return _validate_safe_navigation(value, path, declared_route=declared_route)


def _safe_navigation_list(value: Any, path: Path) -> list[dict[str, str | None]]:
    if not isinstance(value, list):
        raise HelpValidationError(f"Safe links must be a list in {path.name}")
    return [_validate_safe_navigation(item, path) for item in value]


def _validate_safe_navigation(
    value: Any, path: Path, *, declared_route: str | None = None
) -> dict[str, str | None]:
    if not isinstance(value, dict) or set(value) - {"route", "settings_category"}:
        raise HelpValidationError(f"Invalid safe navigation in {path.name}")

    route = value.get("route")
    if not isinstance(route, str) or route not in ALLOWED_ROUTES:
        raise HelpValidationError(f"Unknown safe navigation route in {path.name}")
    if declared_route is not None and route != declared_route:
        raise HelpValidationError(
            f"Safe navigation route must match route in {path.name}"
        )

    settings_category = value.get("settings_category")
    if settings_category is not None and (
        route != "/admin/settings"
        or not isinstance(settings_category, str)
        or settings_category not in ALLOWED_SETTINGS_CATEGORIES
    ):
        raise HelpValidationError(f"Unknown settings category in {path.name}")
    return {"route": route, "settings_category": settings_category}


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
