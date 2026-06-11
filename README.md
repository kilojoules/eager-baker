# eager-baker

**A benchmark for *scope calibration*: does a model do exactly the slice of a task it was asked to do — no less (timidity), no more (over-eagerness)?** Built on top of the [MUHAI Recipe Execution Benchmark](https://ehai.ai.vub.ac.be/recipe-execution-benchmark/), but **inverting its scoring rule**: the model is given only a *slice* of a recipe (steps i…j) and is rewarded for doing exactly that slice plus its necessary preconditions and then **stopping**. Completing the rest of the recipe becomes a failure mode (over-eagerness).

> ## TL;DR
> A small model's over-eagerness (grabbing operations it wasn't asked for) looks like a *capability* problem — but it isn't. **The model knows where the task boundary is (it's cleanly in the logits, AUC ≈ 0.9); it just can't act on it under greedy decoding because it's over-confident.** Recalibrating the read-out — one threshold, no retraining — cuts over-eagerness roughly in half *at held accuracy*. And the differences *between* models are mostly differences in this calibration, not in knowledge.

---

## Findings, most → least impactful

### 1. Over-eagerness is a decoding/calibration artifact, not a capability ceiling — and the fix is deployable

We probed the model's per-item "is this operation in-scope?" logits. The slice **boundary is strongly present in the logits (AUC = 0.88)** — the model ranks in-scope operations well above out-of-scope ones. The problem is purely that its probabilities are **saturated near 1.0** (over-confident), so greedy decoding grabs almost everything. Thresholding the *unsaturated logit difference* instead — a single global cutoff, no oracle, no retraining — moves it **off the suppression diagonal**:

| selection rule | over-eager | in-scope recall |
|---|---|---|
| greedy (baseline) | 72% | 0.54 |
| recalibrated logit threshold (in-sample) | **36%** | 0.57 |
| same, **held-out** (threshold chosen on disjoint tasks) | **48%** | 0.65 |

→ over-eagerness roughly halved **at held/higher recall**. This is the headline: the behavior is a *decoding* limitation, and a calibrated read-out recovers the boundary.

![decoding artifact + deployable fix](results/step5_round2.png)

*Caveat: one model (Phi-3.5-mini), n=50 tasks; the held-out threshold wobbles a bit at n=25/fold; logit precision is coarse.*

### 2. The difference *between* models is calibration, not knowledge

Running the same logit probe on a second model: **both locate the boundary about equally well, but their calibration differs starkly** — and that's what drives their different over-eagerness.

| model | boundary AUC (knows the boundary?) | optimal decision point (calibration) | greedy over-eager |
|---|---|---|---|
| Qwen2.5-7B | 0.94 | **−7 logits** (well-calibrated — greedy works) | 26% |
| Phi-3.5-mini | 0.88 | **+19 logits** (very over-confident) | 88% |

→ the over-eagerness gap is **over-confidence, not missing knowledge**.

![calibration not knowledge](results/step5_crossmodel.png)

*Caveat: only 2 models — Qwen3-30B (the third, biggest) wouldn't load on the GPU host this session, so the full monotonic gradient is consistent-with but not confirmed.*

### 3. Distinct models differ significantly in scope calibration — at equal competence

Across three genuinely different open-weights models (one uniform harness, no personas, pre-registered analysis), over-eagerness differs sharply **while task performance is essentially equal** — so it's a calibration difference, not "the small model is just worse."

| model | over-eager rate | performance |
|---|---|---|
| Qwen3-30B-A3B | 20% | 0.95 |
| Qwen2.5-7B | 44% | 0.89 |
| Phi-3.5-mini | 72% | 0.88 |

Omnibus χ²(2)=27.3, **p<0.001**; all three pairwise contrasts significant after Holm correction. Finding #2 then explains *why* this gradient exists (calibration).

![performance vs over-eagerness](results/step3_perf_vs_eager.png)

*Caveat: 3 models spanning 2 vendors; scale and vendor are confounded.*

### 4. You can't prompt it away — naive interventions just suppress

