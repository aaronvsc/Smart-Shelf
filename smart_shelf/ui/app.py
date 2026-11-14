"""Smart-Shelf user interface (Streamlit).

One set of screens for both architectures. The sidebar switch picks which
architecture does the work behind the screens; what the user sees stays the
same. The five steps follow section 1.4.1 of our proposal.

Run from the Smart-Shelf folder:   streamlit run smart_shelf/ui/app.py
"""
import base64
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parents[1]))    # so `import smart_shelf` works when Streamlit runs this file

from smart_shelf.common.data_access import (  # noqa: E402
    PROFILES_DIR, DataError, ProfileError, load_profile, load_reference_data, save_profile,
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
.steps div {padding: 6px 0 6px 12px; border-left: 2px solid #30363D; color: #6E7681;}
.steps div.done {color: #8B949E;}
.steps div.current {border-left-color: #3B82F6; color: #F0F6FC; font-weight: 600;}
</style>
"""


# ---------------------------------------------------------------- data and state

@st.cache_resource
def reference_data():
    """The read-only data stores, loaded once and shared by every session."""
    return load_reference_data()


def profile_ids():
    return sorted(path.stem for path in PROFILES_DIR.glob("*.json"))


def split_rules(ref):
    """Allergy rules block one tag with the same name (peanut, egg); the rest are diets."""
    allergies = sorted(name for name, tags in ref.restrictions.items() if tags == {name})
    diets = sorted(set(ref.restrictions) - set(allergies))
    return diets, allergies


def reset():
    """Start over: a new architecture or user means a fresh backend and no old results."""
    for key in ("backend", "result", "problem"):
        st.session_state.pop(key, None)
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
        profile = load_profile(st.session_state.user_id)
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
        save_profile(profile)

    st.session_state.step = 2
    backend = BACKENDS[st.session_state.architecture](ref)
    with st.spinner(f"Checking your pantry against {len(ref.recipes)} recipes"):
        result = backend.run(rows, profile)
    st.session_state.backend, st.session_state.result = backend, result
    st.session_state.unrecognized = result.unrecognized

    if result.status == "empty_pantry":
        st.session_state.problem = "None of your pantry items could be used. Fix the rows below and try again."
        st.session_state.step = 1
    else:
        st.session_state.pop("problem", None)
        st.session_state.step = 3
    st.rerun()


# ---------------------------------------------------------------- step 3 (placeholder)

def screen_results(ref):
    page_title("Recipes you can make")
    result = st.session_state.result
    html(f"<span class='muted'>{len(result.ranked)} recipes ranked "
         f"in {result.elapsed_s * 1000:.0f} ms</span>")
    st.button("Back to pantry", on_click=go, args=(1,))


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
    if st.session_state.step >= 3 and "result" in st.session_state:
        screen_results(ref)
    else:
        screen_pantry(ref)


main()
