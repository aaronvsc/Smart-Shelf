"""B result contracts mirror A's UI fields, using the shared domain models."""
from dataclasses import dataclass, field

from smart_shelf.common.models import Nutrition, Recipe


@dataclass(frozen=True)
class UnrecognizedItem:
    row: object
    reason: str


@dataclass(frozen=True)
class Gap:
    name: str
    need_qty: float
    short_qty: float
    unit: str
    required: bool
    substitutable: bool


@dataclass
class RecipeRecord:
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
    matched_count: int
    excluded: dict[str, tuple[str, ...]]


@dataclass
class BlackboardResult:
    status: str
    ranked: list[RecipeRecord] = field(default_factory=list)
    unrecognized: list[UnrecognizedItem] = field(default_factory=list)
    exclusions: ExclusionSummary | None = None
    elapsed_s: float = 0.0
    combined_shopping_list: list[tuple[str, float, str]] = field(default_factory=list)
    activations: tuple[str, ...] = ()
