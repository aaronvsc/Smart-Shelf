from smart_shelf.arch_a.config import PREFERENCE_MAX_BOOST
from smart_shelf.arch_a.filters import PreferenceFilter


def test_previously_chosen_recipe_gets_a_capped_boost(run_filter, make_ctx, make_record):
    ctx = make_ctx({"rice": 100}, profile="rice_fan")       # picked F004 twice
    f004, f005 = run_filter(PreferenceFilter, [make_record("F004"), make_record("F005")], ctx)
    assert 0 < f004.preference_boost <= PREFERENCE_MAX_BOOST
    assert f005.preference_boost == 0


def test_no_history_means_no_boost(run_filter, make_ctx, make_record):
    [r] = run_filter(PreferenceFilter, [make_record("F004")], make_ctx({"rice": 100}))
    assert r.preference_boost == 0
