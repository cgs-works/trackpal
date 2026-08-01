"""Regenerate currency catalog data files from Unicode CLDR (dev-time only).

Run:  cd backend && uv run --with babel python -m scripts.regenerate_currency_catalog

Emits:
  backend/app/core/currency_catalog/data.json
  frontend/src/lib/currency-catalog.json   (demo workspace copy)
Symbols fall back to the curated overrides file first, then CLDR. Territories
with several current currencies use the per-territory national-currency map.
"""

import json
import sys
from pathlib import Path

BACKEND_DATA = (
    Path(__file__).resolve().parents[1]
    / "app"
    / "core"
    / "currency_catalog"
    / "data.json"
)
FRONTEND_DATA = (
    Path(__file__).resolve().parents[2]
    / "frontend"
    / "src"
    / "lib"
    / "currency-catalog.json"
)
OVERRIDES = (
    Path(__file__).resolve().parents[1]
    / "app"
    / "core"
    / "currency_catalog"
    / "overrides.json"
)

# Territories with more than one legal tender where the national currency
# is not the shared anchor (USD/EUR/INR/ZAR/ILS/JOD). Deterministic and reviewable.
_NATIONAL_CURRENCY: dict[str, str] = {
    "BT": "BTN",
    "HT": "HTG",
    "LS": "LSL",
    "NA": "NAD",
    "PA": "PAB",
    "PS": "ILS",
    "ZW": "ZWG",
}


def generate() -> tuple[dict, list[str]]:
    from babel.core import get_global  # dev-time dependency only

    territory_currencies = get_global("territory_currencies")
    currency_fractions = get_global("currency_fractions")
    locale_en = _load_babel_locale()

    with OVERRIDES.open(encoding="utf-8") as fh:
        overrides = json.load(fh)

    countries: list[dict[str, str]] = []
    currencies: dict[str, dict] = {}
    warnings: list[str] = []

    for territory, entries in territory_currencies.items():
        if len(territory) != 2 or not territory.isalpha():
            continue
        current = [
            code for code, _start, end, tender in entries if end is None and tender
        ]
        if not current:
            continue
        currency = _NATIONAL_CURRENCY.get(territory, current[0])
        countries.append({"code": territory, "currency": currency})

    for currency in sorted({c["currency"] for c in countries}):
        frac = currency_fractions.get(currency)
        minor_units = frac[0] if frac is not None else 2
        symbol = overrides.get(currency, {}).get("symbol")
        if symbol is None:
            symbol = locale_en.currency_symbols.get(currency)
        if not symbol or symbol == currency:
            warnings.append(
                f"{currency}: no curated symbol (override it in overrides.json)"
            )
            symbol = symbol or ""
        currencies[currency] = {"symbol": symbol, "minor_units": minor_units}

    return {
        "source": "Unicode CLDR",
        "generated_at": _today(),
        "countries": countries,
        "currencies": currencies,
    }, warnings


def _load_babel_locale():
    from babel import Locale

    return Locale.parse("en")


def _today() -> str:
    import datetime

    return datetime.date.today().isoformat()


def main() -> None:
    payload, warnings = generate()
    for w in warnings:
        print(f"WARN {w}")
    for path in (BACKEND_DATA, FRONTEND_DATA):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(f"wrote {path}")
    if warnings:
        sys.exit(2)


if __name__ == "__main__":
    main()
