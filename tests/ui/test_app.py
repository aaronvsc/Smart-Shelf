"""Smoke tests for the Streamlit UI in smart_shelf/ui/app.py.

Streamlit's AppTest runs the app without a browser, so we can check that each
screen loads without errors and shows what it should, for both architectures.
None of these tests change a profile, so the real demo profile stays the same.
"""
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from smart_shelf.ui.backends import BACKENDS

APP = str(Path(__file__).parents[2] / "smart_shelf" / "ui" / "app.py")


def start(architecture=None, pantry=None):
    app = AppTest.from_file(APP, default_timeout=30)
    if pantry is not None:
        app.session_state["pantry_start"] = pd.DataFrame(
            pantry, columns=["Ingredient", "Quantity", "Unit", "Expires"])
    app.run()
    assert not app.exception
    if architecture:
        app.sidebar.radio(key="architecture").set_value(architecture).run()
    return app


def titles(app):
    return [m.value for m in app.main.markdown if m.value.startswith("## ")]


def test_app_starts_on_step_one():
    app = start()
    assert titles(app) == ["## Enter your pantry"]
    assert app.sidebar.selectbox(key="user_id").value == "demo"


def test_sidebar_offers_both_architectures():
    app = start()
    assert app.sidebar.radio(key="architecture").options == list(BACKENDS)


def test_demo_profile_restrictions_are_filled_in():
    app = start()
    assert app.multiselect(key="diets_demo").value == ["vegetarian"]
    assert app.multiselect(key="allergies_demo").value == ["peanut"]


@pytest.mark.parametrize("architecture", list(BACKENDS))
def test_find_recipes_moves_to_results(architecture):
    app = start(architecture)
    app.button[0].click().run()
    assert not app.exception
    assert titles(app) == ["## Recipes you can make"]
    assert app.session_state["result"].status == "ok"


@pytest.mark.parametrize("architecture", list(BACKENDS))
def test_unusable_pantry_stays_on_step_one(architecture):
    app = start(architecture, pantry=[("unobtainium", 1, "g", None)])
    app.button[0].click().run()
    assert not app.exception
    assert titles(app) == ["## Enter your pantry"]
    assert any("None of your pantry items" in e.value for e in app.error)
    assert any("unobtainium" in w.value for w in app.warning)


def test_switching_architecture_clears_old_results():
    app = start()
    app.button[0].click().run()
    app.sidebar.radio(key="architecture").set_value("B: Blackboard").run()
    assert titles(app) == ["## Enter your pantry"]
    assert "result" not in app.session_state
