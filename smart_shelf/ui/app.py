"""Smart-Shelf user interface (Streamlit).

One set of screens for both architectures. The sidebar switch picks which
architecture does the work behind the screens; what the user sees stays the
same. The five steps follow section 1.4.1 of our proposal.

Run from the Smart-Shelf folder:   streamlit run smart_shelf/ui/app.py
"""
import base64
import os
import shutil
import sys
from datetime import date
from pathlib import Path
from uuid import uuid4

import pandas as pd
import streamlit as st

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parents[1]))    # so `import smart_shelf` works when Streamlit runs this file

from smart_shelf.common.data_access import (  # noqa: E402
    DATA_DIR, PROFILES_DIR, DataError, ProfileError, load_profile, load_reference_data, save_profile,
)
from smart_shelf.common.models import UserProfile  # noqa: E402
from smart_shelf.ui.backends import BACKENDS  # noqa: E402
from smart_shelf.ui.pantry_check import check_pantry, units_for  # noqa: E402

STEPS = ["Enter pantry", "Finding recipes", "Results", "Review substitutes", "Shopping list"]
LOGO = base64.b64encode((HERE / "logo.svg").read_bytes()).decode()
PANTRY_COLUMNS = ["Ingredient", "Quantity", "Unit", "Expires"]
UNITS = ["g", "kg", "oz", "lb", "ml", "l", "fl oz", "tsp", "tbsp", "cup",
         "count", "clove", "slice", "stick", "can"]
# A starting pantry so the app can be tried right away; the user can edit or clear it.
SAMPLE_PANTRY = [
    ("rice", 400, "g", None), ("egg", 6, "count", None), ("olive oil", 200, "ml", None),
    ("onion", 2, "count", None), ("garlic", 4, "clove", None), ("pasta", 500, "g", None),
    ("tomato", 4, "count", "2026-11-16"), ("milk", 2, "cup", "2026-11-18"),
]

# Extra styling the theme in .streamlit/config.toml can't do on its own.
CSS = """
<style>
header[data-testid="stHeader"], [data-testid="stSidebarHeader"] {display: none;}
[data-testid="stMainBlockContainer"] {padding-top: 2.4rem; padding-bottom: 2rem;}
* {border-radius: 0 !important;}
button[kind="primary"] p {color: #0D1117; font-weight: 600;}
.brand {display: flex; align-items: center; gap: 12px; margin: 4px 0 28px 0;}
.brand img {width: 44px; height: 44px;}
.brand span {font-size: 1.35rem; font-weight: 700; letter-spacing: 0.02em;}
.step-label {font-size: 0.78rem; letter-spacing: 0.14em; color: #3B82F6; font-weight: 600;}
.label {font-size: 0.72rem; letter-spacing: 0.12em; color: #8B949E; font-weight: 600;
        text-transform: uppercase; margin-bottom: 2px;}
.muted {color: #8B949E;}
.score {font-size: 1.6rem; font-weight: 700; line-height: 1; text-align: right; color: #3B82F6;}
.pick-need {color: #8B949E; margin: -10px 0 12px 28px; font-size: 0.9rem;}
.score-label {font-size: 0.7rem; letter-spacing: 0.14em; color: #8B949E; text-align: right;}
.steps div {padding: 6px 0 6px 12px; border-left: 2px solid #30363D; color: #6E7681;}
.steps div.done {color: #8B949E;}
.up {color: #3B82F6;} .down {color: #F0F6FC;}
.steps div.current {border-left-color: #3B82F6; color: #F0F6FC; font-weight: 600;}
</style>
"""


# ---------------------------------------------------------------- data and state

@st.cache_resource
def reference_data():
    """The read-only data stores, loaded once and shared by every session."""
    return load_reference_data()


def saved_profiles_dir() -> Path:
    """Where the app reads and writes profiles: a git-ignored copy of data/profiles/.

    Using the app changes a profile (diet edits, recipe history), so it works on a
    copy and the sample profiles in git stay the same. Delete data/user_profiles/
    to start fresh. Tests point SMART_SHELF_PROFILES at a temp folder instead.
    """
    folder = Path(os.environ.get("SMART_SHELF_PROFILES", DATA_DIR / "user_profiles"))
    folder.mkdir(parents=True, exist_ok=True)
    for sample in PROFILES_DIR.glob("*.json"):
        if not (folder / sample.name).exists():
            shutil.copy(sample, folder / sample.name)
    return folder


