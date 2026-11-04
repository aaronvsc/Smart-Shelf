"""Cross-architecture acceptance uses real shared data without changing it."""
from dataclasses import asdict, replace
from datetime import date

import pytest

from smart_shelf.arch_a.pipeline import Pipeline
from smart_shelf.arch_b import Blackboard, BlackboardEngine
from smart_shelf.arch_b.knowledge_sources import default_sources
from smart_shelf.common.data_access import load_reference_data
from smart_shelf.common.models import UserProfile


TODAY = date(2026, 11, 3)


def canonical(result):
    """Compare domain results; execution times and architectural traces differ."""
    records = []
    for record in result.ranked:
        value = asdict(record)
        value.pop("trace")
        records.append(value)
    return {"status": result.status, "ranked": records,
            "unrecognized": [asdict(item) for item in result.unrecognized],
            "exclusions": asdict(result.exclusions) if result.exclusions else None}


@pytest.fixture(scope="module")
def real_ref():
    return load_reference_data()


@pytest.mark.parametrize("restriction", [None, "vegan", "gluten_free", "peanut", "dairy"])
@pytest.mark.parametrize("pantry", ["rice", "milk", "egg", "full", "empty", "malformed"])
def test_a_b_parity_and_restriction_safety(real_ref, restriction, pantry):
    if restriction is not None and restriction not in real_ref.restrictions:
        pytest.skip("Restriction not present in team data")
    names = list(real_ref.ingredients) if pantry == "full" else [pantry]
    rows = [{"name": name, "qty": 1000, "unit": real_ref.ingredients[name].base_unit}
            for name in names if name in real_ref.ingredients]
    if pantry == "malformed":
        rows = [None, {"name": "rice", "qty": "nan", "unit": "g"}]
    profile = UserProfile("acceptance", restrictions=(restriction,) if restriction else ())
    a = Pipeline(real_ref).run(rows, profile, today=TODAY)
    b = BlackboardEngine(real_ref).run(rows, profile, today=TODAY)
    assert canonical(a) == canonical(b)
    for record in b.ranked:
        assert all(not real_ref.violations(part.name, profile) for part in record.recipe.ingredients)
        assert all(not real_ref.violations(name, profile) for name in record.substitutions.values())


def test_incremental_decision_matches_fresh_a_and_b(ref, rows, profile):
    engine = BlackboardEngine(ref)
    engine.run(rows, profile, today=TODAY)
    updated = engine.decide_substitute("R1", "oil", False)
    rejected = [("R1", "oil")]
    a = Pipeline(ref).run(rows, profile, rejected_subs=rejected, today=TODAY)
    fresh = BlackboardEngine(ref).run(rows, profile, rejected_subs=rejected, today=TODAY)
    assert canonical(updated) == canonical(a) == canonical(fresh)


@pytest.mark.parametrize("source_index", range(10))
def test_each_knowledge_source_runs_on_preset_blackboard(ref, rows, profile, source_index):
    engine = BlackboardEngine(ref)
    engine.run(rows, profile, today=TODAY)
    source = default_sources(ref, lambda profile, request: profile)[source_index]
    board = Blackboard()
    board.publish(**{region: engine.board.read(region) for region in source.inputs})
    assert source.can_run(board)
    source.run(board)
    assert board.has(*source.outputs)
    assert not source.can_run(board)
    for region in source.outputs:
        assert board.read(region) == engine.board.read(region)


def test_200_recipe_50_item_performance_and_repeatability(real_ref):
    recipes = tuple(replace(real_ref.recipes[index % len(real_ref.recipes)], id=f"S{index:03}")
                    for index in range(200))
    ref = replace(real_ref, recipes=recipes)
    rows = [{"name": name, "qty": 1000, "unit": ingredient.base_unit}
            for name, ingredient in list(ref.ingredients.items())[:50]]
    expected = None
    for _ in range(10):
        result = BlackboardEngine(ref).run(rows, UserProfile("benchmark"), today=TODAY)
        assert result.elapsed_s < 2
        if expected is None:
            expected = canonical(result)
        assert canonical(result) == expected


def test_every_declared_restriction_blocks_violating_recommendations(real_ref):
    rows = [{"name": name, "qty": 1000, "unit": item.base_unit}
            for name, item in real_ref.ingredients.items()]
    for restriction in real_ref.restrictions:
        profile = UserProfile("acceptance", restrictions=(restriction,))
        result = BlackboardEngine(real_ref).run(rows, profile, today=TODAY)
        for record in result.ranked:
            assert all(not real_ref.violations(item.name, profile) for item in record.recipe.ingredients)
            assert all(not real_ref.violations(name, profile) for name in record.substitutions.values())
