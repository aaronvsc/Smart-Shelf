"""Smoke tests for the Streamlit UI in smart_shelf/ui/app.py.

Streamlit's AppTest runs the app without a browser, so we can check that each
screen loads without errors and shows what it should, for both architectures.
Profiles are read from a temp copy (see conftest.py), so the samples in git never change.
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


def test_demo_profile_starts_with_no_restrictions():
    app = start()
    assert app.multiselect(key="diets_demo").value == []
    assert app.multiselect(key="allergies_demo").value == []


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


# ----------------------------------------------------------- step 3: results

def results(architecture="A: Pipe-and-Filter", pantry=None):
    app = start(architecture, pantry)
    app.button[0].click().run()
    assert not app.exception
    return app


def cards(app):
    return [m.value for m in app.main.markdown if m.value.startswith("**")]


@pytest.mark.parametrize("architecture", list(BACKENDS))
def test_results_show_the_top_ten_cards(architecture):
    app = results(architecture)
    assert cards(app)[0] == "**1. Spaghetti Marinara**"
    assert len(cards(app)) == 10
    assert any("Hidden for your diet (" in m.value for m in app.main.markdown)


def test_show_more_adds_ten_cards():
    app = results()
    next(b for b in app.button if b.label == "Show 10 more").click().run()
    assert len(cards(app)) == 20


def test_every_recipe_breaking_the_diet_explains_why():
    # Run a vegetarian with only chicken directly, so the real demo profile isn't edited.
    from smart_shelf.common.data_access import load_reference_data
    from smart_shelf.common.models import UserProfile
    result = BACKENDS["A: Pipe-and-Filter"](load_reference_data()).run(
        [{"name": "chicken breast", "qty": 500, "unit": "g"}], UserProfile("test", ("vegetarian",)))
    app = start()
    app.session_state["result"] = result
    app.session_state["step"] = 3
    app.run()
    assert not app.exception
    assert cards(app) == []
    assert any("breaks your diet" in i.value for i in app.info)
    assert any("Hidden for your diet (" in m.value for m in app.main.markdown)


def test_no_matches_explains_what_to_add():
    from smart_shelf.arch_a.records import PipelineResult
    app = start()
    app.session_state["result"] = PipelineResult("no_matches")
    app.session_state["step"] = 3
    app.run()
    assert not app.exception
    assert any("None of our recipes" in i.value for i in app.info)


def test_back_button_returns_to_pantry():
    app = results()
    next(b for b in app.button if b.label == "< Back to pantry").click().run()
    assert titles(app) == ["## Enter your pantry"]


# ----------------------------------------------------------- saved profile copy

def test_app_works_on_a_copy_of_the_sample_profiles(saved_profiles):
    from smart_shelf.common.data_access import PROFILES_DIR, load_profile
    sample = (PROFILES_DIR / "demo.json").read_text()
    app = start()
    app.multiselect(key="diets_demo").set_value(["vegetarian"]).run()
    app.button[0].click().run()
    assert not app.exception
    assert load_profile("demo", saved_profiles).restrictions == ("vegetarian",)
    assert (PROFILES_DIR / "demo.json").read_text() == sample
