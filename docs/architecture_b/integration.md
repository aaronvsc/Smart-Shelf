# Integration contract for the shared UI

Aaron retains ownership of the Streamlit UI. These are backend usage examples,
not changes to his files. B is independently importable through:

```python
from smart_shelf.arch_b import BlackboardEngine
from smart_shelf.common.data_access import load_profile, load_reference_data

reference = load_reference_data()
profile = load_profile("demo")  # stop and display an error if this fails
engine = BlackboardEngine(reference)
result = engine.run(
    [{"name": "rice", "qty": 400, "unit": "g"}], profile
)
```

Store `engine` and the latest `result` in `st.session_state`. Create a separate
engine when the user changes; clear any previous user's results. Call `run()`
only for a new pantry/profile analysis. Calling it on every Streamlit rerender
would discard incremental blackboard state. Reload the persisted profile before
each new analysis, and rerun if its restrictions change.

Handle errors before displaying results, including data/profile errors and
controller errors. Do not keep displaying a previously successful result after
a failed analysis. A history-write failure leaves downstream regions invalid;
retry the same selection event after resolving the error, or start a new analysis.

## Result fields

| Field | UI meaning |
|---|---|
| `status` | `ok`, `empty_pantry`, `no_matches`, or `all_excluded` |
| `ranked` | List of records with the same field names as A's records |
| `unrecognized` | Original bad rows and explanatory reasons |
| `exclusions` | Matched count and recipe-to-restriction reasons; `None` for empty pantry |
| `elapsed_s` | Elapsed analysis/update time in seconds |
| `combined_shopping_list` | Selected recipes' pooled shortages as `(name, qty, unit)` tuples |
| `activations` | Source names activated during this call, useful for the demo |

Each record provides `recipe`, `on_hand`, `missing`, `substitutions`, `to_buy`,
`nutrition`, `freshness_boost`, `preference_boost`, `score`, `shopping_list`, and
`trace`. A gap includes required/optional status and quantities in base units.
Display quantities from `to_buy`; `shopping_list` itself is a list of names.
Missing nutrition values are disclosed in the trace; totals may be incomplete.

## Substitute decisions

```python
result = engine.decide_substitute(recipe_id, substitute_name, accepted=False)
# Accept again, restoring eligibility:
result = engine.decide_substitute(recipe_id, substitute_name, accepted=True)
```

Initial eligible substitutions are included provisionally, as in A. Rejecting a
swap can choose another safe available substitute or move the missing ingredient
to the purchase list. Repeating an unchanged decision performs no source work.
The same substitute name used in two gaps of a recipe shares one rejection key,
matching A's existing `(recipe_id, substitute_name)` convention.

## Recipe selection and persistence

```python
from uuid import uuid4

# Generate once inside the explicit selection button's click handler.
click_id = str(uuid4())
result = engine.select(selected_recipe_ids, event_id=click_id)
# A retry/rerender of that click must reuse click_id.
```

Do not call `save_selection()` a second time from the B UI path: the Preference
Weighter does it. A's existing UI path still owns its own save operation. Use a
new ID for a genuinely new selection. Reuse the same engine and event ID for a
retry; creating a new engine loses in-memory deduplication. Shared profile files
provide logical per-user separation, not authentication or concurrent-session
transaction guarantees. Do not expose arbitrary user IDs as authenticated access.

B's combined list accounts for one shared pantry across all selected recipes,
including substitute quantities. Review this with the team before reusing A's
current `combine_shopping_lists()` helper for the shared UI, since that helper
adds independently calculated shortages. No such helper is changed in this PR.
