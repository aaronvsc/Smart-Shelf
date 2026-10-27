"""Filter 1 - Parse & Normalize: clean names and units with the Ingredient Dictionary."""
from __future__ import annotations

import difflib
import math
from datetime import date

from smart_shelf.arch_a.config import TYPO_CUTOFF
from smart_shelf.arch_a.filter_base import Filter
from smart_shelf.arch_a.inputs import Ingredient, PantryItem, ReferenceData
from smart_shelf.arch_a.records import NormalizedPantry, UnrecognizedItem

UNIT_ALIASES = {
    "gram": "g", "grams": "g", "gr": "g",
    "kilogram": "kg", "kilograms": "kg", "kgs": "kg",
    "milliliter": "ml", "milliliters": "ml", "millilitre": "ml", "millilitres": "ml",
    "liter": "l", "liters": "l", "litre": "l", "litres": "l",
    "tablespoon": "tbsp", "tablespoons": "tbsp", "tbs": "tbsp",
    "teaspoon": "tsp", "teaspoons": "tsp",
    "cups": "cup",
    "piece": "count", "pieces": "count", "pc": "count", "pcs": "count",
    "each": "count", "whole": "count",
}
# Units that convert the same way for every ingredient with the matching base unit.
METRIC = {"kg": ("g", 1000.0), "l": ("ml", 1000.0)}


class NormalizeFilter(Filter):
    def process(self, rows):
        pantry, _ = self.normalize(rows, self.ref)
        yield NormalizedPantry(pantry)

    @staticmethod
    def normalize(rows: list[dict], ref: ReferenceData
                  ) -> tuple[dict[str, PantryItem], list[UnrecognizedItem]]:
        """Return (pantry keyed by ingredient name, rows we could not use). Never raises on a bad row."""
        lookup: dict[str, Ingredient] = {}
        for ing in ref.ingredients.values():
            lookup[_clean(ing.name)] = ing
            for alias in ing.aliases:
                lookup.setdefault(_clean(alias), ing)
        known = sorted(lookup)

        pantry: dict[str, PantryItem] = {}
        unrecognized: list[UnrecognizedItem] = []
        for row in rows:
            try:
                key = _clean(row["name"])
                qty = float(row["qty"])
                unit = _clean(row["unit"])
                expires = _parse_date(row.get("expires"))
            except (KeyError, TypeError, ValueError, AttributeError) as e:
                unrecognized.append(UnrecognizedItem(row, f"malformed row: {e}"))
                continue
            if not key:
                unrecognized.append(UnrecognizedItem(row, "missing ingredient name"))
                continue
            if not math.isfinite(qty) or qty <= 0:
                unrecognized.append(UnrecognizedItem(row, "quantity must be a positive number"))
                continue

            ing = _resolve(key, lookup, known)
            if ing is None:
                unrecognized.append(UnrecognizedItem(row, "unknown ingredient"))
                continue
            base_qty = _to_base(ing, qty, unit, ref)
            if base_qty is None:
                unrecognized.append(UnrecognizedItem(row, f"unit {unit!r} does not work for {ing.name}"))
                continue

            prev = pantry.get(ing.name)
            if prev is not None:            # merge duplicate rows, keep the earliest expiry
                dates = [d for d in (prev.expires, expires) if d is not None]
                pantry[ing.name] = PantryItem(ing.name, prev.qty + base_qty, ing.base_unit,
                                              min(dates) if dates else None)
            else:
                pantry[ing.name] = PantryItem(ing.name, base_qty, ing.base_unit, expires)
        return pantry, unrecognized


def _clean(text) -> str:
    if not isinstance(text, str):
        raise TypeError(f"expected text, got {type(text).__name__}")
    return " ".join(text.lower().split())


def _parse_date(value) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)


def _singular_forms(word: str) -> list[str]:
    forms = []
    if word.endswith("ies"):
        forms.append(word[:-3] + "y")
    if word.endswith("es"):
        forms.append(word[:-2])
    if word.endswith("s"):
        forms.append(word[:-1])
    return forms


def _resolve(key: str, lookup: dict[str, Ingredient], known: list[str]) -> Ingredient | None:
    if key in lookup:
        return lookup[key]
    for form in _singular_forms(key):
        if form in lookup:
            return lookup[form]
    close = difflib.get_close_matches(key, known, n=1, cutoff=TYPO_CUTOFF)
    return lookup[close[0]] if close else None


def _to_base(ing: Ingredient, qty: float, unit: str, ref: ReferenceData) -> float | None:
    unit = UNIT_ALIASES.get(unit, unit)
    if unit in METRIC and METRIC[unit][0] == ing.base_unit:
        return qty * METRIC[unit][1]
    return ref.to_base(ing.name, qty, unit)
