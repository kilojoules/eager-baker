# DIAGNOSIS — is the over-eagerness a movable disposition or a capability?

Re-analysis only, off the cached n=50 × 3-model menu run (no new model/sim calls;
deterministic menu rebuild + cached tags). Reproduce: `python3 src/diagnose.py`.

## Verdict: **scope-adherence CAPABILITY (mixed, capability axis dominant).**

Over-eagerness here **co-varies with general scope-handling ability**; it is *not*
a cleanly movable disposition sitting on top of equal competence. The plot's
"calibration, not capability" subtitle overclaims and has been corrected. There is
a genuine next-step-overrun component, so it is not *purely* a capability artifact
— hence "mixed" — but three of four cuts point at capability, and the persona
prior says it won't move with naive prompting.

> **REFINEMENT (2026-06-11, Round-2 logprob probe — see FINDINGS §STEP 5 ROUND 2).**
> "Capability" here is **NOT a knowledge/boundary-identification ceiling.** A
> per-item IN/OUT logprob read-out on phi gives **boundary AUC = 0.877** — the
> model's logits rank in-scope above out-of-scope items well, and per-task
> *rank* selection reaches the success region (52% over-eager at 0.64 recall).
> The failure is at the **decoding/calibration** layer: P(IN) is saturated ≈1.0,
> so greedy/threshold selection can't express a ranking the model clearly has.
> So the accurate framing is: **phi knows the boundary but can't act on it under
> greedy decoding** — a decoding/calibration bottleneck, not missing knowledge.
> (The "phi never used the flag channel" point in §1 is thus a *behaviour/format*
> artifact, not evidence it can't locate the boundary.)
>
> Thresholding this probe's logits *looked* like a deployable fix (72%→36% over-
> eager at held recall). **BUT this was largely a probe artifact — see correction.**
>
> ⚠️ **CORRECTION (2026-06-11, M2 control — FINDINGS §ROUND 2d).** The probe above is
> an *isolated, leading* per-item question, **not** the model's logits on the actual
> menu task. Reading per-label logits in the **real task framing** drops boundary
> AUC from **0.88 → 0.70**, and recalibrating those task logits does **not** help
> (86%/0.57 greedy → 84%/0.52, not off-diagonal). So:
> - the strong "phi knows the boundary but greedy can't express it / deployable fix"
>   claim is **WITHDRAWN** — in the model's own decision context the signal is weak
>   and not recoverable by thresholding;
> - the cross-model AUCs (Qwen2.5-7B 0.94 vs Phi-3.5 0.88) are isolated-probe numbers
>   and are **inflated** by the same artifact → the "calibration not knowledge"
>   cross-model claim is a **deflated lead, not a finding.**
>
> What remains, honestly: there is *some* scope signal even in the task logits
> (0.70 > chance), so it is **not a pure knowledge ceiling** — but it is far from
> cleanly recoverable. The §1 capability framing and the behavioural results
> (Step 3, the intervention study) stand; they never depended on the probe.

## The numbers that decided it

**§1 — composition.** The frozen over-eager metric already counts *only* next-step
(outscope) items, so the headline 20/44/72% rates are genuine sequence overrun
(~60–65% of all non-in-scope picks are real next-steps, not distractors). **But**
the *distractor*-pick rate tracks model strength in lockstep with over-eagerness:

| model | over-eager rate | distractor-pick rate (≥1) | distractor uptake |
|---|---|---|---|
| qwen3-30b-a3b | 20% | 22% | 11/100 |
| qwen2.5-7b | 44% | 34% | 17/100 |
| phi-3.5-mini | 72% | 50% | 29/100 |

→ the weak model selects more *wrong* items too, not just more *next* items. That
is **indiscriminate / low-precision selection**, a capability signal, and it is
invisible to the performance axis (conditional-correctness only scores in-scope
picks). This is the single most important cut and it weakens "disposition".

**§2 — consequence-sensitivity. [FIRM-UP ATTEMPTED 2026-06-09 — remains
underpowered; direction holds.]** No model oversteps *less* when the next step is
destructive; benign−coupled over-eager rate is −12% (phi), +2% (qwen2.5), −25%
(qwen3). Pooled **Mantel-Haenszel** (model-stratified) common **OR = 1.73** (i.e.
coupled is, if anything, *more* over-eager — the opposite of easing off), but
**χ²=0.41, p=0.52**, and achieved power to detect even a 25 pp easing-off is only
~46%. So the *direction* uniformly says **scope-blind**, but it cannot be confirmed
at power.

*Why it can't be powered here:* a deliberate simulator scan of ~140 additional
candidate slices (windowless; the `stdin=/dev/null` fix removed the earlier window
storm) found only **~5 coupled (~4%)** — and the original 50 had 5/45 (~11%).
**Destructive next-steps are genuinely rare in these recipes**, so the coupled-task
count cannot reach the n (~30–50) a powered §2 needs. This is a property of the
benchmark's recipes, not fixable at feasible n. Reported as underpowered;
consequently the consequence-salience intervention arm (Arm 5) was **dropped** (its
precondition — §2 confirming blindness at power — is not met). See
`src/step2_firmup.py`, `src/step4b_scan_coupled.py`.

**§3 — load/temptation correlates (point-biserial, n=50).** Over-eagerness rises
**significantly with the size of the temptation set** (n_outscope) for both weaker
models — phi +0.32\*, qwen2.5 +0.33\* — and with menu length (qwen2.5 +0.32\*);
qwen3 is flat (+0.07, +0.13, n.s.). phi also oversteps more on earlier slices
(position −0.34\*, ≈ more recipe left to grab). More temptation → more overstep,
for the weak models = a **load/comprehension effect**, not a fixed disposition.

**§4 — is y flat by construction?** mean performance 0.88 / 0.89 / 0.95 and
timidity (80/80/76%) and dropped-preconditions (0.38/0.38/0.40) *are* ≈flat — so
on the in-scope dimensions the models are similar. But distractor-pick rate
(50/34/22%) is **not** flat. So "flat y" holds only because conditional-
correctness excludes the precision signal on which the models clearly differ.
"Differ in calibration **not** capability" is therefore **false as stated**.

**§5 — persona prior (from the menu pilot, already on disk).** When *one* model
(Sonnet) was prompted cautious vs. eager under this same menu harness, selections
barely moved (mean signed-scope identical at −0.16; same picks on 6/8 tasks). So a
naive prompt-based "be less eager" intervention is a weak prior to start from.

## What this means for the next study (per spec §6 reframe)

The intervention question is **not** "can we nudge a movable disposition" but:
**"can prompting / few-shot / structured decoding *compensate for* a
scope-adherence deficit?"** That is a different but still-interesting study. When
it starts (not yet): hold the model fixed — **phi-3.5-mini**, most headroom at
72% — and vary only the intervention, same harness, same frozen metric. Given §5,
lead with the stronger levers (few-shot demonstrations of stop-at-boundary,
guided/constrained decoding) rather than a bare "don't overstep" instruction.

## Honest caveats

- coupled n=5 (§2) is descriptive, not powered.
- distractor distinctness varies by task (some slices had 0 distractors and were
  excluded at task-build time); the precision signal is real but coarse.
- 3 models span only 2 vendors and correlate size with recency; "capability" here
  means "general scope-handling ability of these three models", not an isolated
  scaling law.
