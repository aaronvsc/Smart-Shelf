"""Filter 5 - Substitute: cover missing required ingredients with compliant swaps the user has enough of."""
from smart_shelf.arch_a.config import EPSILON
from smart_shelf.arch_a.filter_base import Filter
from smart_shelf.arch_a.inputs import Substitute
from smart_shelf.arch_a.records import Gap, RecipeRecord


class SubstituteFilter(Filter):
    def process(self, record: RecipeRecord):
        remaining = self._remaining_after(record)
        for gap in record.missing:
            if not gap.required:
                continue                    # optional and missing: just left out, never bought
            sub = self._find(record, gap, remaining) if gap.substitutable else None
            if sub is None:
                record.to_buy.append(gap)
                continue
            used = gap.short_qty * sub.ratio
            remaining[sub.name] -= used
            record.substitutions[gap.name] = sub.name
            record.note(self.name, f"{sub.name} ({used:g} {self.ref.ingredients[sub.name].base_unit})"
                                   f" covers {gap.name}")
        yield record

    def _remaining_after(self, record: RecipeRecord) -> dict[str, float]:
        """Pantry quantities left once this recipe's own ingredients are used."""
        remaining = {name: item.qty for name, item in self.ctx.pantry.items()}
        for ing in record.recipe.ingredients:
            if ing.name in remaining:
                need = self.ref.to_base(ing.name, ing.qty, ing.unit) or 0.0
                remaining[ing.name] = max(0.0, remaining[ing.name] - need)
        return remaining

    def _find(self, record: RecipeRecord, gap: Gap, remaining: dict[str, float]) -> Substitute | None:
        for sub in self.ref.substitutes.get(gap.name, ()):
            if (record.recipe.id, sub.name) in self.ctx.rejected_subs:
                continue
            if sub.name not in self.ref.ingredients:
                continue
            if self.ref.violations(sub.name, self.ctx.profile):
                continue
            if remaining.get(sub.name, 0.0) + EPSILON >= gap.short_qty * sub.ratio:
                return sub
        return None