def profile_ids():
    return sorted(path.stem for path in saved_profiles_dir().glob("*.json"))


def split_rules(ref):
    """Allergy rules block one tag with the same name (peanut, egg); the rest are diets."""
    allergies = sorted(name for name, tags in ref.restrictions.items() if tags == {name})
    diets = sorted(set(ref.restrictions) - set(allergies))
    return diets, allergies


def clear_run():
    """Forget the last search: its backend, results and substitute choices."""
    for key in ("backend", "result", "problem", "chosen", "show_top", "rejected",
                "ranking_before", "pending_pick", "saved_picks"):
        st.session_state.pop(key, None)
    for key in [key for key in st.session_state if str(key).startswith(("sub_", "pick_", "choose_", "times_"))]:
        del st.session_state[key]


def reset():
    """Start over: a new architecture or user means a fresh backend and no old results."""
    clear_run()
    st.session_state.step = 1


def go(step):
    st.session_state.step = step


def pantry_rows(table: pd.DataFrame) -> list[dict]:
    """Turn the edited table into the rows both architectures accept. Blank rows are skipped;
    anything else is passed on, so the architectures can explain what's wrong with it."""
    rows = []
    for row in table.to_dict("records"):
        name, qty = row["Ingredient"], row["Quantity"]
        if (pd.isna(name) or not str(name).strip()) and pd.isna(qty):
            continue
        expires = row["Expires"]
        rows.append({"name": "" if pd.isna(name) else str(name),
                     "qty": None if pd.isna(qty) else float(qty),
                     "unit": "" if pd.isna(row["Unit"]) else row["Unit"],
                     "expires": None if pd.isna(expires) else pd.Timestamp(expires).date()})
    return rows


# ---------------------------------------------------------------- layout helpers

def html(text):
    st.markdown(text, unsafe_allow_html=True)


def sidebar():
    with st.sidebar:
        html(f"<div class='brand'><img src='data:image/svg+xml;base64,{LOGO}'>"
             "<span>Smart-Shelf</span></div>")
        st.selectbox("Signed in as", profile_ids(), key="user_id", on_change=reset)
        st.radio("Architecture", list(BACKENDS), key="architecture", on_change=reset)
        st.divider()
        rows = []
        for number, name in enumerate(STEPS, start=1):
            state = ("current" if number == st.session_state.step
                     else "done" if number < st.session_state.step else "")
            rows.append(f"<div class='{state}'>{number}. {name}</div>")
        html("<div class='label'>Steps</div><div class='steps'>" + "".join(rows) + "</div>")


def page_title(title):
    html(f"<div class='step-label'>STEP {st.session_state.step} OF {len(STEPS)}</div>")
    st.markdown(f"## {title}")


def show_unrecognized(items):
    for item in items:
        name = item.row.get("name") if isinstance(item.row, dict) else None
        st.warning(f"“{name or 'A row'}” was skipped: {item.reason}.")


# ---------------------------------------------------------------- step 1 (and 2)

