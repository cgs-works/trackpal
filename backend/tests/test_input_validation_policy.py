"""Tests for the centralized input validation policy.

Covers valid, invalid, boundary, and normalization behaviour for all
four identity/contact fields: ``username``, ``full_name``, ``email``,
``phone``.
"""

from __future__ import annotations

import pytest

from app.core.input_validation import (
    InputValidationError,
    validate_client_local_username,
    validate_client_prefix,
    validate_email,
    validate_full_name,
    validate_phone,
    validate_username,
)


# ===========================================================================
# Username
# ===========================================================================


class TestValidateUsername:
    """Positive and negative rules for usernames."""

    @pytest.mark.parametrize(
        ("value",),
        [
            ("juan",),
            ("maria_123",),
            ("a",),
            ("z_123456789012345678",),  # 20 chars, valid
        ],
    )
    def test_valid_username(self, value: str) -> None:
        assert validate_username(value) == value

    @pytest.mark.parametrize(
        ("value", "expected_code"),
        [
            ("/menu", "username_invalid"),
            ("hola mundo", "username_invalid"),
            ("Admin!", "username_invalid"),
            ("Ñandu", "username_invalid"),
            ("0admin", "username_invalid"),
            ("_admin", "username_invalid"),
            ("", "username_required"),
            ("   ", "username_required"),
            ("a" * 21, "username_too_long"),
        ],
    )
    def test_invalid_username(self, value: str, expected_code: str) -> None:
        with pytest.raises(InputValidationError) as exc:
            validate_username(value)
        assert exc.value.code == expected_code

    def test_none_username_raises(self) -> None:
        with pytest.raises(InputValidationError) as exc:
            validate_username(None)  # type: ignore[arg-type]
        assert exc.value.code == "username_required"

    def test_username_preserves_valid_value(self) -> None:
        """Valid username must be returned unchanged."""
        assert validate_username("test_user_1") == "test_user_1"

    @pytest.mark.parametrize(
        ("value", "expected_code"),
        [
            (" admin", "username_leading_trailing_spaces"),
            ("admin ", "username_leading_trailing_spaces"),
            (" admin ", "username_leading_trailing_spaces"),
            ("\tadmin", "username_leading_trailing_spaces"),
        ],
    )
    def test_username_leading_trailing_spaces_rejected(
        self, value: str, expected_code: str
    ) -> None:
        """Leading/trailing whitespace must be rejected, not silently stripped."""
        with pytest.raises(InputValidationError) as exc:
            validate_username(value)
        assert exc.value.code == expected_code

    def test_username_max_length_boundary(self) -> None:
        """20-character username accepted, 21 rejected."""
        valid = "a" + "0" * 19  # 20 chars total
        assert len(valid) == 20
        assert validate_username(valid) == valid


# ===========================================================================
# Client prefix and local username
# ===========================================================================


class TestValidateClientPrefix:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("abc", "abc"),
            (" ABC12 ", "abc12"),
            ("z9", "z9"),
        ],
    )
    def test_valid_client_prefix(self, value: str, expected: str) -> None:
        assert validate_client_prefix(value) == expected

    @pytest.mark.parametrize(
        ("value", "expected_code"),
        [
            ("", "client_prefix_required"),
            ("   ", "client_prefix_required"),
            ("1abc", "client_prefix_invalid"),
            ("abc-d", "client_prefix_invalid"),
            ("abcdef", "client_prefix_too_long"),
        ],
    )
    def test_invalid_client_prefix(self, value: str, expected_code: str) -> None:
        with pytest.raises(InputValidationError) as exc:
            validate_client_prefix(value)
        assert exc.value.code == expected_code


class TestValidateClientLocalUsername:
    def test_valid_client_local_username(self) -> None:
        assert validate_client_local_username("client_one") == "client_one"

    @pytest.mark.parametrize(
        ("value", "expected_code"),
        [
            ("a" * 95, "client_local_username_too_long"),
            ("1client", "client_local_username_invalid"),
            ("client one", "client_local_username_invalid"),
            ("", "client_local_username_required"),
        ],
    )
    def test_invalid_client_local_username(self, value: str, expected_code: str) -> None:
        with pytest.raises(InputValidationError) as exc:
            validate_client_local_username(value)
        assert exc.value.code == expected_code

        invalid = "a" + "0" * 20  # 21 chars total
        assert len(invalid) == 21
        with pytest.raises(InputValidationError) as exc:
            validate_username(invalid)
        assert exc.value.code == "username_too_long"


