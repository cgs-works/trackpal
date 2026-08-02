from datetime import UTC, datetime

from app.extractors import ParsedEmail, extract_newest_from_emails


def test_extract_newest_from_emails_accepts_literal_now() -> None:
    result = extract_newest_from_emails(
        [
            ParsedEmail(
                subject="Your Spotify login code",
                body="Enter this code 654321",
                received_at=datetime(2026, 8, 1, tzinfo=UTC),
            )
        ],
        "spotify",
        max_age_minutes=5,
        now=datetime(2026, 8, 1, 0, 1, tzinfo=UTC),
    )

    assert result is not None
    assert result.value == "654321"