def screen_pantry(ref):
    page_title("Enter your pantry")
    html("<span class='muted'>Expiration dates are optional, but they help us suggest recipes "
         "that use food before it goes bad.</span>")
    st.write("")

    try:
        profile = load_profile(st.session_state.user_id, saved_profiles_dir())
    except ProfileError as error:
        st.error(f"Your profile couldn't be loaded, so we can't check your diet: {error}")
        return

    left, right = st.columns([0.64, 0.36], gap="large")
    with left:
        st.session_state.setdefault("pantry_start", pd.DataFrame(
            [(name, qty, unit, pd.to_datetime(expires)) for name, qty, unit, expires in SAMPLE_PANTRY],
            columns=PANTRY_COLUMNS))
        add_bar(ref)
        # Ingredient names can't be typed here; new ones come from the Add bar above,
        # so only names in our data get in. Amounts, units and dates stay editable.
        table = st.data_editor(
            st.session_state.pantry_start, num_rows="delete", hide_index=True, width="stretch",
            column_config={
                "Ingredient": st.column_config.TextColumn(width="medium", disabled=True),
                "Quantity": st.column_config.NumberColumn(min_value=0, width="small"),
                "Unit": st.column_config.SelectboxColumn(options=UNITS, width="small"),
                "Expires": st.column_config.DateColumn(format="MMM D, YYYY", width="small"),
            },
            key="pantry_editor",
        )
        st.session_state.pantry_current = table
        html("<span class='muted'>To remove a row, select it on the left edge and press "
             "Delete.</span>")
    with right:
        diets, allergies = split_rules(ref)
        with st.container(border=True):
            chosen_diets = st.multiselect("Dietary restrictions", diets,
                                          default=[r for r in profile.restrictions if r in diets],
                                          key=f"diets_{profile.user_id}")
            chosen_allergies = st.multiselect("Allergies", allergies,
                                              default=[a for a in profile.allergies if a in allergies],
                                              key=f"allergies_{profile.user_id}")
            html("<span class='muted'>Changes are saved to your profile when you search.</span>")

        rows = pantry_rows(table)
        problems = check_pantry(rows, ref)
        with st.container(border=True):
            html("<div class='label'>Pantry check</div>")
            if not rows:
                html("<span class='muted'>Add at least one ingredient.</span>")
            elif problems:
                html(f"{len(rows) - len(problems)} of {len(rows)} items ready. "
                     "Fix or delete these rows to search:")
                for problem in problems:
                    st.warning(problem)
            else:
                html(f"All {len(rows)} items ready.")
            if st.session_state.get("problem"):
                st.error(st.session_state.problem)
                show_unrecognized(st.session_state.get("unrecognized", []))

        if st.button("Find recipes", type="primary", disabled=not rows or bool(problems)):
            find_recipes(ref, profile, chosen_diets, chosen_allergies, rows)


def add_bar(ref):
    """Search our ingredient list as you type, then add the ingredient to the table."""
    with st.container(border=True):
        html("<div class='label'>Add an ingredient</div>")
        name_col, qty_col, unit_col, date_col, button_col = st.columns(
            [0.36, 0.16, 0.16, 0.2, 0.12], vertical_alignment="bottom")
        # The same names the table, recipe cards and shopping list use.
        name = name_col.selectbox("Ingredient", sorted(ref.ingredients), index=None,
                                  placeholder="Start typing, e.g. carrot", key="add_name")
        qty = qty_col.number_input("Quantity", min_value=0.0, value=None, step=1.0, key="add_qty")
        # Only units that work for this ingredient (eggs: count; flour: g, cup, ...).
        unit = unit_col.selectbox("Unit", units_for(ref, name) if name else [],
                                  key=f"add_unit_{name}", disabled=not name)
        expires = date_col.date_input("Expires (optional)", value=None, key="add_expires")
        ready = bool(name and qty and qty > 0 and unit)
        button_col.button("Add", disabled=not ready, on_click=add_row,
                          args=(name, qty, unit, expires))


def add_row(name, qty, unit, expires):
    """Put the new ingredient at the bottom of the table, keeping the edits made so far."""
    current = st.session_state.get("pantry_current", st.session_state.pantry_start)
    new = pd.DataFrame([(name, qty, unit, pd.to_datetime(expires))], columns=PANTRY_COLUMNS)
    st.session_state.pantry_start = pd.concat([current, new], ignore_index=True)
    st.session_state.pop("pantry_editor", None)     # those edits now live in pantry_start
    st.session_state.add_name = None                 # clear the bar for the next ingredient
    st.session_state.add_qty = None
    st.session_state.add_expires = None


def find_recipes(ref, profile, diets, allergies, rows):
    """Step 2: save any diet changes, then hand the pantry to the chosen architecture."""
    if (tuple(diets), tuple(allergies)) != (profile.restrictions, profile.allergies):
        profile = UserProfile(profile.user_id, tuple(diets), tuple(allergies), profile.history)
        save_profile(profile, saved_profiles_dir())

    st.session_state.step = 2
    backend = BACKENDS[st.session_state.architecture](ref, saved_profiles_dir())
    with st.spinner(f"Checking your pantry against {len(ref.recipes)} recipes"):
        result = backend.run(rows, profile)
    clear_run()
    st.session_state.backend, st.session_state.result = backend, result
    st.session_state.unrecognized = result.unrecognized

    if result.status == "empty_pantry":
        st.session_state.problem = "None of your pantry items could be used. Fix the rows below and try again."
        st.session_state.step = 1
    else:
        st.session_state.pop("problem", None)
        st.session_state.step = 3
    st.rerun()


# ---------------------------------------------------------------- step 3

