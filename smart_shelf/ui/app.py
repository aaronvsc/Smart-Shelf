"""Smart-Shelf user interface (Streamlit).

One set of screens for both architectures. The sidebar switch picks which
architecture does the work behind the screens; what the user sees stays the
same. The five steps follow section 1.4.1 of our proposal.

Run from the Smart-Shelf folder:   streamlit run smart_shelf/ui/app.py
"""
import base64
from pathlib import Path

import streamlit as st

HERE = Path(__file__).parent
STEPS = ["Enter pantry", "Finding recipes", "Results", "Review substitutes", "Shopping list"]
ARCHITECTURES = ["A: Pipe-and-Filter", "B: Blackboard"]
LOGO = base64.b64encode((HERE / "logo.svg").read_bytes()).decode()

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


def html(text):
    st.markdown(text, unsafe_allow_html=True)


def sidebar():
    with st.sidebar:
        html(f"<div class='brand'><img src='data:image/svg+xml;base64,{LOGO}'>"
             "<span>Smart-Shelf</span></div>")
        st.radio("Architecture", ARCHITECTURES, key="architecture")
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


def main():
    st.set_page_config(page_title="Smart-Shelf", layout="wide")
    html(CSS)
    st.session_state.setdefault("step", 1)
    sidebar()
    page_title("Enter your pantry")


main()
