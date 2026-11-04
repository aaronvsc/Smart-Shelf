from smart_shelf.arch_a.filters import DietaryFilter
from smart_shelf.arch_a.inputs import Recipe, RecipeIngredient
from smart_shelf.arch_a.records import ExclusionSummary, RecipeRecord


def test_allergen_recipe_is_dropped_and_summarized(run_filter, make_ctx, make_record):
    out = run_filter(DietaryFilter, [make_record("F001"), make_record("F002")],
                     make_ctx({"pasta": 500}, profile="peanut"))
    assert [r.recipe.id for r in out[:-1]] == ["F001"]
    assert out[-1] == ExclusionSummary(2, {"F002": ("peanut",)})


def test_vegan_drops_dairy_egg_and_meat(run_filter, make_ctx, make_record):
    records = [make_record(i) for i in ("F001", "F003", "F004", "F005")]
    out = run_filter(DietaryFilter, records, make_ctx({"rice": 100}, profile="vegan"))
    assert [r.recipe.id for r in out[:-1]] == ["F001"]
    assert out[-1].excluded == {"F003": ("vegan",), "F004": ("vegan",), "F005": ("vegan",)}


def test_allergen_in_an_optional_ingredient_still_excludes(run_filter, make_ctx):
    recipe = Recipe("X1", "Pasta with optional peanut topping", "Fusion", 10, (
        RecipeIngredient("pasta", 100, "g"),
        RecipeIngredient("peanut butter", 10, "g", required=False)))
    out = run_filter(DietaryFilter, [RecipeRecord(recipe)], make_ctx({"pasta": 500}, profile="peanut"))
    assert out == [ExclusionSummary(1, {"X1": ("peanut",)})]


def test_no_restrictions_keeps_everything(run_filter, make_ctx, make_record):
    out = run_filter(DietaryFilter, [make_record("F002")], make_ctx({"pasta": 500}))
    assert [r.recipe.id for r in out[:-1]] == ["F002"] and out[-1].excluded == {}
