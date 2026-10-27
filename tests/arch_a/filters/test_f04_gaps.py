from smart_shelf.arch_a.filters import GapsFilter
from smart_shelf.arch_a.records import Gap


def test_finds_missing_and_short_ingredients(run_filter, make_ctx, make_record):
    ctx = make_ctx({"pasta": 200, "tomato": 120, "garlic": 2})
    [r] = run_filter(GapsFilter, [make_record("F001")], ctx)
    assert r.on_hand == ["pasta", "garlic"]
    assert r.missing == [Gap("tomato", 240, 120, "g", True, False),
                         Gap("basil", 5, 5, "g", False, False)]


def test_recipe_units_are_converted_before_comparing(run_filter, make_ctx, make_record):
    # F002 needs 2 tbsp peanut butter = 32 g and 2 tbsp soy sauce = 30 ml
    ctx = make_ctx({"pasta": 200, "peanut butter": 32, "soy sauce": 30})
    [r] = run_filter(GapsFilter, [make_record("F002")], ctx)
    assert r.missing == [] and r.on_hand == ["pasta", "peanut butter", "soy sauce"]
