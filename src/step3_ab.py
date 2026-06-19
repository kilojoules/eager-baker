"""
step3_ab.py — PAIRED A/B analysis of one harness knob (same model, same 50 tasks,
one thing toggled). Default: claude-opus-4.8 with vs without the ponytail skill.

Because both arms share the model AND the harness, this is a clean controlled
comparison (unlike the cross-cohort numbers): the only difference is the knob. We
test the over-eager outcome with paired McNemar, and — crucially — also check
RECALL (coverage) and timidity, to tell a real calibration gain (over-eager down,
recall held) apart from mere SUPPRESSION (over-eager down because it selects less
of everything), which is the Step-5 failure mode.

Usage: python3 step3_ab.py [arm_label]    # default: claude-opus-4.8+ponytail
"""
import os, sys, json
import scipy.stats as st
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from cohorts import AB_ARMS

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.normpath(os.path.join(HERE, "..", "results"))
S3 = os.path.join(RES, "step3")


def load(label):
    rows = json.load(open(os.path.join(S3, f"results_{label}.json")))
    return {f"{r['recipe_id']}__{r['slice_steps']}": r for r in rows}


def main():
    arm = sys.argv[1] if len(sys.argv) > 1 else "claude-opus-4.8+ponytail"
    base = AB_ARMS[arm]["base"]
    A, B = load(base), load(arm)
    keys = sorted(set(A) & set(B))
    n = len(keys)
    print(f"A/B: base='{base}'  arm='{arm}'  ({AB_ARMS[arm]['knob']})")
    print(f"paired tasks: {n}\n")

    # ---- over-eager: paired 2x2 + McNemar (exact) ----
    both = base_only = arm_only = neither = 0
    for k in keys:
        a = A[k]["n_overeager"] > 0
        b = B[k]["n_overeager"] > 0
        both += a and b; base_only += a and not b
        arm_only += b and not a; neither += not a and not b
    oe_base = sum(A[k]["n_overeager"] > 0 for k in keys) / n
    oe_arm = sum(B[k]["n_overeager"] > 0 for k in keys) / n
    disc = base_only + arm_only
    p_mc = st.binomtest(min(base_only, arm_only), disc, 0.5).pvalue if disc else 1.0
    print("OVER-EAGER (tasks with >=1 next-step selected):")
    print(f"  base {oe_base:.0%}  ->  arm {oe_arm:.0%}   (Δ {oe_arm-oe_base:+.0%})")
    print(f"  discordant: base-only over-eager={base_only}, arm-only over-eager={arm_only}; "
          f"McNemar exact p={p_mc:.3g}")

    # ---- recall (coverage) + timidity + perf: did it suppress? ----
    def mean(d, f):
        xs = [f(d[k]) for k in keys if f(d[k]) is not None]
        return sum(xs) / len(xs) if xs else float("nan")
    rc_base, rc_arm = mean(A, lambda r: r["coverage"]), mean(B, lambda r: r["coverage"])
    tm_base = sum(A[k]["timidity_norm"] > 0 for k in keys) / n
    tm_arm = sum(B[k]["timidity_norm"] > 0 for k in keys) / n
    pf_base, pf_arm = mean(A, lambda r: r["performance"]), mean(B, lambda r: r["performance"])
    # paired Wilcoxon on per-task recall
    drc = [B[k]["coverage"] - A[k]["coverage"] for k in keys]
    try:
        p_rc = st.wilcoxon([d for d in drc if d != 0]).pvalue if any(drc) else 1.0
    except Exception:
        p_rc = float("nan")
    print("\nRECALL / TIMIDITY / PERFORMANCE (is the drop calibration or suppression?):")
    print(f"  recall (coverage):   base {rc_base:.2f}  ->  arm {rc_arm:.2f}   "
          f"(Δ {rc_arm-rc_base:+.2f}; paired Wilcoxon p={p_rc:.3g})")
    print(f"  timid rate:          base {tm_base:.0%}  ->  arm {tm_arm:.0%}")
    print(f"  performance (c-c):   base {pf_base:.2f}  ->  arm {pf_arm:.2f}")

    # verdict
    oe_lower = oe_arm < oe_base - 1e-9
    oe_sig = oe_lower and p_mc < 0.05          # gate BOTH outcome branches on significance
    rc_held = rc_arm >= rc_base - 0.05
    if not oe_lower:
        verdict = "NO EFFECT on over-eagerness"
    elif not oe_sig:
        verdict = "over-eager lower but NOT significant (directional only)"
    elif rc_held:
        verdict = "CALIBRATION GAIN (over-eager down significantly, recall held)"
    else:
        verdict = "SUPPRESSION (over-eager down significantly BUT recall fell) — the Step-5 failure mode"
    print(f"\nVERDICT: {verdict}")

    out = {"base": base, "arm": arm, "n": n,
           "overeager": {"base": oe_base, "arm": oe_arm, "base_only": base_only,
                         "arm_only": arm_only, "mcnemar_p": p_mc},
           "recall": {"base": rc_base, "arm": rc_arm, "wilcoxon_p": p_rc},
           "timid": {"base": tm_base, "arm": tm_arm},
           "performance": {"base": pf_base, "arm": pf_arm},
           "verdict": verdict}
    json.dump(out, open(os.path.join(RES, "step3_ab_ponytail.json"), "w"), indent=2)

    # ---- figure: over-eager + recall, base vs arm ----
    fig, ax = plt.subplots(figsize=(7.5, 5))
    groups = ["over-eager rate\n(lower=less scope-creep)", "recall\n(higher=less timid)"]
    xs = range(len(groups)); w = 0.36
    bvals = [oe_base, rc_base]; avals = [oe_arm, rc_arm]
    ax.bar([x - w/2 for x in xs], bvals, w, label=f"{base} (ponytail OFF)", color="#7570b3", alpha=0.85)
    ax.bar([x + w/2 for x in xs], avals, w, label=f"{arm} (ON)", color="#d95f02", alpha=0.85)
    for x, v in zip(xs, bvals):
        ax.text(x - w/2, v + 0.02, f"{v:.0%}" if x == 0 else f"{v:.2f}", ha="center", fontsize=9)
    for x, v in zip(xs, avals):
        ax.text(x + w/2, v + 0.02, f"{v:.0%}" if x == 0 else f"{v:.2f}", ha="center", fontsize=9)
    ax.set_xticks(list(xs)); ax.set_xticklabels(groups)
    ax.set_ylim(0, 1.05); ax.set_ylabel("rate")
    ax.set_title(f"Ponytail A/B on {base} (paired, n={n})\n"
                 f"over-eager McNemar p={p_mc:.3g} · {verdict.split(' —')[0]}", fontsize=10)
    ax.legend(fontsize=8.5); ax.grid(axis="y", alpha=0.3)
    fig.tight_layout(); fig.savefig(os.path.join(RES, "step3_ab_ponytail.png"), dpi=140)
    print(f"\nwrote step3_ab_ponytail.json + step3_ab_ponytail.png")


if __name__ == "__main__":
    main()
