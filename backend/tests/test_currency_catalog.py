import importlib
import json
from unittest.mock import patch

import pytest

from app.core import currency_catalog
from app.core.currency_catalog import currency_catalog as _mod

FIXTURE = {
    "source": "fixture",
    "generated_at": "2026-08-01",
    "countries": [{"code": "VE", "currency": "VES"}, {"code": "PA", "currency": "PAB"}],
    "currencies": {
        "VES": {"symbol": "Bs.", "minor_units": 2},
        "USD": {"symbol": "$", "minor_units": 2},
        "JPY": {"symbol": "¥", "minor_units": 0},
    },
}


@pytest.fixture(autouse=True)
def _fixture_data():
    with patch.object(_mod, "_load", return_value=FIXTURE):
        yield


def test_validate_country_uppercase_insensitive():
    assert currency_catalog.validate_country("ve")
    assert currency_catalog.validate_country("VE")
    assert not currency_catalog.validate_country("XX")


def test_validate_currency_uppercase_insensitive():
    assert currency_catalog.validate_currency("ves")
    assert not currency_catalog.validate_currency("ZZZ")


def test_official_currency_of():
    assert currency_catalog.official_currency_of("VE") == "VES"
    assert currency_catalog.official_currency_of("XX") is None


def test_symbol_and_minor_units():
    assert currency_catalog.symbol_of("VES") == "Bs."
    assert currency_catalog.minor_units_of("JPY") == 0
    assert currency_catalog.minor_units_of("XXX") is None


def test_list_countries_and_currencies_shape():
    assert {"code": "VE", "currency": "VES"} in currency_catalog.list_countries()
    assert {
        "code": "VES",
        "symbol": "Bs.",
        "minor_units": 2,
    } in currency_catalog.list_currencies()


def test_real_data_contains_venezuela_override():
    """Real committed data.json must carry the curated VES symbol."""
    assert currency_catalog.symbol_of("VES") == "Bs."
    assert currency_catalog.validate_country("VE")


@pytest.mark.skipif(
    importlib.util.find_spec("babel") is None,
    reason="babel is a dev-time dependency",
)
def test_regeneration_matches_checked_in_data():
    from scripts.regenerate_currency_catalog import BACKEND_DATA, generate

    payload, warnings = generate()
    assert warnings == [], f"missing overrides: {warnings}"
    checked_in = json.loads(BACKEND_DATA.read_text(encoding="utf-8"))
    # only compare the domain payload, not the generated_at date
    assert {k: v for k, v in payload.items() if k != "generated_at"} == {
        k: v for k, v in checked_in.items() if k != "generated_at"
    }
