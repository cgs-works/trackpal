import json
from pathlib import Path

import pytest

from app.help.artifact import ARTIFACT_PATH
from app.help.compiler import HelpValidationError, compile_help


SOURCE_DIR = Path(__file__).parents[1] / "help"


def test_repository_help_compiles_with_bilingual_parity() -> None:
    artifact = compile_help(SOURCE_DIR)

    assert artifact["schema_version"] == 1
    assert artifact["content_version"] == "help-common-modules-1"
    assert artifact["frontend_target_contract_version"] == "2"
    assert set(artifact["locales"]) == {"en", "es"}
    expected_ids = [
        "tenant-admin.dashboard",
        "tenant-admin.language",
        "tenant-admin.profile",
        "tenant-admin.password",
        "tenant-admin.whatsapp",
    ]
    assert [topic["id"] for topic in artifact["topics"]["en"]] == sorted(expected_ids)
    assert [topic["id"] for topic in artifact["topics"]["es"]] == sorted(expected_ids)
    assert artifact["topics"]["en"][0]["body"] != artifact["topics"]["es"][0]["body"]

    english_search = artifact["search"]["en"][0]
    assert english_search["title"] in english_search["terms"]
    assert "mailbox" in english_search["terms"]
    assert "home" in english_search["terms"]
    assert "central lookup mailbox" in english_search["terms"][-1]
    assert artifact["topics"]["en"][1]["safe_navigation"] == {
        "route": "/admin/settings",
        "settings_category": "locale",
    }


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
