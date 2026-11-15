"""Tunable rules the team has not settled yet. Change them here, not in the filters."""

# Match: a recipe is "partially makeable" when at least this many required
# ingredients are in the pantry (any quantity).
MATCH_MIN_REQUIRED_ON_HAND = 1

# Normalize: similarity (0-1) needed to accept a typo as a known ingredient.
TYPO_CUTOFF = 0.8

# Rank: credit per required ingredient (on hand = 1.0, to buy = 0.0).
SUBSTITUTE_CREDIT = 0.5

# Freshness: items expiring within this many days (inclusive) boost a recipe.
FRESHNESS_WINDOW_DAYS = 3
FRESHNESS_WEIGHT_PER_ITEM = 0.02
FRESHNESS_MAX_BOOST = 0.05

# Preference: boost per past selection of the same recipe / same cuisine.
PREFERENCE_RECIPE_WEIGHT = 0.02
PREFERENCE_CUISINE_WEIGHT = 0.005
PREFERENCE_MAX_BOOST = 0.05

# Float tolerance for quantity comparisons.
EPSILON = 1e-9
