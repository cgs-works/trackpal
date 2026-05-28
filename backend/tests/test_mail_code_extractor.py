"""Tests for mail code extraction — catalog + pure extractor.

Covers all 6 services (Netflix, Disney+, HBO Max, Spotify, Universal+,
Prime Video), subject matching, body normalisation, edge cases, and
multi-email newest-valid selection.
"""

import re
from datetime import datetime, timedelta, timezone

import pytest

from app.services.mail_code_extractor import (
    ExtractedCode,
    ParsedEmail,
    get_service_entry,
    normalize_body,
    match_subject,
    extract_from_body,
    extract_newest_from_emails,
)
from app.services.mail_code_extractor.catalog_v1 import CATALOG_V1

# ── Constants ─────────────────────────────────────────────────────────────


# Convenient sample codes (not real ones)
CODE_4 = "7392"
CODE_6 = "482910"
CODE_6_ALT = "615083"
CODE_6_ALT2 = "937201"
TOKEN = (
    "eyJhbGciOiJIUzI1NiJ9"
    ".eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jFWfOHTw8NZ1ZxTNR7KsqsAK2T2F6fU"
)
URL = f"https://www.netflix.com/account/travel/verify?nftoken={TOKEN}"
UNIVERSAL_CODE = "XK4M9P"
SPOTIFY_CODE = "291846"


# ── Fixtures ──────────────────────────────────────────────────────────────


def _email(subject: str, body: str, ago_minutes: int = 0) -> ParsedEmail:
    return ParsedEmail(
        subject=subject,
        body=body,
        received_at=datetime.now(timezone.utc) - timedelta(minutes=ago_minutes),
    )


# =====================================================================
# Subject matching
# =====================================================================


class TestMatchSubject:
    def test_known_service_match(self):
        assert match_subject("Tu código de inicio de sesión", "netflix") is True

    def test_known_service_no_match(self):
        assert match_subject("Random email subject", "netflix") is False

    def test_unknown_service_key(self):
        assert match_subject("Tu código de inicio de sesión", "nonexistent") is False

    def test_partial_match(self):
        assert (
            match_subject(
                "Re: Fwd: Tu código de acceso temporal de Netflix - importante",
                "netflix",
            )
            is True
        )

    def test_disney_match(self):
        assert match_subject("Tu código de acceso único para Disney+", "disney") is True

    def test_hbo_match(self):
        assert (
            match_subject("Urgente: Tu código de un solo uso de HBO Max", "hbo_max")
            is True
        )
        assert (
            match_subject("Urgente: Tu código de un solo uso de Max", "hbo_max") is True
        )

    def test_spotify_match(self):
        assert match_subject("Tu código de inicio de sesión de Spotify:", "spotify")
        assert match_subject("Your Spotify login code", "spotify")

    @pytest.mark.parametrize(
        "subject",
        [
            "Universal+ código de activación",
            "Universal+ código de activación (re: subscription)",
            "Re: Universal+ código de activación",
        ],
    )
    def test_universal_match(self, subject):
        assert match_subject(subject, "universal_plus")

    @pytest.mark.parametrize(
        "subject",
        [
            "amazon.com: Intento de inicio de sesión",
            "amazon.com.mx: Intento de inicio de sesión",
            "amazon.com: Sign-in attempt",
        ],
    )
    def test_prime_match(self, subject):
        assert match_subject(subject, "prime_video")

    def test_wrong_service_does_not_match(self):
        """Netflix subject should not match Disney catalog."""
        assert (
            match_subject("Tu código de acceso temporal de Netflix", "disney") is False
        )


# =====================================================================
# Body normalisation
# =====================================================================


class TestNormalizeBody:
    def test_disney_strips_whitespace(self):
        body = "<td style='mso-line-height-rule: exactly;'> 482910 </td>"
        normalized = normalize_body(body, "disney")
        assert " " not in normalized
        assert "\n" not in normalized
        assert "\r" not in normalized
        assert "482910" in normalized

    def test_hbo_collapses_whitespace(self):
        body = "Tu  código  de  un  solo  uso\n\n\n482910"
        normalized = normalize_body(body, "hbo_max")
        assert "  " not in normalized
        assert "\n" not in normalized
        assert "482910" in normalized

    def test_hbo_preserves_single_spaces(self):
        body = "Tu código de un solo uso - 482910"
        assert normalize_body(body, "hbo_max") == body

    def test_unknown_service_no_change(self):
        body = "<html><body>Some email body</body></html>"
        assert normalize_body(body, "nonexistent") == body

    def test_netflix_no_normalization(self):
        body = "Some Netflix email body"
        assert normalize_body(body, "netflix") == body


