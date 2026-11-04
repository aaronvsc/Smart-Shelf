"""Print reproducible comparison evidence without changing profiles or team data."""
from __future__ import annotations

import json
import platform
import statistics
import sys
from dataclasses import asdict, replace
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from smart_shelf.arch_a.pipeline import Pipeline
from smart_shelf.arch_b import BlackboardEngine
from smart_shelf.common.data_access import load_reference_data
from smart_shelf.common.models import UserProfile

TODAY = date(2026, 11, 3)
REPEATS = 10


def canonical(result):
    records = []
    for record in result.ranked:
        value = asdict(record)
        value.pop("trace")
        records.append(value)
    return (result.status, records, [asdict(item) for item in result.unrecognized],
            asdict(result.exclusions) if result.exclusions else None)


def measure(ref, rows):
    timings = {"A": [], "B": []}
    expected = None
    profile = UserProfile("benchmark")
    for _ in range(REPEATS):
        a = Pipeline(ref).run(rows, profile, today=TODAY)
        b = BlackboardEngine(ref).run(rows, profile, today=TODAY)
        if canonical(a) != canonical(b):
            raise AssertionError("A/B recommendation mismatch")
        current = canonical(b)
        if expected is not None and expected != current:
            raise AssertionError("Repeated outputs differ")
        expected = current
        timings["A"].append(a.elapsed_s)
        timings["B"].append(b.elapsed_s)
    return {name: {"median_ms": round(statistics.median(values) * 1000, 3),
                   "max_ms": round(max(values) * 1000, 3)}
            for name, values in timings.items()}


def main():
    ref = load_reference_data()
    rows = [{"name": name, "qty": 1000, "unit": item.base_unit}
            for name, item in list(ref.ingredients.items())[:50]]
    synthetic = replace(ref, recipes=tuple(
        replace(ref.recipes[index % len(ref.recipes)], id=f"S{index:03}")
        for index in range(200)))
    result = {"python": platform.python_version(), "platform": platform.platform(),
              "fixed_analysis_date": str(TODAY), "repeats": REPEATS,
              "real_recipe_count": len(ref.recipes), "pantry_items": len(rows),
              "real_data": measure(ref, rows),
              "synthetic_200_recipes": measure(synthetic, rows),
              "synthetic_note": "Existing recipes repeated with unique IDs; not 200 curated recipes."}
    decision_rows = [{"name": name, "qty": 10000, "unit": item.base_unit}
                     for name, item in ref.ingredients.items() if name != "butter"]
    profile = UserProfile("benchmark")
    sample = BlackboardEngine(ref).run(decision_rows, profile, today=TODAY)
    pair = next(((record.recipe.id, substitute) for record in sample.ranked
                 for substitute in record.substitutions.values()), None)
    if pair is not None:
        a_times, b_times = [], []
        for _ in range(REPEATS):
            engine = BlackboardEngine(ref)
            engine.run(decision_rows, profile, today=TODAY)
            b = engine.decide_substitute(*pair, accepted=False)
            a = Pipeline(ref).run(decision_rows, profile, rejected_subs=[pair], today=TODAY)
            assert canonical(a) == canonical(b)
            a_times.append(a.elapsed_s)
            b_times.append(b.elapsed_s)
        result["substitution_update"] = {
            "decision": pair, "A_median_ms": round(statistics.median(a_times) * 1000, 3),
            "B_median_ms": round(statistics.median(b_times) * 1000, 3),
            "B_activations": b.activations,
            "note": "Fewer activations do not imply lower elapsed time; B copies region snapshots."}
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
