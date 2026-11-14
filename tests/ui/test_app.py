"""Smoke tests for the Streamlit UI in smart_shelf/ui/app.py.

Streamlit's AppTest runs the app without a browser, so we can check that each
screen loads without errors and shows what it should.
"""
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).parents[2] / "smart_shelf" / "ui" / "app.py")


def start():
    app = AppTest.from_file(APP)
    app.run()
    assert not app.exception
    return app


def test_app_starts_on_step_one():
    app = start()
    assert "## Enter your pantry" in [m.value for m in app.main.markdown]


def test_sidebar_offers_both_architectures():
    app = start()
    switch = app.sidebar.radio(key="architecture")
    assert switch.options == ["A: Pipe-and-Filter", "B: Blackboard"]
    switch.set_value("B: Blackboard").run()
    assert not app.exception
