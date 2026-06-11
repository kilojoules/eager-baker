"""step5_crossmodel_plot.py — knowledge (AUC) vs calibration across models.
Two panels: boundary AUC (≈equal = both KNOW the boundary) and greedy over-eager /
optimal decision point (very different = calibration differs). The over-eagerness
gap is driven by calibration, not knowledge."""
import os, json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.normpath(os.path.join(HERE, "..", "results"))


def main():
    rows = json.load(open(os.path.join(RES, "step5_crossmodel.json")))
    label = {"qwen14": "Qwen2.5-14B", "qwen25": "Qwen2.5-7B", "phi": "Phi-3.5-mini"}
    order = {"qwen14": 0, "qwen25": 1, "phi": 2}
    rows.sort(key=lambda r: order.get(r["name"], 9))
    names = [label.get(r["name"], r["name"]) for r in rows]
    x = range(len(rows))
    col = ["#1b9e77", "#7570b3", "#e7298a"][:len(rows)]

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 5))
    # panel 1: AUC (knowledge)
    a1.bar(x, [r["auc"] for r in rows], color=col, alpha=0.85)
    for i, r in enumerate(rows):
        a1.text(i, r["auc"] + 0.01, f"{r['auc']:.2f}", ha="center", fontsize=11)
    a1.set_xticks(list(x)); a1.set_xticklabels(names, fontsize=9)
    a1.set_ylim(0, 1.05); a1.set_ylabel("boundary AUC")
    a1.set_title("KNOWLEDGE: do they locate the boundary?\n(≈ equal — yes, all do)")
    a1.axhline(0.5, color="grey", ls=":", lw=1); a1.grid(axis="y", alpha=0.3)

    # panel 2: greedy over-eager (calibration consequence) + optimal threshold
    a2.bar(x, [r["greedy_oe"] for r in rows], color=col, alpha=0.85)
    for i, r in enumerate(rows):
        a2.text(i, r["greedy_oe"] + 0.02,
                f"{r['greedy_oe']:.0%}\n(opt thr {r['opt_logit_thr']:+.0f})",
                ha="center", fontsize=9)
    a2.set_xticks(list(x)); a2.set_xticklabels(names, fontsize=9)
    a2.set_ylim(0, 1.05); a2.set_ylabel("greedy over-eager rate (P(IN)>0.5)")
    a2.set_title("CALIBRATION: does greedy decoding overstep?\n"
                 "(very different — over-confidence drives over-eagerness)")
    a2.grid(axis="y", alpha=0.3)

    fig.suptitle("Equal boundary knowledge, different calibration → different "
                 "over-eagerness (n=2 models; Qwen3-30B/14B failed to load)",
                 fontsize=11)
    fig.tight_layout(); fig.savefig(os.path.join(RES, "step5_crossmodel.png"), dpi=140)
    print("wrote step5_crossmodel.png")


if __name__ == "__main__":
    main()
