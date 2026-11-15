# Smart-Shelf

Smart-Shelf is a recipe recommender for CS 7319 Software Architecture (Group 1).
You enter what's in your pantry, and it ranks recipes you can make, respects your
diet and allergies, suggests substitutes you already have, and builds one combined
shopping list for the recipes you pick.

We built the same system twice, in two architecture styles:

| Folder | Architecture | Status |
|---|---|---|
| [`Selected/`](Selected/) | **A: Pipe-and-Filter** | our final choice |
| [`Unselected/`](Unselected/) | **B: Blackboard** | the alternative we compared it against |

Each folder is complete on its own: source code, compiled code, data, tests and
one-click launchers. The comparison of the two architectures and why we chose A
are in [Architecture comparison and rationale](#architecture-comparison-and-rationale)
at the end of this Readme.

## Team

| Member | Role |
|---|---|
| Aaron Santa Cruz (@aaronvsc) | Project lead; shared data layer, Streamlit UI, integration, release folders |
| Georgiana Liu (@georgiana0818) | Architecture A: Pipe-and-Filter |
| Rahim Latreche (@rahimcantcode) | Architecture B: Blackboard |

## Quick start

1. Install **Python 3.12 or newer** (see [Platform](#platform) below).
2. Open `Selected/` (or `Unselected/`) and start the launcher for your system:

   | System | Launcher |
   |---|---|
   | macOS | double-click `run_mac.command` (the first time: right-click > Open) |
   | Linux | `./run_linux.sh` |
   | Windows | double-click `run_windows.bat` |

3. The first run sets up a private Python environment and installs the packages
   (about a minute, needs internet). Then the app opens at http://localhost:8501.

To stop the app, press Ctrl+C in the terminal window (or close it on Windows).

## Platform

| Item | Version | Where to get it |
|---|---|---|
| Python | 3.12 or newer (we developed on 3.12.15, macOS Apple Silicon; B was also checked on 3.12.14, Linux x86_64) | https://www.python.org/downloads/ |
| Streamlit (web UI) | 1.65.0 | installed automatically from `requirements.txt` |
| pytest (tests) | 9.2.0 | installed automatically from `requirements.txt` |

**Installing Python**

- **Windows / macOS:** download the 3.12 (or newer) installer from python.org and
  run it. On Windows, tick **"Add python.exe to PATH"** on the first screen.
- **Linux:** use your package manager (for example `sudo apt install python3.12 python3.12-venv`)
  or the python.org source release.
- Check it worked: `python3 --version` (Windows: `py --version`) should print 3.12 or higher.

**Configuring:** nothing else to set up. The launchers create a virtual environment
(`.venv`) inside the folder and install the two packages there, so nothing is
installed system-wide. The app's look is configured in `.streamlit/config.toml`.

## How to run (by hand)

If you prefer not to use the launchers, from inside `Selected/` or `Unselected/`:

```sh
# macOS / Linux
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m streamlit run smart_shelf/ui/app.py
```

```bat
:: Windows
py -3 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m streamlit run smart_shelf\ui\app.py
```

Architecture B also has a command-line demo (from `Unselected/`):

```sh
.venv/bin/python -m smart_shelf.arch_b --pantry data/sample_pantry.json
```

**Using the app:** the five steps follow section 1.4.1 of our proposal.

1. **Enter pantry**: add ingredients with the search bar (it only accepts ingredients
   in our data), set amounts and optional expiry dates, and check your diet and allergies.
2. **Finding recipes**: the chosen architecture analyzes the pantry.
3. **Results**: ranked recipes with a match score and a plain-language "Why it's
   ranked" explanation. Check the ones you want (the top 10 start checked).
4. **Review substitutes**: accept or reject each suggested swap; rankings update.
5. **Shopping list**: set how many times you'll make each recipe, save your picks to
   your history, and download one combined shopping list.

Profile changes are saved to `data/user_profiles/`, a working copy of the sample
profile. Delete that folder to start again from the clean sample.

## How to compile

The professor asked for compiled code, so each folder also contains `compiled/`: every source file compiled to Python 3.12 bytecode (`.pyc`), in the same folder layout as `smart_shelf/`.

To compile it yourself, from inside `Selected/` or `Unselected/`:

```sh
.venv/bin/python -m compileall smart_shelf
```

This writes the bytecode into `__pycache__/` folders next to each source file (that's
where Python looks for it when running). `compiled/` holds the same bytecode, laid out
separately by `scripts/build_release.py` so it's easy to find in the repository.

## How to test

From inside `Selected/` or `Unselected/` (after the setup above):

```sh
.venv/bin/python -m pytest
.venv/bin/python scripts/check_data.py
```

The first runs the automated tests for that architecture, the shared code and the
UI (about 216 tests in `Selected/`, 151 in `Unselected/`). The few tests that
compare A with B directly are skipped there, with a message saying so; they run in
the full repository below. The second checks the data files for problems.

## Repository layout

```
Selected/               Architecture A, ready to run (generated, see below)
Unselected/             Architecture B, ready to run (generated, see below)
smart_shelf/            our working source code, both architectures together
  common/                 shared data models and data access (used by A and B)
  arch_a/                 Architecture A: pipe-and-filter
  arch_b/                 Architecture B: blackboard
  ui/                     Streamlit app shared by both architectures
data/                   ingredients, recipes, substitutions/nutrition, sample profile and pantry
tests/                  every test, including A-vs-B comparisons
scripts/                data check, A-vs-B comparison, release build
```

`Selected/` and `Unselected/` are built from the working code by
`scripts/build_release.py`. Each gets the shared code, the UI and only its own
architecture, so in those folders the app shows no architecture switch. In the
working repository the sidebar has an **A/B switch**, which we use to compare the
two on the same pantry.

To work on the full repository (both architectures):

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pytest                          # every test, both architectures
.venv/bin/python -m streamlit run smart_shelf/ui/app.py
.venv/bin/python scripts/compare_architectures.py   # A-vs-B comparison numbers
.venv/bin/python scripts/build_release.py           # rebuild Selected/ and Unselected/
```

After any code change, rerun the build and commit `Selected/` and `Unselected/` again.

## Architecture comparison and rationale

### Differences between the two designs

Both designs normalize pantry input, find eligible recipes, score and rank them,
review substitution decisions, and build a combined shopping list when the user
selects recipes. Both apply dietary and allergy rules before suggesting swaps or
ranking recommendations, and record history after an explicit selection.

| Concern | A: Pipe-and-Filter | B: Blackboard |
| --- | --- | --- |
| Data flow | Queue-backed pipes pass run input and recipe records between filters. | Knowledge sources read and publish named regions through a shared blackboard. Reads and publications copy snapshots. |
| Control | A fixed filter sequence makes dietary screening an early stage. Worker completion, end markers and timeouts govern each run. | The controller selects ready knowledge sources in a fixed priority order. A dietary barrier gates substitution and ranking. Dependency checks reject cycles and duplicate producers. |
| Dietary exclusions | The dietary filter removes disallowed recipes from the stream and emits an exclusion summary. | The board retains candidate recipes and their dietary decisions. Later sources exclude those candidates from recommendations. |
| Swap decision | The UI adapter runs the pipeline again with the revised rejected-substitute set. | Publishing the revised set invalidates dependent regions. Normalized pantry, matches and dietary decisions stay available. |

### Why we selected Architecture A

A's fixed order makes it easier to inspect when dietary screening runs and
which stages affect a recommendation. Each swap starts a fresh run, so A
has fewer state-invalidation rules to maintain. Its threaded filters still
require explicit completion and error handling. B offers independently testable
knowledge sources and incremental updates, with additional scheduling and
snapshot-management costs.

On the release baseline `879184a`, `python scripts/compare_architectures.py`
produced matching ordered recommendation outputs in ten repeats with the
checked-in 200 recipes and 50 pantry items. On macOS 13.7.8 (Intel, Python
3.11.0), median engine time was 41.305 ms for A and 571.528 ms for B.
Rejecting olive oil for R047 activated five B sources, with a 355.093 ms
median versus 37.499 ms for A's full rerun. B copies region snapshots, which
adds work even when early results are reused. These measurements cover engine
execution on one machine. They exclude browser rendering and use a fixed
analysis date. Run the script on the supported Python 3.12 environment to
reproduce the comparison on your machine.

### Differences between the two implementations

- A's `Pipeline` wires `Pipe` queues to the `Filter` implementations in
  `smart_shelf/arch_a/filters/`. `NormalizeFilter` receives the pantry directly.
  The remaining filters run as workers and pass records and end markers down
  the pipeline. The A adapter handles recipe selection and persists history.
- B's `BlackboardEngine` owns a `Blackboard` and a `Controller`. The controller
  derives dependencies from the ten `KnowledgeSource` implementations in
  `smart_shelf/arch_b/knowledge_sources.py`. The board publishes change events and
  discards invalid dependent regions. The engine uses per-session selection
  event IDs to deduplicate history writes.
- Both reuse the reference data, domain models, and profile storage in
  `smart_shelf/common/` and the Streamlit workflow in `smart_shelf/ui/`.
  `PipeAndFilterBackend` and `BlackboardBackend` translate the same UI actions
  into architecture-specific calls. Queue and blackboard connectors belong to
  their respective architectures.

### Changes from the proposal

The two candidate styles were retained. The final B implementation uses a
validated dependency graph and fixed-priority scheduling to keep repeated runs
deterministic. Swap feedback reuses valid regions, while explicit selection
events keep profile writes tied to the user's action. The shared interaction
changes below apply to both implementations.

Changes to the shared data layer and UI during implementation (Aaron):

- The combined shopping list counts the pantry once across all chosen recipes, in
  both architectures, so two recipes can't both use the same cup of rice.
- Users choose recipes on Step 3; only those go on to substitutes and the shopping
  list, which keeps Step 4 to the swaps that matter.
- Step 5 lets you make a recipe several times; the shopping list scales, and your
  history still records each recipe once.
- Ingredients are entered through a search bar limited to our ingredient list, with a
  live pantry check, so problems show up on Step 1 instead of on the results.
- The app saves profile changes to a working copy, so the sample profile in the
  repository never changes.
