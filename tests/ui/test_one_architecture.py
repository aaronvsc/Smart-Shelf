"""Tests that the UI works when only one architecture's code is present.

That's how the Selected/ and Unselected/ folders ship: each has one architecture,
so the app must offer just that one and show no A/B switch. Each test copies the
project without one architecture and runs the app from the copy in a separate
Python process, so the full repo's code can't leak in.
"""
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
CHECK = """
from streamlit.testing.v1 import AppTest
from smart_shelf.ui.backends import BACKENDS
app = AppTest.from_file("smart_shelf/ui/app.py", default_timeout=30)
app.run()
assert not app.exception, app.exception
assert len(app.sidebar.radio) == 0, "no A/B switch expected"
next(b for b in app.button if b.label == "Find recipes").click().run()
assert not app.exception, app.exception
assert app.session_state["result"].status == "ok"
print(list(BACKENDS))
"""


@pytest.mark.parametrize("keep, drop", [("arch_a", "arch_b"), ("arch_b", "arch_a")])
def test_app_runs_with_only_one_architecture(tmp_path, keep, drop):
    shutil.copytree(ROOT / "smart_shelf", tmp_path / "smart_shelf",
                    ignore=shutil.ignore_patterns("__pycache__", drop))
    shutil.copytree(ROOT / "data", tmp_path / "data",
                    ignore=shutil.ignore_patterns("user_profiles"))
    done = subprocess.run([sys.executable, "-c", CHECK], cwd=tmp_path, capture_output=True,
                          text=True, timeout=120,
                          env={"PATH": "", "SMART_SHELF_PROFILES": str(tmp_path / "profiles")})
    assert done.returncode == 0, done.stderr
    expected = "A: Pipe-and-Filter" if keep == "arch_a" else "B: Blackboard"
    assert done.stdout.strip() == str([expected])
