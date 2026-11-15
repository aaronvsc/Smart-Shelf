"""Messages that flow through the pipes."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from types import MappingProxyType
from typing import Mapping

from smart_shelf.common.models import Nutrition, PantryItem, Recipe


class _EndOfStream:
    """End marker that closes a pipe's stream."""
    def __repr__(self) -> str:
        return "END"


END = _EndOfStream()


@dataclass(frozen=True)
class NormalizedPantry:
    """What p1 carries from Parse & Normalize to Match Recipes: the submitted pantry
    plus the rest of the run's input (restrictions, substitute decisions, date).

    Match attaches it to every record, so later filters read the run's input from
    the stream itself rather than from shared state. Read-only.
    """
    items: Mapping[str, PantryItem]                         # normalized, keyed by ingredient name
    restrictions: tuple[str, ...] = ()                      # the user's diets + allergies
    rejected_subs: frozenset[tuple[str, str]] = frozenset()  # (recipe_id, substitute name)
    today: date | None = None

    def __post_init__(self):
        object.__setattr__(self, "items", MappingProxyType(dict(self.items)))


@dataclass(frozen=True)
class UnrecognizedItem:
    row: object
    reason: str


@dataclass(frozen=True)
class Gap:
    """A recipe ingredient the pantry does not fully cover. Quantities are in base units."""
    name: str
    need_qty: float
    short_qty: float
    unit: str
    required: bool
    substitutable: bool


@dataclass
class RecipeRecord:
    """One recipe streaming through filters 2-10; each filter adds its results.

    Match also attaches two values that travel with the record. They are plain
    attributes, not dataclass fields, so results stay field-for-field comparable
    with Architecture B:
      run:   the NormalizedPantry this record was matched from
      needs: each recipe ingredient's quantity in base units, as (qty, unit),
             in the same order as recipe.ingredients (None if it can't convert)
    """
    run = None
    needs = None

    recipe: Recipe
    on_hand: list[str] = field(default_factory=list)
    missing: list[Gap] = field(default_factory=list)
    substitutions: dict[str, str] = field(default_factory=dict)   # missing item -> substitute
    to_buy: list[Gap] = field(default_factory=list)
    nutrition: Nutrition | None = None
    freshness_boost: float = 0.0
    preference_boost: float = 0.0
    score: float = 0.0
    shopping_list: list[str] = field(default_factory=list)
    trace: list[str] = field(default_factory=list)                # score breakdown (Traceability)

    def note(self, source: str, message: str) -> None:
        self.trace.append(f"[{source}] {message}")


@dataclass(frozen=True)
class ExclusionSummary:
    """Sent by the Dietary Filter just before END."""
    matched_count: int
    excluded: dict[str, tuple[str, ...]]    # recipe_id -> restrictions it broke


@dataclass
class PipelineResult:
    status: str                             # "ok" | "empty_pantry" | "no_matches" | "all_excluded"
    ranked: list[RecipeRecord] = field(default_factory=list)
    unrecognized: list[UnrecognizedItem] = field(default_factory=list)
    exclusions: ExclusionSummary | None = None
    elapsed_s: float = 0.0
    pantry: dict[str, PantryItem] = field(default_factory=dict)  # normalized input, for the combined list
