"""
step3_variability.py — run-to-run variability of the frontier (agentic-CLI) models.

The agentic CLIs (Gemini via `agy`, Claude via Claude Code) expose NO temperature/
seed control, so each 50-task run is a fresh stochastic draw. We repeat each model
n times (the committed run is rep 1; step3_run_cli.py writes reps as
'<model>__rep2', '__rep3', ...) and report the spread of the over-eager rate (and
count), plus per-task label stability. This tells us whether the small frontier
gap (e.g. Gemini 12% vs Claude 8%) is even distinguishable from run noise.

Usage: python3 step3_variability.py   [model ...]   (default: the 2 frontier models)
"""
import os, sys, json, glob
from statistics import mean, pstdev, stdev
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from cohorts import cohort_of

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.normpath(os.path.join(HERE, "..", "results"))
S3 = os.path.join(RES, "step3")
CCOLOR = {"open-vLLM": "#1b9e77", "frontier-agentic": "#7570b3"}


def rep_paths(model):
    """canonical run = rep1, then any __repN, sorted."""
    paths = [os.path.join(S3, f"results_{model}.json")]
    paths += sorted(glob.glob(os.path.join(S3, f"results_{model}__rep*.json")))
    return [p for p in paths if os.path.exists(p)]


def rep_metrics(path):
    rows = json.load(open(path))
    n = len(rows)
    oes = [r["n_overeager"] for r in rows]
    return {
        "n": n,
        "oe_rate": sum(1 for x in oes if x > 0) / n,
        "oe_count": mean(oes),
        "recall": mean(r["coverage"] for r in rows),
        "timid": sum(1 for r in rows if r["timidity_norm"] > 0) / n,
        "by_key": {f"{r['recipe_id']}__{r['slice_steps']}": (r["n_overeager"] > 0) for r in rows},
    }


def summarize(model):
    paths = rep_paths(model)
    metr = [(p, rep_metrics(p)) for p in paths]
    base_n = metr[0][1]["n"] if metr else 0
    reps = []                       # drop incomplete reps (e.g. a run still in progress)
    for p, r in metr:
        if r["n"] < base_n:
            print(f"  [skip] {os.path.basename(p)} incomplete ({r['n']}/{base_n})", flush=True)
            continue
        reps.append(r)
    k = len(reps)
    rates = [r["oe_rate"] for r in reps]
    counts = [r["oe_count"] for r in reps]
    # per-task stability of the over-eager label across reps
    keys = set.intersection(*[set(r["by_key"]) for r in reps]) if reps else set()
    flipped = sum(1 for key in keys if len({r["by_key"][key] for r in reps}) > 1)
    sd = stdev(rates) if k > 1 else 0.0
    return {
        "model": model, "reps": k, "n_per_rep": reps[0]["n"] if reps else 0,
        "oe_rates": rates, "oe_rate_mean": mean(rates) if rates else float("nan"),
        "oe_rate_sd": sd, "oe_rate_range": [min(rates), max(rates)] if rates else [None, None],
        "oe_counts": counts, "oe_count_mean": mean(counts) if counts else float("nan"),
        "oe_count_sd": stdev(counts) if k > 1 else 0.0,
        "recall_mean": mean(r["recall"] for r in reps) if reps else float("nan"),
        "timid_mean": mean(r["timid"] for r in reps) if reps else float("nan"),
        "tasks_compared": len(keys), "tasks_flipped": flipped,
        "label_agreement": (1 - flipped / len(keys)) if keys else float("nan"),
    }