DEFAULT_TOP = 10                      # top recipes shown and checked after a search
SHOW_TOP = [10, 20, 50, "All"]        # how many ranked recipes step 3 can show
PREVIEW = 10                          # rows shown before "more" in the hidden-for-diet box


def amount(qty, unit):
    """50.0 g -> '50 g', 0.333 cup -> '0.33 cup'."""
    return f"{round(qty, 2):g} {unit}"


def chosen_records(result):
    """The recipes the user checked on step 3, in their current ranked order."""
    return [record for record in result.ranked if record.recipe.id in st.session_state.chosen]


def show_top_options():
    """The 'Show top' choices, plus the number the user typed, if any.

    A typed value arrives as text. A whole number above 0 becomes a choice in the
    list; anything else gets a warning and the box goes back to the default.
    """
    typed = st.session_state.get("show_top")
    if typed is None or typed in SHOW_TOP:
        return SHOW_TOP
    text = str(typed).strip()
    if text.isdigit() and int(text) > 0:
        st.session_state.show_top = int(text)
        return SHOW_TOP if int(text) in SHOW_TOP else sorted(SHOW_TOP[:-1] + [int(text)]) + ["All"]
    st.warning(f"\u201c{typed}\u201d isn't a number of recipes, so we're showing the top "
               f"{DEFAULT_TOP}. Type a whole number like 35.")
    st.session_state.show_top = DEFAULT_TOP
    return SHOW_TOP


def toggle_choice(recipe_id):
    if st.session_state[f"choose_{recipe_id}"]:
        st.session_state.chosen.add(recipe_id)
    else:
        st.session_state.chosen.discard(recipe_id)


def pantry_match(record):
    """Score = how well the pantry covers the recipe + freshness boost + history boost,
    so taking the boosts off leaves the match shown as 'Match %'."""
    return record.score - record.freshness_boost - record.preference_boost


def still_need(record):
    """'parmesan (50 g), shrimp (200 g)': exactly what's left to buy for one recipe."""
    return ", ".join(f"{gap.name} ({amount(gap.short_qty, gap.unit)})" for gap in record.to_buy)


def points(value):
    """A score part as points out of 100, to one decimal: 0.9 -> 90.0, 0.025 -> 2.5."""
    return round(value * 100, 1)


def show(pts):
    """90.0 -> '90', 2.5 -> '2.5'."""
    return f"{pts:g}"


def plural(count, word):
    return f"{count} {word}" if count == 1 else f"{count} {word}s"


def score_explanation(record):
    """The ranking score in plain words: points for the pantry match, plus small bonuses.
    The total is the sum of the numbers shown, so it always adds up on screen."""
    recipe = record.recipe
    required = [item.name for item in recipe.ingredients if item.required]
    have = [name for name in record.on_hand if name in required]
    swaps = ", ".join(f"{use} for {need}" for need, use in record.substitutions.items())
    optional = [gap.name for gap in record.missing if not gap.required]
    match, fresh, liked = (points(pantry_match(record)), points(record.freshness_boost),
                           points(record.preference_boost))

    match_line = (f"**Pantry match: {show(match)} points.** You have {len(have)} of "
                  f"the {plural(len(required), 'main ingredient')}.")
    if swaps:
        count = len(record.substitutions)
        match_line += (f" {count} more {'is' if count == 1 else 'are'} covered by a substitute "
                       f"({swaps}), which counts a little less than the real thing.")
    if record.to_buy:
        match_line += f" You'd need to buy {plural(len(record.to_buy), 'item')}."
    fresh_line = (f"**Uses food that expires soon: +{show(fresh)}.** "
                  + ("It uses something in your pantry that's close to its expiry date."
                     if fresh else "None of its ingredients expire soon."))
    liked_line = (f"**Like recipes you've picked before: +{show(liked)}.** "
                  + ("It's similar to recipes in your history." if liked
                     else "Nothing similar in your history yet."))
    total = round(match + fresh + liked, 1)
    lines = [match_line, fresh_line, liked_line,
             f"**Total: {show(total)} points.** Higher totals are ranked first."]
    if optional:
        lines.append(f"Optional, and fine to skip: {', '.join(optional)}.")
    return "\n".join(f"- {line}" for line in lines)


