"""Data access: loads the JSON data stores in data/ into the shared models.

Both architectures read their data through this file instead of opening the
JSON files themselves, so they always get the same data in the same shape.
Bad data raises a DataError with a clear message instead of failing later in
some filter or knowledge source. It also reads and saves user profiles, one
private file per user in data/profiles/.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import date
from pathlib import Path

from smart_shelf.common.models import (
    Ingredient, Nutrition, Recipe, RecipeIngredient, ReferenceData, SelectionEntry,
    Substitute, UserProfile,
)

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
PROFILES_DIR = DATA_DIR / "profiles"

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


class ProfileError(DataError):
    """A user profile can't be loaded or saved. The app must stop instead of
    running without the user's restrictions (edge case in Section 1.4.1)."""


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


def load_recipes(ingredients: dict[str, Ingredient], path: Path | None = None) -> list[Recipe]:
    """Load the Recipe Database, checking every ingredient against the Ingredient Dictionary."""
    path = Path(path) if path else DATA_DIR / "recipes.json"
    raw = _read_json(path)
    if not isinstance(raw, dict) or not isinstance(raw.get("recipes"), list):
        raise DataError(f"{path.name} needs a 'recipes' list")

    recipes: list[Recipe] = []
    seen_ids: set[str] = set()
    for n, entry in enumerate(raw["recipes"]):
        try:
            rid, name, cuisine = entry["id"], entry["name"], entry["cuisine"]
            minutes, items = entry["cook_time_min"], entry["ingredients"]
        except (KeyError, TypeError):
            raise DataError(f"{path.name}, recipe #{n + 1}: needs id, name, cuisine, "
                            "cook_time_min, and ingredients") from None
        where = f"{path.name}, {rid} ({name})"
        if rid in seen_ids:
            raise DataError(f"{where}: recipe id is used more than once")
        seen_ids.add(rid)
        if not isinstance(minutes, int) or minutes <= 0:
            raise DataError(f"{where}: cook_time_min must be a whole number above 0")

        parts: list[RecipeIngredient] = []
        for item in items:
            ing_name, qty, unit = item.get("name"), item.get("qty"), item.get("unit")
            ing = ingredients.get(ing_name)
            if ing is None:
                raise DataError(f"{where}: {ing_name!r} is not in the Ingredient Dictionary")
            if any(p.name == ing_name for p in parts):
                raise DataError(f"{where}: {ing_name!r} is listed more than once")
            if not isinstance(qty, (int, float)) or qty <= 0:
                raise DataError(f"{where}: quantity for {ing_name!r} must be above 0")
            if unit != ing.base_unit and unit not in ing.unit_conversions:
                raise DataError(f"{where}: unit {unit!r} doesn't convert for {ing_name!r}")
            parts.append(RecipeIngredient(ing_name, float(qty), unit,
                                          bool(item.get("required", True)),
                                          bool(item.get("substitutable", False))))
        if not any(p.required for p in parts):
            raise DataError(f"{where}: needs at least one required ingredient")
        recipes.append(Recipe(rid, name, cuisine, minutes, tuple(parts)))
    return recipes


def load_reference_data(data_dir: Path | None = None) -> ReferenceData:
    """Load every read-only data store into one ReferenceData object.

    This is the one call both architectures use to get their data.
    """
    data_dir = Path(data_dir) if data_dir else DATA_DIR
    ingredients, restrictions = load_ingredients(data_dir / "ingredients.json")
    substitutes, nutrition = load_substitutions_nutrition(
        ingredients, data_dir / "substitutions_nutrition.json")
    recipes = load_recipes(ingredients, data_dir / "recipes.json")
    return ReferenceData(ingredients=ingredients, recipes=recipes, substitutes=substitutes,
                         nutrition=nutrition, restrictions=restrictions)


# ----------------------------------------------------------- user profiles

USER_ID_PATTERN = re.compile(r"^[a-z0-9_-]{1,40}$")


def _profile_path(user_id: str, profiles_dir: Path | None) -> Path:
    """The one file for this user. The ID is checked so it can only ever point
    to that user's own file inside the profiles folder (Privacy)."""
    if not isinstance(user_id, str) or not USER_ID_PATTERN.match(user_id):
        raise ProfileError(f"Invalid user id {user_id!r}: use 1-40 lowercase letters, "
                           "digits, '_' or '-'")
    return Path(profiles_dir or PROFILES_DIR) / f"{user_id}.json"


def load_profile(user_id: str, profiles_dir: Path | None = None) -> UserProfile:
    """Load one user's profile, or raise ProfileError if it's missing or invalid."""
    path = _profile_path(user_id, profiles_dir)
    try:
        raw = _read_json(path)
    except DataError as e:
        raise ProfileError(f"Profile for {user_id!r} can't be loaded: {e}") from None
    try:
        if raw["user_id"] != user_id:
            raise ProfileError(f"{path.name} belongs to {raw['user_id']!r}, not {user_id!r}")
        restrictions = tuple(str(r) for r in raw.get("restrictions", []))
        allergies = tuple(str(a) for a in raw.get("allergies", []))
        history = tuple(SelectionEntry(h["recipe_id"], date.fromisoformat(h["selected_at"]))
                        for h in raw.get("history", []))
    except ProfileError:
        raise
    except (KeyError, TypeError, ValueError) as e:
        raise ProfileError(f"Profile for {user_id!r} has invalid content: {e}") from None
    return UserProfile(user_id, restrictions, allergies, history)


def save_profile(profile: UserProfile, profiles_dir: Path | None = None) -> None:
    """Write a profile to its file. Writes to a temp file first, so a crash
    halfway through can't leave a broken profile behind."""
    path = _profile_path(profile.user_id, profiles_dir)
    data = {
        "user_id": profile.user_id,
        "restrictions": list(profile.restrictions),
        "allergies": list(profile.allergies),
        "history": [{"recipe_id": h.recipe_id, "selected_at": h.selected_at.isoformat()}
                    for h in profile.history],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def save_selection(user_id: str, recipe_ids: list[str], on: date | None = None,
                   profiles_dir: Path | None = None) -> UserProfile:
    """Add the recipes a user picked to their history (Step 5 of the main flow)
    and return the updated profile."""
    profile = load_profile(user_id, profiles_dir)
    picked = tuple(SelectionEntry(rid, on or date.today()) for rid in recipe_ids)
    updated = UserProfile(profile.user_id, profile.restrictions, profile.allergies,
                          profile.history + picked)
    save_profile(updated, profiles_dir)
    return updated