def main():
    models = sys.argv[1:] or ["gemini-3.5-flash", "claude-opus-4.8"]
    out = [summarize(m) for m in models]
    print(f"RUN-TO-RUN VARIABILITY (agentic CLIs, no seed)\n{'='*64}")
    for s in out:
        rr = "  ".join(f"{r:.0%}" for r in s["oe_rates"])
        print(f"\n{s['model']}  ({s['reps']} reps x n={s['n_per_rep']})")
        print(f"  over-eager rate per rep: [{rr}]")
        print(f"    mean {s['oe_rate_mean']:.0%}  sd {s['oe_rate_sd']*100:.1f}pp  "
              f"range [{s['oe_rate_range'][0]:.0%}, {s['oe_rate_range'][1]:.0%}]")
        print(f"  mean over-eager count per rep: {[round(c,2) for c in s['oe_counts']]}  "
              f"(mean {s['oe_count_mean']:.2f}, sd {s['oe_count_sd']:.2f})")
        print(f"  per-task label stability: {s['tasks_flipped']}/{s['tasks_compared']} tasks "
              f"flipped over-eager across reps  (agreement {s['label_agreement']:.0%})")
        print(f"  recall mean {s['recall_mean']:.2f}   timid mean {s['timid_mean']:.0%}")
    # ---- between-model comparison at the REP level ----
    # the correct unit for stochastic agents: treat each run's rate as one observation,
    # rather than the single-run per-task chi-square that treats one noisy draw as truth.
    repcmp = None
    if len(out) == 2 and all(o["reps"] >= 2 for o in out):
        import scipy.stats as st
        a, b = out
        ra = [r*100 for r in a["oe_rates"]]; rb = [r*100 for r in b["oe_rates"]]
        U, pu = st.mannwhitneyu(ra, rb, alternative="two-sided")
        t, pt = st.ttest_ind(ra, rb, equal_var=False)
        verdict = ("borderline (~0.05)" if min(pu, pt) < 0.05 <= max(pu, pt)
                   else "significant" if max(pu, pt) < 0.05 else "n.s.")
        repcmp = {"models": [a["model"], b["model"]], "n_reps": a["reps"],
                  "means": [a["oe_rate_mean"], b["oe_rate_mean"]],
                  "mannwhitney_p": pu, "welch_p": pt, "verdict": verdict}
        print(f"\n{'='*64}\nBETWEEN-MODEL @ rep level "
              f"({a['model']} vs {b['model']}, n={a['reps']} reps each)")
        print(f"  mean over-eager {a['oe_rate_mean']:.0%} vs {b['oe_rate_mean']:.0%}  |  "
              f"Mann-Whitney p={pu:.3f}  Welch-t p={pt:.3f}  -> {verdict}")

    json.dump({"per_model": out, "between_model_rep_level": repcmp},
              open(os.path.join(RES, "step3_variability.json"), "w"), indent=2)

    # ---- plot: over-eager rate, each rep a dot, mean bar, per model ----
    fig, ax = plt.subplots(figsize=(7.5, 5))
    for i, s in enumerate(out):
        c = CCOLOR.get(cohort_of(s["model"]), "#7570b3")
        xs = [i + (j - (s["reps"]-1)/2) * 0.12 for j in range(s["reps"])]
        ax.scatter(xs, s["oe_rates"], s=90, color=c, edgecolor="black", zorder=3)
        ax.hlines(s["oe_rate_mean"], i - 0.25, i + 0.25, color=c, lw=2.5)
        ax.text(i, max(s["oe_rates"]) + 0.03,
                f"mean {s['oe_rate_mean']:.0%}\n±{s['oe_rate_sd']*100:.0f}pp", ha="center", fontsize=9)
    ax.set_xticks(range(len(out))); ax.set_xticklabels([s["model"] for s in out], fontsize=9)
    ax.set_ylim(0, max(max(s["oe_rates"]) for s in out) + 0.12)
    ax.set_ylabel("over-eager rate")
    ax.set_title(f"Run-to-run variability of the frontier models "
                 f"(n={out[0]['reps']} reps; agentic CLIs have no seed)\n"
                 "each dot = one 50-task run; bar = mean", fontsize=10)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout(); fig.savefig(os.path.join(RES, "step3_variability.png"), dpi=140)
    print("\nwrote step3_variability.json + step3_variability.png")


if __name__ == "__main__":
    main()