def recipe_card(rank, record):
    recipe = record.recipe
    match = pantry_match(record)
    with st.container(border=True):
        left, right = st.columns([0.8, 0.2])
        with left:
            key = f"choose_{recipe.id}"
            st.session_state[key] = recipe.id in st.session_state.chosen
            st.checkbox(f"**{rank}. {recipe.name}**", key=key, on_change=toggle_choice,
                        args=(recipe.id,))
            html(f"<span class='muted'>{recipe.cook_time_min} min | {recipe.cuisine} | "
                 f"{record.nutrition.kcal:.0f} kcal</span>")
        with right:
            html(f"<div class='score'>{match:.0%}</div><div class='score-label'>MATCH</div>")

        on_hand, swapped, to_buy = st.columns(3)
        with on_hand:
            html("<div class='label'>On hand</div>")
            st.markdown(", ".join(record.on_hand) or "None")
        with swapped:
            html("<div class='label'>Substitute</div>")
            st.markdown("<br>".join(f"{use} for {need}" for need, use in record.substitutions.items())
                        or "None", unsafe_allow_html=True)
        with to_buy:
            html("<div class='label'>To buy</div>")
            st.markdown(still_need(record) or "Nothing")

        with st.expander(f"Why it's ranked #{rank}"):
            st.markdown(score_explanation(record))


def hidden_box(ref, result):
    """Recipes the Dietary Check removed, with the rule each one breaks."""
    excluded = result.exclusions.excluded if result.exclusions else {}
    names = {recipe.id: recipe.name for recipe in ref.recipes}
    with st.container(border=True):
        html(f"<div class='label'>Hidden for your diet ({len(excluded)})</div>")
        if not excluded:
            html("<span class='muted'>None</span>")
        rows = [f"{names[rid]} <span class='muted'>({', '.join(reasons)})</span>"
                for rid, reasons in sorted(excluded.items(), key=lambda item: names[item[0]])]
        for row in rows[:PREVIEW]:
            html(row)
        if len(rows) > PREVIEW:
            with st.expander(f"{len(rows) - PREVIEW} more"):
                for row in rows[PREVIEW:]:
                    html(row)


def screen_results(ref):
    result = st.session_state.result
    st.button("< Back to pantry", on_click=go, args=(1,))
    page_title("Recipes you can make")
    matched = result.exclusions.matched_count if result.exclusions else 0
    hidden = len(result.exclusions.excluded) if result.exclusions else 0
    html(f"<span class='muted'>{len(result.ranked)} recipes use your pantry | "
         f"{hidden} hidden for your diet | ranked in {result.elapsed_s * 1000:.0f} ms</span>")
    st.write("")

    left, right = st.columns([0.68, 0.32], gap="large")
    with left:
        if result.status == "no_matches":
            st.info("None of our recipes use what's in your pantry. Try adding a few staples "
                    "like rice, pasta, eggs or onions.")
        elif result.status == "all_excluded":
            st.info(f"{matched} recipes use your pantry, but every one of them breaks your "
                    "diet or allergies. They're listed on the right.")
        # The top recipes start checked; only checked ones go on to steps 4 and 5.
        st.session_state.setdefault(
            "chosen", {record.recipe.id for record in result.ranked[:DEFAULT_TOP]})
        if result.ranked:
            pick_col, note_col = st.columns([0.2, 0.8], vertical_alignment="bottom")
            # Pick 10/20/50/All or type your own number, e.g. 35.
            options = show_top_options()
            top = pick_col.selectbox("Show top", options, key="show_top", accept_new_options=True)
            shown = result.ranked if top == "All" else result.ranked[:top]
            note_col.markdown(
                f"<span class='muted'>Showing {len(shown)} of {len(result.ranked)}. Only the "
                f"recipes you check go on to substitutes and your shopping list; the top "
                f"{DEFAULT_TOP} start checked.</span>", unsafe_allow_html=True)
            for rank, record in enumerate(shown, start=1):
                recipe_card(rank, record)
    with right:
        if result.ranked:
            count = len(st.session_state.chosen)
            with st.container(border=True):
                html("<div class='label'>Your choices</div>")
                html(f"{count} recipe{'s' if count != 1 else ''} checked." if count
                     else "<span class='muted'>Check at least one recipe to continue.</span>")
            st.button(f"Review substitutes for {count} recipe{'s' if count != 1 else ''}",
                      type="primary", disabled=not count, on_click=review_substitutes)
        hidden_box(ref, result)
        if result.unrecognized:
            with st.container(border=True):
                html("<div class='label'>Skipped pantry items</div>")
                show_unrecognized(result.unrecognized)


# ---------------------------------------------------------------- step 4

