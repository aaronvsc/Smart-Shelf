"""Check script: validates all the data files in data/ before anyone uses them.

Run it after editing any data file:  .venv/bin/python scripts/check_data.py
It first loads everything the same way the app does (so broken data is caught
with a clear message), then runs extra checks across files and prints a summary.
Errors must be fixed (exit code 1); warnings are worth a look but won't fail.
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from smart_shelf.common.data_access import DATA_DIR, DataError, load_reference_data  # noqa: E402

RECIPE_TARGET = 200


def run_checks(data_dir: Path | None = None) -> tuple[list[str], list[str], list[str]]:
    """Return (errors, warnings, summary lines) for the data in data_dir."""
    try:
        ref = load_reference_data(data_dir or DATA_DIR)
    except DataError as e:
        return [str(e)], [], []

    errors: list[str] = []
    warnings: list[str] = []

    for name in sorted(set(ref.ingredients) - set(ref.nutrition)):
        errors.append(f"{name!r} has no nutrition data in substitutions_nutrition.json")

    for r in ref.recipes:
        for part in r.ingredients:
            if part.substitutable and part.name not in ref.substitutes:
                errors.append(f"{r.id} ({r.name}): {part.name!r} is marked substitutable "
                              "but has no substitutes listed")

    name_counts = Counter(r.name.lower() for r in ref.recipes)
    for name, count in sorted(name_counts.items()):
        if count > 1:
            warnings.append(f"recipe name {name!r} is used {count} times")

    used = {part.name for r in ref.recipes for part in r.ingredients}
    for name in sorted(set(ref.ingredients) - used):
        warnings.append(f"{name!r} is in the dictionary but no recipe uses it yet")

    tags_in_use = frozenset().union(*(i.tags for i in ref.ingredients.values()))
    for rule, tags in sorted(ref.restrictions.items()):
        for tag in sorted(tags - tags_in_use):
            warnings.append(f"restriction {rule!r} forbids tag {tag!r}, but no ingredient has it")

    cuisines = Counter(r.cuisine for r in ref.recipes)
    summary = [
        f"{len(ref.recipes)} recipes (target ~{RECIPE_TARGET}), "
        f"{len(ref.ingredients)} ingredients, {len(ref.restrictions)} restriction rules",
        "cuisines: " + ", ".join(f"{c} {n}" for c, n in cuisines.most_common()),
    ]
    return errors, warnings, summary


def main(data_dir: Path | None = None) -> int:
    errors, warnings, summary = run_checks(data_dir)
    for line in summary:
        print(line)
    for w in warnings:
        print(f"WARNING: {w}")
    for e in errors:
        print(f"ERROR: {e}")
    print(f"\n{'FAIL' if errors else 'PASS'}: {len(errors)} error(s), {len(warnings)} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
