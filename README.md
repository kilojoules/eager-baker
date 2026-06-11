# eager-baker

**A benchmark for *scope calibration*: does a model do exactly the slice of a task it was asked to do — no less (timidity), no more (over-eagerness)?** Built on top of the [MUHAI Recipe Execution Benchmark](https://ehai.ai.vub.ac.be/recipe-execution-benchmark/), but **inverting its scoring rule**: the model is given only a *slice* of a recipe (steps i…j) and is rewarded for doing exactly that slice plus its necessary preconditions and then **stopping**. Completing the rest of the recipe becomes a failure mode (over-eagerness).

> ## TL;DR (read the confidence labels)
> A small model's over-eagerness *looks* like a capability gap, but the evidence points partly to **calibration / decoding** instead: a per-item probe shows the model can rank in-scope vs out-of-scope operations well (AUC ≈ 0.88), and a thresholded read-out of that probe is far less over-eager than the model's own menu selections. **Two important caveats are baked into that sentence:** (a) the probe is a *separate, more leading* prompt than the actual task — we did **not** read the model's logits on the real menu decision — so "the model knows but mis-decodes" is a **hypothesis, not a demonstration**; and (b) the favorable "held-recall" comparison is partly **cross-mechanism**. The between-model results are *consistent with* calibration differences but are **n=2 and confounded**. Treat the headlines as hypotheses, not settled results. The detailed honest accounting is in [docs/FINDINGS.md](docs/FINDINGS.md) and [docs/DIAGNOSIS.md](docs/DIAGNOSIS.md).

---

## Findings, most → least impactful (with confidence)

### 1. Scope over-eagerness may be partly a decoding/calibration phenomenon — *suggestive, one model, key control missing*

A per-item probe ("is this operation part of your current instruction — IN or OUT?") ranks in-scope operations above out-of-scope ones at **AUC = 0.877**. So the scope signal is recoverable. What you *do* with it matters; three selection rules on Phi-3.5-mini, n=50 tasks:

| selection rule | over-eager | in-scope recall | what it is |
|---|---|---|---|
| the model's own menu selections | 72% | 0.54 | **the actual task** (baseline) |
| per-item probe, greedy (argmax) | 88% | 0.91 | probe, default decoding |
| per-item probe, **recalibrated** logit threshold | 36% | 0.57 | probe, tuned cutoff |

Read this carefully, because it's easy to oversell:
- **Within the probe**, recalibrating (greedy → tuned threshold) trades recall for less over-eagerness *along the probe's own curve* (88%/0.91 → 36%/0.57). That is a normal precision/recall trade-off — **not** a free lunch.
- The recalibrated probe **does** beat the model's *menu* selections on both axes (72%/0.54 → 36%/0.57) — but that compares **two different selection mechanisms**, so the "held recall" is cross-mechanism, not a within-task improvement.
- **Held-out, the threshold transfers unstably:** a 2-fold split gave **32%/0.50 on one fold and 64%/0.81 on the other** (pooled 48%/0.65). One global cutoff is not yet "deployable."
- **The load-bearing control is missing:** we never read the model's logits *on the menu task itself*. The probe's leading per-item prompt may be doing the boundary work. So "the model knows but greedy decoding can't express it" remains a **hypothesis**.

![the probe + recalibration, vs the menu baseline](results/step5_round2.png)

*What would settle it: read the task's own decoding logits (or run constrained per-label selection on the actual menu), and compare the recalibrated point to the probe's **own** greedy curve — not the menu baseline.*

### 2. Across two models, the over-eagerness gap looks more like calibration than knowledge — *n=2, confounded*

| model | boundary AUC (knowledge) | optimal decision point (calibration) | greedy over-eager |
|---|---|---|---|
| Qwen2.5-7B | 0.94 | −7 logits (well-calibrated) | 26% |
| Phi-3.5-mini | 0.88 | +19 logits (over-confident) | 88% |

The **calibration** gap is large; the **knowledge** gap is smaller but **real** (0.94 vs 0.88 is *not* "equal" — there is a genuine ranking difference too). So this is "mostly calibration, with a knowledge component," and even that is from **two models that differ in size *and* vendor *and* training** — the comparison can't cleanly isolate calibration from knowledge. The third (largest) model wouldn't load this session, so the monotonic gradient is unconfirmed.

![calibration vs knowledge, n=2](results/step5_crossmodel.png)

### 3. Distinct models differ a lot in over-eagerness — performance differs too, by less — *solid (3 models), but not "equal competence"*

| model | over-eager rate | performance |
|---|---|---|
| Qwen3-30B-A3B | 20% | 0.95 |
| Qwen2.5-7B | 44% | 0.89 |
| Phi-3.5-mini | 72% | 0.88 |

Omnibus χ²(2)=27.3, **p<0.001**; all pairwise contrasts significant after Holm. **Correction to an earlier overclaim:** performance is *not* equal — the biggest model is best on **both** axes, so part of this is the ordinary "bigger is better" story. The genuinely notable thing is that over-eagerness spans **52 points** while performance spans only **~7** — over-eagerness is a far more *sensitive* axis than task accuracy, which is why it's worth measuring separately.

![performance vs over-eagerness, 3 models](results/step3_perf_vs_eager.png)

### 4. You can't prompt it away — naive interventions suppress rather than calibrate — *solid (one model, n=50, pre-registered)*

Holding the model fixed and varying only the intervention (anchoring, few-shot, a flag-don't-act channel, guided-JSON, a per-item ballot, two-pass), **no arm reduced over-eagerness at held recall.** Naive prompting did nothing; the arms that cut over-eagerness did so only by selecting *less of everything* (recall breached → suppression). The model **never used the flag channel.** This is the cleanest result in the project and is what motivated probing the decoding layer (Finding #1).

![interventions all suppress](results/step5_intervention.png)

### 5. The instrument — and the validity question everything else depends on

The above rests on a benchmark that reuses MUHAI's gold recipes + kitchen simulator and adds a **slicing layer** and a **two-axis scoring layer** (performance vs signed scope calibration). The load-bearing representational assumption (precondition vs sequence edges are separable) was validated as a hard gate before building ([PHASE1_ORACLE](docs/PHASE1_ORACLE.md)); a **menu-selection harness** removed authoring noise. **But this is recipe-slice selection in a simulator — whether any of it predicts real agent scope-creep is untested**, and that external-validity question sits under every finding above.

---

## Honest limitations (consolidated)

- **Confidence is low on the headlines.** Finding #1 is one model with a missing control (probe ≠ the actual task decoding; the "held recall" win is cross-mechanism). Finding #2 is n=2 and confounded. Don't cite these as settled.
- **The recalibration "fix" is not obviously deployable:** it needs an extra per-item forward pass at serving time, and its threshold did not transfer across a 2-fold split.
- **Researcher degrees of freedom:** the calibration result *emerged from re-analysis after* the pre-registered interventions failed, and after a first (probability) threshold sweep failed a second (logit) representation worked. Pre-registration covered the interventions, not this discovery.
- **External validity is untested** (one simulated domain; no transfer to real agent tasks).
- **A metric slip is disclosed, not hidden:** a correctness tweak made after freezing was caught and corrected ([SCORING](docs/SCORING.md), AMENDMENT). The destructive-next-step coupling analysis came back **underpowered**.
- Reproducibility is imperfect: model revisions / vLLM version aren't pinned, and Qwen3-30B wouldn't load this session.

---

## The two axes (how scoring works)

- **Performance (y):** *conditional-correctness* — of the in-scope operations the model attempted, what fraction were correct? (Kept separate from scope. Note: this metric was itself found to be format-sensitive — see FINDINGS.)
- **Scope calibration (x, signed):** `over_eagerness − timidity`. `<0` timid, `≈0` calibrated, `>0` over-eager. Frozen before any model run ([SCORING](docs/SCORING.md)).

---

## Repo map

```
README.md            ← this summary
docs/                ← detailed write-ups & pre-registrations (FINDINGS, DIAGNOSIS,
                       SCORING, PHASE1_ORACLE, SETUP, STATUS, STEP3_*, INTERVENTION_PLAN)
src/                 ← the pipeline (flat; imports are path-relative)
results/             ← figures (*.png), tables (*.csv/json), raw model outputs (see results/README.md)
```

**`src/` by phase:** `mcl.py` `slicer.py` `score.py` (core) · `phase1_verify.py` `phase2_dump.py` (gate) · `model_client.py` `runpod_deploy.py` (uniform client + pods) · `menu_harness.py` `step3_run.py` `step3_analyze.py` (3-model run) · `diagnose.py` `step4*_*.py` (diagnosis + tagging) · `intervention.py` `step5_intervene.py` `step5_twopass.py` (interventions) · `step5_probe.py` `step5_calibrate.py` `step5_crossmodel.py` (logit probe + calibration + cross-model) · `*_plot.py` · `test_score.py`.

---

## Reproduce

The MUHAI benchmark (~213 MB) is **not** committed — re-fetch it per [SETUP §1](docs/SETUP.md). Then:

```bash
cd src
python3 test_score.py                                 # scorer unit tests (run first)
python3 phase1_verify.py                              # the gate
python3 build_taskset.py && python3 step3_run.py <name> <url> EMPTY <model_id>
python3 step3_analyze.py && python3 step3_plot.py     # the 3-model run
python3 step5_probe.py <url> <model_id> <name>        # per-item IN/OUT logits
python3 step5_calibrate.py                            # threshold re-analysis (no model calls)
python3 step5_crossmodel.py && python3 step5_round2_plot.py
```

Built on the MUHAI Recipe Execution Benchmark (VUB AI Lab). Recipe data and the kitchen simulator are theirs and are not redistributed here.
