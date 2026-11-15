# Verification and graduate risk-analysis evidence

Recorded November 3, 2026, against the development baseline
`9b48ebf14440a0419ee968749e9070cb84481eee` plus B additions.

## Regression and acceptance results

`python -m pytest -q`: **226 passed**, including all **145 original tests** and
81 new tests. A preexisting environment plugin emits a pytest deprecation
warning; no test failures occur. The CLI success and missing-profile failure
paths are exercised in subprocesses. The success test checks that the demo
profile's bytes remain unchanged.

| Requirement | Evidence |
|---|---|
| Independent source testability | All ten knowledge sources tested individually on preset blackboards |
| Dietary-first rule | Custom source priority deliberately puts substitution/ranking ahead of dietary; the controller's barrier still schedules dietary first |
| Fixed priority and termination | Repeated ready-source tie ordering; no-work reruns; cycle/duplicate producer detection; missing output and activation-limit tests |
| Reliability | Every restriction rule in the real data checked for violating recommended ingredients/substitutes; explicit exclusion, unsafe swap, and unknown restriction tests |
| Robustness | Aliases, plural forms, typo, unit conversion, duplicate rows, invalid dates/units, NaN/infinity, conversion/merge overflow, malformed rows |
| Quantity correctness | Hand-calculated partial gaps, substitution ratio, nutrition, optional ingredients, pooled stock and substitute demand |
| Consistency | Exact ordered domain results across ten runs; stable recipe-ID tie break inherited from matching policy |
| Incremental operation | Rejection runs only substitution, nutrition, freshness, ranking, shopping; earlier region versions remain unchanged; acceptance restores initial output |
| A/B comparison | Thirty real-data pantry/restriction combinations and one rejected-substitution scenario compare all domain fields, excluding architectural traces and elapsed times |
| User history | Explicit selection persistence, repeated-click deduplication, distinct clicks, failed-write retry, changed-profile stop, and no writes for invalid selections |
| Performance | Ten runs each on real 25-recipe data and synthetic 200-recipe data, with 50 pantry rows |

The current data checker passes with zero errors and seven preexisting unused
ingredient warnings. It reports 25 recipes, 68 ingredients, and 15 restriction
rules. No original tracked file was modified in this change.

## Timing evidence

Measured on Python 3.12.14, Linux x86_64. Raw values and platform details are in
[benchmark_results.json](benchmark_results.json). Reproduce with
`python scripts/compare_architectures.py`. Analysis date is fixed to 2026-11-03;
timings vary by machine and load.

| Workload, ten runs | A median | A maximum | B median | B maximum |
|---|---:|---:|---:|---:|
| Real 25 recipes, 50 pantry items | 4.314 ms | 8.763 ms | 26.598 ms | 39.678 ms |
| Synthetic 200 recipes, 50 pantry items | 15.213 ms | 31.677 ms | 122.822 ms | 161.761 ms |

For the R001/olive-oil rejection scenario, A's full rerun median was 5.686 ms;
B's incremental update median was 15.948 ms. B ran five sources rather than
all ten. B's snapshot-copy overhead outweighed the avoided work in this small
dataset. This is evidence for simpler A as the current preferred implementation,
not evidence that blackboard is always faster.

The 200-recipe workload duplicates the 25 existing recipes with unique IDs. It
tests scale and repeatability but does not represent 200 separately curated
recipes. Performance excludes browser rendering and user/network time. The
numbers do not establish production food/allergen safety or user authentication.

## Architecture-specific risks and mitigations

| Risk | B mitigation and evidence | A comparison |
|---|---|---|
| Ranking/substitution before dietary validation | Mandatory controller barrier plus explicit dietary dependencies and allowed-status checks; adversarial priority test | Fixed early dietary filter gives simpler ordering evidence |
| Stale results after a user decision | Transitive invalidation removes affected regions; snapshots isolate writes; freshness/nutrition/rank/shopping rerun tests | Full rerun avoids incremental invalidation complexity |
| Nontermination or ambiguous scheduling | Acyclic dependency validation, unique producers, fixed priority, output checks, bounded activations | End markers, thread join and error handling are already covered by A's tests |
| Shared state accidentally mutated | Deep-copy reads and writes; snapshot-isolation test | Recipe records intentionally mutate as they move downstream |
| Performance overhead | Measured 200-recipe/50-item maximum 161.761 ms; within 2 s here, but copying is measurable | A's measured maximum was lower for this workload |
| Repeated history writes | Explicit event IDs and in-memory completion cache; repeated-click and failed-write tests | A's UI must independently guard its save call |
| Profile restriction changes | Default selection writer checks persisted restrictions before writing and refuses an outdated analysis | Both UIs must reload profiles and stop on load failures |
| Shared stock allocated to multiple recipes | B aggregates selected-recipe demand and subtracts stock once; ingredient/substitute shortage tests | Existing A helper sums independent shortages; team review needed |
| Policy drift between architectures | Acceptance comparisons, explicit B-local policy modules and normalization provenance | Future shared-rule extraction requires a coordinated team change |

Residual risks: event deduplication is not durable across process restarts;
profile read/append/write is not a multi-process transaction; profile file
separation is not authentication; missing nutrition yields partial totals with
a trace notice; dietary safety depends on complete and correct ingredient tags
and restriction rules. These are project-level boundaries, not silently solved
by either architecture.

## Suggested presentation sequence for Rahim

1. Explain the blackboard regions, controller priority, and dietary barrier with
   the component view, class view, and mapping table.
2. Run the demo pantry; show ranked recipes, gap quantities, nutrition, and trace.
3. Reject a suggested swap; show the five activated sources and unchanged earlier
   region versions, then restore eligibility.
4. Show a declared restriction excluding unsafe recipes while preserving reasons.
5. Use a temporary test profile to select multiple recipes, show the pooled list,
   and demonstrate that retrying the click does not duplicate history.
6. Present measured A/B timing and risks. Explain why the current evidence still
   supports the proposal's preference for A, while B demonstrates incremental
   state reuse.

The team should rerun this evidence after UI integration, data expansion, or
changes to either architecture. Use the diagrams and evidence in the final
graduate risk-analysis slides and Word README. This document is supporting
material, not a claim that the full team's final submission is complete.
