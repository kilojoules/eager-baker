"""
step3_analyze.py — pre-registered analysis (STEP3_ANALYSIS_PLAN.md), now
COHORT-AWARE (see cohorts.py).

The models split into two NON-COMPARABLE cohorts: open-weights via the clean vLLM
path (pre-registered, primary) and frontier models via vendor agentic CLIs
(exploratory, harness-confounded). Statistics are computed WITHIN each cohort:
omnibus + pairwise Fisher's exact (Holm), rate differences, 95% CIs (Newcombe),
odds ratios. Cross-cohort numbers are printed DESCRIPTIVELY ONLY (no unified test),
because a between-cohort gap conflates model with harness.
"""
import os, json, glob, math, itertools
import scipy.stats as st
from cohorts import COHORTS, COHORT_ORDER, cohort_of, base_models_present

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


def cohort_overeager(models, names, family_label):
    """Print rate table + WITHIN-FAMILY omnibus chi-square + pairwise Fisher/Holm
    for exactly the given `names` (one cohort = one multiple-comparison family)."""
    rates = {}
    for m in names:
        k, n = oe_rate(models[m]); lo, hi = wilson(k, n); rates[m] = (k, n)
        print(f"  {m:22s} {k}/{n} = {k/n:.0%}   95% CI [{lo:.0%}, {hi:.0%}]")
    if len(names) < 2:
        print("  (single model in cohort — no within-cohort test)")
        return rates
    table = [[rates[m][0], rates[m][1]-rates[m][0]] for m in names]
    try:
        chi2, p_omni, dof, _ = st.chi2_contingency(table)
        print(f"\n  Omnibus chi-square ({family_label}): chi2={chi2:.2f} dof={dof} p={p_omni:.3g}")
    except Exception as e:
        print(f"\n  Omnibus chi-square failed: {e}")
    pairs = list(itertools.combinations(names, 2))
    raw = []
    for a, b in pairs:
        ka, na = rates[a]; kb, nb = rates[b]
        odds, p = st.fisher_exact([[ka, na-ka], [kb, nb-kb]])
        dlo, dhi = newcombe_diff(ka, na, kb, nb)
        raw.append((a, b, ka/na, kb/nb, dlo, dhi, odds, p))
    order = sorted(range(len(raw)), key=lambda i: raw[i][7])
    holm = [None]*len(raw)
    for rank, i in enumerate(order):
        holm[i] = min(1.0, raw[i][7]*(len(raw)-rank))
    print(f"  Pairwise (Fisher's exact, Holm over {len(raw)} contrasts in THIS cohort):")
    for i, (a, b, pa, pb, dlo, dhi, odds, p) in enumerate(raw):
        sig = "*" if holm[i] < 0.05 else " "
        print(f"   {sig} {a} vs {b}: {pa:.0%} vs {pb:.0%}  "
              f"diff={pa-pb:+.0%} [95% CI {dlo:+.0%},{dhi:+.0%}]  "
              f"OR={odds:.2f}  p={p:.3g}  p_holm={holm[i]:.3g}")
    return rates


def main():
    models, tags = load()
    present = set(models)
    print(f"Models: {base_models_present(present)}")
    print(f"Tasks/model: {[len(models[m]) for m in base_models_present(present)]}")
    print(f"Coupled/benign tags loaded: {sum(1 for v in tags.values() if v=='coupled')} coupled, "
          f"{sum(1 for v in tags.values() if v=='benign')} benign, "
          f"{sum(1 for v in tags.values() if v=='unknown')} unknown")

    # ---- PRIMARY: over-eager rate, computed SEPARATELY within each cohort ----
    print("\n" + "="*72)
    print("PRIMARY — over-eager rate, BY COHORT (each cohort is its own Holm family;")
    print("cohorts are NOT directly comparable — different harness, see cohorts.py)")
    print("="*72)
    for cid in COHORT_ORDER:
        names = [m for m in COHORTS[cid]["models"] if m in present]
        if not names:
            continue
        c = COHORTS[cid]
        print(f"\n### {c['label']}")
        print(f"    harness: {c['harness']}")
        cohort_overeager(models, names, c["short"])

    # ---- CROSS-COHORT (descriptive only; CONFOUNDED by harness) ----
    print("\n" + "="*72)
    print("CROSS-COHORT — descriptive only (NO unified test: harness-confounded)")
    print("="*72)
    for m in base_models_present(present):
        k, n = oe_rate(models[m])
        print(f"  [{COHORTS[cohort_of(m)]['short']:22s}] {m:22s} {k}/{n} = {k/n:.0%}")

    # ---- SECONDARY (per model, grouped by cohort) ----
    print("\n" + "="*72); print("SECONDARY — per model (grouped by cohort)"); print("="*72)
    print(f"  {'model':22s} {'mean_perf':>10} {'mean_signed (95% CI)':>26} "
          f"{'timid_rate':>10} {'mean_dropP':>10}")
    for cid in COHORT_ORDER:
        names = [m for m in COHORTS[cid]["models"] if m in present]
        if not names:
            continue
        print(f"  -- {COHORTS[cid]['short']} --")
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
    for m in base_models_present(present):
        rows = models[m]
        for tg in ("coupled", "benign"):
            sub = [r for r in rows if r["tag"] == tg]
            if sub:
                k = sum(1 for r in sub if r["n_overeager"] > 0)
                print(f"  {m:22s} {tg:8s}: {k}/{len(sub)} = {k/len(sub):.0%}")

    print("\n" + "="*72)
    print("POWER: n=50/model -> 80% power for ~25 pp gap (MDE). A null = "
          "'no gap >= ~25pp at n=50', NOT 'no difference'.")

    # save combined CSV (with a cohort column)
    import csv
    allrows = [r for m in base_models_present(present) for r in models[m]]
    cols = ["model", "cohort", "recipe_id", "slice_steps", "tag", "performance",
            "signed_scope", "timidity_norm", "over_eagerness_norm", "n_overeager",
            "dropped_preconditions", "n_inscope_total", "n_outscope_total",
            "selected", "category"]
    with open(os.path.join(RES, "step3_results.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(cols)
        for r in allrows:
            r["cohort"] = cohort_of(r["model"])
            w.writerow([r.get(c) for c in cols])
    print(f"\nwrote {os.path.join(RES,'step3_results.csv')} ({len(allrows)} rows)")


if __name__ == "__main__":
    main()
