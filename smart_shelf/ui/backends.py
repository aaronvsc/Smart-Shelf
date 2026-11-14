"""One front door to each architecture, so the UI never has to know which one it's using.

Both classes below offer the same three calls, matching the user's steps:
  run(pantry_rows, profile)             Steps 1-3: analyze the pantry, rank recipes
  decide_substitute(recipe_id, name, accepted)
                                        Step 4: accept or reject a suggested swap
  select(recipe_ids, event_id)          Step 5: save the picks to history and
                                        return the combined shopping list

`event_id` names one click of the "select" button. Streamlit reruns the script
often, so calling select() again with the same ID must not save history twice.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Iterable

from smart_shelf.arch_a.pipeline import Pipeline, combine_shopping_lists
from smart_shelf.arch_b import BlackboardEngine
from smart_shelf.common.data_access import save_selection
from smart_shelf.common.models import ReferenceData, UserProfile

ShoppingList = list[tuple[str, float, str]]        # (ingredient name, quantity, unit)


class PipeAndFilterBackend:
    """Architecture A. Each call reruns the whole pipeline with the latest decisions."""

    def __init__(self, ref: ReferenceData, profiles_dir: Path | None = None):
        self.ref = ref
        self.profiles_dir = profiles_dir
        self.pipeline = Pipeline(ref)
        self.result = None
        self._saved: dict[str, tuple[str, ...]] = {}   # event_id -> recipe IDs it saved

    def run(self, pantry_rows: list[dict], profile: UserProfile, today: date | None = None):
        self._pantry, self._profile = pantry_rows, profile
        self._today = today or date.today()
        self._rejected: set[tuple[str, str]] = set()
        return self._rerun()

    def decide_substitute(self, recipe_id: str, substitute_name: str, accepted: bool):
        self._require_run()
        pair = (recipe_id, substitute_name)
        if accepted:
            self._rejected.discard(pair)
        else:
            self._rejected.add(pair)
        return self._rerun()

    def select(self, recipe_ids: Iterable[str], event_id: str) -> ShoppingList:
        self._require_run()
        ids = tuple(sorted(set(recipe_ids)))
        allowed = {record.recipe.id for record in self.result.ranked}
        if not ids or not set(ids) <= allowed:
            raise ValueError("Select at least one recipe from the ranked results")
        if event_id in self._saved and self._saved[event_id] != ids:
            raise ValueError("A selection event ID cannot be reused with different recipes")
        if event_id not in self._saved:
            save_selection(self._profile.user_id, list(ids), self._today, self.profiles_dir)
            self._saved[event_id] = ids
        return combine_shopping_lists(self.result, ids, self.ref)

    def _rerun(self):
        self.result = self.pipeline.run(self._pantry, self._profile,
                                        rejected_subs=self._rejected, today=self._today)
        return self.result

    def _require_run(self):
        if self.result is None:
            raise ValueError("Call run() with a pantry and profile first")


class BlackboardBackend:
    """Architecture B. The engine keeps its blackboard between calls and saves history itself."""

    def __init__(self, ref: ReferenceData, profiles_dir: Path | None = None):
        self.engine = BlackboardEngine(ref, profiles_dir)
        self.result = None

    def run(self, pantry_rows: list[dict], profile: UserProfile, today: date | None = None):
        self.result = self.engine.run(pantry_rows, profile, today=today)
        return self.result

    def decide_substitute(self, recipe_id: str, substitute_name: str, accepted: bool):
        self.result = self.engine.decide_substitute(recipe_id, substitute_name, accepted)
        return self.result

    def select(self, recipe_ids: Iterable[str], event_id: str) -> ShoppingList:
        self.result = self.engine.select(recipe_ids, event_id=event_id)
        return self.result.combined_shopping_list


# The label shown in the sidebar switch -> the class that does the work.
BACKENDS = {
    "A: Pipe-and-Filter": PipeAndFilterBackend,
    "B: Blackboard": BlackboardBackend,
}
