"""Architecture A matches its design (proposal Figure 1 and Section 2.1).

These fail if the code drifts from the diagram: a filter reading a store it has no
data-access arrow for, shared data that can be changed, or data that bypasses the pipes.
"""
import inspect
from dataclasses import fields
from datetime import date

import pytest

from smart_shelf.arch_a import pipeline as pipeline_module
from smart_shelf.arch_a.filter_base import Filter
from smart_shelf.arch_a.filters import (
    DietaryFilter, FreshnessFilter, GapsFilter, MatchFilter, NormalizeFilter,
    NutritionFilter, PreferenceFilter, RankFilter, ShoppingListFilter, SubstituteFilter,
)
from smart_shelf.arch_a.pipe import Pipe
from smart_shelf.arch_a.pipeline import DEFAULT_FILTERS, Pipeline
from smart_shelf.arch_a.records import END, NormalizedPantry, RecipeRecord
from smart_shelf.arch_a.stores import (
    INGREDIENT_DICTIONARY as DICT, RECIPE_DATABASE as RECIPES, SUBSTITUTION_NUTRITION as SUBS,
    USER_PROFILE as PROFILE, StoreAccessError, StoreView, read_only,
)

TODAY = date(2026, 10, 26)

# Section 2.1: "filters 1, 2, 3, 5, 6, and 8 read reference data".
# Figure 1 draws the main store for each; the Ingredient Dictionary (units, tags,
# restriction rules) and the Recipe Database for filter 8 are the extra reads.
EXPECTED_READS = {
    NormalizeFilter: {DICT},
    MatchFilter: {RECIPES, DICT},
    DietaryFilter: {PROFILE, DICT},
    GapsFilter: set(),
    SubstituteFilter: {SUBS, DICT},
    NutritionFilter: {SUBS, DICT},
    FreshnessFilter: set(),
    PreferenceFilter: {PROFILE, RECIPES},
    RankFilter: set(),
    ShoppingListFilter: set(),
}


def test_each_filter_declares_exactly_its_designed_data_access():
    assert {cls: set(cls.reads) for cls in EXPECTED_READS} == EXPECTED_READS


def test_only_filters_1_2_3_5_6_8_read_stores():
    readers = [i + 1 for i, cls in enumerate([NormalizeFilter, *DEFAULT_FILTERS]) if cls.reads]
    assert readers == [1, 2, 3, 5, 6, 8]


@pytest.mark.parametrize("cls", list(EXPECTED_READS))
def test_a_filter_cannot_read_a_store_outside_its_access(ref, profiles, cls):
    f = cls(Pipe(), Pipe(), ref, profiles["default"])
    allowed = cls.reads
    probes = {
        DICT: lambda s: s.ingredients,
        RECIPES: lambda s: s.recipes,
        SUBS: lambda s: s.substitutes,
        PROFILE: lambda s: s.profile,
    }
    for store, probe in probes.items():
        if store in allowed:
            probe(f.stores)
        else:
            with pytest.raises(StoreAccessError):
                probe(f.stores)


def test_store_data_is_read_only(ref):
    view = StoreView(ref, None, {DICT, RECIPES, SUBS}, "test")
    with pytest.raises(TypeError):
        view.ingredients["new"] = None
    with pytest.raises(TypeError):
        view.ingredients["butter"].unit_conversions["cup"] = 1.0
    with pytest.raises(TypeError):
        view.substitutes["butter"] = ()
    with pytest.raises(TypeError):
        view.restrictions["vegan"] = frozenset()
    with pytest.raises((TypeError, AttributeError)):
        view.recipes.append(None)


def test_read_only_copy_does_not_change_the_original(ref):
    ro = read_only(ref)
    assert dict(ro.ingredients) == dict(ref.ingredients) and tuple(ro.recipes) == tuple(ref.recipes)
    assert read_only(ro) is ro


def test_the_pantry_on_p1_is_read_only():
    msg = NormalizedPantry({"rice": None}, ("vegan",), frozenset(), TODAY)
    with pytest.raises(TypeError):
        msg.items["rice"] = None


def test_filters_have_no_shared_run_context():
    params = list(inspect.signature(Filter.__init__).parameters)
    assert params == ["self", "inp", "out", "ref", "profile"]
    assert not hasattr(pipeline_module, "RunContext")


def test_run_input_is_not_a_result_field():
    """run/needs travel with each record but don't change the result (B parity)."""
    assert {f.name for f in fields(RecipeRecord)} == {
        "recipe", "on_hand", "missing", "substitutions", "to_buy", "nutrition",
        "freshness_boost", "preference_boost", "score", "shopping_list", "trace"}


def test_normalize_is_called_and_writes_p1(ref):
    p1 = Pipe("p1")
    pantry, bad = NormalizeFilter(None, p1, ref).submit(
        [{"name": "rice", "qty": 100, "unit": "g"}, {"name": "unobtainium", "qty": 1, "unit": "g"}],
        ("vegan",), [("F003", "olive oil")], TODAY)
    assert list(pantry) == ["rice"] and len(bad) == 1        # unrecognized go back to the caller
    msg = p1.get(timeout=1)
    assert isinstance(msg, NormalizedPantry)
    assert (list(msg.items), msg.restrictions, msg.rejected_subs, msg.today) == \
        (["rice"], ("vegan",), frozenset({("F003", "olive oil")}), TODAY)
    assert p1.get(timeout=1) is END


def test_pipeline_uses_pipes_p1_to_p10_in_figure_order(ref, profiles, monkeypatch):
    made = []

    class Recording(Pipe):
        def __init__(self, name="pipe"):
            super().__init__(name)
            made.append(name)

    monkeypatch.setattr(pipeline_module, "Pipe", Recording)
    Pipeline(ref).run([{"name": "pasta", "qty": 500, "unit": "g"}], profiles["default"], today=TODAY)
    assert made == [f"p{i}" for i in range(1, 11)]


def test_records_carry_the_run_input_from_p1(ref, profiles):
    result = Pipeline(ref).run([{"name": "pasta", "qty": 500, "unit": "g"}], profiles["peanut"],
                               rejected_subs=[("F003", "olive oil")], today=TODAY)
    run = result.ranked[0].run
    assert list(run.items) == ["pasta"] and run.restrictions == ("peanut",)
    assert run.rejected_subs == frozenset({("F003", "olive oil")}) and run.today == TODAY
    assert all(r.run is run for r in result.ranked)            # one message, shared read-only