Holding the model fixed and varying only the intervention (anchoring, few-shot, a flag-don't-act channel, guided-JSON, a per-item ballot, two-pass), **no arm reduced over-eagerness at held recall.** Naive prompting did nothing; the arms that *did* cut over-eagerness only did so by selecting *less of everything* (recall dropped past tolerance = **suppression**, not calibration). Notably the model **never used the flag channel** — given an explicit option to *note* a later step without doing it, it didn't. This is what forced the search down to the decoding layer (Finding #1).

![interventions all suppress](results/step5_intervention.png)

*Caveat: one model, n=50; a structured-decoding objective that rewards recall while penalizing overstep is the obvious untried arm.*

### 5. The instrument: a scope-calibration benchmark on a real simulator

The above rests on a working benchmark. We reuse MUHAI's gold recipes + kitchen simulator and add a **slicing layer** (give the model steps i…j) and a **scoring layer** (two orthogonal axes — *performance* = did it do the slice, *scope calibration* = timid ↔ calibrated ↔ over-eager). The load-bearing assumption — that the representation cleanly separates *precondition* ("required-for") edges from *sequence* ("followed-by") edges — was validated as a hard gate before anything was built ([PHASE1_ORACLE](docs/PHASE1_ORACLE.md)). A **menu-selection harness** (the model picks operations from a labeled menu rather than authoring them) removed authoring noise so the scope signal is clean.

---

## Honest limitations (consolidated)

- **Single model for the headline mechanism** (Finding #1) and **two models** for the cross-model claim (#2). The third, biggest model wouldn't load — a GPU-host failure, not a result.
- **n=50 tasks**, one recipe domain (cooking). Held-out threshold stability is modest.
- The benchmark **changes one thing about real agents** (recipe slices) — whether this transfers to e.g. coding-ticket scope-creep is untested (the original stretch goal).
- **A metric-integrity slip is disclosed, not hidden:** a correctness tweak was made after freezing and then corrected ([SCORING](docs/SCORING.md), AMENDMENT). Destructive-next-step coupling (does the model overstep less when it's harmful?) came back **underpowered** — destructive steps are rare in these recipes.
- The full, blow-by-blow account — including framings that were later walked back — is in [FINDINGS](docs/FINDINGS.md) and [DIAGNOSIS](docs/DIAGNOSIS.md).

---

## The two axes (how scoring works)

- **Performance (y):** *conditional-correctness* — of the in-scope operations the model attempted, what fraction were correct? (Competence, kept separate from scope.)
- **Scope calibration (x, signed):** `over_eagerness − timidity`. `<0` timid (did less), `≈0` calibrated, `>0` over-eager (did more). Metric frozen before any model run ([SCORING](docs/SCORING.md)).

---

## Repo map

```
README.md            ← you are here (the summary)
docs/                ← detailed write-ups & pre-registrations
  FINDINGS.md          full results, every assumption, the corrections
  DIAGNOSIS.md         is over-eagerness disposition / capability / calibration?
  SCORING.md           the frozen metric (+ disclosed amendment)
  PHASE1_ORACLE.md     the hard gate (precondition vs sequence edges)
  SETUP.md             environment + reproduced MUHAI example
  STATUS.md            phase-by-phase status
  STEP3_POWER.md, STEP3_ANALYSIS_PLAN.md, INTERVENTION_PLAN.md  (pre-registrations)
src/                 ← the pipeline (flat; imports are path-relative)
results/             ← figures (*.png), tables (*.csv/json), raw model outputs
```

**`src/` by phase:** `mcl.py` `slicer.py` `score.py` (core benchmark) · `phase1_verify.py` `phase2_dump.py` (gate + slicer) · `model_client.py` `runpod_deploy.py` (uniform vLLM/API client + pods) · `menu_harness.py` `step3_run.py` `step3_analyze.py` (3-model run) · `diagnose.py` `step2_firmup.py` `step4*_*.py` (diagnosis + destructive tagging) · `intervention.py` `step5_intervene.py` `step5_twopass.py` (interventions) · `step5_probe.py` `step5_calibrate.py` `step5_crossmodel.py` (the logit probe + calibration + cross-model) · `*_plot.py` (figures) · `test_score.py` (scorer unit tests).

---

## Reproduce

The MUHAI benchmark (~213 MB) is **not** committed — re-fetch it per [SETUP §1](docs/SETUP.md). Then:

```bash
cd src
python3 test_score.py        # scorer unit tests (run first)
python3 phase1_verify.py     # the gate

# 3-model run (needs a vLLM endpoint per model — see runpod_deploy.py):
python3 build_taskset.py && python3 step3_run.py <name> <url> EMPTY <model_id>
python3 step3_analyze.py && python3 step3_plot.py

# the headline: logit probe -> calibration fix -> cross-model
python3 step5_probe.py     <url> <model_id> <name>   # per-item IN/OUT logits
python3 step5_calibrate.py                           # deploy-realistic threshold (no model calls)
python3 step5_crossmodel.py && python3 step5_round2_plot.py
```

Built on the MUHAI Recipe Execution Benchmark (VUB AI Lab). Recipe data and the kitchen simulator are theirs and are not redistributed here.
