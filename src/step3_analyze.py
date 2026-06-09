"""
step3_analyze.py — pre-registered analysis (STEP3_ANALYSIS_PLAN.md).

Primary: between-model difference in OVER-EAGER RATE (tasks with >=1 over-eager
selection). Omnibus + pairwise Fisher's exact (Holm), with rate differences,
95% CIs (Newcombe), odds ratios. Secondary: signed-scope, performance, timidity
per model. Coupled/benign split (descriptive). Reports achieved power + MDE.
"""
import os, json, glob, math, itertools
import scipy.stats as st

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.normpath(os.path.join(HERE, "..", "results"))
S3 = os.path.join(RES, "step3")


def wilson(k, n, z=1.959963985):
    if n == 0:
        return (float('nan'), float('nan'))
    p = k / n
    d = 1 + z*z/n
    c = (p + z*z/(2*n)) / d
    h = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / d
    return (max(0, c-h), min(1, c+h))


def newcombe_diff(k1, n1, k2, n2, z=1.959963985):
    """Newcombe method 10 CI for p1 - p2."""
    l1, u1 = wilson(k1, n1, z)
    l2, u2 = wilson(k2, n2, z)
    p1, p2 = k1/n1, k2/n2
    lo = (p1 - p2) - z*0  # placeholder; use the square-root combination:
    lo = (p1 - p2) - math.sqrt((p1-l1)**2 + (u2-p2)**2)
    hi = (p1 - p2) + math.sqrt((u1-p1)**2 + (p2-l2)**2)
    return (lo, hi)


def mean_ci(xs, z=1.959963985):
    xs = [x for x in xs if x is not None]
    if not xs:
        return (float('nan'), float('nan'), float('nan'))
    m = sum(xs)/len(xs)
    if len(xs) < 2:
        return (m, m, m)
    sd = (sum((x-m)**2 for x in xs)/(len(xs)-1))**0.5
    se = sd/math.sqrt(len(xs))
    return (m, m - z*se, m + z*se)


def load():
    tags = {f"{t['recipe_id']}__{t['i']}_{t['j']}": t.get("tag", "unknown")
            for t in json.load(open(os.path.join(RES, "step3_taskset_tagged.json")))} \
        if os.path.exists(os.path.join(RES, "step3_taskset_tagged.json")) else {}
    models = {}
    for f in sorted(glob.glob(os.path.join(S3, "results_*.json"))):
        rows = json.load(open(f))
        for r in rows:
            r["key"] = f"{r['recipe_id']}__{r['slice_steps'].replace('-', '_')}"
            r["tag"] = tags.get(r["key"], "unknown")
        models[rows[0]["model"]] = rows
    return models, tags


def oe_rate(rows):
    k = sum(1 for r in rows if r["n_overeager"] > 0)
    return k, len(rows)


def main():
    models, tags = load()
    names = list(models)
    print(f"Models: {names}")
    print(f"Tasks/model: {[len(models[m]) for m in names]}")
    print(f"Coupled/benign tags loaded: {sum(1 for v in tags.values() if v=='coupled')} coupled, "
          f"{sum(1 for v in tags.values() if v=='benign')} benign, "
          f"{sum(1 for v in tags.values() if v=='unknown')} unknown\n")

    # ---- PRIMARY: over-eager rate ----
    print("="*72); print("PRIMARY — over-eager rate (tasks with >=1 over-eager selection)")
    print("="*72)
    rates = {}
    for m in names:
        k, n = oe_rate(models[m])
        lo, hi = wilson(k, n)
        rates[m] = (k, n)
        print(f"  {m:22s} {k}/{n} = {k/n:.0%}   95% CI [{lo:.0%}, {hi:.0%}]")

    if len(names) >= 2:
        # omnibus: chi-square on models x {oe, not}
        table = [[rates[m][0], rates[m][1]-rates[m][0]] for m in names]
        try:
            chi2, p_omni, dof, _ = st.chi2_contingency(table)
            print(f"\n  Omnibus chi-square: chi2={chi2:.2f} dof={dof} p={p_omni:.3f}")
        except Exception as e:
            print(f"\n  Omnibus chi-square failed: {e}")
        # pairwise Fisher + Holm
        print("\n  Pairwise (Fisher's exact, Holm-corrected):")
        pairs = list(itertools.combinations(names, 2))
        raw = []
        for a, b in pairs:
            ka, na = rates[a]; kb, nb = rates[b]
            odds, p = st.fisher_exact([[ka, na-ka], [kb, nb-kb]])
            dlo, dhi = newcombe_diff(ka, na, kb, nb)
            raw.append((a, b, ka/na, kb/nb, dlo, dhi, odds, p))
        # Holm
        order = sorted(range(len(raw)), key=lambda i: raw[i][7])
        holm = [None]*len(raw)
        for rank, i in enumerate(order):
            holm[i] = min(1.0, raw[i][7]*(len(raw)-rank))
        for i, (a, b, pa, pb, dlo, dhi, odds, p) in enumerate(raw):
            print(f"    {a} vs {b}: {pa:.0%} vs {pb:.0%}  "
                  f"diff={pa-pb:+.0%} [95% CI {dlo:+.0%},{dhi:+.0%}]  "
                  f"OR={odds:.2f}  p={p:.3f}  p_holm={holm[i]:.3f}")

    # ---- SECONDARY ----
    print("\n" + "="*72); print("SECONDARY — per model"); print("="*72)
    print(f"  {'model':22s} {'mean_perf':>10} {'mean_signed (95% CI)':>26} "
          f"{'timid_rate':>10} {'mean_dropP':>10}")
    for m in names:
        rows = models[m]
        perf = mean_ci([r["performance"] for r in rows])[0]
        ms, slo, shi = mean_ci([r["signed_scope"] for r in rows])
        timid = sum(1 for r in rows if r["timidity_norm"] > 0)/len(rows)
        dropp = sum(r["dropped_preconditions"] for r in rows)/len(rows)
        print(f"  {m:22s} {perf:10.2f} {f'{ms:+.2f} [{slo:+.2f},{shi:+.2f}]':>26} "
              f"{timid:10.0%} {dropp:10.2f}")

    # ---- COUPLED/BENIGN split (descriptive) ----
    print("\n" + "="*72)
    print("COUPLED vs BENIGN — over-eager rate (descriptive; subsets small)")
    print("="*72)
    for m in names:
        rows = models[m]
        for tg in ("coupled", "benign"):
            sub = [r for r in rows if r["tag"] == tg]
            if sub:
                k = sum(1 for r in sub if r["n_overeager"] > 0)
                print(f"  {m:22s} {tg:8s}: {k}/{len(sub)} = {k/len(sub):.0%}")

    print("\n" + "="*72)
    print("POWER: n=50/model -> 80% power for ~25 pp gap (MDE). A null = "
          "'no gap >= ~25pp at n=50', NOT 'no difference'.")

    # save combined CSV
    import csv
    allrows = [r for m in names for r in models[m]]
    cols = ["model", "recipe_id", "slice_steps", "tag", "performance",
            "signed_scope", "timidity_norm", "over_eagerness_norm", "n_overeager",
            "dropped_preconditions", "n_inscope_total", "n_outscope_total",
            "selected", "category"]
    with open(os.path.join(RES, "step3_results.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(cols)
        for r in allrows:
            w.writerow([r.get(c) for c in cols])
    print(f"\nwrote {os.path.join(RES,'step3_results.csv')} ({len(allrows)} rows)")


if __name__ == "__main__":
    main()
