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

import pandas as pd
import streamlit as st

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parents[1]))    # so `import smart_shelf` works when Streamlit runs this file

from smart_shelf.common.data_access import (  # noqa: E402
    DATA_DIR, PROFILES_DIR, DataError, ProfileError, load_profile, load_reference_data, save_profile,
)
from smart_shelf.common.models import UserProfile  # noqa: E402
from smart_shelf.ui.backends import BACKENDS  # noqa: E402

STEPS = ["Enter pantry", "Finding recipes", "Results", "Review substitutes", "Shopping list"]
LOGO = base64.b64encode((HERE / "logo.svg").read_bytes()).decode()
UNITS = ["g", "kg", "oz", "lb", "ml", "l", "fl oz", "tsp", "tbsp", "cup",
         "count", "clove", "slice", "stick", "can"]
# A starting pantry so the app can be tried right away; the user can edit or clear it.
SAMPLE_PANTRY = [
    ("rice", 400, "g", None), ("eggs", 6, "count", None), ("olive oil", 200, "ml", None),
    ("onion", 2, "count", None), ("garlic", 4, "clove", None), ("spaghetti", 500, "g", None),
    ("tomatoes", 4, "count", "2026-11-16"), ("milk", 2, "cup", "2026-11-18"),
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
    for key in ("backend", "result", "problem", "shown", "rejected", "ranking_before"):
        st.session_state.pop(key, None)
    for key in [key for key in st.session_state if str(key).startswith("sub_")]:
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
            columns=["Ingredient", "Quantity", "Unit", "Expires"]))
        table = st.data_editor(
            st.session_state.pantry_start, num_rows="dynamic", hide_index=True, width="stretch",
            column_config={
                "Ingredient": st.column_config.TextColumn(width="medium"),
                "Quantity": st.column_config.NumberColumn(min_value=0, width="small"),
                "Unit": st.column_config.SelectboxColumn(options=UNITS, width="small"),
                "Expires": st.column_config.DateColumn(format="MMM D, YYYY", width="small"),
            },
            key="pantry_editor",
        )
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

        if st.session_state.get("problem"):
            with st.container(border=True):
                html("<div class='label'>Pantry check</div>")
                st.error(st.session_state.problem)
                show_unrecognized(st.session_state.get("unrecognized", []))

        if st.button("Find recipes", type="primary"):
            find_recipes(ref, profile, chosen_diets, chosen_allergies, pantry_rows(table))


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
    st.session_state.shown = PAGE_SIZE
    st.session_state.unrecognized = result.unrecognized

    if result.status == "empty_pantry":
        st.session_state.problem = "None of your pantry items could be used. Fix the rows below and try again."
        st.session_state.step = 1
    else:
        st.session_state.pop("problem", None)
        st.session_state.step = 3
    st.rerun()


# ---------------------------------------------------------------- step 3

PAGE_SIZE = 10


def amount(qty, unit):
    """50.0 g -> '50 g', 0.333 cup -> '0.33 cup'."""
    return f"{round(qty, 2):g} {unit}"


def show_more():
    st.session_state.shown += PAGE_SIZE


def recipe_card(rank, record):
    recipe = record.recipe
    # Score = how well the pantry covers the recipe + freshness boost + history boost.
    match = record.score - record.freshness_boost - record.preference_boost
    with st.container(border=True):
        left, right = st.columns([0.8, 0.2])
        with left:
            st.markdown(f"**{rank}. {recipe.name}**")
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
            st.markdown(", ".join(f"{gap.name} ({amount(gap.short_qty, gap.unit)})"
                                  for gap in record.to_buy) or "Nothing")

        with st.expander("Score breakdown"):
            required = sum(item.required for item in recipe.ingredients)
            optional = [gap.name for gap in record.missing if not gap.required]
            lines = [
                f"Pantry match: {match:.3f} ({len(record.on_hand)} on hand, "
                f"{len(record.substitutions)} substituted, {len(record.to_buy)} to buy, "
                f"out of {required} required ingredients; a substitute counts a little less)",
                f"Freshness: +{record.freshness_boost:.3f} (uses food that expires soon)",
                f"Your history: +{record.preference_boost:.3f} (like recipes you picked before)",
                f"Total score: {record.score:.3f}",
            ]
            if optional:
                lines.append("Optional, left out: " + ", ".join(optional))
            st.markdown("\n".join(f"- {line}" for line in lines))


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
        for row in rows[:PAGE_SIZE]:
            html(row)
        if len(rows) > PAGE_SIZE:
            with st.expander(f"{len(rows) - PAGE_SIZE} more"):
                for row in rows[PAGE_SIZE:]:
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
        st.session_state.setdefault("shown", PAGE_SIZE)
        for rank, record in enumerate(result.ranked[:st.session_state.shown], start=1):
            recipe_card(rank, record)
        if len(result.ranked) > st.session_state.shown:
            st.button(f"Show {PAGE_SIZE} more", on_click=show_more)
    with right:
        hidden_box(ref, result)
        if result.unrecognized:
            with st.container(border=True):
                html("<div class='label'>Skipped pantry items</div>")
                show_unrecognized(result.unrecognized)
        if result.ranked:
            st.button("Review substitutes", type="primary", on_click=review_substitutes)


# ---------------------------------------------------------------- step 4

def review_substitutes():
    """Remember the ranking as it was, so step 4 can show how each choice moves recipes."""
    st.session_state.setdefault("ranking_before", [r.recipe.id for r in st.session_state.result.ranked])
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
    """(recipe, needed ingredient, substitute) for the swaps in the recipes shown on step 3,
    plus every swap the user rejected, so it can be accepted again."""
    names = {record.recipe.id: record.recipe for record in result.ranked}
    choices = [(record.recipe, needed, use)
               for record in result.ranked[:st.session_state.get("shown", PAGE_SIZE)]
               for needed, use in record.substitutions.items()]
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
    html("<span class='muted'>We only suggest swaps you have enough of that also fit "
         "your diet. Reject one and we'll look for another swap or add the ingredient "
         "to your shopping list.</span>")
    st.write("")
    if st.session_state.get("problem"):
        st.error(st.session_state.pop("problem"))

    left, right = st.columns([0.55, 0.45], gap="large")
    with left:
        choices = substitute_choices(result)
        if not choices:
            st.info("None of the recipes you're looking at need a substitute.")
        for recipe, needed, use in sorted(choices, key=lambda c: (c[0].name, c[1])):
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
            html("<div class='label'>Updated rankings</div>")
            for rank, record in enumerate(result.ranked[:st.session_state.get("shown", PAGE_SIZE)],
                                          start=1):
                html(f"{rank}. {record.recipe.name} <span class='muted'>| "
                     f"{record.score:.2f} |</span> {movement(rank, record.recipe.id)}")


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
    if st.session_state.step == 4 and "result" in st.session_state:
        screen_substitutes(ref)
    elif st.session_state.step >= 3 and "result" in st.session_state:
        screen_results(ref)
    else:
        screen_pantry(ref)


main()