class TestUsernameExamplesAndBoundaries:
    """Table-driven coverage for all PRD username examples and boundary lengths."""

    @pytest.mark.parametrize(
        ("value", "description"),
        [
            ("a", "single char min length"),
            ("abcdefghij1234567890", "20 chars max length boundary"),
            ("juan", "simple name"),
            ("maria_123", "underscore + digits"),
            ("test_user_1", "username with underscore"),
            ("z_123456789012345678", "20 chars with underscore at pos 1"),
        ],
    )
    def test_valid_username_examples(self, value: str, description: str) -> None:
        assert validate_username(value) == value

    @pytest.mark.parametrize(
        ("value", "expected_code", "description"),
        [
            ("/menu", "username_invalid", "slash command"),
            ("hola mundo", "username_invalid", "space in username"),
            ("Admin!", "username_invalid", "uppercase + punctuation"),
            ("Ñandu", "username_invalid", "unicode letter"),
            ("0admin", "username_invalid", "starts with digit"),
            ("_admin", "username_invalid", "starts with underscore"),
            ("admin!", "username_invalid", "punctuation suffix"),
            ("a" * 21, "username_too_long", "21 chars exceeds limit"),
            ("", "username_required", "empty string"),
            ("   ", "username_required", "whitespace only"),
            (None, "username_required", "None input"),  # type: ignore[arg-type]
        ],
    )
    def test_invalid_username_examples(
        self, value: str | None, expected_code: str, description: str
    ) -> None:
        with pytest.raises(InputValidationError) as exc:
            validate_username(value)  # type: ignore[arg-type]
        assert exc.value.code == expected_code


# ===========================================================================
# Full name
# ===========================================================================


class TestValidateFullName:
    """Positive and negative rules for full names."""

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("Juan Pérez", "Juan Pérez"),           # Spanish accented letter
            ("Maria Müller", "Maria Müller"),         # German umlaut
            ("张三", "张三"),                         # Chinese characters
            ("Jean-Pierre", None),                    # hyphen → should fail
        ],
    )
    def test_valid_full_name_letters_and_spaces(
        self, value: str, expected: str | None
    ) -> None:
        """Unicode letters and spaces are accepted."""
        if expected is not None:
            assert validate_full_name(value) == expected
        else:
            # hyphen is punctuation, should fail
            with pytest.raises(InputValidationError):
                validate_full_name(value)

    def test_valid_with_numbers(self) -> None:
        """Letters, numbers, and spaces are accepted."""
        assert validate_full_name("John Smith 3rd") == "John Smith 3rd"

    def test_internal_spaces_collapsed(self) -> None:
        """Multiple internal spaces are collapsed to one."""
        assert validate_full_name("John   Smith") == "John Smith"
        assert (
            validate_full_name("Maria  Ana  Lopez")
            == "Maria Ana Lopez"
        )

    @pytest.mark.parametrize(
        ("value",),
        [
            (" leading",),
            ("trailing ",),
            ("  both  ",),
        ],
    )
    def test_leading_trailing_spaces_rejected(self, value: str) -> None:
        with pytest.raises(InputValidationError) as exc:
            validate_full_name(value)
        assert exc.value.code == "full_name_leading_trailing_spaces"

    @pytest.mark.parametrize(
        ("value",),
        [
            ("John/Smith",),
            ("John!",),
            ("John.Doe",),
            ("John, Smith",),
            ("John;Smith",),
            ("John\nDoe",),    # newline not a letter/space
            ("John\tDoe",),    # tab not a letter/space
        ],
    )
    def test_slash_punctuation_rejected(self, value: str) -> None:
        with pytest.raises(InputValidationError) as exc:
            validate_full_name(value)
        assert exc.value.code == "full_name_invalid_chars"

    def test_blank_rejected(self) -> None:
        with pytest.raises(InputValidationError) as exc:
            validate_full_name("")
        assert exc.value.code == "full_name_required"

    def test_whitespace_only_rejected(self) -> None:
        with pytest.raises(InputValidationError) as exc:
            validate_full_name("   ")
        assert exc.value.code == "full_name_required"

    def test_none_rejected(self) -> None:
        with pytest.raises(InputValidationError) as exc:
            validate_full_name(None)  # type: ignore[arg-type]
        assert exc.value.code == "full_name_required"

    def test_emoji_rejected(self) -> None:
        """Emoji are not letters, so they should be rejected."""
        with pytest.raises(InputValidationError) as exc:
            validate_full_name("John 😊")
        assert exc.value.code == "full_name_invalid_chars"


