"""
cohorts.py — the Step-3 models split into two NON-COMPARABLE cohorts.

The open-weights models go through the clean vLLM OpenAI-compatible decoding path
(temperature=0, seed=0, no agent scaffolding). The frontier models go through
vendor AGENTIC CLIs (their own system prompt, tools, memory; no temperature/seed/
logprobs control) because no API key / OpenAI-compatible endpoint was available.

Because the harness differs, the two cohorts are NOT directly comparable: any
between-cohort gap conflates model capability with the harness. So statistics are
computed WITHIN each cohort; cross-cohort numbers are descriptive only. The
open-vLLM cohort is the pre-registered primary comparison.
"""

COHORTS = {
    "open-vLLM": {
        "label": "Open-weights — vLLM (pre-registered, primary)",
        "short": "open-weights · vLLM",
        "harness": "vLLM OpenAI-compatible, temp=0 seed=0, no agent scaffolding",
        "preregistered": True,
        "models": ["phi-3.5-mini", "qwen2.5-7b", "qwen3-30b-a3b"],
    },
    "frontier-agentic": {
        "label": "Frontier — agentic CLI (exploratory, confounded)",
        "short": "frontier · agentic CLI",
        "harness": "vendor agentic CLI (own system prompt/tools/memory; no temp/seed)",
        "preregistered": False,
        "models": ["gemini-3.5-flash", "claude-opus-4.8"],
    },
}

# fixed display order (over-eager high -> low), used by analysis + plots
MODEL_ORDER = ["phi-3.5-mini", "qwen2.5-7b", "qwen3-30b-a3b",
               "gemini-3.5-flash", "claude-opus-4.8"]

COHORT_OF = {m: cid for cid, d in COHORTS.items() for m in d["models"]}
COHORT_ORDER = ["open-vLLM", "frontier-agentic"]

# A/B treatment arms: an arm is the SAME model+harness as its base with ONE harness
# knob toggled. Arms are EXCLUDED from the cross-model cohort statistics and analyzed
# as PAIRED within-model comparisons (same 50 tasks) instead — see step3_ab.py.
AB_ARMS = {
    "claude-opus-4.8+ponytail": {
        "base": "claude-opus-4.8",
        "knob": "ponytail skill (scope-discipline persona) appended to the "
                "Claude Code system prompt via --append-system-prompt",
    },
}
BASE_MODELS = set(MODEL_ORDER)


def is_arm(model):
    return model in AB_ARMS


def base_models_present(models_present):
    """Registered cohort/base models only, in display order. A/B treatment arms and
    any UNREGISTERED models are excluded — the latter with a loud warning, so a new
    results file is never silently mislabeled into the open-vLLM cohort."""
    import sys
    present = list(models_present)
    unregistered = [m for m in present if m not in BASE_MODELS and m not in AB_ARMS]
    if unregistered:
        print(f"[cohorts] WARNING: results present for models not registered in any "
              f"cohort (excluded from analysis): {unregistered}. Add them to "
              f"cohorts.COHORTS.", file=sys.stderr)
    return [m for m in MODEL_ORDER if m in present]


def cohort_of(model):
    return COHORT_OF.get(model, "unknown")


def ordered(models_present):
    """MODEL_ORDER filtered to those present, unknown models appended."""
    present = list(models_present)
    out = [m for m in MODEL_ORDER if m in present]
    out += [m for m in present if m not in MODEL_ORDER]
    return out
