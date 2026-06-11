"""
step5_crossmodel.py — calibration-gradient test across models (no model calls;
reads cached per-item IN/OUT logprobs from step5_probe_raw_<name>.json).

For each model reports, to separate KNOWLEDGE from CALIBRATION:
  * boundary AUC                 — ranking quality ("does it KNOW the boundary?")
  * median P(IN) for OUT items   — saturation/over-confidence (calibration)
  * optimal logit decision point — where greedy SHOULD threshold (0=calibrated,
                                    large=over-confident)
  * greedy over-eager rate       — overstep at the DEFAULT decision point (P>0.5)
  * best off-diagonal over-eager — overstep after recalibration (global logit thr)
  * recalibration gap            — greedy minus best (how much is decoding-fixable)

Calibration gradient  => AUC ~equal across models, saturation/greedy-overeager
                         falls with model size, best-threshold overstep converges.
Knowledge gradient    => AUC rises with model size.
"""
import os, json, math, glob
from statistics import median
from slicer import make_task
from menu_harness import build_menu, score_menu

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.normpath(os.path.join(HERE, "..", "results"))


def logit(p):
    p = min(max(p, 1e-9), 1 - 1e-9)
    return math.log(p / (1 - p))


def op_at(objs, ld, thr):
    oe = rc = n = 0
    for key, (t, menu) in objs.items():
        if key not in ld:
            continue
        sel = {l for l, v in ld[key].items() if v >= thr}
        s = score_menu(t, menu, sel)
        oe += (s.n_overeager > 0); rc += s.coverage; n += 1
    return oe / n, rc / n


def analyse(name, raw, objs):
    pos = [d["p_in"] for k in raw for d in raw[k].values() if d["gold"] == "IN"]
    neg = [d["p_in"] for k in raw for d in raw[k].values() if d["gold"] == "OUT"]
    auc = sum((a > b) + 0.5 * (a == b) for a in pos for b in neg) / (len(pos) * len(neg))
    ld = {k: {l: logit(d["p_in"]) for l, d in raw[k].items()} for k in raw}
    grid = sorted({v for d in ld.values() for v in d.values()})
    grid = [grid[int(q * (len(grid) - 1))] for q in [i / 60 for i in range(61)]]
    # greedy = threshold at logit 0 (P>0.5)
    g_oe, g_rc = op_at(objs, ld, 0.0)
    # best off-diagonal (over-eager minimised subject to recall>=0.49)
    best = None
    for thr in grid:
        oe, rc = op_at(objs, ld, thr)
        if rc >= 0.49 and (best is None or oe < best[1]):
            best = (thr, oe, rc)
    # optimal decision point: threshold maximising boundary accuracy (Youden-ish)
    best_acc, opt_thr = -1, 0
    for thr in grid:
        tp = sum(v >= thr and raw[k][l]["gold"] == "IN"
                 for k in ld for l, v in ld[k].items())
        tn = sum(v < thr and raw[k][l]["gold"] == "OUT"
                 for k in ld for l, v in ld[k].items())
        acc = (tp + tn) / sum(len(d) for d in ld.values())
        if acc > best_acc:
            best_acc, opt_thr = acc, thr
    # over-confidence on OUT items: fraction greedy (P>0.5) wrongly accepts
    frac_out_greedy_in = sum(d["p_in"] > 0.5 for k in raw for d in raw[k].values()
                             if d["gold"] == "OUT") / max(1, len(neg))
    return {"name": name, "auc": auc, "frac_OUT_greedyIN": frac_out_greedy_in,
            "opt_logit_thr": opt_thr, "greedy_oe": g_oe, "greedy_rc": g_rc,
            "best_oe": best[1] if best else None, "best_rc": best[2] if best else None,
            "recal_gap": (g_oe - best[1]) if best else None}


def main():
    tasks = json.load(open(os.path.join(RES, "step3_taskset.json")))
    objs = {}
    for c in tasks:
        rid, i, j = c["recipe_id"], c["i"], c["j"]
        t = make_task(rid, i, j)
        objs[f"{rid}__{i}_{j}"] = (t, build_menu(t))

    order = {"qwen3": 0, "qwen25": 1, "phi": 2}   # big -> small
    rows = []
    for f in glob.glob(os.path.join(RES, "step5_probe_raw_*.json")):
        name = os.path.basename(f)[len("step5_probe_raw_"):-len(".json")]
        rows.append(analyse(name, json.load(open(f)), objs))
    rows.sort(key=lambda r: order.get(r["name"], 9))

    print("CROSS-MODEL boundary read-out (big -> small):\n")
    print(f"{'model':8s} {'AUC':>6} {'%OUT>.5':>8} {'optLogitThr':>11} "
          f"{'greedy o-e':>11} {'best o-e':>9} {'recal gap':>9}")
    for r in rows:
        print(f"{r['name']:8s} {r['auc']:6.2f} {r['frac_OUT_greedyIN']:8.0%} "
              f"{r['opt_logit_thr']:11.1f} "
              f"{r['greedy_oe']:10.0%} {(r['best_oe'] or 0):9.0%} "
              f"{(r['recal_gap'] or 0):9.0%}")
    json.dump(rows, open(os.path.join(RES, "step5_crossmodel.json"), "w"), indent=2)
    print("\nReading: AUC ~equal + saturation(medP|OUT, optThr, greedy o-e) falling "
          "with size => CALIBRATION gradient. AUC rising with size => knowledge.")


if __name__ == "__main__":
    main()
