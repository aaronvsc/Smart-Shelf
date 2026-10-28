"""Tests for the shared data models in smart_shelf/common/models.py.

These are automated checks that the data models do what we say they do: unit
conversion, nutrition math, restriction checks, and that data can't be changed
once it's created. Run them with `.venv/bin/python -m pytest tests/common -q`.
We keep them because our proposal promises every piece is unit tested before
it's connected (Testability), and because both architectures build on these
models, so if someone breaks one by mistake, these tests catch it right away.
"""
from dataclasses import FrozenInstanceError

import pytest

from smart_shelf.common.models import (
    Ingredient, Nutrition, Recipe, RecipeIngredient, ReferenceData, UserProfile,
)


@pytest.fixture
def ref():
    ingredients = {
        "flour": Ingredient("flour", "g", ("all-purpose flour",), {"cup": 125}, frozenset({"gluten"})),
        "egg": Ingredient("egg", "count", (), {}, frozenset({"egg"})),
        "milk": Ingredient("milk", "ml", (), {"cup": 240}, frozenset({"dairy"})),
    }
    recipes = [Recipe("R001", "Pancakes", "American", 20, (RecipeIngredient("flour", 1, "cup"),))]
    return ReferenceData(
        ingredients=ingredients,
        recipes=recipes,
        nutrition={"flour": Nutrition(364, 10, 76, 1), "egg": Nutrition(72, 6, 0.4, 5)},
        restrictions={"vegan": frozenset({"dairy", "egg", "meat"}), "gluten_free": frozenset({"gluten"})},
    )


def test_nutrition_add_and_scale():
    total = Nutrition(100, 1, 2, 3) + Nutrition(50, 1, 1, 1)
    assert total == Nutrition(150, 2, 3, 4)
    assert Nutrition(100, 10, 20, 30).scaled(0.5) == Nutrition(50, 5, 10, 15)


def test_models_are_frozen():
    item = Ingredient("egg", "count")
    with pytest.raises(FrozenInstanceError):
        item.name = "duck egg"


def test_to_base_converts_known_units(ref):
    assert ref.to_base("flour", 2, "cup") == 250
    assert ref.to_base("flour", 30, "g") == 30


def test_to_base_returns_none_when_it_cannot_convert(ref):
    assert ref.to_base("flour", 1, "tbsp") is None
    assert ref.to_base("unicorn", 1, "g") is None


def test_all_restrictions_removes_duplicates_in_order():
    profile = UserProfile("u1", restrictions=("vegan", "gluten_free"), allergies=("vegan",))
    assert profile.all_restrictions == ("vegan", "gluten_free")


def test_violations_lists_broken_restrictions(ref):
    vegan = UserProfile("u1", restrictions=("vegan",))
    assert ref.violations("milk", vegan) == ("vegan",)
    assert ref.violations("flour", vegan) == ()


def test_unknown_ingredient_counts_as_violation_only_with_restrictions(ref):
    assert ref.violations("mystery", UserProfile("u1", allergies=("vegan",))) == ("unverified ingredient",)
    assert ref.violations("mystery", UserProfile("u2")) == ()


def test_check_restrictions_rejects_unknown_rules(ref):
    ref.check_restrictions(UserProfile("u1", restrictions=("vegan",)))
    with pytest.raises(ValueError, match="keto"):
        ref.check_restrictions(UserProfile("u2", restrictions=("keto",)))


def test_nutrition_of_handles_weight_and_count(ref):
    assert ref.nutrition_of("flour", 50) == Nutrition(182, 5, 38, 0.5)
    assert ref.nutrition_of("egg", 2) == Nutrition(144, 12, 0.8, 10)
    assert ref.nutrition_of("milk", 100) is None
