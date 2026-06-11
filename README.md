# eager-baker

**A benchmark for *scope calibration*: does a model do exactly the slice of a task it was asked to do — no less (timidity), no more (over-eagerness)?** Built on top of the [MUHAI Recipe Execution Benchmark](https://ehai.ai.vub.ac.be/recipe-execution-benchmark/), but **inverting its scoring rule**: the model is given only a *slice* of a recipe (steps i…j) and is rewarded for doing exactly that slice plus its necessary preconditions and then **stopping**. Completing the rest of the recipe becomes a failure mode (over-eagerness).

> ## TL;DR
> Two robust results: **(1)** distinct open-weights models differ sharply in scope over-eagerness (20% → 44% → 72% across three models), and **(2)** you can't prompt it away — every intervention we tried only reduced over-eagerness by *suppressing selection wholesale* (recall fell too). We also chased a more exciting hypothesis — that the over-eagerness is a **decoding/calibration artifact** (the model knows the boundary but mis-decodes) rather than a capability gap. An isolated probe suggested yes; **a control reading the model's logits on the *actual* task deflated it** (boundary AUC 0.88 → 0.70; the recalibration "fix" stops working). So that story is mostly a probe artifact, and the dependable findings are the behavioral ones. This README leads with what survived scrutiny; the full record (including what was walked back) is in [docs/FINDINGS.md](docs/FINDINGS.md).

---

## Findings, most → least reliable

### 1. Distinct models differ sharply in scope over-eagerness — *solid (3 models, pre-registered)*

Three genuinely different open-weights models, one uniform harness (no personas), pre-registered analysis, n=50 tasks each:

| model | over-eager rate | performance |
|---|---|---|
| Qwen3-30B-A3B | 20% | 0.95 |
| Qwen2.5-7B | 44% | 0.89 |
| Phi-3.5-mini | 72% | 0.88 |

Omnibus χ²(2)=27.3, **p<0.001**; all three pairwise contrasts significant after Holm correction. Performance is *not* equal (the biggest model is best on both axes — partly the ordinary "bigger is better" story), but **over-eagerness spans 52 points while performance spans only ~7** — so over-eagerness is a far more *sensitive* axis than task accuracy, which is the case for measuring it separately.

![performance vs over-eagerness, 3 models](results/step3_perf_vs_eager.png)

*Caveat: 3 models span 2 vendors; scale and vendor are confounded.*

### 2. You can't prompt it away — every intervention suppresses rather than calibrates — *solid (one model, n=50, pre-registered)*

Holding the model fixed (Phi-3.5) and varying only the intervention — anchoring, few-shot, a flag-don't-act channel, guided-JSON, a per-item ballot, two-pass — **no arm reduced over-eagerness *at held recall*.** Naive prompting did nothing; the arms that *did* cut over-eagerness only did so by selecting **less of everything** (in-scope recall dropped past tolerance = suppression, not calibration). The model **never used the flag channel** — given an explicit option to *note* a later step without doing it, it didn't. This is the cleanest result in the project.

![interventions all suppress](results/step5_intervention.png)

*Caveat: one model, n=50; a structured objective that rewards recall while penalizing overstep is the obvious untried arm.*

### 3. Is it a decoding/calibration artifact, not a capability gap? — *tested, and a control says mostly no*

This was the exciting hypothesis, and it's instructive how it fell apart under its own control.

**The lead that looked strong.** An isolated per-item probe ("is operation X part of your instruction — IN or OUT?") ranks in-scope above out-of-scope at **AUC 0.877**, and thresholding its logits gives a selection far less over-eager than the model's menu selections. That *suggested* the model "knows" the boundary and just mis-decodes it.

**The control that deflated it (M2).** Read the per-label logits in the **actual task framing** instead — full menu shown, the real *selection* question — and the signal collapses:

| read-out | boundary AUC | recalibration helps? |
|---|---|---|
| isolated comprehension probe | 0.877 | yes (looked like a fix) |
| **the actual task's logits** | **0.700** | **no** (86%/0.57 greedy → 84%/0.52 best; not off-diagonal) |

The high AUC and the "recalibration fix" were **substantially artifacts of the probe's leading framing.** In the model's own decision context the boundary is only weakly separable (AUC 0.70) and thresholding doesn't recover it.

**What survives (weaker, honest):** there *is* some scope signal even in the task logits (0.70 > chance), so it isn't a pure capability ceiling — but the strong "decoding artifact + deployable recalibration fix" claim is **withdrawn.** Two related cross-model numbers (Qwen2.5-7B AUC 0.94 vs Phi-3.5 0.88, suggesting the between-model gap is calibration not knowledge) come from the **same isolated probe** and are therefore **inflated by the artifact above** — treat as a discarded lead, not a finding.

![the isolated-probe view (deflated by the M2 control)](results/step5_round2.png)

*The chart shows the isolated-probe recalibration against the menu baseline; the M2 control (above) is why this is no longer claimed as a result.*

### 4. The instrument — and the validity question under everything

The above rests on a benchmark that reuses MUHAI's gold recipes + kitchen simulator and adds a **slicing layer** and a **two-axis scoring layer** (performance vs signed scope calibration). The load-bearing representational assumption (precondition vs sequence edges are separable) was validated as a hard gate before building ([PHASE1_ORACLE](docs/PHASE1_ORACLE.md)); a **menu-selection harness** removed authoring noise. **But this is recipe-slice selection in a simulator — whether it predicts real agent scope-creep is untested,** and that question sits under every finding above.

---

## Honest limitations (consolidated)

- **The most exciting hypothesis (Finding #3) failed its own control** — reported as a deflated lead, not a result. The behavioral findings (#1, #2) are the dependable ones.
- **External validity is untested:** one simulated domain; no transfer to real agent tasks.
- **Single model** for the intervention study and the probe; **n=2 and confounded** for the (now-discarded) cross-model calibration lead; the third model wouldn't load this session.
- **Researcher degrees of freedom:** Finding #3 emerged from re-analysis after the pre-registered interventions failed; pre-registration covered the interventions, not that exploration.
- **A metric slip is disclosed, not hidden** ([SCORING](docs/SCORING.md), AMENDMENT). The destructive-next-step coupling analysis came back underpowered. `conditional-correctness` (the performance axis) is itself format-sensitive.
- Reproducibility is imperfect: model revisions / vLLM version aren't pinned; Qwen3-30B wouldn't load.

---

## The two axes (how scoring works)

- **Performance (y):** *conditional-correctness* — of the in-scope operations the model attempted, what fraction were correct? (Kept separate from scope; note it's format-sensitive — see FINDINGS.)
- **Scope calibration (x, signed):** `over_eagerness − timidity`. `<0` timid, `≈0` calibrated, `>0` over-eager. Frozen before any model run ([SCORING](docs/SCORING.md)).

---

## Repo map

```
README.md            ← this summary
docs/                ← detailed write-ups & pre-registrations (FINDINGS, DIAGNOSIS,
                       SCORING, PHASE1_ORACLE, SETUP, STATUS, STEP3_*, INTERVENTION_PLAN)
src/                 ← the pipeline (flat; imports are path-relative)
results/             ← figures (*.png), tables (*.csv/json), raw outputs (see results/README.md)
```

**`src/` by phase:** `mcl.py` `slicer.py` `score.py` (core) · `phase1_verify.py` `phase2_dump.py` (gate) · `model_client.py` `runpod_deploy.py` (uniform client + pods) · `menu_harness.py` `step3_run.py` `step3_analyze.py` (3-model run) · `intervention.py` `step5_intervene.py` `step5_twopass.py` (interventions) · `step5_probe.py` (isolated probe) · `step5_probe_task.py` (**the M2 control**) · `step5_calibrate.py` `step5_crossmodel.py` (calibration + cross-model, now deflated) · `*_plot.py` · `test_score.py`.

---

## Reproduce

The MUHAI benchmark (~213 MB) is **not** committed — re-fetch it per [SETUP §1](docs/SETUP.md). Then:

```bash
cd src
python3 test_score.py                                 # scorer unit tests (run first)
python3 phase1_verify.py                              # the gate
python3 build_taskset.py && python3 step3_run.py <name> <url> EMPTY <model_id>
python3 step3_analyze.py && python3 step3_plot.py     # Finding #1
python3 step5_intervene.py <url> <model_id> <arm>     # Finding #2 (arms)
python3 step5_probe.py <url> <model_id> <name>        # the isolated probe (Finding #3 lead)
python3 step5_probe_task.py <url> <model_id> <name>   # the control that deflated it
```

Built on the MUHAI Recipe Execution Benchmark (VUB AI Lab). Recipe data and the kitchen simulator are theirs and are not redistributed here.