# =====================================================================
# Extraction — Netflix
# =====================================================================


class TestExtractNetflix:
    def test_travel_verify_url_markdown(self):
        body = f"Click here: [{URL}]({URL}) to verify your account."
        result = extract_from_body(body, "netflix")
        assert result is not None
        assert result.value == URL
        assert result.result_type == "url"
        assert result.service_key == "netflix"

    def test_travel_verify_url_html(self):
        body = f'<a href="{URL}">Verify</a>'
        result = extract_from_body(body, "netflix")
        assert result is not None
        assert result.value == URL
        assert result.result_type == "url"

    def test_four_digit_signin_es(self):
        body = (
            "Escribe este código para iniciar sesión\r\n\r\n"
            "Escribe este código para iniciar sesión\r\n\r\n"
            f"{CODE_4}\r\n\r\n"
        )
        result = extract_from_body(body, "netflix")
        assert result is not None
        assert result.value == CODE_4
        assert result.result_type == "code"

    def test_six_digit_account_change_es(self):
        body = (
            f"Confirma el cambio en tu cuenta con este código:\r\n\r\n{CODE_6}\r\n\r\n"
        )
        result = extract_from_body(body, "netflix")
        assert result is not None
        assert result.value == CODE_6
        assert result.result_type == "code"

    def test_six_digit_account_change_en(self):
        body = (
            f"Confirm your account change with this code:\r\n\r\n{CODE_6_ALT}\r\n\r\n"
        )
        result = extract_from_body(body, "netflix")
        assert result is not None
        assert result.value == CODE_6_ALT
        assert result.result_type == "code"

    def test_access_attempt_code(self):
        body = f"Código de verificación:\r\n\r\n{CODE_6_ALT2}\r\n\r\n"
        result = extract_from_body(body, "netflix")
        assert result is not None
        assert result.value == CODE_6_ALT2
        assert result.result_type == "code"

    def test_four_digit_html_inline_style(self):
        body = (
            '<table><tr><td style="font-size: 28px; line-height: 32px; '
            "letter-spacing: 6px; font-family: NetflixSans-Regular, Helvetica, "
            "Roboto, Segoe UI, sans-serif; font-weight: 400; padding-top: 20px; "
            f'color: #221f1f;"> {CODE_4} </td></tr></table>'
        )
        result = extract_from_body(body, "netflix")
        assert result is not None
        assert result.value == CODE_4
        assert result.result_type == "code"

    def test_no_match_returns_none(self):
        body = "This email body has no code whatsoever 123"
        result = extract_from_body(body, "netflix")
        assert result is None


# =====================================================================
# Extraction — Disney+
# =====================================================================


class TestExtractDisney:
    def test_td_inline_style(self):
        body = f'<td style="mso-line-height-rule: exactly;"> {CODE_6} </td>'
        normalized = normalize_body(body, "disney")
        result = extract_from_body(normalized, "disney")
        assert result is not None
        assert result.value == CODE_6
        assert result.result_type == "code"

    def test_td_mso_line_height(self):
        body = (
            '<td style="line-height:38px; mso-line-height-rule: exactly;">'
            f" {CODE_6_ALT} </td>"
        )
        normalized = normalize_body(body, "disney")
        result = extract_from_body(normalized, "disney")
        assert result is not None
        assert result.value == CODE_6_ALT

    def test_no_code_returns_none(self):
        body = "<td>Some random content</td>"
        normalized = normalize_body(body, "disney")
        result = extract_from_body(normalized, "disney")
        assert result is None


# =====================================================================
# Extraction — HBO Max
# =====================================================================


class TestExtractHboMax:
    def test_inline_one_time_code(self):
        body = f"Tu código de un solo uso - {CODE_6}"
        result = extract_from_body(body, "hbo_max")
        assert result is not None
        assert result.value == CODE_6
        assert result.result_type == "code"

    def test_utiliza_este_codigo(self):
        body = (
            "Utiliza este código para iniciar sesión en tu cuenta de Max.\n\n"
            f"Tu código de un solo uso: {CODE_6}"
        )
        result = extract_from_body(body, "hbo_max")
        assert result is not None
        assert result.value == CODE_6

    def test_code_standalone_line(self):
        body = f"\n\n{CODE_6_ALT}\n\nSome other text"
        result = extract_from_body(body, "hbo_max")
        assert result is not None
        assert result.value == CODE_6_ALT

    def test_code_with_extra_whitespace(self):
        body = f"Tu  código  de  un  solo  uso      {CODE_6}"
        result = extract_from_body(body, "hbo_max")
        assert result is not None
        assert result.value == CODE_6

    def test_no_code_returns_none(self):
        body = "This Max email has no code inside"
        result = extract_from_body(body, "hbo_max")
        assert result is None


