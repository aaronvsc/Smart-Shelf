"""Checks each pantry row on Step 1 while the user types, before any search runs.

Each problem comes back as a short, plain sentence ("carrots: add a quantity"),
so the user can fix it right there instead of finding out on the results
screen. Both architectures still check the rows themselves; this is only for
earlier, friendlier feedback.
"""
from __future__ import annotations

import difflib
import math

from smart_shelf.common.models import ReferenceData


def _clean(text: str) -> str:
    return " ".join(str(text).lower().split())


def name_lookup(ref: ReferenceData) -> dict[str, str]:
    """Every name and alias (lowercase) -> the ingredient's real name."""
    lookup = {}
    for ingredient in ref.ingredients.values():
        lookup[_clean(ingredient.name)] = ingredient.name
        for alias in ingredient.aliases:
            lookup.setdefault(_clean(alias), ingredient.name)
    return lookup


def resolve(name: str, lookup: dict[str, str]) -> str | None:
    """The real ingredient name for what the user typed, allowing simple plurals."""
    key = _clean(name)
    forms = [key]
    if key.endswith("ies"):
        forms.append(key[:-3] + "y")
    if key.endswith("es"):
        forms.append(key[:-2])
    if key.endswith("s"):
        forms.append(key[:-1])
    return next((lookup[form] for form in forms if form in lookup), None)


def suggestions(name: str, lookup: dict[str, str], limit: int = 3) -> list[str]:
    """Close matches for an unknown name: ones that contain it first, then similar spellings."""
    key = _clean(name)
    found = [real for typed, real in lookup.items() if key and key in typed]
    found += [lookup[typed] for typed in difflib.get_close_matches(key, list(lookup), n=limit, cutoff=0.6)]
    unique = list(dict.fromkeys(found))
    return unique[:limit]


def units_for(ref: ReferenceData, ingredient: str) -> list[str]:
    """The units that work for one ingredient, its main unit first."""
    item = ref.ingredients[ingredient]
    return [item.base_unit] + [unit for unit in item.unit_conversions if unit != item.base_unit]


def _or_list(words: list[str]) -> str:
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " or " + words[-1]


def row_problem(number: int, row: dict, ref: ReferenceData, lookup: dict[str, str]) -> str | None:
    """What's wrong with one row, or None if it's ready. `number` is the row's place in the table."""
    name = str(row.get("name") or "").strip()
    if not name:
        return f"Row {number}: add an ingredient name."
    ingredient = resolve(name, lookup)
    if ingredient is None:
        close = suggestions(name, lookup)
        hint = f" Did you mean {_or_list(close)}?" if close else ""
        return f"{name}: not in our ingredient list.{hint}"
    qty = row.get("qty")
    if qty is None or not math.isfinite(qty) or qty <= 0:
        return f"{name}: add a quantity above 0."
    unit = row.get("unit")
    if not unit:
        return f"{name}: pick a unit."
    if ref.to_base(ingredient, qty, unit) is None:
        return f"{name}: {unit} doesn't work for {ingredient}. Try {_or_list(units_for(ref, ingredient))}."
    return None


def check_pantry(rows: list[dict], ref: ReferenceData) -> list[str]:
    """One message per row that needs fixing; an empty list means every row is ready."""
    lookup = name_lookup(ref)
    problems = [row_problem(number, row, ref, lookup) for number, row in enumerate(rows, start=1)]
    return [problem for problem in problems if problem]
