"""Filter 6 - Nutrition: calories and macros from per-ingredient data, reflecting substitutes."""
from smart_shelf.arch_a.filter_base import Filter
from smart_shelf.arch_a.inputs import Nutrition
from smart_shelf.arch_a.records import RecipeRecord


class NutritionFilter(Filter):
    def process(self, record: RecipeRecord):
        gaps = {g.name: g for g in record.missing}
        total = Nutrition()
        no_data: list[str] = []
        for ing in record.recipe.ingredients:
            gap = gaps.get(ing.name)
            if gap is not None and not gap.required:
                continue                    # optional and missing: not in the dish
            need = self.ref.to_base(ing.name, ing.qty, ing.unit) or 0.0
            parts = [(ing.name, need)]
            if gap is not None and ing.name in record.substitutions:
                sub = self._substitute(ing.name, record.substitutions[ing.name])
                parts = [(ing.name, need - gap.short_qty), (sub.name, gap.short_qty * sub.ratio)]
            for name, qty in parts:
                if qty <= 0:
                    continue
                n = self.ref.nutrition_of(name, qty)
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
        return next(s for s in self.ref.substitutes[original] if s.name == name)
