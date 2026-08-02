import json
import re
from pathlib import Path

import pytest

from app.core.i18n.catalogs_en_frontend import _CATALOG_EN_FRONTEND
from app.core.i18n.catalogs_es_frontend import _CATALOG_ES_FRONTEND
from app.help.artifact import ARTIFACT_PATH
from app.help.compiler import HelpValidationError, compile_help


SOURCE_DIR = Path(__file__).parents[1] / "help"


def _make_topic(
    topic_id: str = "tenant-admin.test",
    settings_category: str | None = None,
    tab: str | None = None,
) -> str:
    """Build a minimal topic markdown with the given safe_navigation fields."""
    nav_lines = ["  route: /admin/settings"]
    if settings_category is not None:
        nav_lines.append(f"  settings_category: {settings_category}")
    if tab is not None:
        nav_lines.append(f"  tab: {tab}")
    safe_navigation = "\n".join(nav_lines)
    return f"""---
id: {topic_id}
audience: tenant_admin
plans:
  - starter
channels:
  - web
module: settings
capabilities:
  - tenant_settings
route: /admin/settings
help_targets:
  - admin.settings.reminders
title: Test
summary: Test topic.
search_tags:
  - test
synonyms:
  - test
order: 999
safe_navigation:
{safe_navigation}
related_topics: []
---

# Test

Test body.
"""


def _compile_with_topics(tmp_path: Path, topics: dict[str, str]) -> dict:
    """Write mirrored topics and compile from tmp_path."""
    for locale in ("en", "es"):
        locale_dir = tmp_path / locale / "tenant-admin"
        locale_dir.mkdir(parents=True)
        for filename, body in topics.items():
            (locale_dir / filename).write_text(body)
    return compile_help(tmp_path)


def test_compiler_rejects_locale_settings_category(tmp_path: Path) -> None:
    """settings_category 'locale' must be rejected — it is no longer allowed."""
    topic = _make_topic(settings_category="locale")
    topics = {"test.md": topic}
    with pytest.raises(HelpValidationError, match="settings category"):
        _compile_with_topics(tmp_path, topics)


def test_compiler_rejects_timezone_settings_category(tmp_path: Path) -> None:
    """settings_category 'timezone' must be rejected — it is no longer allowed."""
    topic = _make_topic(settings_category="timezone")
    topics = {"test.md": topic}
    with pytest.raises(HelpValidationError, match="settings category"):
        _compile_with_topics(tmp_path, topics)


def test_compiler_accepts_my_account_with_regional_tab(tmp_path: Path) -> None:
    """settings_category 'my-account' + tab 'regional' must compile."""
    topic = _make_topic(settings_category="my-account", tab="regional")
    topics = {"test.md": topic}
    artifact = _compile_with_topics(tmp_path, topics)
    compiled_topic = artifact["topics"]["en"][0]
    assert compiled_topic["safe_navigation"] == {
        "route": "/admin/settings",
        "settings_category": "my-account",
        "tab": "regional",
    }


def test_compiler_rejects_invalid_tab(tmp_path: Path) -> None:
    """An invalid tab value must be rejected."""
    topic = _make_topic(settings_category="my-account", tab="invalid")
    topics = {"test.md": topic}
    with pytest.raises(HelpValidationError, match="tab"):
        _compile_with_topics(tmp_path, topics)


def test_compiler_rejects_tab_without_my_account(tmp_path: Path) -> None:
    """tab must only be allowed with settings_category 'my-account'."""
    topic = _make_topic(settings_category="code-services", tab="regional")
    topics = {"test.md": topic}
    with pytest.raises(HelpValidationError, match="tab"):
        _compile_with_topics(tmp_path, topics)


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
        "tenant-admin.country",
        "tenant-admin.currency",
        "tenant-admin.dashboard",
        "tenant-admin.data-export",
        "tenant-admin.delete-account",
        "tenant-admin.help",
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
    assert "central mailbox" in english_search["terms"][-1]
    code_services = next(
        topic
        for topic in artifact["topics"]["en"]
        if topic["id"] == "tenant-admin.code-services"
    )
    assert code_services["safe_navigation"] == {
        "route": "/admin/settings",
        "settings_category": "code-services",
    }
    tracer = next(
        release
        for release in artifact["tour_releases"]["en"]
        if release["release_id"] == "tenant-admin-starter-1"
    )
    assert tracer["release_id"] == "tenant-admin-starter-1"
    assert [step["target"] for step in tracer["steps"]] == [
        "admin.dashboard",
        "admin.dashboard",
        "admin.settings.profile",
        "admin.settings.whatsapp",
        "admin.settings.code-services",
        "admin.settings.access-control",
        "admin.help",
    ]
    assert tracer["plans"] == ["starter"]
    tour_content = " ".join(step["content"] for step in tracer["steps"]).casefold()
    for forbidden in (
        "clients",
        "catalog",
        "subscriptions",
        "reminder",
        "timezone",
        "public api",
    ):
        assert forbidden not in tour_content


