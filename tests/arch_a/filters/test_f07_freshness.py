from datetime import timedelta

import pytest

from smart_shelf.arch_a.filters import FreshnessFilter


def boost(run_filter, make_ctx, make_record, days):
    ctx = make_ctx({"tomato": 240})
    ctx = make_ctx({"tomato": 240}, expires={"tomato": ctx.today + timedelta(days=days)})
    [r] = run_filter(FreshnessFilter, [make_record("F001")], ctx)
    return r.freshness_boost


def test_recipe_using_an_expiring_item_gets_a_boost(run_filter, make_ctx, make_record):
    today = make_ctx().today
    ctx = make_ctx({"tomato": 240, "pasta": 500}, expires={"tomato": today + timedelta(days=1)})
    a, b = run_filter(FreshnessFilter, [make_record("F001"), make_record("F002")], ctx)
    assert a.freshness_boost > 0 and b.freshness_boost == 0


def test_sooner_expiry_means_bigger_boost(run_filter, make_ctx, make_record):
    assert boost(run_filter, make_ctx, make_record, 0) > boost(run_filter, make_ctx, make_record, 3) > 0


@pytest.mark.parametrize("days", [-1, 10])
def test_expired_or_far_off_items_give_no_boost(run_filter, make_ctx, make_record, days):
    assert boost(run_filter, make_ctx, make_record, days) == 0
