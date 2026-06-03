from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CATALOG_FILES = [
    ROOT / "app" / "core" / "i18n" / "catalogs_es_wa.py",
    ROOT / "app" / "core" / "i18n" / "catalogs_en_wa.py",
]

SOURCE_GLOBS = [
    ROOT / "app" / "services",
    ROOT / "app" / "api" / "v1" / "endpoints" / "integrations",
]

FORBIDDEN_PATTERNS = [
    re.compile(r"0(?:️)?(?:⃣|️⃣)?\s*(?:Volver|Regresar|Back|Return)", re.IGNORECASE),
    re.compile(r"9(?:️)?(?:⃣|️⃣)?\s*(?:Siguiente|Next)", re.IGNORECASE),
    re.compile(r"8(?:️)?(?:⃣|️⃣)?\s*(?:Anterior|Previous|Regresar|Back)", re.IGNORECASE),
    re.compile(r"(?:escribe|write|type|respond(?:e)?)\s+\*?9\*?\s+(?:para\s+)?(?:cancelar|cancel)", re.IGNORECASE),
]

REQUIRED_LABELS_ES = ["8️⃣ Siguiente", "9️⃣ Regresar", "0️⃣ Cancelar"]
REQUIRED_LABELS_EN = ["8️⃣ Next", "9️⃣ Back", "0️⃣ Cancel"]


def _python_text_files(root: Path) -> list[Path]:
    return [path for path in root.rglob("*.py") if "__pycache__" not in str(path)]


def test_whatsapp_catalogs_do_not_define_conflicting_numeric_navigation() -> None:
    offenders: list[str] = []
    for path in CATALOG_FILES:
        text = path.read_text(encoding="utf-8")
        for pattern in FORBIDDEN_PATTERNS:
            for match in pattern.finditer(text):
                offenders.append(f"{path.relative_to(ROOT)}: {match.group(0)!r}")
    assert offenders == []


def test_console_sources_do_not_present_conflicting_numeric_navigation() -> None:
    offenders: list[str] = []
    for root in SOURCE_GLOBS:
        for path in _python_text_files(root):
            text = path.read_text(encoding="utf-8")
            for pattern in FORBIDDEN_PATTERNS:
                for match in pattern.finditer(text):
                    offenders.append(f"{path.relative_to(ROOT)}: {match.group(0)!r}")
    assert offenders == []


def test_shared_navigation_labels_exist_in_catalogs() -> None:
    es_text = CATALOG_FILES[0].read_text(encoding="utf-8")
    en_text = CATALOG_FILES[1].read_text(encoding="utf-8")

    for label in REQUIRED_LABELS_ES:
        assert label in es_text
    for label in REQUIRED_LABELS_EN:
        assert label in en_text
