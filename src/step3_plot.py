"""step3_plot.py — Step-3 figures, COHORT-AWARE (see cohorts.py).

The open-weights (vLLM, pre-registered) and frontier (agentic-CLI, exploratory)
cohorts are drawn as visually separated groups and are NOT pooled into one stat —
a between-cohort gap conflates model capability with the harness.
"""
import os, json, glob, math
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from cohorts import COHORTS, COHORT_ORDER, cohort_of, base_models_present

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.normpath(os.path.join(HERE, "..", "results"))
S3 = os.path.join(RES, "step3")

CCOLOR = {"open-vLLM": "#1b9e77", "frontier-agentic": "#7570b3"}
CMARK = {"open-vLLM": "o", "frontier-agentic": "*"}


def wilson(k, n, z=1.96):
    if n == 0:
        return (0, 0)
    p = k/n; d = 1+z*z/n
    c = (p+z*z/(2*n))/d
    h = z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return (max(0, c-h), min(1, c+h))


def load():
    tags = {f"{t['recipe_id']}__{t['i']}_{t['j']}": t.get("tag", "unknown")
            for t in json.load(open(os.path.join(RES, "step3_taskset_tagged.json")))}
    models = {}
    for f in sorted(glob.glob(os.path.join(S3, "results_*.json"))):
        rows = json.load(open(f))
        for r in rows:
            r["tag"] = tags.get(f"{r['recipe_id']}__{r['slice_steps'].replace('-','_')}", "unknown")
        models[rows[0]["model"]] = rows
    return models


def layout(names):
    """x positions grouped by cohort with a gap between cohorts."""
    xpos, groups, x = {}, [], 0
    for cid in COHORT_ORDER:
        ms = [m for m in names if cohort_of(m) == cid]
        if not ms:
            continue
        start = x
        for m in ms:
            xpos[m] = x; x += 1
        groups.append((cid, start, x - 1))
        x += 1.2   # gap between cohorts
    return xpos, groups


