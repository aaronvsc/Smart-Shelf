from dataclasses import asdict, replace
from datetime import date, timedelta

import pytest

from smart_shelf.arch_b import BlackboardEngine
from smart_shelf.common.data_access import load_profile, save_profile
from smart_shelf.common.models import SelectionEntry, UserProfile


def by_id(result, rid):
    return next(record for record in result.ranked if record.recipe.id == rid)


def test_hand_computed_gaps_substitution_nutrition_and_rank(ref, rows, profile, today):
    result = BlackboardEngine(ref).run(rows, profile, today=today)
    assert result.status == "ok"
    assert [record.recipe.id for record in result.ranked] == ["R4", "R1", "R2", "R3"]
    record = by_id(result, "R1")
    assert record.on_hand == ["rice", "egg"]
    assert record.substitutions == {"butter": "oil"}
    assert record.to_buy == []
    assert record.nutrition.kcal == 215
    assert record.score == pytest.approx(2.5 / 3)
    assert by_id(result, "R2").shopping_list == ["milk"]
    assert by_id(result, "R4").shopping_list == []
    assert "score" in " ".join(record.trace)


def test_substitution_decision_reuses_earlier_results_and_is_reversible(ref, rows, profile):
    engine = BlackboardEngine(ref)
    initial = engine.run(rows, profile)
    versions = dict(engine.board.versions)
    rejected = engine.decide_substitute("R1", "oil", False)
    assert rejected.activations == ("SubstituteFinder", "NutritionCalculator", "FreshnessScorer",
                                    "Ranker", "ShoppingListBuilder")
    for region in ("pantry", "candidates", "dietary", "gaps", "preferences"):
        assert engine.board.versions[region] == versions[region]
    assert by_id(rejected, "R1").shopping_list == ["butter"]
    assert by_id(rejected, "R1").nutrition.kcal == 220
    assert engine.decide_substitute("R1", "oil", False).activations == ()
    restored = engine.decide_substitute("R1", "oil", True)
    assert asdict(by_id(restored, "R1")) == asdict(by_id(initial, "R1"))
    assert by_id(initial, "R1").substitutions == {"butter": "oil"}


def test_dietary_exclusions_remain_on_blackboard_but_never_in_rankings(ref, rows):
    engine = BlackboardEngine(ref)
    result = engine.run(rows, UserProfile("tester", allergies=("peanut",)))
    assert result.exclusions.excluded == {"R3": ("peanut",)}
    assert engine.board.read("dietary")["R3"] == ("peanut",)
    assert "R3" not in {record.recipe.id for record in result.ranked}
    vegan = engine.run(rows, UserProfile("tester", restrictions=("vegan",)))
    assert "R1" not in {record.recipe.id for record in vegan.ranked}


def test_unsafe_substitute_is_skipped_and_quantity_is_reserved(ref, profile):
    rows = [{"name": "rice", "qty": 100, "unit": "g"},
            {"name": "egg", "qty": 1, "unit": "count"},
            {"name": "nut", "qty": 30, "unit": "g"}]
    result = BlackboardEngine(ref).run(rows, replace(profile, allergies=("peanut",)))
    assert by_id(result, "R1").substitutions == {}
    result = BlackboardEngine(ref).run(rows[:2] + [{"name": "oil", "qty": 14, "unit": "ml"}], profile)
    assert by_id(result, "R1").substitutions == {}


@pytest.mark.parametrize("rows,status", [
    ([], "empty_pantry"),
    ([{"name": "unknown_xyz", "qty": 1, "unit": "g"}], "empty_pantry"),
    ([{"name": "oil", "qty": 100, "unit": "ml"}], "no_matches"),
])
def test_empty_and_no_match_states(ref, profile, rows, status):
    result = BlackboardEngine(ref).run(rows, profile)
    assert result.status == status
    assert result.ranked == []
    if status == "empty_pantry":
        assert result.activations == ("InputNormalizer",)


def test_all_excluded_reports_reason(ref):
    result = BlackboardEngine(ref).run([{"name": "nut", "qty": 20, "unit": "g"}],
                                      UserProfile("tester", allergies=("peanut",)))
    assert result.status == "all_excluded"
    assert result.exclusions.matched_count == 2
    assert set(result.exclusions.excluded) == {"R3", "R6"}


@pytest.mark.parametrize("bad", [None, 7, {}, {"name": None},
    {"name": "rice", "qty": "nan", "unit": "g"},
    {"name": "rice", "qty": float("inf"), "unit": "g"},
    {"name": "rice", "qty": -1, "unit": "g"},
    {"name": "rice", "qty": 1, "unit": "g", "expires": "not-a-date"},
    {"name": "rice", "qty": 1, "unit": "ml"},
])
def test_bad_rows_reported_without_crashing(ref, profile, bad):
    result = BlackboardEngine(ref).run([bad], profile)
    assert result.status == "empty_pantry"
    assert len(result.unrecognized) == 1