# =====================================================================
# Extraction — Spotify
# =====================================================================


class TestExtractSpotify:
    def test_code_after_colon_es(self):
        body = f"Tu código de inicio de sesión de Spotify: {SPOTIFY_CODE}"
        result = extract_from_body(body, "spotify")
        assert result is not None
        assert result.value == SPOTIFY_CODE
        assert result.result_type == "code"

    def test_code_after_es(self):
        body = f"Tu código de inicio de sesión de Spotify es {SPOTIFY_CODE}"
        result = extract_from_body(body, "spotify")
        assert result is not None
        assert result.value == SPOTIFY_CODE

    def test_ingresa_este_codigo(self):
        body = f"Ingresa este código en la pantalla de inicio de sesión: {CODE_6}"
        result = extract_from_body(body, "spotify")
        assert result is not None
        assert result.value == CODE_6

    def test_code_before_valid_text_es(self):
        body = f"{CODE_6_ALT} Este código es válido por 5 minutos"
        result = extract_from_body(body, "spotify")
        assert result is not None
        assert result.value == CODE_6_ALT

    def test_code_before_label_en(self):
        body = f"{CODE_6} - Your Spotify login code"
        result = extract_from_body(body, "spotify")
        assert result is not None
        assert result.value == CODE_6

    def test_enter_this_code_en(self):
        body = f"Enter this code on the login screen: {SPOTIFY_CODE}"
        result = extract_from_body(body, "spotify")
        assert result is not None
        assert result.value == SPOTIFY_CODE

    def test_code_before_valid_text_en(self):
        body = f"{CODE_6_ALT2} This code is valid for 5 minutes"
        result = extract_from_body(body, "spotify")
        assert result is not None
        assert result.value == CODE_6_ALT2

    def test_no_code_returns_none(self):
        body = "Welcome to Spotify! Enjoy your premium subscription."
        result = extract_from_body(body, "spotify")
        assert result is None


# =====================================================================
# Extraction — Universal+
# =====================================================================


class TestExtractUniversalPlus:
    def test_activation_code_in_strong_html(self):
        body = f"<p>código de activación</p><strong>{UNIVERSAL_CODE}</strong>"
        result = extract_from_body(body, "universal_plus")
        assert result is not None
        assert result.value == UNIVERSAL_CODE
        assert result.result_type == "code"

    def test_any_strong_with_code(self):
        body = f"<strong>{UNIVERSAL_CODE}</strong>"
        result = extract_from_body(body, "universal_plus")
        assert result is not None
        assert result.value == UNIVERSAL_CODE

    def test_standalone_line(self):
        body = f"\n{UNIVERSAL_CODE}\n"
        result = extract_from_body(body, "universal_plus")
        assert result is not None
        assert result.value == UNIVERSAL_CODE

    def test_activation_text_generic(self):
        body = (
            "código de activación\n"
            "Gracias por tu compra. Usa este código para activar:\n"
            f"{UNIVERSAL_CODE}"
        )
        result = extract_from_body(body, "universal_plus")
        assert result is not None
        assert result.value == UNIVERSAL_CODE

    def test_no_code_returns_none(self):
        body = "Thank you for subscribing to Universal+!"
        result = extract_from_body(body, "universal_plus")
        assert result is None


# =====================================================================
# Extraction — Prime Video
# =====================================================================


class TestExtractPrimeVideo:
    def test_verification_text_es(self):
        body = f"Tu código de verificación es: {CODE_6}"
        result = extract_from_body(body, "prime_video")
        assert result is not None
        assert result.value == CODE_6
        assert result.result_type == "code"

    def test_background_color_pattern(self):
        body = (
            '<table><tr><td style="background-color: #D3D3D3;">'
            f" {CODE_6_ALT} </td></tr></table>"
        )
        result = extract_from_body(body, "prime_video")
        assert result is not None
        assert result.value == CODE_6_ALT

    def test_standalone_line(self):
        body = f"\n{CODE_6}\n"
        result = extract_from_body(body, "prime_video")
        assert result is not None
        assert result.value == CODE_6

    def test_generic_codigo_fallback(self):
        body = f"Su código de verificación es el siguiente {CODE_6_ALT2}"
        result = extract_from_body(body, "prime_video")
        assert result is not None
        assert result.value == CODE_6_ALT2

    def test_no_code_returns_none(self):
        body = "Your Amazon order has been shipped!"
        result = extract_from_body(body, "prime_video")
        assert result is None


