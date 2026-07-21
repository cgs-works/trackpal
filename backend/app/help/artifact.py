"""Access to the generated private Help artifact."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

ARTIFACT_PATH = Path(__file__).with_name("artifact.json")


class HelpCatalog:
    """Filter compiled Help content for an authorized Help audience."""

    def __init__(self, artifact: dict[str, Any]) -> None:
        self.artifact = artifact

    def index(
        self, locale: str, plan: str, audience: str = "tenant_admin"
    ) -> dict[str, Any]:
        return {
            "schema_version": self.artifact["schema_version"],
            "content_version": self.artifact["content_version"],
            "frontend_target_contract_version": self.artifact[
                "frontend_target_contract_version"
            ],
            "locale": locale,
            "topics": [
                _public_topic(topic)
                for topic in self._authorized_topics(locale, plan, audience)
            ],
        }

    def topic(
        self,
        locale: str,
        plan: str,
        topic_id: str,
        audience: str = "tenant_admin",
    ) -> dict[str, Any] | None:
        for topic in self._authorized_topics(locale, plan, audience):
            if topic["id"] == topic_id:
                return {
                    **_public_topic(topic),
                    "body": topic["body"],
                }
        return None

    def search(
        self,
        locale: str,
        plan: str,
        query: str,
        audience: str = "tenant_admin",
    ) -> list[dict[str, Any]]:
        normalized_query = _normalize_search_text(query)
        if not normalized_query:
            return []

        authorized = {
            topic["id"] for topic in self._authorized_topics(locale, plan, audience)
        }
        topics = {
            topic["id"]: topic
            for topic in self.artifact.get("topics", {}).get(locale, [])
        }
        results: list[dict[str, Any]] = []
        for item in self.artifact.get("search", {}).get(locale, []):
            if item["id"] not in authorized:
                continue
            if not any(
                normalized_query in _normalize_search_text(term)
                for term in item["terms"]
            ):
                continue
            topic = topics.get(item["id"])
            if topic is None:
                continue
            results.append(
                {
                    **_public_search_topic(topic),
                    "excerpt": _excerpt(
                        topic["body"], normalized_query, topic["title"]
                    ),
                }
            )
        return results

    def _authorized_topics(
        self, locale: str, plan: str, audience: str
    ) -> list[dict[str, Any]]:
        topics = [
            topic
            for topic in self.artifact.get("topics", {}).get(locale, [])
            if topic["audience"] == audience and plan in topic["plans"]
        ]
        return sorted(topics, key=lambda topic: (topic["order"], topic["id"]))


@lru_cache(maxsize=1)
def get_help_catalog() -> HelpCatalog:
    """Load the generated artifact once per process."""

    artifact = json.loads(ARTIFACT_PATH.read_text(encoding="utf-8"))
    return HelpCatalog(artifact)


def _public_topic(topic: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": topic["id"],
        "title": topic["title"],
        "summary": topic["summary"],
        "module": topic["module"],
        "route": topic["route"],
        "order": topic["order"],
        "help_targets": topic["help_targets"],
        "safe_navigation": topic["safe_navigation"],
        "safe_links": topic.get("safe_links", []),
    }


def _public_search_topic(topic: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": topic["id"],
        "title": topic["title"],
        "module": topic["module"],
        "route": topic["route"],
        "order": topic["order"],
    }


def _normalize_search_text(value: str) -> str:
    return " ".join(value.casefold().split())


def _excerpt(body: str, query: str, fallback: str = "") -> str:
    lines = [line.strip() for line in body.split("\n") if line.strip()]
    for line in lines:
        if query in _normalize_search_text(line):
            return _clean_excerpt(line)
    if fallback:
        return _clean_excerpt(fallback)
    return _clean_excerpt(lines[0]) if lines else ""


def _clean_excerpt(value: str) -> str:
    return value.lstrip("#- ")
