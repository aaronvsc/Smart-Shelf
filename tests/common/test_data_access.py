"""Tests for loading the data stores in smart_shelf/common/data_access.py.

These check that the real data files load correctly and that bad data (missing
files, broken JSON, duplicate names, unknown tags) raises a clear DataError
instead of slipping through to the architectures.
"""
import json

import pytest

from smart_shelf.common.data_access import DataError, load_ingredients


def write(tmp_path, data, name="ingredients.json"):
    path = tmp_path / name
    path.write_text(json.dumps(data) if not isinstance(data, str) else data)
    return path


def small_dictionary(*ingredients):
    return {"restrictions": {"vegan": ["dairy", "egg"], "gluten_free": ["gluten"]},
            "ingredients": list(ingredients)}


# ----------------------------------------------------------- real data file

def test_real_ingredient_dictionary_loads():
    ingredients, restrictions = load_ingredients()
    assert "flour" in ingredients and "egg" in ingredients
    assert "vegan" in restrictions and "peanut" in restrictions


def test_real_dictionary_catches_key_allergens():
    ingredients, restrictions = load_ingredients()
    assert "peanut" in ingredients["peanut butter"].tags
    assert "dairy" in ingredients["butter"].tags
    assert {"soy", "gluten"} <= ingredients["soy sauce"].tags


# ----------------------------------------------------------- loader behavior

def test_standard_conversions_are_added(tmp_path):
    path = write(tmp_path, small_dictionary(
        {"name": "milk", "base_unit": "ml", "tags": ["dairy"]},
        {"name": "flour", "base_unit": "g", "unit_conversions": {"cup": 125}, "tags": ["gluten"]}))
    ingredients, _ = load_ingredients(path)
    assert ingredients["milk"].unit_conversions["cup"] == 240
    assert ingredients["flour"].unit_conversions["cup"] == 125
    assert ingredients["flour"].unit_conversions["kg"] == 1000


def test_names_and_aliases_are_lowercased(tmp_path):
    path = write(tmp_path, small_dictionary(
        {"name": " Egg ", "base_unit": "count", "aliases": ["Large Egg"], "tags": ["egg"]}))
    ingredients, _ = load_ingredients(path)
    assert ingredients["egg"].aliases == ("large egg",)


def test_about_key_is_ignored(tmp_path):
    data = small_dictionary({"name": "salt", "base_unit": "g"})
    data["_about"] = "description"
    ingredients, _ = load_ingredients(write(tmp_path, data))
    assert list(ingredients) == ["salt"]


# ----------------------------------------------------------- bad data

def test_missing_file_raises(tmp_path):
    with pytest.raises(DataError, match="not found"):
        load_ingredients(tmp_path / "nope.json")


def test_broken_json_raises(tmp_path):
    with pytest.raises(DataError, match="not valid JSON"):
        load_ingredients(write(tmp_path, '{"restrictions": {'))


def test_duplicate_ingredient_raises(tmp_path):
    path = write(tmp_path, small_dictionary({"name": "salt", "base_unit": "g"},
                                            {"name": "Salt", "base_unit": "g"}))
    with pytest.raises(DataError, match="more than once"):
        load_ingredients(path)


def test_bad_base_unit_raises(tmp_path):
    path = write(tmp_path, small_dictionary({"name": "salt", "base_unit": "pinch"}))
    with pytest.raises(DataError, match="base_unit"):
        load_ingredients(path)


def test_unknown_tag_raises(tmp_path):
    path = write(tmp_path, small_dictionary({"name": "milk", "base_unit": "ml", "tags": ["diary"]}))
    with pytest.raises(DataError, match="diary"):
        load_ingredients(path)


def test_alias_used_by_two_ingredients_raises(tmp_path):
    path = write(tmp_path, small_dictionary(
        {"name": "chicken breast", "base_unit": "g", "aliases": ["chicken"]},
        {"name": "chicken thigh", "base_unit": "g", "aliases": ["chicken"]}))
    with pytest.raises(DataError, match="'chicken' is used by both"):
        load_ingredients(path)


def test_bad_conversion_raises(tmp_path):
    path = write(tmp_path, small_dictionary(
        {"name": "flour", "base_unit": "g", "unit_conversions": {"cup": 0}}))
    with pytest.raises(DataError, match="positive"):
        load_ingredients(path)
