"""Filter 8 - Preference Weighting: favor recipes and cuisines the user picked before.

Reads only this user's own history from the run context (Privacy).
"""
from collections import Counter

from smart_shelf.arch_a.config import (
    PREFERENCE_CUISINE_WEIGHT, PREFERENCE_MAX_BOOST, PREFERENCE_RECIPE_WEIGHT,
)
from smart_shelf.arch_a.filter_base import Filter
from smart_shelf.arch_a.records import RecipeRecord


class PreferenceFilter(Filter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        cuisine_of = {r.id: r.cuisine for r in self.ref.recipes}
        history = self.ctx.profile.history if self.ctx else ()
        self.recipe_counts = Counter(h.recipe_id for h in history)
        self.cuisine_counts = Counter(cuisine_of[h.recipe_id] for h in history
                                      if h.recipe_id in cuisine_of)

    def process(self, record: RecipeRecord):
        times = self.recipe_counts[record.recipe.id]
        same_cuisine = self.cuisine_counts[record.recipe.cuisine]
        boost = PREFERENCE_RECIPE_WEIGHT * times + PREFERENCE_CUISINE_WEIGHT * same_cuisine
        record.preference_boost = min(boost, PREFERENCE_MAX_BOOST)
        if times or same_cuisine:
            record.note(self.name, f"chosen {times} time(s) before; "
                                   f"{same_cuisine} past {record.recipe.cuisine} pick(s)")
        yield record
