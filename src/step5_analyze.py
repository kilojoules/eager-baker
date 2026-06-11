"""
step5_analyze.py — paired analysis of intervention arms vs baseline (phi, n=50).
Applies the PRE-REGISTERED success criterion (INTERVENTION_PLAN.md) mechanically.
"""
import os, json, glob, math
import scipy.stats as st
from slicer import make_task
from menu_harness import build_menu

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.normpath(os.path.join(HERE, "..", "results"))
RECALL_TOL = 0.05    # pre-registered: recall may drop by at most this


def distractor_count(rid, i, j, selected):
    menu = {m.label: m for m in build_menu(make_task(rid, i, j))}
    return sum(1 for l in selected if menu.get(l) and menu[l].kind == "distractor")


def rowkey(r):
    ss = r["slice_steps"]; return f"{r['recipe_id']}__{ss.replace('-', '_')}"


def index(rows):
    out = {}
    for r in rows:
        i, j = r["slice_steps"].split("-")
        sel = set(r["selected"].split("|")) if r["selected"] else set()
        out[rowkey(r)] = {
            "overrun": r["n_overeager"] > 0,
            "recall": r["coverage"],
            "perf": r["performance"],
            "distractor": distractor_count(r["recipe_id"], int(i), int(j), sel) > 0,
            "n_flagged": r.get("n_flagged", 0),
        }
    return out


def mcnemar_exact(b, c):
    """exact McNemar p (two-sided) on discordant counts b, c."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    p = 2*sum(math.comb(n, x) for x in range(0, k+1))*(0.5**n)
    return min(1.0, p)


def main():
    base = index(json.load(open(os.path.join(RES, "step3", "results_phi-3.5-mini.json"))))
    arms = {}
    for f in sorted(glob.glob(os.path.join(RES, "step5", "results_*.json"))):
        arm = os.path.basename(f)[len("results_"):-len(".json")]
        arms[arm] = index(json.load(open(f)))

    keys = sorted(base)
    b_oe = sum(base[k]["overrun"] for k in keys)/len(keys)
    b_rc = sum(base[k]["recall"] for k in keys)/len(keys)
    b_di = sum(base[k]["distractor"] for k in keys)/len(keys)
    b_pf = sum(base[k]["perf"] for k in keys if base[k]["perf"] is not None)/ \
        sum(1 for k in keys if base[k]["perf"] is not None)
    print(f"BASELINE (phi, n={len(keys)}): over-eager {b_oe:.0%}  recall {b_rc:.2f}  "
          f"distractor {b_di:.0%}  perf {b_pf:.2f}\n")
    print(f"{'arm':12s} {'over-eager':>11} {'Δrecall':>8} {'McNemar p':>10} "
          f"{'distractor':>10} {'perf':>5} {'flag':>5}  verdict")
    print("-"*84)

    results = []
    for arm in [a for a in ["anchor", "fewshot", "flag", "guided", "consequence",
                            "ballot", "twopass"] if a in arms]:
        A = arms[arm]
        ks = [k for k in keys if k in A]
        oe = sum(A[k]["overrun"] for k in ks)/len(ks)
        rc = sum(A[k]["recall"] for k in ks)/len(ks)
        di = sum(A[k]["distractor"] for k in ks)/len(ks)
        pf = sum(A[k]["perf"] for k in ks if A[k]["perf"] is not None)/ \
            sum(1 for k in ks if A[k]["perf"] is not None)
        fl = sum(A[k]["n_flagged"] for k in ks)/len(ks)
        # paired McNemar on overrun
        b_disc = sum(base[k]["overrun"] and not A[k]["overrun"] for k in ks)  # base yes, arm no
        c_disc = sum(A[k]["overrun"] and not base[k]["overrun"] for k in ks)  # arm yes, base no
        p = mcnemar_exact(b_disc, c_disc)
        drecall = rc - b_rc
        # pre-registered success criterion
        overrun_down = oe < b_oe and p < 0.05
        recall_held = drecall >= -RECALL_TOL
        if overrun_down and recall_held:
            verdict = "SUCCESS (calibration)"
        elif oe < b_oe and not recall_held:
            verdict = "suppression (recall breached)"
        elif oe < b_oe:
            verdict = "overrun↓ but n.s."
        else:
            verdict = "no effect"
        scope_specific = (oe < b_oe) and (di >= b_di - 1e-9)
        tag = "  [scope-specific]" if scope_specific and oe < b_oe else \
              ("  [general-carefulness]" if oe < b_oe and di < b_di else "")
        print(f"{arm:12s} {f'{oe:.0%}':>11} {drecall:+8.2f} {p:10.3f} "
              f"{f'{di:.0%}':>10} {pf:5.2f} {fl:5.1f}  {verdict}{tag}")
        results.append({"arm": arm, "overeager": oe, "drecall": drecall,
                        "mcnemar_p": p, "distractor": di, "perf": pf, "flag": fl,
                        "verdict": verdict})

    json.dump({"baseline": {"overeager": b_oe, "recall": b_rc, "distractor": b_di,
                            "perf": b_pf}, "arms": results},
              open(os.path.join(RES, "step5_summary.json"), "w"), indent=2)
    print(f"\nRecall tolerance (pre-registered): drop <= {RECALL_TOL:.2f}.")
    print("SUCCESS = over-eager down (McNemar p<0.05) AND recall held.")


if __name__ == "__main__":
    main()
