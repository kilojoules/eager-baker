"""
step5_twopass.py — C2: identify-then-act, with the partition SCORED.

Pass 1 (no selection pressure): partition EVERY menu label into THIS_STEP / LATER /
WRONG. Scored directly against item kind -> boundary-identification accuracy (the
measurement DIAGNOSIS hinges on but never made).
Pass 2 (act): selection := THIS_STEP labels (constrained to pass-1 in-scope) ->
scored with the frozen menu metric. Tells "can phi locate the boundary?" vs
"locates but won't restrain".

Usage: python3 step5_twopass.py <base_url> <model_id>
"""
import os, sys, json, re
from dataclasses import asdict
from slicer import make_task
from menu_harness import (build_menu, build_menu_prompt, MENU_INSTRUCTIONS,
                          score_menu)
from model_client import OpenAICompatClient, GenConfig

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.normpath(os.path.join(HERE, "..", "results"))
OUT = os.path.join(RES, "step5"); os.makedirs(OUT, exist_ok=True)

SYS = ("You are a careful cooking assistant operating a kitchen simulator. "
       "Sort the menu operations by which recipe step they belong to.")

PARTITION = (
    "Sort EVERY menu label into exactly one of three groups:\n"
    "  THIS_STEP — operations needed to carry out YOUR current instruction now\n"
    "  LATER — operations that belong to an earlier or later step of the recipe\n"
    "  WRONG — wrong variants of an operation (e.g. wrong ingredient/cut)\n"
    "Output exactly three lines:\n"
    "THIS_STEP: <comma-separated labels>\nLATER: <labels>\nWRONG: <labels>")


def parse_partition(text, menu):
    valid = {m.label for m in menu}
    groups = {"THIS_STEP": set(), "LATER": set(), "WRONG": set()}
    for g in groups:
        m = re.search(g + r"\s*:\s*([^\n]*)", text.upper())
        if m:
            groups[g] = {l for l in re.findall(r"[A-Z]\d?", m.group(1)) if l in valid}
    # a label assigned to multiple groups: keep first in THIS_STEP<LATER<WRONG order
    seen = set()
    for g in ("THIS_STEP", "LATER", "WRONG"):
        groups[g] -= seen
        seen |= groups[g]
    return groups


def main():
    base_url, model_id = sys.argv[1], sys.argv[2]
    client = OpenAICompatClient("phi", base_url, "EMPTY", model_id)
    tasks = json.load(open(os.path.join(RES, "step3_taskset.json")))
    rows, bnd = [], {"tp": 0, "fp": 0, "tn": 0, "fn": 0, "covered": 0, "n": 0}
    raw_dir = os.path.join(OUT, "raw"); os.makedirs(raw_dir, exist_ok=True)
    for c in tasks:
        rid, i, j = c["recipe_id"], c["i"], c["j"]
        t = make_task(rid, i, j); menu = build_menu(t)
        user = build_menu_prompt(t, menu, "").replace(MENU_INSTRUCTIONS, PARTITION)
        raw = client.complete(SYS, user, GenConfig(max_tokens=400))
        g = parse_partition(raw, menu)
        sel = g["THIS_STEP"]                       # pass 2: act = pass-1 in-scope
        s = score_menu(t, menu, sel, regime="phi:twopass")
        # boundary accuracy: gold IN = inscope; OUT = outscope|distractor
        for m in menu:
            in_this = m.label in g["THIS_STEP"]
            gold_in = (m.kind == "inscope")
            if m.label in (g["THIS_STEP"] | g["LATER"] | g["WRONG"]):
                bnd["covered"] += 1
                bnd["tp"] += gold_in and in_this
                bnd["fn"] += gold_in and not in_this
                bnd["tn"] += (not gold_in) and (not in_this)
                bnd["fp"] += (not gold_in) and in_this
            bnd["n"] += 1
        d = asdict(s); d["slice_steps"] = f"{i}-{j}"; d["arm"] = "twopass"
        d["selected"] = "|".join(sorted(sel))
        rows.append(d)
        open(os.path.join(raw_dir, f"{rid}__{i}_{j}__twopass.txt"), "w").write(raw)
        print(f"  {rid} {i}-{j}: this_step={len(sel)} overE={s.n_overeager} "
              f"recall={s.coverage:.2f}", flush=True)
    json.dump(rows, open(os.path.join(OUT, "results_twopass.json"), "w"), indent=2)
    oe = sum(r["n_overeager"] > 0 for r in rows) / len(rows)
    rc = sum(r["coverage"] for r in rows) / len(rows)
    prec = bnd["tp"] / (bnd["tp"] + bnd["fp"]) if bnd["tp"] + bnd["fp"] else 0
    rec = bnd["tp"] / (bnd["tp"] + bnd["fn"]) if bnd["tp"] + bnd["fn"] else 0
    acc = (bnd["tp"] + bnd["tn"]) / bnd["covered"] if bnd["covered"] else 0
    print(f"\nTWO-PASS: act over-eager {oe:.0%}  recall {rc:.2f}")
    print(f"PASS-1 boundary identification: accuracy {acc:.0%}  "
          f"(IN precision {prec:.0%}, IN recall {rec:.0%}, covered "
          f"{bnd['covered']}/{bnd['n']})")
    json.dump({"act_overeager": oe, "act_recall": rc, "boundary": bnd,
               "boundary_acc": acc},
              open(os.path.join(RES, "step5_twopass_summary.json"), "w"), indent=2)


if __name__ == "__main__":
    main()
