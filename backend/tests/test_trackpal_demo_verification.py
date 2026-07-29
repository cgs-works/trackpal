"""Verification fixture tests for the synthetic TrackPal Demo email."""

from pathlib import Path

from app.services.mail_code_extractor import extract_from_body
from app.services.mail_lookup_worker.providers._google import _html_to_text

SUBJECT = "Your TrackPal demo access code"
EXPECTED_CODE = "864215"
REAL_SERVICE_BRANDS = (
    "Netflix",
    "Disney",
    "HBO",
    "Spotify",
    "Amazon",
    "Universal+",
)


def test_demo_html_extracts_expected_code_without_real_service_brands() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    html = (
        repo_root / "docs" / "verification" / "trackpal-demo-code-email.html"
    ).read_text(encoding="utf-8")

    for brand in REAL_SERVICE_BRANDS:
        assert brand not in html

    body = _html_to_text(html)
    result = extract_from_body(body, "trackpal_demo", subject=SUBJECT)

    assert result is not None
    assert result.value == EXPECTED_CODE
    assert result.result_type == "code"
