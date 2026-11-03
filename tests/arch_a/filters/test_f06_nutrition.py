import pytest

from smart_shelf.arch_a.filters import GapsFilter, NutritionFilter, SubstituteFilter


def run_chain(run_filter, ctx, record):
    for cls in (GapsFilter, SubstituteFilter, NutritionFilter):
        [record] = run_filter(cls, [record], ctx)
    return record


def test_totals_per_recipe(run_filter, make_ctx, make_record):
    ctx = make_ctx({"rice": 185, "egg": 2, "onion": 1, "soy sauce": 15})
    r = run_chain(run_filter, ctx, make_record("F004"))
    # rice 1.85 x 130 + 2 eggs x 72 + 1 onion x 44 + soy 0.15 x 53
    assert r.nutrition.kcal == pytest.approx(240.5 + 144 + 44 + 7.95)


def test_totals_use_the_substitute(run_filter, make_ctx, make_record):
    ctx = make_ctx({"flour": 125, "egg": 1, "milk": 240, "olive oil": 21})
    r = run_chain(run_filter, ctx, make_record("F003"))
    # flour 455 + egg 72 + milk 146.4 + olive oil 0.21 x 884 (instead of butter)
    assert r.nutrition.kcal == pytest.approx(455 + 72 + 146.4 + 185.64)


def test_missing_optional_ingredient_is_left_out(run_filter, make_ctx, make_record):
    ctx = make_ctx({"pasta": 200, "tomato": 240, "garlic": 2})
    r = run_chain(run_filter, ctx, make_record("F001"))
    assert r.nutrition.kcal == pytest.approx(742 + 43.2 + 8)
