"""Compile private Help Markdown into the backend artifact."""

from pathlib import Path

from app.help.compiler import compile_help, write_artifact


ROOT = Path(__file__).resolve().parents[1]


if __name__ == "__main__":
    artifact = compile_help(ROOT / "help")
    write_artifact(artifact, ROOT / "app" / "help" / "artifact.json")
    print("Compiled private Help artifact")
