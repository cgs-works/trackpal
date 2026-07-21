from app.help.artifact import HelpCatalog


def _topic(topic_id: str, audience: str, plans: list[str], title: str) -> dict:
    return {
        "id": topic_id,
        "locale": "en",
        "audience": audience,
        "plans": plans,
        "channels": ["web"],
        "module": "dashboard",
        "capabilities": ["tenant_dashboard"],
        "route": "/admin/dashboard",
        "help_targets": ["admin.dashboard"],
        "title": title,
        "summary": f"{title} summary",
        "search_tags": ["starter-tag" if "starter" in topic_id else "pro-tag"],
        "synonyms": ["begin" if "starter" in topic_id else "premium"],
        "related_topics": [],
        "tour": None,
        "body": f"# {title}\n\nThis is the {topic_id} article.",
    }


def _catalog() -> HelpCatalog:
    topics = [
        _topic(
            "tenant-admin.starter", "tenant_admin", ["starter", "pro"], "Starter Help"
        ),
        _topic("tenant-admin.pro", "tenant_admin", ["pro"], "Pro Help"),
        _topic("client.dashboard", "client", ["pro"], "Client Dashboard"),
    ]
    return HelpCatalog(
        {
            "schema_version": 1,
            "content_version": "test",
            "frontend_target_contract_version": "1",
            "topics": {"en": topics},
            "search": {
                "en": [
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
            },
        }
    )


def test_catalog_filters_audience_and_plan_before_search_matching() -> None:
    catalog = _catalog()

    starter_topics = catalog.index("en", "starter")["topics"]
    starter_search = catalog.search("en", "starter", "premium")
    client_search = catalog.search("en", "pro", "dashboard", audience="client")

    assert [topic["id"] for topic in starter_topics] == ["tenant-admin.starter"]
    assert starter_search == []
    assert [result["id"] for result in client_search] == ["client.dashboard"]
    assert set(client_search[0]) == {"id", "title", "module", "route", "excerpt"}


def test_catalog_search_matches_maintained_synonyms() -> None:
    catalog = _catalog()

    results = catalog.search("en", "starter", "begin")

    assert [result["id"] for result in results] == ["tenant-admin.starter"]
    assert results[0]["excerpt"] == "Starter Help"