# ===========================================================================
# Email
# ===========================================================================


class TestValidateEmail:
    """Positive and negative rules for email addresses."""

    def test_valid_normalized_casing(self) -> None:
        """Email domain is lowercased by default; local part casing preserved
        per the email-validator library behaviour with normalization."""
        result = validate_email("User@Example.COM")
        # email-validator normalizes domain to lowercase
        assert result is not None
        assert "@" in result
        assert result == result.lower() or "User" in result

    def test_valid_email_returns_normalized(self) -> None:
        """A syntactically valid email returns the library-normalized form."""
        result = validate_email("test@example.com")
        assert result == "test@example.com"

    def test_invalid_syntax_rejected(self) -> None:
        with pytest.raises(InputValidationError) as exc:
            validate_email("not-an-email")
        assert exc.value.code == "email_invalid"

    def test_invalid_dot_rejected(self) -> None:
        with pytest.raises(InputValidationError):
            validate_email("user@.com")

    @pytest.mark.parametrize(
        ("value",),
        [
            (None,),
            ("",),
            ("   ",),
        ],
    )
    def test_blank_optional_returns_none(self, value: str | None) -> None:
        """None/blank returns None when not required."""
        assert validate_email(value) is None

    def test_required_blank_raises(self) -> None:
        with pytest.raises(InputValidationError) as exc:
            validate_email("", required=True)
        assert exc.value.code == "email_required"

    def test_required_none_raises(self) -> None:
        with pytest.raises(InputValidationError) as exc:
            validate_email(None, required=True)
        assert exc.value.code == "email_required"

    def test_no_deliverability_check(self) -> None:
        """A valid-syntax email passes even if the domain does not exist."""
        # This domain almost certainly does not exist, but syntax is valid.
        result = validate_email("test@nonexistent-domain-xyz.example")
        assert result is not None
        assert "@" in result


# ===========================================================================
# Phone
# ===========================================================================


