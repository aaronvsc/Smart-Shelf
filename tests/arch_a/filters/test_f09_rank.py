import random

import pytest

from smart_shelf.arch_a.filters import RankFilter
from smart_shelf.arch_a.records import Gap


def ids(records):
    return [r.recipe.id for r in records]


def test_on_hand_beats_substituted_beats_to_buy(run_filter, make_ctx, make_record):
    full = make_record("F005")
    full.on_hand = ["chicken", "rice", "onion"]
    subbed = make_record("F003")
    subbed.on_hand = ["flour", "egg", "milk"]
    subbed.substitutions = {"butter": "olive oil"}
    buy = make_record("F001")
    buy.on_hand = ["pasta", "garlic"]
    buy.to_buy = [Gap("tomato", 240, 240, "g", True, False)]
    records = [full, subbed, buy]
    random.Random(1).shuffle(records)
    out = run_filter(RankFilter, records, make_ctx({"rice": 1}))
    assert ids(out) == ["F005", "F003", "F001"]
    assert [r.score for r in out] == pytest.approx([1.0, 0.875, 2 / 3])


def test_ties_break_by_recipe_id(run_filter, make_ctx, make_record):
    out = run_filter(RankFilter, [make_record("F002"), make_record("F001")], make_ctx({"rice": 1}))
    assert ids(out) == ["F001", "F002"]


def test_boost_breaks_a_closeness_tie(run_filter, make_ctx, make_record):
    a, b = make_record("F001"), make_record("F002")
    b.freshness_boost = 0.01
    assert ids(run_filter(RankFilter, [a, b], make_ctx({"rice": 1}))) == ["F002", "F001"]


def test_score_breakdown_is_recorded(run_filter, make_ctx, make_record):
    [r] = run_filter(RankFilter, [make_record("F001")], make_ctx({"rice": 1}))
    assert r.trace[-1].startswith("[RankFilter] score")
