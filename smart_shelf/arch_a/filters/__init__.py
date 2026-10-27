"""The 10 filters of Architecture A, in pipeline order."""
from smart_shelf.arch_a.filters.f01_normalize import NormalizeFilter
from smart_shelf.arch_a.filters.f02_match import MatchFilter
from smart_shelf.arch_a.filters.f03_dietary import DietaryFilter
from smart_shelf.arch_a.filters.f04_gaps import GapsFilter
from smart_shelf.arch_a.filters.f05_substitute import SubstituteFilter
from smart_shelf.arch_a.filters.f06_nutrition import NutritionFilter
from smart_shelf.arch_a.filters.f07_freshness import FreshnessFilter
from smart_shelf.arch_a.filters.f08_preference import PreferenceFilter
from smart_shelf.arch_a.filters.f09_rank import RankFilter
from smart_shelf.arch_a.filters.f10_shopping import ShoppingListFilter

__all__ = [
    "NormalizeFilter", "MatchFilter", "DietaryFilter", "GapsFilter", "SubstituteFilter",
    "NutritionFilter", "FreshnessFilter", "PreferenceFilter", "RankFilter", "ShoppingListFilter",
]
