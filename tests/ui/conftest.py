"""Shared setup for the UI tests.

Every UI test gets its own empty temp folder for saved profiles, so running the
tests never creates data/user_profiles/ or changes the sample profiles in git.
"""
import pytest


@pytest.fixture(autouse=True)
def saved_profiles(tmp_path, monkeypatch):
    folder = tmp_path / "user_profiles"
    monkeypatch.setenv("SMART_SHELF_PROFILES", str(folder))
    return folder
