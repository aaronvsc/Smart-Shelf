import random
import time
from datetime import date

import pytest

from smart_shelf.arch_a.filter_base import Filter
from smart_shelf.arch_a.filters import MatchFilter
from smart_shelf.arch_a.inputs import (
    Ingredient, Nutrition, Recipe, RecipeIngredient, ReferenceData, Substitute, UserProfile,
)
from smart_shelf.arch_a.pipeline import (
    DEFAULT_FILTERS, Pipeline, PipelineError, combine_shopping_lists,
)

TODAY = date(2026, 10, 26)
PASTA_PANTRY = [{"name": "Spaghetti", "qty": 500, "unit": "g"},
                {"name": "tomatoes", "qty": 2, "unit": "count", "expires": "2026-10-27"},
                {"name": "garlic cloves", "qty": 3, "unit": "count"},
                {"name": "basil", "qty": 5, "unit": "g"}]
PANCAKE_PANTRY = [{"name": "flour", "qty": 2, "unit": "cup"},
                  {"name": "eggs", "qty": 2, "unit": "count"},
                  {"name": "milk", "qty": 1, "unit": "cup"},
                  {"name": "olive oil", "qty": 2, "unit": "tbsp"}]


@pytest.fixture
def run(ref, profiles):
    def _run(pantry, profile="default", **kwargs):
        return Pipeline(ref).run(pantry, profiles[profile], today=TODAY, **kwargs)
    return _run


def ids(result):
    return [r.recipe.id for r in result.ranked]


# --- wiring -----------------------------------------------------------------

def test_default_filters_are_in_designed_order():
    assert [c.__name__ for c in DEFAULT_FILTERS] == [
        "MatchFilter", "DietaryFilter", "GapsFilter", "SubstituteFilter", "NutritionFilter",
        "FreshnessFilter", "PreferenceFilter", "RankFilter", "ShoppingListFilter",
    ]


def test_records_visit_filters_in_order(ref, profiles):
    def tagger(label):
        def process(self, record):
            record.note(self.name, "visited")
            yield record
        return type(label, (Filter,), {"process": process})

    pipeline = Pipeline(ref, [MatchFilter, tagger("X"), tagger("Y"), tagger("Z")])
    result = pipeline.run(PASTA_PANTRY, profiles["default"], today=TODAY)
    assert result.ranked
    for record in result.ranked:
        assert [t[1:t.index("]")] for t in record.trace] == ["MatchFilter", "X", "Y", "Z"]


def test_filter_error_is_raised_not_swallowed(ref, profiles):
    class Boom(Filter):
        def process(self, item):
            raise RuntimeError("boom")

    with pytest.raises(PipelineError, match="Boom"):
        Pipeline(ref, [MatchFilter, Boom]).run(PASTA_PANTRY, profiles["default"], today=TODAY)


# --- main flow ----------------------------------------------------------------

def test_basic_run(run):
    result = run(PASTA_PANTRY)
    assert result.status == "ok"
    assert ids(result) == ["F001", "F002"]
    f001, f002 = result.ranked
    assert f001.shopping_list == [] and f001.freshness_boost > 0
    assert f002.shopping_list == ["peanut butter", "soy sauce"]
    assert result.exclusions.excluded == {}


def test_every_ranked_recipe_shows_its_breakdown(run):
    for record in run(PASTA_PANTRY).ranked:
        sources = {t[1:t.index("]")] for t in record.trace}
        assert {"MatchFilter", "RankFilter"} <= sources


def test_unrecognized_items_are_reported_alongside_results(run):
    result = run(PASTA_PANTRY + [{"name": "unobtainium", "qty": 1, "unit": "g"}])
    assert result.status == "ok"
    assert [u.row["name"] for u in result.unrecognized] == ["unobtainium"]


def test_substitute_then_reject_it(run):
    first = run(PANCAKE_PANTRY)
    assert ids(first) == ["F003", "F004"]
    assert first.ranked[0].substitutions == {"butter": "olive oil"}

    again = run(PANCAKE_PANTRY, rejected_subs=[("F003", "olive oil")])
    assert again.ranked[0].substitutions == {}
    assert again.ranked[0].shopping_list == ["butter"]


def test_combined_shopping_list_sums_quantities(run):
    result = run([{"name": "rice", "qty": 100, "unit": "g"}])
    combined = {name: (qty, unit) for name, qty, unit in
                combine_shopping_lists(result.ranked, ["F004", "F005"])}
    assert combined == {"rice": (170, "g"), "egg": (2, "count"), "onion": (2, "count"),
                        "soy sauce": (15, "ml"), "chicken": (200, "g")}


