"""Small shared-model fixtures with hand-checkable quantities."""
from datetime import date

import pytest

from smart_shelf.common.models import (
    Ingredient, Nutrition, Recipe, RecipeIngredient as Part, ReferenceData,
    Substitute, UserProfile,
)


@pytest.fixture
def ref():
    ingredients = [
        Ingredient("rice", "g", ("white rice",), {"cup": 100}),
        Ingredient("egg", "count", tags=frozenset({"egg"})),
        Ingredient("milk", "ml", tags=frozenset({"dairy"})),
        Ingredient("oat milk", "ml"),
        Ingredient("butter", "g", tags=frozenset({"dairy"})),
        Ingredient("oil", "ml"),
        Ingredient("nut", "g", tags=frozenset({"peanut"})),
        Ingredient("salt", "g"),
    ]
    recipes = (
        Recipe("R1", "Rice and egg", "A", 10, (
            Part("rice", 100, "g"), Part("egg", 1, "count"),
            Part("butter", 20, "g", substitutable=True))),
        Recipe("R2", "Rice pudding", "B", 20, (
            Part("rice", 150, "g"), Part("milk", 100, "ml", substitutable=True))),
        Recipe("R3", "Nut rice", "A", 10, (Part("rice", 100, "g"), Part("nut", 20, "g"))),
        Recipe("R4", "Plain rice", "A", 10, (
            Part("rice", 100, "g"), Part("salt", 1, "g", required=False))),
        Recipe("R5", "Milk sauce", "B", 5, (
            Part("milk", 100, "ml"), Part("butter", 20, "g", substitutable=True))),
        Recipe("R6", "Nuts", "C", 5, (Part("nut", 20, "g"),)),
    )
    return ReferenceData(
        {ingredient.name: ingredient for ingredient in ingredients}, recipes,
        {"butter": (Substitute("oil", .75), Substitute("nut", 1)),
         "milk": (Substitute("oat milk", 1),)},
        {ingredient.name: Nutrition(100, 10, 20, 5) for ingredient in ingredients},
        {"peanut": frozenset({"peanut"}), "vegan": frozenset({"egg", "dairy"})},
    )


@pytest.fixture
def profile():
    return UserProfile("tester")


@pytest.fixture
def rows():
    return [{"name": "rice", "qty": 200, "unit": "g"},
            {"name": "egg", "qty": 1, "unit": "count"},
            {"name": "oil", "qty": 15, "unit": "ml"}]


@pytest.fixture
def today():
    return date(2026, 11, 3)
