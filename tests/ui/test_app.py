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


def test_pantry_check_blocks_search_until_rows_are_fixed():
    app = start(pantry=[("eggs", 6, "count", None), ("carrots", None, None, None)])
    assert any("1 of 2 items ready" in m.value for m in app.main.markdown)
    assert [w.value for w in app.warning] == ["carrots: add a quantity above 0."]
    assert app.button[0].disabled


def test_ready_pantry_can_search():
    app = start()
    assert any("All 8 items ready." in m.value for m in app.main.markdown)
    assert not app.button[0].disabled


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


# ----------------------------------------------------------- step 4: substitutes

def substitutes(architecture):
    app = results(architecture)
    next(b for b in app.button if b.label == "Review substitutes").click().run()
    assert not app.exception
    return app


def choice_keys(app):
    return [r.key for r in app.main.radio]


@pytest.mark.parametrize("architecture", list(BACKENDS))
def test_review_lists_swaps_from_the_shown_recipes(architecture):
    app = substitutes(architecture)
    assert titles(app) == ["## Review substitutes"]
    assert "sub_R003_tomato" in choice_keys(app)
    assert all(r.value == "Accept" for r in app.main.radio)
    assert any("Updated rankings" in m.value for m in app.main.markdown)


@pytest.mark.parametrize("architecture", list(BACKENDS))
def test_rejecting_a_swap_reranks_and_can_be_undone(architecture):
    app = substitutes(architecture)
    app.radio(key="sub_R003_tomato").set_value("Reject").run()
    assert not app.exception
    r003 = next(r for r in app.session_state["result"].ranked if r.recipe.id == "R003")
    assert "canned tomatoes" not in r003.substitutions
    assert app.radio(key="sub_R003_tomato").value == "Reject"        # still listed, to undo
    assert any("down from #" in m.value for m in app.main.markdown)

    app.radio(key="sub_R003_tomato").set_value("Accept").run()
    r003 = next(r for r in app.session_state["result"].ranked if r.recipe.id == "R003")
    assert r003.substitutions == {"canned tomatoes": "tomato"}


def test_new_search_forgets_old_choices():
    app = substitutes("A: Pipe-and-Filter")
    app.radio(key="sub_R003_tomato").set_value("Reject").run()
    next(b for b in app.button if b.label == "< Back to results").click().run()
    next(b for b in app.button if b.label == "< Back to pantry").click().run()
    app.button[0].click().run()
    assert "rejected" not in app.session_state
    assert not any(str(k).startswith("sub_") for k in app.session_state)


# ----------------------------------------------------------- step 5: pick and shop

SAVE = "Save picks and make shopping list"


def pick_screen(architecture):
    app = substitutes(architecture)
    next(b for b in app.button if b.label == "Choose recipes").click().run()
    assert not app.exception
    assert titles(app) == ["## Pick what you're cooking"]
    return app


def save_button(app):
    return next(b for b in app.button if b.label == SAVE)


def test_save_is_disabled_until_something_is_picked():
    app = pick_screen("A: Pipe-and-Filter")
    assert save_button(app).disabled


@pytest.mark.parametrize("architecture", list(BACKENDS))
def test_saving_picks_records_history_once_and_lists_what_to_buy(architecture, saved_profiles):
    from smart_shelf.common.data_access import load_profile
    app = pick_screen(architecture)
    before = len(load_profile("demo", saved_profiles).history)
    app.checkbox(key="pick_R002").check().run()
    app.checkbox(key="pick_R004").check().run()
    save_button(app).click().run()
    assert not app.exception
    app.run()                                                       # a plain rerun saves nothing new
    history = load_profile("demo", saved_profiles).history
    assert [entry.recipe_id for entry in history[before:]] == ["R002", "R004"]
    assert app.session_state["saved_picks"][1] == [("parmesan", 50.0, "g")]
    assert any(m.value == "parmesan, 50 g" for m in app.main.markdown)
    assert any("Saved to your history" in s.value for s in app.success)
    assert save_button(app).disabled                                # no double save by clicking again


def test_both_architectures_make_the_same_shopping_list():
    lists = []
    for architecture in BACKENDS:
        app = pick_screen(architecture)
        for rid in ("R002", "R004", "R009"):
            app.checkbox(key=f"pick_{rid}").check().run()
        save_button(app).click().run()
        lists.append(app.session_state["saved_picks"])
    assert lists[0] == lists[1]


def test_start_over_returns_to_an_empty_search():
    app = pick_screen("A: Pipe-and-Filter")
    app.checkbox(key="pick_R002").check().run()
    save_button(app).click().run()
    next(b for b in app.button if b.label == "Start over").click().run()
    assert titles(app) == ["## Enter your pantry"]
    assert "saved_picks" not in app.session_state and "result" not in app.session_state
