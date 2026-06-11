"""
step5_probe_rank.py — re-analysis (no model): does the high boundary AUC (0.877)
translate to an OFF-DIAGONAL operating point under RANK-based selection?

The global-threshold sweep (step5_probe) failed because phi's P(IN) is saturated
near 1.0 (poor absolute calibration). But AUC measures RANKING, which was good.
So test per-task rank-based selection on the cached P(IN):
  - oracle top-n_in (upper bound: select the n_in highest-P(IN) items),
  - deploy-realistic: per-task largest-gap cut in sorted P(IN).
Report (over-eager rate, in-scope recall) for each vs baseline 72% / 0.54.
"""
import os, json
from slicer import make_task
from menu_harness import build_menu, score_menu

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.normpath(os.path.join(HERE, "..", "results"))


def main():
    probe = json.load(open(os.path.join(RES, "step5_probe_raw.json")))
    tasks = json.load(open(os.path.join(RES, "step3_taskset.json")))

    strategies = {"oracle_top_n_in": [], "gap_cut": [], "greedy_argmax": []}
    for c in tasks:
        rid, i, j = c["recipe_id"], c["i"], c["j"]
        key = f"{rid}__{i}_{j}"
        if key not in probe:
            continue
        t = make_task(rid, i, j); menu = build_menu(t)
        n_in = sum(1 for m in menu if m.kind == "inscope")
        pin = {lab: probe[key][lab]["p_in"] for lab in probe[key]}
        ranked = sorted(pin, key=lambda l: pin[l], reverse=True)

        # (1) oracle top-n_in
        sel_oracle = set(ranked[:n_in])
        # (2) deploy-realistic: cut at the largest gap in sorted P(IN)
        gaps = [(pin[ranked[k]] - pin[ranked[k+1]], k+1) for k in range(len(ranked)-1)]
        cut = max(gaps)[1] if gaps else len(ranked)
        sel_gap = set(ranked[:cut])
        # (3) greedy argmax = chosen IN (the C1 behaviour, for reference)
        sel_greedy = {lab for lab in probe[key] if probe[key][lab]["chosen"].strip().upper() == "IN"}

        for name, sel in [("oracle_top_n_in", sel_oracle), ("gap_cut", sel_gap),
                          ("greedy_argmax", sel_greedy)]:
            s = score_menu(t, menu, sel)
            strategies[name].append((s.n_overeager > 0, s.coverage))

    print(f"baseline (one-shot select): over-eager 72%  recall 0.54\n")
    print(f"{'strategy':18s} {'over-eager':>11} {'recall':>8}  off-diagonal?")
    for name, rows in strategies.items():
        oe = sum(a for a, _ in rows)/len(rows)
        rc = sum(b for _, b in rows)/len(rows)
        off = oe <= 0.55 and rc >= 0.49
        print(f"{name:18s} {oe:11.0%} {rc:8.2f}  {'YES — OFF DIAGONAL' if off else 'no'}")
    print("\noracle_top_n_in uses ground-truth n_in (upper bound on rank quality);")
    print("gap_cut is deploy-realistic (no oracle). AUC=0.877 from step5_probe.json.")


if __name__ == "__main__":
    main()
