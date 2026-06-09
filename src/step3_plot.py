"""step3_plot.py — Step-3 figures: primary over-eager-rate bars (95% CI),
2D scatter (signed scope vs performance) per model, and coupled/benign facet."""
import os, json, glob, math
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.normpath(os.path.join(HERE, "..", "results"))
S3 = os.path.join(RES, "step3")
COLORS = ["#1b9e77", "#d95f02", "#7570b3", "#e7298a"]


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


def main():
    models = load()
    names = list(models)

    # ---- Figure 1: primary over-eager rate per model, with 95% CI ----
    fig, ax = plt.subplots(figsize=(7, 5))
    for i, m in enumerate(names):
        rows = models[m]; n = len(rows)
        k = sum(1 for r in rows if r["n_overeager"] > 0)
        lo, hi = wilson(k, n)
        ax.bar(i, k/n, color=COLORS[i % 4], alpha=0.85)
        ax.errorbar(i, k/n, yerr=[[k/n-lo], [hi-k/n]], color="black", capsize=6, lw=1.5)
        ax.text(i, k/n+0.02, f"{k}/{n}={k/n:.0%}", ha="center", fontsize=10)
    ax.set_xticks(range(len(names))); ax.set_xticklabels(names, rotation=10, fontsize=9)
    ax.set_ylabel("over-eager rate (tasks with ≥1 next-step selected)")
    ax.set_ylim(0, 1.05)
    ax.set_title("PRIMARY: over-eagerness rate by model (95% Wilson CI)")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout(); fig.savefig(os.path.join(RES, "step3_overeager_rate.png"), dpi=140)
    print("wrote step3_overeager_rate.png")

    # ---- Figure 2: 2D scatter signed-scope vs performance ----
    fig, ax = plt.subplots(figsize=(8.5, 6.5))
    ax.axvspan(-0.05, 0.05, color="#d9f0d3", alpha=0.6, zorder=0)
    ax.axvline(0, color="grey", ls="--", lw=1)
    for i, m in enumerate(names):
        rows = models[m]
        xs = [r["signed_scope"] for r in rows]
        ys = [(-0.06 if r["performance"] is None else r["performance"]) for r in rows]
        ax.scatter([x+ (i-1)*0.004 for x in xs], ys, s=45, alpha=0.5, c=COLORS[i % 4], label=m)
        perfs = [r["performance"] for r in rows if r["performance"] is not None]
        mx = sum(xs)/len(xs); my = sum(perfs)/len(perfs)
        ax.scatter([mx], [my], s=350, marker="*", c=COLORS[i % 4],
                   edgecolors="black", linewidths=1.3, zorder=5)
    ax.set_xlim(-1.05, 1.05); ax.set_ylim(-0.12, 1.05)
    ax.set_xlabel("← timid    signed scope calibration    over-eager →")
    ax.set_ylabel("performance (conditional-correctness)")
    ax.set_title("Scope calibration vs performance — Step 3 (3 models, n=50, menu)")
    ax.legend(loc="lower left", fontsize=9); ax.grid(alpha=0.25)
    fig.tight_layout(); fig.savefig(os.path.join(RES, "step3_scatter.png"), dpi=140)
    print("wrote step3_scatter.png")

    # ---- Figure 3: coupled vs benign over-eager rate, per model ----
    fig, ax = plt.subplots(figsize=(8, 5))
    w = 0.35
    for i, m in enumerate(names):
        rows = models[m]
        for j, tg in enumerate(("benign", "coupled")):
            sub = [r for r in rows if r["tag"] == tg]
            if sub:
                k = sum(1 for r in sub if r["n_overeager"] > 0)
                ax.bar(i + (j-0.5)*w, k/len(sub), w, color=COLORS[i % 4],
                       alpha=0.85 if tg == "benign" else 0.45,
                       hatch="" if tg == "benign" else "//")
                ax.text(i+(j-0.5)*w, k/len(sub)+0.02, f"{k}/{len(sub)}", ha="center", fontsize=8)
    ax.set_xticks(range(len(names))); ax.set_xticklabels(names, rotation=10, fontsize=9)
    ax.set_ylabel("over-eager rate"); ax.set_ylim(0, 1.05)
    ax.set_title("Over-eager rate: benign (solid) vs coupled/destructive (hatched) — descriptive")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout(); fig.savefig(os.path.join(RES, "step3_coupled_facet.png"), dpi=140)
    print("wrote step3_coupled_facet.png")


if __name__ == "__main__":
    main()
