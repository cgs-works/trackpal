import shutil
from pathlib import Path

import pytest

import app.api.v1.endpoints.help as help_endpoint
from app.help.compiler import HelpValidationError, compile_help, validate_artifact

SOURCE_DIR = Path(__file__).parents[1] / "help"


def test_compiler_rejects_non_contiguous_tour_order(tmp_path: Path) -> None:
    source_dir = tmp_path / "help"
    shutil.copytree(SOURCE_DIR, source_dir)

    for locale in ("en", "es"):
        path = source_dir / locale / "tenant-admin" / "help.md"
        source = path.read_text(encoding="utf-8")
        path.write_text(
            source.replace("    order: 7", "    order: 8", 1), encoding="utf-8"
        )

    with pytest.raises(HelpValidationError, match="ordered from 1"):
        compile_help(source_dir)


def test_compiler_rejects_cross_audience_navigation(tmp_path: Path) -> None:
    source_dir = tmp_path / "help"
    shutil.copytree(SOURCE_DIR, source_dir)

    for locale in ("en", "es"):
        path = source_dir / locale / "client" / "profile.md"
        source = path.read_text(encoding="utf-8")
        source = source.replace(
            "related_topics:\n",
            "safe_links:\n  - route: /admin/dashboard\n    settings_category: null\nrelated_topics:\n",
            1,
        )
        path.write_text(source, encoding="utf-8")

    with pytest.raises(HelpValidationError, match="Client topic cannot navigate"):
        compile_help(source_dir)


def test_compiler_rejects_client_orientation_tours(tmp_path: Path) -> None:
    source_dir = tmp_path / "help"
    shutil.copytree(SOURCE_DIR, source_dir)

    for locale in ("en", "es"):
        path = source_dir / locale / "client" / "profile.md"
        source = path.read_text(encoding="utf-8")
        source = source.replace(
            "related_topics:\n",
            "tour:\n  release_id: client-tour\n  order: 1\n  target: client.profile\nrelated_topics:\n",
            1,
        )
        path.write_text(source, encoding="utf-8")

    with pytest.raises(
        HelpValidationError, match="Client topic cannot declare an orientation tour"
    ):
        compile_help(source_dir)


def test_artifact_validator_rejects_incompatible_schema_and_target_contract() -> None:
    artifact = compile_help(SOURCE_DIR)

    artifact["schema_version"] = 99
    with pytest.raises(HelpValidationError, match="Incompatible Help artifact schema"):
        validate_artifact(artifact)

    artifact = compile_help(SOURCE_DIR)
    artifact["frontend_target_contract_version"] = "future"
    with pytest.raises(
        HelpValidationError, match="Incompatible Help frontend target contract"
    ):
        validate_artifact(artifact)


@pytest.mark.asyncio
async def test_help_artifact_failure_is_scoped_to_help_api(
    client, active_tenant_user, monkeypatch
):
    login = await client.post(
        "/api/v1/auth/login",
        json={"username": "tenant", "password": "tenant-password"},
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    def broken_catalog():
        raise OSError("artifact unavailable")

    monkeypatch.setattr(help_endpoint, "get_help_catalog", broken_catalog)
    help_response = await client.get("/api/v1/help", headers=headers)
    dashboard_response = await client.get("/api/v1/dashboard", headers=headers)

    assert help_response.status_code == 503
    assert dashboard_response.status_code == 200
