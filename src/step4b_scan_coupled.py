"""
step4b_scan_coupled.py — Tier 2: deliberately find more COUPLED tasks.

Scans single- and two-step slices across the 30 recipes (deduped vs the existing
50-task set), simulator-tagging each (windowless, stdin detached). A slice is
coupled iff some next-step op lowers its baseline DAS (early-stop on first hit).
Collects up to TARGET new coupled tasks. Model-free.
"""
import os, json, random
from concurrent.futures import ThreadPoolExecutor, as_completed
from slicer import make_task, list_recipes, _xml_path
from mcl import parse_gold_xml
from menu_harness import build_menu
from step4_tag import run_eval_single, EPS

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.normpath(os.path.join(HERE, "..", "results"))
TARGET_NEW_COUPLED = 22
MAX_SCAN = 170
MAX_NEXTOPS = 16        # cap next-ops checked per candidate (cost bound; logged)


def candidate_slices():
    existing = {(c["recipe_id"], c["i"], c["j"])
                for c in json.load(open(os.path.join(RES, "step3_taskset.json")))}
    cands = []
    for rid in list_recipes():
        _, meta = parse_gold_xml(_xml_path(rid))
        n = len([s for s in meta["steps"] if s["kind"] == "instruction"])
        windows = [(k, k) for k in range(1, n+1)] + [(k, k+1) for k in range(1, n)]
        for i, j in windows:
            if (rid, i, j) in existing:
                continue
            try:
                t = make_task(rid, i, j)
            except ValueError:
                continue
            if not t.out_of_scope_ops:
                continue
            if sum(1 for m in build_menu(t) if m.kind == "distractor") < 1:
                continue
            cands.append((rid, i, j))
    return cands


def tag_one(rid, i, j):
    """Return dict with tag/coupled info, or None if unscoreable baseline."""
    t = make_task(rid, i, j)
    prefix = t.kitchen_state["prefix_network"]
    base_net = "#%s\n%s" % (rid, "\n".join(
        prefix + [o["sexp"] for o in t.in_scope_ops]))
    base = run_eval_single(base_net, timeout=120)
    if base is None:
        return None
    n_checked = 0
    for k, o in enumerate(t.out_of_scope_ops[:MAX_NEXTOPS]):
        net = "#%s\n%s" % (rid, "\n".join(
            prefix + [x["sexp"] for x in t.in_scope_ops] + [o["sexp"]]))
        das = run_eval_single(net, timeout=120)
        n_checked += 1
        if das is not None and das - base < -EPS:
            return {"recipe_id": rid, "i": i, "j": j, "tag": "coupled",
                    "das_baseline": round(base, 3),
                    "destructive_op_idx": k, "das_after": round(das, 3),
                    "n_in": len(t.in_scope_ops), "n_out": len(t.out_of_scope_ops)}
    return {"recipe_id": rid, "i": i, "j": j, "tag": "benign",
            "das_baseline": round(base, 3), "n_checked": n_checked,
            "n_in": len(t.in_scope_ops), "n_out": len(t.out_of_scope_ops)}


def main():
    cands = candidate_slices()
    random.seed(0)
    random.shuffle(cands)
    cands = cands[:MAX_SCAN]
    print(f"scanning {len(cands)} candidate slices for coupling (windowless)...",
          flush=True)

    coupled, benign, unscoreable = [], [], 0
    done = 0
    ex = ThreadPoolExecutor(max_workers=6)
    futs = {ex.submit(tag_one, *c): c for c in cands}
    for fut in as_completed(futs):
        r = fut.result()
        done += 1
        if r is None:
            unscoreable += 1
        elif r["tag"] == "coupled":
            coupled.append(r)
        else:
            benign.append(r)
        if done % 20 == 0:
            print(f"  {done}/{len(cands)} scanned | coupled={len(coupled)} "
                  f"benign={len(benign)} unscoreable={unscoreable}", flush=True)
        if len(coupled) >= TARGET_NEW_COUPLED:
            print(f"  reached target {TARGET_NEW_COUPLED} coupled at "
                  f"{done} scanned", flush=True)
            break
    ex.shutdown(wait=False, cancel_futures=True)

    json.dump({"coupled": coupled, "benign": benign, "n_unscoreable": unscoreable,
               "n_scanned": done},
              open(os.path.join(RES, "step3_coupled_extra.json"), "w"), indent=2)
    print(f"\nFOUND {len(coupled)} new coupled, {len(benign)} benign, "
          f"{unscoreable} unscoreable (of {done} scanned)")
    print("coupled:", [(c['recipe_id'], c['i'], c['j']) for c in coupled])


if __name__ == "__main__":
    main()
