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


def find_button(app):
    return next(b for b in app.button if b.label == "Find recipes")


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
    find_button(app).click().run()
    assert not app.exception
    assert titles(app) == ["## Recipes you can make"]
    assert app.session_state["result"].status == "ok"


def test_pantry_check_blocks_search_until_rows_are_fixed():
    app = start(pantry=[("eggs", 6, "count", None), ("carrots", None, None, None)])
    assert any("1 of 2 items ready" in m.value for m in app.main.markdown)
    assert [w.value for w in app.warning] == ["carrots: add a quantity above 0."]
    assert find_button(app).disabled


def test_ready_pantry_can_search():
    app = start()
    assert any("All 8 items ready." in m.value for m in app.main.markdown)
    assert not find_button(app).disabled


def test_switching_architecture_clears_old_results():
    app = start()
    find_button(app).click().run()
    app.sidebar.radio(key="architecture").set_value("B: Blackboard").run()
    assert titles(app) == ["## Enter your pantry"]
    assert "result" not in app.session_state


# ----------------------------------------------------------- step 3: results

def results(architecture="A: Pipe-and-Filter", pantry=None):
    app = start(architecture, pantry)
    find_button(app).click().run()
    assert not app.exception
    return app


def cards(app):
    """The recipe cards' titles; each title is the checkbox for choosing that recipe."""
    return [c.label for c in app.main.checkbox if c.key.startswith("choose_")]


def checked(app):
    return sorted(c.key.removeprefix("choose_") for c in app.main.checkbox
                  if c.key.startswith("choose_") and c.value)


def button(app, starts_with):
    return next(b for b in app.button if b.label.startswith(starts_with))


@pytest.mark.parametrize("architecture", list(BACKENDS))
def test_results_show_and_check_the_top_ten(architecture):
    app = results(architecture)
    assert cards(app)[0] == "**1. Spaghetti Marinara**"
    assert len(cards(app)) == 10 and len(checked(app)) == 10
    assert any("Only the recipes you check go on" in m.value for m in app.main.markdown)
    assert button(app, "Review substitutes").label == "Review substitutes for 10 recipes"
    assert any("Hidden for your diet (" in m.value for m in app.main.markdown)


def test_show_top_shows_more_without_checking_them():
    app = results()
    app.selectbox(key="show_top").select(20).run()
    assert len(cards(app)) == 20
    assert len(checked(app)) == 10
    app.selectbox(key="show_top").select("All").run()
    assert len(cards(app)) == len(app.session_state["result"].ranked)


def test_checking_and_unchecking_changes_what_goes_on():
    app = results()
    app.selectbox(key="show_top").select(20).run()
    app.checkbox(key="choose_R147").check().run()
    app.checkbox(key="choose_R003").uncheck().run()
    assert "R147" in checked(app) and "R003" not in checked(app)
    assert button(app, "Review substitutes").label == "Review substitutes for 10 recipes"
    app.selectbox(key="show_top").select(10).run()                # hidden, but still chosen
    assert "R147" in app.session_state["chosen"]


def test_nothing_checked_means_no_review():
    app = results()
    for key in checked(app):
        app.checkbox(key=f"choose_{key}").uncheck().run()
    assert button(app, "Review substitutes").disabled


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
    find_button(app).click().run()
    assert not app.exception
    assert load_profile("demo", saved_profiles).restrictions == ("vegetarian",)
    assert (PROFILES_DIR / "demo.json").read_text() == sample


# ----------------------------------------------------------- step 4: substitutes

def substitutes(architecture, uncheck=(), check=()):
    app = results(architecture)
    if check:
        app.selectbox(key="show_top").select(20).run()
    for rid in uncheck:
        app.checkbox(key=f"choose_{rid}").uncheck().run()
    for rid in check:
        app.checkbox(key=f"choose_{rid}").check().run()
    button(app, "Review substitutes").click().run()
    assert not app.exception
    return app


def choice_keys(app):
    return [r.key for r in app.main.radio]


@pytest.mark.parametrize("architecture", list(BACKENDS))
def test_review_lists_swaps_only_for_chosen_recipes(architecture):
    app = substitutes(architecture, uncheck=["R002"], check=["R147"])
    assert titles(app) == ["## Review substitutes"]
    keys = choice_keys(app)
    assert "sub_R003_tomato" in keys and "sub_R147_olive oil" in keys
    assert "sub_R002_olive oil" not in keys
    assert all(r.value == "Accept" for r in app.main.radio)
    assert any("Swaps for the 10 recipes you chose" in m.value for m in app.main.markdown)


