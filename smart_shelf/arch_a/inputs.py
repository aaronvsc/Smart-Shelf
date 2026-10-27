"""Input types Architecture A works with.

The team's shared models and data loading are not designed yet, so Architecture A
defines the minimum it needs here. Once the shared models exist, swap these for
imports (or convert at the Pipeline boundary); the filters only rely on the
attributes below.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Mapping, Sequence


@dataclass(frozen=True)
class Ingredient:
    """One Ingredient Dictionary entry."""
    name: str
    base_unit: str                                   # "g", "ml" or "count"
    aliases: tuple[str, ...] = ()
    unit_conversions: Mapping[str, float] = field(default_factory=dict)  # unit -> base units
    tags: frozenset[str] = frozenset()               # e.g. {"dairy", "gluten"}


@dataclass(frozen=True)
class RecipeIngredient:
    name: str
    qty: float
    unit: str
    required: bool = True
    substitutable: bool = False


@dataclass(frozen=True)
class Recipe:
    id: str
    name: str
    cuisine: str
    cook_time_min: int
    ingredients: tuple[RecipeIngredient, ...]


@dataclass(frozen=True)
class Substitute:
    name: str
    ratio: float = 1.0      # substitute base units per 1 base unit of the original


@dataclass(frozen=True)
class Nutrition:
    kcal: float = 0.0
    protein_g: float = 0.0
    carbs_g: float = 0.0
    fat_g: float = 0.0

    def __add__(self, other: Nutrition) -> Nutrition:
        return Nutrition(self.kcal + other.kcal, self.protein_g + other.protein_g,
                         self.carbs_g + other.carbs_g, self.fat_g + other.fat_g)

    def scaled(self, factor: float) -> Nutrition:
        return Nutrition(self.kcal * factor, self.protein_g * factor,
                         self.carbs_g * factor, self.fat_g * factor)


@dataclass(frozen=True)
class PantryItem:
    """A pantry entry after normalization: qty is in the ingredient's base unit."""
    name: str
    qty: float
    unit: str
    expires: date | None = None


@dataclass(frozen=True)
class SelectionEntry:
    recipe_id: str
    selected_at: date


@dataclass(frozen=True)
class UserProfile:
    user_id: str
    restrictions: tuple[str, ...] = ()      # e.g. ("vegan",)
    allergies: tuple[str, ...] = ()         # e.g. ("peanut",)
    history: tuple[SelectionEntry, ...] = ()

    @property
    def all_restrictions(self) -> tuple[str, ...]:
        """Diets and allergies, de-duplicated, in declaration order."""
        return tuple(dict.fromkeys(self.restrictions + self.allergies))


@dataclass(frozen=True)
class ReferenceData:
    """Read-only reference data the filters look up (the store lookups in Figure 1)."""
    ingredients: Mapping[str, Ingredient]
    recipes: Sequence[Recipe]
    substitutes: Mapping[str, Sequence[Substitute]] = field(default_factory=dict)
    nutrition: Mapping[str, Nutrition] = field(default_factory=dict)  # per 100 g/ml, or per item
    restrictions: Mapping[str, frozenset[str]] = field(default_factory=dict)  # -> forbidden tags

    def to_base(self, name: str, qty: float, unit: str) -> float | None:
        """Convert qty to the ingredient's base unit, or None if that is not possible."""
        ing = self.ingredients.get(name)
        if ing is None:
            return None
        if unit == ing.base_unit:
            return qty
        factor = ing.unit_conversions.get(unit)
        return None if factor is None else qty * factor

    def check_restrictions(self, profile: UserProfile) -> None:
        """Raise ValueError for a restriction we have no rule for, instead of ignoring it."""
        for r in profile.all_restrictions:
            self._forbidden(r)

    def violations(self, name: str, profile: UserProfile) -> tuple[str, ...]:
        """The profile's restrictions that this ingredient breaks.

        An ingredient missing from the dictionary cannot be checked, so it counts
        as a violation when the profile has any restriction (Reliability).
        """
        ing = self.ingredients.get(name)
        if ing is None:
            return ("unverified ingredient",) if profile.all_restrictions else ()
        return tuple(r for r in profile.all_restrictions if self._forbidden(r) & ing.tags)

    def nutrition_of(self, name: str, base_qty: float) -> Nutrition | None:
        per = self.nutrition.get(name)
        ing = self.ingredients.get(name)
        if per is None or ing is None:
            return None
        return per.scaled(base_qty if ing.base_unit == "count" else base_qty / 100)

    def _forbidden(self, restriction: str) -> frozenset[str]:
        try:
            return self.restrictions[restriction]
        except KeyError:
            raise ValueError(f"Unknown restriction or allergy {restriction!r}") from None