def main():
    models = load()
    names = base_models_present(models)   # cohort figures: base models only (A/B arms handled in step3_ab.py)
    xpos, groups = layout(names)

    # ---- Figure 1: primary over-eager rate, cohorts separated ----
    fig, ax = plt.subplots(figsize=(9, 5.5))
    top = 1.05
    for m in names:
        rows = models[m]; n = len(rows); cid = cohort_of(m)
        k = sum(1 for r in rows if r["n_overeager"] > 0)
        p = k / n
        se = math.sqrt(p * (1 - p) / n)            # standard error of the proportion
        ax.bar(xpos[m], p, color=CCOLOR[cid], alpha=0.85, width=0.8)
        ax.errorbar(xpos[m], p, yerr=[[min(se, p)], [se]], color="black", capsize=6, lw=1.5)
        ax.text(xpos[m], p + se + 0.02, f"{k}/{n}={p:.0%}", ha="center", fontsize=10)
    for cid, a, b in groups:
        ax.axvspan(a-0.55, b+0.55, color=CCOLOR[cid], alpha=0.06, zorder=0)
        ax.text((a+b)/2, top-0.02, COHORTS[cid]["label"], ha="center", va="top",
                fontsize=9, style="italic", color=CCOLOR[cid])
    ax.set_xticks([xpos[m] for m in names]); ax.set_xticklabels(names, rotation=12, fontsize=9)
    ax.set_ylabel("over-eager rate (tasks with ≥1 next-step selected; bars ±1 SE)")
    ax.set_ylim(0, top)
    ax.set_title("PRIMARY: over-eagerness by model — cohorts kept separate\n"
                 "open-weights/vLLM = pre-registered  ·  frontier/agentic-CLI = exploratory, confounded "
                 "(not pooled)", fontsize=10)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout(); fig.savefig(os.path.join(RES, "step3_overeager_rate.png"), dpi=140)
    print("wrote step3_overeager_rate.png")

    # ---- Figure 1b: performance vs over-eagerness (one point per model) ----
    fig, ax = plt.subplots(figsize=(8.5, 6))
    for m in names:
        rows = models[m]; n = len(rows); cid = cohort_of(m)
        k = sum(1 for r in rows if r["n_overeager"] > 0); rate = k/n
        rlo, rhi = wilson(k, n)
        perfs = [r["performance"] for r in rows if r["performance"] is not None]
        mp = sum(perfs)/len(perfs)
        sd = (sum((x-mp)**2 for x in perfs)/(len(perfs)-1))**0.5 if len(perfs) > 1 else 0
        pse = 1.96*sd/math.sqrt(len(perfs)) if perfs else 0
        ax.errorbar(rate, mp, xerr=[[rate-rlo], [rhi-rate]], yerr=pse,
                    fmt=CMARK[cid], ms=(20 if cid == "frontier-agentic" else 13),
                    color=CCOLOR[cid], capsize=5, lw=1.5,
                    markeredgecolor="black", zorder=3)
        ax.annotate(f" {m}\n {rate:.0%} over-eager, perf {mp:.2f}",
                    (rate, mp), textcoords="offset points", xytext=(10, -4),
                    fontsize=8.5, va="center")
    ax.set_xlim(-0.02, 1.0); ax.set_ylim(0.80, 1.01)
    ax.set_xlabel("over-eagerness  →  (rate of tasks with ≥1 unrequested next step)")
    ax.set_ylabel("performance (conditional-correctness)")
    handles = [Line2D([0], [0], marker=CMARK[c], color="w", markerfacecolor=CCOLOR[c],
                      markeredgecolor="black", markersize=13, label=COHORTS[c]["label"])
               for c in COHORT_ORDER]
    ax.legend(handles=handles, loc="lower left", fontsize=8.5, framealpha=0.9)
    ax.set_title("Performance vs over-eagerness — two cohorts, not pooled\n"
                 "frontier (agentic CLI) cluster low/high; open-weights (vLLM) span the over-eager axis",
                 fontsize=10)
    ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(os.path.join(RES, "step3_perf_vs_eager.png"), dpi=140)
    print("wrote step3_perf_vs_eager.png")

    # ---- Figure 2: 2D scatter signed-scope vs performance (color by cohort) ----
    fig, ax = plt.subplots(figsize=(9, 6.5))
    ax.axvspan(-0.05, 0.05, color="#d9f0d3", alpha=0.6, zorder=0)
    ax.axvline(0, color="grey", ls="--", lw=1)
    for m in names:
        rows = models[m]; cid = cohort_of(m)
        xs = [r["signed_scope"] for r in rows]
        ys = [(-0.06 if r["performance"] is None else r["performance"]) for r in rows]
        ax.scatter(xs, ys, s=42, alpha=0.45, c=CCOLOR[cid],
                   marker=CMARK[cid], label=None)
        perfs = [r["performance"] for r in rows if r["performance"] is not None]
        mx = sum(xs)/len(xs); my = sum(perfs)/len(perfs)
        ax.scatter([mx], [my], s=(420 if cid == "frontier-agentic" else 300),
                   marker=CMARK[cid], c=CCOLOR[cid], edgecolors="black",
                   linewidths=1.3, zorder=5)
        ax.annotate(f" {m}", (mx, my), fontsize=8, xytext=(6, 4),
                    textcoords="offset points")
    ax.set_xlim(-1.05, 1.05); ax.set_ylim(-0.12, 1.05)
    ax.set_xlabel("← timid    signed scope calibration    over-eager →")
    ax.set_ylabel("performance (conditional-correctness)")
    handles = [Line2D([0], [0], marker=CMARK[c], color="w", markerfacecolor=CCOLOR[c],
                      markeredgecolor="black", markersize=13, label=COHORTS[c]["label"])
               for c in COHORT_ORDER]
    ax.legend(handles=handles, loc="lower left", fontsize=8.5)
    ax.set_title("Scope calibration vs performance — Step 3 (cohorts colored separately)")
    ax.grid(alpha=0.25)
    fig.tight_layout(); fig.savefig(os.path.join(RES, "step3_scatter.png"), dpi=140)
    print("wrote step3_scatter.png")

    # ---- Figure 3: coupled vs benign over-eager rate, per model ----
    fig, ax = plt.subplots(figsize=(9.5, 5))
    w = 0.38
    for m in names:
        rows = models[m]; cid = cohort_of(m)
        for j, tg in enumerate(("benign", "coupled")):
            sub = [r for r in rows if r["tag"] == tg]
            if sub:
                k = sum(1 for r in sub if r["n_overeager"] > 0)
                ax.bar(xpos[m] + (j-0.5)*w, k/len(sub), w, color=CCOLOR[cid],
                       alpha=0.85 if tg == "benign" else 0.45,
                       hatch="" if tg == "benign" else "//")
                ax.text(xpos[m]+(j-0.5)*w, k/len(sub)+0.02, f"{k}/{len(sub)}", ha="center", fontsize=8)
    for cid, a, b in groups:
        ax.axvspan(a-0.55, b+0.55, color=CCOLOR[cid], alpha=0.06, zorder=0)
    ax.set_xticks([xpos[m] for m in names]); ax.set_xticklabels(names, rotation=12, fontsize=9)
    ax.set_ylabel("over-eager rate"); ax.set_ylim(0, 1.05)
    ax.set_title("Over-eager rate: benign (solid) vs coupled/destructive (hatched) — descriptive")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout(); fig.savefig(os.path.join(RES, "step3_coupled_facet.png"), dpi=140)
    print("wrote step3_coupled_facet.png")


if __name__ == "__main__":
    main()
