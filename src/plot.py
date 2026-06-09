"""plot.py — the scope-calibration 2D plot:
   x = signed scope calibration (<0 timid, ~0 calibrated, >0 over-eager)
   y = performance (conditional-correctness)
Per-task points + per-regime means. Optionally split by coupled/benign regime.
"""
import os, csv, math
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.normpath(os.path.join(HERE, "..", "results"))

COLORS = {"cautious": "#2166ac", "eager": "#b2182b"}


def load(path):
    rows = []
    with open(path) as f:
        for r in csv.DictReader(f):
            r["performance"] = None if r["performance"] in ("", "None") else float(r["performance"])
            r["signed_scope"] = float(r["signed_scope"])
            rows.append(r)
    return rows


def plot(rows, out_png, title, regime_field="regime"):
    fig, ax = plt.subplots(figsize=(8.5, 6.5))
    # calibrated target region (x≈0, high y)
    ax.axvspan(-0.08, 0.08, color="#d9f0d3", alpha=0.6, zorder=0,
               label="calibrated band (x≈0)")
    ax.axvline(0, color="grey", lw=1, ls="--", zorder=1)

    regimes = sorted({r[regime_field] for r in rows})
    for regime in regimes:
        rs = [r for r in rows if r[regime_field] == regime]
        # NA performance plotted at y=-0.06 with a hollow marker
        xs = [r["signed_scope"] for r in rs]
        ys = [(-0.06 if r["performance"] is None else r["performance"]) for r in rs]
        na = [r["performance"] is None for r in rs]
        c = COLORS.get(regime, None)
        for x, y, is_na in zip(xs, ys, na):
            ax.scatter([x], [y], s=70, alpha=0.75, c=c,
                       marker=("x" if is_na else "o"),
                       edgecolors="none", zorder=3)
        # regime mean (performance over non-NA)
        perfs = [r["performance"] for r in rs if r["performance"] is not None]
        if perfs:
            mx = sum(r["signed_scope"] for r in rs) / len(rs)
            my = sum(perfs) / len(perfs)
            ax.scatter([mx], [my], s=340, c=c, marker="*",
                       edgecolors="black", linewidths=1.3, zorder=5,
                       label=f"{regime} (mean)")
            ax.annotate(regime, (mx, my), textcoords="offset points",
                        xytext=(10, 8), fontsize=11, fontweight="bold", color=c)

    ax.set_xlim(-1.05, 1.05)
    ax.set_ylim(-0.12, 1.05)
    ax.set_xlabel("← timid        signed scope calibration "
                  "(over_eagerness − timidity)        over-eager →", fontsize=11)
    ax.set_ylabel("performance  (conditional-correctness)", fontsize=11)
    ax.set_title(title, fontsize=12)
    ax.text(-1.0, 1.0, "did LESS than asked", fontsize=9, color="#2166ac", va="top")
    ax.text(1.0, 1.0, "did MORE than asked", fontsize=9, color="#b2182b",
            va="top", ha="right")
    ax.text(0, -0.10, "x = NA performance (no in-scope attempts)", fontsize=8,
            color="grey", ha="center")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="lower right", fontsize=9, framealpha=0.9)
    fig.tight_layout()
    fig.savefig(out_png, dpi=140)
    print("wrote", out_png)


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 4:
        rows = load(os.path.join(RES, sys.argv[1]))
        plot(rows, os.path.join(RES, sys.argv[2]), sys.argv[3])
    else:
        rows = load(os.path.join(RES, "pilot_results.csv"))
        plot(rows, os.path.join(RES, "pilot_plot.png"),
             "Scope calibration vs. performance — raw-MCL pilot (8×2, Sonnet)")
