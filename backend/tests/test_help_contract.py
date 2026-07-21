import json
from pathlib import Path

import pytest

from app.help.artifact import ARTIFACT_PATH
from app.help.compiler import HelpValidationError, compile_help


SOURCE_DIR = Path(__file__).parents[1] / "help"


def test_repository_help_compiles_with_bilingual_parity() -> None:
    artifact = compile_help(SOURCE_DIR)

    assert artifact["schema_version"] == 1
    assert artifact["content_version"] == "help-client-manual-1"
    assert artifact["frontend_target_contract_version"] == "2"
    assert set(artifact["locales"]) == {"en", "es"}
    expected_ids = [
        "tenant-admin.access-control",
        "tenant-admin.activate-access-code-lookup",
        "tenant-admin.code-services",
        "tenant-admin.dashboard",
        "tenant-admin.language",
        "tenant-admin.mailbox",
        "tenant-admin.password",
        "tenant-admin.profile",
        "tenant-admin.whatsapp",
        "tenant-admin.catalog",
        "tenant-admin.clients",
        "tenant-admin.first-pro-client",
        "tenant-admin.public-api",
        "tenant-admin.reminders",
        "tenant-admin.subscription-expirations",
        "tenant-admin.subscriptions",
        "tenant-admin.timezone",
        "client.dashboard",
        "client.password",
        "client.profile",
        "client.subscriptions",
        "client.whatsapp",
    ]
    assert [topic["id"] for topic in artifact["topics"]["en"]] == sorted(expected_ids)
    assert [topic["id"] for topic in artifact["topics"]["es"]] == sorted(expected_ids)
    assert artifact["topics"]["en"][0]["body"] != artifact["topics"]["es"][0]["body"]

    english_search = next(
        item
        for item in artifact["search"]["en"]
        if item["id"] == "tenant-admin.dashboard"
    )
    assert english_search["title"] in english_search["terms"]
    assert "mailbox" in english_search["terms"]
    assert "home" in english_search["terms"]
    assert "central lookup mailbox" in english_search["terms"][-1]
    code_services = next(
        topic
        for topic in artifact["topics"]["en"]
        if topic["id"] == "tenant-admin.code-services"
    )
    assert code_services["safe_navigation"] == {
        "route": "/admin/settings",
        "settings_category": "code-services",
    }


