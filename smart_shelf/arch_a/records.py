"""Messages that flow through the pipes."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from smart_shelf.arch_a.inputs import Nutrition, PantryItem, Recipe, UserProfile


class _EndOfStream:
    """End marker that closes a pipe's stream."""
    def __repr__(self) -> str:
        return "END"


END = _EndOfStream()


@dataclass(frozen=True)
class RunContext:
    """Read-only input for one pipeline run, handed to every filter at setup."""
    pantry: dict[str, PantryItem]                       # normalized, keyed by ingredient name
    profile: UserProfile
    rejected_subs: frozenset[tuple[str, str]] = frozenset()   # (recipe_id, substitute name)
    today: date = field(default_factory=date.today)


@dataclass(frozen=True)
class NormalizedPantry:
    """What p1 carries from Parse & Normalize to Match Recipes."""
    items: dict[str, PantryItem]


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
    """One recipe streaming through filters 2-10; each filter adds its results."""
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
