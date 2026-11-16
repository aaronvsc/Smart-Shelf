"""Filter 5 - Substitute.

In:  RecipeRecord (p4)
Out: the record with substitutions and to_buy filled in (p5)
"""
from smart_shelf.arch_a.config import EPSILON
from smart_shelf.arch_a.filter_base import Filter
from smart_shelf.common.models import Substitute, UserProfile
from smart_shelf.arch_a.records import Gap, RecipeRecord
from smart_shelf.arch_a.stores import INGREDIENT_DICTIONARY, SUBSTITUTION_NUTRITION


class SubstituteFilter(Filter):
    reads = frozenset({SUBSTITUTION_NUTRITION, INGREDIENT_DICTIONARY})

    def process(self, record: RecipeRecord):
        remaining = self._remaining_after(record)
        restrictions = UserProfile("run", restrictions=record.run.restrictions)
        for gap in record.missing:
            if not gap.required:
                continue
            sub = self._find(record, gap, remaining, restrictions) if gap.substitutable else None
            if sub is None:
                record.to_buy.append(gap)
                continue
            used = gap.short_qty * sub.ratio
            remaining[sub.name] -= used
            record.substitutions[gap.name] = sub.name
            record.note(self.name, f"{sub.name} ({used:g} {self.stores.ingredients[sub.name].base_unit})"
                                   f" covers {gap.name}")
        yield record

    @staticmethod
    def _remaining_after(record: RecipeRecord) -> dict[str, float]:
        """Out: pantry quantities left after this recipe's own ingredients."""
        remaining = {name: item.qty for name, item in record.run.items.items()}
        for ing, need_unit in zip(record.recipe.ingredients, record.needs):
            if ing.name in remaining:
                need = need_unit[0] if need_unit else 0.0
                remaining[ing.name] = max(0.0, remaining[ing.name] - need)
        return remaining

    def _find(self, record: RecipeRecord, gap: Gap, remaining: dict[str, float],
              restrictions: UserProfile) -> Substitute | None:
        for sub in self.stores.substitutes.get(gap.name, ()):
            if (record.recipe.id, sub.name) in record.run.rejected_subs:
                continue
            if sub.name not in self.stores.ingredients:
                continue
            if self.stores.violations(sub.name, restrictions):
                continue
            if remaining.get(sub.name, 0.0) + EPSILON >= gap.short_qty * sub.ratio:
                return sub
        return None