def review_substitutes():
    """Remember the chosen recipes' order, so step 4 can show how each choice moves them."""
    st.session_state.ranking_before = [r.recipe.id for r in chosen_records(st.session_state.result)]
    st.session_state.setdefault("rejected", {})
    go(4)


def decide(recipe_id, substitute, needed):
    """Send one Accept/Reject choice to the architecture and keep its new result."""
    accepted = st.session_state[f"sub_{recipe_id}_{substitute}"] == "Accept"
    try:
        st.session_state.result = st.session_state.backend.decide_substitute(
            recipe_id, substitute, accepted)
    except ValueError as error:
        st.session_state.problem = f"That choice couldn't be applied: {error}"
        return
    if accepted:
        st.session_state.rejected.pop((recipe_id, substitute), None)
    else:
        st.session_state.rejected[(recipe_id, substitute)] = needed


def substitute_choices(result):
    """(recipe, needed ingredient, substitute) for the swaps in the recipes chosen on step 3,
    plus every swap the user rejected in them, so it can be accepted again."""
    chosen = chosen_records(result)
    names = {record.recipe.id: record.recipe for record in chosen}
    choices = [(record.recipe, needed, use)
               for record in chosen for needed, use in record.substitutions.items()]
    for (recipe_id, use), needed in st.session_state.rejected.items():
        if recipe_id in names:
            choices.append((names[recipe_id], needed, use))
    return choices


def movement(rank, recipe_id):
    before = st.session_state.ranking_before
    if recipe_id not in before:
        return "<span class='muted'>new</span>"
    old = before.index(recipe_id) + 1
    if rank < old:
        return f"<span class='up'>up from #{old}</span>"
    if rank > old:
        return f"<span class='down'>down from #{old}</span>"
    return "<span class='muted'>no change</span>"


def screen_substitutes(ref):
    result = st.session_state.result
    st.button("< Back to results", on_click=go, args=(3,))
    page_title("Review substitutes")
    count = len(chosen_records(result))
    html(f"<span class='muted'>Swaps for the {count} recipe{'s' if count != 1 else ''} you chose. "
         "We only suggest swaps you have enough of that also fit "
         "your diet. Reject one and we'll look for another swap or add the ingredient "
         "to your shopping list.</span>")
    st.write("")
    if st.session_state.get("problem"):
        st.error(st.session_state.pop("problem"))

    left, right = st.columns([0.55, 0.45], gap="large")
    with left:
        choices = substitute_choices(result)
        if not choices:
            st.info("None of the recipes you chose need a substitute.")
        # Same order as the ranking when this screen opened (#1 first). It stays put while
        # you decide; only the "Updated rankings" box on the right moves.
        start = st.session_state.ranking_before
        order = lambda c: (start.index(c[0].id) if c[0].id in start else len(start), c[1])
        for recipe, needed, use in sorted(choices, key=order):
            key = f"sub_{recipe.id}_{use}"
            st.session_state.setdefault(
                key, "Reject" if (recipe.id, use) in st.session_state.rejected else "Accept")
            with st.container(border=True):
                html(f"<div class='label'>{recipe.name}</div>")
                st.markdown(f"Needs {needed}. Use **{use}** instead?")
                st.radio("Your choice", ["Accept", "Reject"], key=key, horizontal=True,
                         label_visibility="collapsed", on_change=decide,
                         args=(recipe.id, use, needed))
    with right:
        with st.container(border=True):
            html("<div class='label'>Updated rankings of your recipes</div>")
            for rank, record in enumerate(chosen_records(result), start=1):
                html(f"{rank}. {record.recipe.name} <span class='muted'>| "
                     f"{record.score:.2f} |</span> {movement(rank, record.recipe.id)}")
        st.button("Choose recipes", type="primary", on_click=go, args=(5,))


# ---------------------------------------------------------------- step 5

