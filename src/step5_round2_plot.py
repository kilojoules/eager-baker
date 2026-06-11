"""step5_round2_plot.py — Round-2 result on the (over-eagerness, in-scope recall)
plane: behavioural arms (ballot, two-pass) + the logprob threshold-sweep curve +
the rank-based operating points. The punchline: oracle rank selection lands in the
success region (boundary is recoverable), so over-eagerness is a decoding/
calibration bottleneck, not a knowledge ceiling (boundary AUC=0.877)."""
import os, json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.normpath(os.path.join(HERE, "..", "results"))
B_OE, B_RC, TOL = 0.72, 0.54, 0.05


def main():
    sweep = json.load(open(os.path.join(RES, "step5_probe.json")))["sweep"]
    auc = json.load(open(os.path.join(RES, "step5_probe.json")))["auc"]
    fig, ax = plt.subplots(figsize=(9, 6.5))
    # success region: left of baseline overrun AND recall held
    ax.axhspan(B_RC - TOL, 1.0, xmin=0, xmax=B_OE, color="#d9f0d3", alpha=0.5, zorder=0)
    ax.axhline(B_RC, color="grey", ls=":", lw=1); ax.axvline(B_OE, color="grey", ls="--", lw=1)
    ax.text(0.02, 0.72, "SUCCESS REGION\n(less overstep,\nheld recall)", fontsize=9,
            color="#2a7", va="center")

    # threshold-sweep operating curve (global threshold on P(IN))
    xs = [s["overeager_rate"] for s in sweep]; ys = [s["recall"] for s in sweep]
    ax.plot(xs, ys, "-", color="#888", lw=1, alpha=0.7, zorder=2,
            label=f"global P(IN) threshold sweep (flat — saturated probs)")

    pts = [
        ("baseline (one-shot select)", B_OE, B_RC, "#444", "o"),
        ("C1 ballot (per-item IN/OUT)", 0.92, 0.74, "#e7298a", "o"),
        ("C2 two-pass (act=THIS_STEP)", 0.64, 0.43, "#d95f02", "o"),
        ("rank: gap-cut (deploy-realistic)", 0.88, 0.91, "#7570b3", "s"),
        ("rank: oracle top-n_in", 0.52, 0.64, "#1b9e77", "*"),
    ]
    for name, oe, rc, c, mk in pts:
        ax.scatter([oe], [rc], s=(420 if mk == "*" else 150), c=c, marker=mk,
                   edgecolors="black", linewidths=1.2, zorder=5, label=name)

    ax.set_xlim(0, 1.0); ax.set_ylim(0.3, 1.0)
    ax.set_xlabel("over-eagerness (next-step overrun rate) → lower is the goal")
    ax.set_ylabel("in-scope recall → must be held")
    ax.set_title(f"Round 2: the boundary IS in phi's logits (AUC={auc:.2f}) but greedy "
                 f"decoding can't\nexpress it — rank selection reaches the success "
                 f"region; it's a decoding/calibration bottleneck, not a ceiling")
    ax.legend(loc="lower right", fontsize=8.5, framealpha=0.95)
    ax.grid(alpha=0.25)
    fig.tight_layout(); fig.savefig(os.path.join(RES, "step5_round2.png"), dpi=140)
    print("wrote step5_round2.png")


if __name__ == "__main__":
    main()