def test_pro_topics_cover_client_catalog_and_first_client_contracts() -> None:
    artifact = compile_help(SOURCE_DIR)
    topics = {topic["id"]: topic for topic in artifact["topics"]["en"]}

    assert topics["tenant-admin.clients"]["plans"] == ["pro"]
    assert topics["tenant-admin.clients"]["help_targets"] == ["admin.clients"]

    client_topics = {
        topic["id"]: topic
        for topic in artifact["topics"]["en"]
        if topic["audience"] == "client"
    }
    assert list(client_topics) == [
        "client.dashboard",
        "client.password",
        "client.profile",
        "client.subscriptions",
        "client.whatsapp",
    ]
    assert all(topic["plans"] == ["pro"] for topic in client_topics.values())
    assert client_topics["client.password"]["channels"] == ["web"]
    assert client_topics["client.password"]["safe_navigation"] == {
        "route": "/client/profile",
        "settings_category": None,
    }
    assert client_topics["client.subscriptions"]["help_targets"] == [
        "client.subscriptions"
    ]
    assert client_topics["client.whatsapp"]["help_targets"] == []

    for topic_id, phrases in {
        "client.dashboard": ("provider", "read-only", "WhatsApp"),
        "client.profile": ("read-only", "provider", "WhatsApp"),
        "client.subscriptions": ("active", "service", "expiration", "password"),
        "client.password": ("Web only", "current password", "WhatsApp"),
        "client.whatsapp": ("profile", "subscriptions", "access code", "exit"),
    }.items():
        body = client_topics[topic_id]["body"].lower()
        assert all(phrase.lower() in body for phrase in phrases)

    assert topics["tenant-admin.clients"]["safe_navigation"] == {
        "route": "/admin/clients",
        "settings_category": None,
    }
    assert topics["tenant-admin.catalog"]["help_targets"] == ["admin.catalog"]
    assert topics["tenant-admin.catalog"]["safe_navigation"] == {
        "route": "/admin/catalog",
        "settings_category": None,
    }
    assert topics["tenant-admin.subscriptions"]["help_targets"] == [
        "admin.subscriptions"
    ]
    first_client = topics["tenant-admin.first-pro-client"]
    assert first_client["help_targets"] == []
    assert first_client["related_topics"] == [
        "tenant-admin.catalog",
        "tenant-admin.clients",
        "tenant-admin.subscriptions",
    ]
    assert [
        first_client["safe_navigation"]["route"],
        *[link["route"] for link in first_client["safe_links"]],
    ] == [
        "/admin/catalog",
        "/admin/clients",
        "/admin/subscriptions",
    ]

    clients_body = topics["tenant-admin.clients"]["body"].lower()
    for phrase in (
        "search",
        "create",
        "edit",
        "activate",
        "deactivate",
        "delete",
        "canonical",
        "subscriptions",
    ):
        assert phrase in clients_body

    catalog_body = topics["tenant-admin.catalog"]["body"].lower()
    for phrase in (
        "service",
        "plan",
        "rename",
        "empty",
        "active subscription",
        "historical subscription",
        "irreversible",
        "confirm",
    ):
        assert phrase in catalog_body

    whatsapp_body = topics["tenant-admin.whatsapp"]["body"].lower()
    for phrase in ("clients", "catalog", "subscriptions", "context shortcut"):
        assert phrase in whatsapp_body


def test_public_api_topic_covers_safe_browser_publication_contract() -> None:
    artifact = compile_help(SOURCE_DIR)
    topic = next(
        topic
        for topic in artifact["topics"]["en"]
        if topic["id"] == "tenant-admin.public-api"
    )

    assert topic["plans"] == ["pro"]
    assert topic["channels"] == ["web"]
    assert topic["help_targets"] == ["admin.settings.public-api"]
    assert topic["safe_navigation"] == {
        "route": "/admin/settings",
        "settings_category": "public-api",
    }
    body = topic["body"].lower()
    for phrase in (
        "allowed origin",
        "exact",
        "read-only",
        "regenerat",
        "revok",
        "cloudflare",
        "rate-limit",
        "your_public_api_key",
    ):
        assert phrase in body


def test_subscription_topics_cover_lifecycle_reminders_and_expiration_contracts() -> (
    None
):
    artifact = compile_help(SOURCE_DIR)
    topics = {topic["id"]: topic for topic in artifact["topics"]["en"]}

    subscriptions = topics["tenant-admin.subscriptions"]
    assert subscriptions["channels"] == ["web", "whatsapp"]
    assert subscriptions["safe_navigation"] == {
        "route": "/admin/subscriptions",
        "settings_category": None,
    }
    subscriptions_body = subscriptions["body"].lower()
    for phrase in (
        "filter",
        "create",
        "edit",
        "reveal",
        "cancel",
        "renew",
        "reactivate",
        "active",
        "expired",
        "cancelled",
        "duration",
        "profile",
        "credential",
        "whatsapp",
        "8",
        "9",
        "0",
    ):
        assert phrase in subscriptions_body

    reminders = topics["tenant-admin.reminders"]
    assert reminders["help_targets"] == ["admin.settings.reminders"]
    assert reminders["safe_navigation"] == {
        "route": "/admin/settings",
        "settings_category": "reminders",
    }
    reminders_body = reminders["body"].lower()
    for phrase in (
        "opt-in",
        "warning days",
        "local time",
        "recipients",
        "custom message",
        "automation",
        "pro",
    ):
        assert phrase in reminders_body

    timezone = topics["tenant-admin.timezone"]
    assert timezone["help_targets"] == ["admin.settings.timezone"]
    assert timezone["safe_navigation"] == {
        "route": "/admin/settings",
        "settings_category": "timezone",
    }
    timezone_body = timezone["body"].lower()
    for phrase in ("iana", "local date", "reminder", "expiration", "pro"):
        assert phrase in timezone_body

    expiration = topics["tenant-admin.subscription-expirations"]
    assert expiration["help_targets"] == []
    assert expiration["safe_navigation"] == {
        "route": "/admin/subscriptions",
        "settings_category": None,
    }
    assert expiration["safe_links"] == [
        {"route": "/admin/settings", "settings_category": "timezone"},
        {"route": "/admin/settings", "settings_category": "reminders"},
    ]
    expiration_body = expiration["body"].lower()
    for phrase in (
        "timezone",
        "reminder",
        "expire",
        "renew",
        "reactivat",
        "cancel",
        "automation",
    ):
        assert phrase in expiration_body