# --- reliability ----------------------------------------------------------------

def test_allergen_recipes_never_reach_the_output(run, ref, profiles):
    pantry = [{"name": "pasta", "qty": 500, "unit": "g"},
              {"name": "peanut butter", "qty": 100, "unit": "g"},
              {"name": "soy sauce", "qty": 100, "unit": "ml"},
              {"name": "margarine", "qty": 100, "unit": "g"}]
    for profile in ("peanut", "vegan", "soy"):
        result = run(pantry, profile)
        for record in result.ranked:
            used = [i.name for i in record.recipe.ingredients] + list(record.substitutions.values())
            for name in used:
                assert not ref.violations(name, profiles[profile]), (profile, record.recipe.id, name)


def test_peanut_allergy_summary(run):
    pantry = [{"name": "pasta", "qty": 500, "unit": "g"},
              {"name": "peanut butter", "qty": 100, "unit": "g"},
              {"name": "soy sauce", "qty": 100, "unit": "ml"}]
    result = run(pantry, "peanut")
    assert ids(result) == ["F001", "F004"]
    assert result.exclusions.excluded == {"F002": ("peanut",)}


def test_missing_profile_stops_the_run(ref):
    with pytest.raises(ValueError, match="profile"):
        Pipeline(ref).run(PASTA_PANTRY, None, today=TODAY)


def test_unknown_restriction_stops_the_run(ref):
    with pytest.raises(ValueError, match="keto"):
        Pipeline(ref).run(PASTA_PANTRY, UserProfile("u", restrictions=("keto",)), today=TODAY)


# --- edge cases (Section 1.4.1) ---------------------------------------------------

def test_empty_pantry_does_not_start(run):
    assert run([]).status == "empty_pantry"


def test_only_unrecognized_items_counts_as_empty(run):
    result = run([{"name": "unobtainium", "qty": 1, "unit": "g"}])
    assert result.status == "empty_pantry" and len(result.unrecognized) == 1


def test_no_recipes_match(run):
    assert run([{"name": "basil", "qty": 20, "unit": "g"}]).status == "no_matches"


def test_every_match_excluded(run):
    result = run([{"name": "peanut butter", "qty": 100, "unit": "g"}], "peanut")
    assert result.status == "all_excluded" and result.ranked == []
    assert result.exclusions.excluded == {"F002": ("peanut",)}


# --- consistency and performance ---------------------------------------------------

def test_same_input_gives_same_output_over_ten_runs(run):
    def snapshot():
        result = run(PASTA_PANTRY + PANCAKE_PANTRY, "rice_fan")
        return [(r.recipe.id, r.score, r.substitutions, r.shopping_list, r.trace)
                for r in result.ranked]
    first = snapshot()
    assert all(snapshot() == first for _ in range(9))


def synthetic_reference(n_ingredients=60, n_recipes=200, seed=0) -> ReferenceData:
    rng = random.Random(seed)
    names = [f"ing{i:02d}" for i in range(n_ingredients)]
    tags = ["dairy", "gluten", "meat", "egg", "soy", "nut"]
    ingredients = {n: Ingredient(n, "g", (), {"cup": 100}, frozenset(rng.sample(tags, 1)))
                   for n in names}
    recipes = [Recipe(f"R{i:03d}", f"Recipe {i}", rng.choice(["A", "B", "C"]), 30, tuple(
        RecipeIngredient(n, rng.randint(10, 300), "g", rng.random() > 0.2, rng.random() > 0.5)
        for n in rng.sample(names, rng.randint(5, 12)))) for i in range(n_recipes)]
    substitutes = {n: tuple(Substitute(s, 1.0) for s in rng.sample(names, 2)) for n in names}
    nutrition = {n: Nutrition(100, 5, 10, 3) for n in names}
    return ReferenceData(ingredients, recipes, substitutes, nutrition,
                         {"dairy_free": frozenset({"dairy"})})


def test_fifty_item_pantry_against_200_recipes_under_two_seconds():
    ref = synthetic_reference()
    pantry = [{"name": f"ing{i:02d}", "qty": 200, "unit": "g"} for i in range(50)]
    start = time.perf_counter()
    result = Pipeline(ref).run(pantry, UserProfile("u", restrictions=("dairy_free",)), today=TODAY)
    assert time.perf_counter() - start < 2.0
    assert result.status == "ok"
