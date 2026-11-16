"""Creates, connects and runs the pipes and filters.

In:  raw pantry rows, user profile, rejected substitutes, today
Out: PipelineResult (ranked records, unrecognized rows, exclusion summary)
"""
from __future__ import annotations

import time
from datetime import date
from typing import Iterable, Sequence

from smart_shelf.arch_a.config import EPSILON
from smart_shelf.arch_a.filter_base import Filter
from smart_shelf.arch_a.filters import (
    DietaryFilter, FreshnessFilter, GapsFilter, MatchFilter, NormalizeFilter,
    NutritionFilter, PreferenceFilter, RankFilter, ShoppingListFilter, SubstituteFilter,
)
from smart_shelf.common.models import ReferenceData, UserProfile
from smart_shelf.arch_a.pipe import Pipe
from smart_shelf.arch_a.records import END, ExclusionSummary, PipelineResult, RecipeRecord
from smart_shelf.arch_a.stores import read_only

DEFAULT_FILTERS: tuple[type[Filter], ...] = (
    MatchFilter, DietaryFilter, GapsFilter, SubstituteFilter, NutritionFilter,
    FreshnessFilter, PreferenceFilter, RankFilter, ShoppingListFilter,
)


class PipelineError(Exception):
    pass


class Pipeline:
    def __init__(self, ref: ReferenceData,
                 filter_classes: Sequence[type[Filter]] = DEFAULT_FILTERS,
                 timeout_s: float = 10.0):
        self.ref = read_only(ref)
        self.filter_classes = tuple(filter_classes)
        self.timeout_s = timeout_s

    def run(self, raw_pantry: list[dict], profile: UserProfile | None,
            rejected_subs: Iterable[tuple[str, str]] = (),
            today: date | None = None) -> PipelineResult:
        start = time.perf_counter()
        if profile is None:
            raise ValueError("A user profile is required; refusing to run without "
                             "the user's restrictions")

        pipes = [Pipe(f"p{i + 1}") for i in range(len(self.filter_classes) + 1)]
        normalize = NormalizeFilter(None, pipes[0], self.ref)
        pantry, unrecognized = normalize.submit(raw_pantry, profile.all_restrictions,
                                                rejected_subs, today or date.today())
        if not pantry:
            return PipelineResult("empty_pantry", unrecognized=unrecognized,
                                  elapsed_s=time.perf_counter() - start)

        filters = [cls(pipes[i], pipes[i + 1], self.ref, profile)
                   for i, cls in enumerate(self.filter_classes)]
        for f in filters:
            f.start()

        ranked: list[RecipeRecord] = []
        exclusions: ExclusionSummary | None = None
        while (item := pipes[-1].get(timeout=self.timeout_s)) is not END:
            if isinstance(item, ExclusionSummary):
                exclusions = item
            else:
                ranked.append(item)

        for f in filters:
            f.join(timeout=self.timeout_s)
        for f in filters:
            if f.error is not None:
                raise PipelineError(f"{f.name} failed: {f.error!r}") from f.error
            if f.is_alive():
                raise PipelineError(f"{f.name} did not finish")

        if ranked:
            status = "ok"
        elif exclusions is not None and exclusions.matched_count > 0:
            status = "all_excluded"
        else:
            status = "no_matches"
        return PipelineResult(status, ranked, unrecognized, exclusions,
                              time.perf_counter() - start, pantry)


def combine_shopping_lists(result: PipelineResult, selected_ids: Iterable[str],
                           ref: ReferenceData, counts: dict[str, int] | None = None
                           ) -> list[tuple[str, float, str]]:
    """Step 5.

    In:  a PipelineResult, the selected recipe IDs, times to make each (default 1)
    Out: one shopping list as (name, qty, base unit), pantry subtracted once
    """
    selected = set(selected_ids)
    counts = counts or {}
    demand: dict[str, float] = {}
    for record in result.ranked:
        if record.recipe.id not in selected:
            continue
        times = counts.get(record.recipe.id, 1)
        gaps = {gap.name: gap for gap in record.missing}
        for item in record.recipe.ingredients:
            gap = gaps.get(item.name)
            if gap is not None and not gap.required:
                continue
            need = ref.to_base(item.name, item.qty, item.unit)
            if item.name in record.substitutions:
                name = record.substitutions[item.name]
                sub = next(s for s in ref.substitutes[item.name] if s.name == name)
                demand[item.name] = demand.get(item.name, 0.0) + (need - gap.short_qty) * times
                demand[name] = demand.get(name, 0.0) + gap.short_qty * sub.ratio * times
            else:
                demand[item.name] = demand.get(item.name, 0.0) + need * times
    combined = []
    for name, qty in sorted(demand.items()):
        short = qty - (result.pantry[name].qty if name in result.pantry else 0.0)
        if short > EPSILON:
            combined.append((name, short, ref.ingredients[name].base_unit))
    return combined
