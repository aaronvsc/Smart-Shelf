# Architecture B: Blackboard

Implementation owner: Rahim Latreche. Scope follows sections 2.2, 3.3, and 4 of
the submitted Smart-Shelf proposal, Project Group 1.

This branch adds B alongside the existing implementation. It does not change
Architecture A, shared models, data access, JSON datasets, profiles, existing
tests, or the root README. Its base is `dev/architecture-A-development` at
`9b48ebf14440a0419ee968749e9070cb84481eee`, which already includes Aaron's shared
data work. The pull request targets that development branch so its diff contains
only B additions. Aaron can integrate it into the team's final branch.

## Run and test

Validated on Python 3.12.14, Linux x86_64. Python is available from
https://www.python.org/downloads/. Use a local virtual environment:

```sh
python -m venv .venv
# Linux/macOS:
source .venv/bin/activate
# Windows PowerShell instead:
# .venv\Scripts\Activate.ps1
python -m pip install pytest
python -m pytest -q
python scripts/check_data.py
python -m smart_shelf.arch_b --pantry docs/architecture_b/pantry_demo.json --today 2026-11-03
python scripts/compare_architectures.py
```

B has no third-party runtime dependencies. The CLI prints JSON and does not
write history. Use `--user ID` for an existing profile and `--data-dir PATH` for
another dataset directory. Missing or unreadable profiles stop execution.
Python source runs directly; no separate compilation is required. A syntax check
is available with `python -m compileall -q smart_shelf/arch_b`.

## Execution model

`Blackboard` stores named regions. Readers receive deep copies, preventing a
knowledge source from mutating another region without a publication event.
`publish()` writes related outputs together and invalidates all transitive
dependents. Unchanged writes produce no event. The controller subscribes to
events and reevaluates readiness after each source activation.

`KnowledgeSource.can_run()` requires valid inputs and invalid outputs. The
controller always chooses the first ready source in its fixed priority list.
Substitution and ranking also have a mandatory dietary barrier. Each source is
independent: it never calls another source. No work remains once all sources are
up to date. Duplicate producers, dependency cycles, missing publications, and an
activation limit prevent ambiguous scheduling and silent incomplete results.

| Priority | Component/class | Reads | Publishes |
|---|---|---|---|
| 1 | `InputNormalizer` | Raw pantry | Pantry, unrecognized rows |
| 2 | `RecipeMatcher` | Pantry | Candidate recipes |
| 3 | `DietaryChecker` | Candidates, profile | Per-recipe dietary status |
| 4 | `GapDetector` | Candidates, dietary status, pantry | On-hand ingredients and quantity gaps |
| 5 | `SubstituteFinder` | Gaps, pantry, profile, rejections, dietary status | Substitutions and remaining required purchases |
| 6 | `NutritionCalculator` | Substituted records | Nutrition totals and missing nutrition notices |
| 7 | `FreshnessScorer` | Substituted records, pantry, date | Freshness scores |
| 8 | `PreferenceWeighter` | Candidates, dietary status, profile, selection request | Preference scores, updated profile snapshot |
| 9 | `Ranker` | Substituted records, dietary status, nutrition, freshness, preferences | Ranked records and score explanations |
| 10 | `ShoppingListBuilder` | Rankings, selected IDs, pantry | Per-recipe lists and pooled selected-recipe list |

Recipes excluded by dietary rules remain in `candidates` and `dietary` for
explanation. They never enter gaps, substitution, or ranked recommendations.
An empty/unrecognized pantry stops after normalization. A valid pantry with no
matching recipes returns `no_matches`; matching recipes all excluded returns
`all_excluded` plus the per-recipe reasons.

## Interaction and UI integration

Keep one `BlackboardEngine` per user session. See [integration.md](integration.md)
for Aaron's integration contract. Initial recommendations and substitutions
follow A's policy: an eligible pantry substitute is provisionally included,
and rejection removes it. Accepting restores its eligibility. Decisions use
`(recipe_id, substitute_name)`, matching A's rejection contract. They do not
force a particular swap ahead of the existing substitution-table order.

A rejection invalidates substitution, nutrition, freshness, rankings, and
shopping. Matching, dietary status, gaps, and preferences remain valid. Freshness
must rerun too because the expiring ingredient used may have changed.

Explicit recipe selection activates `PreferenceWeighter`, `Ranker`, and
`ShoppingListBuilder`. History is saved through Aaron's existing data-access
function. A nonempty event ID identifies a click. Repeating a completed event
does not save twice or undo a later selection; a new cooking action requires a
new ID. Idempotency is limited to the lifetime of the in-memory engine, rather
than a durable cross-process guarantee. A failed write is retryable.

## Boundaries and team decisions

- B uses the common frozen domain models and reference-data helpers. It has no
  production imports from `arch_a`. The normalizer and policy constants were
  adapted from A into B-local modules to preserve the team's existing files and
  allow independent packaging. Parity tests catch drift. The team can later
  extract common pure rules in a separate coordinated change.
- For multiple selected recipes, B totals ingredient and substitute demand,
  then subtracts pantry stock once. This deliberately differs from A's current
  helper, which sums independently calculated shortages and may count the same
  inventory more than once. The behavior has dedicated quantity tests. No A
  code is changed. The team should agree on pooled accounting for the final UI.
- Reference data currently contains 25 curated recipes, not the proposal's
  approximate 200. The benchmark's 200-recipe workload repeats existing recipes
  with unique IDs and demonstrates scheduling/processing scale only. It does
  not close the data-content gap.
- The shared Streamlit UI remains Aaron's responsibility. This PR provides its
  backend contract and a working CLI demo; it does not claim a completed UI.
- Keep source ownership visible in Git and rehearse the B explanation/demo.
  Every team member must contribute and present, per Canvas.

## Final-deliverable handoff

The Canvas deadline for implementations, slides, and presentation/repository
links is November 17, 2026 at 11:59 p.m. Central. GitHub documents may be improved
until December 3, 2026 at 11:59 p.m. Central. Aaron is the designated submitter.

Before final submission the team still needs to integrate the UI, finish the
curated recipe dataset, select the final architecture based on evidence, create
the required `Selected` and `Unselected` packages, and produce the final Word
README and single PowerPoint. The repository must be public and follow the
instructor's group/last-name naming convention. The unlisted YouTube demo must
show both working architectures and remain accessible through final grading.

Use [architecture.md](architecture.md) for B diagrams and implementation
mapping, and [verification.md](verification.md) plus the reproducible benchmark
for comparison and graduate risk-analysis evidence. The proposal currently
prefers A. No architecture selection or repository rename is made by this PR.
