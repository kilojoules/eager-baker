"""
step2_firmup.py — Handoff 1: power up §2 (consequence-blindness).

Tests, per model and pooled (Mantel-Haenszel, model-stratified), whether
over-eager rate differs between coupled (destructive next-step) and benign tasks.
Reports effect size, CI, and ACHIEVED POWER. A model "eases off" iff coupled rate
< benign rate; the DIAGNOSIS finding was the opposite (no easing / scope-blind).
"""
import os, json, glob, math
import scipy.stats as st

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.normpath(os.path.join(HERE, "..", "results"))


def wilson(k, n, z=1.96):
    if n == 0:
        return (float('nan'),)*2
    p = k/n; d = 1+z*z/n; c = (p+z*z/(2*n))/d
    h = z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return (max(0, c-h), min(1, c+h))


def newcombe(k1, n1, k2, n2, z=1.96):
    l1, u1 = wilson(k1, n1, z); l2, u2 = wilson(k2, n2, z)
    p1, p2 = k1/n1, k2/n2
    return ((p1-p2) - math.sqrt((p1-l1)**2+(u2-p2)**2),
            (p1-p2) + math.sqrt((u1-p1)**2+(p2-l2)**2))


def two_prop_power(p1, p2, n1, n2, alpha=0.05):
    """Power of a two-sided two-proportion z-test (unequal n)."""
    pbar = (p1*n1+p2*n2)/(n1+n2)
    se0 = math.sqrt(pbar*(1-pbar)*(1/n1+1/n2))
    se1 = math.sqrt(p1*(1-p1)/n1 + p2*(1-p2)/n2)
    if se1 == 0:
        return float('nan')
    za = st.norm.ppf(1-alpha/2)
    z = (abs(p1-p2) - za*se0)/se1
    return st.norm.cdf(z)


def load():
    tags = {f"{t['recipe_id']}__{t['i']}_{t['j']}": t.get("tag")
            for t in json.load(open(os.path.join(RES, "step3_taskset_tagged.json")))}
    models = {}
    for f in sorted(glob.glob(os.path.join(RES, "step3", "results_*.json"))):
        rows = json.load(open(f))
        for r in rows:
            i, j = r["slice_steps"].split("-")
            r["tag"] = tags.get(f"{r['recipe_id']}__{i}_{j}")
        models[rows[0]["model"]] = rows
    return models


def main():
    models = load()
    names = list(models)
    print("§2 FIRM-UP — over-eager rate: coupled (destructive next-step) vs benign\n")

    strata = []   # (a,b,c,d) per model: a=coupled&oe, b=coupled&not, c=benign&oe, d=benign&not
    print(f"{'model':16s} {'coupled oe':>14} {'benign oe':>14} {'diff(c-b)':>10} "
          f"{'95% CI':>16} {'Fisher p':>9}")
    for m in names:
        rows = models[m]
        cp = [r for r in rows if r["tag"] == "coupled"]
        bn = [r for r in rows if r["tag"] == "benign"]
        a = sum(r["n_overeager"] > 0 for r in cp); b = len(cp)-a
        c = sum(r["n_overeager"] > 0 for r in bn); d = len(bn)-c
        strata.append((a, b, c, d))
        pc, pb = a/len(cp), c/len(bn)
        lo, hi = newcombe(a, len(cp), c, len(bn))
        _, p = st.fisher_exact([[a, b], [c, d]])
        print(f"{m:16s} {f'{a}/{len(cp)}={pc:.0%}':>14} {f'{c}/{len(bn)}={pb:.0%}':>14} "
              f"{pc-pb:+10.0%} {f'[{lo:+.0%},{hi:+.0%}]':>16} {p:9.2f}")

    # ---- Mantel-Haenszel pooled across models (strata) ----
    num_or = sum(a*d/(a+b+c+d) for (a, b, c, d) in strata)
    den_or = sum(b*c/(a+b+c+d) for (a, b, c, d) in strata)
    mh_or = num_or/den_or if den_or else float('inf')
    # MH chi-square (with continuity correction)
    sum_a = sum(a for a, b, c, d in strata)
    sum_ea = sum((a+b)*(a+c)/(a+b+c+d) for a, b, c, d in strata)
    sum_v = sum((a+b)*(c+d)*(a+c)*(b+d)/((a+b+c+d)**2*(a+b+c+d-1))
                for a, b, c, d in strata if (a+b+c+d) > 1)
    mh_chi = (abs(sum_a-sum_ea)-0.5)**2/sum_v if sum_v else float('nan')
    mh_p = 1-st.chi2.cdf(mh_chi, 1)
    print(f"\nMantel-Haenszel (model-stratified) common OR = {mh_or:.2f}  "
          f"chi2={mh_chi:.2f}  p={mh_p:.2f}")
    print("  (OR>1 => coupled MORE over-eager than benign, i.e. NO easing off.)")

    # ---- achieved power ----
    nc = sum(a+b for a, b, c, d in strata)   # total coupled cells (3 models x5)
    nb = sum(c+d for a, b, c, d in strata)   # total benign cells
    pooled_c = sum_a/nc
    pooled_b = sum(c for a, b, c, d in strata)/nb
    print(f"\nPooled: coupled {sum_a}/{nc}={pooled_c:.0%}  benign "
          f"{sum(c for a,b,c,d in strata)}/{nb}={pooled_b:.0%}")
    for delta in (0.20, 0.25, 0.30):
        # power to detect an EASING-OFF of `delta` (coupled = benign - delta)
        pw = two_prop_power(max(0.001, pooled_b-delta), pooled_b, nc, nb)
        print(f"  achieved power to detect coupled = benign-{delta:.0%} "
              f"easing-off: {pw:.0%}")
    print("\nVERDICT INPUT: if power to detect a meaningful easing-off is low AND the "
          "observed direction is OR>=1, §2 'no easing off' is SUGGESTED but "
          "UNDERPOWERED -> Tier 2 (more coupled tasks) needed to confirm at power.")


if __name__ == "__main__":
    main()
