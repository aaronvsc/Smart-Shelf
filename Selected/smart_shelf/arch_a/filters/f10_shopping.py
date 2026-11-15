"""Filter 10 - Shopping List: every missing required ingredient with no available substitute."""
from smart_shelf.arch_a.filter_base import Filter
from smart_shelf.arch_a.records import RecipeRecord


class ShoppingListFilter(Filter):
    def process(self, record: RecipeRecord):
        record.shopping_list = [gap.name for gap in record.to_buy]
        if record.shopping_list:
            record.note(self.name, "buy " + ", ".join(record.shopping_list))
        yield record
