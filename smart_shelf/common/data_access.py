"""Data access: loads the JSON data stores in data/ into the shared models.

Both architectures read their data through this file instead of opening the
JSON files themselves, so they always get the same data in the same shape.
Bad data raises a DataError with a clear message instead of failing later in
some filter or knowledge source.
"""
from __future__ import annotations

import json
from pathlib import Path

from smart_shelf.common.models import Ingredient, Nutrition, Substitute

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

BASE_UNITS = ("g", "ml", "count")

# Conversions that are the same for every ingredient with that base unit.
# Food-specific ones (like "1 cup of flour = 125 g") live in ingredients.json
# and override these.
STANDARD_CONVERSIONS = {
    "g": {"kg": 1000.0, "oz": 28.35, "lb": 453.6},
    "ml": {"l": 1000.0, "tsp": 5.0, "tbsp": 15.0, "cup": 240.0, "fl oz": 30.0},
    "count": {},
}


class DataError(Exception):
    """A data file is missing, unreadable, or has invalid content."""


def _read_json(path: Path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        raise DataError(f"Data file not found: {path}") from None
    except json.JSONDecodeError as e:
        raise DataError(f"{path.name} is not valid JSON (line {e.lineno}): {e.msg}") from None


def load_ingredients(path: Path | None = None
                     ) -> tuple[dict[str, Ingredient], dict[str, frozenset[str]]]:
    """Load the Ingredient Dictionary.

    Returns (ingredients keyed by name, restriction name -> forbidden tags).
    """
    path = Path(path) if path else DATA_DIR / "ingredients.json"
    raw = _read_json(path)
    if not isinstance(raw, dict) or "restrictions" not in raw or "ingredients" not in raw:
        raise DataError(f"{path.name} needs 'restrictions' and 'ingredients' sections")

    restrictions = {name: frozenset(tags) for name, tags in raw["restrictions"].items()}
    known_tags = frozenset().union(*restrictions.values())

    ingredients: dict[str, Ingredient] = {}
    for i, entry in enumerate(raw["ingredients"]):
        where = f"{path.name}, ingredient #{i + 1}"
        try:
            name = entry["name"].strip().lower()
            base = entry["base_unit"]
        except (KeyError, TypeError, AttributeError):
            raise DataError(f"{where}: every ingredient needs a 'name' and 'base_unit'") from None
        where = f"{path.name}, {name!r}"
        if not name:
            raise DataError(f"{where}: name can't be empty")
        if name in ingredients:
            raise DataError(f"{where}: listed more than once")
        if base not in BASE_UNITS:
            raise DataError(f"{where}: base_unit must be one of {BASE_UNITS}, got {base!r}")

        conversions = dict(STANDARD_CONVERSIONS[base])
        for unit, factor in entry.get("unit_conversions", {}).items():
            if not isinstance(factor, (int, float)) or factor <= 0:
                raise DataError(f"{where}: conversion for {unit!r} must be a positive number")
            conversions[unit] = float(factor)

        tags = frozenset(entry.get("tags", []))
        unknown = tags - known_tags
        if unknown:
            raise DataError(f"{where}: unknown tag(s) {sorted(unknown)}; "
                            "tags must appear in at least one restriction")

        ingredients[name] = Ingredient(
            name=name,
            base_unit=base,
            aliases=tuple(a.strip().lower() for a in entry.get("aliases", [])),
            unit_conversions=conversions,
            tags=tags,
        )

    # every name and alias has to point to exactly one ingredient
    owner: dict[str, str] = {}
    for ing in ingredients.values():
        for key in (ing.name, *ing.aliases):
            if key in owner and owner[key] != ing.name:
                raise DataError(f"{path.name}: {key!r} is used by both "
                                f"{owner[key]!r} and {ing.name!r}")
            owner[key] = ing.name
    return ingredients, restrictions


NUTRITION_FIELDS = ("kcal", "protein_g", "carbs_g", "fat_g")


def load_substitutions_nutrition(ingredients: dict[str, Ingredient], path: Path | None = None
                                 ) -> tuple[dict[str, tuple[Substitute, ...]], dict[str, Nutrition]]:
    """Load the Substitution & Nutrition Data.

    Needs the already-loaded ingredients so every name can be checked against the
    Ingredient Dictionary. Returns (substitutes by ingredient, nutrition by ingredient).
    """
    path = Path(path) if path else DATA_DIR / "substitutions_nutrition.json"
    raw = _read_json(path)
    if not isinstance(raw, dict) or not isinstance(raw.get("ingredients"), dict):
        raise DataError(f"{path.name} needs an 'ingredients' section")

    substitutes: dict[str, tuple[Substitute, ...]] = {}
    nutrition: dict[str, Nutrition] = {}
    for name, entry in raw["ingredients"].items():
        where = f"{path.name}, {name!r}"
        if name not in ingredients:
            raise DataError(f"{where}: not in the Ingredient Dictionary")

        if "nutrition" in entry:
            values = entry["nutrition"]
            if set(values) != set(NUTRITION_FIELDS):
                raise DataError(f"{where}: nutrition needs exactly {NUTRITION_FIELDS}")
            if any(not isinstance(v, (int, float)) or v < 0 for v in values.values()):
                raise DataError(f"{where}: nutrition values must be numbers 0 or higher")
            nutrition[name] = Nutrition(**{k: float(values[k]) for k in NUTRITION_FIELDS})

        subs = []
        for sub in entry.get("substitutes", []):
            sub_name, ratio = sub.get("name"), sub.get("ratio", 1.0)
            if sub_name not in ingredients:
                raise DataError(f"{where}: substitute {sub_name!r} is not in the Ingredient Dictionary")
            if sub_name == name:
                raise DataError(f"{where}: an ingredient can't substitute for itself")
            if not isinstance(ratio, (int, float)) or ratio <= 0:
                raise DataError(f"{where}: substitute ratio for {sub_name!r} must be a positive number")
            subs.append(Substitute(sub_name, float(ratio)))
        if subs:
            substitutes[name] = tuple(subs)
    return substitutes, nutrition
