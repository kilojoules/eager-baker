"""
step5_calibrate.py — deploy-realistic decoding rule (NO oracle, NO model calls).

Round-2 found the boundary is in phi's logits (AUC 0.877) but a global P(IN)
threshold was flat — because P(IN) is saturated near 1.0 and the coarse [0..1]
grid couldn't see the action. The fix: threshold on the LOGIT DIFFERENCE
(= logit(P(IN)) = IN_logprob - OUT_logprob), which is NOT saturated. This is a
single global, deployable rule (one cutoff for all tasks, no oracle n_in).

We sweep that threshold and also test two oracle-free per-task rules, and report
whether any reaches the success region (over-eager <= 55% AND recall >= 0.49).
"""
import os, json, math
from slicer import make_task
from menu_harness import build_menu, score_menu

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.normpath(os.path.join(HERE, "..", "results"))
B_OE, B_RC = 0.72, 0.54


def logit(p):
    p = min(max(p, 1e-9), 1 - 1e-9)
    return math.log(p / (1 - p))


def load():
    probe = json.load(open(os.path.join(RES, "step5_probe_raw.json")))
    tasks = json.load(open(os.path.join(RES, "step3_taskset.json")))
    items = {}    # key -> {label: logit_diff}, plus menu/task
    objs = {}
    for c in tasks:
        rid, i, j = c["recipe_id"], c["i"], c["j"]
        key = f"{rid}__{i}_{j}"
        if key not in probe:
            continue
        t = make_task(rid, i, j); menu = build_menu(t)
        objs[key] = (t, menu)
        items[key] = {lab: logit(probe[key][lab]["p_in"]) for lab in probe[key]}
    return objs, items


def operating_point(objs, items, select_fn):
    oe = rc = n = 0
    for key, (t, menu) in objs.items():
        if key not in items:
            continue
        sel = select_fn(key, items[key], menu)
        s = score_menu(t, menu, sel)
        oe += (s.n_overeager > 0); rc += s.coverage; n += 1
    return oe / n, rc / n


def main():
    objs, items = load()
    print(f"baseline: over-eager {B_OE:.0%}  recall {B_RC:.2f}\n")

    # ---- (A) GLOBAL logit-difference threshold sweep (deploy-realistic) ----
    allvals = sorted({v for d in items.values() for v in d.values()})
    grid = [allvals[int(q * (len(allvals) - 1))] for q in
            [i / 40 for i in range(41)]]
    print("(A) GLOBAL logit-diff threshold sweep  (select items with logit_diff >= thr)")
    print(f"   {'thr':>7} {'over-eager':>11} {'recall':>8}  off-diagonal?")
    best = None
    curve = []
    for thr in grid:
        oe, rc = operating_point(objs, items,
                                 lambda k, d, m, thr=thr: {l for l, v in d.items() if v >= thr})
        curve.append({"thr": thr, "overeager": oe, "recall": rc})
        off = oe <= 0.55 and rc >= 0.49
        if off and (best is None or rc - oe > best[2]):
            best = (thr, oe, rc - oe, rc)
        if abs(thr) < 0.6 or off or thr in (grid[0], grid[-1]):
            print(f"   {thr:7.2f} {oe:11.0%} {rc:8.2f}  {'YES' if off else ''}")
    print()
    if best:
        print(f"   -> BEST off-diagonal global threshold: logit_diff>={best[0]:.2f} "
              f"=> over-eager {best[1]:.0%}, recall {best[3]:.2f}")
    else:
        print("   -> no global logit-diff threshold reaches the success region")

    # ---- (B) oracle-free per-task rules ----
    print("\n(B) oracle-free per-task rules:")
    # top-fraction of items by logit_diff (f swept)
    def topfrac(key, d, menu, f):
        ranked = sorted(d, key=lambda l: d[l], reverse=True)
        k = max(1, round(f * len(ranked)))
        return set(ranked[:k])
    for f in (0.2, 0.3, 0.4):
        oe, rc = operating_point(objs, items, lambda k, d, m, f=f: topfrac(k, d, m, f))
        print(f"   top-{f:.0%} of items: over-eager {oe:.0%}  recall {rc:.2f}"
              f"  {'OFF-DIAGONAL' if oe<=0.55 and rc>=0.49 else ''}")
    # largest gap in logit space (knee)
    def kneecut(key, d, menu):
        ranked = sorted(d, key=lambda l: d[l], reverse=True)
        if len(ranked) < 2:
            return set(ranked)
        gaps = [(d[ranked[k]] - d[ranked[k + 1]], k + 1) for k in range(len(ranked) - 1)]
        cut = max(gaps)[1]
        return set(ranked[:cut])
    oe, rc = operating_point(objs, items, kneecut)
    print(f"   logit-space knee cut: over-eager {oe:.0%}  recall {rc:.2f}"
          f"  {'OFF-DIAGONAL' if oe<=0.55 and rc>=0.49 else ''}")

    # ---- (C) held-out CV: pick threshold on train half, evaluate on test half ----
    print("\n(C) held-out cross-validation (threshold NOT chosen on the test tasks):")
    keys = sorted(objs)
    folds = {"even": keys[::2], "odd": keys[1::2]}

    def op_on(subset, select_fn):
        oe = rc = n = 0
        for key in subset:
            t, menu = objs[key]
            sel = select_fn(key, items[key], menu)
            s = score_menu(t, menu, sel)
            oe += (s.n_overeager > 0); rc += s.coverage; n += 1
        return oe / n, rc / n

    def pick_thr(train):
        # choose threshold maximizing recall subject to over-eager <= 0.55 on train
        best_t, best_rc = None, -1
        for thr in grid:
            oe, rc = op_on(train, lambda k, d, m, thr=thr: {l for l, v in d.items() if v >= thr})
            if oe <= 0.55 and rc > best_rc:
                best_t, best_rc = thr, rc
        return best_t

    test_pts = []
    for name, test in folds.items():
        train = folds["odd" if name == "even" else "even"]
        thr = pick_thr(train)
        if thr is None:
            print(f"   train={'odd' if name=='even' else 'even'}: no off-diag thr")
            continue
        oe, rc = op_on(test, lambda k, d, m, thr=thr: {l for l, v in d.items() if v >= thr})
        test_pts.append((oe, rc, len(test)))
        print(f"   thr from train -> test={name} (n={len(test)}): logit_diff>={thr:.2f}"
              f"  => over-eager {oe:.0%}  recall {rc:.2f}"
              f"  {'OFF-DIAGONAL' if oe<=0.55 and rc>=0.49 else '(generalised poorly)'}")
    if test_pts:
        toe = sum(o * n for o, r, n in test_pts) / sum(n for _, _, n in test_pts)
        trc = sum(r * n for o, r, n in test_pts) / sum(n for _, _, n in test_pts)
        print(f"   POOLED held-out: over-eager {toe:.0%}  recall {trc:.2f}"
              f"  {'-> deployable (off-diagonal on UNSEEN tasks)' if toe<=0.55 and trc>=0.49 else ''}")

    json.dump({"best_global_insample": best, "curve": curve,
               "heldout_pooled": [toe, trc] if test_pts else None},
              open(os.path.join(RES, "step5_calibrate.json"), "w"), indent=2)


if __name__ == "__main__":
    main()
