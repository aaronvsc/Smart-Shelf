"""Filter 3 - Dietary Filter: drop recipes that break a restriction or allergy.

Runs right after matching, so nothing later in the pipeline can bring an unsafe
recipe back (Reliability). Any ingredient counts, optional ones included.
"""
from smart_shelf.arch_a.filter_base import Filter
from smart_shelf.arch_a.records import ExclusionSummary, RecipeRecord
from smart_shelf.arch_a.stores import INGREDIENT_DICTIONARY, USER_PROFILE


class DietaryFilter(Filter):
    # The restriction rules and ingredient tags live in the Ingredient Dictionary.
    reads = frozenset({USER_PROFILE, INGREDIENT_DICTIONARY})

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.matched_count = 0
        self.excluded: dict[str, tuple[str, ...]] = {}

    def process(self, record: RecipeRecord):
        self.matched_count += 1
        profile = self.stores.profile
        broken: dict[str, None] = {}
        for ing in record.recipe.ingredients:
            for r in self.stores.violations(ing.name, profile):
                broken[r] = None
        if broken:
            self.excluded[record.recipe.id] = tuple(broken)
            return
        if profile.all_restrictions:
            record.note(self.name, "complies with " + ", ".join(profile.all_restrictions))
        yield record

    def flush(self):
        yield ExclusionSummary(self.matched_count, dict(self.excluded))
