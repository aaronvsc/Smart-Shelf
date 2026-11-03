import pytest

from smart_shelf.arch_a.filters import GapsFilter, SubstituteFilter

PANCAKE_BASE = {"flour": 500, "egg": 6, "milk": 1000}


@pytest.fixture
def pancakes(run_filter, make_ctx, make_record):
    def _run(extra=None, **ctx_kwargs):
        ctx = make_ctx({**PANCAKE_BASE, **(extra or {})}, **ctx_kwargs)
        gaps = run_filter(GapsFilter, [make_record("F003")], ctx)
        [r] = run_filter(SubstituteFilter, gaps, ctx)
        return r
    return _run


def test_uses_a_substitute_the_user_has_enough_of(pancakes):
    r = pancakes({"olive oil": 30})               # needs 28 g * 0.75 = 21 ml
    assert r.substitutions == {"butter": "olive oil"} and r.to_buy == []


def test_not_enough_substitute_means_buy(pancakes):
    r = pancakes({"olive oil": 10})
    assert r.substitutions == {} and [g.name for g in r.to_buy] == ["butter"]


def test_rejected_substitute_is_skipped_for_the_next_one(pancakes):
    r = pancakes({"olive oil": 30, "margarine": 50}, rejected_subs={("F003", "olive oil")})
    assert r.substitutions == {"butter": "margarine"}


def test_substitute_that_breaks_a_restriction_is_never_suggested(pancakes):
    r = pancakes({"margarine": 50}, profile="soy")
    assert r.substitutions == {} and [g.name for g in r.to_buy] == ["butter"]


def test_substitute_only_covers_the_shortfall(pancakes):
    r = pancakes({"butter": 14, "olive oil": 11})  # short 14 g -> needs 10.5 ml
    assert r.substitutions == {"butter": "olive oil"}


def test_non_substitutable_missing_ingredient_goes_to_buy(run_filter, make_ctx, make_record):
    ctx = make_ctx({"flour": 500, "egg": 6, "olive oil": 30})        # no milk
    [r] = run_filter(SubstituteFilter, run_filter(GapsFilter, [make_record("F003")], ctx), ctx)
    assert [g.name for g in r.to_buy] == ["milk"]


def test_optional_missing_ingredient_is_never_bought(run_filter, make_ctx, make_record):
    ctx = make_ctx({"pasta": 200, "tomato": 240, "garlic": 2})       # no basil
    [r] = run_filter(SubstituteFilter, run_filter(GapsFilter, [make_record("F001")], ctx), ctx)
    assert r.to_buy == []
