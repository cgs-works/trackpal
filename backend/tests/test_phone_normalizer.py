"""Tests for the shared phone normalizer.

Verifies all PRD normalization requirements:
- digits-only output
- removes `+` prefix
- strips WhatsApp JID suffixes (@c.us, @s.whatsapp.net)
- strips device suffixes after `:`
- returns None for blank/None/optional input
- preserves already canonical values unchanged
"""

import pytest

from app.core.phone import normalize_phone


class TestNormalizePhone:
    """Core normalization behaviour."""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("+1234567890", "1234567890"),
            ("1234567890", "1234567890"),
            ("+1 (555) 123-4567", "15551234567"),
            ("+123 456 7890", "1234567890"),
            ("+123-456-7890", "1234567890"),
            ("+1234567890@c.us", "1234567890"),
            ("+1234567890@s.whatsapp.net", "1234567890"),
            ("1234567890@c.us", "1234567890"),
            ("1234567890@s.whatsapp.net", "1234567890"),
            ("+1234567890:45@s.whatsapp.net", "1234567890"),
            ("+1234567890:45", "1234567890"),
            ("1234567890:45@c.us", "1234567890"),
            # Already canonical
            ("1234567890", "1234567890"),
            # With spaces/dashes/parentheses
            ("+1 (555) 123-4567 ext.100", "15551234567100"),  # keeps digits
            # Short phone
            ("+111", "111"),
        ],
    )
    def test_normalize_various_formats(self, raw: str, expected: str) -> None:
        assert normalize_phone(raw) == expected

    @pytest.mark.parametrize(
        ("raw",),
        [
            (None,),
            ("",),
            ("   ",),
            ("—",),  # skip word used in console flow
        ],
    )
    def test_blank_or_none_returns_none(self, raw: str | None) -> None:
        assert normalize_phone(raw) is None

    def test_only_non_digit_chars_returns_none(self) -> None:
        """String with no digits at all should return None."""
        assert normalize_phone("abc") is None
        assert normalize_phone("@c.us") is None
        assert normalize_phone("+-()") is None

    def test_jid_without_plus(self) -> None:
        """JID format without plus sign."""
        assert normalize_phone("1234567890@c.us") == "1234567890"
        assert normalize_phone("1234567890@s.whatsapp.net") == "1234567890"

    def test_device_suffix_stripped(self) -> None:
        """Device suffix after : is stripped regardless of JID suffix."""
        assert normalize_phone("+1234567890:99@s.whatsapp.net") == "1234567890"
        assert normalize_phone("+1234567890:99") == "1234567890"

    def test_empty_after_strip_returns_none(self) -> None:
        """Input that becomes empty after JID/device stripping returns None."""
        assert normalize_phone("@c.us") is None
        assert normalize_phone(":45@s.whatsapp.net") is None
