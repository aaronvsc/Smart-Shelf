"""Tests for smart_shelf/ui/pantry_check.py, the live row check on Step 1.

Each test feeds in rows like the pantry table produces and checks the plain
message the user would see (or that a good row gives no message).
"""
import pytest

from smart_shelf.common.data_access import load_reference_data
from smart_shelf.ui.pantry_check import check_pantry


@pytest.fixture(scope="module")
def ref():
    return load_reference_data()


def row(name, qty=1, unit="count"):
    return {"name": name, "qty": qty, "unit": unit, "expires": None}


@pytest.mark.parametrize("good", [
    row("carrots", 3), row("Eggs", 6), row("spaghetti", 500, "g"), row("tomatoes", 4),
    row("garlic", 2, "clove"), row("milk", 1, "cup"),
])
def test_good_rows_have_no_problems(ref, good):
    assert check_pantry([good], ref) == []


@pytest.mark.parametrize("bad, message", [
    (row("carrots", None), "carrots: add a quantity above 0."),
    (row("carrots", 0), "carrots: add a quantity above 0."),
    (row("", 1), "Row 1: add an ingredient name."),
    (row("rice", 100, ""), "rice: pick a unit."),
    (row("flour", 1, "can"), "flour: can doesn't work for flour. Try g, kg, oz, lb, cup or tbsp."),
    (row("unobtainium", 1, "g"), "unobtainium: not in our ingredient list."),
])
def test_bad_rows_explain_the_fix(ref, bad, message):
    assert check_pantry([bad], ref) == [message]


def test_unknown_name_suggests_close_matches(ref):
    (message,) = check_pantry([row("cheese", 1, "cup")], ref)
    assert message.startswith("cheese: not in our ingredient list. Did you mean ")
    assert "cheddar cheese" in message


def test_only_bad_rows_are_reported(ref):
    assert check_pantry([row("eggs", 6), row("carrots", None)], ref) == ["carrots: add a quantity above 0."]
