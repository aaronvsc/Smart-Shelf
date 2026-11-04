from smart_shelf.arch_a.filters import MatchFilter
from smart_shelf.arch_a.records import NormalizedPantry


def run(run_filter, ctx):
    return [r.recipe.id for r in run_filter(MatchFilter, [NormalizedPantry(ctx.pantry)], ctx)]


def test_one_record_per_candidate_in_id_order(run_filter, make_ctx):
    assert run(run_filter, make_ctx({"rice": 100, "pasta": 500})) == ["F001", "F002", "F004", "F005"]


def test_partial_match_counts(run_filter, make_ctx):
    assert run(run_filter, make_ctx({"chicken": 50})) == ["F005"]


def test_optional_ingredient_alone_is_not_a_match(run_filter, make_ctx):
    assert run(run_filter, make_ctx({"basil": 5})) == []
