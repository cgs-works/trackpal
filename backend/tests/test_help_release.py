import copy
import json
from pathlib import Path

import pytest

from app.help.artifact import ARTIFACT_PATH
from app.help.compiler import HelpValidationError, compile_help
from app.help.release import validate_release_artifact

SOURCE_DIR = Path(__file__).parents[1] / "help"


def test_checked_in_help_release_contains_both_manuals_and_tours() -> None:
    artifact = json.loads(ARTIFACT_PATH.read_text(encoding="utf-8"))

    validate_release_artifact(artifact)

    assert set(artifact["locales"]) == {"en", "es"}
    assert {topic["audience"] for topic in artifact["topics"]["en"]} == {
        "tenant_admin",
        "client",
    }
    assert {release["release_id"] for release in artifact["tour_releases"]["en"]} == {
        "tenant-admin-starter-1",
        "tenant-admin-pro-1",
        "tenant-admin-pro-upgrade-1",
    }


def test_release_contract_rejects_a_partial_manual() -> None:
    artifact = compile_help(SOURCE_DIR)
    artifact["topics"]["es"] = [
        topic for topic in artifact["topics"]["es"] if topic["id"] != "client.whatsapp"
    ]

    with pytest.raises(HelpValidationError, match="Incomplete private Help topic set"):
        validate_release_artifact(artifact)


def test_release_contract_rejects_a_missing_tour_step() -> None:
    artifact = copy.deepcopy(compile_help(SOURCE_DIR))
    artifact["tour_releases"]["en"][0]["steps"].pop()

    with pytest.raises(HelpValidationError, match="must contain 7 steps"):
        validate_release_artifact(artifact)
