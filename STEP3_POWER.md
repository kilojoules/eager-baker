# STEP3_POWER.md — Gates A & B for the scale-up

## Gate A — model diversity: ✅ PASS

- **No external API key** (`ANTHROPIC_API_KEY`/`OPENAI_API_KEY`/… all unset; SDK
  auth fails). So cross-family models (GPT, Gemini, …) are **not** reachable.
- **In-session Agent-tool model override IS reachable and routes to genuinely
  distinct models.** A 3-tier probe (same prompt, `model: haiku|sonnet|opus`)
  returned three different self-reported model IDs:
  - `haiku` → `claude-haiku-4-5-20251001`
  - `sonnet` → `claude-sonnet-4-6`
  - `opus` → `claude-opus-4-8[1m]`
- These are **clearly different sizes** in the Claude 4.x family — which the spec
  accepts ("different families, or clearly different sizes"). They are **not**
  three personas of one model (the confound the menu pilot exposed).
- **Limitation (stated honestly):** I cannot cryptographically verify the backend
  from inside a subagent; this rests on (a) the harness's documented model-override
  routing and (b) the three distinct self-reported IDs matching the requested
  tiers. The CRT probe did not separate them on capability (all answered 0.05),
  so distinctness rests on routing+IDs, not a behavioral capability gap.

**Locked config:** 3 models {Haiku-4.5, Sonnet-4.6, Opus-4.8}, **no persona**,
menu harness, one condition per (model × task). n set below.

## Gate B — power: ⚠️ well-powered n is expensive → human chooses n

**Primary signal is a rare event.** Pilot over-eager *rates* (fraction of tasks
with ≥1 over-eager selection) under the menu were **0/8 (cautious)** and **1/8
(eager)** → ~6% combined; plausible per-model base rate 5–25%. Detecting a
*difference between two rare rates* needs large n.

Two-proportion power (normal approx; α=0.05 two-sided; 80% power). Fisher's exact,
used in the actual small-n analysis, needs **similar-or-larger** n, so these are
optimistic lower bounds:

**(a) n per model for plausible effects**

| effect (rate A vs B) | n / model | total (3 models) |
|---|---|---|
| 10% vs 25% (15 pp) | **100** | 300 |
| 10% vs 30% | 62 | 186 |
| 5% vs 25% | 49 | 147 |
| 15% vs 40% | 49 | 147 |
| 5% vs 30% | 36 | 108 |
| 10% vs 40% (30 pp) | 32 | 96 |
| 10% vs 50% | 20 | 60 |

**(b) what each feasible n can actually detect** (baseline 15%, 80% power)

| n / model | total | min detectable rate (from 15%) |
|---|---|---|
| 15 | 45 | ≥ 63% (Δ 48 pp) |
| 20 | 60 | ≥ 57% (Δ 42 pp) |
| 30 | 90 | ≥ 48% (Δ 33 pp) |
| 50 | 150 | ≥ 40% (Δ 25 pp) |
| 80 | 240 | ≥ 34% (Δ 19 pp) |
| 100 | 300 | ≥ 32% (Δ 17 pp) |

**(c) achieved power at the agent's originally-proposed n=30/model**

| true effect | power at n=30 |
|---|---|
| 10% vs 25% | **33%** (badly underpowered) |
| 5% vs 30% | 73% |
| 20% vs 50% | 69% |
| 10% vs 40% | 78% |

**Conclusion / Gate B decision.** ~30 tasks/model is powered (~80%) **only for a
large ~30 pp between-model gap**; for a plausible moderate gap (15 pp) it has ~33%
power. The well-powered n (~100/model = 300 runs) is a large in-session subagent
spend. Per the spec, I am **not** silently running an underpowered 30 — I reported
the number and the tradeoff and the human chose **n**.

### CHOSEN: n = 50 / model (human decision 2026-06-09)

- 3 models × 50 tasks = **150 model runs**; §4 simulator tagging kept (~500–750
  evaluator runs).
- **Achieved power: 80% for a Δ≈25 pp between-model over-eager-rate gap**
  (e.g. 15% vs 40%). For the plausible ~12 pp pilot-like gap, power is low — so a
  null at n=50 means **"no between-model gap ≥ ~25 pp at this n"**, NOT "no
  difference". This MDE will be stated with every result.

Whatever n is chosen, the FINDINGS will state the **achieved power** and the
**minimum detectable effect** alongside the result, and a null will be reported
as "does not distinguish these models at n=X (MDE = Y pp)", not as "no effect".

Reproduce: `python3 src/power.py`.
