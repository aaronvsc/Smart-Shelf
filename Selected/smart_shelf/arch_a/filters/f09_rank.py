"""Filter 9 - Rank: the only filter that waits for every record before sending anything on.

Each required ingredient earns credit: on hand 1.0, substituted SUBSTITUTE_CREDIT,
to buy 0. Closeness is the average credit; freshness and preference boosts are
added on top. Ties break by fewer items to buy, then recipe ID (Consistency).
"""
from smart_shelf.arch_a.config import SUBSTITUTE_CREDIT
from smart_shelf.arch_a.filter_base import Filter
from smart_shelf.arch_a.records import RecipeRecord


class RankFilter(Filter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.buffer: list[RecipeRecord] = []

    def process(self, record: RecipeRecord):
        required = [i.name for i in record.recipe.ingredients if i.required]
        on_hand = sum(1 for n in required if n in record.on_hand)
        subbed = sum(1 for n in required if n in record.substitutions)
        to_buy = len(record.to_buy)
        closeness = (on_hand + SUBSTITUTE_CREDIT * subbed) / len(required) if required else 0.0
        record.score = closeness + record.freshness_boost + record.preference_boost
        record.note(self.name, f"score {record.score:.3f} = closeness {closeness:.3f} "
                               f"({on_hand} on hand, {subbed} substituted, {to_buy} to buy) "
                               f"+ freshness {record.freshness_boost:.3f} "
                               f"+ preference {record.preference_boost:.3f}")
        self.buffer.append(record)
        return ()

    @staticmethod
    def sort_key(record: RecipeRecord):
        return (-round(record.score, 9), len(record.to_buy), record.recipe.id)

    def flush(self):
        yield from sorted(self.buffer, key=self.sort_key)
