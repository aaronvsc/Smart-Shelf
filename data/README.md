# Smart-Shelf Data

This folder holds the four data stores both architectures share (Section 2 of our
proposal). Always load them through `smart_shelf/common/data_access.py` instead of
opening the JSON files directly, so A and B get the same data in the same shape.

## Files

| File | Data store | What's in it |
|---|---|---|
| `ingredients.json` | Ingredient Dictionary | Every ingredient's name, other spellings, base unit (`g`, `ml`, or `count`), food-specific unit conversions, and allergen/diet tags. Also the restriction rules: each diet or allergy and the tags it forbids. |
| `substitutions_nutrition.json` | Substitution & Nutrition Data | Each ingredient's nutrition (per 100 g/ml, or per item for `count` ingredients) and what can stand in for it. A substitute's `ratio` is how many of its base units replace 1 base unit of the original. |
| `recipes.json` | Recipe Database | Every recipe's id, name, cuisine, cook time, and ingredients. Ingredients are required unless marked `"required": false`, and only ones marked `"substitutable": true` can be swapped. |
| `profiles/<user_id>.json` | User Profile & History | One private file per user: diet restrictions, allergies, and past recipe picks. `demo.json` is a sample. |

## Using the data in code

```python
from smart_shelf.common.data_access import load_reference_data, load_profile, save_selection

ref = load_reference_data()          # ingredients, recipes, substitutes, nutrition, restriction rules
profile = load_profile("demo")       # raises ProfileError if missing or broken; stop, don't run without it
save_selection("demo", ["R003"])     # Step 5: add the picked recipes to the user's history
```

`ref` also has the shared helpers: `ref.to_base(name, qty, unit)`, `ref.violations(name, profile)`,
`ref.check_restrictions(profile)`, and `ref.nutrition_of(name, base_qty)`.

**Architecture A:** `smart_shelf/arch_a/inputs.py` can be replaced with imports from
`smart_shelf.common.models`. The class names and fields are identical.

## Adding or editing data

1. Edit the JSON file. Every ingredient a recipe uses must already be in `ingredients.json`,
   with a unit that converts for it (its base unit, a standard unit, or one listed in its
   `unit_conversions`).
2. Run the check script and fix anything marked `ERROR`:
   ```
   .venv/bin/python scripts/check_data.py
   ```
3. Run the tests:
   ```
   .venv/bin/python -m pytest tests/common -q
   ```