def test_access_code_topics_expose_cross_channel_contracts_and_states() -> None:
    artifact = compile_help(SOURCE_DIR)
    topics = {topic["id"]: topic for topic in artifact["topics"]["en"]}

    assert topics["tenant-admin.code-services"]["help_targets"] == [
        "admin.settings.code-services"
    ]
    assert topics["tenant-admin.mailbox"]["safe_navigation"] == {
        "route": "/admin/settings",
        "settings_category": "mailbox",
    }
    assert topics["tenant-admin.access-control"]["help_targets"] == [
        "admin.settings.access-control"
    ]
    assert topics["tenant-admin.activate-access-code-lookup"]["help_targets"] == [
        "admin.settings"
    ]
    assert topics["tenant-admin.activate-access-code-lookup"]["safe_navigation"] == {
        "route": "/admin/settings",
        "settings_category": "code-services",
    }

    access_code_body = topics["tenant-admin.activate-access-code-lookup"][
        "body"
    ].lower()
    for state in ("pending", "found", "not found", "duplicate", "timeout"):
        assert state in access_code_body
    assert "0" in access_code_body
    assert "8" in access_code_body
    assert "9" in access_code_body


def test_checked_in_artifact_matches_the_compiled_sources() -> None:
    checked_in = json.loads(ARTIFACT_PATH.read_text(encoding="utf-8"))

    assert checked_in == compile_help(SOURCE_DIR)


def test_compiler_rejects_duplicate_topic_ids(tmp_path: Path) -> None:
    for locale in ("en", "es"):
        locale_dir = tmp_path / locale
        locale_dir.mkdir(parents=True)
        source = (SOURCE_DIR / locale / "tenant-admin" / "dashboard.md").read_text()
        (locale_dir / "first.md").write_text(source)
        (locale_dir / "second.md").write_text(source)

    with pytest.raises(HelpValidationError, match="Duplicate topic id"):
        compile_help(tmp_path)


def test_compiler_rejects_unknown_values_and_executable_markdown(
    tmp_path: Path,
) -> None:
    for locale in ("en", "es"):
        locale_dir = tmp_path / locale / "tenant-admin"
        locale_dir.mkdir(parents=True)
        source = (SOURCE_DIR / locale / "tenant-admin" / "dashboard.md").read_text()
        source = source.replace("module: dashboard", "module: unknown-module")
        source += "\n<script>alert('x')</script>\n"
        (locale_dir / "dashboard.md").write_text(source)

    with pytest.raises(HelpValidationError):
        compile_help(tmp_path)


def test_compiler_rejects_locale_metadata_drift(tmp_path: Path) -> None:
    for locale in ("en", "es"):
        locale_dir = tmp_path / locale / "tenant-admin"
        locale_dir.mkdir(parents=True)
        source = (SOURCE_DIR / locale / "tenant-admin" / "dashboard.md").read_text()
        if locale == "es":
            source = source.replace("module: dashboard", "module: help")
        (locale_dir / "dashboard.md").write_text(source)

    with pytest.raises(HelpValidationError, match="metadata parity"):
        compile_help(tmp_path)
