"""step5_plot.py — intervention arms on the (over-eagerness, in-scope recall)
plane. The pre-registered success region is: LEFT of baseline over-eagerness AND
within the recall tolerance band. Arms that cut overrun but fall BELOW the band
are suppression, not calibration."""
import os, json, glob
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from slicer import make_task
from menu_harness import build_menu

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.normpath(os.path.join(HERE, "..", "results"))
TOL = 0.05
COL = {"baseline": "#444", "anchor": "#1b9e77", "fewshot": "#7570b3",
       "flag": "#d95f02", "guided": "#e7298a", "consequence": "#66a61e"}


def stats(rows):
    n = len(rows)
    oe = sum(r["n_overeager"] > 0 for r in rows)/n
    rc = sum(r["coverage"] for r in rows)/n
    return oe, rc


def main():
    base = json.load(open(os.path.join(RES, "step3", "results_phi-3.5-mini.json")))
    b_oe, b_rc = stats(base)
    pts = [("baseline", b_oe, b_rc)]
    for f in sorted(glob.glob(os.path.join(RES, "step5", "results_*.json"))):
        arm = os.path.basename(f)[len("results_"):-len(".json")]
        oe, rc = stats(json.load(open(f)))
        pts.append((arm, oe, rc))

    fig, ax = plt.subplots(figsize=(8.5, 6.5))
    # held-recall band (success requires recall >= baseline - TOL)
    ax.axhspan(b_rc - TOL, 1.0, color="#d9f0d3", alpha=0.5, zorder=0,
               label=f"held-recall band (≥ baseline−{TOL})")
    ax.axhline(b_rc, color="grey", ls=":", lw=1)
    ax.axvline(b_oe, color="grey", ls="--", lw=1)
    # success region annotation: left of baseline overrun AND in band
    ax.axvspan(0, b_oe, ymin=(b_rc - TOL), ymax=1.0, color="#b8e0a0",
               alpha=0.25, zorder=0)
    for arm, oe, rc in pts:
        ax.scatter([oe], [rc], s=180, c=COL.get(arm, "#000"),
                   edgecolors="black", zorder=4)
        ax.annotate(arm, (oe, rc), textcoords="offset points", xytext=(8, 6),
                    fontsize=10, fontweight="bold")
    ax.set_xlim(0, 0.8); ax.set_ylim(0.35, 0.75)
    ax.set_xlabel("over-eagerness (next-step overrun rate) → lower is the goal")
    ax.set_ylabel("in-scope recall (suppression guard) → must be held")
    ax.set_title("phi-3.5-mini interventions: every overrun reduction came with a "
                 "recall drop\n(no arm lands in the success region = left-of-baseline "
                 "AND in the recall band)")
    ax.legend(loc="lower left", fontsize=9)
    ax.grid(alpha=0.25)
    fig.tight_layout(); fig.savefig(os.path.join(RES, "step5_intervention.png"), dpi=140)
    print("wrote step5_intervention.png")
    print("baseline overrun=%.0f%% recall=%.2f" % (b_oe*100, b_rc))


if __name__ == "__main__":
    main()
