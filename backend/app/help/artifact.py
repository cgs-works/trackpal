"""Access to the generated private Help artifact."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

ARTIFACT_PATH = Path(__file__).with_name("artifact.json")


class HelpCatalog:
    """Filter compiled Help content for the authenticated Tenant Admin."""

    def __init__(self, artifact: dict[str, Any]) -> None:
        self.artifact = artifact

    def index(self, locale: str, plan: str) -> dict[str, Any]:
        return {
            "schema_version": self.artifact["schema_version"],
            "content_version": self.artifact["content_version"],
            "frontend_target_contract_version": self.artifact[
                "frontend_target_contract_version"
            ],
            "locale": locale,
            "topics": [
                _public_topic(topic) for topic in self._authorized_topics(locale, plan)
            ],
        }

    def topic(self, locale: str, plan: str, topic_id: str) -> dict[str, Any] | None:
        for topic in self._authorized_topics(locale, plan):
            if topic["id"] == topic_id:
                return {
                    **_public_topic(topic),
                    "body": topic["body"],
                }
        return None

    def search(self, locale: str, plan: str, query: str) -> list[dict[str, Any]]:
        normalized_query = query.strip().casefold()
        if not normalized_query:
            return []
        authorized = {topic["id"] for topic in self._authorized_topics(locale, plan)}
        topics = {topic["id"]: topic for topic in self.artifact["topics"][locale]}
        results: list[dict[str, Any]] = []
        for item in self.artifact["search"][locale]:
            if item["id"] not in authorized:
                continue
            if not any(normalized_query in term.casefold() for term in item["terms"]):
                continue
            topic = topics[item["id"]]
            results.append(
                {
                    **_public_topic(topic),
                    "excerpt": _excerpt(topic["body"], normalized_query),
                }
            )
        return results

    def _authorized_topics(self, locale: str, plan: str) -> list[dict[str, Any]]:
        return [
            topic
            for topic in self.artifact["topics"].get(locale, [])
            if topic["audience"] == "tenant_admin" and plan in topic["plans"]
        ]


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
    }


def _excerpt(body: str, query: str) -> str:
    sentences = [sentence.strip() for sentence in body.split("\n") if sentence.strip()]
    for sentence in sentences:
        if query in sentence.casefold():
            return sentence.lstrip("#- ")
    return sentences[0].lstrip("#- ") if sentences else ""