# =====================================================================
# Extraction — subject-scoped
# =====================================================================


class TestExtractWithSubject:
    def test_matching_subject_extracts(self):
        body = f"Código de verificación:\r\n\r\n{CODE_6}\r\n\r\n"
        result = extract_from_body(
            body,
            "netflix",
            subject="Tu código de verificación",
        )
        assert result is not None
        assert result.value == CODE_6

    def test_non_matching_subject_skips(self):
        """When subject doesn't match service, extraction is skipped."""
        result = extract_from_body(
            "<strong>ABC123</strong>",
            "netflix",
            subject="Your Disney+ one-time passcode",
        )
        assert result is None

    def test_body_has_code_but_wrong_subject(self):
        """Even if body contains a code, wrong subject → skip extraction."""
        result = extract_from_body(
            "Tu código de inicio de sesión de Spotify: 291846",
            "spotify",
            subject="amazon.com: Sign-in attempt",
        )
        assert result is None


# =====================================================================
# Multi-email newest-valid extraction
# =====================================================================


class TestExtractNewestFromEmails:
    def test_newest_valid_wins(self):
        emails = [
            _email("Random email", "No code here", ago_minutes=3),
            _email(
                "Tu código de inicio de sesión de Spotify:",
                f"Tu código de inicio de sesión de Spotify: {CODE_6}",
                ago_minutes=1,
            ),
            _email(
                "Your Spotify login code",
                f"Enter this code on the login screen: {CODE_6_ALT}",
                ago_minutes=0,
            ),
        ]
        result = extract_newest_from_emails(emails, "spotify")
        assert result is not None
        assert result.value == CODE_6_ALT  # newest match

    def test_only_code_in_window_counts(self):
        emails = [
            _email(
                "Tu código de inicio de sesión de Spotify:",
                f"Tu código de inicio de sesión de Spotify: {CODE_6}",
                ago_minutes=10,  # outside 5-min window
            ),
        ]
        result = extract_newest_from_emails(emails, "spotify")
        assert result is None

    def test_no_valid_emails_returns_none(self):
        emails = [
            _email("Random email", "Some random body", ago_minutes=1),
            _email("Another email", "No codes anywhere", ago_minutes=0),
        ]
        result = extract_newest_from_emails(emails, "netflix")
        assert result is None

    def test_empty_list(self):
        result = extract_newest_from_emails([], "netflix")
        assert result is None

    def test_multiple_services_isolated(self):
        """Extraction for one service does not match codes from another."""
        emails = [
            _email(
                "Tu código de acceso temporal de Netflix",
                f"Código de verificación:\r\n\r\n{CODE_6}\r\n\r\n",
                ago_minutes=0,
            ),
        ]
        # Looking for Spotify in a Netflix email → nothing
        result = extract_newest_from_emails(emails, "spotify")
        assert result is None

    def test_newest_url_over_older_code(self):
        """URL result takes precedence when it's the newest match."""
        body = f"[{URL}]({URL})"
        result = extract_from_body(
            body,
            "netflix",
            subject="Tu código de acceso temporal de Netflix",
        )
        assert result is not None
        assert result.result_type == "url"


# =====================================================================
# Edge cases
# =====================================================================


class TestEdgeCases:
    def test_empty_body(self):
        result = extract_from_body("", "netflix")
        assert result is None

    def test_body_with_only_whitespace(self):
        result = extract_from_body("   \n   \n  ", "netflix")
        assert result is None

    def test_unknown_service_key(self):
        result = extract_from_body("Any body", "unknown_service")
        assert result is None

    def test_catalog_has_expected_services(self):
        assert "netflix" in CATALOG_V1
        assert "disney" in CATALOG_V1
        assert "hbo_max" in CATALOG_V1
        assert "spotify" in CATALOG_V1
        assert "universal_plus" in CATALOG_V1
        assert "prime_video" in CATALOG_V1

    def test_every_service_has_subject_patterns(self):
        for key, entry in CATALOG_V1.items():
            assert len(entry["subject_patterns"]) > 0, f"{key} has no subject patterns"

    def test_every_service_has_extraction_rules(self):
        for key, entry in CATALOG_V1.items():
            assert len(entry["extraction_rules"]) > 0, f"{key} has no extraction rules"

    def test_every_extraction_rule_compiles(self):
        for key, entry in CATALOG_V1.items():
            for rule in entry["extraction_rules"]:
                try:
                    re.compile(rule["regex"])
                except re.error as e:
                    pytest.fail(
                        f"Regex in {key} rule '{rule['desc']}' failed to compile: {e}"
                    )

    def test_all_rules_have_valid_type(self):
        for key, entry in CATALOG_V1.items():
            for rule in entry["extraction_rules"]:
                assert rule["type"] in ("code", "url"), (
                    f"Invalid type '{rule['type']}' in {key}"
                )

    def test_get_service_entry_known(self):
        entry = get_service_entry("netflix")
        assert entry is not None
        assert entry["service_name"] == "Netflix"

    def test_get_service_entry_unknown(self):
        assert get_service_entry("nonexistent") is None

    def test_extracted_code_named_tuple(self):
        code = ExtractedCode("123456", "code", "netflix")
        assert code.value == "123456"
        assert code.result_type == "code"
        assert code.service_key == "netflix"
        v, t, k = code  # unpacking
        assert v == "123456"
        assert t == "code"
        assert k == "netflix"


