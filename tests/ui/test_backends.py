"""Tests for smart_shelf/ui/backends.py, the UI's front door to A and B.

Every test runs against both architectures with the real data, to show the
UI gets the same answers and the same saving behavior from either one.
Profiles are copied to a temp folder so the real demo profile never changes.
"""
import shutil
from datetime import date

import pytest

from smart_shelf.common.data_access import DATA_DIR, load_profile, load_reference_data
from smart_shelf.ui.backends import BACKENDS

TODAY = date(2026, 11, 14)
PANTRY = [{"name": name, "qty": qty, "unit": unit} for name, qty, unit in [
    ("rice", 400, "g"), ("egg", 6, "count"), ("olive oil", 200, "ml"), ("onion", 2, "count"),
    ("garlic", 4, "count"), ("pasta", 500, "g"), ("tomato", 4, "count"), ("milk", 500, "ml")]]


@pytest.fixture(scope="module")
def ref():
    return load_reference_data()


@pytest.fixture
def profiles_dir(tmp_path):
    shutil.copytree(DATA_DIR / "profiles", tmp_path / "profiles")
    return tmp_path / "profiles"


@pytest.fixture(params=list(BACKENDS))
def backend(request, ref, profiles_dir):
    return BACKENDS[request.param](ref, profiles_dir)


def start(backend, profiles_dir):
    return backend.run(PANTRY, load_profile("demo", profiles_dir), today=TODAY)


def test_run_ranks_recipes(backend, profiles_dir):
    result = start(backend, profiles_dir)
    assert result.status == "ok"
    assert result.ranked[0].recipe.id == "R003"
    assert result.ranked[0].substitutions == {"canned tomatoes": "tomato"}


def test_rejecting_then_accepting_a_substitute(backend, profiles_dir):
    start(backend, profiles_dir)
    rejected = backend.decide_substitute("R003", "tomato", accepted=False)
    r003 = next(r for r in rejected.ranked if r.recipe.id == "R003")
    assert "canned tomatoes" not in r003.substitutions
    accepted = backend.decide_substitute("R003", "tomato", accepted=True)
    assert accepted.ranked[0].substitutions == {"canned tomatoes": "tomato"}


def test_select_saves_history_once_per_click(backend, profiles_dir):
    start(backend, profiles_dir)
    before = len(load_profile("demo", profiles_dir).history)
    backend.select(["R002", "R004"], event_id="click-1")
    backend.select(["R002", "R004"], event_id="click-1")      # a Streamlit rerun of the same click
    history = load_profile("demo", profiles_dir).history
    assert len(history) == before + 2
    assert {entry.recipe_id for entry in history[-2:]} == {"R002", "R004"}


def test_select_rejects_recipes_that_were_not_ranked(backend, profiles_dir):
    start(backend, profiles_dir)
    with pytest.raises(ValueError):
        backend.select(["R999"], event_id="click-1")


def test_calls_before_run_are_refused(backend):
    with pytest.raises(ValueError):
        backend.select(["R002"], event_id="click-1")


def test_both_architectures_give_the_same_answers(ref, tmp_path):
    answers = []
    for name, cls in BACKENDS.items():
        folder = tmp_path / name[0]
        shutil.copytree(DATA_DIR / "profiles", folder)
        backend = cls(ref, folder)
        backend.run(PANTRY, load_profile("demo", folder), today=TODAY)
        result = backend.decide_substitute("R003", "tomato", accepted=False)
        ranking = [r.recipe.id for r in result.ranked]
        # Compare what the user sees. (After select, B re-ranks with the new
        # history right away; A uses it on the next run.)
        shopping = backend.select(["R002", "R004", "R150"], event_id="click-1")
        answers.append((ranking, [(n, round(q, 6), u) for n, q, u in shopping]))
    assert answers[0] == answers[1]