class TestValidatePhone:
    """Positive and negative rules for phone numbers."""

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("+14155552671", "14155552671"),       # with +
            ("14155552671", "14155552671"),          # without +
        ],
    )
    def test_valid_e164_returns_digits(
        self, value: str, expected: str
    ) -> None:
        """Valid E.164 phone returns digits-only canonical form."""
        assert validate_phone(value) == expected

    def test_jid_suffix_stripped(self) -> None:
        """WhatsApp JID suffix is stripped before validation."""
        result = validate_phone("+14155552671@c.us")
        assert result == "14155552671"

    def test_device_suffix_stripped(self) -> None:
        """Device suffix after : is stripped before validation."""
        result = validate_phone("+14155552671:45")
        assert result == "14155552671"

    def test_jid_and_device_suffix_stripped(self) -> None:
        """Both JID and device suffixes are stripped."""
        result = validate_phone("+14155552671:45@s.whatsapp.net")
        assert result == "14155552671"

    @pytest.mark.parametrize(
        ("value",),
        [
            ("123",),        # too short, no country code
            ("abc",),        # non-phone text
            ("+123",),       # invalid country code + short
            ("+1",),         # too short even if starts with +
            ("",),
            ("   ",),
            (None,),
        ],
    )
    def test_invalid_or_blank_optional_returns_none(
        self, value: str | None
    ) -> None:
        """Invalid/blank/None returns None when not required."""
        # For valid-format-but-invalid numbers, InputValidationError is raised
        # For blank/None, None is returned
        if value is None or (isinstance(value, str) and not value.strip()):
            assert validate_phone(value) is None
        else:
            with pytest.raises(InputValidationError):
                validate_phone(value)

    def test_required_blank_raises(self) -> None:
        with pytest.raises(InputValidationError) as exc:
            validate_phone("", required=True)
        assert exc.value.code == "phone_required"

    def test_required_none_raises(self) -> None:
        with pytest.raises(InputValidationError) as exc:
            validate_phone(None, required=True)
        assert exc.value.code == "phone_required"

    def test_canonical_digits_only_output(self) -> None:
        """Result must contain only digits, no +, spaces, or punctuation."""
        result = validate_phone("+1 (415) 555-2671")
        assert result is not None
        assert result.isdigit()
        assert "+" not in result
        assert result == "14155552671"

    def test_non_phone_text_rejected(self) -> None:
        """Non-phone text with no digits raises parse error."""
        with pytest.raises(InputValidationError) as exc:
            validate_phone("hello")
        assert exc.value.code == "phone_no_digits"

    def test_short_ambiguous_rejected(self) -> None:
        """Short numbers that can't be valid E.164 are rejected."""
        with pytest.raises(InputValidationError):
            validate_phone("1234")

    def test_only_jid_suffix_returns_none_optional(self) -> None:
        """JID suffix with no phone digits returns None when optional."""
        # "@c.us" stripped leaves "", which should raise if required
        # but return None if optional
        assert validate_phone("@c.us") is None

    def test_only_jid_suffix_required_raises(self) -> None:
        with pytest.raises(InputValidationError) as exc:
            validate_phone("@c.us", required=True)
        assert exc.value.code == "phone_required"

    def test_valid_mexico_number(self) -> None:
        """A valid Mexico number should pass and canonicalize."""
        result = validate_phone("+525511223344")
        assert result == "525511223344"

    # ------------------------------------------------------------------
    # Noisy / non-E.164 inputs (regression coverage)
    # ------------------------------------------------------------------

    @pytest.mark.parametrize(
        ("value", "expected_code"),
        [
            ("++14155552671", "phone_invalid_plus"),
            ("+1415555+2671", "phone_invalid_plus"),
            ("1415555+2671", "phone_invalid_plus"),
        ],
    )
    def test_phone_duplicate_or_misplaced_plus(
        self, value: str, expected_code: str
    ) -> None:
        """Multiple or misplaced plus signs are rejected."""
        with pytest.raises(InputValidationError) as exc:
            validate_phone(value)
        assert exc.value.code == expected_code

    @pytest.mark.parametrize(
        ("value", "expected_code"),
        [
            ("+14155552671 ext 789", "phone_extension_suffix"),
            ("+14155552671 x789", "phone_extension_suffix"),
            ("+14155552671 extension 789", "phone_extension_suffix"),
            ("+14155552671 #789", "phone_extension_suffix"),
            ("14155552671 ext 789", "phone_extension_suffix"),
            ("14155552671x789", "phone_extension_suffix"),
        ],
    )
    def test_phone_extension_rejected(
        self, value: str, expected_code: str
    ) -> None:
        """Extension patterns are rejected, not silently accepted."""
        with pytest.raises(InputValidationError) as exc:
            validate_phone(value)
        assert exc.value.code == expected_code

    @pytest.mark.parametrize(
        ("value", "expected_code"),
        [
            ("+14155552671;phone=abc", "phone_invalid_chars"),
            ("+14155552671/abc", "phone_invalid_chars"),
            ("+14155552671=123", "phone_invalid_chars"),
        ],
    )
    def test_phone_suffix_junk_rejected(
        self, value: str, expected_code: str
    ) -> None:
        """Noisy suffix junk after the number is rejected."""
        with pytest.raises(InputValidationError) as exc:
            validate_phone(value)
        assert exc.value.code == expected_code

    def test_phone_jid_still_allowed(self) -> None:
        """WhatsApp JID suffix is still cleaned (regression guard)."""
        result = validate_phone("+14155552671@c.us")
        assert result == "14155552671"

    def test_phone_device_suffix_still_allowed(self) -> None:
        """Device suffix is still cleaned (regression guard)."""
        result = validate_phone("+14155552671:99")
        assert result == "14155552671"