def test_normalization_merges_aliases_units_and_earliest_expiry(ref, profile, today):
    rows = [{"name": " WHITE   RICE ", "qty": .1, "unit": "kilograms", "expires": str(today)},
            {"name": "rices", "qty": 1, "unit": "cup", "expires": str(today + timedelta(days=2))},
            {"name": "ric", "qty": 1, "unit": "g"}]
    engine = BlackboardEngine(ref)
    result = engine.run(rows, profile, today=today)
    assert result.unrecognized == []
    assert engine.board.read("pantry")["rice"].qty == 201
    assert engine.board.read("pantry")["rice"].expires == today
    assert by_id(result, "R4").freshness_boost == pytest.approx(.02)


def test_profile_required_and_unknown_restrictions_stop(ref, rows):
    with pytest.raises(ValueError, match="profile"):
        BlackboardEngine(ref).run(rows, None)
    with pytest.raises(ValueError, match="Unknown restriction"):
        BlackboardEngine(ref).run(rows, UserProfile("tester", allergies=("unknown",)))


def test_stable_tie_break_and_private_preference(ref, rows, profile):
    history = (SelectionEntry("R3", date(2026, 10, 1)),) * 10
    first = BlackboardEngine(ref).run(rows, replace(profile, history=history))
    second = BlackboardEngine(ref).run(rows, UserProfile("other"))
    assert by_id(first, "R3").preference_boost == .05
    assert by_id(second, "R3").preference_boost == 0
    expected = [asdict(record) for record in second.ranked]
    for _ in range(10):
        result = BlackboardEngine(ref).run(rows, profile)
        assert [asdict(record) for record in result.ranked] == expected


def test_selection_combines_total_demand_without_double_spending_pantry(ref, profile, tmp_path, today):
    save_profile(profile, tmp_path)
    engine = BlackboardEngine(ref, profiles_dir=tmp_path)
    engine.run([{"name": "rice", "qty": 150, "unit": "g"}], profile, today=today)
    result = engine.select(["R4", "R2"], "click-1")
    assert result.combined_shopping_list == [("milk", 100, "ml"), ("rice", 100, "g")]
    assert result.activations == ("PreferenceWeighter", "Ranker", "ShoppingListBuilder")
    assert len(load_profile(profile.user_id, tmp_path).history) == 2
    assert engine.select(["R2", "R4"], "click-1").activations == ()
    assert len(load_profile(profile.user_id, tmp_path).history) == 2
    engine.select(["R4"], "click-2")
    assert len(load_profile(profile.user_id, tmp_path).history) == 3
    engine.select(["R2", "R4"], "click-1")
    assert engine.board.read("selected_ids") == ("R4",)
    with pytest.raises(ValueError, match="event ID"):
        engine.select(["R4"], "click-1")


def test_failed_history_save_can_be_retried(ref, rows, profile):
    calls = []

    def writer(current, request):
        calls.append(request)
        if len(calls) == 1:
            raise OSError("disk full")
        return replace(current, history=(SelectionEntry("R1", request.on),))

    engine = BlackboardEngine(ref, selection_writer=writer)
    engine.run(rows, profile)
    with pytest.raises(OSError):
        engine.select(["R1"], "click")
    result = engine.select(["R1"], "click")
    assert result.status == "ok"
    assert len(calls) == 2
    assert len(engine.board.read("effective_profile").history) == 1


def test_invalid_ui_operations_do_not_write_history(ref, rows, profile, tmp_path):
    engine = BlackboardEngine(ref, profiles_dir=tmp_path)
    with pytest.raises(ValueError, match="first"):
        engine.select(["R1"], "click")
    engine.run(rows, profile)
    for ids in ([], ["not-a-recipe"]):
        with pytest.raises(ValueError):
            engine.select(ids, "click")
    with pytest.raises(ValueError):
        engine.decide_substitute("R6", "oil", False)
    assert list(tmp_path.iterdir()) == []


def test_changed_profile_on_disk_stops_selection_before_history_write(ref, rows, profile, tmp_path):
    save_profile(profile, tmp_path)
    engine = BlackboardEngine(ref, profiles_dir=tmp_path)
    engine.run(rows, profile)
    save_profile(replace(profile, allergies=("peanut",)), tmp_path)
    with pytest.raises(ValueError, match="restrictions changed"):
        engine.select(["R1"], "click")
    assert load_profile(profile.user_id, tmp_path).history == ()


def test_combined_substitution_quantities_share_one_inventory(ref, profile, tmp_path):
    save_profile(profile, tmp_path)
    rows = [{"name": "rice", "qty": 200, "unit": "g"},
            {"name": "egg", "qty": 1, "unit": "count"},
            {"name": "milk", "qty": 100, "unit": "ml"},
            {"name": "oil", "qty": 15, "unit": "ml"}]
    engine = BlackboardEngine(ref, profiles_dir=tmp_path)
    engine.run(rows, profile)
    assert engine.select(["R1", "R5"], "click").combined_shopping_list == [("oil", 15, "ml")]


def test_conversion_and_duplicate_overflow_are_flagged(ref, profile):
    rows = [{"name": "rice", "qty": 1e308, "unit": "kg"},
            {"name": "rice", "qty": 1e308, "unit": "g"},
            {"name": "rice", "qty": 1e308, "unit": "g"}]
    engine = BlackboardEngine(ref)
    result = engine.run(rows, profile)
    assert len(result.unrecognized) == 2
    assert engine.board.read("pantry")["rice"].qty == 1e308