def test_pro_tours_declare_initial_and_upgrade_sequences() -> None:
    artifact = compile_help(SOURCE_DIR)
    releases = {
        release["release_id"]: release for release in artifact["tour_releases"]["en"]
    }

    initial = releases["tenant-admin-pro-1"]
    assert initial["plans"] == ["pro"]
    assert [step["target"] for step in initial["steps"]] == [
        "admin.dashboard",
        "admin.dashboard",
        "admin.clients",
        "admin.catalog",
        "admin.subscriptions",
        "admin.settings.regional",
        "admin.help",
    ]
    assert "tenant-admin.reminders" in initial["steps"][5]["related_topics"]

    upgrade = releases["tenant-admin-pro-upgrade-1"]
    assert upgrade["plans"] == ["pro"]
    assert [step["target"] for step in upgrade["steps"]] == [
        "admin.clients",
        "admin.catalog",
        "admin.subscriptions",
        "admin.settings.reminders",
        "admin.settings.public-api",
    ]
    upgrade_content = " ".join(step["content"] for step in upgrade["steps"]).casefold()
    for forbidden in ("starter", "dashboard"):
        assert forbidden not in upgrade_content


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
        "full username",
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
    for phrase in ("clients", "catalog", "subscriptions", "private client menu"):
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
        "turn this feature on",
        "warning days",
        "local time",
        "recipients",
        "custom message",
        "automation",
        "current plan",
    ):
        assert phrase in reminders_body

    timezone = topics["tenant-admin.timezone"]
    assert timezone["help_targets"] == ["admin.settings.regional"]
    assert timezone["safe_navigation"] == {
        "route": "/admin/settings",
        "settings_category": "my-account",
        "tab": "regional",
    }
    timezone_body = timezone["body"].lower()
    for phrase in (
        "region",
        "local calendar",
        "reminder",
        "expiration",
        "current plan",
    ):
        assert phrase in timezone_body

    expiration = topics["tenant-admin.subscription-expirations"]
    assert expiration["help_targets"] == []
    assert expiration["safe_navigation"] == {
        "route": "/admin/subscriptions",
        "settings_category": None,
    }
    assert expiration["safe_links"] == [
        {
            "route": "/admin/settings",
            "settings_category": "my-account",
            "tab": "regional",
        },
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
        "admin.settings.code-services"
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


def test_help_copy_avoids_internal_tenant_jargon() -> None:
    artifact = compile_help(SOURCE_DIR)

    for locale in ("en", "es"):
        visible_copy = []
        for topic in artifact["topics"][locale]:
            visible_copy.extend((topic["title"], topic["summary"], topic["body"]))
        for release in artifact["tour_releases"][locale]:
            for step in release["steps"]:
                visible_copy.extend((step["title"], step["content"]))

        assert "tenant" not in " ".join(visible_copy).casefold()


def test_help_copy_uses_complete_trackpal_plan_names() -> None:
    artifact = compile_help(SOURCE_DIR)

    for locale in ("en", "es"):
        visible_copy = []
        for topic in artifact["topics"][locale]:
            visible_copy.extend((topic["title"], topic["summary"], topic["body"]))
        for release in artifact["tour_releases"][locale]:
            for step in release["steps"]:
                visible_copy.extend((step["title"], step["content"]))

        joined = " ".join(visible_copy)
        assert re.search(r"(?<!TrackPal )\b(?:Pro|Starter)\b", joined) is None


def test_tour_copy_avoids_repetitive_safety_disclaimers() -> None:
    artifact = compile_help(SOURCE_DIR)
    forbidden_by_locale = {
        "en": (
            "this tour",
            "the tour only",
            "the tour is read-only",
            "this step opens",
        ),
        "es": (
            "este recorrido",
            "el recorrido solo",
            "el recorrido es de solo lectura",
            "este paso abre",
        ),
    }

    for locale, forbidden_phrases in forbidden_by_locale.items():
        tour_copy = " ".join(
            step["content"]
            for release in artifact["tour_releases"][locale]
            for step in release["steps"]
        ).casefold()
        assert all(phrase not in tour_copy for phrase in forbidden_phrases)


def test_frontend_i18n_copy_avoids_internal_tenant_jargon() -> None:
    for catalog in (_CATALOG_EN_FRONTEND, _CATALOG_ES_FRONTEND):
        assert "tenant" not in " ".join(catalog.values()).casefold()


def test_mailbox_help_covers_gmail_app_password_setup() -> None:
    artifact = compile_help(SOURCE_DIR)
    topics_by_locale = {
        locale: {topic["id"]: topic for topic in artifact["topics"][locale]}
        for locale in ("en", "es")
    }

    for locale in ("en", "es"):
        body = topics_by_locale[locale]["tenant-admin.mailbox"]["body"]
        assert "myaccount.google.com/apppasswords" in body
        assert "support.google.com/accounts/answer/185833" in body
        assert "Microsoft" not in body
        assert "Outlook" not in body


def test_mailbox_help_describes_only_app_password_connection() -> None:
    artifact = compile_help(SOURCE_DIR)
    topics_by_locale = {
        locale: {topic["id"]: topic for topic in artifact["topics"][locale]}
        for locale in ("en", "es")
    }

    for locale in ("en", "es"):
        body = topics_by_locale[locale]["tenant-admin.mailbox"]["body"]
        assert "myaccount.google.com/apppasswords" in body
        assert "OAuth" not in body
        assert "Google Connection" not in body
        assert "Conexión de Google" not in body


def test_mailbox_secret_help_copy_is_app_password_only() -> None:
    artifact = compile_help(SOURCE_DIR)
    topics = {
        locale: {topic["id"]: topic for topic in artifact["topics"][locale]}
        for locale in ("en", "es")
    }

    export_en = topics["en"]["tenant-admin.data-export"]["body"]
    export_es = topics["es"]["tenant-admin.data-export"]["body"]
    delete_en = topics["en"]["tenant-admin.delete-account"]["body"]
    delete_es = topics["es"]["tenant-admin.delete-account"]["body"]

    assert "Mailbox login credentials or app passwords" in export_en
    assert (
        "Credenciales de inicio de sesión del correo o contraseñas de aplicación"
        in export_es
    )
    assert "Google app password" in delete_en
    assert "Contraseña de aplicación de Google" in delete_es
    for body in (export_en, export_es, delete_en, delete_es):
        assert "OAuth" not in body


def test_mailbox_help_covers_app_password_eligibility_causes() -> None:
    artifact = compile_help(SOURCE_DIR)
    topics_by_locale = {
        locale: {topic["id"]: topic for topic in artifact["topics"][locale]}
        for locale in ("en", "es")
    }

    for locale, phrases in (
        ("en", ("2-step verification", "work or school", "advanced protection")),
        (
            "es",
            ("verificación en dos pasos", "trabajo o escuela", "protección avanzada"),
        ),
    ):
        body = topics_by_locale[locale]["tenant-admin.mailbox"]["body"].lower()
        for phrase in phrases:
            assert phrase in body, (
                f"Mailbox tutorial must mention '{phrase}' as an "
                f"app-password eligibility cause"
            )


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


def test_country_topic_metadata() -> None:
    artifact = compile_help(SOURCE_DIR)
    topics = {topic["id"]: topic for topic in artifact["topics"]["en"]}

    country = topics["tenant-admin.country"]
    assert country["plans"] == ["starter", "pro"]
    assert country["help_targets"] == ["admin.settings.regional"]
    assert country["safe_navigation"] == {
        "route": "/admin/settings",
        "settings_category": "my-account",
        "tab": "regional",
    }
    assert "tenant-admin.currency" in country["related_topics"]
    assert "tenant-admin.language" in country["related_topics"]

    country_es = {topic["id"]: topic for topic in artifact["topics"]["es"]}[
        "tenant-admin.country"
    ]
    assert country_es["safe_navigation"] == country["safe_navigation"]


def test_currency_topic_metadata() -> None:
    artifact = compile_help(SOURCE_DIR)
    topics = {topic["id"]: topic for topic in artifact["topics"]["en"]}

    currency = topics["tenant-admin.currency"]
    assert currency["plans"] == ["pro"]
    assert currency["help_targets"] == ["admin.settings.regional"]
    assert currency["safe_navigation"] == {
        "route": "/admin/settings",
        "settings_category": "my-account",
        "tab": "regional",
    }


def test_language_topic_uses_my_account_regional_tab() -> None:
    artifact = compile_help(SOURCE_DIR)
    topics = {topic["id"]: topic for topic in artifact["topics"]["en"]}

    language = topics["tenant-admin.language"]
    assert language["safe_navigation"] == {
        "route": "/admin/settings",
        "settings_category": "my-account",
        "tab": "regional",
    }
    assert "admin.settings.regional" in language["help_targets"]
    body = language["body"].lower()
    assert "regional" in body


def test_timezone_topic_uses_my_account_regional_tab() -> None:
    artifact = compile_help(SOURCE_DIR)
    topics = {topic["id"]: topic for topic in artifact["topics"]["en"]}

    timezone = topics["tenant-admin.timezone"]
    assert timezone["safe_navigation"] == {
        "route": "/admin/settings",
        "settings_category": "my-account",
        "tab": "regional",
    }
    assert "admin.settings.regional" in timezone["help_targets"]
    body = timezone["body"].lower()
    assert "regional" in body
