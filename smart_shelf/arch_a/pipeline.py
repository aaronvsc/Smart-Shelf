"""Creates, connects and runs the pipes and filters (Figure 1)."""
from __future__ import annotations

import time
from datetime import date
from typing import Iterable, Sequence

from smart_shelf.arch_a.filter_base import Filter
from smart_shelf.arch_a.filters import (
    DietaryFilter, FreshnessFilter, GapsFilter, MatchFilter, NormalizeFilter,
    NutritionFilter, PreferenceFilter, RankFilter, ShoppingListFilter, SubstituteFilter,
)
from smart_shelf.arch_a.inputs import ReferenceData, UserProfile
from smart_shelf.arch_a.pipe import Pipe
from smart_shelf.arch_a.records import (
    END, ExclusionSummary, NormalizedPantry, PipelineResult, RecipeRecord, RunContext,
)

# Filters 2-10, in order. Filter 1 (Normalize) runs synchronously first so that
# unrecognized items come straight back to the UI (the "Submit pantry" call).
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
        self.ref = ref
        self.filter_classes = tuple(filter_classes)
        self.timeout_s = timeout_s

    def run(self, raw_pantry: list[dict], profile: UserProfile | None,
            rejected_subs: Iterable[tuple[str, str]] = (),
            today: date | None = None) -> PipelineResult:
        """Run once. A substitute decision means calling run() again with rejected_subs."""
        start = time.perf_counter()
        if profile is None:
            raise ValueError("A user profile is required; refusing to run without "
                             "the user's restrictions")
        self.ref.check_restrictions(profile)

        pantry, unrecognized = NormalizeFilter.normalize(raw_pantry, self.ref)
        if not pantry:
            return PipelineResult("empty_pantry", unrecognized=unrecognized,
                                  elapsed_s=time.perf_counter() - start)

        ctx = RunContext(pantry, profile, frozenset(map(tuple, rejected_subs)),
                         today or date.today())
        pipes = [Pipe(f"p{i + 1}") for i in range(len(self.filter_classes) + 1)]
        filters = [cls(pipes[i], pipes[i + 1], ctx, self.ref)
                   for i, cls in enumerate(self.filter_classes)]
        for f in filters:
            f.start()
        pipes[0].put(NormalizedPantry(pantry))
        pipes[0].close()

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
                              time.perf_counter() - start)


def combine_shopping_lists(ranked: Sequence[RecipeRecord],
                           selected_ids: Iterable[str]) -> list[tuple[str, float, str]]:
    """Step 5: merge the shopping lists of the selected recipes into (name, qty, unit)."""
    selected = set(selected_ids)
    totals: dict[str, list] = {}
    for record in ranked:
        if record.recipe.id not in selected:
            continue
        for gap in record.to_buy:
            entry = totals.setdefault(gap.name, [0.0, gap.unit])
            entry[0] += gap.short_qty
    return [(name, qty, unit) for name, (qty, unit) in totals.items()]
