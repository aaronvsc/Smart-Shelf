"""Fixtures for Architecture A tests.

The reference data here is a small hand-made set built in Python, so these tests
do not depend on the team's real data files.
"""
from __future__ import annotations

from datetime import date

import pytest

from smart_shelf.arch_a.inputs import (
    Ingredient, Nutrition, PantryItem, Recipe, RecipeIngredient, ReferenceData,
    SelectionEntry, Substitute, UserProfile,
)
from smart_shelf.arch_a.pipe import Pipe
from smart_shelf.arch_a.records import END, RecipeRecord, RunContext

TODAY = date(2026, 10, 26)


def _ing(name, base, aliases=(), conv=None, tags=()):
    return Ingredient(name, base, tuple(aliases), conv or {}, frozenset(tags))


def _ri(name, qty, unit, required=True, substitutable=False):
    return RecipeIngredient(name, qty, unit, required, substitutable)


INGREDIENTS = [
    _ing("pasta", "g", ["spaghetti", "noodles"], {"cup": 100}, ["gluten"]),
    _ing("tomato", "g", ["roma tomato"], {"count": 120, "cup": 180}, ["vegetable"]),
    _ing("garlic", "count", ["garlic clove"], tags=["vegetable"]),
    _ing("basil", "g", ["fresh basil"], {"cup": 20}, ["herb"]),
    _ing("olive oil", "ml", [], {"tbsp": 15, "cup": 240}, ["oil"]),
    _ing("butter", "g", ["unsalted butter"], {"tbsp": 14, "cup": 227}, ["dairy"]),
    _ing("margarine", "g", [], {"tbsp": 14}, ["soy"]),
    _ing("egg", "count", [], tags=["egg"]),
    _ing("flour", "g", ["all-purpose flour"], {"cup": 125}, ["gluten"]),
    _ing("milk", "ml", ["whole milk"], {"cup": 240}, ["dairy"]),
    _ing("peanut butter", "g", ["pb"], {"tbsp": 16}, ["peanut"]),
    _ing("rice", "g", ["white rice"], {"cup": 185}, ["grain"]),
    _ing("soy sauce", "ml", ["soya sauce"], {"tbsp": 15}, ["soy", "gluten"]),
    _ing("chicken", "g", ["chicken breast"], {"count": 200}, ["meat"]),
    _ing("onion", "count", ["yellow onion"], tags=["vegetable"]),
]

RECIPES = [
    Recipe("F001", "Tomato Garlic Pasta", "Italian", 20, (
        _ri("pasta", 200, "g"), _ri("tomato", 2, "count"), _ri("garlic", 2, "count"),
        _ri("basil", 5, "g", required=False))),
    Recipe("F002", "Peanut Noodles", "Thai", 15, (
        _ri("pasta", 200, "g"), _ri("peanut butter", 2, "tbsp"), _ri("soy sauce", 2, "tbsp"))),
    Recipe("F003", "Pancakes", "American", 25, (
        _ri("flour", 1, "cup"), _ri("egg", 1, "count"), _ri("milk", 1, "cup"),
        _ri("butter", 2, "tbsp", substitutable=True))),
    Recipe("F004", "Egg Fried Rice", "Chinese", 15, (
        _ri("rice", 1, "cup"), _ri("egg", 2, "count"), _ri("onion", 1, "count"),
        _ri("soy sauce", 1, "tbsp"))),
    Recipe("F005", "Chicken and Rice", "American", 35, (
        _ri("chicken", 200, "g"), _ri("rice", 185, "g"), _ri("onion", 1, "count"))),
]

NUTRITION = {   # per 100 g/ml, or per item for "count" ingredients
    "pasta": Nutrition(371, 13.0, 75.0, 1.5), "tomato": Nutrition(18, 0.9, 3.9, 0.2),
    "garlic": Nutrition(4, 0.2, 1.0, 0.0), "basil": Nutrition(23, 3.2, 2.7, 0.6),
    "olive oil": Nutrition(884, 0, 0, 100), "butter": Nutrition(717, 0.9, 0.1, 81),
    "margarine": Nutrition(717, 0.2, 0.7, 80), "egg": Nutrition(72, 6.3, 0.4, 4.8),
    "flour": Nutrition(364, 10.3, 76.3, 1.0), "milk": Nutrition(61, 3.2, 4.8, 3.3),
    "peanut butter": Nutrition(588, 25, 20, 50), "rice": Nutrition(130, 2.7, 28, 0.3),
    "soy sauce": Nutrition(53, 8.1, 4.9, 0.6), "chicken": Nutrition(165, 31, 0, 3.6),
    "onion": Nutrition(44, 1.2, 10.3, 0.1),
}

RESTRICTIONS = {
    "vegan": frozenset({"meat", "fish", "dairy", "egg", "honey"}),
    "vegetarian": frozenset({"meat", "fish"}),
    "gluten_free": frozenset({"gluten"}),
    "peanut": frozenset({"peanut"}),
    "soy": frozenset({"soy"}),
}

PROFILES = {
    "default": UserProfile("default"),
    "peanut": UserProfile("peanut", allergies=("peanut",)),
    "vegan": UserProfile("vegan", restrictions=("vegan",)),
    "soy": UserProfile("soy", allergies=("soy",)),
    "rice_fan": UserProfile("rice_fan", history=(
        SelectionEntry("F004", date(2026, 10, 1)), SelectionEntry("F004", date(2026, 10, 8)))),
}


@pytest.fixture(scope="session")
def ref() -> ReferenceData:
    return ReferenceData(
        ingredients={i.name: i for i in INGREDIENTS},
        recipes=RECIPES,
        substitutes={"butter": (Substitute("olive oil", 0.75), Substitute("margarine", 1.0))},
        nutrition=NUTRITION,
        restrictions=RESTRICTIONS,
    )


@pytest.fixture
def profiles():
    return PROFILES


@pytest.fixture
def make_ctx(ref):
    def _make(pantry: dict[str, float] | None = None, profile: str = "default",
              rejected_subs=(), expires: dict[str, date] | None = None, today: date = TODAY):
        """pantry is {ingredient name: qty in its base unit}."""
        expires = expires or {}
        items = {n: PantryItem(n, q, ref.ingredients[n].base_unit, expires.get(n))
                 for n, q in (pantry or {}).items()}
        return RunContext(items, PROFILES[profile], frozenset(rejected_subs), today)
    return _make


@pytest.fixture
def make_record(ref):
    by_id = {r.id: r for r in ref.recipes}
    return lambda recipe_id: RecipeRecord(by_id[recipe_id])


@pytest.fixture
def run_filter(ref):
    """Run one filter alone on a list of items and return everything it sends out."""
    def _run(filter_cls, items, ctx):
        inp, out = Pipe("in"), Pipe("out")
        f = filter_cls(inp, out, ctx, ref)
        f.start()
        for item in items:
            inp.put(item)
        inp.close()
        results = []
        while (item := out.get(timeout=5)) is not END:
            results.append(item)
        f.join(timeout=5)
        if f.error:
            raise f.error
        return results
    return _run