@pytest.mark.parametrize("architecture", list(BACKENDS))
def test_rejecting_a_swap_reranks_only_the_chosen_recipes(architecture):
    app = substitutes(architecture)
    app.radio(key="sub_R003_tomato").set_value("Reject").run()
    assert not app.exception
    r003 = next(r for r in app.session_state["result"].ranked if r.recipe.id == "R003")
    assert "canned tomatoes" not in r003.substitutions
    assert app.radio(key="sub_R003_tomato").value == "Reject"        # still listed, to undo
    ranking = [m.value for m in app.main.markdown if m.value[:1].isdigit()]
    assert len(ranking) == 10                                       # only the chosen recipes
    assert any("Spaghetti Marinara" in line and "down from #1" in line for line in ranking)

    app.radio(key="sub_R003_tomato").set_value("Accept").run()
    r003 = next(r for r in app.session_state["result"].ranked if r.recipe.id == "R003")
    assert r003.substitutions == {"canned tomatoes": "tomato"}


def test_new_search_forgets_old_choices():
    app = substitutes("A: Pipe-and-Filter")
    app.radio(key="sub_R003_tomato").set_value("Reject").run()
    button(app, "< Back to results").click().run()
    button(app, "< Back to pantry").click().run()
    find_button(app).click().run()
    assert "rejected" not in app.session_state
    assert not any(str(k).startswith("sub_") for k in app.session_state)


# ----------------------------------------------------------- step 5: pick and shop

SAVE = "Save picks and make shopping list"


def pick_screen(architecture, **chosen):
    app = substitutes(architecture, **chosen)
    button(app, "Choose recipes").click().run()
    assert not app.exception
    assert titles(app) == ["## Pick what you're cooking"]
    return app


def picks(app):
    return sorted(c.key.removeprefix("pick_") for c in app.main.checkbox
                  if c.key.startswith("pick_") and c.value)


def test_step_five_starts_with_every_chosen_recipe_checked():
    app = pick_screen("A: Pipe-and-Filter", uncheck=["R002"], check=["R147"])
    assert len(picks(app)) == 10
    assert "R147" in picks(app) and "R002" not in picks(app)


def test_save_is_disabled_when_everything_is_unchecked():
    app = pick_screen("A: Pipe-and-Filter")
    for rid in picks(app):
        app.checkbox(key=f"pick_{rid}").uncheck().run()
    assert button(app, SAVE).disabled


@pytest.mark.parametrize("architecture", list(BACKENDS))
def test_saving_picks_records_history_once_and_lists_what_to_buy(architecture, saved_profiles):
    from smart_shelf.common.data_access import load_profile
    app = pick_screen(architecture)
    before = len(load_profile("demo", saved_profiles).history)
    for rid in picks(app):
        if rid not in ("R002", "R004"):
            app.checkbox(key=f"pick_{rid}").uncheck().run()
    button(app, SAVE).click().run()
    assert not app.exception
    app.run()                                                       # a plain rerun saves nothing new
    history = load_profile("demo", saved_profiles).history
    assert [entry.recipe_id for entry in history[before:]] == ["R002", "R004"]
    assert app.session_state["saved_picks"]["list"] == [("parmesan", 50.0, "g")]
    assert any(m.value == "parmesan, 50 g" for m in app.main.markdown)
    assert any("Saved to your history" in s.value for s in app.success)
    assert button(app, "Update shopping list").disabled             # no double save by clicking again


def test_both_architectures_make_the_same_shopping_list():
    lists = []
    for architecture in BACKENDS:
        app = pick_screen(architecture)
        button(app, SAVE).click().run()
        saved = app.session_state["saved_picks"]
        lists.append((saved["ids"], saved["list"]))
    assert lists[0] == lists[1]
    assert len(lists[0][0]) == 10


def test_start_over_returns_to_an_empty_search():
    app = pick_screen("A: Pipe-and-Filter")
    button(app, SAVE).click().run()
    button(app, "Start over").click().run()
    assert titles(app) == ["## Enter your pantry"]
    assert "saved_picks" not in app.session_state and "result" not in app.session_state
    assert "chosen" not in app.session_state


# ----------------------------------------------------------- step 1: add ingredient bar

def add_button(app):
    return next(b for b in app.button if b.label == "Add")


def test_add_bar_offers_only_known_ingredients_and_their_units():
    app = start()
    names = app.selectbox(key="add_name")
    assert "carrot" in names.options                           # the same plain name as the table
    assert "unobtainium" not in names.options
    assert add_button(app).disabled
    names.select("egg").run()
    assert app.selectbox(key="add_unit_egg").options == ["count"]


def test_starting_pantry_uses_the_same_names_as_the_add_bar():
    app = start()
    names = set(app.selectbox(key="add_name").options)
    assert set(app.session_state["pantry_start"]["Ingredient"]) <= names


def test_adding_an_ingredient_puts_it_in_the_table_and_clears_the_bar():
    app = start()
    app.selectbox(key="add_name").select("carrot").run()
    app.number_input(key="add_qty").set_value(3).run()
    assert not add_button(app).disabled
    add_button(app).click().run()
    assert not app.exception
    table = app.session_state["pantry_start"]
    assert list(table.iloc[-1][["Ingredient", "Quantity", "Unit"]]) == ["carrot", 3, "count"]
    assert len(table) == 9
    assert app.selectbox(key="add_name").value is None
    assert any("All 9 items ready." in m.value for m in app.main.markdown)


