"""Tests for deterministic mail lookup fingerprints."""

from app.pipeline.fingerprint import compute_fingerprint


def test_compute_fingerprint_with_message_id_has_known_sha256() -> None:
    result = compute_fingerprint(
        service_key="spotify",
        message_id="msg-001",
        sender="noreply@spotify.com",
        received_at_iso="2026-08-01T00:00:00+00:00",
        subject="Your Spotify login code",
        payload_normalized="654321",
    )

    assert result == "9e489b9e2c12812ab8f4df8d6be3587aa969ddf2771ae361cb92b97f262bea6c"


def test_compute_fingerprint_without_message_id_uses_fallback_fields() -> None:
    result = compute_fingerprint(
        service_key="netflix",
        message_id=None,
        sender="noreply@netflix.com",
        received_at_iso="2026-05-27T12:00:00",
        subject="Your Netflix code",
        payload_normalized="ABC123",
    )

    assert result == "3065871453b0bbbb015c89d421f4fdf224b53ebb41d518b5cf45c725a4a4b0cf"
