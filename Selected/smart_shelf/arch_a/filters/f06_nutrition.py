"""Filter 6 - Nutrition.

In:  RecipeRecord (p5)
Out: the record with nutrition filled in (p6)
"""
from smart_shelf.arch_a.filter_base import Filter
from smart_shelf.common.models import Nutrition
from smart_shelf.arch_a.records import RecipeRecord
from smart_shelf.arch_a.stores import INGREDIENT_DICTIONARY, SUBSTITUTION_NUTRITION


class NutritionFilter(Filter):
    reads = frozenset({SUBSTITUTION_NUTRITION, INGREDIENT_DICTIONARY})

    def process(self, record: RecipeRecord):
        gaps = {g.name: g for g in record.missing}
        total = Nutrition()
        no_data: list[str] = []
        for ing, need_unit in zip(record.recipe.ingredients, record.needs):
            gap = gaps.get(ing.name)
            if gap is not None and not gap.required:
                continue
            need = need_unit[0] if need_unit else 0.0
            parts = [(ing.name, need)]
            if gap is not None and ing.name in record.substitutions:
                sub = self._substitute(ing.name, record.substitutions[ing.name])
                parts = [(ing.name, need - gap.short_qty), (sub.name, gap.short_qty * sub.ratio)]
            for name, qty in parts:
                if qty <= 0:
                    continue
                n = self.stores.nutrition_of(name, qty)
                if n is None:
                    no_data.append(name)
                else:
                    total = total + n
        record.nutrition = total
        msg = f"{total.kcal:.0f} kcal"
        if no_data:
            msg += "; no nutrition data for " + ", ".join(no_data)
        record.note(self.name, msg)
        yield record

    def _substitute(self, original: str, name: str):
        return next(s for s in self.stores.substitutes[original] if s.name == name)
