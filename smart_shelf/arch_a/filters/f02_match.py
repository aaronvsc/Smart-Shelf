"""Filter 2 - Match Recipes: send out each fully or partially makeable recipe as its own record."""
from smart_shelf.arch_a.config import MATCH_MIN_REQUIRED_ON_HAND
from smart_shelf.arch_a.filter_base import Filter
from smart_shelf.arch_a.records import NormalizedPantry, RecipeRecord


class MatchFilter(Filter):
    def process(self, pantry: NormalizedPantry):
        for recipe in sorted(self.ref.recipes, key=lambda r: r.id):    # fixed order (Consistency)
            required = [i.name for i in recipe.ingredients if i.required]
            on_hand = [n for n in required if n in pantry.items]
            if required and len(on_hand) >= MATCH_MIN_REQUIRED_ON_HAND:
                record = RecipeRecord(recipe)
                record.note(self.name, f"{len(on_hand)}/{len(required)} required ingredients in pantry")
                yield record