# =====================================================================
# Regression — legacy compatibility
# =====================================================================


class TestLegacyCompatibility:
    """Ensure migrated patterns still match the same inputs as the legacy bot."""

    def test_netflix_legacy_subject(self):
        """Legacy subjects.py had 'Tu código de acceso temporal de Netflix'."""
        assert match_subject("Tu código de acceso temporal de Netflix", "netflix")

    def test_disney_legacy_subject(self):
        assert match_subject("Your one-time passcode for Disney+", "disney")

    def test_hbo_legacy_subject(self):
        assert match_subject("Urgente: Tu código de un solo uso de Max", "hbo_max")

    def test_spotify_legacy_subject_arabic(self):
        """Arabic subject from legacy list."""
        assert match_subject("Your Spotify login code", "spotify")

    def test_prime_legacy_subject_english(self):
        assert match_subject("amazon.com: Sign-in attempt", "prime_video")

    def test_universal_plus_exact_subject(self):
        assert match_subject("Universal+ código de activación", "universal_plus")

    def test_all_regexes_match_at_least_one_test_case(self):
        """Every regex must match at least one known positive sample."""
        positive_cases = {
            "netflix": [
                f"[{URL}]",
                f'<a href="{URL}">Verify</a>',
                f'"{URL}"',
                f"Escribe este código para iniciar sesión\n\n{CODE_4}",
                f"Ingresa este código para iniciar sesión\n\n{CODE_4}",
                f"Enter this code to sign in\n\n{CODE_4}",
                f'<td style="font-size: 28px; line-height: 32px; letter-spacing: 6px; font-family: NetflixSans-Regular, Helvetica, Roboto, Segoe UI, sans-serif; font-weight: 400; padding-top: 20px; color: #221f1f;">{CODE_4}</td>',
                f"Confirma el cambio en tu cuenta con este código:\n\n{CODE_6}",
                f"Confirma el cambio de cuenta con este código:\n\n{CODE_6}",
                f"Confirm your account change with this code:\n\n{CODE_6}",
                f"Código de verificación:\n\n{CODE_6}",
            ],
            "disney": [
                f'<td style="x"> {CODE_6} </td>',
                f"token {CODE_6} body",
            ],
            "hbo_max": [
                f"Tu código de un solo uso - {CODE_6}",
                f"Utiliza este código para iniciar sesión en tu cuenta de Max. Tu código de un solo uso: {CODE_6}",
                f"\n\n{CODE_6}\n\n",
            ],
            "spotify": [
                f"Enter this code on the login screen: {SPOTIFY_CODE}",
                f"Tu código de inicio de sesión de Spotify: {CODE_6}",
                f"Tu código de inicio de sesión de Spotify es {CODE_6}",
                f"Ingresa este código en la pantalla de inicio de sesión: {CODE_6}",
                f"{CODE_6} Este código es válido por 5 minutos",
                f"{CODE_6} - Your Spotify login code",
                f"{CODE_6} This code is valid for 5 minutes",
            ],
            "universal_plus": [
                f"<p>código de activación</p><strong>{UNIVERSAL_CODE}</strong>",
                f"<strong>{UNIVERSAL_CODE}</strong>",
                f"\n{UNIVERSAL_CODE}\n",
                f"código de activación usa {UNIVERSAL_CODE}",
            ],
            "prime_video": [
                f"Tu código de verificación es: {CODE_6}",
                f'<td style="background-color: #D3D3D3;"> {CODE_6} </td>',
                f"\n{CODE_6}\n",
            ],
        }

        for key, entry in CATALOG_V1.items():
            samples = positive_cases.get(key, [])
            assert samples, f"No positive samples configured for {key}"
            for rule in entry["extraction_rules"]:
                pattern = re.compile(rule["regex"])
                assert any(pattern.search(sample) for sample in samples), (
                    f"Regex '{rule['desc']}' in {key} has no matching positive sample"
                )
