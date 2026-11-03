"""Tests for loading and saving user profiles in smart_shelf/common/data_access.py.

They check that a profile loads correctly, that a missing or broken profile
stops with a ProfileError instead of running without the user's restrictions
(edge case in Section 1.4.1), that a user id can only reach that user's own
file (Privacy), and that saving a selection adds it to the user's history.
"""
import json
from datetime import date

import pytest

from smart_shelf.common.data_access import (
    ProfileError, load_profile, save_profile, save_selection,
)
from smart_shelf.common.models import SelectionEntry, UserProfile


@pytest.fixture
def profiles(tmp_path):
    """A temporary profiles folder with one valid profile in it."""
    (tmp_path / "sam.json").write_text(json.dumps({
        "user_id": "sam", "restrictions": ["vegan"], "allergies": ["peanut"],
        "history": [{"recipe_id": "R001", "selected_at": "2026-10-01"}]}))
    return tmp_path


def test_real_sample_profile_loads():
    profile = load_profile("demo")
    assert profile.restrictions == ("vegetarian",)
    assert profile.allergies == ("peanut",)


def test_load_profile(profiles):
    profile = load_profile("sam", profiles)
    assert profile == UserProfile("sam", ("vegan",), ("peanut",),
                                  (SelectionEntry("R001", date(2026, 10, 1)),))


def test_missing_profile_raises(profiles):
    with pytest.raises(ProfileError, match="can't be loaded"):
        load_profile("nobody", profiles)


def test_broken_profile_raises(profiles):
    (profiles / "sam.json").write_text("{ not json")
    with pytest.raises(ProfileError):
        load_profile("sam", profiles)


def test_bad_date_raises(profiles):
    (profiles / "sam.json").write_text(json.dumps({
        "user_id": "sam", "history": [{"recipe_id": "R001", "selected_at": "yesterday"}]}))
    with pytest.raises(ProfileError, match="invalid content"):
        load_profile("sam", profiles)


def test_file_for_a_different_user_raises(profiles):
    (profiles / "alex.json").write_text(json.dumps({"user_id": "sam"}))
    with pytest.raises(ProfileError, match="belongs to"):
        load_profile("alex", profiles)


@pytest.mark.parametrize("bad_id", ["../sam", "sam/../alex", "Sam", "", "a" * 41, None])
def test_user_id_can_only_reach_its_own_file(profiles, bad_id):
    with pytest.raises(ProfileError, match="Invalid user id"):
        load_profile(bad_id, profiles)


def test_save_selection_adds_to_history(profiles):
    updated = save_selection("sam", ["R002", "R005"], on=date(2026, 10, 27), profiles_dir=profiles)
    assert [h.recipe_id for h in updated.history] == ["R001", "R002", "R005"]
    assert load_profile("sam", profiles) == updated


def test_save_selection_needs_an_existing_profile(profiles):
    with pytest.raises(ProfileError):
        save_selection("nobody", ["R001"], profiles_dir=profiles)


def test_save_and_load_round_trip(tmp_path):
    profile = UserProfile("new_user", ("gluten_free",), (), ())
    save_profile(profile, tmp_path)
    assert load_profile("new_user", tmp_path) == profile
    assert not list(tmp_path.glob("*.tmp"))
