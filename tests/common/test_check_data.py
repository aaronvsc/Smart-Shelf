"""Tests for the check script in scripts/check_data.py.

They confirm the real data passes, and that the script catches cross-file
problems (missing nutrition, substitutable items with no swaps) and stops
cleanly on broken data instead of crashing.
"""
import json
import shutil

import pytest

from scripts.check_data import main, run_checks
from smart_shelf.common.data_access import DATA_DIR


@pytest.fixture
def data_copy(tmp_path):
    """A copy of the real data folder that a test can safely edit."""
    for name in ("ingredients.json", "substitutions_nutrition.json", "recipes.json"):
        shutil.copy(DATA_DIR / name, tmp_path / name)
    shutil.copytree(DATA_DIR / "profiles", tmp_path / "profiles")
    return tmp_path


def edit(path, change):
    data = json.loads(path.read_text())
    change(data)
    path.write_text(json.dumps(data))


def test_real_data_passes():
    errors, _, summary = run_checks()
    assert errors == []
    assert "recipes" in summary[0]


def test_main_returns_exit_codes(data_copy, capsys):
    assert main(data_copy) == 0
    assert "PASS" in capsys.readouterr().out
    (data_copy / "recipes.json").write_text("{ broken")
    assert main(data_copy) == 1
    assert "FAIL" in capsys.readouterr().out


def test_missing_nutrition_is_an_error(data_copy):
    edit(data_copy / "substitutions_nutrition.json",
         lambda d: d["ingredients"]["flour"].pop("nutrition"))
    errors, _, _ = run_checks(data_copy)
    assert any("'flour' has no nutrition" in e for e in errors)


def test_substitutable_without_swaps_is_an_error(data_copy):
    def mark_egg_substitutable(d):
        d["recipes"][0]["ingredients"][2]["substitutable"] = True   # R001's egg
    edit(data_copy / "recipes.json", mark_egg_substitutable)
    errors, _, _ = run_checks(data_copy)
    assert any("'egg' is marked substitutable" in e for e in errors)


def test_duplicate_recipe_name_is_a_warning(data_copy):
    edit(data_copy / "recipes.json", lambda d: d["recipes"][1].update(name=d["recipes"][0]["name"]))
    errors, warnings, _ = run_checks(data_copy)
    assert errors == []
    assert any("used 2 times" in w for w in warnings)


def test_broken_data_is_reported_not_raised(data_copy):
    edit(data_copy / "recipes.json",
         lambda d: d["recipes"][0]["ingredients"].append({"name": "unicorn", "qty": 1, "unit": "g"}))
    errors, _, _ = run_checks(data_copy)
    assert len(errors) == 1 and "unicorn" in errors[0]


def test_profile_with_unknown_rule_or_recipe_is_an_error(data_copy):
    def break_profile(d):
        d["allergies"].append("glitter")
        d["history"].append({"recipe_id": "R999", "selected_at": "2026-10-25"})
    edit(data_copy / "profiles" / "demo.json", break_profile)
    errors, _, _ = run_checks(data_copy)
    assert any("'glitter'" in e for e in errors)
    assert any("'R999'" in e for e in errors)