# ----------------------------------------------------------- step 3: custom show-top number
# AppTest can't type into a dropdown, so these store what typing would, while the
# results screen is off-screen (AppTest can't redraw a dropdown with a new value).

def results_with_typed_top(typed):
    app = results()
    button(app, "< Back to pantry").click().run()
    app.session_state["show_top"] = typed
    app.session_state["step"] = 3
    app.run()
    assert not app.exception
    return app

def test_show_top_accepts_a_typed_number():
    app = results_with_typed_top("35")
    assert len(cards(app)) == 35
    assert len(checked(app)) == 10
    assert app.selectbox(key="show_top").options == ["10", "20", "35", "50", "All"]


def test_show_top_rejects_text_that_is_not_a_number():
    app = results_with_typed_top("lots")
    assert len(cards(app)) == 10
    assert any("isn't a number of recipes" in w.value for w in app.warning)
    assert app.selectbox(key="show_top").value == 10


# ----------------------------------------------------------- step 5: details beside each pick

@pytest.mark.parametrize("architecture", list(BACKENDS))
def test_step_five_shows_rank_match_and_what_is_still_needed(architecture):
    app = pick_screen(architecture)
    labels = [c.label for c in app.main.checkbox if c.key.startswith("pick_")]
    assert labels[0] == "**1. Spaghetti Marinara** | 90% match | 25 min"
    assert all(f"**{n}. " in label and "% match" in label for n, label in enumerate(labels, start=1))
    needs = [m.value for m in app.main.markdown if m.value.startswith("<div class='pick-need'>")]
    assert len(needs) == len(labels)
    assert any("Ready to cook. Nothing to buy." in n for n in needs)
    assert any("Still need: parmesan (50 g)" in n for n in needs)


# ----------------------------------------------------------- step 3: plain-language score

@pytest.mark.parametrize("architecture", list(BACKENDS))
def test_ranking_explanation_is_plain_and_adds_up(architecture):
    import re
    app = results(architecture)
    first = app.main.expander[0]
    assert first.label == "Why it's ranked #1"
    text = first.markdown[0].value
    assert "You have 4 of the 5 main ingredients." in text
    assert "covered by a substitute (tomato for canned tomatoes)" in text
    assert "Optional, and fine to skip: basil, salt." in text
    # The four bold numbers: match points, freshness bonus, history bonus, total.
    match, fresh, liked, total = [float(n) for n in re.findall(r"([\d.]+)(?: points)?\.\*\*", text)]
    assert round(match + fresh + liked, 1) == total


# ----------------------------------------------------------- step 4: swap order

@pytest.mark.parametrize("architecture", list(BACKENDS))
def test_swaps_are_listed_in_ranked_order_and_stay_put(architecture):
    app = substitutes(architecture)
    first = choice_keys(app)
    # Ranked order: #1 Spaghetti Marinara, #2 Scrambled Eggs, #4 Penne alla Vodka Style, ...
    assert first[:3] == ["sub_R003_tomato", "sub_R002_olive oil", "sub_R079_milk"]
    app.radio(key="sub_R003_tomato").set_value("Reject").run()     # R003 drops in the ranking
    assert choice_keys(app)[:3] == first[:3]                         # but its card doesn't move


# ----------------------------------------------------------- step 5: times per recipe

def only_pick(app, keep):
    for rid in picks(app):
        if rid not in keep:
            app.checkbox(key=f"pick_{rid}").uncheck().run()


@pytest.mark.parametrize("architecture", list(BACKENDS))
def test_times_scale_the_list_and_changing_them_adds_no_history(architecture, saved_profiles):
    from smart_shelf.common.data_access import load_profile
    app = pick_screen(architecture)
    only_pick(app, ["R004"])           # Garlic Butter Pasta: 50 g parmesan to buy for one batch
    app.number_input(key="times_R004").set_value(3).run()
    button(app, SAVE).click().run()
    # Three batches also use up the pantry's 4 garlic and 500 g pasta.
    assert app.session_state["saved_picks"]["list"] == [
        ("garlic", 8.0, "count"), ("parmesan", 150.0, "g"), ("pasta", 100.0, "g")]
    history = len(load_profile("demo", saved_profiles).history)

    app.number_input(key="times_R004").set_value(2).run()
    assert any("Press Update shopping list" in m.value for m in app.main.markdown)
    button(app, "Update shopping list").click().run()
    assert not app.exception
    assert app.session_state["saved_picks"]["list"] == [("garlic", 4.0, "count"),
                                                        ("parmesan", 100.0, "g")]
    assert len(load_profile("demo", saved_profiles).history) == history    # no new history
    assert button(app, "Update shopping list").disabled


def test_times_box_is_off_for_unchecked_recipes():
    app = pick_screen("A: Pipe-and-Filter")
    app.checkbox(key="pick_R002").uncheck().run()
    assert app.number_input(key="times_R002").disabled
    assert not app.number_input(key="times_R003").disabled
