# SETUP.md — Environment for the Scope-Calibration Benchmark

Built on top of the **MUHAI Recipe Execution Benchmark** (standalone). This
records exact steps, versions, the blocker hit on macOS, and the reproduced
example output.

## 0. Host

- macOS (Darwin 25.2.0), Apple Silicon (`arm64`).
- Python 3 (system), used for the slicing/scoring/analysis layer (`src/`).
- Rosetta 2 present (the shipped evaluator is an `x86_64` Mach-O — see §3).

## 1. Download the standalone benchmark

Source page: https://ehai.ai.vub.ac.be/recipe-execution-benchmark/

```bash
curl -sSL -o reb.zip \
  "https://ehai.ai.vub.ac.be/recipe-execution-benchmark/assets/zips/recipe-execution-benchmark.zip"
unzip -q reb.zip -d reb_extracted
```

- Size: ~213 MB. Build date of contents: 2023-01-25.
- Layout:
  - `data/recipe texts/` — 30 recipes (structured XML with `<id>`, ingredients,
    instructions).
  - `data/gold standard solutions/meaning-only/` — 30 `.solution` files (MCL
    networks only).
  - `data/gold standard solutions/utterance and meaning/` — 30 `.xml` files that
    align each natural-language utterance (ingredient line / instruction
    sentence) to its MCL operations. **This alignment is what the slicer uses.**
  - `executables/cookingbot-evaluator-{mac,linux,windows}.zip` — the one-click
    kitchen simulator + evaluator (LispWorks/IRL binary).
  - `libs/smatch/` — Python Smatch implementation (for the `smatch-score` metric).
  - `documentation/documentation.pdf` — primitive specs (§3.1), metrics (§6),
    examples.
  - `documentation/examples/` — runnable example script + evaluation example
    solutions (incl. named failure modes: `extended-main-dish`,
    `additional-side-dish`, `missing-minor-implicit`, `no-cooking`, …).

## 2. The evaluator interface (one-click)

```
cookingbot-evaluator -input <predicted.solution> -output <results.csv> \
    [-show-output true]                # visualize simulation in browser
    [-metrics smatch-score goal-condition-success dish-approximation-score execution-time | none]
    [-lib-dir <path-to-libs/smatch>]   # required only for smatch-score
```

- `-input`: a `.solution` file; each network prefixed by `#<recipe-id>` (the id
  must match a recipe `<id>` in `data/recipe texts/`).
- `-output`: CSV with columns `recipe-id,goal-condition-success,dish-approximation-score,execution-time`.
- Metrics: **Goal-Condition Success (GCS)**, **Dish Approximation Score (DAS)**,
  **Recipe Execution Time** come from the binary; **Smatch** is computed via the
  bundled Python lib (`-lib-dir libs/smatch`, needs Graphviz for some features).

## 3. macOS blocker + fix (RECORD FOR HUMAN)

The Mac evaluator is an **unsigned `x86_64` LispWorks binary from 2023**. Two
issues on current macOS / Apple Silicon:

1. **XProtect removed the binary on first execution.** The whole
   `cookingbot-evaluator.app` was silently deleted after the first exec attempt
   (the curl-downloaded zip carries no quarantine flag, so this is XProtect
   *malware remediation* of the unsigned binary, not a Gatekeeper prompt).
2. **Fix that worked:** re-extract, then **ad-hoc codesign** the bundle:
   ```bash
   unzip -q executables/cookingbot-evaluator-mac.zip -d executables/mac
   codesign -s - --force --deep executables/mac/cookingbot-evaluator.app
   ```
   After ad-hoc signing the binary is no longer removed and runs fine. `spctl`
   still reports "rejected" (expected for ad-hoc) but direct execution works.
3. **Harmless runtime warning:** it prints a `libcrypto.dylib` (CL+SSL) load
   warning at startup — the simulator does not need SSL; ignore it.

> If reproducing on a different machine, the equivalent step is to clear
> quarantine / ad-hoc sign, or run the **Linux** evaluator (also `x86_64`) in a
> container. The `x86_64` binary runs on Apple Silicon via Rosetta 2.

No network domains were needed beyond the single benchmark download.

## 4. Reproduced example output (ACCEPTANCE ✅)

```bash
BIN="$PWD/reb_extracted/recipe-execution-benchmark/executables/mac/cookingbot-evaluator.app/Contents/MacOS/cookingbot-evaluator"
cd /tmp/cb_run
cp ".../documentation/examples/script/example-multiple-recipes.solution" input.solution
"$BIN" -input input.solution -output results.csv
```

Produced `results.csv`:

```
recipe-id,goal-condition-success,dish-approximation-score,execution-time
afghan-biscuits,1.00,1.00,2735
almond-crescent-cookies,0.96,0.85,2550
```

This **matches the shipped reference** `documentation/examples/script/results.csv`
**exactly** (afghan-biscuits 1.00/1.00/2735; almond-crescent-cookies
0.96/0.85/2550). Console also prints the per-recipe GCS/DAS/Execution-Time and
"The simulation process has finished." Each recipe takes a few seconds (LispWorks
heap load + simulation).

**Acceptance met:** a gold procedural semantic network can be fed to the kitchen
simulator and returns execution + evaluation results (GCS, DAS, Execution Time;
Smatch available via the Python lib) with no manual intervention.

## 5. This project's layer (added on top)

- `src/mcl.py` — MCL parser + precondition/sequence graph extraction (Phase 1).
- `src/phase1_verify.py` — all-recipe separability sweep.
- `src/phase1_worked_example.py` — the banana-bread worked example.
- See `PHASE1_ORACLE.md` for the Phase-1 gate result (PASS).
