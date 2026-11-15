"""Filter 2 - Match Recipes: send out each fully or partially makeable recipe as its own record."""
from smart_shelf.arch_a.config import MATCH_MIN_REQUIRED_ON_HAND
from smart_shelf.arch_a.filter_base import Filter
from smart_shelf.arch_a.records import NormalizedPantry, RecipeRecord
from smart_shelf.arch_a.stores import INGREDIENT_DICTIONARY, RECIPE_DATABASE


def recipe_needs(recipe, stores) -> tuple:
    """Each ingredient's quantity in base units, as (qty, unit), in recipe order."""
    needs = []
    for ing in recipe.ingredients:
        qty = stores.to_base(ing.name, ing.qty, ing.unit)
        needs.append(None if qty is None else (qty, stores.ingredients[ing.name].base_unit))
    return tuple(needs)


class MatchFilter(Filter):
    # Also reads the Ingredient Dictionary to put recipe quantities in base units,
    # so later filters compare quantities without their own store access.
    reads = frozenset({RECIPE_DATABASE, INGREDIENT_DICTIONARY})

    def process(self, pantry: NormalizedPantry):
        for recipe in sorted(self.stores.recipes, key=lambda r: r.id):    # fixed order (Consistency)
            required = [i.name for i in recipe.ingredients if i.required]
            on_hand = [n for n in required if n in pantry.items]
            if required and len(on_hand) >= MATCH_MIN_REQUIRED_ON_HAND:
                record = RecipeRecord(recipe)
                record.run = pantry
                record.needs = recipe_needs(recipe, self.stores)
                record.note(self.name, f"{len(on_hand)}/{len(required)} required ingredients in pantry")
                yield record
