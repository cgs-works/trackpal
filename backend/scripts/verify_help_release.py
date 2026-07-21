"""Verify that the checked-in private Help release is publishable."""

from __future__ import annotations

import json
from pathlib import Path

from app.help.artifact import ARTIFACT_PATH
from app.help.compiler import compile_help
from app.help.release import validate_release_artifact

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "help"


def main() -> None:
    """Validate source, artifact parity, and the atomic release contract."""

    compiled = compile_help(SOURCE_DIR)
    checked_in = json.loads(ARTIFACT_PATH.read_text(encoding="utf-8"))
    validate_release_artifact(checked_in)
    if checked_in != compiled:
        raise SystemExit(
            "Private Help artifact is stale; run `uv run python -m scripts.compile_help`"
        )
    print("Private Help release contract is ready")


if __name__ == "__main__":
    main()
