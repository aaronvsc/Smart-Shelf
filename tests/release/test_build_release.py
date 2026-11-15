"""Tests for scripts/build_release.py, which makes the Selected/ and Unselected/ folders.

Each test builds into a temp folder (never the real repo), then checks that each
folder holds exactly one architecture, its compiled code and launchers, and that
its own test suite passes when run from inside it, the way the TA would run it.
"""
import os
import subprocess
import sys

import pytest

from scripts.build_release import RELEASES, build


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    target = tmp_path_factory.mktemp("release")
    build(target)
    return target


@pytest.mark.parametrize("folder", list(RELEASES))
def test_each_folder_has_one_architecture_and_everything_to_run_it(built, folder):
    keep, drop, _ = RELEASES[folder]
    out = built / folder
    assert (out / "smart_shelf" / keep).is_dir()
    assert not (out / "smart_shelf" / drop).exists()
    assert not (out / "tests" / drop).exists()
    for name in ("requirements.txt", "HOW_TO_RUN.txt", "run_windows.bat", "data/recipes.json",
                 ".streamlit/config.toml", "smart_shelf/ui/app.py", "smart_shelf/ui/logo.svg"):
        assert (out / name).is_file(), name
    for name in ("run_mac.command", "run_linux.sh"):
        assert os.access(out / name, os.X_OK), f"{name} should be executable"
    assert not list(out.rglob("__pycache__")) and not (out / "data" / "user_profiles").exists()


@pytest.mark.parametrize("folder", list(RELEASES))
def test_every_source_file_is_compiled(built, folder):
    out = built / folder
    sources = {p.relative_to(out).with_suffix("") for p in (out / "smart_shelf").rglob("*.py")}
    compiled = {p.relative_to(out / "compiled").with_suffix("")
                for p in (out / "compiled").rglob("*.pyc")}
    assert sources and sources == compiled


@pytest.mark.parametrize("folder", list(RELEASES))
def test_folder_passes_its_own_tests(built, folder, tmp_path):
    done = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"],
                          cwd=built / folder, capture_output=True, text=True, timeout=300,
                          env={**os.environ, "SMART_SHELF_PROFILES": str(tmp_path / "profiles")})
    assert done.returncode == 0, done.stdout[-3000:]
    assert " passed" in done.stdout and " failed" not in done.stdout
