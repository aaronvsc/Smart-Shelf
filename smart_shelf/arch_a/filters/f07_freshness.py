"""Filter 7 - Freshness: boost recipes that use pantry items close to expiring."""
from smart_shelf.arch_a.config import (
    FRESHNESS_MAX_BOOST, FRESHNESS_WEIGHT_PER_ITEM, FRESHNESS_WINDOW_DAYS,
)
from smart_shelf.arch_a.filter_base import Filter
from smart_shelf.arch_a.records import RecipeRecord


class FreshnessFilter(Filter):
    def process(self, record: RecipeRecord):
        used = [i.name for i in record.recipe.ingredients] + list(record.substitutions.values())
        boost = 0.0
        for name in dict.fromkeys(used):
            item = self.ctx.pantry.get(name)
            if item is None or item.expires is None:
                continue
            days = (item.expires - self.ctx.today).days
            if 0 <= days <= FRESHNESS_WINDOW_DAYS:
                # sooner expiry -> bigger boost
                boost += FRESHNESS_WEIGHT_PER_ITEM * (FRESHNESS_WINDOW_DAYS + 1 - days) / (FRESHNESS_WINDOW_DAYS + 1)
                record.note(self.name, f"uses {name}, expires in {days} day(s)")
        record.freshness_boost = min(boost, FRESHNESS_MAX_BOOST)
        yield record