def save_picks(recipe_ids, counts):
    """Save the picked recipes to history and get one shopping list for all of them.

    Each click gets its own event ID. If saving fails and the user retries the same
    picks, the same ID is reused, so the architecture never saves history twice.
    If the picks are already saved and only the counts changed, the saved click's ID
    is reused too: the list is rebuilt and nothing new goes into history.
    """
    saved = st.session_state.get("saved_picks")
    pending = st.session_state.get("pending_pick")
    if saved and saved["ids"] == recipe_ids:
        event_id = saved["event_id"]
    elif pending and pending[1] == recipe_ids:
        event_id = pending[0]
    else:
        event_id = str(uuid4())
    st.session_state.pending_pick = (event_id, recipe_ids)
    try:
        shopping = st.session_state.backend.select(recipe_ids, event_id=event_id,
                                                   counts=dict(counts))
    except (ValueError, ProfileError, OSError) as error:
        st.session_state.problem = f"Your picks couldn't be saved: {error}"
        return
    st.session_state.pop("pending_pick")
    st.session_state.saved_picks = {"ids": recipe_ids, "counts": counts,
                                    "list": shopping, "event_id": event_id}


def shopping_text(shopping):
    return "\n".join(f"{name}, {amount(qty, unit)}" for name, qty, unit in shopping)


def screen_select(ref):
    result = st.session_state.result
    st.button("< Back to substitutes", on_click=go, args=(4,))
    page_title("Pick what you're cooking")
    html("<span class='muted'>Your chosen recipes, in their new order. Uncheck any you've "
         "changed your mind about. We'll save your picks to your history, so future rankings "
         "lean toward recipes like these, and make one shopping list for all of them.</span>")
    st.write("")
    if st.session_state.get("problem"):
        st.error(st.session_state.pop("problem"))

    left, right = st.columns([0.5, 0.5], gap="large")
    with left:
        with st.container(border=True):
            html("<div class='label'>Your recipes</div>")
            picked, times_of = [], {}
            for rank, record in enumerate(chosen_records(result), start=1):
                rid = record.recipe.id
                key = f"pick_{rid}"
                st.session_state.setdefault(key, True)          # chosen on step 3, so start checked
                pick_col, times_col = st.columns([0.78, 0.22], vertical_alignment="center")
                checked = pick_col.checkbox(
                    f"**{rank}. {record.recipe.name}** | {pantry_match(record):.0%} match "
                    f"| {record.recipe.cook_time_min} min", key=key)
                # How many times you'll make it this week; the shopping list scales to match.
                times = times_col.number_input("Times", min_value=1, max_value=50, value=1, step=1,
                                               key=f"times_{rid}", disabled=not checked)
                if checked:
                    picked.append(rid)
                    times_of[rid] = int(times)
                need = still_need(record)
                html(f"<div class='pick-need'>Still need: {need}</div>" if need
                     else "<div class='pick-need'>Ready to cook. Nothing to buy.</div>")
        picked = tuple(sorted(picked))
        counts = tuple(sorted(times_of.items()))
        saved = st.session_state.get("saved_picks")
        same_picks = saved is not None and saved["ids"] == picked
        already_saved = same_picks and saved["counts"] == counts
        st.button("Update shopping list" if same_picks else "Save picks and make shopping list",
                  type="primary", disabled=not picked or already_saved,
                  on_click=save_picks, args=(picked, counts))

    with right:
        with st.container(border=True):
            html("<div class='label'>Your shopping list</div>")
            if same_picks and not already_saved:
                html("<span class='muted'>You changed how many times you'll make a recipe. "
                     "Press Update shopping list to see the new amounts.</span>")
            elif not already_saved:
                html("<span class='muted'>Pick your recipes and save them to see one combined "
                     "list. We count your pantry once across every recipe.</span>")
            elif not saved["list"]:
                html("<span class='muted'>Nothing to buy. You have everything.</span>")
            else:
                for name, qty, unit in saved["list"]:
                    html(f"{name}, {amount(qty, unit)}")
        if already_saved:
            if saved["list"]:
                st.download_button("Download list", shopping_text(saved["list"]),
                                   file_name="shopping-list.txt")
            st.success("Saved to your history. Future rankings will lean toward recipes like these.")
            st.button("Start over", on_click=reset)


# ---------------------------------------------------------------- main

def main():
    st.set_page_config(page_title="Smart-Shelf", layout="wide")
    html(CSS)
    st.session_state.setdefault("step", 1)
    sidebar()
    try:
        ref = reference_data()
    except DataError as error:
        st.error(f"The recipe data couldn't be loaded, so Smart-Shelf can't run: {error}")
        return
    if st.session_state.step == 5 and "result" in st.session_state:
        screen_select(ref)
    elif st.session_state.step == 4 and "result" in st.session_state:
        screen_substitutes(ref)
    elif st.session_state.step >= 3 and "result" in st.session_state:
        screen_results(ref)
    else:
        screen_pantry(ref)


main()
