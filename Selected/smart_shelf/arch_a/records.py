"""Messages carried by the pipes."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from types import MappingProxyType
from typing import Mapping

from smart_shelf.common.models import Nutrition, PantryItem, Recipe


class _EndOfStream:
    def __repr__(self) -> str:
        return "END"


END = _EndOfStream()


@dataclass(frozen=True)
class NormalizedPantry:
    """On p1, Normalize -> Match: the pantry and the run's input. Read-only."""
    items: Mapping[str, PantryItem]
    restrictions: tuple[str, ...] = ()
    rejected_subs: frozenset[tuple[str, str]] = frozenset()
    today: date | None = None

    def __post_init__(self):
        object.__setattr__(self, "items", MappingProxyType(dict(self.items)))


@dataclass(frozen=True)
class UnrecognizedItem:
    row: object
    reason: str


@dataclass(frozen=True)
class Gap:
    """A recipe ingredient the pantry does not fully cover (base units)."""
    name: str
    need_qty: float
    short_qty: float
    unit: str
    required: bool
    substitutable: bool


@dataclass
class RecipeRecord:
    """On p2-p10: one recipe; each filter adds its results.

    run and needs (set by Match, not dataclass fields): the NormalizedPantry, and
    each ingredient's (qty, base unit) in recipe order.
    """
    run = None
    needs = None

    recipe: Recipe
    on_hand: list[str] = field(default_factory=list)
    missing: list[Gap] = field(default_factory=list)
    substitutions: dict[str, str] = field(default_factory=dict)
    to_buy: list[Gap] = field(default_factory=list)
    nutrition: Nutrition | None = None
    freshness_boost: float = 0.0
    preference_boost: float = 0.0
    score: float = 0.0
    shopping_list: list[str] = field(default_factory=list)
    trace: list[str] = field(default_factory=list)

    def note(self, source: str, message: str) -> None:
        self.trace.append(f"[{source}] {message}")


@dataclass(frozen=True)
class ExclusionSummary:
    """Sent by the Dietary Filter before END: recipes matched and excluded."""
    matched_count: int
    excluded: dict[str, tuple[str, ...]]


@dataclass
class PipelineResult:
    """Pipeline.run() output. status: ok, empty_pantry, no_matches or all_excluded."""
    status: str
    ranked: list[RecipeRecord] = field(default_factory=list)
    unrecognized: list[UnrecognizedItem] = field(default_factory=list)
    exclusions: ExclusionSummary | None = None
    elapsed_s: float = 0.0
    pantry: dict[str, PantryItem] = field(default_factory=dict)
