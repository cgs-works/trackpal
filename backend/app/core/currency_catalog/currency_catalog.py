"""Currency Catalog — bundled countries/currencies from Unicode CLDR + curated overrides.

Single source of truth for validating Country (ISO 3166-1 alpha-2) and
Currency (ISO 4217) codes and for resolving official currency, symbols and
minor units. Data is generated dev-time (see scripts/regenerate_currency_catalog.py)
and committed; never queried at runtime.
"""

import json
from functools import lru_cache
from pathlib import Path

_DATA_PATH = Path(__file__).resolve().parent / "data.json"


@lru_cache(maxsize=1)
def _load() -> dict:
    with _DATA_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def _country_codes() -> frozenset[str]:
    return frozenset(c["code"] for c in _load()["countries"])


def _currency_codes() -> frozenset[str]:
    return frozenset(_load()["currencies"])


def list_countries() -> list[dict[str, str]]:
    return [dict(c) for c in _load()["countries"]]


def list_currencies() -> list[dict[str, object]]:
    return [
        {
            "code": code,
            "symbol": meta["symbol"],
            "minor_units": meta["minor_units"],
        }
        for code, meta in _load()["currencies"].items()
    ]


def official_currency_of(country_code: str) -> str | None:
    for c in _load()["countries"]:
        if c["code"] == country_code:
            return c["currency"]
    return None


def symbol_of(currency_code: str) -> str | None:
    return _load()["currencies"].get(currency_code, {}).get("symbol")


def minor_units_of(currency_code: str) -> int | None:
    return _load()["currencies"].get(currency_code, {}).get("minor_units")


def validate_country(code: str) -> bool:
    return code.upper() in _country_codes()


def validate_currency(code: str) -> bool:
    return code.upper() in _currency_codes()
