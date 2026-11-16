"""Filter 7 - Freshness.

In:  RecipeRecord (p6)
Out: the record with freshness_boost filled in (p7)
"""
from smart_shelf.arch_a.config import (
    FRESHNESS_MAX_BOOST, FRESHNESS_WEIGHT_PER_ITEM, FRESHNESS_WINDOW_DAYS,
)
from smart_shelf.arch_a.filter_base import Filter
from smart_shelf.arch_a.records import RecipeRecord


class FreshnessFilter(Filter):
    def process(self, record: RecipeRecord):
        used = [i.name for i in record.recipe.ingredients] + list(record.substitutions.values())
        pantry, today = record.run.items, record.run.today
        boost = 0.0
        for name in dict.fromkeys(used):
            item = pantry.get(name)
            if item is None or item.expires is None:
                continue
            days = (item.expires - today).days
            if 0 <= days <= FRESHNESS_WINDOW_DAYS:
                boost += FRESHNESS_WEIGHT_PER_ITEM * (FRESHNESS_WINDOW_DAYS + 1 - days) / (FRESHNESS_WINDOW_DAYS + 1)
                record.note(self.name, f"uses {name}, expires in {days} day(s)")
        record.freshness_boost = min(boost, FRESHNESS_MAX_BOOST)
        yield record
