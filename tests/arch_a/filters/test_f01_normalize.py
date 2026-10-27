import pytest

from smart_shelf.arch_a.filters import NormalizeFilter


@pytest.fixture
def norm(ref):
    return lambda rows: NormalizeFilter.normalize(rows, ref)


@pytest.mark.parametrize("raw, unit, expected", [
    ("  Spaghetti ", "g", "pasta"),           # case, spaces, alias
    ("tomatoes", "count", "tomato"),          # plural -es
    ("Eggs", "count", "egg"),                 # plural -s
    ("garlic cloves", "count", "garlic"),     # plural of an alias
    ("tomatoe", "count", "tomato"),           # typo
    ("onoin", "count", "onion"),              # typo
])
def test_name_variations_resolve_to_one_ingredient(norm, raw, unit, expected):
    pantry, bad = norm([{"name": raw, "qty": 1, "unit": unit}])
    assert list(pantry) == [expected] and bad == []


@pytest.mark.parametrize("name, qty, unit, expected", [
    ("tomato", 2, "count", 240),
    ("olive oil", 2, "tablespoons", 30),
    ("rice", 1, "kg", 1000),
    ("milk", 0.5, "L", 500),
    ("flour", 250, "grams", 250),
])
def test_units_convert_to_the_base_unit(norm, name, qty, unit, expected):
    pantry, _ = norm([{"name": name, "qty": qty, "unit": unit}])
    assert pantry[name].qty == pytest.approx(expected)


def test_duplicate_rows_merge_and_keep_earliest_expiry(norm):
    pantry, _ = norm([{"name": "egg", "qty": 2, "unit": "count", "expires": "2026-11-05"},
                      {"name": "eggs", "qty": 3, "unit": "count", "expires": "2026-10-30"}])
    assert pantry["egg"].qty == 5
    assert pantry["egg"].expires.isoformat() == "2026-10-30"


@pytest.mark.parametrize("row", [
    {"name": "unobtainium", "qty": 1, "unit": "g"},
    {"name": "egg", "qty": 1, "unit": "parsec"},
    {"name": "egg", "qty": "lots", "unit": "count"},
    {"name": "egg", "qty": -1, "unit": "count"},
    {"name": "egg", "qty": float("nan"), "unit": "count"},
    {"name": "", "qty": 1, "unit": "count"},
    {"name": 5, "qty": 1, "unit": "count"},
    {"qty": 1, "unit": "g"},
    {"name": "egg", "qty": 1, "unit": "count", "expires": "soon"},
    "not a dict",
])
def test_bad_rows_are_reported_not_raised(norm, row):
    pantry, bad = norm([row])
    assert pantry == {} and len(bad) == 1 and bad[0].row == row


def test_a_bad_row_does_not_stop_the_others(norm):
    pantry, bad = norm([{"name": "unobtainium", "qty": 1, "unit": "g"},
                        {"name": "rice", "qty": 100, "unit": "g"}])
    assert list(pantry) == ["rice"] and len(bad) == 1
