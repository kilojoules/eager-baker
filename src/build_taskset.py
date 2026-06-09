"""build_taskset.py — §3: assemble the 50-task set for Step 3.

Per task: non-empty out-of-scope set AND >=1 menu distractor (so both axes have
signal). Single-step instruction slices (non-overlapping within a recipe), selected
round-robin across the 30 recipes for spread. Reports distractor coverage.
"""
import os, json
from slicer import make_task, list_recipes
from mcl import parse_gold_xml
from slicer import _xml_path
from menu_harness import build_menu

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.normpath(os.path.join(HERE, "..", "results"))
N_TARGET = 50


def candidates():
    """All single-step instruction slices passing the filters, grouped by recipe."""
    by_recipe = {}
    for rid in list_recipes():
        _, meta = parse_gold_xml(_xml_path(rid))
        n_instr = len([s for s in meta["steps"] if s["kind"] == "instruction"])
        cands = []
        for k in range(1, n_instr + 1):
            try:
                t = make_task(rid, k, k)
            except ValueError:
                continue
            if not t.out_of_scope_ops:
                continue
            menu = build_menu(t)
            n_dist = sum(1 for m in menu if m.kind == "distractor")
            if n_dist < 1:
                continue
            cands.append({"recipe_id": rid, "i": k, "j": k,
                          "n_in": len(t.in_scope_ops),
                          "n_out": len(t.out_of_scope_ops),
                          "n_distractor": n_dist, "n_menu": len(menu)})
        if cands:
            by_recipe[rid] = cands
    return by_recipe


def main():
    by_recipe = candidates()
    total_cand = sum(len(v) for v in by_recipe.values())
    print(f"{total_cand} candidate slices across {len(by_recipe)} recipes "
          f"(all pass: nonempty out-of-scope + >=1 distractor)")

    # round-robin select N_TARGET across recipes for spread
    chosen = []
    pools = {r: list(v) for r, v in by_recipe.items()}
    order = sorted(pools)
    idx = 0
    while len(chosen) < N_TARGET and any(pools.values()):
        r = order[idx % len(order)]
        if pools[r]:
            chosen.append(pools[r].pop(0))
        idx += 1
        if idx > 100000:
            break

    chosen = chosen[:N_TARGET]
    with open(os.path.join(RES, "step3_taskset.json"), "w") as f:
        json.dump(chosen, f, indent=2)

    n_recipes = len({c["recipe_id"] for c in chosen})
    print(f"\nSELECTED {len(chosen)} tasks across {n_recipes} recipes")
    print(f"  distractor coverage: all {len(chosen)}/{len(chosen)} have >=1 distractor "
          f"(min={min(c['n_distractor'] for c in chosen)}, "
          f"max={max(c['n_distractor'] for c in chosen)})")
    print(f"  in-scope size: min={min(c['n_in'] for c in chosen)} "
          f"max={max(c['n_in'] for c in chosen)}")
    print(f"  out-scope size: min={min(c['n_out'] for c in chosen)} "
          f"max={max(c['n_out'] for c in chosen)}")
    tot_outops = sum(c["n_out"] for c in chosen)
    print(f"  total out-of-scope ops across tasks = {tot_outops} "
          f"(≈ §4 simulator runs: {tot_outops + len(chosen)})")


if __name__ == "__main__":
    main()
