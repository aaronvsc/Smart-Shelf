"""Read-only, per-filter access to the data stores (the dashed data-access arrows in Figure 1).

Each filter declares the stores it reads in `Filter.reads`. Its StoreView exposes only
those, and only as read-only views, so no filter can change data another one depends
on, and no filter can quietly start depending on a store the design doesn't give it.
"""
from __future__ import annotations

from dataclasses import replace
from types import MappingProxyType
from typing import Iterable

from smart_shelf.common.models import Nutrition, ReferenceData, UserProfile

# The four data stores in Figure 1. The restriction rules live in ingredients.json,
# so they belong to the Ingredient Dictionary.
INGREDIENT_DICTIONARY = "Ingredient Dictionary"
RECIPE_DATABASE = "Recipe Database"
SUBSTITUTION_NUTRITION = "Substitution & Nutrition Data"
USER_PROFILE = "User Profile & History"


class StoreAccessError(PermissionError):
    """A filter tried to read a store outside its declared data access."""


def read_only(ref: ReferenceData) -> ReferenceData:
    """A copy of the reference data whose mappings can't be changed."""
    if isinstance(ref.ingredients, MappingProxyType):
        return ref
    ingredients = {name: replace(ing, unit_conversions=MappingProxyType(dict(ing.unit_conversions)))
                   for name, ing in ref.ingredients.items()}
    return ReferenceData(
        ingredients=MappingProxyType(ingredients),
        recipes=tuple(ref.recipes),
        substitutes=MappingProxyType({name: tuple(subs) for name, subs in ref.substitutes.items()}),
        nutrition=MappingProxyType(dict(ref.nutrition)),
        restrictions=MappingProxyType({name: frozenset(tags) for name, tags in ref.restrictions.items()}),
    )


class StoreView:
    """The stores one filter may read. Anything else raises StoreAccessError."""

    def __init__(self, ref: ReferenceData, profile: UserProfile | None,
                 reads: Iterable[str], owner: str):
        self._ref = read_only(ref)
        self._profile = profile
        self._reads = frozenset(reads)
        self._owner = owner

    def _need(self, *stores: str) -> None:
        missing = [s for s in stores if s not in self._reads]
        if missing:
            raise StoreAccessError(f"{self._owner} has no data access to {', '.join(missing)}")

    # --- Ingredient Dictionary
    @property
    def ingredients(self):
        self._need(INGREDIENT_DICTIONARY)
        return self._ref.ingredients

    @property
    def restrictions(self):
        self._need(INGREDIENT_DICTIONARY)
        return self._ref.restrictions

    def to_base(self, name: str, qty: float, unit: str) -> float | None:
        self._need(INGREDIENT_DICTIONARY)
        return self._ref.to_base(name, qty, unit)

    def violations(self, name: str, profile: UserProfile) -> tuple[str, ...]:
        self._need(INGREDIENT_DICTIONARY)
        return self._ref.violations(name, profile)

    def check_restrictions(self, profile: UserProfile) -> None:
        self._need(INGREDIENT_DICTIONARY)
        self._ref.check_restrictions(profile)

    # --- Recipe Database
    @property
    def recipes(self):
        self._need(RECIPE_DATABASE)
        return self._ref.recipes

    # --- Substitution & Nutrition Data
    @property
    def substitutes(self):
        self._need(SUBSTITUTION_NUTRITION)
        return self._ref.substitutes

    def nutrition_of(self, name: str, base_qty: float) -> Nutrition | None:
        self._need(SUBSTITUTION_NUTRITION, INGREDIENT_DICTIONARY)   # per-100 values need the base unit
        return self._ref.nutrition_of(name, base_qty)

    # --- User Profile & History (loaded by the UI for this run; frozen)
    @property
    def profile(self) -> UserProfile | None:
        self._need(USER_PROFILE)
        return self._profile
