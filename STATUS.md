# STATUS — Scope-Calibration Benchmark

Checkpoint after the Phase-1 hard gate. Read this first.

## TL;DR

- **Section 2 (setup): DONE.** Evaluator runs and reproduces the shipped example
  output **exactly**. (`SETUP.md`)
- **Phase 1 (HARD GATE): ✅ PASS.** The MUHAI representation cleanly separates
  *precondition* ("required-for") from *sequence* ("followed-by") edges. The
  scope boundary computes automatically — no hand-labeling needed. (`PHASE1_ORACLE.md`)
- **Phase 2 (slicer): DONE & validated.** `make_task(recipe, i, j)` produces
  `{nl_instruction, kitchen_state, in_scope_ops, out_of_scope_ops}`; validated on
  387 slices with **0 invariant violations**; 5 example tasks dumped for your
  spot-check. (`src/slicer.py`, `results/phase2_examples.txt`)
- **Phase 3 (scoring): ✅ FROZEN 2026-06-09.** Approach (A) + performance =
  **conditional-correctness** (not raw recall), per human sign-off. Metric is now
  locked; no retroactive tuning. (`SCORING.md`)
- **Phase 4 (harness + pilot): ✅ DONE — signal found.** 8 recipes × 2 prompt
  regimes (cautious/eager) on one model (Sonnet). The regimes **separate on the
  scope axis at equal performance** (cautious signed −0.15, 0/8 over-eager; eager
  +0.03, 2/8 over-eager). Scorer validated on 6 synthetic cases first.
  (`FINDINGS.md`, `results/pilot_plot.png`, `results/pilot_results.csv`)
- **Step 3 (scaled run): ✅ DONE.** 3 real open-weights models via a uniform
  RunPod/vLLM client (Gate A satisfied with genuinely distinct models, no
  personas); n=50/model; metric frozen; analysis pre-registered. **Result: models
  differ significantly in over-eager rate** — Qwen3-30B 20%, Qwen2.5-7B 44%,
  Phi-3.5-mini 72% (omnibus p<0.001; all pairwise sig after Holm), at equal
  performance → calibration not capability. The effect is in the *rate*, not the
  signed-scope magnitude (all net-timid). §4 simulator tagging done (5 coupled).
  All RunPod pods terminated. See `FINDINGS.md` (STEP 3), `STEP3_POWER.md`,
  `STEP3_ANALYSIS_PLAN.md`, `results/step3_*`.
- **Still open:** Phase 5 (fold DAS penalty into scoring for coupled tasks — the
  §4 tags now exist); more model families (Mistral failed to serve); larger n for
  the ~24–28 pp pairwise gaps that sit at the MDE.

## What's the load-bearing result

The whole project hinged on Phase 1. It passes, three independent ways:

1. **Docs say so** (documentation.pdf §3): dependencies are encoded via argument
   sharing — "a shared argument used as input … is only available once it is
   provided as output in the other predicate." Kitchen-state variables sit in
   fixed argument positions, so they're separable from object data-flow.
2. **All 30 gold recipes confirm it** (`python3 src/phase1_verify.py`): 986 ops,
   0 unknown primitives, every timeline a clean linear chain, and **42.4% of
   adjacent-in-time op pairs have no precondition link** — "follows" ≠ "requires".
3. **Hand-checked worked example** (`python3 src/phase1_worked_example.py`): for
   "cream together butter, eggs and sugar", `crack` is correctly in the
   precondition closure while the next step ("add bananas") is a temporal
   successor outside it.

## What I learned that changes the back half (measured, not assumed)

Running the benchmark's own failure-mode examples through the working evaluator
(`results/failure_mode_metrics.csv`) showed:

- **Over-eagerness is "free" under GCS/DAS** unless it's *destructive*:
  `additional-side-dish` (extra dish) = GCS 1.00 / DAS 1.00; `extended-main-dish`
  (dips the finished cookies) = GCS 1.00 / **DAS 0.87**. → **Phase 5's
  destructive-slice requirement is empirically necessary**, and **DAS** (not GCS)
  is the metric that detects destruction.
- **Timidity is severe under GCS:** skipping one early implicit precondition
  (`missing-minor-implicit`) = **GCS 0.38** while DAS stays 0.99.
- These mean whole-recipe GCS/DAS **cannot** be the slice "performance" axis (a
  correct-and-stopped model would look like a failure). Performance must be
  measured against the **in-scope target** — see `SCORING.md §1, §5`.

## The one decision I need from you (see SCORING.md §5)

The shipped evaluator is a black box keyed by recipe-id (scores against the
*full* gold recipe only). For a slice-aware performance signal I propose:
- **(A, recommended)** Smatch-**recall** on the gold in-scope subgraph as the
  universal performance axis (extra ops don't lower it → axes stay orthogonal),
  plus simulator **DAS** on coupled/destructive tasks only. Uses shipped tools.
- **(B)** Extend the simulator (Babel/Lisp toolkit) to score a truncated gold —
  cleaner but heavier; the brief deferred the toolkit.

If (A) is fine, say so and I'll freeze `SCORING.md` and proceed to Phase 4
(model harness + 5–8 recipe pilot, cautious-vs-eager models).

## Also worth knowing

- **macOS blocker (resolved):** XProtect deleted the unsigned 2023 evaluator on
  first run; ad-hoc `codesign` fixes it. Details in `SETUP.md §3`.
- **Prefix kitchen-state is symbolic**, derived from the gold prefix network
  (the standalone evaluator doesn't expose a live kitchen object). For scoring we
  prepend the gold prefix to model output. Limitation noted in `slicer.py` /
  `SCORING.md`.
- **6 slices have empty out-of-scope sets** (recipes ending in no-op "serve and
  enjoy" steps) — over-eagerness is untestable there; Phase 4 task selection
  should avoid them.

## Files

```
SETUP.md                         setup + reproduced example output
PHASE1_ORACLE.md                 the gate result (PASS) + evidence
SCORING.md                       proposed metric (NOT yet frozen)
STATUS.md                        this file
src/mcl.py                       MCL parser + precondition/sequence graph
src/phase1_verify.py             all-recipe separability sweep
src/phase1_worked_example.py     banana-bread worked example
src/slicer.py                    make_task() — Phase 2 slicer
src/phase2_dump.py               slice validation + 5 example tasks
results/phase2_examples.txt      the 5 example tasks (for your spot-check)
results/failure_mode_metrics.csv evaluator behavior on shipped failure modes
```

## Reproduce everything

```
# (one-time) download + ad-hoc sign evaluator — see SETUP.md §1, §3
cd src
python3 phase1_verify.py          # gate evidence
python3 phase1_worked_example.py  # worked example
python3 phase2_dump.py            # slice validation + 5 example tasks
```
