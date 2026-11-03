"""Ten independently scheduled knowledge sources from proposal section 2.2."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date
from typing import Callable

from smart_shelf.common.models import Nutrition, ReferenceData, UserProfile

from . import config
from .controller import KnowledgeSource
from .models import Gap, RecipeRecord
from .normalization import normalize


@dataclass(frozen=True)
class SelectionRequest:
    event_id: str
    recipe_ids: tuple[str, ...]
    on: date


class ReferenceSource(KnowledgeSource):
    def __init__(self, ref: ReferenceData):
        self.ref = ref


class InputNormalizer(ReferenceSource):
    inputs = ("raw_pantry",)
    outputs = ("pantry", "unrecognized")

    def run(self, board):
        pantry, errors = normalize(board.read("raw_pantry"), self.ref)
        board.publish(pantry=pantry, unrecognized=errors)


class RecipeMatcher(ReferenceSource):
    inputs = ("pantry",)
    outputs = ("candidates",)

    def can_run(self, board):
        return super().can_run(board) and bool(board.read("pantry"))

    def run(self, board):
        pantry = board.read("pantry")
        candidates = []
        for recipe in sorted(self.ref.recipes, key=lambda item: item.id):
            required = [item.name for item in recipe.ingredients if item.required]
            if required and sum(name in pantry for name in required) >= config.MATCH_MIN_REQUIRED_ON_HAND:
                candidates.append(recipe)
        board.publish(candidates=candidates)


class DietaryChecker(ReferenceSource):
    inputs = ("candidates", "profile")
    outputs = ("dietary",)

    def run(self, board):
        profile = board.read("profile")
        self.ref.check_restrictions(profile)
        status = {}
        for recipe in board.read("candidates"):
            broken = dict.fromkeys(reason for item in recipe.ingredients
                                   for reason in self.ref.violations(item.name, profile))
            status[recipe.id] = tuple(broken)
        board.publish(dietary=status)


class GapDetector(ReferenceSource):
    inputs = ("candidates", "dietary", "pantry")
    outputs = ("gaps",)

    def run(self, board):
        pantry, dietary = board.read("pantry"), board.read("dietary")
        records = []
        for recipe in board.read("candidates"):
            if dietary[recipe.id]:
                continue
            record = RecipeRecord(recipe)
            required = [item for item in recipe.ingredients if item.required]
            record.note("RecipeMatcher", f"{sum(item.name in pantry for item in required)}/"
                        f"{len(required)} required ingredients in pantry")
            record.note("DietaryChecker", "allowed")
            for item in recipe.ingredients:
                need = self.ref.to_base(item.name, item.qty, item.unit)
                if need is None:
                    raise ValueError(f"{recipe.id}: cannot convert {item.name!r}")
                have = pantry[item.name].qty if item.name in pantry else 0.0
                if have + config.EPSILON >= need:
                    record.on_hand.append(item.name)
                else:
                    gap = Gap(item.name, need, need - have,
                              self.ref.ingredients[item.name].base_unit,
                              item.required, item.substitutable)
                    record.missing.append(gap)
                    record.note(self.name, f"{'required' if item.required else 'optional'} "
                                f"{item.name}: short {gap.short_qty:g} {gap.unit}")
            records.append(record)
        board.publish(gaps=records)


class SubstituteFinder(ReferenceSource):
    inputs = ("gaps", "pantry", "profile", "rejected_subs", "dietary")
    outputs = ("substituted",)
    requires_dietary = True

    def run(self, board):
        pantry, profile = board.read("pantry"), board.read("profile")
        rejected, dietary = board.read("rejected_subs"), board.read("dietary")
        records = board.read("gaps")
        for record in records:
            if dietary.get(record.recipe.id, ("unchecked",)):
                raise ValueError("Substitution requires an explicitly allowed recipe")
            remaining = {name: item.qty for name, item in pantry.items()}
            for item in record.recipe.ingredients:
                if item.name in remaining:
                    need = self.ref.to_base(item.name, item.qty, item.unit)
                    remaining[item.name] = max(0.0, remaining[item.name] - need)
            for gap in record.missing:
                if not gap.required:
                    continue
                options = self.ref.substitutes.get(gap.name, ()) if gap.substitutable else ()
                chosen = next((sub for sub in options
                               if (record.recipe.id, sub.name) not in rejected
                               and sub.name in self.ref.ingredients
                               and not self.ref.violations(sub.name, profile)
                               and remaining.get(sub.name, 0) + config.EPSILON >= gap.short_qty * sub.ratio), None)
                if chosen is None:
                    record.to_buy.append(gap)
                else:
                    used = gap.short_qty * chosen.ratio
                    remaining[chosen.name] -= used
                    record.substitutions[gap.name] = chosen.name
                    record.note(self.name, f"{chosen.name} ({used:g} "
                                f"{self.ref.ingredients[chosen.name].base_unit}) covers {gap.name}")
        board.publish(substituted=records)


class NutritionCalculator(ReferenceSource):
    inputs = ("substituted",)
    outputs = ("nutrition",)

    def run(self, board):
        result = {}
        for record in board.read("substituted"):
            gaps = {gap.name: gap for gap in record.missing}
            total, missing = Nutrition(), []
            for item in record.recipe.ingredients:
                gap = gaps.get(item.name)
                if gap is not None and not gap.required:
                    continue
                need = self.ref.to_base(item.name, item.qty, item.unit)
                portions = [(item.name, need)]
                if item.name in record.substitutions:
                    name = record.substitutions[item.name]
                    sub = next(sub for sub in self.ref.substitutes[item.name] if sub.name == name)
                    portions = [(item.name, need - gap.short_qty), (name, gap.short_qty * sub.ratio)]
                for name, qty in portions:
                    if qty <= 0:
                        continue
                    nutrition = self.ref.nutrition_of(name, qty)
                    if nutrition is None:
                        missing.append(name)
                    else:
                        total = total + nutrition
            result[record.recipe.id] = (total, tuple(missing))
        board.publish(nutrition=result)


class FreshnessScorer(ReferenceSource):
    inputs = ("substituted", "pantry", "today")
    outputs = ("freshness",)

    def run(self, board):
        pantry, today = board.read("pantry"), board.read("today")
        result = {}
        for record in board.read("substituted"):
            names = [item.name for item in record.recipe.ingredients] + list(record.substitutions.values())
            boost = 0.0
            for name in dict.fromkeys(names):
                item = pantry.get(name)
                if item is not None and item.expires is not None:
                    days = (item.expires - today).days
                    if 0 <= days <= config.FRESHNESS_WINDOW_DAYS:
                        boost += config.FRESHNESS_WEIGHT_PER_ITEM * (
                            config.FRESHNESS_WINDOW_DAYS + 1 - days) / (config.FRESHNESS_WINDOW_DAYS + 1)
            result[record.recipe.id] = min(boost, config.FRESHNESS_MAX_BOOST)
        board.publish(freshness=result)


class PreferenceWeighter(ReferenceSource):
    inputs = ("candidates", "dietary", "profile", "selection_request")
    outputs = ("preferences", "effective_profile")

    def __init__(self, ref, save_selection: Callable[[UserProfile, SelectionRequest], UserProfile]):
        super().__init__(ref)
        self.save_selection = save_selection

    def run(self, board):
        profile, request = board.read("profile"), board.read("selection_request")
        if request is not None:
            profile = self.save_selection(profile, request)
        recipes = Counter(entry.recipe_id for entry in profile.history)
        cuisine_of = {recipe.id: recipe.cuisine for recipe in self.ref.recipes}
        cuisines = Counter(cuisine_of[entry.recipe_id] for entry in profile.history
                           if entry.recipe_id in cuisine_of)
        dietary = board.read("dietary")
        scores = {recipe.id: min(config.PREFERENCE_MAX_BOOST,
                                config.PREFERENCE_RECIPE_WEIGHT * recipes[recipe.id]
                                + config.PREFERENCE_CUISINE_WEIGHT * cuisines[recipe.cuisine])
                  for recipe in board.read("candidates") if not dietary[recipe.id]}
        board.publish(preferences=scores, effective_profile=profile)


class Ranker(ReferenceSource):
    inputs = ("substituted", "dietary", "nutrition", "freshness", "preferences")
    outputs = ("rankings",)
    requires_dietary = True

    def run(self, board):
        records = board.read("substituted")
        dietary, nutrition = board.read("dietary"), board.read("nutrition")
        freshness, preferences = board.read("freshness"), board.read("preferences")
        for record in records:
            if dietary.get(record.recipe.id, ("unchecked",)):
                raise ValueError("Ranking requires an explicitly allowed recipe")
            record.nutrition, missing = nutrition[record.recipe.id]
            record.freshness_boost = freshness[record.recipe.id]
            record.preference_boost = preferences[record.recipe.id]
            required = [item.name for item in record.recipe.ingredients if item.required]
            direct = sum(name in record.on_hand for name in required)
            substituted = sum(name in record.substitutions for name in required)
            closeness = (direct + config.SUBSTITUTE_CREDIT * substituted) / len(required)
            record.score = closeness + record.freshness_boost + record.preference_boost
            record.note("NutritionCalculator", f"{record.nutrition.kcal:.0f} kcal"
                        + ("; no nutrition data for " + ", ".join(missing) if missing else ""))
            record.note(self.name, f"score {record.score:.3f} = closeness {closeness:.3f} "
                        f"({direct} on hand, {substituted} substituted, {len(record.to_buy)} to buy) "
                        f"+ freshness {record.freshness_boost:.3f} "
                        f"+ preference {record.preference_boost:.3f}")
        records.sort(key=lambda record: (-round(record.score, 9), len(record.to_buy), record.recipe.id))
        board.publish(rankings=records)


class ShoppingListBuilder(ReferenceSource):
    inputs = ("rankings", "selected_ids", "pantry")
    outputs = ("shopping", "combined_shopping")

    def run(self, board):
        records = board.read("rankings")
        selected, pantry = set(board.read("selected_ids")), board.read("pantry")
        demand: Counter[str] = Counter()
        for record in records:
            record.shopping_list = [gap.name for gap in record.to_buy]
            if record.shopping_list:
                record.note(self.name, "buy " + ", ".join(record.shopping_list))
            if record.recipe.id not in selected:
                continue
            gaps = {gap.name: gap for gap in record.missing}
            for item in record.recipe.ingredients:
                gap = gaps.get(item.name)
                if gap is not None and not gap.required:
                    continue
                need = self.ref.to_base(item.name, item.qty, item.unit)
                if item.name in record.substitutions:
                    name = record.substitutions[item.name]
                    sub = next(sub for sub in self.ref.substitutes[item.name] if sub.name == name)
                    demand[item.name] += need - gap.short_qty
                    demand[name] += gap.short_qty * sub.ratio
                else:
                    demand[item.name] += need
        combined = []
        for name, qty in sorted(demand.items()):
            short = qty - (pantry[name].qty if name in pantry else 0.0)
            if short > config.EPSILON:
                combined.append((name, short, self.ref.ingredients[name].base_unit))
        board.publish(shopping=records, combined_shopping=combined)


def default_sources(ref, save_selection):
    return (InputNormalizer(ref), RecipeMatcher(ref), DietaryChecker(ref),
            GapDetector(ref), SubstituteFinder(ref), NutritionCalculator(ref),
            FreshnessScorer(ref), PreferenceWeighter(ref, save_selection),
            Ranker(ref), ShoppingListBuilder(ref))
