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
from smart_shelf.common.models import ReferenceData, UserProfile
from smart_shelf.arch_a.pipe import Pipe
from smart_shelf.arch_a.records import END, ExclusionSummary, PipelineResult, RecipeRecord
from smart_shelf.arch_a.stores import read_only

# Filters 2-10, in order, connected by pipes p2-p10. Filter 1 (Normalize) is called
# first, like Figure 1's "submit pantry" procedure call: unrecognized items come
# straight back to the caller, and the usable pantry goes down p1.
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
        """Run once. A substitute decision means calling run() again with rejected_subs."""
        start = time.perf_counter()
        if profile is None:
            raise ValueError("A user profile is required; refusing to run without "
                             "the user's restrictions")

        pipes = [Pipe(f"p{i + 1}") for i in range(len(self.filter_classes) + 1)]   # p1-p10
        normalize = NormalizeFilter(None, pipes[0], self.ref)
        pantry, unrecognized = normalize.submit(raw_pantry, profile.all_restrictions,
                                                rejected_subs, today or date.today())
        if not pantry:
            return PipelineResult("empty_pantry", unrecognized=unrecognized,
                                  elapsed_s=time.perf_counter() - start)

        # The profile is the User Profile store; only filters that declare it can read it.
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
                              time.perf_counter() - start)


def combine_shopping_lists(ranked: Sequence[RecipeRecord],
                           selected_ids: Iterable[str]) -> list[tuple[str, float, str]]:
    """Step 5 (UI side, after the run): merge the selected recipes' shopping lists
    into (name, qty, unit)."""
    selected = set(selected_ids)
    totals: dict[str, list] = {}
    for record in ranked:
        if record.recipe.id not in selected:
            continue
        for gap in record.to_buy:
            entry = totals.setdefault(gap.name, [0.0, gap.unit])
            entry[0] += gap.short_qty
    return [(name, qty, unit) for name, (qty, unit) in totals.items()]
