"""Filter 4 - Detect Gaps: find missing or short ingredients.

Reads no store: the pantry and the recipe's base-unit quantities arrive with the record.
"""
from smart_shelf.arch_a.config import EPSILON
from smart_shelf.arch_a.filter_base import Filter
from smart_shelf.arch_a.records import Gap, RecipeRecord


class GapsFilter(Filter):
    def process(self, record: RecipeRecord):
        pantry = record.run.items
        for ing, need_unit in zip(record.recipe.ingredients, record.needs):
            if need_unit is None:
                raise ValueError(f"{record.recipe.id}: cannot convert {ing.qty} {ing.unit} "
                                 f"of {ing.name!r}; check the recipe data")
            need, unit = need_unit
            item = pantry.get(ing.name)
            have = item.qty if item else 0.0
            if have + EPSILON >= need:
                record.on_hand.append(ing.name)
                continue
            record.missing.append(Gap(ing.name, need, need - have, unit,
                                      ing.required, ing.substitutable))
            kind = "required" if ing.required else "optional"
            record.note(self.name, f"{kind} {ing.name}: short {need - have:g} {unit}")
        yield record
